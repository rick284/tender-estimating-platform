from __future__ import annotations
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from db import get_db
from security import current_user
from services import (STAGES, audit, new_id, norm_name, now, read_workbook, revision_doc, revision_label, sha256,
                      summarise)
from tender_engine.diff import diff_estimates

router = APIRouter(prefix="/api/tenders", tags=["tenders"])


def _out(t: dict[str, Any]) -> dict[str, Any]:
    return {"id": t["_id"], "name": t["name"], "client": t.get("client", ""), "location": t.get("location", ""),
            "stage": t["stage"], "latest_rev": t["latest_rev"], "summary": t["summary"],
            "created_at": t["created_at"], "updated_at": t["updated_at"]}


def _rev_out(r: dict[str, Any]) -> dict[str, Any]:
    return {"n": r["n"], "label": r["label"], "lifecycle": r["lifecycle"], "created_at": r["created_at"],
            "source_filename": r["source_filename"], "all_in": r.get("all_in")}


async def _tender(user: dict[str, Any], tender_id: str) -> dict[str, Any]:
    t = await get_db().tenders.find_one({"_id": tender_id, "org_id": user["org_id"]})
    if not t:
        raise HTTPException(404, "Tender not found.")
    return t


@router.get("")
async def list_tenders(user: dict[str, Any] = Depends(current_user)):
    docs = await get_db().tenders.find({"org_id": user["org_id"]}).sort("updated_at", -1).to_list(500)
    tenders = [_out(t) for t in docs]
    by_stage = {s: {"count": 0, "value": 0.0} for s in STAGES}
    for t in tenders:
        by_stage[t["stage"]]["count"] += 1
        by_stage[t["stage"]]["value"] += t["summary"]["all_in"] or 0
    return {"tenders": tenders, "totals": {"count": len(tenders), "by_stage": by_stage}}


@router.post("")
async def create_tender(file: UploadFile = File(...), name: str = Form(""), client: str = Form(""),
                        label: str = Form(""), user: dict[str, Any] = Depends(current_user)):
    db = get_db()
    data, est = await read_workbook(file)
    project = (name or est["meta"].get("project") or "Untitled tender").strip()[:160]
    lab = (label.strip() or revision_label(est, file.filename or ""))[:40]
    t = {"_id": new_id(), "org_id": user["org_id"], "name": project, "client": client.strip()[:160],
         "location": est["meta"].get("location", ""), "stage": "estimating", "latest_rev": 1,
         "summary": summarise(est, lab), "created_at": now(), "updated_at": now(), "created_by": user["_id"],
         "project_key": norm_name(est["meta"].get("project", project))}
    await db.tenders.insert_one(t)
    rev = revision_doc(t, 1, lab, est, user, file.filename or "", sha256(data))
    rev["all_in"] = est["summary"]["all_in"]
    await db.revisions.insert_one(rev)
    await audit(db, user, "tender.create", t["_id"], project)
    return _out(t)


@router.get("/{tender_id}")
async def get_tender(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    revs = await get_db().revisions.find({"tender_id": tender_id, "org_id": user["org_id"]},
                                         {"estimate": 0}).sort("n", -1).to_list(200)
    return {**_out(t), "revisions": [_rev_out(r) for r in revs]}


class TenderPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    client: str | None = Field(default=None, max_length=160)
    stage: str | None = None


@router.patch("/{tender_id}")
async def patch_tender(tender_id: str, body: TenderPatch, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    upd: dict[str, Any] = {}
    if body.name is not None:
        upd["name"] = body.name.strip()
    if body.client is not None:
        upd["client"] = body.client.strip()
    if body.stage is not None:
        if body.stage not in STAGES:
            raise HTTPException(422, f"Stage must be one of: {', '.join(STAGES)}.")
        upd["stage"] = body.stage
    if upd:
        upd["updated_at"] = now()
        await get_db().tenders.update_one({"_id": t["_id"], "org_id": user["org_id"]}, {"$set": upd})
        await audit(get_db(), user, "tender.update", t["_id"], ",".join(upd))
    return _out(await _tender(user, tender_id))


@router.delete("/{tender_id}")
async def delete_tender(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    if user["role"] != "owner":
        raise HTTPException(403, "Only an account owner can delete a tender.")
    t = await _tender(user, tender_id)
    db = get_db()
    await db.revisions.delete_many({"tender_id": t["_id"], "org_id": user["org_id"]})
    await db.tenders.delete_one({"_id": t["_id"], "org_id": user["org_id"]})
    await audit(db, user, "tender.delete", t["_id"], t["name"])
    return {"deleted": True}


@router.post("/{tender_id}/revisions")
async def add_revision(tender_id: str, file: UploadFile = File(...), label: str = Form(""),
                       confirm_different_project: bool = Form(False), user: dict[str, Any] = Depends(current_user)):
    db = get_db()
    t = await _tender(user, tender_id)
    data, est = await read_workbook(file)
    digest = sha256(data)
    if await db.revisions.find_one({"tender_id": t["_id"], "source_sha256": digest}):
        raise HTTPException(409, "This exact workbook has already been uploaded to this tender.")
    if norm_name(est["meta"].get("project", "")) != t.get("project_key") and not confirm_different_project:
        raise HTTPException(409, f"This workbook is for \"{est['meta'].get('project', 'a different project')}\", not \"{t['name']}\". "
                                 "Upload it as a new tender, or confirm it belongs to this one.")
    n = t["latest_rev"] + 1
    lab = (label.strip() or revision_label(est, file.filename or ""))[:40]
    rev = revision_doc(t, n, lab, est, user, file.filename or "", digest)
    rev["all_in"] = est["summary"]["all_in"]
    await db.revisions.insert_one(rev)
    await db.tenders.update_one({"_id": t["_id"], "org_id": user["org_id"]},
                                {"$set": {"latest_rev": n, "summary": summarise(est, lab), "updated_at": now()}})
    await audit(db, user, "revision.create", t["_id"], f"{lab} (n={n})")
    return _rev_out(rev)


async def _estimate(user: dict[str, Any], tender_id: str, n: int) -> dict[str, Any]:
    r = await get_db().revisions.find_one({"tender_id": tender_id, "org_id": user["org_id"], "n": n})
    if not r:
        raise HTTPException(404, "Revision not found.")
    return r


@router.get("/{tender_id}/revisions/{n}")
async def get_revision(tender_id: str, n: int, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    r = await _estimate(user, t["_id"], n)
    return {"tender": _out(t), "revision": _rev_out(r), "estimate": r["estimate"]}


@router.get("/{tender_id}/compare")
async def compare(tender_id: str, a: int, b: int, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    ra, rb = await _estimate(user, t["_id"], a), await _estimate(user, t["_id"], b)
    diff = await run_in_threadpool(diff_estimates, ra["estimate"], rb["estimate"])
    return {"a": _rev_out(ra), "b": _rev_out(rb), "diff": diff}
