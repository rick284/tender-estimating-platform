"""The job's build path: read-only view of the step files the senior estimator (ChatGPT project) keeps in the job's Drive folder."""
from __future__ import annotations
import re
import asyncio
import httpx
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

import drive_client as dc
import drive_index
import steps as st
from routes_drive import _tender, _token
from security import current_user

router = APIRouter(prefix="/api/steps", tags=["steps"])
MAX_STEPS = 80


def _f(x: dict[str, Any]) -> dict[str, Any]:
    return {"id": x["id"], "name": x["name"], "mime": x.get("mimeType", ""), "size": int(x["size"]) if x.get("size") else None}


async def _scan(user, tender_id: str) -> tuple[str, dict[str, Any], dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    t = await _tender(user, tender_id)
    link = t.get("drive_folder")
    if not link:
        raise HTTPException(409, "Link this tender to its Drive job folder first (Drive Documents).")
    tok = await _token(user)
    try:
        top = await dc.list_children(tok, link["id"])
        admin = next((x for x in top if x["mimeType"] == dc.FOLDER_MIME and drive_index._has_number(x["name"], "00")), None)
        if not admin:
            return tok, t, None, [], []
        inside = await dc.list_children(tok, admin["id"])
        record = next((x for x in inside if st.norm_name(x["name"]).lower().startswith("job_record") and st.norm_name(x["name"]).lower().endswith(".md")), None)
        steps_dir = next((x for x in inside if x["mimeType"] == dc.FOLDER_MIME and x["name"].strip().lower() == "steps"), None)
        folders: list[dict[str, Any]] = []
        if steps_dir:
            kids = [k for k in await dc.list_children(tok, steps_dir["id"]) if k["mimeType"] == dc.FOLDER_MIME and st.parse_step_folder(k["name"])][:MAX_STEPS]
            sem = asyncio.Semaphore(6)

            async def one(k):
                async with sem:
                    return {"folder_id": k["id"], "name": k["name"], "files": [_f(x) for x in await dc.list_children(tok, k["id"]) if st.parse_step_file(x["name"], loose=True)]}
            folders = await asyncio.gather(*(one(k) for k in kids))
        loose = [_f(x) for x in inside if x["mimeType"] != dc.FOLDER_MIME and st.parse_step_file(x["name"], loose=True)]
        return tok, t, record, list(folders), loose
    except dc.DriveError as e:
        raise HTTPException(409, str(e))


async def _text(tok: str, f: dict[str, Any]) -> str:
    try:
        _, _, data = await dc.download(tok, {"id": f["id"], "name": f["name"], "mime": f.get("mime") or "text/markdown", "size": f.get("size")})
    except dc.DriveError as e:
        raise HTTPException(409, str(e))
    return data.decode("utf-8", errors="replace")[:400_000]


@router.get("/tenders/{tender_id}")
async def overview(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    """The step list (grouped for the sidebar) and the parsed Job Record header. Files are read, never written."""
    tok, t, record, folders, loose = await _scan(user, tender_id)
    text, parsed = "", {"fields": {}, "steps": []}
    if record:
        text = await _text(tok, _f(record))
        parsed = st.parse_job_record(text)
    steps = st.build_steps(folders, parsed, loose)
    return {"folder_found": record is not None or bool(folders), "job_record": {"found": record is not None, "name": record["name"] if record else "", "link": record.get("webViewLink", "") if record else "",
            "text": text, "fields": parsed["fields"]}, "steps": steps, "groups": st.group_order(),
            "counts": {"steps": len(steps), "locked": sum(1 for s in steps if s["status"] == "APPROVED-LOCKED"), "draft": sum(1 for s in steps if s["status"] in ("DRAFT", "REPORTED")), "reopened": sum(1 for s in steps if s["status"] == "REOPENED")}}


@router.get("/tenders/{tender_id}/step/{key}")
async def step(tender_id: str, key: str, user: dict[str, Any] = Depends(current_user)):
    """One step's brief and report text."""
    tok, t, record, folders, loose = await _scan(user, tender_id)
    parsed = st.parse_job_record(await _text(tok, _f(record))) if record else {"fields": {}, "steps": []}
    found = next((s for s in st.build_steps(folders, parsed, loose) if s["key"] == key), None)
    if not found:
        raise HTTPException(404, "That step was not found in the job folder.")
    out = {k: found[k] for k in ("key", "number", "name", "group", "status", "chat_title", "workbook_revision", "folder_name")}
    for which in ("brief", "report"):
        f = found.get(which)
        out[which] = {"name": f["name"], "text": await _text(tok, f)} if f else None
    return out


@router.get("/tenders/{tender_id}/step01")
async def step_one(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    """Step 01 outputs found anywhere in the linked job folder: the Scope Confirmation (rows and interface questions), the Estimating Proposal (hours and fee window) and the
    internal decision card. Read only; the rows are offered to the estimator and only enter the estimate when added to the Scope Coverage draft and approved."""
    import step01
    t = await _tender(user, tender_id)
    link = t.get("drive_folder")
    if not link:
        raise HTTPException(409, "Link this tender to its Drive job folder first (Drive Documents).")
    tok = await _token(user)
    try:
        items, _trunc = await dc.walk(tok, link["id"], max_depth=4, max_files=1500)
        found = step01.pick_files([x for x in items if not x["is_folder"]])
        out: dict[str, Any] = {"files": {k: {"name": v["name"], "link": v.get("link", "")} for k, v in found.items()}, "scope": None, "proposal": None, "card": "",
                               "scanned": {"folder": link.get("name", ""), "path": link.get("path", ""), "files": sum(1 for x in items if not x["is_folder"]), "folders": sum(1 for x in items if x["is_folder"]),
                                           "candidates": [x["name"] for x in items if not x["is_folder"] and re.search(r"scope|proposal|step.?0?1", x["name"], re.I)][:8]}}
        get = lambda f: dc.download(tok, {"id": f["id"], "name": f["name"], "mime": f["mime"], "size": f.get("size")})
        gd = lambda f: f.get("mime") == step01.GDOC
        if "scope" in found:
            data = (await get(found["scope"]))[2]
            out["scope"] = step01.parse_scope_text(data.decode("utf-8", errors="replace")) if gd(found["scope"]) else step01.parse_scope_confirmation(data)
        if "proposal" in found:
            data = (await get(found["proposal"]))[2]
            out["proposal"] = step01.parse_proposal_text(data.decode("utf-8", errors="replace")) if gd(found["proposal"]) else step01.parse_proposal(data)
        if "card" in found:
            out["card"] = (await get(found["card"]))[2].decode("utf-8", errors="replace")[:60_000]
    except dc.DriveError as e:
        raise HTTPException(409, str(e))
    except httpx.HTTPError as e:
        raise HTTPException(502, f"The connection to Google Drive dropped part-way ({type(e).__name__}). Press Refresh from Drive to try again.")
    except Exception as e:                                                       # noqa: BLE001  a file that is not a readable Word document
        raise HTTPException(422, f"One of the Step 01 files could not be read ({type(e).__name__}). Save the Scope Confirmation and Proposal as Word (.docx) files in the job folder.")
    out["go_ahead"] = _go(t)
    return out


async def _tracked_hours(user: dict[str, Any], tender_id: str) -> float:
    """Hours actually worked on this tender according to the Timesheet (active time of all sessions + manual entries)."""
    from db import get_db
    db = get_db()
    sec = sum([s.get("active_seconds", 0) async for s in db.time_sessions.find({"org_id": user["org_id"], "tender_id": tender_id})])
    mins = sum([m.get("minutes", 0) async for m in db.time_entries.find({"org_id": user["org_id"], "tender_id": tender_id})])
    return sec / 3600 + mins / 60


async def _production_out(user: dict[str, Any], t: dict[str, Any]) -> dict[str, Any]:
    import production
    p = t.get("production_plan") or {}
    tasks = p.get("tasks") or []
    return {"tasks": tasks, "window": p.get("window"), "source": p.get("source", ""), "updated_at": p.get("updated_at", ""), "go_ahead": _go(t),
            "summary": production.summarise(tasks, p.get("window"), await _tracked_hours(user, t["_id"])) if tasks else None}


@router.get("/tenders/{tender_id}/production")
async def get_production(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    return await _production_out(user, await _tender(user, tender_id))


@router.put("/tenders/{tender_id}/production")
async def put_production(tender_id: str, body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    """Save the plan as edited in the app (tasks and the Step 01 window). The previous version is kept in the audit trail's detail count only; Drive files are never touched."""
    import production
    from db import get_db
    from services import audit, now
    t = await _tender(user, tender_id)
    try:
        tasks = production.clean(body.get("tasks") or [])
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e))
    w = body.get("window")
    if w is not None:
        try:
            w = {k: (None if w.get(k) in (None, "") else float(w[k])) for k in ("low_hours", "high_hours", "benchmark_hours")}
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(422, "The fee window hours must be numbers.")
    prev = t.get("production_plan") or {}
    plan = {"tasks": tasks, "window": w if w is not None else prev.get("window"), "source": prev.get("source") or "Entered in the app", "updated_at": now().isoformat()}
    await get_db().tenders.update_one({"_id": t["_id"]}, {"$set": {"production_plan": plan}})
    await audit(get_db(), user, "steps.production_save", t["_id"], f"{len(tasks)} tasks")
    return await _production_out(user, {**t, "production_plan": plan})


@router.post("/tenders/{tender_id}/production/import")
async def import_production(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    """Read the newest Step 02 task-plan workbook (.xlsx) in the linked Drive folder, and the Step 01 hours window from the proposal. Replaces the saved plan (read only on Drive)."""
    import production
    import step01
    from db import get_db
    from services import audit, now
    t = await _tender(user, tender_id)
    link = t.get("drive_folder")
    if not link:
        raise HTTPException(409, "Link this tender to its Drive job folder first (Drive Documents).")
    tok = await _token(user)
    try:
        items, _trunc = await dc.walk(tok, link["id"], max_depth=4, max_files=1500)
        files = [x for x in items if not x["is_folder"]]
        plans = [f for f in files if re.search(r"production|task.?plan|step.?0?2", f["name"], re.I) and re.search(r"\.xlsx$", f["name"], re.I)]
        if not plans:
            raise HTTPException(404, "No Step 02 task-plan workbook (.xlsx with 'production' or 'task plan' in its name) was found in the job folder.")
        best = max(plans, key=lambda f: f.get("modified", ""))
        get = lambda f: dc.download(tok, {"id": f["id"], "name": f["name"], "mime": f["mime"], "size": f.get("size")})
        tasks = production.clean(production.parse_task_plan((await get(best))[2]))
        window = (t.get("production_plan") or {}).get("window")
        prop = step01.pick_files(files).get("proposal")
        if prop:
            pr = step01.parse_proposal((await get(prop))[2])
            if pr.get("low_hours") is not None:
                window = {"low_hours": pr.get("low_hours"), "high_hours": pr.get("high_hours"), "benchmark_hours": window.get("benchmark_hours") if window else None}
    except dc.DriveError as e:
        raise HTTPException(409, str(e))
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:                                                       # noqa: BLE001
        raise HTTPException(422, f"The task plan could not be read ({type(e).__name__}).")
    plan = {"tasks": tasks, "window": window, "source": f"Drive: {best['name']}", "updated_at": now().isoformat()}
    await get_db().tenders.update_one({"_id": t["_id"]}, {"$set": {"production_plan": plan}})
    await audit(get_db(), user, "steps.production_import", t["_id"], best["name"])
    return await _production_out(user, {**t, "production_plan": plan})


def _go(t: dict[str, Any]) -> dict[str, Any] | None:
    g = t.get("go_ahead")
    return {"mode": g["mode"], "note": g.get("note", ""), "at": g["at"], "by": g.get("by_name", "")} if g else None


@router.get("/tenders/{tender_id}/go-ahead")
async def get_go_ahead(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    return {"go_ahead": _go(await _tender(user, tender_id))}


@router.put("/tenders/{tender_id}/go-ahead")
async def put_go_ahead(tender_id: str, body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    """Record the checkpoint (Rick's alone to record): the client's go-ahead, or 'proceed anyway'. Nothing else happens automatically."""
    from services import audit, now
    t = await _tender(user, tender_id)
    mode = body.get("mode")
    if mode not in ("client_go", "proceed_anyway"):
        raise HTTPException(422, "Choose: the client has given the go-ahead, or proceed anyway.")
    note = str(body.get("note") or "").strip()[:1000]
    if mode == "proceed_anyway" and len(note) < 5:
        raise HTTPException(422, "Say why you are proceeding without the client's go-ahead (the scope then stays 'subject to client confirmation').")
    g = {"mode": mode, "note": note, "at": now().isoformat(), "by": user["_id"], "by_name": user.get("name", "")}
    from db import get_db
    await get_db().tenders.update_one({"_id": t["_id"]}, {"$set": {"go_ahead": g}})
    await audit(get_db(), user, "steps.go_ahead", t["_id"], mode)
    return {"go_ahead": _go({"go_ahead": g})}


@router.delete("/tenders/{tender_id}/go-ahead")
async def clear_go_ahead(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    from services import audit
    from db import get_db
    t = await _tender(user, tender_id)
    await get_db().tenders.update_one({"_id": t["_id"]}, {"$unset": {"go_ahead": ""}})
    await audit(get_db(), user, "steps.go_ahead_cleared", t["_id"])
    return {"go_ahead": None}
