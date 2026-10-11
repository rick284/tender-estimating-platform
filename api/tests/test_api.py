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
