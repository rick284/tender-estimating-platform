import hashlib
import pytest
from pathlib import Path
from conftest import register
from factory import make_workbook

PRIVATE = Path(__file__).resolve().parents[2] / "private"


def up(client, auth, data=None, name="a.xlsx", form=None):
    data = data or make_workbook()
    return client.post("/api/tenders", headers=auth, files={"file": (name, data)}, data=form or {})


# ---------------------------------------------------------------- auth
def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_auth_required(client):
    for path in ("/api/tenders", "/api/auth/me"):
        assert client.get(path).status_code == 401
    assert client.get("/api/tenders", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_first_account_then_invite_only(client):
    assert client.get("/api/auth/config").json()["first_account"] is True
    assert register(client).status_code == 200
    assert client.get("/api/auth/config").json() == {"registration_open": False, "first_account": False}
    assert register(client, email="other@example.com").status_code == 403


def test_bootstrap_email_pins_first_account(client, monkeypatch):
    import config
    monkeypatch.setattr(config, "BOOTSTRAP_EMAIL", "owner@3bears.co.nz")
    assert register(client, email="stranger@evil.com").status_code == 403
    assert register(client, email="Owner@3Bears.co.nz").status_code == 200


def test_open_registration_flag(client, monkeypatch):
    import config
    register(client)
    monkeypatch.setattr(config, "REGISTRATION_OPEN", True)
    assert register(client, email="b@example.com", company="Beta").status_code == 200


def test_password_rules_and_duplicate_email(client):
    assert client.post("/api/auth/register", json={"email": "a@b.co", "password": "short", "name": "x", "company": "y"}).status_code == 422
    assert client.post("/api/auth/register", json={"email": "nope", "password": "long enough password", "name": "x", "company": "y"}).status_code == 422
    assert register(client).status_code == 200
    import config
    config.REGISTRATION_OPEN = True
    try:
        assert register(client, email="RICK@example.com").status_code == 409     # case-insensitive
    finally:
        config.REGISTRATION_OPEN = False


def test_login_and_me(client):
    register(client)
    r = client.post("/api/auth/login", json={"email": "Rick@Example.com", "password": "correct horse battery"})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).json()
    assert me["email"] == "rick@example.com" and me["role"] == "owner" and me["org_name"] == "Acme Civil"
    assert "password" not in str(me)


def test_login_failures_generic_and_lockout(client):
    register(client)
    bad = lambda e: client.post("/api/auth/login", json={"email": e, "password": "wrong password!!"})
    r1, r2 = bad("rick@example.com"), bad("nobody@example.com")
    assert r1.status_code == r2.status_code == 401 and r1.json() == r2.json()      # no user enumeration
    for _ in range(10):
        bad("rick@example.com")
    assert bad("rick@example.com").status_code == 429
    good = client.post("/api/auth/login", json={"email": "rick@example.com", "password": "correct horse battery"})
    assert good.status_code == 429                                                  # locked even with correct password


def test_overlong_password_rejected_not_500(client):
    register(client)
    r = client.post("/api/auth/login", json={"email": "rick@example.com", "password": "x" * 150})
    assert r.status_code == 401


# ---------------------------------------------------------------- tenders
def test_create_list_get_tender(client, auth):
    r = up(client, auth, form={"client": "Acme Developments"})
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["name"] == "Test Depot Civil Works" and t["stage"] == "estimating" and t["latest_rev"] == 1
    assert t["summary"]["label"] == "Rev1" and t["summary"]["reconciled"] is True and round(t["summary"]["all_in"], 2) == 323.53
    lst = client.get("/api/tenders", headers=auth).json()
    assert lst["totals"]["count"] == 1 and lst["totals"]["by_stage"]["estimating"]["count"] == 1
    detail = client.get(f"/api/tenders/{t['id']}", headers=auth).json()
    assert [r["label"] for r in detail["revisions"]] == ["Rev1"]
    rev = client.get(f"/api/tenders/{t['id']}/revisions/1", headers=auth).json()
    assert rev["estimate"]["qs"][0]["code"] == "EW01" and "password" not in str(rev)


def test_upload_validation(client, auth):
    assert client.post("/api/tenders", headers=auth, files={"file": ("a.txt", b"x")}).status_code == 400
    assert client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", b"not a zip")}).status_code == 400
    import openpyxl, io
    buf = io.BytesIO(); openpyxl.Workbook().save(buf)
    r = client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", buf.getvalue())})
    assert r.status_code == 422 and "missing sheets" in r.json()["detail"]


def test_new_revision_and_compare(client, auth):
    t = up(client, auth).json()
    r2 = client.post(f"/api/tenders/{t['id']}/revisions", headers=auth,
                     files={"file": ("b.xlsx", make_workbook(rev="Rev2", qty=200, oh=0.12))})
    assert r2.status_code == 200 and r2.json()["n"] == 2 and r2.json()["label"] == "Rev2"
    d = client.get(f"/api/tenders/{t['id']}", headers=auth).json()
    assert d["latest_rev"] == 2 and d["summary"]["label"] == "Rev2" and [r["n"] for r in d["revisions"]] == [2, 1]
    cmp = client.get(f"/api/tenders/{t['id']}/compare?a=1&b=2", headers=auth).json()
    assert cmp["diff"]["qs"][0]["code"] == "EW01" and cmp["diff"]["qs"][0]["delta"] == 200.0
    assert [s["key"] for s in cmp["diff"]["settings"]] == ["overhead_rate"]
    assert client.get(f"/api/tenders/{t['id']}/compare?a=1&b=9", headers=auth).status_code == 404


