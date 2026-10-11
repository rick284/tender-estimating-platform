from __future__ import annotations
import datetime as dt
import hashlib
import io
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

import config
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook
from tender_engine.inputs import to_json

XLSX_MAGIC = b"PK\x03\x04"
STAGES = ("estimating", "submitted", "won", "lost", "withdrawn")


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


def _compute(data: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        imported = load_master_workbook(io.BytesIO(data))
        return compute_estimate(imported), to_json(imported)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception:
        raise HTTPException(422, "This file could not be read as a Master Estimate Workbook.")


async def read_workbook(upload) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Validate an uploaded workbook and run the engine on it (off the event loop)."""
    if not (upload.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, "Please upload an Excel (.xlsx) workbook.")
    data = await upload.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 25 MB.")
    if not data.startswith(XLSX_MAGIC):
        raise HTTPException(400, "That file is not a valid .xlsx workbook.")
    est, inputs = await run_in_threadpool(_compute, data)
    return data, est, inputs


def revision_label(est: dict[str, Any], filename: str) -> str:
    first = (est["meta"].get("snapshot") or "").split(" ")[0]
    if re.match(r"^Rev\w+$", first, re.I):
        return first
    m = re.search(r"(Rev\w+)", filename or "", re.I)
    return m.group(1) if m else Path(filename or "workbook").stem[:40]


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def summarise(est: dict[str, Any], label: str) -> dict[str, Any]:
    c = est["controls"]
    return {
        "label": label, "all_in": est["summary"]["all_in"], "siteworks_tender": est["summary"]["siteworks_tender"],
        "known_cost": est["summary"]["known_cost"], "release": c.get("cover_release", ""),
        "red_risks": int(c["red_risks"]) if str(c.get("red_risks", "")).isdigit() else None,
        "reconciled": est["reconciled"], "edited": est.get("edited", False), "gross_margin_on_sell": est["summary"]["gross_margin_on_sell"],
    }


def revision_doc(tender: dict[str, Any], n: int, label: str, est: dict[str, Any], user: dict[str, Any],
                 filename: str, sha: str, inputs: dict[str, Any] | None = None, changes: list | None = None,
                 parent_n: int | None = None, note: str = "") -> dict[str, Any]:
    return {"_id": new_id(), "tender_id": tender["_id"], "org_id": tender["org_id"], "n": n, "label": label,
            "lifecycle": "WORKING", "created_at": now(), "created_by": user["_id"], "source_filename": filename,
            "source_sha256": sha, "estimate": est, "inputs": inputs, "changes": changes or [],
            "parent_n": parent_n, "note": note, "all_in": est["summary"]["all_in"]}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def audit(db, user: dict[str, Any] | None, action: str, target: str = "", detail: str = "") -> None:
    await db.audit.insert_one({"_id": new_id(), "org_id": user["org_id"] if user else None,
                               "user_id": user["_id"] if user else None, "action": action,
                               "target": target, "detail": detail[:300], "ts": now()})
