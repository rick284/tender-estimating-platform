"""Runtime configuration from environment variables (no secrets in code)."""
from __future__ import annotations
import os
import secrets

ENV = os.environ.get("ENV", "development")          # "production" enforces strict settings
IS_PROD = ENV == "production"
MONGO_URL = os.environ.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME", "tender_platform")
CORS_ORIGINS = [o.strip().rstrip("/") for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
ACCESS_TOKEN_HOURS = int(os.environ.get("ACCESS_TOKEN_HOURS", "12"))
# Open sign-up is off unless explicitly enabled. The very first account can always be created.
REGISTRATION_OPEN = os.environ.get("REGISTRATION_OPEN", "false").lower() == "true"
USE_MOCK_DB = os.environ.get("USE_MOCK_DB", "false").lower() == "true" and not IS_PROD
# If set, only this email may create the very first account (protects a fresh deployment).
BOOTSTRAP_EMAIL = os.environ.get("BOOTSTRAP_EMAIL", "").strip().lower()
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
LOGIN_MAX_FAILURES = 8
LOGIN_WINDOW_MINUTES = 15


def _jwt_secret() -> str:
    s = os.environ.get("JWT_SECRET", "")
    if IS_PROD and len(s) < 32:
        raise RuntimeError("JWT_SECRET must be set to a random value of at least 32 characters in production")
    return s or secrets.token_urlsafe(48)           # dev: random per process (sessions reset on restart)


JWT_SECRET = _jwt_secret()
if IS_PROD and not MONGO_URL:
    raise RuntimeError("MONGO_URL must be set in production")