def test_duplicate_and_wrong_project_revisions(client, auth):
    t = up(client, auth).json()
    same = client.post(f"/api/tenders/{t['id']}/revisions", headers=auth, files={"file": ("a.xlsx", make_workbook())})
    assert same.status_code == 409 and "already been uploaded" in same.json()["detail"]
    other = make_workbook(project="Completely Different Job", rev="Rev9")
    r = client.post(f"/api/tenders/{t['id']}/revisions", headers=auth, files={"file": ("c.xlsx", other)})
    assert r.status_code == 409 and "not" in r.json()["detail"]
    ok = client.post(f"/api/tenders/{t['id']}/revisions", headers=auth, files={"file": ("c.xlsx", other)},
                     data={"confirm_different_project": "true"})
    assert ok.status_code == 200


def test_patch_and_delete(client, auth):
    t = up(client, auth).json()
    p = client.patch(f"/api/tenders/{t['id']}", headers=auth, json={"stage": "submitted", "client": "Big Builder Ltd"})
    assert p.status_code == 200 and p.json()["stage"] == "submitted" and p.json()["client"] == "Big Builder Ltd"
    assert client.patch(f"/api/tenders/{t['id']}", headers=auth, json={"stage": "bogus"}).status_code == 422
    assert client.delete(f"/api/tenders/{t['id']}", headers=auth).json() == {"deleted": True}
    assert client.get(f"/api/tenders/{t['id']}", headers=auth).status_code == 404
    assert client.get(f"/api/tenders/{t['id']}/revisions/1", headers=auth).status_code == 404


# ---------------------------------------------------------------- tenant isolation (release blocker)
def test_tenant_isolation(client, auth):
    import config
    t = up(client, auth).json()
    config.REGISTRATION_OPEN = True
    try:
        other = register(client, email="spy@rival.co.nz", company="Rival Civil")
    finally:
        config.REGISTRATION_OPEN = False
    h2 = {"Authorization": f"Bearer {other.json()['token']}"}
    tid = t["id"]
    assert client.get("/api/tenders", headers=h2).json()["totals"]["count"] == 0
    for method, path in [("get", f"/api/tenders/{tid}"), ("get", f"/api/tenders/{tid}/revisions/1"),
                         ("get", f"/api/tenders/{tid}/compare?a=1&b=1"), ("delete", f"/api/tenders/{tid}")]:
        assert getattr(client, method)(path, headers=h2).status_code == 404, path
    assert client.patch(f"/api/tenders/{tid}", headers=h2, json={"stage": "won"}).status_code == 404
    assert client.post(f"/api/tenders/{tid}/revisions", headers=h2, files={"file": ("x.xlsx", make_workbook(rev="Rev5"))}).status_code == 404
    # the owner's data is untouched
    assert client.get(f"/api/tenders/{tid}", headers=auth).json()["stage"] == "estimating"
    assert client.get("/api/tenders", headers=h2).json()["totals"]["count"] == 0
    # same workbook uploaded by the rival is a separate tender in their own workspace
    assert up(client, h2).status_code == 200
    assert client.get("/api/tenders", headers=h2).json()["totals"]["count"] == 1
    assert client.get("/api/tenders", headers=auth).json()["totals"]["count"] == 1


@pytest.mark.skipif(not (PRIVATE / "Rev34E.xlsx").exists(), reason="private workbooks not present")
def test_real_hobsonville_revisions(client, auth):
    c = (PRIVATE / "Rev34C.xlsx").read_bytes()
    e = (PRIVATE / "Rev34E.xlsx").read_bytes()
    t = up(client, auth, c, name="Rev34C.xlsx").json()
    assert t["summary"]["label"] == "Rev34C" and round(t["summary"]["all_in"], 2) == 1163543.00
    r = client.post(f"/api/tenders/{t['id']}/revisions", headers=auth, files={"file": ("Rev34E.xlsx", e)})
    assert r.status_code == 200 and r.json()["label"] == "Rev34E"
    d = client.get(f"/api/tenders/{t['id']}/compare?a=1&b=2", headers=auth).json()["diff"]
    assert next(h for h in d["headline"] if h["key"] == "all_in")["delta"] == 63373.81


# ---------------------------------------------------------------- editing
def _tender(client, auth):
    return up(client, auth).json()["id"]


QTY = {"target": "qs", "key": "EW01", "field": "quantity", "value": 200}


def test_preview_recalculates_without_saving(client, auth):
    tid = _tender(client, auth)
    r = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [QTY]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["estimate"]["qs"][0]["quantity"] == 200 and round(j["estimate"]["qs"][0]["amount"], 2) == 400.0
    assert j["estimate"]["edited"] is True and j["estimate"]["reconciled"] is None
    assert round(j["base"]["all_in"], 2) == 323.53 and j["estimate"]["summary"]["all_in"] > j["base"]["all_in"]
    assert [c["field"] for c in j["changes"]] == ["quantity"]
    d = client.get(f"/api/tenders/{tid}", headers=auth).json()
    assert d["latest_rev"] == 1 and len(d["revisions"]) == 1                      # nothing was saved


