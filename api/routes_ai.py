"""AI drafting: propose tender-register items from documents already read from Drive. Draft only; the estimator accepts or rejects each proposal."""
from __future__ import annotations
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

import ai_client
import ai_draft
import config
import drive_client
from db import get_db
from security import current_user
from routes_time import timed_ai
from services import audit, new_id, now

router = APIRouter(prefix="/api/ai", tags=["ai"])
MAX_FILES = 12
INTAKE_FILES = 20                 # parts per call in a whole-folder run
BATCH_CHARS = 300_000             # characters per call in a whole-folder run
MAX_INTAKE_BATCHES = 10          # a run over more than this is refused until the estimator narrows it


async def _org(user: dict[str, Any]) -> dict[str, Any]:
    return await get_db().orgs.find_one({"_id": user["org_id"]}) or {}


def _resolve(org: dict[str, Any]) -> tuple[Any, str, str, str] | None:
    """(provider, key, model, source) for this company, or None when no usable key exists. The company's own key always wins."""
    pid = org.get("ai_provider") or "anthropic"
    prov = ai_client.PROVIDERS.get(pid)
    if prov is None or not prov.available:
        return None
    model = (org.get("ai_model") or "").strip() or prov.default_model
    if org.get("ai_key_enc"):
        try:
            return prov, drive_client.decrypt(org["ai_key_enc"]), model, "own"
        except drive_client.DriveError:
            return None
    key = ai_client.platform_key(pid)
    return (prov, key, model, "platform") if key else None


@router.get("/status")
async def status(user: dict[str, Any] = Depends(current_user)):
    org = await _org(user)
    res = _resolve(org)
    pid = org.get("ai_provider") or "anthropic"
    prov = ai_client.PROVIDERS.get(pid) or ai_client.PROVIDERS["anthropic"]
    return {"configured": res is not None, "enabled": bool(org.get("ai_enabled")) and res is not None, "provider": prov.id, "model": (res[2] if res else (org.get("ai_model") or prov.default_model)),
            "key_source": res[3] if res else None, "key_last4": org.get("ai_key_last4", ""), "providers": ai_client.catalogue(), "can_change": user.get("role") == "owner",
            "acknowledged_at": org["ai_ack_at"].isoformat() if org.get("ai_ack_at") else None, "max_files": MAX_FILES, "max_pictures": config.TAKEOFF_MAX_PICTURES}


