"""Minimal read-only Google Drive client (OAuth + file listing). The HTTP transport is injectable so tests never
touch the network. Scope is drive.readonly: the platform can look, never change or delete."""
from __future__ import annotations
import base64
import hashlib
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

import config
from drive_index import FOLDER_MIME

SCOPES = "https://www.googleapis.com/auth/drive.readonly openid email"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/drive/v3"
FIELDS = "nextPageToken, files(id,name,mimeType,modifiedTime,size,webViewLink,parents,shortcutDetails)"

# A transport can be swapped in tests: set drive_client.TRANSPORT = httpx.MockTransport(handler)
TRANSPORT: httpx.BaseTransport | None = None


class DriveError(Exception):
    """Message is safe to show to the user."""


def configured() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)


def _fernet() -> Fernet:
    key = config.TOKEN_ENC_KEY or config.JWT_SECRET
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def encrypt(s: str) -> str:
    return _fernet().encrypt(s.encode()).decode()


def decrypt(s: str) -> str:
    try:
        return _fernet().decrypt(s.encode()).decode()
    except InvalidToken as e:
        raise DriveError("The saved Google connection can no longer be read. Please disconnect and connect again.") from e


def auth_url(state: str) -> str:
    q = {"client_id": config.GOOGLE_CLIENT_ID, "redirect_uri": config.GOOGLE_REDIRECT_URI, "response_type": "code",
         "scope": SCOPES, "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state}
    return f"{AUTH_URL}?{urlencode(q)}"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=TRANSPORT, timeout=30)


async def _token_call(data: dict[str, str]) -> dict[str, Any]:
    async with _client() as c:
        r = await c.post(TOKEN_URL, data={"client_id": config.GOOGLE_CLIENT_ID, "client_secret": config.GOOGLE_CLIENT_SECRET, **data})
    if r.status_code != 200:
        raise DriveError("Google did not accept the sign-in. Try connecting again.")
    return r.json()


async def exchange_code(code: str) -> dict[str, Any]:
    return await _token_call({"code": code, "grant_type": "authorization_code", "redirect_uri": config.GOOGLE_REDIRECT_URI})


async def access_token(refresh_token: str) -> str:
    return (await _token_call({"refresh_token": refresh_token, "grant_type": "refresh_token"}))["access_token"]


async def _get(token: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
    async with _client() as c:
        r = await c.get(f"{API}{path}", params=params, headers={"Authorization": f"Bearer {token}"})
    if r.status_code in (401, 403):
        raise DriveError("Google Drive refused access. Reconnect Drive, or check the folder is shared with the connected account.")
    if r.status_code == 404:
        raise DriveError("That Drive folder was not found (it may have been moved or unshared).")
    if r.status_code != 200:
        raise DriveError("Google Drive had a problem. Please try again.")
    return r.json()


async def list_children(token: str, folder_id: str, only_folders: bool = False) -> list[dict[str, Any]]:
    q = f"'{folder_id.replace(chr(39), '')}' in parents and trashed=false"
    if only_folders:
        q += f" and mimeType='{FOLDER_MIME}'"
    out: list[dict[str, Any]] = []
    page = None
    while True:
        params = {"q": q, "fields": FIELDS, "pageSize": 1000, "orderBy": "name", "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if page:
            params["pageToken"] = page
        d = await _get(token, "/files", params)
        out += d.get("files", [])
        page = d.get("nextPageToken")
        if not page:
            return out


async def get_file(token: str, file_id: str) -> dict[str, Any]:
    return await _get(token, f"/files/{file_id}", {"fields": "id,name,mimeType,webViewLink", "supportsAllDrives": "true"})


async def userinfo_email(id_token_or_access: str) -> str:
    async with _client() as c:
        r = await c.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {id_token_or_access}"})
    return r.json().get("email", "") if r.status_code == 200 else ""


async def walk(token: str, root_id: str, max_depth: int = 6, max_files: int = 3000) -> tuple[list[dict[str, Any]], bool]:
    """Recursive listing. Returns (files, truncated). Each item has path (folders above it) and folder (its parent path)."""
    items: list[dict[str, Any]] = []
    stack = [(root_id, "", 0)]
    truncated = False
    while stack:
        fid, path, depth = stack.pop(0)
        for f in await list_children(token, fid):
            is_folder = f["mimeType"] == FOLDER_MIME
            items.append({"id": f["id"], "name": f["name"], "path": path, "folder": path, "mime": f["mimeType"], "is_folder": is_folder,
                          "modified": f.get("modifiedTime", ""), "size": int(f["size"]) if f.get("size") else None, "link": f.get("webViewLink", "")})
            if len(items) >= max_files:
                return items, True
            if is_folder:
                if depth + 1 < max_depth:
                    stack.append((f["id"], f"{path}/{f['name']}".lstrip("/"), depth + 1))
                else:
                    truncated = True
    return items, truncated


MAX_DOWNLOAD = 25 * 1024 * 1024
EXPORTS = {"application/vnd.google-apps.document": ("text/plain", ".txt"), "application/vnd.google-apps.spreadsheet": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")}


async def download(token: str, f: dict[str, Any]) -> tuple[str, str, bytes]:
    """Fetch one file's bytes (read-only). Google Docs/Sheets are exported. Returns (name, mime, data)."""
    mime, name = f["mime"], f["name"]
    if mime in EXPORTS:
        em, ext = EXPORTS[mime]
        path, params = f"/files/{f['id']}/export", {"mimeType": em}
        name, mime = name + ext, em
    else:
        path, params = f"/files/{f['id']}", {"alt": "media", "supportsAllDrives": "true"}
    if f.get("size") and f["size"] > MAX_DOWNLOAD:
        raise DriveError(f"{f['name']} is larger than {MAX_DOWNLOAD // 1048576} MB and was skipped.")
    async with _client() as c:
        r = await c.get(f"{API}{path}", params=params, headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        raise DriveError(f"Google would not give us {f['name']} (error {r.status_code}).")
    if len(r.content) > MAX_DOWNLOAD:
        raise DriveError(f"{f['name']} is larger than {MAX_DOWNLOAD // 1048576} MB and was skipped.")
    return name, mime, r.content