def test_save_creates_new_revision_and_leaves_base_untouched(client, auth):
    tid = _tender(client, auth)
    before = client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()
    r = client.post(f"/api/tenders/{tid}/revisions/1/save", headers=auth,
                    json={"edits": [QTY], "label": "Rev1-qty", "note": "Quantity updated from Rev2 drawings"})
    assert r.status_code == 200, r.text
    rev = r.json()
    assert rev["n"] == 2 and rev["label"] == "Rev1-qty" and rev["edited"] is True and rev["parent_n"] == 1 and rev["change_count"] == 1
    assert rev["note"] == "Quantity updated from Rev2 drawings"
    t = client.get(f"/api/tenders/{tid}", headers=auth).json()
    assert t["latest_rev"] == 2 and t["summary"]["label"] == "Rev1-qty" and t["summary"]["edited"] is True
    after = client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()
    assert (after["revision"], after["estimate"]) == (before["revision"], before["estimate"])      # base revision immutable
    got = client.get(f"/api/tenders/{tid}/revisions/2", headers=auth).json()
    assert got["revision"]["changes"][0]["before"] == "100" and got["revision"]["changes"][0]["after"] == "200"
    assert got["estimate"]["qs"][0]["quantity"] == 200
    cmp = client.get(f"/api/tenders/{tid}/compare?a=1&b=2", headers=auth).json()["diff"]
    assert cmp["qs"][0]["code"] == "EW01" and cmp["qs"][0]["delta"] == 200.0


def test_edits_chain_from_an_edited_revision(client, auth):
    tid = _tender(client, auth)
    client.post(f"/api/tenders/{tid}/revisions/1/save", headers=auth, json={"edits": [QTY], "note": "first change"})
    r = client.post(f"/api/tenders/{tid}/revisions/2/save", headers=auth, json={
        "edits": [{"target": "commercial", "key": "CA18", "field": "pct", "value": 0.2}], "note": "raise margin to 20%"})
    assert r.status_code == 200 and r.json()["n"] == 3 and r.json()["parent_n"] == 2
    est = client.get(f"/api/tenders/{tid}/revisions/3", headers=auth).json()["estimate"]
    assert est["qs"][0]["quantity"] == 200 and est["consolidated"]["margin"] == 0.2            # carries both edits


def test_save_requires_reason_and_a_real_change(client, auth):
    tid = _tender(client, auth)
    path = f"/api/tenders/{tid}/revisions/1/save"
    assert client.post(path, headers=auth, json={"edits": [QTY], "note": ""}).status_code == 422
    assert client.post(path, headers=auth, json={"edits": [QTY], "note": "ok"}).status_code == 422
    same = {"target": "qs", "key": "EW01", "field": "quantity", "value": 100}
    r = client.post(path, headers=auth, json={"edits": [same], "note": "no real change here"})
    assert r.status_code == 409 and "no changes" in r.json()["detail"].lower()
    assert client.get(f"/api/tenders/{tid}", headers=auth).json()["latest_rev"] == 1


@pytest.mark.parametrize("edit,msg", [
    ({"target": "qs", "key": "EW01", "field": "quantity", "value": -1}, "less than"),
    ({"target": "qs", "key": "NOPE", "field": "quantity", "value": 1}, "Unknown QS item"),
    ({"target": "commercial", "key": "CA18", "field": "pct", "value": 1.5}, "more than"),
    ({"target": "row", "key": "EW01-001", "field": "resource_code", "value": "X"}, "can't be edited"),
])
def test_invalid_edits_give_plain_422(client, auth, edit, msg):
    tid = _tender(client, auth)
    for path in ("preview", "save"):
        r = client.post(f"/api/tenders/{tid}/revisions/1/{path}", headers=auth, json={"edits": [edit], "note": "valid reason"})
        assert r.status_code == 422 and msg in r.json()["detail"], (path, r.text)


def test_too_many_edits_rejected(client, auth):
    tid = _tender(client, auth)
    r = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [QTY] * 501})
    assert r.status_code == 422


def test_legacy_revision_without_inputs_cannot_be_edited(client, auth):
    import asyncio, db as dbmod
    tid = _tender(client, auth)
    asyncio.run(dbmod.get_db().revisions.update_many({"tender_id": tid}, {"$set": {"inputs": None}}))
    r = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [QTY]})
    assert r.status_code == 409 and "Upload the workbook again" in r.json()["detail"]
    assert client.get(f"/api/tenders/{tid}", headers=auth).json()["revisions"][0]["has_inputs"] is False


