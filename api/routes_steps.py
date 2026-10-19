"""The job's build path: read-only view of the step files the senior estimator (ChatGPT project) keeps in the job's Drive folder."""
from __future__ import annotations
import asyncio
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
        record = next((x for x in inside if x["name"].lower().startswith("job_record") and x["name"].lower().endswith(".md")), None)
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
