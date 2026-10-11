import json
from pathlib import Path
import pytest

from tender_engine import D, cents
from tender_engine.edits import EditError, apply_edits
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook
from tender_engine.inputs import from_json, to_json

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"
pytestmark = pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")


@pytest.fixture(scope="module")
def base():
    return load_master_workbook(PRIVATE)


@pytest.fixture(scope="module")
def e0(base):
    return compute_estimate(base)


QS_ADD = {"target": "qs", "op": "add", "key": "ew11", "value": {
    "section": "Earthworks", "description": "Test stripping", "unit": "m2", "quantity": "1000", "basis": "measured", "source": "DWG 301"}}
ROW_ADD = {"target": "row", "op": "add", "key": "N-abc123", "value": {
    "qs_code": "EW11", "mode": "Time x Count", "resource_code": "PL-EXC-13", "task": "Strip with excavator"}}
ROW_PROD = {"target": "row", "key": "N-abc123", "field": "productivity_rate", "value": "100"}


def rows_of(est, code):
    return [r for r in est["buildup"] if r["qs_code"] == code]


def test_add_qs_item_and_row_flows_to_totals(base, e0):
    m, ch = apply_edits(base, [QS_ADD, ROW_ADD, ROW_PROD])
    e = compute_estimate(m)
    line = next(q for q in e["qs"] if q["code"] == "EW11")
    assert line["quantity"] == 1000 and round(line["amount"], 2) == 1500.00           # 1000 m2 / 100 per hr = 10 h x 1 x $150
    assert line["section"] == "Earthworks" and line["rag"] == "AMBER" and "ADDED" in line["status"]
    assert line["basis"] == "MEASURED" and line["source"] == "DWG 301" and line["verification"] == "NOT VERIFIED"
    assert round(e["tender"]["base_direct"] - e0["tender"]["base_direct"], 2) == 1500.00
    sec = lambda est: next(s["amount"] for s in est["sections"] if s["section"] == "Earthworks")
    assert round(sec(e) - sec(e0), 2) == 1500.00
    new = rows_of(e, "EW11")
    assert len(new) == 1 and new[0]["row_id"] == "EW11-001" and new[0]["uid"] == "N-abc123"
    assert new[0]["resource_type"] == "Plant" and new[0]["qa"] == "VERIFY" and new[0]["rag"] == "AMBER"
    assert new[0]["count"] == 1 and new[0]["utilisation"] == 1 and new[0]["waste"] == 0
    # new items sit with their section (after the last Earthworks item), not at the end
    codes = [q["code"] for q in e["qs"]]
    assert codes.index("EW11") == codes.index("EW10") + 1
    # a row edit on a just-added row folds into the add: one 'added' change per new thing, no separate row-set change
    assert [(c["target"], c["field"]) for c in ch] == [("qs", "added"), ("row", "added")]


def test_new_section_and_adding_then_deleting_cancels_out(base, e0):
    new_sec = {**QS_ADD, "value": {**QS_ADD["value"], "section": "Landscaping"}}
    m, ch = apply_edits(base, [new_sec])
    e = compute_estimate(m)
    assert "Landscaping" in [s["section"] for s in e["sections"]] and e["tender"]["base_direct"] == e0["tender"]["base_direct"]
    m2, ch2 = apply_edits(base, [QS_ADD, ROW_ADD, ROW_PROD, {"target": "row", "op": "delete", "key": "N-abc123"},
                                 {"target": "qs", "op": "delete", "key": "EW11"}])
    assert ch2 == []
    assert compute_estimate(m2)["summary"] == e0["summary"]


def test_delete_row_then_edit_a_later_row_by_permanent_id(base, e0):
    # EW02-001 is deleted, so the display id of the old EW02-002 becomes EW02-001, but edits still hit the right row
    old_002 = next(r for r in e0["buildup"] if r["uid"] == "EW02-002")
    m, ch = apply_edits(base, [{"target": "row", "op": "delete", "key": "EW02-001"},
                               {"target": "row", "key": "EW02-002", "field": "job_rate_override", "value": 200}])
    e = compute_estimate(m)
    now = next(r for r in e["buildup"] if r["uid"] == "EW02-002")
    assert now["row_id"] == "EW02-001" and now["applied_rate"] == 200 and now["cost"] != old_002["cost"]
    gone = next(r for r in e0["buildup"] if r["uid"] == "EW02-001")
    assert round(e["tender"]["base_direct"] - e0["tender"]["base_direct"], 2) == round(now["cost"] - old_002["cost"] - gone["cost"], 2)
    removed = next(c for c in ch if c["field"] == "removed")
    assert removed["label"].startswith("EW02-001 ") and removed["key"] == "EW02-001"      # labelled with the id the user saw


