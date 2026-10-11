from __future__ import annotations
import datetime as dt
import re
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import config
from db import get_db

bearer = HTTPBearer(auto_error=False)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# A fixed hash so that unknown emails cost the same time as wrong passwords (no user enumeration by timing).
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt(rounds=12))


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(pw: str, hashed: str | None) -> bool:
    target = hashed.encode() if hashed else _DUMMY_HASH
    raw = pw.encode()
    if len(raw) > 72:                      # bcrypt limit; such a password can never have been set
        bcrypt.checkpw(b"x", target)
        return False
    ok = bcrypt.checkpw(raw, target)
    return ok and hashed is not None


def validate_password(pw: str) -> None:
    if len(pw) < 10:
        raise HTTPException(422, "Password must be at least 10 characters.")
    if len(pw.encode()) > 72:
        raise HTTPException(422, "Password must be 72 characters or fewer.")


def create_token(user: dict[str, Any]) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": user["_id"], "org": user["org_id"], "iat": now, "exp": now + dt.timedelta(hours=config.ACCESS_TOKEN_HOURS)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


async def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, Any]:
    if creds is None:
        raise HTTPException(401, "Not signed in.")
    try:
        data = jwt.decode(creds.credentials, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    user = await get_db().users.find_one({"_id": data.get("sub"), "org_id": data.get("org"), "active": True})
    if not user:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    return user


def public_user(u: dict[str, Any], org_name: str | None = None) -> dict[str, Any]:
    return {"id": u["_id"], "email": u["email"], "name": u["name"], "role": u["role"], "org_id": u["org_id"], "org_name": org_name}
