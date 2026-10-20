from __future__ import annotations
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from db import get_db
from security import current_user
from services import (STAGES, audit, new_id, norm_name, now, read_workbook, revision_doc, revision_label, sha256,
                      summarise)
from tender_engine.blank import IntakeError, blank_from_template
from tender_engine.diff import diff_estimates
from tender_engine.edits import EditError, apply_edits
from tender_engine.estimate import compute_estimate
from tender_engine.inputs import from_json, to_json

log = logging.getLogger("tender.api")
router = APIRouter(prefix="/api/tenders", tags=["tenders"])


def _out(t: dict[str, Any]) -> dict[str, Any]:
    return {"id": t["_id"], "name": t["name"], "client": t.get("client", ""), "location": t.get("location", ""),
            "stage": t["stage"], "latest_rev": t["latest_rev"], "summary": t["summary"],
            "created_at": t["created_at"], "updated_at": t["updated_at"]}


def _rev_out(r: dict[str, Any]) -> dict[str, Any]:
    return {"n": r["n"], "label": r["label"], "lifecycle": r["lifecycle"], "created_at": r["created_at"],
            "source_filename": r["source_filename"], "all_in": r.get("all_in"),
            "has_inputs": bool(r.get("inputs")), "parent_n": r.get("parent_n"), "note": r.get("note", ""),
            "change_count": len(r.get("changes") or []), "edited": r.get("parent_n") is not None}


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
    data, est, inputs = await read_workbook(file)
    project = (name or est["meta"].get("project") or "Untitled tender").strip()[:160]
    lab = (label.strip() or revision_label(est, file.filename or ""))[:40]
    t = {"_id": new_id(), "org_id": user["org_id"], "name": project, "client": client.strip()[:160],
         "location": est["meta"].get("location", ""), "stage": "estimating", "latest_rev": 1,
         "summary": summarise(est, lab), "created_at": now(), "updated_at": now(), "created_by": user["_id"],
         "project_key": norm_name(est["meta"].get("project", project))}
    await db.tenders.insert_one(t)
    rev = revision_doc(t, 1, lab, est, user, file.filename or "", sha256(data), inputs=inputs)
    await db.revisions.insert_one(rev)
    await audit(db, user, "tender.create", t["_id"], project)
    await _programme_from_workbook(db, user, t, rev)
    return _out(t)


async def _programme_from_workbook(db: Any, user: dict[str, Any], t: dict[str, Any], rev: dict[str, Any]) -> None:
    """A programme in the uploaded workbook becomes the tender's Gantt programme too. Never stops the upload."""
    try:
        from routes_programme import create_from_workbook
        await create_from_workbook(db, user, t, rev)
    except Exception:                                               # noqa: BLE001
        log.exception("could not build the programme from the workbook")


class BlankIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    template_tender_id: str | None = None
    intake: dict[str, str] = Field(default_factory=dict)


@router.post("/blank")
async def create_blank_tender(body: BlankIn, user: dict[str, Any] = Depends(current_user)):
    """Start a tender from scratch. Rates, overhead/margin and other commercial settings come from an earlier
    tender in this workspace (the chosen one, or the most recently updated one that can be edited)."""
    db = get_db()
    if body.template_tender_id:
        candidates = [await _tender(user, body.template_tender_id)]
    else:
        candidates = await db.tenders.find({"org_id": user["org_id"]}).sort("updated_at", -1).to_list(50)
    src = None
    for c in candidates:
        r = await db.revisions.find_one({"tender_id": c["_id"], "org_id": user["org_id"], "inputs": {"$ne": None}}, sort=[("n", -1)])
        if r:
            src = r
            break
    if src is None:
        raise HTTPException(409, "A new tender borrows its rates and commercial settings from an earlier one, and this workspace "
                                 "doesn't have one that can be edited yet. Upload a Master Estimate Workbook first (re-upload an older one to enable editing).")
    try:
        m = from_json(src["inputs"])
        blank = await run_in_threadpool(blank_from_template, m, body.name, body.intake)
    except IntakeError as e:
        raise HTTPException(422, str(e))
    est = await run_in_threadpool(compute_estimate, blank)
    inputs = to_json(blank)
    lab = "Rev0"
    t = {"_id": new_id(), "org_id": user["org_id"], "name": body.name.strip()[:160], "client": body.intake.get("client", "").strip()[:160],
         "location": body.intake.get("location", "").strip()[:160], "stage": "estimating", "latest_rev": 1,
         "summary": summarise(est, lab), "created_at": now(), "updated_at": now(), "created_by": user["_id"],
         "project_key": norm_name(body.name)}
    await db.tenders.insert_one(t)
    rev = revision_doc(t, 1, lab, est, user, "(started from scratch)", sha256(json.dumps(inputs, sort_keys=True).encode() + t["_id"].encode()), inputs=inputs)
    await db.revisions.insert_one(rev)
    await audit(db, user, "tender.create_blank", t["_id"], f"{t['name']} from tender {src['tender_id']} rev {src['n']}")
    return _out(t)