def test_delete_qs_item_removes_its_rows(base, e0):
    amount = next(q["amount"] for q in e0["qs"] if q["code"] == "EW04")
    n_rows = len(rows_of(e0, "EW04"))
    assert n_rows > 0
    m, ch = apply_edits(base, [{"target": "qs", "op": "delete", "key": "EW04"}])
    e = compute_estimate(m)
    assert "EW04" not in [q["code"] for q in e["qs"]] and not rows_of(e, "EW04")
    assert round(e0["tender"]["base_direct"] - e["tender"]["base_direct"], 2) == round(amount, 2)
    assert e["buildup"] and len(e["buildup"]) == len(e0["buildup"]) - n_rows
    assert sum(1 for c in ch if c["target"] == "row" and c["field"] == "removed") == n_rows
    assert any(c["target"] == "qs" and c["field"] == "removed" for c in ch)


def test_rows_that_drive_the_weather_calculation_cannot_be_deleted(base):
    for uid in [base.weather_links["daily_uid"], *base.weather_links["weekly_uids"]]:
        with pytest.raises(EditError, match="weather calculation"):
            apply_edits(base, [{"target": "row", "op": "delete", "key": uid}])
    # deleting the whole QS item that contains one is blocked too
    qs_code = next(r.qs_code for r in base.rows if r.uid == base.weather_links["daily_uid"])
    with pytest.raises(EditError, match="weather calculation"):
        apply_edits(base, [{"target": "qs", "op": "delete", "key": qs_code}])


def test_weather_links_survive_deleting_rows_before_them(base, e0):
    m, _ = apply_edits(base, [{"target": "qs", "op": "delete", "key": "EW01"}])       # removes rows ahead of the weather rows
    e = compute_estimate(m)
    assert e["weather"]["daily_prelims"] == e0["weather"]["daily_prelims"]           # still the supervisor rate x 8
    assert e["weather"]["weekly_hire"] == e0["weather"]["weekly_hire"]
    assert e["weather"]["exposed_pool"] < e0["weather"]["exposed_pool"]               # EW01 plant/labour no longer exposed


def test_new_library_rate_and_row(base):
    lib = {"target": "library", "op": "add", "key": "pl-test-1", "value": {"description": "20 t excavator", "unit": "hr", "base_rate": "200", "category": "Plant"}}
    row = {"target": "row", "op": "add", "key": "N-xyz789", "value": {"qs_code": "EW01", "mode": "Direct Qty", "resource_code": "PL-TEST-1", "task": "Extra plant"}}
    qty = {"target": "row", "key": "N-xyz789", "field": "manual_qty", "value": "5"}
    m, ch = apply_edits(base, [lib, row, qty])
    e = compute_estimate(m)
    r = next(x for x in e["buildup"] if x["uid"] == "N-xyz789")
    assert r["library_rate"] == 200 and r["cost"] == 1000 and r["resource_type"] == "Plant" and r["library_source"].startswith("Added in platform")
    assert [c["field"] for c in ch] == ["added", "added"] and ch[0]["target"] == "library"
    assert any(x["code"] == "PL-TEST-1" for x in e["library"])


def test_lump_sum_row_may_have_no_library_rate(base):
    row = {"target": "row", "op": "add", "key": "N-lump01", "value": {"qs_code": "ES01", "mode": "Lump Sum / Quote", "resource_code": "", "task": "Allowance"}}
    price = [{"target": "row", "key": "N-lump01", "field": "manual_qty", "value": 1}, {"target": "row", "key": "N-lump01", "field": "job_rate_override", "value": 2500}]
    m, _ = apply_edits(base, [row, *price])
    r = next(x for x in compute_estimate(m)["buildup"] if x["uid"] == "N-lump01")
    assert r["cost"] == 2500 and r["resource_type"] == "Other"