def test_edit_endpoints_are_tenant_isolated(client, auth):
    import config
    tid = _tender(client, auth)
    config.REGISTRATION_OPEN = True
    try:
        h2 = {"Authorization": f"Bearer {register(client, email='spy@rival.co.nz', company='Rival').json()['token']}"}
    finally:
        config.REGISTRATION_OPEN = False
    for path in ("preview", "save"):
        r = client.post(f"/api/tenders/{tid}/revisions/1/{path}", headers=h2, json={"edits": [QTY], "note": "stealing a look"})
        assert r.status_code == 404
    assert client.get(f"/api/tenders/{tid}", headers=auth).json()["latest_rev"] == 1
    assert client.post(f"/api/tenders/{tid}/revisions/1/preview", json={"edits": [QTY]}).status_code == 401


def test_original_upload_still_reconciles_and_edited_does_not(client, auth):
    tid = _tender(client, auth)
    assert client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]["reconciled"] is True
    client.post(f"/api/tenders/{tid}/revisions/1/save", headers=auth, json={"edits": [QTY], "note": "bigger area"})
    e = client.get(f"/api/tenders/{tid}/revisions/2", headers=auth).json()["estimate"]
    assert e["reconciled"] is None and e["reconciliation"] == []


def test_reuploading_same_file_enables_editing_on_a_legacy_revision(client, auth):
    import asyncio, db as dbmod
    tid = _tender(client, auth)
    before = client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]
    asyncio.run(dbmod.get_db().revisions.update_many({"tender_id": tid}, {"$set": {"inputs": None}}))
    assert client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [QTY]}).status_code == 409
    r = client.post(f"/api/tenders/{tid}/revisions", headers=auth, files={"file": ("a.xlsx", make_workbook())})
    assert r.status_code == 200 and r.json()["upgraded"] is True and r.json()["n"] == 1 and r.json()["has_inputs"] is True
    d = client.get(f"/api/tenders/{tid}", headers=auth).json()
    assert d["latest_rev"] == 1 and len(d["revisions"]) == 1                       # no new revision created
    assert client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"] == before   # estimate untouched
    assert client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [QTY]}).status_code == 200
    again = client.post(f"/api/tenders/{tid}/revisions", headers=auth, files={"file": ("a.xlsx", make_workbook())})
    assert again.status_code == 409                                                # now it IS a plain duplicate


# ---------------------------------------------------------------- resilience
def test_unexpected_error_returns_json_message_with_cors_and_reference(client, auth, monkeypatch):
    import routes_tenders
    async def boom(*a, **k):
        raise RuntimeError("simulated database failure")
    monkeypatch.setattr(routes_tenders, "_editable", boom)
    r = client.post("/api/tenders/x/revisions/1/save", headers={**auth, "Origin": "http://localhost:5173"},
                    json={"edits": [QTY], "note": "valid reason"})
    assert r.status_code == 500
    assert "reference" in r.json()["detail"] and "simulated" not in r.json()["detail"]      # no internals leaked
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"          # browser can read it


def test_database_self_check(client):
    r = client.get("/api/health/db")
    assert r.status_code == 200 and r.json() == {"database": "ok", "read": "ok", "write": "ok"}


# ---------------------------------------------------------------- add / delete items
ADD_QS = {"target": "qs", "op": "add", "key": "EW02", "value": {"section": "Earthworks", "description": "Bulk fill", "unit": "m3",
                                                                  "quantity": 500, "basis": "CALCULATED", "source": "Rev2 survey"}}
ADD_ROW = {"target": "row", "op": "add", "key": "N-row001", "value": {"qs_code": "EW02", "mode": "Time x Count", "resource_code": "PL-EXC", "task": "Place fill"}}
ADD_PROD = {"target": "row", "key": "N-row001", "field": "productivity_rate", "value": 25}


def test_add_items_via_api_and_save(client, auth):
    tid = _tender(client, auth)
    pv = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [ADD_QS, ADD_ROW, ADD_PROD]})
    assert pv.status_code == 200, pv.text
    est = pv.json()["estimate"]
    assert [q["code"] for q in est["qs"]] == ["EW01", "EW02"]
    assert round(est["qs"][1]["amount"], 2) == 2000.00                    # 500 m3 / 25 per hr = 20 h x $100/hr
    assert est["buildup"][1]["uid"] == "N-row001" and est["buildup"][1]["row_id"] == "EW02-001"


def test_save_structural_edits_creates_revision_and_stays_editable(client, auth):
    tid = _tender(client, auth)
    r = client.post(f"/api/tenders/{tid}/revisions/1/save", headers=auth,
                    json={"edits": [ADD_QS, ADD_ROW, ADD_PROD], "note": "Added bulk fill item from survey"})
    assert r.status_code == 200 and r.json()["change_count"] == 2
    got = client.get(f"/api/tenders/{tid}/revisions/2", headers=auth).json()
    assert [x["field"] for x in got["revision"]["changes"]] == ["added", "added"]
    # the new revision keeps the new row's permanent id and can be edited further
    r2 = client.post(f"/api/tenders/{tid}/revisions/2/save", headers=auth, json={
        "edits": [{"target": "row", "key": "N-row001", "field": "productivity_rate", "value": 50}], "note": "faster plant"})
    assert r2.status_code == 200 and r2.json()["n"] == 3
    cmp = client.get(f"/api/tenders/{tid}/compare?a=1&b=2", headers=auth).json()["diff"]
    assert {c["kind"] for c in cmp["qs"]} == {"added"} and {c["kind"] for c in cmp["buildup"]} == {"added"}


