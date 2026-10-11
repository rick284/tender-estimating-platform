"""HTTP API for the tender estimating platform (Phase 1a: import + compute, stateless)."""
from __future__ import annotations
import io
import os
import sys
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from tender_engine.estimate import compute_estimate          # noqa: E402
from tender_engine.importers import load_master_workbook    # noqa: E402

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
XLSX_MAGIC = b"PK\x03\x04"

app = FastAPI(title="Tender Estimating Platform API", version="0.1.0")
origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


def _compute(data: bytes) -> dict:
    try:
        imported = load_master_workbook(io.BytesIO(data))
        return compute_estimate(imported)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="This file could not be read as a Master Estimate Workbook.")


@app.post("/api/estimates/import")
async def import_estimate(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Please upload an Excel (.xlsx) workbook.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 25 MB.")
    if not data.startswith(XLSX_MAGIC):
        raise HTTPException(status_code=400, detail="That file is not a valid .xlsx workbook.")
    return _compute(data)


@app.get("/api/demo")
def demo():
    """Computes the workbook named by DEMO_WORKBOOK (development only; never set in production)."""
    path = os.environ.get("DEMO_WORKBOOK")
    if not path or not Path(path).is_file():
        raise HTTPException(status_code=404, detail="No demo workbook configured.")
    return _compute(Path(path).read_bytes())
