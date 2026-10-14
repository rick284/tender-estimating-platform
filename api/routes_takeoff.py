"""AI takeoff: propose quantity lines from drawings and reports already read from Drive. The AI proposes components and an operation; the platform does the
arithmetic and checks every number it says it read. The estimator accepts a line into the QS draft (through the normal Add QS item dialog) or rejects it."""
from __future__ import annotations
import uuid
from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool

import ai_client
import ai_takeoff
import config
import drawing_reader
import drive_client as dc
from db import get_db
from routes_ai import _org, _ready, _tender
from routes_drive import _token
from security import current_user
from routes_time import timed_ai
from services import audit, new_id, now

router = APIRouter(prefix="/api/takeoff", tags=["takeoff"])
MAX_DOCS = 8
MAX_PICTURES = config.TAKEOFF_MAX_PICTURES
MAX_PICTURE_BYTES = 4_000_000
BASIS = {"READ": "PROVIDED", "COUNTED": "MEASURED", "SCALED": "MEASURED", "CALCULATED": "CALCULATED"}


def _public(p: dict[str, Any]) -> dict[str, Any]:
    return {"id": p["_id"], "run": p["run"], "description": p["description"], "section": p["section"], "unit": p["unit"], "operation": p["operation"], "method": p["method"],
            "confidence": p["confidence"], "notes": p["notes"], "quantity": p["quantity"], "quantity_claimed": p.get("quantity_claimed"), "components": p["components"],
            "status": p["status"], "problems": p["problems"], "decision": p.get("decision"), "created_at": p["created_at"].isoformat()}


