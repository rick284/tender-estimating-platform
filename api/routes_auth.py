from __future__ import annotations
import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

import config
from db import get_db
from security import (EMAIL_RE, create_token, current_user, hash_password, public_user, validate_password,
                      verify_password)
from services import audit, new_id, now

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)
    name: str = Field(min_length=1, max_length=120)
    company: str = Field(min_length=1, max_length=160)


class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


@router.get("/config")
async def auth_config():
    """Lets the sign-in screen know whether to offer 'Create account'."""
    db = get_db()
    first = await db.users.count_documents({}) == 0
    return {"registration_open": config.REGISTRATION_OPEN or first, "first_account": first}


@router.post("/register")
async def register(body: RegisterIn):
    db = get_db()
    first = await db.users.count_documents({}) == 0
    if not (config.REGISTRATION_OPEN or first):
        raise HTTPException(403, "Sign-up is by invitation only.")
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    if first and config.BOOTSTRAP_EMAIL and email != config.BOOTSTRAP_EMAIL:
        raise HTTPException(403, "This workspace can only be created by its designated owner.")
    validate_password(body.password)
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "An account with that email already exists.")
    org = {"_id": new_id(), "name": body.company.strip(), "created_at": now()}
    await db.orgs.insert_one(org)
    user = {"_id": new_id(), "org_id": org["_id"], "email": email, "name": body.name.strip(), "role": "owner",
            "password_hash": hash_password(body.password), "active": True, "created_at": now()}
    await db.users.insert_one(user)
    await audit(db, user, "register", user["_id"])
    return {"token": create_token(user), "user": public_user(user, org["name"])}


@router.post("/login")
async def login(body: LoginIn, request: Request):
    db = get_db()
    email = body.email.strip().lower()
    since = now() - dt.timedelta(minutes=config.LOGIN_WINDOW_MINUTES)
    recent = await db.login_attempts.count_documents({"email": email, "ts": {"$gte": since}})
    if recent >= config.LOGIN_MAX_FAILURES:
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
    user = await db.users.find_one({"email": email, "active": True})
    if not verify_password(body.password, user["password_hash"] if user else None):
        await db.login_attempts.insert_one({"_id": new_id(), "email": email, "ts": now(),
                                            "ip": request.client.host if request.client else ""})
        raise HTTPException(401, "Email or password is incorrect.")
    await db.login_attempts.delete_many({"email": email})
    org = await db.orgs.find_one({"_id": user["org_id"]})
    return {"token": create_token(user), "user": public_user(user, org["name"] if org else None)}


@router.get("/me")
async def me(user: dict[str, Any] = Depends(current_user)):
    org = await get_db().orgs.find_one({"_id": user["org_id"]})
    return public_user(user, org["name"] if org else None)
