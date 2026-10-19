import json
import urllib.parse as up

import httpx
import pytest

import config
import drive_client as dc
import steps as st
from conftest import register
from factory import make_workbook

RECORD = """# JOB RECORD: 329 Hobsonville Road        Updated: 18-Oct-2026        By: AI Senior Estimator

## Status
- Mode: STEP        Step just completed: 02        Hours this step: planned 3 / actual 2.5
- Stage reached: 1C        Lifecycle: WORKING
- Revision: Rev00            Release status: HOLD            Price excl. GST: $____ (pre-commercial)

## Steps (one chat each)
| Step | Chat title | Status (DRAFT / APPROVED-LOCKED / REOPENED) | Brief | Report | Workbook revision |
|---|---|---|---|---|---|
| 01 | 329 Hobsonville Rd \\| Step 01 Scope of Work and Effort \\| Dave Stewart | APPROVED-LOCKED | STEP_01_BRIEF.md | STEP_01_REPORT.md | Rev00 |
| 02 | 329 Hobsonville Rd \\| Step 02 Production Programme \\| Dave Stewart | DRAFT | STEP_02_BRIEF.md | STEP_02_REPORT.md | |
| 05 | 329 Hobsonville Rd \\| Step 05 Take-off - Drainage \\| Dave Stewart | REOPENED | | | |

## Change notes open: none
"""


def test_job_record_header_and_steps_table_are_read_leniently():
    p = st.parse_job_record(RECORD)
    assert p["fields"]["revision"] == "Rev00" and p["fields"]["release_status"] == "HOLD" and p["fields"]["mode"] == "STEP" and p["fields"]["stage"] == "1C"
    assert "price" not in p["fields"]                                                # a blank template value ($____ ...) is not data
    assert [(s["key"], s["status"]) for s in p["steps"]] == [("01", "APPROVED-LOCKED"), ("02", "DRAFT"), ("05", "REOPENED")]
    assert st.parse_job_record("nothing useful here") == {"fields": {}, "steps": []}


def test_step_folders_files_groups_and_status():
    assert st.parse_step_folder("Step 05 Take-off – Drainage")["name"] == "Take-off – Drainage"
    assert st.parse_step_folder("Step 05a Take-off - Drainage (rebuild)")["key"] == "05a" and st.parse_step_folder("Notes") is None
    assert st.parse_step_file("STEP_05_BRIEF.md") == ("05", "brief") and st.parse_step_file("STEP_05A_REPORT.md") == ("05a", "report") and st.parse_step_file("step_5.md") is None
    assert [st.group_for(n) for n in ("Scope of Work and Effort", "Production Programme", "Document Control", "Take-off - Drainage", "Quotes", "Build-up - Earthworks",
                                      "Programme and Weather", "Triple verification and release", "Client pack", "Site visit")] == [
        "Scope and plan", "Scope and plan", "Documents", "Takeoff", "Quotes and correspondence", "Build-up and workbook", "Programme and weather", "Review and release", "Client pack", "Other"]
    folders = [{"folder_id": "F2", "name": "Step 02 Production Programme", "files": [{"id": "b2", "name": "STEP_02_BRIEF.md"}, {"id": "r2", "name": "STEP_02_REPORT.md"}]},
               {"folder_id": "F3", "name": "Step 03 Document Control", "files": [{"id": "b3", "name": "STEP_03_BRIEF.md"}]},
               {"folder_id": "F4", "name": "Step 04 Scope Coverage", "files": []}]
    out = st.build_steps(folders, st.parse_job_record(RECORD))
    by = {s["key"]: s for s in out}
    assert [s["key"] for s in out] == ["01", "02", "03", "04", "05"]                           # in the Job Record but no folder yet: 01 and 05 still listed
    assert by["02"]["status"] == "DRAFT" and by["02"]["in_record"] and by["02"]["report"]["id"] == "r2"
    assert by["03"]["status"] == "READY" and by["04"]["status"] == "NOT STARTED" and by["01"]["folder_id"] is None and by["05"]["status"] == "REOPENED"
    assert by["01"]["name"] == "Scope of Work and Effort"