@router.put("/settings")
async def settings(body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    """Company AI settings (owner only): provider, model, the company's own API key (write-only, stored encrypted), and the on/off switch.
    Switching on records that the text of the documents you select is sent to the chosen provider."""
    if user.get("role") != "owner":
        raise HTTPException(403, "Only the company owner can change the AI settings.")
    db = get_db()
    org = await _org(user)
    upd: dict[str, Any] = {}
    unset: dict[str, str] = {}
    pid = str(body.get("provider") or org.get("ai_provider") or "anthropic")
    try:
        prov = ai_client.get(pid)
    except ai_client.AIError as e:
        raise HTTPException(422, str(e))
    if pid != (org.get("ai_provider") or "anthropic"):
        upd["ai_provider"] = pid
        unset.update({"ai_key_enc": "", "ai_key_last4": ""})       # a key belongs to one provider: changing provider drops it and switches AI off
        upd["ai_enabled"] = False
    if "model" in body:
        m = str(body.get("model") or "").strip()
        if len(m) > 80 or any(c.isspace() for c in m):
            raise HTTPException(422, "That model name doesn't look right.")
        upd["ai_model"] = m
    if body.get("clear_key"):
        unset.update({"ai_key_enc": "", "ai_key_last4": ""}); upd["ai_enabled"] = False
    if body.get("api_key"):
        key = str(body["api_key"]).strip()
        try:
            prov.check_key(key)
        except ai_client.AIError as e:
            raise HTTPException(422, str(e))
        upd["ai_key_enc"] = drive_client.encrypt(key); upd["ai_key_last4"] = key[-4:]
        unset.pop("ai_key_enc", None); unset.pop("ai_key_last4", None)
    if "enabled" in body:
        if body["enabled"]:
            after = {**org, **upd}
            for k in unset:
                after.pop(k, None)
            if _resolve(after) is None:
                raise HTTPException(409, "Add this company's API key for the chosen provider first.")
            if body.get("acknowledged") is not True and not org.get("ai_ack_at"):
                raise HTTPException(422, f"Please confirm that the text of the documents you select will be sent to {prov.label} for drafting.")
            upd["ai_enabled"] = True
            if body.get("acknowledged") is True:
                upd.update({"ai_ack_at": now(), "ai_ack_by": user["_id"], "ai_ack_provider": pid})
        else:
            upd["ai_enabled"] = False
    op: dict[str, Any] = {}
    if upd:
        op["$set"] = upd
    if unset:
        op["$unset"] = unset
    if op:
        await db.orgs.update_one({"_id": user["org_id"]}, op)
    await audit(db, user, "ai.settings", user["org_id"], ", ".join(sorted(k.replace("ai_", "") for k in {**upd, **unset} if k not in ("ai_key_enc",))) + (" key changed" if "ai_key_enc" in upd else ""))
    return await status(user)


@router.post("/test")
async def test_connection(user: dict[str, Any] = Depends(current_user)):
    """Free check (no tokens used) that the company's key works and the chosen model exists."""
    if user.get("role") != "owner":
        raise HTTPException(403, "Only the company owner can test the AI connection.")
    res = _resolve(await _org(user))
    if res is None:
        raise HTTPException(409, "Add this company's API key for the chosen provider first.")
    prov, key, model, _ = res
    try:
        name = await run_in_threadpool(prov.test, key, model)
    except ai_client.AIError as e:
        raise HTTPException(502, str(e))
    return {"ok": True, "model": name}


async def _tender(user, tender_id):
    t = await get_db().tenders.find_one({"_id": tender_id, "org_id": user["org_id"]})
    if not t:
        raise HTTPException(404, "Tender not found.")
    return t


def _public(p: dict[str, Any]) -> dict[str, Any]:
    return {"id": p["_id"], "batch": p["batch"], "kind": p["kind"], "title": p["title"], "detail": p["detail"], "impact": p["impact"], "rag": p["rag"], "basis": p["basis"],
            "evidence": p["evidence"], "status": p["status"], "problems": p["problems"], "decision": p.get("decision"), "created_at": p["created_at"].isoformat()}


async def _ready(user, org):
    res = _resolve(org)
    if res is None:
        raise HTTPException(503, "AI drafting is not set up for your company yet (no API key). The owner can add one in AI Drafting.")
    if not org.get("ai_enabled"):
        raise HTTPException(403, "AI drafting is switched off for your company. The owner can switch it on in AI Drafting.")
    return res


def _doc(f: dict[str, Any], pages=None) -> dict[str, Any]:
    return {"file_id": f["file_id"], "name": f["name"], "revision": f.get("revision"), "pages": f["pages"] if pages is None else pages}


def _chars(docs) -> int:
    return sum(len(p["text"]) for d in docs for p in d["pages"])


async def _existing(db, user, t, est) -> list[dict[str, Any]]:
    """Register items plus proposals already made for this tender (not rejected) so a later part of a run does not repeat an earlier one."""
    out = list(est.get("register") or [])
    async for p in db.ai_proposals.find({"org_id": user["org_id"], "tender_id": t["_id"]}):
        if (p.get("decision") or {}).get("decision") != "rejected" and p["status"] in ("verified", "gap"):
            out.append({"kind": p["kind"], "ref": "AI", "title": p["title"]})
    return out


@router.get("/tenders/{tender_id}/intake/plan")
async def intake_plan(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    """Whole-folder intake: every read, latest, non-archive document with text, split into parts that each fit one AI call.  Nothing is sent here."""
    t = await _tender(user, tender_id)
    db = get_db()
    ds = await db.doc_texts.find({"org_id": user["org_id"], "tender_id": t["_id"]}).sort("name", 1).to_list(2000)
    use, skipped = [], []
    for d in ds:
        if d.get("in_archive"):
            skipped.append({"name": d["name"], "reason": "In an archive / superseded folder."})
        elif d.get("superseded_by"):
            skipped.append({"name": d["name"], "reason": f"Superseded by {d['superseded_by']}."})
        elif d["status"] not in ("ok", "partial"):
            skipped.append({"name": d["name"], "reason": {"needs_ocr": "Scanned or drawing-only: no text to read (needs the drawing reader).", "unsupported": "File type not supported yet."}.get(d["status"], "Could not be read.")})
        else:
            use.append(d)
            if d["status"] == "partial":
                skipped.append({"name": d["name"], "reason": "Only part of this file had readable text (still included)."})
    docs = [_doc(d) for d in use]
    batches = ai_draft.plan_batches(docs, min(config.AI_MAX_INPUT_CHARS, BATCH_CHARS), INTAKE_FILES)
    out = [{"index": i, "chars": _chars(b), "parts": [{"file_id": x["file_id"], "name": x["name"], "page_from": x["pages"][0]["n"], "page_to": x["pages"][-1]["n"]} for x in b]} for i, b in enumerate(batches)]
    return {"batches": out, "skipped": skipped, "total_chars": sum(b["chars"] for b in out), "files": len(use), "max_batches": MAX_INTAKE_BATCHES}


@router.post("/tenders/{tender_id}/draft")
async def draft(tender_id: str, body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    """One AI call over chosen documents.  `file_ids` (whole files) or `parts` ([{file_id, page_from, page_to}]) as produced by the intake plan."""
    t = await _tender(user, tender_id)
    org = await _org(user)
    prov, key, model, _src = await _ready(user, org)
    parts = body.get("parts")
    if parts:
        want = [(str(x.get("file_id")), int(x.get("page_from", 0)), int(x.get("page_to", 0))) for x in parts][:INTAKE_FILES]
    else:
        want = [(str(i), None, None) for i in body.get("file_ids", [])][:MAX_FILES]
    if not want:
        raise HTTPException(422, f"Choose at least one document that has been read (up to {MAX_FILES}).")
    db = get_db()
    found = {d["file_id"]: d async for d in db.doc_texts.find({"org_id": user["org_id"], "tender_id": t["_id"], "file_id": {"$in": [w[0] for w in want]}})}
    if [w for w in want if w[0] not in found]:
        raise HTTPException(409, "Some of those documents have not been read yet. Read them on the Drive Documents page first.")
    docs = []
    for fid, a, b in want:
        f = found[fid]
        if f["status"] not in ("ok", "partial"):
            continue
        pages = f["pages"] if a is None else [p for p in f["pages"] if a <= p["n"] <= b]
        if pages:
            docs.append(_doc(f, pages))
    if not docs:
        raise HTTPException(409, "None of the chosen documents has readable text (scanned files and drawings need the drawing reader).")
    chars = _chars(docs)
    if chars > config.AI_MAX_INPUT_CHARS:
        raise HTTPException(413, f"That is {chars:,} characters of text; the limit for one run is {config.AI_MAX_INPUT_CHARS:,}. Choose fewer documents.")
    last = await db.revisions.find_one({"tender_id": t["_id"], "org_id": user["org_id"]}, sort=[("n", -1)])
    est = (last or {}).get("estimate", {})
    meta = {**{k: v for k, v in (est.get("meta") or {}).items() if isinstance(v, str)}, "project": t["name"], "client": t.get("client", ""), "location": t.get("location", "")}
    existing = await _existing(db, user, t, est)
    user_msg = ai_draft.build_user_message(meta, docs, existing)
    try:
        data = await timed_ai(user, t["_id"], "drafting", model, prov.draft_json, key, model, ai_draft.SYSTEM, user_msg, ai_draft.SCHEMA)
    except ai_client.AIError as e:
        await audit(db, user, "ai.draft_failed", t["_id"], str(e)[:200])
        raise HTTPException(502, str(e))
    items = ai_draft.verify(data["items"][:60], docs, existing)
    batch = str(body.get("run") or "")[:40] or uuid.uuid4().hex
    stamp = now()
    docs_out = []
    for it in items:
        doc = {"_id": new_id(), "org_id": user["org_id"], "tender_id": t["_id"], "batch": batch, "created_at": stamp, "created_by": user["_id"], "model": model, "provider": prov.id,
               "prompt_version": ai_draft.PROMPT_VERSION, "file_ids": [d["file_id"] for d in docs], **{k: it[k] for k in ("kind", "title", "detail", "impact", "rag", "basis", "evidence", "status", "problems")},
               "decision": None}
        docs_out.append(doc)
    if docs_out:
        await db.ai_proposals.insert_many(docs_out)
    await db.ai_batches.insert_one({"_id": new_id(), "run": batch, "org_id": user["org_id"], "tender_id": t["_id"], "created_at": stamp, "created_by": user["_id"], "model": model, "provider": prov.id,
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
