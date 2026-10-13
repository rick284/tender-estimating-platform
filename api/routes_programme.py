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

import programme_mpxj as mp
from db import get_db
from programme_build import BadProgramme, clean_tasks, tasks_from_estimate
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
