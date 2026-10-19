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


# The first real Job Record the ChatGPT project wrote (19 Oct 2026 test): a slightly different layout from the template.
REAL = """# JOB RECORD: 329 Hobsonville Road — TEST COPY
Updated: 19-Oct-2026 | By: AI Senior Estimator

## Status
- Trigger: Reconstruct scope confirmation from Dave Stewart’s 04-Sep-2026 initial enquiry and current Drive tender documents
- Mode: STEP — Step 01 Scope and estimating proposal COMPLETE AS DRAFT TEST
- Lifecycle: WORKING | Release: HOLD / NOT SENT | Revision: Scope Rev A / Proposal Rev A
- Construction price excl GST: NOT PREPARED (not the purpose of Step 01)
- Current tender due date: NOT PROVIDED; historical original 14-Sep-2026 (passed)

## Steps
| Step | Status | Brief | Report / outputs |
|---|---|---|---|
| Step 01 | DRAFT, NOT APPROVED | This chat request | 329Hobsonville_Scope_Confirmation_RevA_2026-10-19.docx; 329Hobsonville_Estimating_Proposal_RevA_2026-10-19.docx |
| Step 02 | NOT STARTED | 329Hobsonville_Step02_Production_Programme_Brief_2026-10-19.md | - |

## Open high-priority questions
1. Scope ownership
"""


def test_real_chatgpt_job_record_is_read():
    p = st.parse_job_record(REAL)
    f = p["fields"]
    assert f["lifecycle"] == "WORKING" and f["release_status"] == "HOLD" and f["revision"] == "Scope Rev A / Proposal Rev A" and f["mode"] == "STEP"
    assert f["price"].startswith("NOT PREPARED") and f["tender_closes"].startswith("NOT PROVIDED") and f["updated"] == "19-Oct-2026"
    assert [(s["key"], s["status"]) for s in p["steps"]] == [("01", "DRAFT"), ("02", "NOT STARTED")]
    steps = st.build_steps([], p, [{"id": "b2", "name": "329Hobsonville_Step02_Production_Programme_Brief_2026-10-19.md"}])
    by = {s["key"]: s for s in steps}
    assert by["01"]["name"] == "Scope of work and effort estimate" and by["01"]["group"] == "Scope and plan"        # the standard's fixed name for step 01
    assert by["02"]["name"] == "Production Programme" and by["02"]["group"] == "Scope and plan" and by["02"]["brief"]["id"] == "b2"
    assert st.parse_step_file("329Hobsonville_Step02_Production_Programme_Brief_2026-10-19.md") is None                      # strict by default
    assert st.parse_step_file("329Hobsonville_Step02_Production_Programme_Brief_2026-10-19.md", loose=True) == ("02", "brief")
    assert st.parse_step_file("Hobsonville_Estimating_Proposal_RevA.md", loose=True) is None


# ---- Step 01 files and the go-ahead record ----
def _docx(build):
    import io, docx
    d = docx.Document(); build(d); b = io.BytesIO(); d.save(b); return b.getvalue()


def _scope_doc(d):
    t = d.add_table(rows=1, cols=6)
    for c, h in zip(t.rows[0].cells, ["Ref", "Work item", "Proposed work and boundaries", "Our proposal", "Client response", "Source"]):
        c.text = h
    for r in [("00", "PRELIMINARIES / ACCESS", "Site establishment, fencing.", "Included", "[ ] Confirm\n[ ] Exclude\n[ ] Query", "Dave 04-Sep"), ("12", "FOUNDATIONS / FLOOR SLAB", "Subcontractor pricing.", "Subcontract quote", "[ ] Confirm", "DHC"),
              ("28", "BUILDING AND FIT-OUT", "Outside this package.", "Excluded", "[ ] Confirm", "Spec"), ("26", "LANDSCAPE", "Fencing interface.", "By others / confirm", "[ ] Confirm", "RC"), ("16", "PARKING FIT-OUT", "Marking.", "To confirm", "[ ] Confirm", "RC")]:
        cells = t.add_row().cells
        for c, v in zip(cells, r):
            c.text = v
    q = d.add_table(rows=1, cols=3)
    for c, h in zip(q.rows[0].cells, ["Ref", "Interface", "Written answer requested"]):
        c.text = h
    cells = q.add_row().cells
    for c, v in zip(cells, ["Q1", "Concrete/foundation excavation", "Does the quotation include pad excavation and disposal?"]):
        c.text = v


def _proposal_doc(d):
    d.add_paragraph("ESTIMATING SERVICES PROPOSAL Rev A")
    t = d.add_table(rows=1, cols=4)
    for c, h in zip(t.rows[0].cells, ["Planning basis", "Estimator hours", "Rate (excl. GST)", "Indicative fee (excl. GST)"]):
        c.text = h
    for r in [("Lower effort case", "30", "$125/hr", "$3,750"), ("Reference effort scenario", "38", "$125/hr", "$4,750"), ("Upper effort case", "40", "$125/hr", "$5,000")]:
        cells = t.add_row().cells
        for c, v in zip(cells, r):
            c.text = v


