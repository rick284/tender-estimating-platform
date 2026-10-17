"""Google Drive connection (read-only) and per-tender folder linking."""
from __future__ import annotations
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

import config
import drive_client as dc
from db import get_db
import doc_text
from drive_index import FOLDER_MIME, JOB_FOLDERS, STANDARD_FOLDERS, analyse, check_structure, plan_folders
from security import current_user
from services import audit, now

router = APIRouter(prefix="/api/drive", tags=["drive"])


def _need_config() -> None:
    if not dc.configured():
        raise HTTPException(503, "Google Drive is not set up on this server yet (the Google client ID and secret have not been added).")


async def _integration(user: dict[str, Any]) -> dict[str, Any] | None:
    return await get_db().integrations.find_one({"org_id": user["org_id"], "kind": "google_drive"})


async def _token(user: dict[str, Any]) -> str:
    doc = await _integration(user)
    if not doc:
        raise HTTPException(409, "Google Drive is not connected. Connect it first (Tenders > Drive).")
    try:
        return await dc.access_token(dc.decrypt(doc["refresh_token"]))
    except dc.DriveError as e:
        raise HTTPException(409, str(e))


@router.get("/status")
async def status(user: dict[str, Any] = Depends(current_user)):
    doc = await _integration(user)
    return {"configured": dc.configured(), "connected": bool(doc), "account": doc.get("account", "") if doc else "",
            "connected_at": doc["connected_at"].isoformat() if doc else None, "read_only": not (doc and dc.can_write(doc.get("scopes", ""))),
            "can_write": bool(doc and dc.can_write(doc.get("scopes", ""))),
            "can_write_anywhere": bool(doc and dc.can_write_anywhere(doc.get("scopes", ""))), "job_folders": [f"{n} {l}" for n, l in JOB_FOLDERS],
            "standard_folders": [f"{n} {l}" for n, l in STANDARD_FOLDERS]}


@router.get("/connect")
async def connect(tender: str = Query("", max_length=64), write: bool = Query(False), user: dict[str, Any] = Depends(current_user)):
    _need_config()
    state = jwt.encode({"org": user["org_id"], "uid": user["_id"], "t": tender if tender.isalnum() else "", "exp": int(now().timestamp()) + 600, "p": "drive"}, config.JWT_SECRET, algorithm="HS256")
    return {"url": dc.auth_url(state, write)}


@router.get("/callback")
async def callback(code: str = "", state: str = "", error: str = ""):
    """Google sends the browser here. Signed state tells us which company is connecting."""
    back = f"{config.WEB_URL}/#/tenders"
    if error or not code:
        return RedirectResponse(f"{back}?drive=cancelled")
    try:
        st = jwt.decode(state, config.JWT_SECRET, algorithms=["HS256"])
        assert st.get("p") == "drive"
    except Exception:
        return RedirectResponse(f"{back}?drive=badstate")
    if st.get("t"):
        back = f"{back}/{st['t']}/drive"
    try:
        tok = await dc.exchange_code(code)
    except dc.DriveError:
        return RedirectResponse(f"{back}?drive=failed")
    rt = tok.get("refresh_token")
    if not rt:
        return RedirectResponse(f"{back}?drive=norefresh")
    db = get_db()
    account = await dc.userinfo_email(tok.get("access_token", ""))
    await db.integrations.update_one({"org_id": st["org"], "kind": "google_drive"},
                                     {"$set": {"refresh_token": dc.encrypt(rt), "account": account, "connected_at": now(), "connected_by": st["uid"], "scopes": tok.get("scope", "")}},
                                     upsert=True)
    await audit(db, {"org_id": st["org"], "_id": st["uid"]}, "drive.connect", "google_drive", account)
    return RedirectResponse(f"{back}?drive=connected")


@router.delete("/connection")
async def disconnect(user: dict[str, Any] = Depends(current_user)):
    db = get_db()
    r = await db.integrations.delete_one({"org_id": user["org_id"], "kind": "google_drive"})
    await db.tenders.update_many({"org_id": user["org_id"]}, {"$unset": {"drive_folder": ""}})
    if r.deleted_count:
        await audit(db, user, "drive.disconnect", "google_drive")
    return {"ok": True}


@router.get("/folders")
async def browse(parent: str = Query("root", max_length=100), user: dict[str, Any] = Depends(current_user)):
    """Folders inside `parent` (default: My Drive) so the estimator can pick the tender's folder."""
    tok = await _token(user)
    try:
        fs = await dc.list_children(tok, parent, only_folders=True)
    except dc.DriveError as e:
        raise HTTPException(409, str(e))
    return {"parent": parent, "folders": [{"id": f["id"], "name": f["name"]} for f in fs]}


