import json
import urllib.parse as up

import httpx
import pytest

import config
import drive_client as dc
from drive_index import analyse, check_structure, split_revision
from conftest import register

FOLDER = "application/vnd.google-apps.folder"
TREE = {  # folder id -> children
    "root": [{"id": "T1", "name": "329 Hobsonville Road", "mimeType": FOLDER}],
    "T1": [{"id": "F1", "name": "01 Client Issue Pack", "mimeType": FOLDER}, {"id": "F3", "name": "03 Supplier and Subcontractor Quotes", "mimeType": FOLDER},
           {"id": "F7", "name": "07 Superseded and Archive", "mimeType": FOLDER}, {"id": "L1", "name": "Estimate_Rev34C.xlsx", "mimeType": "x/xlsx"},
           {"id": "L2", "name": "Estimate_Rev34E.xlsx", "mimeType": "x/xlsx"}],
    "F1": [{"id": "D1", "name": "Drawings RevB.pdf", "mimeType": "application/pdf", "size": "1200"}, {"id": "D2", "name": "Drawings RevC.pdf", "mimeType": "application/pdf"},
           {"id": "D3", "name": "Spec.pdf", "mimeType": "application/pdf"}],
    "F3": [], "F7": [{"id": "A1", "name": "Estimate_Rev30.xlsx", "mimeType": "x/xlsx"}],
}


def handler(request: httpx.Request) -> httpx.Response:
    u = request.url
    if u.host == "oauth2.googleapis.com":
        form = dict(up.parse_qsl(request.content.decode()))
        if form["grant_type"] == "authorization_code":
            return httpx.Response(200, json={"access_token": "AT", "refresh_token": "RT-secret"})
        assert form["refresh_token"] == "RT-secret"
        return httpx.Response(200, json={"access_token": "AT2"})
    if u.host == "openidconnect.googleapis.com":
        return httpx.Response(200, json={"email": "rick@gmail.example"})
    assert request.headers["authorization"].startswith("Bearer AT")
    assert request.method == "GET"                      # read-only: the client never writes
    if u.path == "/drive/v3/files":
        q = u.params["q"]; pid = q.split("'")[1]
        kids = TREE.get(pid, [])
        if "mimeType='" + FOLDER in q:
            kids = [k for k in kids if k["mimeType"] == FOLDER]
        return httpx.Response(200, json={"files": kids})
    fid = u.path.rsplit("/", 1)[1]
    for kids in TREE.values():
        for k in kids:
            if k["id"] == fid:
                return httpx.Response(200, json=k)
    return httpx.Response(404, json={})


@pytest.fixture()
def drive(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "cid"); monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "sec")
    monkeypatch.setattr(dc, "TRANSPORT", httpx.MockTransport(handler))


def test_revision_parsing():
    assert split_revision("Hobsonville_Rev34E.xlsx") == ("hobsonville", "34E")
    assert split_revision("Drawings RevB.pdf")[1] == "B"
    assert split_revision("Spec.pdf")[1] is None
    assert split_revision("Issue for Tender.pdf")[1] is None
    assert split_revision("Plan v2.pdf")[1] == "2"


def test_latest_and_superseded():
    fs = [{"name": "A Rev34C.xlsx", "folder": "", "path": ""}, {"name": "A Rev34E.xlsx", "folder": "", "path": ""},
          {"name": "A Rev34D.xlsx", "folder": "x", "path": "x"}, {"name": "Notes.docx", "folder": "", "path": ""}]
    r = {f["name"]: f for f in analyse(fs)["files"]}
    assert r["A Rev34E.xlsx"]["latest"] and r["A Rev34C.xlsx"]["superseded_by"] == "A Rev34E.xlsx"
    assert r["A Rev34D.xlsx"]["latest"]                  # different folder: not compared
    assert r["Notes.docx"]["latest"] is None


def test_structure_check():
    s = check_structure(["01 Client Issue Pack", "03 Quotes"])
    assert [x["found"] for x in s] == [True, False, True, False, False, False, False]
    assert s[0]["exact"] and not s[2]["exact"]


def test_not_configured_and_isolation(client, auth):
    st = client.get("/api/drive/status", headers=auth).json()
    assert st == {**st, "configured": False, "connected": False, "read_only": True}
    assert client.get("/api/drive/connect", headers=auth).status_code == 503
    assert client.get("/api/drive/status").status_code == 401


def test_connect_flow_files_and_tenant_isolation(client, auth, drive, monkeypatch):
    monkeypatch.setattr(config, "REGISTRATION_OPEN", True)
    url = client.get("/api/drive/connect", headers=auth).json()["url"]
    q = dict(up.parse_qsl(up.urlparse(url).query))
    assert "drive.readonly" in q["scope"] and "auth/drive " not in q["scope"] + " " and q["access_type"] == "offline"
    r = client.get("/api/drive/callback", params={"code": "c", "state": q["state"]}, follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"].endswith("?drive=connected")
    assert client.get("/api/drive/callback", params={"code": "c", "state": "junk"}, follow_redirects=False).headers["location"].endswith("badstate")
    st = client.get("/api/drive/status", headers=auth).json()
    assert st["connected"] and st["account"] == "rick@gmail.example"
    assert [f["name"] for f in client.get("/api/drive/folders", headers=auth).json()["folders"]] == ["329 Hobsonville Road"]

    from factory import make_workbook
    tid = client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", make_workbook())}).json()["id"]
    assert client.get(f"/api/drive/tenders/{tid}/files", headers=auth).status_code == 409           # nothing linked yet
    assert client.put(f"/api/drive/tenders/{tid}", headers=auth, json={"folder_id": "L1"}).status_code == 422   # a file, not a folder
    assert client.put(f"/api/drive/tenders/{tid}", headers=auth, json={"folder_id": "T1"}).json()["folder"]["name"] == "329 Hobsonville Road"
    d = client.get(f"/api/drive/tenders/{tid}/files", headers=auth).json()
    by = {f["name"]: f for f in d["files"]}
    assert by["Estimate_Rev34E.xlsx"]["latest"] and by["Estimate_Rev34C.xlsx"]["superseded_by"] == "Estimate_Rev34E.xlsx"
    assert by["Drawings RevC.pdf"]["latest"] and by["Drawings RevB.pdf"]["superseded_by"] == "Drawings RevC.pdf"
    assert by["Estimate_Rev30.xlsx"]["in_archive"] and by["Drawings RevB.pdf"]["path"] == "01 Client Issue Pack"
    assert d["counts"]["loose_in_root"] == 2 and d["counts"]["superseded"] == 2
    assert [s["found"] for s in d["structure"]] == [True, False, True, False, False, False, True]

    # a different company sees nothing and cannot use the first company's connection
    other = {"Authorization": f"Bearer {register(client, 'b@example.com', 'Other Ltd').json()['token']}"}
    assert client.get("/api/drive/status", headers=other).json()["connected"] is False
    assert client.get("/api/drive/folders", headers=other).status_code == 409
    assert client.get(f"/api/drive/tenders/{tid}/files", headers=other).status_code == 404

    assert client.delete("/api/drive/connection", headers=auth).status_code == 200
    assert client.get("/api/drive/status", headers=auth).json()["connected"] is False
    assert client.get(f"/api/drive/tenders/{tid}", headers=auth).json()["folder"] is None


def test_token_is_encrypted():
    s = dc.encrypt("RT-secret")
    assert "RT-secret" not in s and dc.decrypt(s) == "RT-secret"