@router.post("/tenders/{tender_id}/run")
async def run(tender_id: str, body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    """body: {file_ids: [...], pictures: [{file_id, page}], run?}.  Text of the chosen documents (and up to 8 page pictures) goes to the company's AI provider."""
    t = await _tender(user, tender_id)
    prov, key, model, _src = await _ready(user, await _org(user))
    ids = [str(i) for i in body.get("file_ids", [])][:MAX_DOCS]
    if not ids:
        raise HTTPException(422, f"Choose at least one document that has been read (up to {MAX_DOCS}).")
    pics = [(str(x.get("file_id")), int(x.get("page", 0))) for x in (body.get("pictures") or [])]
    if len(pics) > MAX_PICTURES:
        raise HTTPException(422, f"That is {len(pics)} page pictures; the limit for one run is {MAX_PICTURES}. Run the takeoff again for the remaining pages: earlier lines are not repeated.")
    db = get_db()
    found = {d["file_id"]: d async for d in db.doc_texts.find({"org_id": user["org_id"], "tender_id": t["_id"], "file_id": {"$in": ids}})}
    if [i for i in ids if i not in found]:
        raise HTTPException(409, "Some of those documents have not been read yet. Read them on the Drive Documents page first.")
    docs, label_of = [], {}
    for i in ids:
        f = found[i]
        if f["status"] in ("ok", "partial"):
            label = f"D{len(docs) + 1}"
            label_of[i] = label
            docs.append({"label": label, "name": f["name"], "file_id": i, "pages": f["pages"]})
    if not docs:
        raise HTTPException(409, "None of the chosen documents has readable text.")
    chars = sum(len(p["text"]) for d in docs for p in d["pages"])
    if chars > config.AI_MAX_INPUT_CHARS:
        raise HTTPException(413, f"That is {chars:,} characters of text; the limit for one run is {config.AI_MAX_INPUT_CHARS:,}. Choose fewer documents.")
    images: list[tuple[str, bytes]] = []
    if pics:
        bad = [p for p in pics if p[0] not in label_of]
        if bad:
            raise HTTPException(422, "Page pictures can only come from the documents you chose.")
        tok = await _token(user)
        link = t.get("drive_folder")
        if not link:
            raise HTTPException(409, "No Drive folder is linked to this tender yet.")
        try:
            items, _ = await dc.walk(tok, link["id"])
        except dc.DriveError as e:
            raise HTTPException(409, str(e))
        by_id = {f["id"]: f for f in items if not f["is_folder"]}
        for fid in dict.fromkeys(p[0] for p in pics):
            if fid not in by_id:
                raise HTTPException(409, "A chosen drawing is no longer in the tender's Drive folder.")
            try:
                _n, mime, data = await dc.download(tok, by_id[fid])
            except dc.DriveError as e:
                raise HTTPException(409, str(e))
            if "pdf" not in mime:
                raise HTTPException(422, "Page pictures are only available for PDF drawings.")
            count = await run_in_threadpool(drawing_reader.page_count, data)
            for _f, pg in [p for p in pics if p[0] == fid]:
                if not 1 <= pg <= count:
                    raise HTTPException(422, f"{found[fid]['name']} has {count} pages; page {pg} does not exist.")
                png = await run_in_threadpool(drawing_reader.render_page, data, pg)
                if len(png) > MAX_PICTURE_BYTES:
                    png = await run_in_threadpool(drawing_reader.render_page, data, pg, 1.0, 2000)
                images.append((f"{label_of[fid]} ({found[fid]['name']}) page {pg}:", png))
    prior = await db.ai_takeoff_lines.find({"org_id": user["org_id"], "tender_id": t["_id"]}).to_list(500)
    existing = [{"description": p["description"], "quantity": p["quantity"], "unit": p["unit"]} for p in prior if (p.get("decision") or {}).get("decision") != "rejected" and p["status"] != "unverified"]
    user_msg = ai_takeoff.build_user_message(t["name"], docs, existing)
    try:
        data = await timed_ai(user, t["_id"], "takeoff", model, prov.draft_json, key, model, ai_takeoff.SYSTEM, user_msg, ai_takeoff.SCHEMA, images)
    except ai_client.AIError as e:
        await audit(db, user, "takeoff.failed", t["_id"], str(e)[:200])
        raise HTTPException(502, str(e))
    pages = {d["label"]: {p["n"]: p["text"] for p in d["pages"]} for d in docs}
    names = {d["label"]: d["name"] for d in docs}
    fid_of = {d["label"]: d["file_id"] for d in docs}
    items = ai_takeoff.verify(data["items"][:80], pages)
    run_id, stamp, out = str(body.get("run") or "")[:40] or uuid.uuid4().hex, now(), []
    for it in items:
        comps = [{**c, "file": names.get(str(c.get("doc")), ""), "file_id": fid_of.get(str(c.get("doc")), "")} for c in it["components"]]
        qty = it["computed"] if it["computed"] is not None else it["quantity_claimed"]
        out.append({"_id": new_id(), "org_id": user["org_id"], "tender_id": t["_id"], "run": run_id, "created_at": stamp, "created_by": user["_id"], "model": model, "provider": prov.id,
                    "prompt_version": ai_takeoff.PROMPT_VERSION, "pictures": [c for c, _ in images], "decision": None,
                    **{k: it[k] for k in ("description", "section", "unit", "operation", "method", "confidence", "notes", "status", "problems")},
                    "quantity": qty, "quantity_claimed": it["quantity_claimed"], "components": comps})
    if out:
        await db.ai_takeoff_lines.insert_many(out)
    await audit(db, user, "takeoff.run", t["_id"], f"{len(docs)} documents, {len(images)} pictures, {len(out)} lines")
    return {"run": run_id, "lines": [_public(p) for p in out], "not_measurable": data.get("not_measurable", [])[:40], "files_sent": [d["name"] for d in docs], "pictures": len(images)}


@router.get("/tenders/{tender_id}/lines")
async def lines(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    ps = await get_db().ai_takeoff_lines.find({"org_id": user["org_id"], "tender_id": t["_id"]}).sort("created_at", -1).to_list(500)
    return {"lines": [_public(p) for p in ps]}


def _template(p: dict[str, Any]) -> dict[str, Any]:
    """What the Add QS item dialog is pre-filled with. The quantity is the PLATFORM's arithmetic, never the AI's stated total."""
    src = "; ".join(f"{c.get('file') or c.get('doc')} {c.get('sheet', '')} p.{c.get('page')}" + (f" “{str(c.get('quote', '')).strip()[:60]}”" if c.get("quote") else "") for c in p["components"][:3])
    note = f"AI takeoff ({p['method']}, {p['confidence']} confidence)." + (" Scaled or counted: check on the drawing." if p["status"] == "check" else "")
    return {"description": p["description"][:200], "unit": p["unit"], "quantity": round(float(p["quantity"]), 3), "basis": BASIS.get(p["method"], "MEASURED"),
            "source": ("AI takeoff: " + src)[:300], "notes": (note + " " + p["notes"]).strip()[:500], "section_hint": p["section"]}


@router.post("/lines/{lid}/decision")
async def decide(lid: str, body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    db = get_db()
    p = await db.ai_takeoff_lines.find_one({"_id": lid, "org_id": user["org_id"]})
    if not p:
        raise HTTPException(404, "Line not found.")
    d = body.get("decision")
    if d not in ("accepted", "rejected"):
        raise HTTPException(422, "Decision must be accepted or rejected.")
    if p.get("decision") and p["decision"]["decision"] != d:
        raise HTTPException(409, f"This line was already {p['decision']['decision']}.")
    if d == "rejected":
        reason = str(body.get("reason", "")).strip()
        if len(reason) < 3:
            raise HTTPException(422, "Give a short reason for rejecting it (it helps the platform learn what to leave out).")
        await db.ai_takeoff_lines.update_one({"_id": lid}, {"$set": {"decision": {"decision": "rejected", "reason": reason[:500], "by": user["_id"], "at": now()}}})
        await audit(db, user, "takeoff.reject", p["tender_id"], p["description"][:80])
        return {"decision": "rejected"}
    if p["status"] == "unverified":
        raise HTTPException(409, "This line can't be accepted: a number it says it read is not on the page it cites, or its arithmetic does not add up.")
    if body.get("commit", True) and not p.get("decision"):          # commit=false only fetches the pre-filled item; the line counts as accepted once it is really added to the draft
        await db.ai_takeoff_lines.update_one({"_id": lid}, {"$set": {"decision": {"decision": "accepted", "by": user["_id"], "at": now()}}})
        await audit(db, user, "takeoff.accept", p["tender_id"], p["description"][:80])
    return {"decision": "accepted" if p.get("decision") or body.get("commit", True) else "pending", "qs": _template(p)}


# ------------------------------------------------------------------ read-only drawing viewer
_CACHE: "OrderedDict[tuple, bytes]" = OrderedDict()          # recently opened PDFs (Drive downloads are slow); the original is never stored on disk or in the database
_CACHE_BYTES = 60_000_000


async def _pdf(user: dict[str, Any], t: dict[str, Any], file_id: str) -> tuple[bytes, dict[str, Any]]:
    rec = await get_db().doc_texts.find_one({"org_id": user["org_id"], "tender_id": t["_id"], "file_id": file_id}, {"pages": 0})
    if not rec:
        raise HTTPException(404, "That document has not been read for this tender.")
    if "pdf" not in (rec.get("mime") or "") and not rec["name"].lower().endswith(".pdf"):
        raise HTTPException(422, "The viewer only shows PDF drawings.")
    key = (user["org_id"], file_id, rec.get("modified"))
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key], rec
    tok = await _token(user)
    try:
        _n, _m, data = await dc.download(tok, {"id": file_id, "mime": rec.get("mime") or "application/pdf", "name": rec["name"]})
    except dc.DriveError as e:
        raise HTTPException(409, str(e))
    _CACHE[key] = data
    while sum(len(v) for v in _CACHE.values()) > _CACHE_BYTES and len(_CACHE) > 1:
        _CACHE.popitem(last=False)
    return data, rec


@router.get("/tenders/{tender_id}/files/{file_id}/sheets")
async def sheets(tender_id: str, file_id: str, user: dict[str, Any] = Depends(current_user)):
    """Every page of a drawing PDF with its sheet code and title where the index on page 1 gives one (used to pick pages for the AI and to move around the viewer)."""
    t = await _tender(user, tender_id)
    data, rec = await _pdf(user, t, file_id)
    pages = await run_in_threadpool(drawing_reader.page_texts, data)
    return {"file": rec["name"], "pages": await run_in_threadpool(drawing_reader.sheet_list, pages), "scale": {p["n"]: drawing_reader.scale_note(p) for p in pages if drawing_reader.scale_note(p)}}


@router.get("/tenders/{tender_id}/files/{file_id}/pages/{page}/image")
async def page_image(tender_id: str, file_id: str, page: int, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    data, _rec = await _pdf(user, t, file_id)
    count = await run_in_threadpool(drawing_reader.page_count, data)
    if not 1 <= page <= count:
        raise HTTPException(404, f"This drawing has {count} pages.")
    png = await run_in_threadpool(drawing_reader.render_page, data, page, 1.8, 3200)
    await audit(get_db(), user, "takeoff.view_page", t["_id"], f"{file_id[:12]} p.{page}")
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=600"})


@router.get("/lines/{lid}/sources")
async def sources(lid: str, user: dict[str, Any] = Depends(current_user)):
    """For each number behind a takeoff line: the document, the page and, where the quote or number can be found in the PDF's text, a highlight rectangle."""
    db = get_db()
    p = await db.ai_takeoff_lines.find_one({"_id": lid, "org_id": user["org_id"]})
    if not p:
        raise HTTPException(404, "Line not found.")
    t = await _tender(user, p["tender_id"])
    by_name = {d["name"]: d["file_id"] async for d in db.doc_texts.find({"org_id": user["org_id"], "tender_id": t["_id"]}, {"name": 1, "file_id": 1})}
    out = []
    for i, c in enumerate(p["components"]):
        fid = c.get("file_id") or by_name.get(c.get("file", ""), "")
        item = {"index": i, "label": c.get("label"), "value": c.get("value"), "unit": c.get("unit"), "source": c.get("source"), "file_id": fid, "file": c.get("file"), "sheet": c.get("sheet"),
                "page": c.get("page"), "quote": c.get("quote", ""), "how": "none", "rects": [], "viewable": False}
        if fid and isinstance(c.get("page"), int):
            try:
                data, _rec = await _pdf(user, t, fid)
                count = await run_in_threadpool(drawing_reader.page_count, data)
                if 1 <= c["page"] <= count:
                    item["viewable"], item["pages"] = True, count
                    if c.get("source") in ("read_text", "schedule", "stated_area"):
                        loc = await run_in_threadpool(drawing_reader.locate, data, c["page"], c.get("quote", ""), c.get("value"))
                        item["how"], item["rects"] = loc["how"], loc["rects"]
            except HTTPException:
                pass                                   # not a PDF, or Drive not reachable right now: the numbers are still listed
        out.append(item)
    return {"line": lid, "description": p["description"], "sources": out}
