"""Programme documents (MS Project style): upload .mpp/.xml, build blank or from an estimate, edit and save, export MS Project XML.

The programme is stored as a document per tender (`programme_docs`). The editing logic (scheduling, links, outline) runs in the browser, as in the
Blackline programme viewer; the server stores what the estimator saves and reads/writes MS Project files through MPXJ in a helper process."""
from __future__ import annotations
import os
import tempfile
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel

import ai_client
import programme_ai
import programme_mpxj as mp
from db import get_db
from programme_build import BadProgramme, clean_tasks, tasks_from_estimate
from routes_ai import _org, _ready
from security import current_user
from services import audit, new_id, now

router = APIRouter(prefix="/api/tenders/{tender_id}/programmes", tags=["programmes"])
ALLOWED = {".mpp", ".mpx", ".mpt", ".xml", ".planner", ".pmxml", ".xer"}
MAX_UPLOAD = 25 * 1024 * 1024
WEEK = [True, True, True, True, True, False, False]


async def _tender(user: dict[str, Any], tender_id: str) -> dict[str, Any]:
    t = await get_db().tenders.find_one({"_id": tender_id, "org_id": user["org_id"]})
    if not t:
        raise HTTPException(404, "Tender not found.")
    return t


async def _doc(user: dict[str, Any], tender_id: str, pid: str) -> dict[str, Any]:
    d = await get_db().programme_docs.find_one({"_id": pid, "tender_id": tender_id, "org_id": user["org_id"]})
    if not d:
        raise HTTPException(404, "Programme not found.")
    return d


def _out(d: dict[str, Any], full: bool = True) -> dict[str, Any]:
    o = {k: v for k, v in d.items() if k not in ("_id", "org_id")}
    o["id"] = d["_id"]
    if not full:
        o.pop("tasks", None)
    return o


def _base(user: dict[str, Any], tender_id: str, name: str, start: str, source: str, tasks: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    s = (start or now().strftime("%Y-%m-%d"))[:10]
    return {"_id": new_id(), "org_id": user["org_id"], "tender_id": tender_id, "name": name[:200], "source": source, "filename": None,
            "start": f"{s}T08:00", "finish": f"{s}T17:00", "status_date": None, "author": "", "company": "", "working_days": WEEK, "non_working_dates": [],
            "hours_per_day": 8.0, "task_count": len(tasks), "tasks": tasks, "needs_schedule": True, "created_by": user["_id"],
            "created_at": now().isoformat(), "updated_at": now().isoformat(), **extra}


@router.get("")
async def list_programmes(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    await _tender(user, tender_id)
    ds = await get_db().programme_docs.find({"tender_id": tender_id, "org_id": user["org_id"]}, {"tasks": 0}).sort("updated_at", -1).to_list(200)
    return {"programmes": [_out(d, False) for d in ds]}


@router.get("/{pid}")
async def get_programme(tender_id: str, pid: str, user: dict[str, Any] = Depends(current_user)):
    await _tender(user, tender_id)
    return _out(await _doc(user, tender_id, pid))


@router.post("/upload")
async def upload(tender_id: str, file: UploadFile = File(...), user: dict[str, Any] = Depends(current_user)):
    await _tender(user, tender_id)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"That file type isn't supported. Use one of: {', '.join(sorted(ALLOWED))}.")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "That file is too large (25 MB maximum).")
    fd, path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        parsed = await run_in_threadpool(mp.parse_in_worker, path)
    except mp.WorkerError as e:
        raise HTTPException(400, str(e))
    finally:
        if os.path.exists(path):
            os.unlink(path)
    try:
        parsed["tasks"] = clean_tasks(parsed.get("tasks", []))
    except BadProgramme as e:
        raise HTTPException(400, str(e))
    if parsed.get("name") in (None, "", "Programme"):
        parsed["name"] = os.path.splitext(file.filename or "Programme")[0][:200]
    doc = _base(user, tender_id, parsed["name"], "", "upload", parsed["tasks"], filename=file.filename)
    doc.update({k: parsed[k] for k in ("start", "finish", "status_date", "author", "company", "working_days", "non_working_dates", "hours_per_day") if k in parsed})
    doc["needs_schedule"] = False
    doc["task_count"] = len(doc["tasks"])
    db = get_db()
    await db.programme_docs.insert_one(doc)
    await audit(db, user, "programme.upload", tender_id, f"{file.filename}: {doc['task_count']} tasks")
    return _out(doc)


class BlankIn(BaseModel):
    name: str = "New programme"
    start_date: str | None = None


@router.post("/blank")
async def blank(tender_id: str, body: BlankIn, user: dict[str, Any] = Depends(current_user)):
    await _tender(user, tender_id)
    doc = _base(user, tender_id, (body.name or "New programme").strip() or "New programme", body.start_date or "", "blank", [])
    await get_db().programme_docs.insert_one(doc)
    await audit(get_db(), user, "programme.create", tender_id, "blank")
    return _out(doc)


class FromEstimateIn(BaseModel):
    revision: int
    start_date: str | None = None
    name: str | None = None


