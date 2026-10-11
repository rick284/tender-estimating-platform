import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT.parent / "engine"))

import db as dbmod  # noqa: E402
from app import app  # noqa: E402


@pytest.fixture()
def client():
    dbmod.set_db(AsyncMongoMockClient()["test"])
    with TestClient(app) as c:
        yield c
    dbmod.set_db(None)


def register(client, email="rick@example.com", company="Acme Civil", password="correct horse battery"):
    r = client.post("/api/auth/register", json={"email": email, "password": password, "name": "Rick", "company": company})
    return r


@pytest.fixture()
def auth(client):
    r = register(client)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
