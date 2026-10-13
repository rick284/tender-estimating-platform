"""Programme documents: build from an estimate, edit/save, export MS Project XML and read it back (needs Java + mpxj; skipped when absent)."""
import shutil

import pytest
from factory import make_workbook

import programme_build as pb

JAVA = shutil.which("java") is not None
try:
    import jpype  # noqa: F401
    import mpxj  # noqa: F401
    MPXJ = True
except ImportError:
    MPXJ = False
needs_java = pytest.mark.skipif(not (JAVA and MPXJ), reason="Java / mpxj not installed")


def tender(client, auth):
    return client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", make_workbook())}).json()["id"]


def test_tasks_from_estimate_uses_sections_and_hours():
    est = {"programme": {"set_up": False}, "qs": [{"code": "EW01", "section": "Earthworks", "description": "Strip", "amount": 100},
                                                   {"code": "EW02", "section": "Earthworks", "description": "Fill", "amount": 200},
                                                   {"code": "ZZ", "section": "Other", "description": "Nothing", "amount": 0}],
           "buildup": [{"qs_code": "EW01", "resource_type": "Labour", "hours": 20, "resource": "Civil labourer", "count": 2}, {"qs_code": "EW01", "resource_type": "Plant", "hours": 33, "resource": "14 t excavator"},
                       {"qs_code": "EW01", "resource_type": "Material", "hours": 999}]}
    t = pb.tasks_from_estimate(est)
    assert [x["name"] for x in t] == ["Earthworks", "EW01 Strip", "EW02 Fill"]            # zero-amount item left out, materials never drive duration
    assert t[1]["duration"]["value"] == 5 and t[2]["duration"]["value"] == 1              # ROUNDUP(33/8)=5; no hours -> 1 day placeholder
    assert t[2]["predecessors"] == [{"uid": t[1]["uid"], "type": "FS", "lag_days": 0}] and t[1]["predecessors"] == []
    assert [(a["name"], a["type"], a["units"]) for a in t[1]["resource_assignments"]] == [("Civil labourer", "labour", 2.0), ("14 t excavator", "plant", 1.0)]
    assert t[1]["resources"] == ["Civil labourer", "14 t excavator"]                       # materials never become resources
    assert t[0]["resource_assignments"] == []                                               # summary rows carry no resources


def test_tasks_from_platform_programme_keep_links_and_group_sections():
    est = {"programme": {"set_up": True, "tasks": [
        {"code": "A", "name": "One", "section": "S1", "duration": 3, "predecessors": [], "basis": "x"},
        {"code": "B", "name": "Two", "section": "S2", "duration": 0, "predecessors": ["A"], "basis": ""},
        {"code": "C", "name": "Three", "section": "S1", "duration": 2, "predecessors": ["A", "nope"], "basis": ""}]}}
    t = pb.tasks_from_estimate(est)
    assert [x["name"] for x in t] == ["S1", "A One", "C Three", "S2", "B Two"]
    by = {x["name"]: x for x in t}
    assert by["B Two"]["is_milestone"] and by["B Two"]["predecessors"] == [{"uid": by["A One"]["uid"], "type": "FS", "lag_days": 0}]
    assert by["C Three"]["predecessors"] == [{"uid": by["A One"]["uid"], "type": "FS", "lag_days": 0}]     # unknown predecessor dropped


def test_clean_tasks_rules():
    with pytest.raises(pb.BadProgramme):
        pb.clean_tasks([{"uid": 1}, {"uid": 1}])
    with pytest.raises(pb.BadProgramme):
        pb.clean_tasks([{"name": "no uid"}])
    assert pb.clean_tasks([{"uid": 1, "name": "a", "evil": "x"}]) == [{"uid": 1, "name": "a"}]