@router.post("/from-estimate")
async def from_estimate(tender_id: str, body: FromEstimateIn, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    r = await get_db().revisions.find_one({"tender_id": tender_id, "org_id": user["org_id"], "n": body.revision})
    if not r:
        raise HTTPException(404, "Revision not found.")
    tasks = tasks_from_estimate(r["estimate"])
    if not tasks:
        raise HTTPException(400, "That revision has no priced QS items to build a programme from.")
    doc = _base(user, tender_id, (body.name or f"{t['name']} - programme").strip(), body.start_date or "", "estimate", tasks, revision=body.revision)
    await get_db().programme_docs.insert_one(doc)
    await audit(get_db(), user, "programme.create", tender_id, f"from revision {body.revision}: {len(tasks)} rows")
    return _out(doc)


class SaveIn(BaseModel):
    name: str | None = None
    tasks: list[dict[str, Any]]
    start: str | None = None
    finish: str | None = None
    working_days: list[bool] | None = None
    non_working_dates: list[str] | None = None


@router.put("/{pid}")
async def save(tender_id: str, pid: str, body: SaveIn, user: dict[str, Any] = Depends(current_user)):
    await _tender(user, tender_id)
    await _doc(user, tender_id, pid)
    try:
        tasks = clean_tasks(body.tasks)
    except BadProgramme as e:
        raise HTTPException(400, str(e))
    sets: dict[str, Any] = {"tasks": tasks, "task_count": len(tasks), "updated_at": now().isoformat(), "needs_schedule": False}
    if body.name and body.name.strip():
        sets["name"] = body.name.strip()[:200]
    for k in ("start", "finish"):
        if getattr(body, k):
            sets[k] = getattr(body, k)
    if body.working_days and len(body.working_days) == 7:
        sets["working_days"] = body.working_days
    if body.non_working_dates is not None:
        sets["non_working_dates"] = [str(x)[:10] for x in body.non_working_dates][:2000]
    await get_db().programme_docs.update_one({"_id": pid, "org_id": user["org_id"]}, {"$set": sets})
    await audit(get_db(), user, "programme.save", tender_id, f"{pid}: {len(tasks)} tasks")
    return _out(await _doc(user, tender_id, pid))


@router.delete("/{pid}")
async def delete(tender_id: str, pid: str, user: dict[str, Any] = Depends(current_user)):
    await _tender(user, tender_id)
    await _doc(user, tender_id, pid)
    await get_db().programme_docs.delete_one({"_id": pid, "org_id": user["org_id"]})
    await audit(get_db(), user, "programme.delete", tender_id, pid)
    return {"ok": True}


@router.get("/{pid}/export/xml")
async def export_xml(tender_id: str, pid: str, user: dict[str, Any] = Depends(current_user)):
    await _tender(user, tender_id)
    d = await _doc(user, tender_id, pid)
    fd, path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        await run_in_threadpool(mp.export_in_worker, {k: v for k, v in d.items() if k != "_id"}, path)
        with open(path, "rb") as f:
            content = f.read()
    except mp.WorkerError as e:
        raise HTTPException(500, str(e))
    finally:
        if os.path.exists(path):
            os.unlink(path)
    safe = "".join(c for c in d["name"] if c.isalnum() or c in " -_").strip().replace(" ", "_") or "programme"
    await audit(get_db(), user, "programme.export", tender_id, pid)
    return Response(content, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{safe}.xml"'})


# ------------------------------------------------------------------ AI proposals for programme logic
MAX_AI_TASKS = 400


def _public(p: dict[str, Any], names: dict[int, str]) -> dict[str, Any]:
    o = {k: p[k] for k in ("kind", "pred_uid", "succ_uid", "type", "lag_days", "reason", "basis", "confidence", "register_ref", "status", "problems", "decision", "created_at")}
    o["id"] = p["_id"]
    o["pred_name"], o["succ_name"] = names.get(p["pred_uid"], ""), names.get(p["succ_uid"], "")
    return o


async def _register_context(user: dict[str, Any], t: dict[str, Any]) -> list[dict[str, str]]:
    r = await get_db().revisions.find_one({"tender_id": t["_id"], "org_id": user["org_id"], "n": t.get("latest_rev")})
    items = (r or {}).get("estimate", {}).get("register") or []
    return [{"ref": x.get("ref", ""), "kind": x.get("kind", ""), "title": str(x.get("title", ""))[:160], "detail": str(x.get("detail", ""))[:200]}
            for x in items if x.get("kind") in ("assumption", "exclusion", "risk") or (x.get("kind") == "rfi" and x.get("status") != "CLOSED")]


@router.post("/{pid}/ai/propose")
async def ai_propose(tender_id: str, pid: str, user: dict[str, Any] = Depends(current_user)):
    """Ask the company's AI to propose links between the tasks of the SAVED programme. Only task names, durations, resources and the register's titles are sent."""
    t = await _tender(user, tender_id)
    d = await _doc(user, tender_id, pid)
    prov, key, model, _src = await _ready(user, await _org(user))
    tasks = d.get("tasks") or []
    if len(tasks) < 3:
        raise HTTPException(409, "Add at least a few tasks (and save the programme) before asking the AI for logic.")
    if len(tasks) > MAX_AI_TASKS:
        raise HTTPException(413, f"This programme has {len(tasks)} rows; the AI can look at up to {MAX_AI_TASKS} at a time.")
    msg = programme_ai.build_user_message(t["name"], tasks, await _register_context(user, t))
    db = get_db()
    try:
        data = await run_in_threadpool(prov.draft_json, key, model, programme_ai.SYSTEM, msg, programme_ai.SCHEMA, None, "links")
    except ai_client.AIError as e:
        await audit(db, user, "programme.ai_failed", tender_id, str(e)[:200])
        raise HTTPException(502, str(e))
    res = programme_ai.verify(data, tasks)
    await db.ai_programme_proposals.delete_many({"org_id": user["org_id"], "programme_id": pid, "decision": None})        # an earlier undecided run is replaced
    batch, stamp = new_id(), now().isoformat()
    docs = [{"_id": new_id(), "org_id": user["org_id"], "tender_id": tender_id, "programme_id": pid, "batch": batch, "created_at": stamp, "created_by": user["_id"], "model": model,
             "provider": prov.id, "prompt_version": programme_ai.PROMPT_VERSION, "decision": None, **p} for p in res["proposals"]]
    if docs:
        await db.ai_programme_proposals.insert_many(docs)
    await db.ai_programme_batches.insert_one({"_id": batch, "org_id": user["org_id"], "tender_id": tender_id, "programme_id": pid, "created_at": stamp, "model": model,
                                              "questions": res["questions"], "coverage_notes": str(data.get("coverage_notes", ""))[:600], "counts": {s: sum(1 for p in docs if p["status"] == s) for s in ("ok", "exists", "invalid")}})
    await audit(db, user, "programme.ai_propose", tender_id, f"{pid}: {len(docs)} proposals")
    names = {x["uid"]: x.get("name", "") for x in tasks}
    return {"batch": batch, "proposals": [_public(p, names) for p in docs], "questions": res["questions"], "coverage_notes": str(data.get("coverage_notes", ""))[:600]}


@router.get("/{pid}/ai/proposals")
async def ai_proposals(tender_id: str, pid: str, user: dict[str, Any] = Depends(current_user)):
    await _tender(user, tender_id)
    d = await _doc(user, tender_id, pid)
    names = {x["uid"]: x.get("name", "") for x in d.get("tasks") or []}
    ps = await get_db().ai_programme_proposals.find({"org_id": user["org_id"], "programme_id": pid}).sort("created_at", -1).to_list(500)
    b = await get_db().ai_programme_batches.find({"org_id": user["org_id"], "programme_id": pid}).sort("created_at", -1).to_list(1)
    return {"proposals": [_public(p, names) for p in ps], "questions": b[0]["questions"] if b else [], "coverage_notes": b[0]["coverage_notes"] if b else ""}


@router.post("/{pid}/ai/decision")
async def ai_decision(tender_id: str, pid: str, body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    """body: {accept: [proposal ids], reject: [{id, reason}]}. Accepting only records the decision and returns the link changes; the browser applies them to the
    programme the estimator is editing (nothing is saved until they press Save). A rejection needs a reason: it is kept for the learning loop."""
    await _tender(user, tender_id)
    d = await _doc(user, tender_id, pid)
    db = get_db()
    names = {x["uid"]: x.get("name", "") for x in d.get("tasks") or []}
    acc_ids = [str(i) for i in body.get("accept") or []]
    rej = [(str(r.get("id")), str(r.get("reason") or "").strip()) for r in body.get("reject") or []]
    if any(len(reason) < 5 for _i, reason in rej):
        raise HTTPException(422, "Say briefly why you are rejecting (at least a few words): it helps the AI learn what is not wanted.")
    found = {p["_id"]: p async for p in db.ai_programme_proposals.find({"org_id": user["org_id"], "programme_id": pid, "_id": {"$in": acc_ids + [i for i, _ in rej]}})}
    if any(i not in found for i in acc_ids + [i for i, _ in rej]):
        raise HTTPException(404, "One of those proposals no longer exists. Ask the AI again.")
    if any(found[i]["status"] != "ok" for i in acc_ids):
        raise HTTPException(409, "A proposal that failed the checks (or already exists) can't be accepted.")
    stamp, out = now().isoformat(), []
    for i in acc_ids:
        await db.ai_programme_proposals.update_one({"_id": i}, {"$set": {"decision": {"decision": "accepted", "by": user["_id"], "at": stamp}}})
        found[i]["decision"] = {"decision": "accepted"}
        out.append(_public(found[i], names))
    for i, reason in rej:
        await db.ai_programme_proposals.update_one({"_id": i}, {"$set": {"decision": {"decision": "rejected", "reason": reason[:300], "by": user["_id"], "at": stamp}}})
    await audit(db, user, "programme.ai_decision", tender_id, f"{pid}: {len(acc_ids)} accepted, {len(rej)} rejected")
    return {"accepted": out, "rejected": len(rej)}