def test_deleting_the_row_that_drives_weather_is_refused_with_a_clear_message(client, auth):
    tid = _tender(client, auth)
    r = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [{"target": "row", "op": "delete", "key": "EW01-001"}]})
    assert r.status_code == 422 and "weather calculation" in r.json()["detail"]


def test_invalid_structural_edit_via_api(client, auth):
    tid = _tender(client, auth)
    bad = {**ADD_QS, "key": "EW01"}
    r = client.post(f"/api/tenders/{tid}/revisions/1/save", headers=auth, json={"edits": [bad], "note": "duplicate code"})
    assert r.status_code == 422 and "already used" in r.json()["detail"]
    assert client.get(f"/api/tenders/{tid}", headers=auth).json()["latest_rev"] == 1


def test_revision_saved_before_row_ids_still_editable(client, auth):
    import asyncio, db as dbmod
    tid = _tender(client, auth)

    async def strip():
        d = dbmod.get_db()
        doc = await d.revisions.find_one({"tender_id": tid})
        inp = doc["inputs"]
        for row in inp["rows"]:
            row.pop("uid", None)
        inp["weather_links"].pop("daily_uid", None); inp["weather_links"].pop("weekly_uids", None)
        await d.revisions.update_one({"_id": doc["_id"]}, {"$set": {"inputs": inp}})
    asyncio.run(strip())
    r = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [ADD_QS, ADD_ROW, ADD_PROD]})
    assert r.status_code == 200 and r.json()["estimate"]["buildup"][0]["uid"] == "EW01-001"


# ---------------------------------------------------------------- tender from scratch
INTAKE = {"client": "Acme Developments", "location": "Albany", "tender_level": "Tender", "scope": "Civil works to new depot"}


def test_blank_tender_needs_an_earlier_tender_to_borrow_from(client, auth):
    r = client.post("/api/tenders/blank", headers=auth, json={"name": "First job", "intake": INTAKE})
    assert r.status_code == 409 and "Master Estimate Workbook" in r.json()["detail"]


def test_blank_tender_created_empty_with_borrowed_rates_and_is_editable(client, auth):
    src = _tender(client, auth)
    r = client.post("/api/tenders/blank", headers=auth, json={"name": "New depot", "intake": INTAKE})
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["name"] == "New depot" and t["client"] == "Acme Developments" and t["location"] == "Albany" and t["id"] != src
    est = client.get(f"/api/tenders/{t['id']}/revisions/1", headers=auth).json()["estimate"]
    assert est["qs"] == [] and est["buildup"] == [] and est["summary"]["all_in"] == 0
    assert [x["code"] for x in est["library"]] == ["PL-EXC"]                       # rates borrowed
    assert est["meta"]["scope"] == "Civil works to new depot"
    lst = client.get("/api/tenders", headers=auth).json()
    assert lst["totals"]["count"] == 2
    # can be built up straight away: add a QS item, a priced row, and a subcontract package
    edits = [
        {"target": "qs", "op": "add", "key": "EW01", "value": {"section": "Earthworks", "description": "Strip", "unit": "m2", "quantity": "100", "basis": "MEASURED"}},
        {"target": "row", "op": "add", "key": "N-row0001", "value": {"qs_code": "EW01", "mode": "Time x Count", "resource_code": "PL-EXC", "task": "Strip"}},
        {"target": "row", "key": "N-row0001", "field": "productivity_rate", "value": "50"},
        {"target": "overlay", "op": "add", "key": "Pipes Ltd", "value": {"amount": "1000"}},
    ]
    pv = client.post(f"/api/tenders/{t['id']}/revisions/1/preview", headers=auth, json={"edits": edits})
    assert pv.status_code == 200, pv.text
    assert pv.json()["estimate"]["consolidated"]["overlays_total"] == 1000 and pv.json()["estimate"]["summary"]["all_in"] > 1000
    sv = client.post(f"/api/tenders/{t['id']}/revisions/1/save", headers=auth, json={"edits": edits, "note": "First pass build-up"})
    assert sv.status_code == 200, sv.text


def test_blank_tender_validation_and_isolation(client, auth):
    src = _tender(client, auth)
    assert client.post("/api/tenders/blank", headers=auth, json={"name": "", "intake": {}}).status_code == 422
    assert client.post("/api/tenders/blank", headers=auth, json={"name": "x", "intake": {"tender_level": "Guess"}}).status_code == 422
    assert client.post("/api/tenders/blank", headers=auth, json={"name": "x", "intake": {"scope": "a" * 3000}}).status_code == 422
    # another workspace can't borrow from this one
    other = client.post("/api/auth/register", json={"email": "o@example.com", "password": "correct horse battery", "name": "O", "company": "Other"})
    if other.status_code == 200:
        h = {"Authorization": f"Bearer {other.json()['token']}"}
        assert client.post("/api/tenders/blank", headers=h, json={"name": "x", "template_tender_id": src}).status_code == 404