def test_blank_save_list_delete_and_isolation(client, auth):
    tid = tender(client, auth)
    r = client.post(f"/api/tenders/{tid}/programmes/blank", headers=auth, json={"name": "Mine", "start_date": "2026-11-02"})
    assert r.status_code == 200 and r.json()["needs_schedule"] and r.json()["start"] == "2026-11-02T08:00"
    pid = r.json()["id"]
    tasks = [{"uid": 1, "name": "Dig", "outline_level": 1, "duration": {"value": 3, "unit": "D"}}]
    s = client.put(f"/api/tenders/{tid}/programmes/{pid}", headers=auth, json={"name": "Renamed", "tasks": tasks, "working_days": [True] * 5 + [False] * 2})
    assert s.status_code == 200 and s.json()["name"] == "Renamed" and s.json()["task_count"] == 1 and not s.json()["needs_schedule"]
    assert client.put(f"/api/tenders/{tid}/programmes/{pid}", headers=auth, json={"tasks": [{"uid": 1}, {"uid": 1}]}).status_code == 400
    lst = client.get(f"/api/tenders/{tid}/programmes", headers=auth).json()["programmes"]
    assert len(lst) == 1 and "tasks" not in lst[0]
    # another company cannot see it
    other = client.post("/api/auth/register", json={"email": "b@example.com", "password": "correct horse battery", "name": "B", "company": "Other Co"})
    h2 = {"Authorization": f"Bearer {other.json()['token']}"} if other.status_code == 200 else None
    if h2:
        assert client.get(f"/api/tenders/{tid}/programmes/{pid}", headers=h2).status_code == 404
    assert client.delete(f"/api/tenders/{tid}/programmes/{pid}", headers=auth).status_code == 200
    assert client.get(f"/api/tenders/{tid}/programmes/{pid}", headers=auth).status_code == 404


