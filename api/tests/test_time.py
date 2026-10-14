import datetime as dt
import json
from types import SimpleNamespace

import ai_client
import db as dbmod
import routes_time as rt
from conftest import *            # noqa: F401,F403
from test_programme import FakeAI, tender, _ai_on
from services import now


def _day(offset=0):
    return (dt.datetime.now(rt.ZONE) + dt.timedelta(days=offset)).strftime("%Y-%m-%d")


def ping(client, auth, tid, sid="sess-0000001", page="qs", sec=30, edits=0, end=False):
    return client.post("/api/time/ping", headers=auth, json={"session_id": sid, "tender_id": tid, "page": page, "active_seconds": sec, "draft_edits": edits, "end": end})


def test_ping_adds_only_real_active_time_and_rejects_strangers(client, auth):
    tid = tender(client, auth)
    assert ping(client, auth, tid, sec=30).status_code == 200
    assert ping(client, auth, tid, sec=9999).status_code == 200                       # capped: can't add more than has really passed
    assert client.post("/api/time/ping", headers=auth, json={"session_id": "x", "tender_id": tid}).status_code == 422
    assert client.post("/api/time/ping", headers=auth, json={"session_id": "sess-0000002", "tender_id": "nope"}).status_code == 404
    ts = client.get(f"/api/time/timesheet?start={_day()}&end={_day()}", headers=auth).json()
    assert 30 <= ts["totals"]["active_seconds"] <= 40 and ts["round_minutes"] == 6


def test_billable_time_rounds_up_per_tender_per_day_and_actual_is_kept(client, auth):
    tid = tender(client, auth)
    db = dbmod.get_db()
    async def seed():
        u = (await db.users.find_one({}))
        base = now().replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
        for i, sec in enumerate((400, 100)):                                           # 6m40 + 1m40 = 8m20 actual -> 12 minutes at 6-minute units
            await db.time_sessions.insert_one({"_id": f"seed-session-{i}", "org_id": u["org_id"], "user_id": u["_id"], "tender_id": tid, "tender_name": "T", "started_at": base + dt.timedelta(hours=i),
                                               "last_seen": base + dt.timedelta(hours=i, seconds=sec + 60), "active_seconds": sec, "pages": {"qs": sec}, "draft_edits": 0, "ended": True, "note": ""})
    client.portal.call(seed)
    d = client.get(f"/api/time/timesheet?start={_day()}&end={_day(1)}", headers=auth).json()
    g = [x for x in d["groups"] if x["tender_id"] == tid]
    assert len(g) == 1 and g[0]["active_seconds"] == 500 and g[0]["billable_minutes"] == 12 and g[0]["elapsed_seconds"] == 460 + 160
    assert client.put("/api/time/settings", headers=auth, json={"round_minutes": 15}).status_code == 200
    d = client.get(f"/api/time/timesheet?start={_day()}&end={_day(1)}", headers=auth).json()
    assert [x for x in d["groups"] if x["tender_id"] == tid][0]["billable_minutes"] == 15
    assert client.put("/api/time/settings", headers=auth, json={"round_minutes": 7}).status_code == 422


def test_session_summary_reads_back_what_was_done(client, auth):
    tid = tender(client, auth)
    ping(client, auth, tid, sec=60, page="qs"); ping(client, auth, tid, sec=60, page="commercial", edits=3)
    client.post("/api/time/entries", headers=auth, json={"date": _day(), "minutes": 10, "note": "call", "tender_id": tid})      # the timesheet's own actions are not "work"
    d = client.get(f"/api/time/timesheet?start={_day()}&end={_day()}", headers=auth).json()
    lines = next(e for e in d["entries"] if e["kind"] == "session")["summary"]
    assert not any(l.strip() == "Time in:" for l in lines)                                # brief visits don't leave an empty line
    assert not any(l.lower().startswith("time ") and "manual" in l.lower() for l in lines)
    assert any("Edit draft reached 3 changes" in l for l in lines)
    assert any(l.startswith("Created the tender") for l in lines)                         # creating the tender happened within the window
    sess = next(e for e in d["entries"] if e["kind"] == "session")
    assert sess["elapsed_seconds"] >= sess["active_seconds"]


