import io

import openpyxl

from conftest import *            # noqa: F401,F403
from factory import make_workbook
import programme_table as pt

MSP_HEAD = ["ID", "Outline Level", "WBS", "Task Name", "Duration", "Predecessors", "Fixed Cost", "Start", "Finish", "Resource Names", "Category", "Notes"]
MSP_ROWS = [[1, 1, "", "Earthworks", "0 days", "", "", "", "", "", "Summary", ""],
            [2, 2, "EW01", "Strip and stockpile", "3 days", "", 100, "", "", "Excavator; Labourer", "Earthworks", "first"],
            [3, 2, "TS01", "Proof roll and inspection", "1 day", "2", 0, "", "", "", "Control", "hold point"],
            [4, 2, "EW02", "Place fill", "2 wks", "3FS+1d", 200, "", "", "Roller", "Earthworks", ""],
            [5, 1, "MILESTONE-PC", "Practical completion", "0 days", "4;3", 0, "", "", "", "Milestone", ""]]


def workbook_with_msp_sheet() -> bytes:
    wb = openpyxl.load_workbook(io.BytesIO(make_workbook()))
    ws = wb.create_sheet("MS Project Import")
    ws.append(MSP_HEAD)
    for r in MSP_ROWS:
        ws.append(r)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_the_csv_table_becomes_gantt_tasks_with_links_resources_and_milestones():
    rows = [MSP_HEAD] + [[str(c) for c in r] for r in MSP_ROWS]
    tasks = pt.tasks_from_table(rows)
    by = {t["name"]: t for t in tasks}
    assert [t["outline_level"] for t in tasks] == [1, 2, 2, 2, 1]
    assert by["Strip and stockpile"]["duration"] == {"value": 3, "unit": "D"} and by["Strip and stockpile"]["resources"] == ["Excavator", "Labourer"]
    assert by["Place fill"]["duration"]["value"] == 10                                            # 2 weeks = 10 working days
    assert by["Place fill"]["predecessors"] == [{"uid": 3, "type": "FS", "lag_days": 1}]
    assert by["Practical completion"].get("is_milestone") and {p["uid"] for p in by["Practical completion"]["predecessors"]} == {3, 4}
    assert pt.duration_days("16 hrs") == 2 and pt.duration_days("55 days") == 55 and pt.duration_days("TBC") is None


def test_csv_text_is_read_whatever_the_delimiter():
    text = "﻿ID;Task Name;Duration;Predecessors\n1;Dig;2 days;\n2;Lay;1 day;1\n"
    t = pt.tasks_from_table(pt.read_csv(text.encode("utf-8")))
    assert [x["name"] for x in t] == ["Dig", "Lay"] and t[1]["predecessors"][0]["uid"] == 1


def test_uploading_a_csv_to_the_gantt_builds_a_programme(client, auth):
    tid = client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", make_workbook())}).json()["id"]
    csv = ",".join(MSP_HEAD) + "\n" + "\n".join(",".join(str(c) for c in r) for r in MSP_ROWS) + "\n"
    r = client.post(f"/api/tenders/{tid}/programmes/upload", headers=auth, files={"file": ("prog.csv", csv.encode(), "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["task_count"] == 5 and r.json()["needs_schedule"] is True
    bad = client.post(f"/api/tenders/{tid}/programmes/upload", headers=auth, files={"file": ("p.csv", b"A,B\n1,2\n", "text/csv")})
    assert bad.status_code == 400


def test_a_workbook_with_only_the_ms_project_import_sheet_builds_the_programme_on_upload(client, auth):
    r = client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", workbook_with_msp_sheet())})
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    docs = client.get(f"/api/tenders/{tid}/programmes", headers=auth).json()["programmes"]
    assert len(docs) == 1 and docs[0]["source"] == "workbook"
    full = client.get(f"/api/tenders/{tid}/programmes/{docs[0]['id']}", headers=auth).json()
    names = [t["name"] for t in full["tasks"]]
    assert any(n.startswith("EW01") for n in names) and any(n.startswith("TS01") for n in names)
    ts = next(t for t in full["tasks"] if t["name"].startswith("TS01"))
    ew1 = next(t for t in full["tasks"] if t["name"].startswith("EW01"))
    assert ts["predecessors"] == [{"uid": ew1["uid"], "type": "FS", "lag_days": 0}]


def test_a_workbook_without_a_programme_makes_no_programme(client, auth):
    tid = client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", make_workbook())}).json()["id"]
    assert client.get(f"/api/tenders/{tid}/programmes", headers=auth).json()["programmes"] == []