def test_from_estimate_endpoint(client, auth):
    tid = tender(client, auth)
    r = client.post(f"/api/tenders/{tid}/programmes/from-estimate", headers=auth, json={"revision": 1, "start_date": "2026-11-02"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["source"] == "estimate" and d["task_count"] >= 2 and d["tasks"][0]["outline_level"] == 1
    assert client.post(f"/api/tenders/{tid}/programmes/from-estimate", headers=auth, json={"revision": 9}).status_code == 404


def test_upload_rejects_wrong_type(client, auth):
    tid = tender(client, auth)
    r = client.post(f"/api/tenders/{tid}/programmes/upload", headers=auth, files={"file": ("x.pdf", b"%PDF")})
    assert r.status_code == 400 and "isn't supported" in r.json()["detail"]


@needs_java
def test_export_xml_then_upload_round_trip(client, auth):
    tid = tender(client, auth)
    d = client.post(f"/api/tenders/{tid}/programmes/from-estimate", headers=auth, json={"revision": 1, "start_date": "2026-11-02"}).json()
    # give the tasks real dates like the browser would before saving
    tasks = d["tasks"]
    for i, t in enumerate(tasks):
        t["start"], t["finish"] = f"2026-11-{2 + i:02d}T08:00", f"2026-11-{2 + i:02d}T17:00"
    tasks.append({"uid": 99, "name": "Handover", "outline_level": 1, "duration": {"value": 1, "unit": "D"}, "start": "2026-11-20T08:00", "finish": "2026-11-20T17:00",
                  "predecessors": [{"uid": tasks[-1]["uid"], "type": "FS", "lag_days": 2}]})
    client.put(f"/api/tenders/{tid}/programmes/{d['id']}", headers=auth, json={"tasks": tasks})
    x = client.get(f"/api/tenders/{tid}/programmes/{d['id']}/export/xml", headers=auth)
    assert x.status_code == 200 and x.headers["content-type"].startswith("application/xml") and b"<Project" in x.content
    up = client.post(f"/api/tenders/{tid}/programmes/upload", headers=auth, files={"file": ("round.xml", x.content)})
    assert up.status_code == 200, up.text
    back = up.json()
    assert back["task_count"] == len(tasks) and back["source"] == "upload" and not back["needs_schedule"]
    assert [t["name"] for t in back["tasks"]] == [t["name"] for t in tasks]
    last = back["tasks"][-1]
    assert last["name"] == "Handover" and last["predecessors"][0]["lag_days"] == 2 and last["predecessors"][0]["type"] == "FS"
    assert last["predecessors"][0]["uid"] == back["tasks"][-2]["uid"]


# ---------------------------------------------------------------- AI proposals for programme logic
import json
from types import SimpleNamespace

import ai_client
import programme_ai as pa


def _t(uid, name, level=2, days=3, preds=None, res=None):
    return {"uid": uid, "name": name, "outline_level": level, "duration": {"value": days, "unit": "D"}, "predecessors": preds or [], "resource_assignments": [{"name": r} for r in res or []]}


TASKS = [_t(1, "Earthworks", 1), _t(2, "Strip topsoil"), _t(3, "Bulk fill", preds=[{"uid": 2, "type": "FS", "lag_days": 0}]), _t(4, "Proof roll", preds=[{"uid": 3, "type": "FS", "lag_days": 0}]),
         _t(5, "Pavements", 1), _t(6, "Basecourse", preds=[{"uid": 4, "type": "FS", "lag_days": 0}]), _t(7, "Drainage trenches", preds=[{"uid": 6, "type": "FS", "lag_days": 0}])]


def L(a, b, typ="FS", lag=0, reason="Normal sequence", basis="construction_logic", ref="", conf="high"):
    return {"pred_uid": a, "succ_uid": b, "type": typ, "lag_days": lag, "reason": reason, "basis": basis, "register_ref": ref, "confidence": conf}


def test_verify_checks_every_proposal_deterministically():
    data = {"links": [L(2, 6),                                   # redundant with the chain but no loop: fine
                      L(2, 7),                                   # ok
                      L(6, 7),                                   # already exists -> exists... after removal below it would not; see remove
                      L(1, 3),                                   # a section heading
                      L(3, 3), L(99, 3), L(2, 4, typ="XX"), L(2, 4, lag=90), L(2, 4, reason=""), L(2, 4, basis="tender_document"),
                      L(4, 2)],                                  # 4 already depends on 3 which depends on 2: 2 -> ... -> 4 -> 2 would loop
            "remove_links": [{"pred_uid": 6, "succ_uid": 7, "reason": "Trenching is not after basecourse"}, {"pred_uid": 2, "succ_uid": 6, "reason": "not there"}],
            "questions": [{"question": "Is a retaining wall needed first?", "why": "affects order"}], "coverage_notes": ""}
    r = pa.verify(data, TASKS)
    st = [(p["kind"], p["pred_uid"], p["succ_uid"], p["status"]) for p in r["proposals"]]
    assert ("remove", 6, 7, "ok") in st and ("remove", 2, 6, "invalid") in st                    # a link that isn't there can't be removed
    assert [p["status"] for p in r["proposals"] if p["kind"] == "link" and (p["pred_uid"], p["succ_uid"]) == (2, 6)] == ["ok"]
    assert [p["status"] for p in r["proposals"] if p["kind"] == "link" and (p["pred_uid"], p["succ_uid"]) == (2, 7)] == ["ok"]
    assert [p["status"] for p in r["proposals"] if p["kind"] == "link" and (p["pred_uid"], p["succ_uid"]) == (6, 7)] == ["ok"]      # removed first, so adding it back is not a duplicate
    for bad in ((1, 3), (3, 3), (99, 3)):
        assert [p["status"] for p in r["proposals"] if p["kind"] == "link" and (p["pred_uid"], p["succ_uid"]) == bad] == ["invalid"]
    assert sum(1 for p in r["proposals"] if p["kind"] == "link" and (p["pred_uid"], p["succ_uid"]) == (2, 4) and p["status"] == "invalid") == 4     # bad type, lag, no reason, document with no reference
    loop = [p for p in r["proposals"] if p["kind"] == "link" and (p["pred_uid"], p["succ_uid"]) == (4, 2)][0]
    assert loop["status"] == "invalid" and "loop" in loop["problems"][0]
    assert r["questions"][0]["question"].startswith("Is a retaining")


def test_verify_loops_across_proposals_and_existing_links():
    r = pa.verify({"links": [L(2, 6), L(6, 2)], "remove_links": [], "questions": [], "coverage_notes": ""}, TASKS)
    assert [p["status"] for p in r["proposals"]] == ["ok", "invalid"]                           # the second would close a loop with the first
    r = pa.verify({"links": [L(3, 4)], "remove_links": [], "questions": [], "coverage_notes": ""}, TASKS)
    assert r["proposals"][0]["status"] == "exists"


def test_apply_to_predecessors_adds_removes_and_never_duplicates():
    cur = [{"uid": 3, "type": "FS", "lag_days": 0}, {"uid": 5, "type": "SS", "lag_days": 2}]
    out = pa.apply_to_predecessors(cur, [{"pred_uid": 3, "type": "FS", "lag_days": 0}, {"pred_uid": 9, "type": "SS", "lag_days": -1}], [{"pred_uid": 5}])
    assert out == [{"uid": 3, "type": "FS", "lag_days": 0}, {"uid": 9, "type": "SS", "lag_days": -1}]


def test_prompt_lists_tasks_sections_links_and_context_but_no_money():
    msg = pa.build_user_message("Depot", TASKS, [{"ref": "RFI-01", "kind": "rfi", "title": "Retaining wall height", "detail": "Conflict"}])
    assert "1 | 1 | SECTION: Earthworks" in msg and "3 | 2 | task: Bulk fill | 3 d | - | 2" in msg and "RFI-01 rfi: Retaining wall height - Conflict" in msg and "$" not in msg


class FakeAI:
    def __init__(self, payload):
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self._payload = payload

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(self._payload))])


