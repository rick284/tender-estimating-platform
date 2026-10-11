"""HTTP API for the tender estimating platform."""
from __future__ import annotations
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config                                   # noqa: E402
from db import ensure_indexes, get_db           # noqa: E402
from routes_auth import router as auth_router   # noqa: E402
from routes_tenders import router as tenders_router  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ensure_indexes(get_db())
    yield


app = FastAPI(title="Tender Estimating Platform API", version="0.2.0", lifespan=lifespan,
              docs_url=None if config.IS_PROD else "/docs", redoc_url=None, openapi_url=None if config.IS_PROD else "/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET", "POST", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type"])
app.include_router(auth_router)
app.include_router(tenders_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
