"""Emails page: thread files that Mason saved in the job's Drive folder, read-only. See emails.py for the file layout."""
from __future__ import annotations
import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

import doc_text
import drive_client as dc
import emails
from db import get_db
from routes_drive import _tender, _token
from security import current_user
from services import audit, now

router = APIRouter(prefix="/api/emails", tags=["emails"])
MAX_THREADS = 300
MAX_TEXT = 200_000
TEXTLIKE = (".txt", ".md", ".docx", ".eml")


def _out(d: dict[str, Any], with_text: bool = False) -> dict[str, Any]:
    o = {k: d.get(k) for k in ("file_id", "name", "link", "path", "direction", "date", "subject", "party", "count", "refs", "attachments", "links", "gmail_ids", "modified")}
    if with_text:
        o["messages"] = d.get("messages", []); o["text"] = d.get("text", "")
    return o


@router.post("/tenders/{tender_id}/refresh")
async def refresh(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    """Read the email files in the linked Drive folder (new or changed ones only) and keep a copy of their text. Read only on Drive."""
    t = await _tender(user, tender_id)
    link = t.get("drive_folder")
    if not link:
        raise HTTPException(409, "Link this tender to its Drive job folder first (Drive Documents).")
    tok = await _token(user)
    db = get_db()
    try:
        items, trunc = await dc.walk(tok, link["id"], max_depth=5, max_files=2500)
        files = [f for f in items if not f["is_folder"] and emails.classify(f["path"], f["name"]) and (f["mime"] == "application/vnd.google-apps.document" or f["name"].lower().endswith(TEXTLIKE))]
        files = files[:MAX_THREADS]
        have = {d["file_id"]: d async for d in db.email_threads.find({"tender_id": t["_id"], "org_id": user["org_id"]}, {"file_id": 1, "modified": 1})}
        todo = [f for f in files if have.get(f["id"], {}).get("modified") != f["modified"]]
        sem = asyncio.Semaphore(5)
        problems: list[str] = []

        async def one(f: dict[str, Any]):
            async with sem:
                try:
                    name, mime, data = await dc.download(tok, {"id": f["id"], "name": f["name"], "mime": f["mime"], "size": f.get("size")})
                    r = doc_text.extract(name, mime, data)
                    text = "\n\n".join(p["text"] for p in r["pages"])[:MAX_TEXT]
                    if not text.strip():
                        problems.append(f"{f['name']}: no readable text."); return None
                    th = emails.parse_thread(f["name"], text)
                    return {"_id": f"{t['_id']}:{f['id']}", "org_id": user["org_id"], "tender_id": t["_id"], "file_id": f["id"], "name": f["name"], "link": f.get("link", ""), "path": f["path"],
                            "direction": emails.classify(f["path"], f["name"]), "modified": f["modified"], "text": text, "read_at": now(), **th}
                except dc.DriveError as e:
                    problems.append(str(e)); return None
        docs = [d for d in await asyncio.gather(*(one(f) for f in todo)) if d]
        for d in docs:
            await db.email_threads.replace_one({"_id": d["_id"]}, d, upsert=True)
        gone = [fid for fid in have if fid not in {f["id"] for f in files}]
        if gone and not trunc:
            await db.email_threads.delete_many({"tender_id": t["_id"], "org_id": user["org_id"], "file_id": {"$in": gone}})   # only our own copy of the text
    except dc.DriveError as e:
        raise HTTPException(409, str(e))
    await audit(db, user, "emails.refresh", t["_id"], f"{len(docs)} read, {len(files)} found")
    return {"found": len(files), "read": len(docs), "removed": len(gone) if not trunc else 0, "problems": problems[:10], "truncated": trunc}


@router.get("/tenders/{tender_id}")
async def list_threads(tender_id: str, q: str = "", direction: str = "", ref: str = "", user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    rows = await get_db().email_threads.find({"tender_id": t["_id"], "org_id": user["org_id"]}).to_list(MAX_THREADS)
    q = q.strip()
    out = []
    for d in rows:
        if direction in ("in", "out") and d["direction"] != direction:
            continue
        if ref and ref not in d.get("refs", []):
            continue
        hit = ""
        if q:
            if q.lower() not in (d.get("text", "") + " " + d["name"]).lower():
                continue
            hit = emails.snippet(d.get("text", ""), q)
        out.append({**_out(d), "hit": hit})
    out.sort(key=lambda x: (x["date"] or "", x["name"]), reverse=True)
    allrefs = sorted({r for d in rows for r in d.get("refs", [])})
    return {"threads": out, "total": len(rows), "refs": allrefs}


@router.get("/tenders/{tender_id}/thread/{file_id}")
async def thread(tender_id: str, file_id: str, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    d = await get_db().email_threads.find_one({"_id": f"{t['_id']}:{file_id}", "org_id": user["org_id"]})
    if not d:
        raise HTTPException(404, "That email isn't in the saved copy. Refresh from Drive.")
    return _out(d, with_text=True)