def test_step01_files_are_parsed_and_mapped_to_scope_suggestions():
    import step01
    s = step01.parse_scope_confirmation(_docx(_scope_doc))
    by = {r["ref"]: r for r in s["rows"]}
    assert len(s["rows"]) == 5 and by["00"]["title"] == "PRELIMINARIES / ACCESS" and by["00"]["proposal"] == "Included" and by["00"]["source"] == "Dave 04-Sep"
    assert (by["00"]["owner"], by["00"]["treatment"]) == ("OWN WORKS", "UNRESOLVED") and (by["12"]["owner"], by["12"]["treatment"]) == ("SUBCONTRACT", "UNRESOLVED")
    assert (by["28"]["owner"], by["28"]["treatment"]) == ("OTHERS", "EXCLUDED") and (by["26"]["owner"], by["26"]["treatment"]) == ("OTHERS", "BY OTHERS") and by["16"]["owner"] == "TBC"
    assert all(r["treatment"] != "PRICED" for r in s["rows"])                                  # nothing is priced at Step 01
    assert s["questions"] == [{"ref": "Q1", "title": "Concrete/foundation excavation", "question": "Does the quotation include pad excavation and disposal?"}]
    p = step01.parse_proposal(_docx(_proposal_doc))
    assert (p["low_hours"], p["high_hours"], p["low_fee"], p["high_fee"], p["rate"], p["revision"]) == (30, 40, 3750, 5000, 125, "A") and len(p["cases"]) == 3
    files = [{"name": "329H_Scope_Confirmation_RevA_2026-10-19.docx", "modified": "1"}, {"name": "329H_Scope_Confirmation_RevB_2026-10-20.docx", "modified": "2"},
             {"name": "329H_Scope_Confirmation_RevA_2026-10-19.pdf", "modified": "3"}, {"name": "329H_Internal_Effort_Decision_Card_RevA.md", "modified": "1"}, {"name": "Estimating_Proposal_RevA.docx", "modified": "1"}]
    got = step01.pick_files(files)
    assert got["scope"]["name"].endswith("RevB_2026-10-20.docx") and got["proposal"] and got["card"]


def test_go_ahead_record(client, auth):
    tid = client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", make_workbook())}).json()["id"]
    assert client.get(f"/api/steps/tenders/{tid}/go-ahead", headers=auth).json() == {"go_ahead": None}
    assert client.put(f"/api/steps/tenders/{tid}/go-ahead", headers=auth, json={"mode": "maybe"}).status_code == 422
    assert client.put(f"/api/steps/tenders/{tid}/go-ahead", headers=auth, json={"mode": "proceed_anyway", "note": "ok"}).status_code == 422       # a reason is needed
    r = client.put(f"/api/steps/tenders/{tid}/go-ahead", headers=auth, json={"mode": "client_go", "note": "Dave replied 20-Oct"}).json()["go_ahead"]
    assert r["mode"] == "client_go" and r["note"] == "Dave replied 20-Oct" and r["at"]
    assert client.get(f"/api/steps/tenders/{tid}/go-ahead", headers=auth).json()["go_ahead"]["mode"] == "client_go"
    assert client.delete(f"/api/steps/tenders/{tid}/go-ahead", headers=auth).json() == {"go_ahead": None}


def test_api_step01_reads_the_word_files_from_the_job_folder(client, auth, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "cid"); monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "sec")
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    tree = {"J": [{"id": "A", "name": "00 Project Admin", "mimeType": FOLDER}],
            "A": [{"id": "SC", "name": "329H_Scope_Confirmation_RevA_2026-10-19.docx", "mimeType": DOCX, "size": "9000"}, {"id": "EP", "name": "329H_Estimating_Proposal_RevA_2026-10-19.docx", "mimeType": DOCX},
                  {"id": "DC", "name": "329H_Internal_Effort_Decision_Card_RevA_2026-10-19.md", "mimeType": "text/markdown"}]}
    blobs = {"SC": _docx(_scope_doc), "EP": _docx(_proposal_doc), "DC": b"# Decision card\n- Fee 30-40 h"}

    def h(request):
        u = request.url
        if u.host == "oauth2.googleapis.com":
            form = dict(up.parse_qsl(request.content.decode()))
            return httpx.Response(200, json={"access_token": "AT", "refresh_token": "RT"} if form["grant_type"] == "authorization_code" else {"access_token": "AT2"})
        if u.host == "openidconnect.googleapis.com":
            return httpx.Response(200, json={"email": "r@x.example"})
        if u.path == "/drive/v3/files":
            return httpx.Response(200, json={"files": tree.get(u.params["q"].split("'")[1], [])})
        fid = u.path.rsplit("/", 1)[1]
        if u.params.get("alt") == "media":
            return httpx.Response(200, content=blobs[fid])
        if fid == "J":
            return httpx.Response(200, json={"id": "J", "name": "329 Hobsonville Road", "mimeType": FOLDER})
        return httpx.Response(404, json={})
    monkeypatch.setattr(dc, "TRANSPORT", httpx.MockTransport(h))
    tid = client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", make_workbook())}).json()["id"]
    q = dict(up.parse_qsl(up.urlparse(client.get("/api/drive/connect", headers=auth).json()["url"]).query))
    client.get("/api/drive/callback", params={"code": "c", "state": q["state"]})
    client.put(f"/api/drive/tenders/{tid}", headers=auth, json={"folder_id": "J"})
    r = client.get(f"/api/steps/tenders/{tid}/step01", headers=auth)
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["scope"]["rows"]) == 5 and d["scope"]["questions"][0]["ref"] == "Q1" and d["proposal"]["low_fee"] == 3750 and d["card"].startswith("# Decision card")
    assert set(d["files"]) == {"scope", "proposal", "card"} and d["go_ahead"] is None
