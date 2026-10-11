import datetime as dt
from pathlib import Path

import pytest

from tender_engine import D
from tender_engine.blank import blank_from_template
from tender_engine.edits import EditError, apply_edits
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook
from tender_engine.inputs import from_json, to_json
from tender_engine.weather_tool import Activity, ToolSettings, run_tool

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"
pytestmark = pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")


@pytest.fixture(scope="module")
def template():
    return load_master_workbook(PRIVATE)


QS = {"target": "qs", "op": "add", "key": "EW01", "value": {"section": "Earthworks", "description": "Strip", "unit": "m2", "quantity": "1000", "basis": "MEASURED"}}
PLANT = {"target": "row", "op": "add", "key": "N-plant01", "value": {"qs_code": "EW01", "mode": "Time x Count", "resource_code": "PL-EXC-13", "task": "Strip"}}
PROD = {"target": "row", "key": "N-plant01", "field": "productivity_rate", "value": "20"}
EXPOSE = {"target": "row", "key": "N-plant01", "field": "weather_exposed", "value": "Yes"}
SETUP = {"target": "weather", "op": "add", "key": "setup", "value": {"station": "Auckland", "start": "2026-10-01", "working_days_per_week": 5, "baseline_wd": 55}}
ACT = {"target": "weather_activity", "op": "add", "key": "W-act0001", "value": {"task": "Bulk earthworks", "start": "2026-10-01", "finish": "2026-10-30", "critical": True, "qs_codes": "EW01"}}
BUILD = [QS, PLANT, PROD, EXPOSE]


def blank(template):
    return blank_from_template(template, "x", {})


def test_live_tool_on_a_new_tender_matches_the_tool_port_and_feeds_ca10(template):
    base = blank(template)
    m, changes = apply_edits(base, BUILD + [SETUP, ACT])
    e = compute_estimate(m)
    exposed = sum(r["cost"] for r in e["buildup"] if r["weather_exposed"])
    assert exposed > 0
    act = e["weather"]["tool"]["activities"][0]
    assert act["labour"] == 0 and abs(act["plant"] - exposed) < 1e-9 and act["workdays"] == 22
    expect = run_tool(ToolSettings("Auckland", 5), [Activity("Bulk earthworks", dt.date(2026, 10, 1), dt.date(2026, 10, 30), True, D(0), D(str(exposed)))])
    assert abs(e["weather"]["direct_productivity"] - float(expect.direct_allowance)) < 1e-6
    assert abs(e["weather"]["critical_path_delay_wd"] - float(expect.critical_path_delay_wd)) < 1e-9
    assert e["weather"]["live"] is True and e["weather"]["meta"]["station"] == "Auckland"
    ca10 = next(c for c in e["commercial"] if c["ref"] == "CA10")
    assert abs(ca10["amount"] - e["weather"]["allowance"]) < 1e-9 and ca10["amount"] > 0
    assert {c["target"] for c in changes} >= {"weather", "weather_activity"}


def test_manual_amounts_work_without_any_exposed_rows(template):
    m, _ = apply_edits(blank(template), [SETUP, {**ACT, "value": {**ACT["value"], "qs_codes": "", "labour": "10000", "plant": "5000"}}])
    e = compute_estimate(m)
    expect = run_tool(ToolSettings("Auckland", 5), [Activity("Bulk earthworks", dt.date(2026, 10, 1), dt.date(2026, 10, 30), True, D(10000), D(5000))])
    assert e["weather"]["direct_productivity"] > 0 and abs(e["weather"]["direct_productivity"] - float(expect.direct_allowance)) < 1e-6


def test_unlinked_exposed_cost_is_warned_about(template):
    m, _ = apply_edits(blank(template), BUILD + [SETUP])
    e = compute_estimate(m)
    assert any("not linked" in w for w in e["weather"]["tool"]["warnings"]) and e["weather"]["direct_productivity"] == 0


def test_wind_switch_and_local_factor_change_the_allowance(template):
    m, _ = apply_edits(blank(template), BUILD + [SETUP, ACT])
    base = compute_estimate(m)["weather"]
    m2, ch = apply_edits(m, [{"target": "weather", "key": "setup", "field": "include_wind", "value": "Yes"}])
    w2 = compute_estimate(m2)["weather"]
    assert w2["wind_included"] and w2["allowance"] > base["allowance"] and abs(w2["allowance"] - base["allowance"] - base["wind_sensitivity"]) < 1e-6 or w2["allowance"] > base["allowance"]
    m3, _ = apply_edits(m, [{"target": "weather", "key": "setup", "field": "local_factor", "value": "1.2"}])
    assert compute_estimate(m3)["weather"]["direct_productivity"] > base["direct_productivity"]
    assert ch and ch[0]["field"] == "include_wind"