# ---------------------------------------------------------------- live weather tool
WX_SETUP = {"target": "weather", "op": "add", "key": "setup", "value": {"station": "Auckland", "start": "2026-10-01", "working_days_per_week": 5, "baseline_wd": 55}}
WX_ACT = {"target": "weather_activity", "op": "add", "key": "W-act0001",
          "value": {"task": "Bulk earthworks", "start": "2026-10-01", "finish": "2026-10-30", "critical": True, "labour": "10000", "plant": "5000"}}


def test_live_weather_tool_preview_save_and_reload(client, auth):
    tid = _tender(client, auth)
    pv = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [WX_SETUP, WX_ACT]})
    assert pv.status_code == 200, pv.text
    w = pv.json()["estimate"]["weather"]
    assert w["live"] is True and w["tool"]["activities"][0]["workdays"] == 22 and w["allowance"] > 0 and w["direct_productivity"] > 0
    sv = client.post(f"/api/tenders/{tid}/revisions/1/save", headers=auth, json={"edits": [WX_SETUP, WX_ACT], "note": "Live weather tool on"})
    assert sv.status_code == 200, sv.text
    est = client.get(f"/api/tenders/{tid}/revisions/2", headers=auth).json()["estimate"]
    assert est["weather"]["tool"]["settings"]["station"] == "Auckland"
    # editable again after saving, and the setting can be changed
    pv2 = client.post(f"/api/tenders/{tid}/revisions/2/preview", headers=auth,
                      json={"edits": [{"target": "weather", "key": "setup", "field": "station", "value": "Christchurch"}]})
    assert pv2.status_code == 200 and pv2.json()["estimate"]["weather"]["meta"]["station"] == "Christchurch"


def test_weather_edit_errors_are_plain_422(client, auth):
    tid = _tender(client, auth)
    r = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth,
                    json={"edits": [{**WX_SETUP, "value": {"station": "Atlantis", "start": "2026-10-01"}}]})
    assert r.status_code == 422 and "station" in r.json()["detail"]


def test_weather_catalog_requires_login_and_lists_stations_and_tasks(client, auth):
    assert client.get("/api/weather/catalog").status_code == 401
    c = client.get("/api/weather/catalog", headers=auth).json()
    assert len(c["stations"]) == 30 and len(c["tasks"]) == 39 and "Auckland" in c["stations"] and c["wind_proxy_stations"] == ["Auckland"]
    assert c["tasks"][2]["name"] == "Bulk earthworks" and c["tasks"][2]["rain_loss"] == 0.7


# ---------------------------------------------------------------- client outputs
@pytest.mark.parametrize("kind,magic", [("report.pdf", b"%PDF"), ("schedule.pdf", b"%PDF"), ("pricing.xlsx", b"PK")])
def test_client_outputs_download(client, auth, kind, magic):
    tid = _tender(client, auth)
    r = client.get(f"/api/tenders/{tid}/revisions/1/outputs/{kind}", headers=auth)
    assert r.status_code == 200, r.text
    assert r.content.startswith(magic) and "attachment" in r.headers["content-disposition"] and r.headers["cache-control"] == "no-store"
    assert r.headers["content-disposition"].endswith(f'.{kind.split(".")[1]}"')


def test_client_outputs_need_login_unknown_kind_and_isolation(client, auth):
    tid = _tender(client, auth)
    assert client.get(f"/api/tenders/{tid}/revisions/1/outputs/report.pdf").status_code == 401
    assert client.get(f"/api/tenders/{tid}/revisions/1/outputs/evil.exe", headers=auth).status_code == 404
    assert client.get(f"/api/tenders/{tid}/revisions/9/outputs/report.pdf", headers=auth).status_code == 404


def test_schedule_edits_via_api_and_pricing_reflects_them(client, auth):
    tid = _tender(client, auth)
    est = client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]
    assert est["schedule"]["auto"] and est["schedule"]["reconciles"]
    fmt = {"target": "schedule", "op": "add", "key": "format", "value": {"text": "# WORKS | W\n1  Civil works\n2  Margin  [margin]", "name": "Client format"}}
    pv = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [fmt]})
    assert pv.status_code == 200 and not pv.json()["estimate"]["schedule"]["reconciles"] and pv.json()["estimate"]["schedule"]["unmapped"]
    maps = [{"target": "schedule_map", "key": u["key"], "field": "to", "value": "line:1"} for u in pv.json()["estimate"]["schedule"]["unmapped"]]
    pv2 = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [fmt] + maps})
    assert pv2.json()["estimate"]["schedule"]["reconciles"] and pv2.json()["estimate"]["schedule"]["name"] == "Client format"
    bad = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [{**fmt, "value": {"text": "nonsense"}}]})
    assert bad.status_code == 422
    sv = client.post(f"/api/tenders/{tid}/revisions/1/save", headers=auth, json={"edits": [fmt] + maps, "note": "Client schedule format"})
    assert sv.status_code == 200
    assert client.get(f"/api/tenders/{tid}/revisions/2/outputs/schedule.pdf", headers=auth).content.startswith(b"%PDF")