@router.get("/{tender_id}")
async def get_tender(tender_id: str, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    db = get_db()
    # inputs and estimates are large; only fetch which revisions HAVE inputs, not the inputs themselves
    revs = await db.revisions.find({"tender_id": tender_id, "org_id": user["org_id"]},
                                   {"estimate": 0, "inputs": 0}).sort("n", -1).to_list(200)
    editable = {d["_id"] async for d in db.revisions.find({"tender_id": tender_id, "org_id": user["org_id"], "inputs": {"$ne": None}}, {"_id": 1})}
    return {**_out(t), "revisions": [_rev_out({**r, "inputs": True if r["_id"] in editable else None}) for r in revs]}


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
    data, est, inputs = await read_workbook(file)
    digest = sha256(data)
    dup = await db.revisions.find_one({"tender_id": t["_id"], "source_sha256": digest})
    gaps = [k for k in ("register", "quotes", "programme", "risk_truth", "management_reserve", "scope") if dup and dup.get("inputs") and k not in dup["inputs"] and inputs.get(k)]
    if dup and dup.get("parent_n") is None and gaps:
        # Saved before the tender register / quote register / Risk Truth existed: add what is read from the same workbook. Nothing else changes.
        upd = {f"inputs.{k}": inputs[k] for k in gaps}
        if "risk_truth" in gaps and "register" not in gaps:
            # the workbook's Risk Truth tab is the controlling risk list: swap the register's risk items for it, keep everything else
            upd["inputs.register"] = [x for x in dup["inputs"].get("register", []) if x.get("kind") != "risk"] + [x for x in inputs.get("register", []) if x.get("kind") == "risk"]
        await db.revisions.update_one({"_id": dup["_id"]}, {"$set": upd})
        await audit(db, user, "revision.add_register", t["_id"], f"{dup['label']} (n={dup['n']})")
        return {**_rev_out({**dup, "inputs": dup["inputs"]}), "upgraded": True}
    if dup and not dup.get("inputs"):
        # Saved before editing existed: attach the inputs so it can be edited. The stored estimate is left untouched.
        await db.revisions.update_one({"_id": dup["_id"]}, {"$set": {"inputs": inputs}})
        await audit(db, user, "revision.enable_editing", t["_id"], f"{dup['label']} (n={dup['n']})")
        return {**_rev_out({**dup, "inputs": inputs}), "upgraded": True}
    if dup:
        raise HTTPException(409, "This exact workbook has already been uploaded to this tender.")
    if norm_name(est["meta"].get("project", "")) != t.get("project_key") and not confirm_different_project:
        raise HTTPException(409, f"This workbook is for \"{est['meta'].get('project', 'a different project')}\", not \"{t['name']}\". "
                                 "Upload it as a new tender, or confirm it belongs to this one.")
    n = t["latest_rev"] + 1
    lab = (label.strip() or revision_label(est, file.filename or ""))[:40]
    rev = revision_doc(t, n, lab, est, user, file.filename or "", digest, inputs=inputs)
    await db.revisions.insert_one(rev)
    await db.tenders.update_one({"_id": t["_id"], "org_id": user["org_id"]},
                                {"$set": {"latest_rev": n, "summary": summarise(est, lab), "updated_at": now()}})
    await audit(db, user, "revision.create", t["_id"], f"{lab} (n={n})")
    await _programme_from_workbook(db, user, t, rev)
    return _rev_out(rev)


async def _estimate(user: dict[str, Any], tender_id: str, n: int) -> dict[str, Any]:
    r = await get_db().revisions.find_one({"tender_id": tender_id, "org_id": user["org_id"], "n": n})
    if not r:
        raise HTTPException(404, "Revision not found.")
    return r


async def _estimate_with_schedule(r: dict[str, Any]) -> dict[str, Any]:
    """Revisions saved before price schedules existed get one rebuilt from their saved inputs (the stored estimate is left untouched)."""
    est = r["estimate"]
    missing = [k for k in ("schedule", "register", "register_summary", "quotes", "programme", "risk_truth", "management_reserve", "scope") if k not in est]
    if not missing or not r.get("inputs"):
        return est
    fresh = await run_in_threadpool(lambda: compute_estimate(from_json(r["inputs"])))
    return {**est, **{k: fresh[k] for k in missing}}


@router.get("/{tender_id}/revisions/{n}")
async def get_revision(tender_id: str, n: int, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    r = await _estimate(user, t["_id"], n)
    return {"tender": _out(t), "revision": {**_rev_out(r), "changes": r.get("changes") or []}, "estimate": await _estimate_with_schedule(r)}


@router.get("/{tender_id}/compare")
async def compare(tender_id: str, a: int, b: int, user: dict[str, Any] = Depends(current_user)):
    t = await _tender(user, tender_id)
    ra, rb = await _estimate(user, t["_id"], a), await _estimate(user, t["_id"], b)
    diff = await run_in_threadpool(diff_estimates, ra["estimate"], rb["estimate"])
    return {"a": _rev_out(ra), "b": _rev_out(rb), "diff": diff}


# ------------------------------------------------------------------ editing
class EditsIn(BaseModel):
    edits: list[dict[str, Any]] = Field(default_factory=list, max_length=500)


class SaveIn(EditsIn):
    label: str = Field(default="", max_length=40)
    note: str = Field(default="", max_length=2000)


def _recalc(base_inputs: dict[str, Any], edits: list[dict[str, Any]]):
    """CPU work: apply validated edits to saved inputs and recompute. Returns (estimate, inputs_json, changes)."""
    try:
        m, changes = apply_edits(from_json(base_inputs), edits)
    except EditError as e:
        raise HTTPException(422, str(e))
    return compute_estimate(m), to_json(m), changes


async def _editable(user: dict[str, Any], tender_id: str, n: int):
    t = await _tender(user, tender_id)
    r = await _estimate(user, t["_id"], n)
    if not r.get("inputs"):
        raise HTTPException(409, "This revision was saved before editing was available. Upload the workbook again to edit it.")
    return t, r


@router.post("/{tender_id}/revisions/{n}/preview")
async def preview_edits(tender_id: str, n: int, body: EditsIn, user: dict[str, Any] = Depends(current_user)):
    """Recalculate with the proposed edits. Nothing is saved."""
    _, r = await _editable(user, tender_id, n)
    est, _, changes = await run_in_threadpool(_recalc, r["inputs"], body.edits)
    return {"estimate": est, "changes": changes,
            "base": {"all_in": r["estimate"]["summary"]["all_in"], "siteworks_tender": r["estimate"]["summary"]["siteworks_tender"]}}


@router.post("/{tender_id}/revisions/{n}/save")
async def save_edits(tender_id: str, n: int, body: SaveIn, user: dict[str, Any] = Depends(current_user)):
    """Save the edits as a NEW revision. The revision they were based on is left untouched."""
    from drive_filing import file_to_reviews, revision_markdown, scope_markdown
    db = get_db()
    t, r = await _editable(user, tender_id, n)
    note = body.note.strip()
    if len(note) < 5:
        raise HTTPException(422, "Write a short reason for the change (at least 5 characters).")
    log.info("save start tender=%s base=#%s edits=%s", tender_id, n, len(body.edits))
    est, inputs, changes = await run_in_threadpool(_recalc, r["inputs"], body.edits)
    if not changes:
        raise HTTPException(409, "There are no changes to save.")
    new_n = t["latest_rev"] + 1
    lab = (body.label.strip() or f"{r['label']}-ed{new_n}")[:40]
    rev = revision_doc(t, new_n, lab, est, user, "(edited in platform)", sha256(json.dumps(inputs, sort_keys=True).encode()),
                       inputs=inputs, changes=changes, parent_n=n, note=note)
    await db.revisions.insert_one(rev)
    await db.tenders.update_one({"_id": t["_id"], "org_id": user["org_id"]},
                                {"$set": {"latest_rev": new_n, "summary": summarise(est, lab), "updated_at": now()}})
    await audit(db, user, "revision.edit", t["_id"], f"{lab} from #{n}: {len(changes)} changes")
    log.info("save done tender=%s new=#%s changes=%s", tender_id, new_n, len(changes))
    out = _rev_out(rev)
    if any(c.get("target") == "scope" for c in changes):                       # the chat reads Drive, so a scope change is filed there as a new file (best effort, reported)
        stamp = now()
        text = scope_markdown(t.get("name", ""), lab, user.get("name", ""), stamp.strftime("%d-%b-%Y %H:%M UTC"), note, changes, (est.get("scope") or {}).get("items") or [])
        out["scope_filed"] = await file_to_reviews(user, t, f"SCOPE_CURRENT_{stamp.strftime('%Y-%m-%d_%H%M')}.md", text)
    stamp = now()                                                              # every saved revision also leaves a plain note of what changed (create-only, best effort, reported)
    rtext = revision_markdown(t.get("name", ""), lab, new_n, n, user.get("name", ""), stamp.strftime("%d-%b-%Y %H:%M UTC"), note, rev.get("all_in"), changes)
    out["revision_filed"] = await file_to_reviews(user, t, f"REVISION_NOTE_Rev{new_n:02d}_{stamp.strftime('%Y-%m-%d_%H%M')}.md", rtext)
    return out


# ------------------------------------------------------------------ client outputs
OUTPUTS = {
    "report.pdf": ("Estimate_Basis_Tender_Report", "application/pdf"),
    "schedule.pdf": ("Tender_Price_Schedule", "application/pdf"),
    "pricing.xlsx": ("Client_Pricing", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "verification-index.pdf": ("Supplier_Verification_Index", "application/pdf"),
    "evidence-notes.pdf": ("Supplier_Evidence_Notes", "application/pdf"),
    "programme.xlsx": ("Programme", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
}


def _build_output(kind: str, est: dict[str, Any], ctx_kw: dict[str, str], intake: dict[str, str]) -> bytes:
    from tender_engine.outputs import (OutputContext, evidence_notes_pdf, pricing_workbook, programme_workbook, report_pdf, schedule_pdf, verification_index_pdf)
    ctx = OutputContext(**ctx_kw)
    if kind == "verification-index.pdf":
        return verification_index_pdf(est, ctx)
    if kind == "evidence-notes.pdf":
        return evidence_notes_pdf(est, ctx)
    if kind == "programme.xlsx":
        return programme_workbook(est, ctx)
    if kind == "report.pdf":
        return report_pdf(est, ctx, intake)
    if kind == "schedule.pdf":
        return schedule_pdf(est, ctx)
    return pricing_workbook(est, ctx)


@router.get("/{tender_id}/revisions/{n}/outputs/{kind}")
async def download_output(tender_id: str, n: int, kind: str, user: dict[str, Any] = Depends(current_user)):
    """The client pack, generated from the stored estimate of a revision: report, price schedule PDF and pricing workbook."""
    if kind not in OUTPUTS:
        raise HTTPException(404, "Unknown output.")
    t = await _tender(user, tender_id)
    r = await _estimate(user, t["_id"], n)
    org = await get_db().orgs.find_one({"_id": user["org_id"]})
    est = await _estimate_with_schedule(r)
    if "schedule" not in est:
        raise HTTPException(409, "This revision was saved before client outputs were available. Upload its workbook again to enable them.")
    today = now()
    ctx_kw = {"company": (org or {}).get("name", ""), "prepared_by": user.get("name", ""), "project": t["name"], "client": t.get("client", ""),
              "location": t.get("location", ""), "revision": r["label"], "issue_date": f"{today.day} {today:%B %Y}"}
    from tender_engine.blank import INTAKE_FIELDS
    intake = {k: (est["meta"].get(k) or "") for k, _, _ in INTAKE_FIELDS}
    try:
        data = await run_in_threadpool(_build_output, kind, est, ctx_kw, intake)
    except ValueError as e:
        raise HTTPException(409, str(e))
    except ModuleNotFoundError:
        raise HTTPException(503, "Document generation isn't available on this server yet.")
    stem, mime = OUTPUTS[kind]
    safe = "".join(ch if ch.isalnum() else "_" for ch in t["name"]).strip("_")[:60] or "Tender"
    await audit(get_db(), user, "output.download", t["_id"], f"{kind} {r['label']}")
    return Response(content=data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{safe}_{stem}_{r["label"]}.{kind.split(".")[1]}"',
                                                            "Cache-Control": "no-store"})