def _saved_programme(client, auth, tid):
    d = client.post(f"/api/tenders/{tid}/programmes/blank", headers=auth, json={"name": "P", "start_date": "2026-11-02"}).json()
    assert client.put(f"/api/tenders/{tid}/programmes/{d['id']}", headers=auth, json={"tasks": TASKS}).status_code == 200
    return d["id"]


def _ai_on(client, auth):
    assert client.put("/api/ai/settings", headers=auth, json={"api_key": "sk-ant-test1234abcdefgh", "enabled": True, "acknowledged": True}).status_code == 200


def _propose(client, auth, tid, pid, payload):
    fake = FakeAI(payload)
    ai_client.CLIENT = fake
    try:
        return client.post(f"/api/tenders/{tid}/programmes/{pid}/ai/propose", headers=auth), fake
    finally:
        ai_client.CLIENT = None


def test_ai_proposals_end_to_end(client, auth):
    tid = tender(client, auth)
    pid = _saved_programme(client, auth, tid)
    r, _ = _propose(client, auth, tid, pid, {"links": [], "remove_links": [], "questions": [], "coverage_notes": ""})
    assert r.status_code == 503                                                                  # no key yet: plain message, nothing sent
    _ai_on(client, auth)
    payload = {"links": [L(2, 7, reason="Drainage goes in before the pavement base"), L(4, 2)], "remove_links": [{"pred_uid": 6, "succ_uid": 7, "reason": "Not a real dependency"}],
               "questions": [{"question": "Is cure time needed?", "why": "affects PV"}], "coverage_notes": "Looked at 7 rows."}
    r, fake = _propose(client, auth, tid, pid, payload)
    assert r.status_code == 200, r.text
    sent = json.dumps(fake.calls[0])
    assert "Strip topsoil" in sent and "programme-v1" not in sent
    body = r.json()
    by = {(p["kind"], p["pred_uid"], p["succ_uid"]): p for p in body["proposals"]}
    assert by[("link", 2, 7)]["status"] == "ok" and by[("link", 2, 7)]["pred_name"] == "Strip topsoil" and by[("link", 4, 2)]["status"] == "invalid" and by[("remove", 6, 7)]["status"] == "ok"
    assert body["questions"][0]["question"] == "Is cure time needed?"
    ok_id, bad_id, rm_id = by[("link", 2, 7)]["id"], by[("link", 4, 2)]["id"], by[("remove", 6, 7)]["id"]
    assert client.post(f"/api/tenders/{tid}/programmes/{pid}/ai/decision", headers=auth, json={"accept": [bad_id]}).status_code == 409           # failed the checks
    assert client.post(f"/api/tenders/{tid}/programmes/{pid}/ai/decision", headers=auth, json={"reject": [{"id": bad_id, "reason": "no"}]}).status_code == 422   # needs a real reason
    d = client.post(f"/api/tenders/{tid}/programmes/{pid}/ai/decision", headers=auth, json={"accept": [ok_id, rm_id], "reject": [{"id": bad_id, "reason": "Loops the programme"}]})
    assert d.status_code == 200 and {(a["kind"], a["pred_uid"], a["succ_uid"]) for a in d.json()["accepted"]} == {("link", 2, 7), ("remove", 6, 7)}
    listed = {p["id"]: p["decision"]["decision"] for p in client.get(f"/api/tenders/{tid}/programmes/{pid}/ai/proposals", headers=auth).json()["proposals"] if p["decision"]}
    assert listed == {ok_id: "accepted", rm_id: "accepted", bad_id: "rejected"}
    # a new run replaces what was still undecided but keeps the decided history
    r, _ = _propose(client, auth, tid, pid, {"links": [L(2, 7)], "remove_links": [], "questions": [], "coverage_notes": ""})
    assert r.status_code == 200
    ids = [p["id"] for p in client.get(f"/api/tenders/{tid}/programmes/{pid}/ai/proposals", headers=auth).json()["proposals"]]
    assert {ok_id, rm_id, bad_id} <= set(ids) and len(ids) == 4