def test_old_revision_without_schedule_gets_one_rebuilt_and_outputs_work(client, auth):
    import asyncio, db as dbmod
    tid = _tender(client, auth)

    async def strip():                      # as saved before price schedules existed
        await dbmod.get_db().revisions.update_one({"tender_id": tid}, {"$unset": {"estimate.schedule": ""}})
    asyncio.run(strip())
    est = client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]
    assert est["schedule"]["auto"] and est["schedule"]["reconciles"]
    assert client.get(f"/api/tenders/{tid}/revisions/1/outputs/report.pdf", headers=auth).content.startswith(b"%PDF")

    async def strip_all():                  # and with no saved inputs either: a clear message, not a crash
        await dbmod.get_db().revisions.update_one({"tender_id": tid}, {"$set": {"inputs": None}})
    asyncio.run(strip_all())
    assert "schedule" not in client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]
    r = client.get(f"/api/tenders/{tid}/revisions/1/outputs/report.pdf", headers=auth)
    assert r.status_code == 409 and "Upload its workbook again" in r.json()["detail"]


# ---------------------------------------------------------------- tender register
@pytest.mark.skipif(not (PRIVATE / "Rev34E.xlsx").exists(), reason="private workbook not present")
def test_register_is_read_from_the_workbook_and_added_to_an_older_revision(client, auth):
    import asyncio, db as dbmod
    data = (PRIVATE / "Rev34E.xlsx").read_bytes()
    r = up(client, auth, data=data, name="Rev34E.xlsx")
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    est = client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]
    assert est["register_summary"] == {"rfis": 18, "open_rfis": 15, "open_red_rfis": 4, "red_risks": 4} and len(est["register"]) == 54

    async def make_old():                       # a revision saved before registers existed
        d = dbmod.get_db()
        doc = await d.revisions.find_one({"tender_id": tid})
        inp = doc["inputs"]; inp.pop("register", None)
        est_ = doc["estimate"]; [est_.pop(k, None) for k in ("register", "register_summary")]
        await d.revisions.update_one({"_id": doc["_id"]}, {"$set": {"inputs": inp, "estimate": est_}})
    asyncio.run(make_old())
    assert client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]["register"] == []
    up_ = client.post(f"/api/tenders/{tid}/revisions", headers=auth, files={"file": ("Rev34E.xlsx", data)})
    assert up_.status_code == 200 and up_.json().get("upgraded") is True
    assert len(client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]["register"]) == 54
    assert client.post(f"/api/tenders/{tid}/revisions", headers=auth, files={"file": ("Rev34E.xlsx", data)}).status_code == 409   # now truly a duplicate


def test_register_edits_via_api(client, auth):
    tid = _tender(client, auth)
    add = {"target": "register", "op": "add", "key": "R-test0001", "value": {"kind": "rfi", "title": "Confirm access", "rag": "RED"}}
    pv = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [add]})
    assert pv.status_code == 200 and pv.json()["estimate"]["register_summary"]["open_red_rfis"] == 1
    assert client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [{**add, "value": {"kind": "rfi"}}]}).status_code == 422
    assert client.post(f"/api/tenders/{tid}/revisions/1/save", headers=auth, json={"edits": [add], "note": "Added an RFI"}).status_code == 200


# ---------------------------------------------------------------- quote register
def test_quote_register_edits_and_evidence_pdfs(client, auth):
    tid = _tender(client, auth)
    add = {"target": "quote", "op": "add", "key": "S-test0001", "value": {"supplier": "Acme Aggregates", "package": "AP40 delivered", "amount": "$12,345.50", "estimate_ref": "EW01", "notes": "Quote 123 dated 1 Oct"}}
    pv = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [add]})
    assert pv.status_code == 200 and pv.json()["estimate"]["quotes"][0]["amount"] == "12345.50" and pv.json()["estimate"]["quotes"][0]["ref"] == "Q-01"
    for bad in ({**add, "value": {}}, {**add, "value": {"supplier": "x", "amount": "abc"}}, {**add, "key": "bad"}):
        assert client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [bad]}).status_code == 422
    assert client.post(f"/api/tenders/{tid}/revisions/1/save", headers=auth, json={"edits": [add], "note": "Recorded the aggregate quote"}).status_code == 200
    for kind in ("verification-index.pdf", "evidence-notes.pdf"):
        r = client.get(f"/api/tenders/{tid}/revisions/2/outputs/{kind}", headers=auth)
        assert r.status_code == 200 and r.content.startswith(b"%PDF")


# ---------------------------------------------------------------- programme
def test_programme_setup_edits_and_export(client, auth):
    tid = _tender(client, auth)
    assert client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]["programme"]["set_up"] is False
    r = client.get(f"/api/tenders/{tid}/revisions/1/outputs/programme.xlsx", headers=auth)
    assert r.status_code == 409 and "hasn't been set up" in r.json()["detail"]
    edits = [{"target": "programme", "op": "add", "key": "setup", "value": {"start": "2026-10-01"}},
             {"target": "programme_task", "key": "P-EW01", "field": "override_days", "value": "4"}]
    pv = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": edits})
    assert pv.status_code == 200, pv.text
    p = pv.json()["estimate"]["programme"]
    assert p["set_up"] and p["duration"] == 4 and p["critical_path"] == ["EW01"] and p["finish"] == "2026-10-06"
    assert client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": [edits[1]]}).status_code == 422     # before setup
    assert client.post(f"/api/tenders/{tid}/revisions/1/save", headers=auth, json={"edits": edits, "note": "Programme set up"}).status_code == 200
    x = client.get(f"/api/tenders/{tid}/revisions/2/outputs/programme.xlsx", headers=auth)
    assert x.status_code == 200 and x.content.startswith(b"PK")