@pytest.mark.parametrize("edit,msg", [
    ({**QS_ADD, "key": "9X"}, "QS code is letters"),
    ({**QS_ADD, "key": "EW01"}, "already used"),
    ({**QS_ADD, "value": {**QS_ADD["value"], "basis": "GUESS"}}, "Classify the quantity"),
    ({**QS_ADD, "value": {**QS_ADD["value"], "quantity": -3}}, "less than"),
    ({**QS_ADD, "value": {**QS_ADD["value"], "description": " "}}, "can't be blank"),
    ({**QS_ADD, "value": {**QS_ADD["value"], "unit": "x" * 20}}, "too long"),
    ({**ROW_ADD, "value": {**ROW_ADD["value"], "qs_code": "NOPE"}}, "Unknown QS item"),
    ({**ROW_ADD, "value": {**ROW_ADD["value"], "qs_code": "EW01", "mode": "Magic"}}, "Calculation mode"),
    ({**ROW_ADD, "value": {**ROW_ADD["value"], "qs_code": "EW01", "resource_code": ""}}, "Choose a rate"),
    ({**ROW_ADD, "value": {**ROW_ADD["value"], "qs_code": "EW01", "resource_code": "NOPE-1"}}, "not in this tender's library"),
    ({**ROW_ADD, "key": "bad id"}, "invalid or already used"),
    ({**ROW_ADD, "key": "EW01-001"}, "invalid or already used"),
    ({"target": "library", "op": "add", "key": "PL-EXC-13", "value": {"description": "d", "unit": "hr", "base_rate": 1, "category": "Plant"}}, "already exists"),
    ({"target": "library", "op": "add", "key": "NEW-1", "value": {"description": "d", "unit": "hr", "base_rate": 1, "category": "Wizards"}}, "Category must be"),
    ({"target": "library", "op": "add", "key": "NEW-1", "value": {"description": "d", "unit": "hr", "base_rate": -1, "category": "Plant"}}, "less than"),
    ({"target": "library", "op": "delete", "key": "PL-EXC-13"}, "can only be added"),
    ({"target": "row", "op": "delete", "key": "ZZ-9"}, "Unknown build-up row"),
    ({"target": "qs", "op": "delete", "key": "ZZ9"}, "Unknown QS item"),
    ({"target": "qs", "op": "explode", "key": "EW01"}, "Unknown operation"),
])
def test_invalid_structural_edits_have_plain_messages(base, edit, msg):
    with pytest.raises(EditError, match=msg):
        apply_edits(base, [edit])


def test_cannot_edit_or_reuse_things_already_deleted(base):
    with pytest.raises(EditError, match="has been deleted"):
        apply_edits(base, [{"target": "row", "op": "delete", "key": "EW01-001"}, {"target": "row", "key": "EW01-001", "field": "count", "value": 2}])
    with pytest.raises(EditError, match="has been deleted"):
        apply_edits(base, [{"target": "qs", "op": "delete", "key": "EW04"}, ROW_ADD | {"value": {**ROW_ADD["value"], "qs_code": "EW04"}}])
    with pytest.raises(EditError, match="already used"):          # a deleted code can't be reused in the same change set
        apply_edits(base, [{"target": "qs", "op": "delete", "key": "EW04"}, {**QS_ADD, "key": "EW04"}])


def test_structural_edits_survive_json_roundtrip_and_do_not_mutate_original(base):
    before = json.dumps(to_json(base), sort_keys=True)
    m, _ = apply_edits(base, [QS_ADD, ROW_ADD, ROW_PROD, {"target": "row", "op": "delete", "key": "EW02-001"}])
    assert json.dumps(to_json(base), sort_keys=True) == before
    again = from_json(json.loads(json.dumps(to_json(m))))
    assert compute_estimate(again) == compute_estimate(m)
    assert "N-abc123" in [r.uid for r in again.rows]
    # and an edited revision can itself be edited further, by uid
    m3, ch3 = apply_edits(again, [{"target": "row", "key": "N-abc123", "field": "productivity_rate", "value": 50}])
    assert [c["field"] for c in ch3] == ["productivity_rate"] and ch3[0]["label"].startswith("EW11-001")


def test_inputs_saved_before_row_ids_existed_still_load(base, e0):
    blob = json.loads(json.dumps(to_json(base)))
    for r in blob["rows"]:
        r.pop("uid")
    blob["weather_links"].pop("daily_uid"); blob["weather_links"].pop("weekly_uids")
    old = from_json(blob)
    assert [r.uid for r in old.rows][:3] == ["EW01-001", "EW01-002", "EW02-001"]     # the display ids they had at the time
    assert compute_estimate(old)["summary"] == e0["summary"]
