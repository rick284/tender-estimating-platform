import copy
import pytest
from tender_engine.diff import diff_estimates


def est(all_in=1000.0, qs=None, rows=None):
    qs = qs or [{"code": "EW01", "description": "Strip", "unit": "m2", "quantity": 100.0, "amount": 500.0, "section": "Earthworks"}]
    rows = rows or [{"row_id": "EW01-001", "qs_code": "EW01", "task": "Strip", "resource": "Excavator", "applied_rate": 150.0, "hours": 10.0, "cost": 500.0}]
    return {"summary": {"all_in": all_in, "siteworks_tender": 600.0, "known_cost": 800.0, "base_direct": 500.0,
                        "management_reserve": 10.0, "weather_allowance": 5.0},
            "sections": [{"section": "Earthworks", "amount": sum(q["amount"] for q in qs), "items": []}],
            "qs": qs, "buildup": rows,
            "commercial": [{"ref": "CA10", "name": "Weather", "method": "Weather Engine", "include": True, "pct": 0.0, "pc_sum": 0.0, "amount": 5.0, "stage": "pre"}],
            "consolidated": {"overlays": [{"name": "Coast", "amount": 200.0, "kind": "QUOTED"}]}}


def test_identical():
    d = diff_estimates(est(), est())
    assert d["identical"] and d["counts"] == {"qs_changed": 0, "buildup_changed": 0, "commercial_changed": 0, "overlays_changed": 0, "settings_changed": 0}


def test_headline_and_quantity_change():
    b = est(all_in=1100.0)
    b["qs"][0].update(quantity=120.0, amount=600.0)
    b["buildup"][0].update(hours=12.0, cost=600.0)
    d = diff_estimates(est(), b)
    assert d["headline"][0]["delta"] == 100.0
    assert d["qs"][0]["kind"] == "changed" and d["qs"][0]["delta"] == 100.0 and d["qs"][0]["qty_b"] == 120.0
    assert d["buildup"][0]["kind"] == "changed" and d["buildup"][0]["hours_b"] == 12.0
    assert not d["identical"]


def test_added_removed_items_sorted_by_impact():
    a = est()
    b = est(qs=[{"code": "PV01", "description": "Pavement", "unit": "m2", "quantity": 10.0, "amount": 5000.0, "section": "Pavements"}],
            rows=[{"row_id": "PV01-001", "qs_code": "PV01", "task": "Pave", "resource": "Concrete", "applied_rate": 500.0, "hours": 0.0, "cost": 5000.0}])
    d = diff_estimates(a, b)
    kinds = {c["code"]: c["kind"] for c in d["qs"]}
    assert kinds == {"PV01": "added", "EW01": "removed"}
    assert d["qs"][0]["code"] == "PV01"                      # biggest movement first
    assert {r["kind"] for r in d["buildup"]} == {"added", "removed"}


def test_overlay_and_commercial_changes():
    b = est()
    b["consolidated"]["overlays"][0]["amount"] = 250.0
    b["commercial"][0].update(include=False, amount=0.0)
    d = diff_estimates(est(), b)
    assert d["overlays"][0]["delta"] == 50.0
    assert d["commercial"][0]["include_a"] is True and d["commercial"][0]["include_b"] is False


def test_real_hobsonville_c_to_e():
    from pathlib import Path
    from tender_engine.estimate import compute_estimate
    from tender_engine.importers import load_master_workbook
    root = Path(__file__).resolve().parents[2] / "private"
    if not (root / "Rev34C.xlsx").exists() or not (root / "Rev34E.xlsx").exists():
        pytest.skip("private workbooks not present")
    a = compute_estimate(load_master_workbook(root / "Rev34C.xlsx"))
    b = compute_estimate(load_master_workbook(root / "Rev34E.xlsx"))
    d = diff_estimates(a, b)
    head = {h["key"]: h for h in d["headline"]}
    assert round(head["all_in"]["a"], 2) == 1163543.00 and round(head["all_in"]["b"], 2) == 1226916.81
    assert round(head["all_in"]["delta"], 2) == 63373.81
    # Rev34C -> Rev34E: every cost is identical; the whole movement is the commercial settings.
    assert d["counts"]["qs_changed"] == 0 and d["counts"]["buildup_changed"] == 0
    assert round(head["known_cost"]["delta"], 2) == 0 and round(head["base_direct"]["delta"], 2) == 0
    s = {x["key"]: x for x in d["settings"]}
    assert round(s["overhead_rate"]["b"], 4) == 0.10 and round(s["margin"]["b"], 4) == 0.15
    assert s["overhead_rate"]["a"] < 0.10 and s["margin"]["a"] < 0.15
    assert [c["ref"] for c in d["commercial"]] == ["CA17", "CA18"]
    assert not d["identical"]