def test_ai_needs_a_saved_programme_with_tasks(client, auth):
    tid = tender(client, auth)
    _ai_on(client, auth)
    d = client.post(f"/api/tenders/{tid}/programmes/blank", headers=auth, json={"name": "P"}).json()
    r, _ = _propose(client, auth, tid, d["id"], {"links": [], "remove_links": [], "questions": [], "coverage_notes": ""})
    assert r.status_code == 409 and "Add at least a few tasks" in r.json()["detail"]


def test_a_removal_that_changes_the_link_type_carries_its_replacement_as_a_checked_pair():
    data = {"links": [], "remove_links": [{"pred_uid": 2, "succ_uid": 3, "reason": "Cartage runs alongside stripping", "confidence": "medium", "replace_type": "SS", "replace_lag_days": 1},
                                           {"pred_uid": 3, "succ_uid": 4, "reason": "Not needed", "confidence": "high", "replace_type": "none", "replace_lag_days": 0}],
            "questions": [], "coverage_notes": ""}
    r = pa.verify(data, TASKS)
    rem = [p for p in r["proposals"] if p["kind"] == "remove"]
    new = [p for p in r["proposals"] if p["kind"] == "link"]
    assert [p["confidence"] for p in rem] == ["medium", "high"]                       # removals now carry their own confidence
    assert len(new) == 1 and (new[0]["pred_uid"], new[0]["succ_uid"], new[0]["type"], new[0]["lag_days"]) == (2, 3, "SS", 1)
    assert new[0]["status"] == "ok" and new[0]["pair"] == rem[0]["pair"] and "pair" not in rem[1]


def test_prompt_explains_confidence_and_replacement():
    assert pa.PROMPT_VERSION == "programme-v2" and "replace_type" in pa.SYSTEM and "normal, near-universal construction sequence" in pa.SYSTEM


def test_accepting_one_half_of_a_replacement_pair_takes_the_other_too(client, auth):
    tid = tender(client, auth)
    pid = _saved_programme(client, auth, tid)
    _ai_on(client, auth)
    payload = {"links": [], "remove_links": [{"pred_uid": 2, "succ_uid": 3, "reason": "Runs alongside", "confidence": "medium", "replace_type": "SS", "replace_lag_days": 0}],
                "questions": [], "coverage_notes": ""}
    r, _ = _propose(client, auth, tid, pid, payload)
    ps = r.json()["proposals"]
    assert {p["kind"] for p in ps} == {"link", "remove"} and len({p["pair"] for p in ps}) == 1
    rm = next(p["id"] for p in ps if p["kind"] == "remove")
    d = client.post(f"/api/tenders/{tid}/programmes/{pid}/ai/decision", headers=auth, json={"accept": [rm]})
    assert d.status_code == 200 and {a["kind"] for a in d.json()["accepted"]} == {"link", "remove"}      # the link is never lost