def test_manual_entries_notes_delete_and_csv(client, auth):
    tid = tender(client, auth)
    r = client.post("/api/time/entries", headers=auth, json={"date": _day(), "minutes": 20, "note": "Phone call with client", "tender_id": tid})
    assert r.status_code == 200
    assert client.post("/api/time/entries", headers=auth, json={"date": _day(), "minutes": 0, "note": "x"}).status_code == 422
    assert client.post("/api/time/entries", headers=auth, json={"date": _day(), "minutes": 5, "note": ""}).status_code == 422
    ping(client, auth, tid, sec=45)
    assert client.put("/api/time/sessions/sess-0000001", headers=auth, json={"note": "Checked earthworks"}).status_code == 200
    csv_text = client.get(f"/api/time/timesheet.csv?start={_day()}&end={_day()}", headers=auth).text
    assert "Billable minutes (rounded up to 6)" in csv_text and "Phone call with client" in csv_text and "Checked earthworks" in csv_text
    detail = client.get(f"/api/time/timesheet.csv?start={_day()}&end={_day()}&detail=true", headers=auth).text
    assert "Manual" in detail and "Session" in detail
    assert client.delete(f"/api/time/entries/{r.json()['id']}", headers=auth).status_code == 200
    assert client.delete("/api/time/sessions/sess-0000001", headers=auth).status_code == 200
    assert client.delete("/api/time/sessions/sess-0000001", headers=auth).status_code == 404


def test_ai_runs_are_timed_and_counted(client, auth):
    tid = tender(client, auth)
    from test_programme import _saved_programme, TASKS, _propose
    pid = _saved_programme(client, auth, tid)
    _ai_on(client, auth)
    r, _ = _propose(client, auth, tid, pid, {"links": [], "remove_links": [], "questions": [], "coverage_notes": ""})
    assert r.status_code == 200
    d = client.get(f"/api/time/timesheet?start={_day()}&end={_day()}", headers=auth).json()
    g = [x for x in d["groups"] if x["tender_id"] == tid][0]
    assert g["ai"]["runs"] == 1 and d["totals"]["ai_runs"] == 1


def test_other_companies_cannot_see_or_add_time(client, auth, monkeypatch):
    import config
    monkeypatch.setattr(config, "REGISTRATION_OPEN", True)
    tid = tender(client, auth)
    ping(client, auth, tid, sec=30)
    from conftest import register
    r2 = register(client, email="other@example.com", company="Other Ltd")
    h2 = {"Authorization": "Bearer " + r2.json()["token"]}
    assert ping(client, h2, tid).status_code == 404
    d = client.get(f"/api/time/timesheet?start={_day()}&end={_day()}", headers=h2).json()
    assert d["totals"]["active_seconds"] == 0 and d["entries"] == []


def test_a_read_only_session_is_recorded_as_review(client, auth):
    tid = tender(client, auth)
    db = dbmod.get_db()
    async def seed():
        u = await db.users.find_one({})
        base = now() - dt.timedelta(minutes=30)
        await db.time_sessions.insert_one({"_id": "seed-review-001", "org_id": u["org_id"], "user_id": u["_id"], "tender_id": tid, "tender_name": "T", "started_at": base,
                                           "last_seen": base + dt.timedelta(minutes=12), "active_seconds": 700, "pages": {"quotes": 700}, "draft_edits": 0, "ended": True, "note": ""})
    client.portal.call(seed)
    d = client.get(f"/api/time/timesheet?start={_day()}&end={_day()}", headers=auth).json()
    e = next(x for x in d["entries"] if x["id"] == "seed-review-001")
    assert "Time in: Quotes (12m)" in e["summary"] and any(l.startswith("Review only") for l in e["summary"]) and e["active_seconds"] == 700
