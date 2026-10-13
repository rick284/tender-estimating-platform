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
