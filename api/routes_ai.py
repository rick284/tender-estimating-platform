"""AI drafting: propose tender-register items from documents already read from Drive. Draft only; the estimator accepts or rejects each proposal."""
from __future__ import annotations
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

import ai_client
import ai_draft
import config
from db import get_db
from security import current_user
from services import audit, new_id, now

router = APIRouter(prefix="/api/ai", tags=["ai"])
MAX_FILES = 12


async def _org(user: dict[str, Any]) -> dict[str, Any]:
    return await get_db().orgs.find_one({"_id": user["org_id"]}) or {}


@router.get("/status")
async def status(user: dict[str, Any] = Depends(current_user)):
    org = await _org(user)
    return {"configured": ai_client.configured(), "enabled": bool(org.get("ai_enabled")), "model": config.AI_MODEL, "can_change": user.get("role") == "owner",
            "acknowledged_at": org["ai_ack_at"].isoformat() if org.get("ai_ack_at") else None, "max_files": MAX_FILES}


@router.put("/settings")
async def settings(body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    """Switch AI drafting on or off for the company. Only an owner can; switching on records that the tender text is sent to Anthropic's API."""
    if user.get("role") != "owner":
        raise HTTPException(403, "Only the company owner can switch AI drafting on or off.")
    enable = bool(body.get("enabled"))
    db = get_db()
    if enable:
        if not ai_client.configured():
            raise HTTPException(503, "AI drafting is not set up on this server yet (no Anthropic key has been added).")
        if body.get("acknowledged") is not True:
            raise HTTPException(422, "Please confirm that the text of the documents you select will be sent to Anthropic's API for drafting.")
        await db.orgs.update_one({"_id": user["org_id"]}, {"$set": {"ai_enabled": True, "ai_ack_at": now(), "ai_ack_by": user["_id"]}})
    else:
        await db.orgs.update_one({"_id": user["org_id"]}, {"$set": {"ai_enabled": False}})
    await audit(db, user, "ai.enable" if enable else "ai.disable", user["org_id"])
    return {"enabled": enable}


async def _tender(user, tender_id):
    t = await get_db().tenders.find_one({"_id": tender_id, "org_id": user["org_id"]})
    if not t:
        raise HTTPException(404, "Tender not found.")
    return t


def _public(p: dict[str, Any]) -> dict[str, Any]:
    return {"id": p["_id"], "batch": p["batch"], "kind": p["kind"], "title": p["title"], "detail": p["detail"], "impact": p["impact"], "rag": p["rag"], "basis": p["basis"],
            "evidence": p["evidence"], "status": p["status"], "problems": p["problems"], "decision": p.get("decision"), "created_at": p["created_at"].isoformat()}


@router.post("/tenders/{tender_id}/draft")
async def draft(tender_id: str, body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    if not ai_client.configured():
        raise HTTPException(503, "AI drafting is not set up on this server yet (no Anthropic key has been added).")
    if not (await _org(user)).get("ai_enabled"):
        raise HTTPException(403, "AI drafting is switched off for your company. The owner can switch it on in AI Drafting.")
    ids = [str(i) for i in body.get("file_ids", [])][:MAX_FILES]
    if not ids:
        raise HTTPException(422, f"Choose at least one document that has been read (up to {MAX_FILES}).")
    db = get_db()
    found = {d["file_id"]: d async for d in db.doc_texts.find({"org_id": user["org_id"], "tender_id": t["_id"], "file_id": {"$in": ids}})}
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(409, "Some of those documents have not been read yet. Read them on the Drive Documents page first.")
    docs = [{"file_id": f["file_id"], "name": f["name"], "revision": f.get("revision"), "pages": f["pages"]} for f in (found[i] for i in ids) if f["status"] in ("ok", "partial")]
    if not docs:
        raise HTTPException(409, "None of the chosen documents has readable text (scanned files and drawings need the drawing reader).")
    chars = sum(len(p["text"]) for d in docs for p in d["pages"])
    if chars > config.AI_MAX_INPUT_CHARS:
        raise HTTPException(413, f"That is {chars:,} characters of text; the limit for one run is {config.AI_MAX_INPUT_CHARS:,}. Choose fewer documents.")
    last = await db.revisions.find_one({"tender_id": t["_id"], "org_id": user["org_id"]}, sort=[("n", -1)])
    est = (last or {}).get("estimate", {})
    meta = {**{k: v for k, v in (est.get("meta") or {}).items() if isinstance(v, str)}, "project": t["name"], "client": t.get("client", ""), "location": t.get("location", "")}
    existing = (est.get("register") or [])
    user_msg = ai_draft.build_user_message(meta, docs, existing)
    try:
        data = await run_in_threadpool(ai_client.draft_json, ai_draft.SYSTEM, user_msg, ai_draft.SCHEMA)
    except ai_client.AIError as e:
        await audit(db, user, "ai.draft_failed", t["_id"], str(e)[:200])
        raise HTTPException(502, str(e))
    items = ai_draft.verify(data["items"][:60], docs, existing)
    batch = uuid.uuid4().hex
    stamp = now()
    docs_out = []
    for it in items:
        doc = {"_id": new_id(), "org_id": user["org_id"], "tender_id": t["_id"], "batch": batch, "created_at": stamp, "created_by": user["_id"], "model": config.AI_MODEL,
               "prompt_version": ai_draft.PROMPT_VERSION, "file_ids": [d["file_id"] for d in docs], **{k: it[k] for k in ("kind", "title", "detail", "impact", "rag", "basis", "evidence", "status", "problems")},
               "decision": None}
        docs_out.append(doc)
    if docs_out:
        await db.ai_proposals.insert_many(docs_out)
    await db.ai_batches.insert_one({"_id": batch, "org_id": user["org_id"], "tender_id": t["_id"], "created_at": stamp, "created_by": user["_id"], "model": config.AI_MODEL,
                                    "prompt_version": ai_draft.PROMPT_VERSION, "file_ids": [d["file_id"] for d in docs], "chars": chars,
                                    "coverage_notes": str(data.get("coverage_notes", ""))[:2000], "counts": {s: sum(1 for i in items if i["status"] == s) for s in ("verified", "gap", "unverified", "duplicate")}})
    await audit(db, user, "ai.draft", t["_id"], f"{len(docs)} files, {chars} chars, {len(items)} proposals")
    return {"batch": batch, "coverage_notes": str(data.get("coverage_notes", "")), "proposals": [_public(p) for p in docs_out], "files_sent": [d["name"] for d in docs]}


@router.get("/tenders/{tender_id}/proposals")
async def proposals(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    ps = await get_db().ai_proposals.find({"org_id": user["org_id"], "tender_id": t["_id"]}).sort("created_at", -1).to_list(500)
    return {"proposals": [_public(p) for p in ps]}


@router.post("/proposals/{pid}/decision")
async def decide(pid: str, body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    """accept: returns the register edit to add to the estimator's draft (nothing is saved to the estimate here).  reject: needs a short reason."""
    db = get_db()
    p = await db.ai_proposals.find_one({"_id": pid, "org_id": user["org_id"]})
    if not p:
        raise HTTPException(404, "Proposal not found.")
    d = body.get("decision")
    if d not in ("accepted", "rejected"):
        raise HTTPException(422, "Decision must be accepted or rejected.")
    if p.get("decision") and p["decision"]["decision"] != d:
        raise HTTPException(409, f"This proposal was already {p['decision']['decision']}.")
    if d == "rejected":
        reason = str(body.get("reason", "")).strip()
        if len(reason) < 3:
            raise HTTPException(422, "Give a short reason for rejecting it (it helps the platform learn what to leave out).")
        await db.ai_proposals.update_one({"_id": pid}, {"$set": {"decision": {"decision": "rejected", "reason": reason[:500], "by": user["_id"], "at": now()}}})
        await audit(db, user, "ai.reject", p["tender_id"], f"{p['kind']}: {p['title'][:80]}")
        return {"decision": "rejected"}
    if p["status"] not in ("verified", "gap"):
        raise HTTPException(409, "This proposal can't be accepted: its source quotes could not be verified against the documents." if p["status"] == "unverified"
                            else "This proposal repeats something already in the register.")
    key = (p.get("decision") or {}).get("edit_key") or "R-" + uuid.uuid4().hex[:8]
    if not p.get("decision"):
        await db.ai_proposals.update_one({"_id": pid}, {"$set": {"decision": {"decision": "accepted", "edit_key": key, "by": user["_id"], "at": now()}}})
        await audit(db, user, "ai.accept", p["tender_id"], f"{p['kind']}: {p['title'][:80]}")
    return {"decision": "accepted", "edit": ai_draft.to_edit(p, key)}