@pytest.mark.skipif(not (PRIVATE / "Rev34E.xlsx").exists(), reason="private workbook not present")
def test_live_path_old_revision_upgrade_then_agreed_reserve_adjudication(client, auth):
    """Rick's live path: a Rev34E revision stored BEFORE Risk Truth / Management Reserve existed -> re-upload the same file (upgrade, no new revision)
    -> apply the agreed cost-basis adjudication -> price unchanged -> save as a new revision -> reload."""
    import asyncio, db as dbmod
    data = (PRIVATE / "Rev34E.xlsx").read_bytes()
    r = client.post("/api/tenders", headers=auth, files={"file": ("Rev34E.xlsx", data)})
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    price = client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]["summary"]["all_in"]

    async def make_old():
        d = dbmod.get_db()
        doc = await d.revisions.find_one({"tender_id": tid})
        inp, est_ = doc["inputs"], doc["estimate"]
        inp.pop("risk_truth", None); inp.pop("management_reserve", None)
        inp["register"] = [x for x in inp["register"] if x["kind"] != "risk"][:]          # the older register without the Risk Truth risk list
        for k in ("risk_truth", "management_reserve"):
            est_.pop(k, None)
        await d.revisions.update_one({"_id": doc["_id"]}, {"$set": {"inputs": inp, "estimate": est_}})
    asyncio.run(make_old())
    old = client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]
    assert old["risk_truth"]["exposures"] == [] and old["management_reserve"] is None          # old revision still opens, with empty new sections

    up = client.post(f"/api/tenders/{tid}/revisions", headers=auth, files={"file": ("Rev34E.xlsx", data)})
    assert up.status_code == 200 and up.json().get("upgraded") is True and up.json()["n"] == 1
    est = client.get(f"/api/tenders/{tid}/revisions/1", headers=auth).json()["estimate"]
    assert len(est["risk_truth"]["exposures"]) == 15 and est["risk_truth"]["red_risks"] == 4 and est["risk_truth"]["red_exposures"] == 4
    assert [i["ref"] for i in est["management_reserve"]["items"]] == ["MR-01", "MR-02", "MR-03", "MR-04"]
    assert est["register_summary"]["red_risks"] == 4 and abs(est["summary"]["all_in"] - price) < 0.005

    def e(key, field, value):
        return {"target": "reserve_item", "key": key, "field": field, "value": value}
    agreed = [e("M-wb0001", "basis", "Cost"), e("M-wb0001", "impact", "23314.55"), e("M-wb0001", "probability_low", "0.55"), e("M-wb0001", "probability_high", "0.65"),
              e("M-wb0001", "prob_status", "AMBER"), e("M-wb0001", "exposure_ref", "RT01-001"),
              e("M-wb0002", "basis", "Cost"), e("M-wb0002", "impact", "7741"), e("M-wb0002", "probability_low", "0.3"), e("M-wb0002", "probability_high", "0.4"),
              e("M-wb0002", "prob_status", "AMBER"), e("M-wb0002", "exposure_ref", "RT14-001"),
              e("M-wb0003", "exposure_ref", "RT02-001"), e("M-wb0004", "exposure_ref", "RT13-001")]
    pv = client.post(f"/api/tenders/{tid}/revisions/1/preview", headers=auth, json={"edits": agreed})
    assert pv.status_code == 200, pv.text
    mr = pv.json()["estimate"]["management_reserve"]
    assert abs(mr["weighted_low"] - 15145.30) < 0.05 and abs(mr["weighted_high"] - 18250.86) < 0.05 and 18 < mr["gap"] < 19 and mr["issues"] == []
    assert abs(pv.json()["estimate"]["summary"]["all_in"] - price) < 0.005 and abs(pv.json()["base"]["all_in"] - price) < 0.005
    sv = client.post(f"/api/tenders/{tid}/revisions/1/save", headers=auth, json={"edits": agreed, "label": "Rev34E-res", "note": "Management Reserve adjudicated on a cost basis"})
    assert sv.status_code == 200, sv.text
    n = sv.json()["n"]
    got = client.get(f"/api/tenders/{tid}/revisions/{n}", headers=auth).json()
    assert got["estimate"]["management_reserve"]["position"] == "above" and abs(got["estimate"]["summary"]["all_in"] - price) < 0.005
    assert len(got["revision"]["changes"]) > 0 and all(c["target"] in ("reserve_item",) for c in got["revision"]["changes"])
    # editing again from the saved revision still works, and the commercial line cannot be edited behind the reserve's back
    again = client.post(f"/api/tenders/{tid}/revisions/{n}/preview", headers=auth, json={"edits": [{"target": "commercial", "key": "CA16", "field": "pc_sum", "value": "1"}]})
    assert again.status_code == 422 and "Management Reserve page" in again.json()["detail"]