# ---- the company's jobs folder: every new job folder goes inside it, as <jobs folder> / <Client> / <Job name> ----------------------

async def _jobs_root(user: dict[str, Any]) -> dict[str, Any] | None:
    org = await get_db().orgs.find_one({"_id": user["org_id"]}) or {}
    return org.get("drive_jobs_root")


@router.get("/jobs-root")
async def get_jobs_root(user: dict[str, Any] = Depends(current_user)):
    return {"folder": await _jobs_root(user)}


@router.put("/jobs-root")
async def set_jobs_root(body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    """Choose the company's top jobs folder once (for example 'Blackline Estimating'). New job folders are made inside it, under the client's folder."""
    fid = str(body.get("folder_id", "")).strip()
    if not fid or len(fid) > 100:
        raise HTTPException(422, "Choose a folder.")
    tok = await _token(user)
    try:
        f = await dc.get_file(tok, fid)
    except dc.DriveError as e:
        raise HTTPException(409, str(e))
    if f["mimeType"] != FOLDER_MIME:
        raise HTTPException(422, "That is a file, not a folder.")
    root = {"id": f["id"], "name": f["name"], "url": f.get("webViewLink", ""), "set_at": now().isoformat(), "set_by": user["_id"]}
    db = get_db()
    await db.orgs.update_one({"_id": user["org_id"]}, {"$set": {"drive_jobs_root": root}})
    await audit(db, user, "drive.set_jobs_root", "google_drive", f["name"])
    return {"folder": root}


def _clean_name(s: Any, what: str) -> str:
    name = " ".join(str(s or "").replace("/", "-").split())[:120]
    if not name:
        raise HTTPException(422, f"Type the {what} folder name.")
    return name


@router.get("/tenders/{tender_id}/new-job-plan")
async def new_job_plan(tender_id: str, client: str = Query("", max_length=160), job: str = Query("", max_length=160),
                       user: dict[str, Any] = Depends(current_user)):
    """What 'Create the job folder' would do: <jobs folder> / <Client> / <Job name> / 00-07. Read-only. Existing folders are reused, never duplicated."""
    t = await _tender(user, tender_id)
    doc = await _integration(user)
    root = await _jobs_root(user)
    client_name = " ".join((client or t.get("client", "")).split())[:120]
    job_name = " ".join((job or t.get("name", "")).split())[:120]
    out = {"root": root, "client": client_name, "job": job_name, "clients": [], "client_exists": False, "job_exists": False,
           "can_write_anywhere": bool(doc and dc.can_write_anywhere(doc.get("scopes", ""))), "folders": [f"{n} {l}" for n, l in JOB_FOLDERS]}
    if not root:
        return out
    tok = await _token(user)
    try:
        kids = await dc.list_children(tok, root["id"], only_folders=True)
        out["clients"] = [k["name"] for k in kids]
        cf = next((k for k in kids if dc._same(k["name"], client_name)), None) if client_name else None
        out["client_exists"] = bool(cf)
        if cf and job_name:
            out["job_exists"] = bool(await dc.find_folder(tok, cf["id"], job_name))
    except dc.DriveError as e:
        raise HTTPException(409, str(e))
    return out


async def _tender(user: dict[str, Any], tender_id: str) -> dict[str, Any]:
    t = await get_db().tenders.find_one({"_id": tender_id, "org_id": user["org_id"]})
    if not t:
        raise HTTPException(404, "Tender not found.")
    return t


@router.get("/tenders/{tender_id}")
async def tender_link(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    return {"folder": t.get("drive_folder")}


@router.put("/tenders/{tender_id}")
async def link_folder(tender_id: str, body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    fid = str(body.get("folder_id", "")).strip()
    if not fid or len(fid) > 100:
        raise HTTPException(422, "Choose a folder.")
    tok = await _token(user)
    try:
        f = await dc.get_file(tok, fid)
    except dc.DriveError as e:
        raise HTTPException(409, str(e))
    if f["mimeType"] != "application/vnd.google-apps.folder":
        raise HTTPException(422, "That is a file, not a folder.")
    link = {"id": f["id"], "name": f["name"], "url": f.get("webViewLink", ""), "linked_at": now().isoformat()}
    db = get_db()
    await db.tenders.update_one({"_id": t["_id"]}, {"$set": {"drive_folder": link}})
    await audit(db, user, "drive.link_folder", t["_id"], f["name"])
    return {"folder": link}


@router.delete("/tenders/{tender_id}")
async def unlink_folder(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    await get_db().tenders.update_one({"_id": t["_id"]}, {"$unset": {"drive_folder": ""}})
    await audit(get_db(), user, "drive.unlink_folder", t["_id"])
    return {"ok": True}


async def _top_folder_names(user, link) -> list[str]:
    tok = await _token(user)
    try:
        return [f["name"] for f in await dc.list_children(tok, link["id"], only_folders=True)]
    except dc.DriveError as e:
        raise HTTPException(409, str(e))


@router.get("/tenders/{tender_id}/folder-plan")
async def folder_plan(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    """What 'Set up job folders' would do in the linked folder. Read-only: nothing is created here."""
    t = await _tender(user, tender_id)
    link = t.get("drive_folder")
    if not link:
        raise HTTPException(409, "Link this tender to a Drive folder first.")
    doc = await _integration(user)
    return {"folder": link, "plan": plan_folders(await _top_folder_names(user, link)), "can_write": bool(doc and dc.can_write(doc.get("scopes", "")))}


@router.post("/tenders/{tender_id}/folders")
async def setup_folders(tender_id: str, body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    """Create the missing job subfolders. where='linked' adds them inside the linked folder. where='new' makes the job folder inside the
    company's jobs folder as <jobs folder> / <Client> / <Job name> (an existing client or job folder of that name is reused, never duplicated),
    adds 00-07 there and links the tender to it. Never in My Drive. New folders only: nothing is renamed, moved, overwritten or deleted."""
    t = await _tender(user, tender_id)
    doc = await _integration(user)
    if not doc or not dc.can_write(doc.get("scopes", "")):
        raise HTTPException(409, "Drive has only been given read-only access. Press 'Allow Drive to add folders' first.")
    where = body.get("where", "linked")
    if where not in ("linked", "new"):
        raise HTTPException(422, "Choose where to create the folders.")
    tok = await _token(user)
    db = get_db()
    created: list[str] = []
    try:
        if where == "new":
            jobs_root = await _jobs_root(user)
            if not jobs_root:
                raise HTTPException(409, "Choose the company's jobs folder first (for example 'Blackline Estimating'). New job folders go inside it, never in My Drive.")
            if not dc.can_write_anywhere(doc.get("scopes", "")):
                raise HTTPException(409, "Drive needs the permission to add folders inside your existing folders. Press 'Allow Drive to add folders' and approve it.")
            client_name, job_name = _clean_name(body.get("client") or t.get("client"), "client"), _clean_name(body.get("job") or t.get("name"), "job")
            cf = await dc.find_folder(tok, jobs_root["id"], client_name)
            if not cf:
                cf = await dc.create_folder(tok, client_name, jobs_root["id"])
                created.append(f"{client_name} (client folder)")
            jf = await dc.find_folder(tok, cf["id"], job_name)
            if not jf:
                jf = await dc.create_folder(tok, job_name, cf["id"])
                created.append(f"{job_name} (job folder)")
                names: list[str] = []
            else:
                names = [f["name"] for f in await dc.list_children(tok, jf["id"], only_folders=True)]
            if not jf.get("webViewLink"):
                jf = {**jf, **(await dc.get_file(tok, jf["id"]))}
            link = {"id": jf["id"], "name": jf["name"], "url": jf.get("webViewLink", ""), "linked_at": now().isoformat(),
                    "path": f"{jobs_root['name']} / {cf['name']} / {jf['name']}"}
            await db.tenders.update_one({"_id": t["_id"]}, {"$set": {"drive_folder": link}})
        else:
            link = t.get("drive_folder")
            if not link:
                raise HTTPException(409, "Link this tender to a Drive folder first.")
            names = [f["name"] for f in await dc.list_children(tok, link["id"], only_folders=True)]
        for step in plan_folders(names):
            if step["action"] == "create":
                await dc.create_folder(tok, step["name"], link["id"])
                created.append(step["name"])
    except dc.DriveError as e:
        await audit(db, user, "drive.setup_folders_failed", t["_id"], f"{len(created)} created before the error")
        raise HTTPException(409, f"{e} ({len(created)} folder(s) were created before this stopped.)" if created else str(e))
    await audit(db, user, "drive.setup_folders", t["_id"], f"{where}: {len(created)} created")
    return {"created": created, "folder": link, "plan": plan_folders(names + [c for c in created if c[:2].isdigit()])}


@router.get("/tenders/{tender_id}/files")
async def files(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    """Live listing of the linked folder with latest/superseded analysis and a check against the 01-07 structure."""
    t = await _tender(user, tender_id)
    link = t.get("drive_folder")
    if not link:
        raise HTTPException(409, "No Drive folder is linked to this tender yet.")
    tok = await _token(user)
    try:
        items, truncated = await dc.walk(tok, link["id"])
    except dc.DriveError as e:
        raise HTTPException(409, str(e))
    res = analyse(items)
    top = [i["name"] for i in items if i["is_folder"] and not i["path"]]
    docs = [f for f in res["files"] if not f["is_folder"]]
    reads = {d["file_id"]: d async for d in get_db().doc_texts.find({"org_id": user["org_id"], "tender_id": t["_id"]}, {"pages": 0})}
    for f in res["files"]:
        d = reads.get(f["id"])
        f["read"] = None if not d else {"status": d["status"], "read_at": d["read_at"].isoformat(), "pages": d["page_count"], "chars": d["chars"],
                                        "stale": d["modified"] != f["modified"], "warnings": d["warnings"]}
    await audit(get_db(), user, "drive.list", t["_id"], f"{len(docs)} files")
    return {"folder": link, "files": res["files"], "truncated": truncated, "structure": check_structure(top),
            "counts": {"files": len(docs), "latest_revisions": sum(1 for f in docs if f["latest"]),
                       "superseded": sum(1 for f in docs if f["superseded_by"]), "ambiguous_groups": res["ambiguous_groups"],
                       "loose_in_root": sum(1 for f in docs if not f["path"])}}


MAX_READ_BATCH = 25
MAX_CHARS_PER_FILE = 3_000_000


def _summary(d: dict[str, Any]) -> dict[str, Any]:
    return {"file_id": d["file_id"], "name": d["name"], "path": d["path"], "revision": d.get("revision"), "status": d["status"], "method": d["method"],
            "pages": d["page_count"], "chars": d["chars"], "warnings": d["warnings"], "read_at": d["read_at"].isoformat(), "modified": d["modified"]}


@router.post("/tenders/{tender_id}/read")
async def read_files(tender_id: str, body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    """Download the chosen files (read-only), pull out their text page by page and store the text (not the original file).
    Only files inside the tender's linked folder can be read."""
    t = await _tender(user, tender_id)
    link = t.get("drive_folder")
    if not link:
        raise HTTPException(409, "No Drive folder is linked to this tender yet.")
    ids = [str(i) for i in body.get("file_ids", [])][:MAX_READ_BATCH]
    if not ids:
        raise HTTPException(422, f"Choose at least one file (up to {MAX_READ_BATCH} at a time).")
    tok = await _token(user)
    try:
        items, _ = await dc.walk(tok, link["id"])
    except dc.DriveError as e:
        raise HTTPException(409, str(e))
    by_id = {f["id"]: f for f in analyse(items)["files"] if not f["is_folder"]}
    db, out = get_db(), []
    for fid in ids:
        f = by_id.get(fid)
        if not f:
            out.append({"file_id": fid, "name": fid, "status": "failed", "warnings": ["That file is not inside this tender's folder."], "pages": 0}); continue
        try:
            name, mime, data = await dc.download(tok, f)
            r = doc_text.extract(name, mime, data)
        except dc.DriveError as e:
            out.append({"file_id": fid, "name": f["name"], "status": "failed", "warnings": [str(e)], "pages": 0}); continue
        pages, total = [], 0
        for p in r["pages"]:
            if total + len(p["text"]) > MAX_CHARS_PER_FILE:
                r["warnings"].append(f"Text was cut off at page {p['n']} (very large file)."); break
            pages.append(p); total += len(p["text"])
        doc = {"_id": f"{t['_id']}:{fid}", "org_id": user["org_id"], "tender_id": t["_id"], "file_id": fid, "name": f["name"], "path": f["path"], "mime": f["mime"],
               "modified": f["modified"], "revision": f.get("revision"), "latest": f.get("latest"), "superseded_by": f.get("superseded_by"),
               "in_archive": bool(f.get("in_archive")), "status": r["status"], "method": r["method"], "warnings": r["warnings"],
               "pages": pages, "page_count": len(pages), "chars": total, "read_at": now(), "read_by": user["_id"]}
        await db.doc_texts.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        out.append(_summary(doc))
    await audit(db, user, "drive.read", t["_id"], f"{len(ids)} files requested, {sum(1 for o in out if o['status'] in ('ok', 'partial'))} read")
    return {"results": out}


@router.get("/tenders/{tender_id}/texts")
async def texts(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    ds = await get_db().doc_texts.find({"org_id": user["org_id"], "tender_id": t["_id"]}, {"pages": 0}).sort("name", 1).to_list(2000)
    return {"texts": [_summary(d) for d in ds]}


@router.get("/tenders/{tender_id}/texts/{file_id}")
async def text_pages(tender_id: str, file_id: str, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    d = await get_db().doc_texts.find_one({"_id": f"{t['_id']}:{file_id}", "org_id": user["org_id"]})
    if not d:
        raise HTTPException(404, "That file has not been read yet.")
    return {**_summary(d), "pages_text": d["pages"]}
