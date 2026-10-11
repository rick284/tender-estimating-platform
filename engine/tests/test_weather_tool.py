import datetime as dt
import json
from pathlib import Path

import pytest

from tender_engine import D
from tender_engine.weather_tool import Activity, ToolSettings, run_tool, stations, task_names, tool_data

GOLD = json.loads((Path(__file__).parent / "golden_weather_rev2.json").read_text())["scenarios"]
TOL = 1e-6


def _run(sc, include_wind=True):
    settings = ToolSettings(sc["station"], sc["working_days_per_week"], D(sc["local_factor"]),
                            None if sc["wind_override"] is None else D(sc["wind_override"]),
                            D(sc["daily_prelims"]), D(sc["weekly_hire"]), D(sc["recovery"]))
    acts = [Activity(a["task"], dt.date.fromisoformat(a["start"]), dt.date.fromisoformat(a["finish"]), a["critical"],
                     D(a["labour"]), D(a["plant"]), {k: D(v) for k, v in a["overrides"].items()}) for a in sc["activities"]]
    return run_tool(settings, acts, include_wind=include_wind)


@pytest.mark.parametrize("i", range(len(GOLD)))
def test_matches_the_real_tool_workbook(i):
    """Each scenario was run through NZ_Weather_Risk_Estimating_Tool_Rev2.xlsx (recalculated in LibreOffice)."""
    sc = GOLD[i]; exp = sc["expected"]; r = _run(sc)
    for act, a, e in zip(sc["activities"], r.activities, exp["activities"]):
        assert a.workdays == e["workdays"]
        if a.workdays == 0:       # the workbook leaves the row blank; the platform flags it RED
            assert e["wet_probability"] is None and a.status == "RED - date input"
            continue
        for mine, key in [(a.wet_probability, "wet_probability"), (a.adjusted_wet_probability, "adjusted_wet_probability"),
                          (a.wind_probability, "wind_probability"), (a.rain_impact, "rain_impact"), (a.carryover_impact, "carryover_impact"),
                          (a.wind_impact, "wind_impact"), (a.combined_impact, "combined_impact"), (a.direct_allowance, "direct_allowance"),
                          (a.lost_wd, "lost_wd")]:
            assert abs(float(mine) - float(e[key])) < TOL, (i, a.task, key, mine, e[key])
        numeric_wind = a.status == "RED - wind input" or "wind_sensitivity" in act["overrides"] or \
            next(t for t in tool_data()["tasks"] if t["name"] == a.task)["wind_sensitivity"] >= "0.2"
        if numeric_wind or e["status"] != "RED - wind input":
            assert a.status == e["status"], (a.task, a.status, e["status"])
        else:
            # Known workbook quirk: task factors are stored as TEXT, and Excel treats text as greater than any number, so
            # the workbook flags every task at a station with no wind data as RED. The platform applies the intended rule
            # (RED only when wind sensitivity is 20% or more).
            assert a.wind_probability == 0 and a.status.startswith("AMBER")
    assert abs(float(r.exposed_pool) - exp["exposed_pool"]) < TOL
    if exp["total"] == "#VALUE!":
        # An activity with no working days breaks the workbook's totals (#VALUE!). The platform flags that row RED and
        # totals the valid rows, so compare with the workbook's own per-activity numbers for the valid rows.
        ok = [(act, e) for act, e in zip(sc["activities"], exp["activities"]) if e["workdays"]]
        direct = sum(float(e["direct_allowance"]) for _, e in ok)
        delay = sum(float(e["cp_delay_wd"]) for _, e in ok)
        assert abs(float(r.direct_allowance) - direct) < TOL and abs(float(r.critical_path_delay_wd) - delay) < TOL
        return
    assert abs(float(r.direct_allowance) - exp["direct"]) < TOL
    assert abs(float(r.critical_path_delay_wd) - exp["cp_delay_wd"]) < TOL
    assert r.additional_billed_weeks == exp["weeks"]
    assert abs(float(r.prelims_allowance) - exp["prelims"]) < TOL
    assert abs(float(r.hire_allowance) - exp["hire"]) < TOL
    assert abs(float(r.total_allowance) - exp["total"]) < TOL


def test_wind_excluded_basis_removes_only_the_wind_term():
    sc = next(s for s in GOLD if s["station"] == "Auckland" and s["wind_override"] is None)
    w, x = _run(sc, True), _run(sc, False)
    assert x.wind_sensitivity == w.wind_sensitivity > 0
    assert x.direct_allowance + x.wind_sensitivity == w.direct_allowance
    assert x.critical_path_delay_wd <= w.critical_path_delay_wd


def test_data_is_complete():
    d = tool_data()
    assert len(stations()) == 30 and len(task_names()) == 39 and d["engine_from"] == "2025-01-01"
    assert all(len(v) == 12 for v in d["climate"].values())


def test_input_validation():
    s = ToolSettings("Auckland")
    day = dt.date(2026, 10, 1)
    with pytest.raises(ValueError):
        run_tool(s, [Activity("Not a task", day, day)])
    with pytest.raises(ValueError):
        run_tool(ToolSettings("Atlantis"), [Activity("Bulk earthworks", day, day)])
    r = run_tool(s, [Activity("Bulk earthworks", dt.date(2045, 1, 1), dt.date(2045, 2, 1), True, D(100), D(0))])
    assert r.activities[0].status == "RED - date input" and r.red_flags and r.confidence.startswith("RED")
    sat = dt.date(2026, 10, 3)   # a Saturday: no working days in the window
    assert run_tool(s, [Activity("Bulk earthworks", sat, sat, True, D(100), D(0))]).activities[0].status == "RED - date input"
    assert run_tool(s, []).confidence.startswith("INCOMPLETE")


def test_non_auckland_wind_sensitive_task_is_flagged_red():
    day = dt.date(2026, 10, 1)
    r = run_tool(ToolSettings("Christchurch"), [Activity("Roofing", day, day + dt.timedelta(days=30), True, D(1000), D(0))])
    assert r.activities[0].status == "RED - wind input" and r.red_flags