def test_round_trip_through_saved_json(template):
    m, _ = apply_edits(blank(template), BUILD + [SETUP, ACT])
    a, b = compute_estimate(m), compute_estimate(from_json(to_json(m)))
    assert a["weather"]["allowance"] == b["weather"]["allowance"] and a["summary"]["all_in"] == b["summary"]["all_in"]


def test_turning_it_on_for_an_imported_tender_and_off_again_restores_the_recorded_run(template):
    e0 = compute_estimate(template)
    m, ch = apply_edits(template, [SETUP, ACT])
    assert compute_estimate(m)["weather"]["live"] is True and compute_estimate(m)["weather"]["allowance"] != e0["weather"]["allowance"]
    m2, ch2 = apply_edits(m, [{"target": "weather", "op": "delete", "key": "setup"}])
    assert compute_estimate(m2)["weather"]["allowance"] == e0["weather"]["allowance"] and compute_estimate(m2)["weather"]["live"] is False
    assert ch2 and ch2[0]["field"] == "removed"          # relative to the edited version
    assert apply_edits(template, [SETUP, ACT, {"target": "weather", "op": "delete", "key": "setup"}])[1] == []


def test_net_changes_cancel_when_added_then_removed(template):
    _, ch = apply_edits(blank(template), [SETUP, ACT, {"target": "weather_activity", "op": "delete", "key": "W-act0001"},
                                          {"target": "weather", "op": "delete", "key": "setup"}])
    assert ch == []


@pytest.mark.parametrize("edit,msg", [
    ({"target": "weather", "op": "add", "key": "setup", "value": {"station": "Atlantis", "start": "2026-10-01"}}, "station"),
    ({"target": "weather", "op": "add", "key": "setup", "value": {"station": "Auckland", "start": "2045-10-01"}}, "between"),
    ({"target": "weather", "op": "add", "key": "setup", "value": {"station": "Auckland", "start": "soon"}}, "valid date"),
    ([SETUP, {"target": "weather", "key": "setup", "field": "local_factor", "value": "0"}], "Local wet-day factor"),
    ({"target": "weather_activity", "op": "add", "key": "W-act0009", "value": ACT["value"]}, "Switch the live weather tool on"),
    ({"target": "weather", "key": "setup", "field": "station", "value": "x"}, "Switch the live weather tool on"),
])
def test_bad_weather_edits_give_plain_messages(template, edit, msg):
    with pytest.raises(EditError, match=msg):
        apply_edits(blank(template), edit if isinstance(edit, list) else [edit])


def test_activity_validation(template):
    for bad, msg in [({"task": "Nope", "start": "2026-10-01", "finish": "2026-10-02"}, "task library"),
                     ({"task": "Bulk earthworks", "start": "2026-10-05", "finish": "2026-10-02"}, "before it starts"),
                     ({"task": "Bulk earthworks", "start": "2026-10-05"}, "start and a finish"),
                     ({"task": "Bulk earthworks", "start": "2026-10-01", "finish": "2026-10-02", "labour": "-5"}, "Exposed labour"),
                     ({"task": "Bulk earthworks", "start": "2026-10-01", "finish": "2026-10-02", "ov_rain_loss": "2"}, "rain loss")]:
        with pytest.raises(EditError, match=msg):
            apply_edits(blank(template), [SETUP, {**ACT, "value": bad}])
    with pytest.raises(EditError, match="already used"):
        apply_edits(blank(template), [SETUP, ACT, ACT])
    with pytest.raises(EditError, match="at most"):
        apply_edits(blank(template), [SETUP] + [{**ACT, "key": f"W-act{i:04d}"} for i in range(31)])


def test_links_and_protection_follow_the_chosen_rows(template):
    base, _ = apply_edits(blank(template), BUILD)
    link = {"target": "weather", "key": "links", "field": "daily_uid", "value": "N-plant01"}
    m, _ = apply_edits(base, [link])
    with pytest.raises(EditError, match="drives the weather"):
        apply_edits(m, [{"target": "row", "op": "delete", "key": "N-plant01"}])
    apply_edits(base, [{"target": "row", "op": "delete", "key": "N-plant01"}])          # fine while unlinked
    with pytest.raises(EditError, match="Unknown build-up row"):
        apply_edits(base, [{**link, "value": "N-nothere"}])
    # prelims now come from the linked row's rate x hours per day
    e = compute_estimate(apply_edits(m, [{"target": "weather", "key": "links", "field": "hours_per_day", "value": 10}])[0])
    assert e["weather"]["daily_prelims"] == pytest.approx(e["buildup"][0]["applied_rate"] * 10)