FOLDER = "application/vnd.google-apps.folder"
TREE = {
    "J": [{"id": "A", "name": "00 Project Admin", "mimeType": FOLDER}, {"id": "S", "name": "02 Tender Source Documents", "mimeType": FOLDER}],
    "A": [{"id": "JR", "name": "JOB_RECORD.md", "mimeType": "text/markdown", "size": "900"}, {"id": "SD", "name": "Steps", "mimeType": FOLDER}],
    "SD": [{"id": "F2", "name": "Step 02 Production Programme", "mimeType": FOLDER}],
    "F2": [{"id": "B2", "name": "STEP_02_BRIEF.md", "mimeType": "text/markdown"}, {"id": "R2", "name": "STEP_02_REPORT.md", "mimeType": "text/markdown"}, {"id": "X", "name": "notes.txt", "mimeType": "text/plain"}],
}
BLOBS = {"JR": RECORD.encode(), "B2": b"# STEP 02 BRIEF\nDo the plan.", "R2": b"# STEP 02 REPORT\nDone.\n\n| a | b |\n|---|---|\n| 1 | 2 |"}


def handler(request: httpx.Request) -> httpx.Response:
    u = request.url
    if u.host == "oauth2.googleapis.com":
        form = dict(up.parse_qsl(request.content.decode()))
        return httpx.Response(200, json={"access_token": "AT", "refresh_token": "RT"} if form["grant_type"] == "authorization_code" else {"access_token": "AT2"})
    if u.host == "openidconnect.googleapis.com":
        return httpx.Response(200, json={"email": "rick@x.example"})
    assert request.method == "GET"                                                           # reading the build path never writes
    if u.path == "/drive/v3/files":
        return httpx.Response(200, json={"files": TREE.get(u.params["q"].split("'")[1], [])})
    fid = u.path.rsplit("/", 1)[1]
    if u.params.get("alt") == "media":
        return httpx.Response(200, content=BLOBS[fid])
    for kids in TREE.values():
        for k in kids:
            if k["id"] == fid:
                return httpx.Response(200, json=k)
    if fid == "J":
        return httpx.Response(200, json={"id": "J", "name": "329 Hobsonville Road", "mimeType": FOLDER})
    return httpx.Response(404, json={})


def test_api_reads_the_build_path_from_drive_and_never_writes(client, auth, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "cid"); monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "sec")
    monkeypatch.setattr(dc, "TRANSPORT", httpx.MockTransport(handler))
    tid = client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", make_workbook())}).json()["id"]
    assert client.get(f"/api/steps/tenders/{tid}", headers=auth).status_code == 409           # nothing linked yet
    q = dict(up.parse_qsl(up.urlparse(client.get("/api/drive/connect", headers=auth).json()["url"]).query))
    client.get("/api/drive/callback", params={"code": "c", "state": q["state"]})
    assert client.put(f"/api/drive/tenders/{tid}", headers=auth, json={"folder_id": "J"}).status_code == 200
    r = client.get(f"/api/steps/tenders/{tid}", headers=auth)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["job_record"]["found"] and d["job_record"]["fields"]["revision"] == "Rev00"
    assert [(s["key"], s["status"], s["group"]) for s in d["steps"]] == [("01", "APPROVED-LOCKED", "Scope and plan"), ("02", "DRAFT", "Scope and plan"), ("05", "REOPENED", "Takeoff")]
    assert d["counts"] == {"steps": 3, "locked": 1, "draft": 1, "reopened": 1}
    s2 = client.get(f"/api/steps/tenders/{tid}/step/02", headers=auth).json()
    assert s2["brief"]["text"].startswith("# STEP 02 BRIEF") and "| 1 | 2 |" in s2["report"]["text"] and s2["chat_title"].endswith("Dave Stewart")
    assert client.get(f"/api/steps/tenders/{tid}/step/09", headers=auth).status_code == 404
    monkeypatch.setattr(config, "REGISTRATION_OPEN", True)
    other = {"Authorization": f"Bearer {register(client, 'z@example.com', 'Other Ltd').json()['token']}"}
    assert client.get(f"/api/steps/tenders/{tid}", headers=other).status_code == 404       # another company cannot read it
