"""HTTP API for the tender estimating platform."""
from __future__ import annotations
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config                                   # noqa: E402
from db import ensure_indexes, get_db           # noqa: E402
from routes_auth import router as auth_router   # noqa: E402
from routes_tenders import router as tenders_router  # noqa: E402
from routes_weather import router as weather_router  # noqa: E402
from routes_drive import router as drive_router  # noqa: E402
from routes_ai import router as ai_router  # noqa: E402
from routes_takeoff import router as takeoff_router  # noqa: E402


log = logging.getLogger("tender.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await ensure_indexes(get_db())
    except Exception:  # database briefly unreachable: stay up so the host shows a clear status, retry on next start
        log.exception("Could not create database indexes at startup")
    yield


app = FastAPI(title="Tender Estimating Platform API", version="0.2.0", lifespan=lifespan,
              docs_url=None if config.IS_PROD else "/docs", redoc_url=None, openapi_url=None if config.IS_PROD else "/openapi.json")


@app.middleware("http")
async def never_fail_silently(request: Request, call_next):
    """Turn any unexpected error into a clear JSON message with a reference id (and a log entry with the traceback).
    Added BEFORE the CORS middleware so the CORS middleware wraps it: the browser then receives the message instead of
    an opaque 'network error'."""
    try:
        return await call_next(request)
    except Exception:
        ref = uuid.uuid4().hex[:8]
        log.exception("Unhandled error ref=%s %s %s", ref, request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": f"The server hit an unexpected problem (reference {ref}). Please try again; if it keeps happening, quote this reference."})


app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                   allow_headers=["Authorization", "Content-Type"])
app.include_router(auth_router)
app.include_router(tenders_router)
app.include_router(weather_router)
app.include_router(drive_router)
app.include_router(ai_router)
app.include_router(takeoff_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health/db")
async def health_db():
    """Open in a browser to check the database connection and that writes work. Reveals no data."""
    db = get_db()
    try:
        await db.command("ping")
        await db._healthcheck.insert_one({"_id": "probe", "ts": uuid.uuid4().hex})
        await db._healthcheck.delete_one({"_id": "probe"})
        return {"database": "ok", "read": "ok", "write": "ok"}
    except Exception as e:
        log.exception("Database health check failed")
        return JSONResponse(status_code=503, content={"database": "error", "problem": type(e).__name__})
