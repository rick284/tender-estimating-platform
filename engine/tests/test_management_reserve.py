"""Management Reserve adjudication: weighted exposure items -> range -> selected reserve (fixed), feeding CA16 once."""
from decimal import Decimal
from pathlib import Path

import pytest

from tender_engine import management_reserve as mr
from tender_engine.edits import EditError, apply_edits
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook
from tender_engine.inputs import from_json, to_json

D = Decimal
F = D("1.1") / D("0.85")            # 10% overhead, 15% true margin
PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"
needs_private = pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")


def block(*items, selected="", basis=""):
    b = mr.new_block(selected, basis)
    for i, v in enumerate(items):
        b["items"].append(mr.build_item(f"M-t{i:04d}", v, b["items"]))
    return b


def test_policy_worked_example_hobsonville_rev34():
    """Policy section 15 (example only): A $28.6k sell at 55-65%, B $9.5k sell at 30-40%, C no incremental consequence, D unquantified.
    Weighted sell exposure about $18.6k to $22.4k, midpoint about $20.5k."""
    b = block(dict(title="Rev17 vs Yodha earthworks", impact="28600", probability_low="0.55", probability_high="0.65"),
              dict(title="Ramp / entry / stairs ownership", impact="9500", probability_low="0.30", probability_high="0.40"),
              dict(title="Retaining 1.5m vs 1.8m", impact="0", probability_low="0.8"),
              dict(title="PV01 productivity", impact_status="Unquantified", probability_low="0.5"), selected="18269.06")
    r = mr.compute(b, F)
    assert abs(r["weighted_low_sell"] - D("18580")) < D("0.01") and abs(r["weighted_high_sell"] - D("22390")) < D("0.01")
    assert abs(r["weighted_mid_sell"] - D("20485")) < D("0.01")
    assert r["unquantified_items"] == 1 and r["unknown_items"] == 0
    # reserve is a pre-margin cost: 18,269.06 sells for 23,642, above the top of the sell range at today's 10% / 15%
    assert r["position"] == "above" and abs(r["selected_sell"] - D("23642.31")) < D("0.01")
    assert [i["counted"] for i in r["items"]] == [True, True, True, False]
    assert r["items"][3]["weighted_low"] is None


def test_unknown_probability_is_never_turned_into_dollars():
    b = block(dict(title="X", impact="10000", basis="Cost", probability_low="0.5", prob_status="UNKNOWN"), selected="1000", basis="why")
    r = mr.compute(b, F)
    assert r["weighted_high"] == 0 and r["unknown_items"] == 1 and r["items"][0]["sensitivity"] == D("10000") and r["items"][0]["status"] == "RED"
    b2 = block(dict(title="No probability given", impact="10000", basis="Cost"), selected="1000")
    assert mr.compute(b2, F)["items"][0]["weighted_low"] is None


def test_cost_basis_needs_no_conversion_and_sell_basis_converts():
    r = mr.compute(block(dict(title="c", impact="1000", basis="Cost", probability_low="0.5"), dict(title="s", impact="1000", basis="Sell", probability_low="0.5")), F)
    assert r["items"][0]["weighted_low"] == D("500") and abs(r["items"][1]["weighted_low"] - D("500") / F) < D("0.0001")


def test_overlap_only_primary_counts_and_issues_are_raised():
    b = block(dict(title="A", impact="1000", basis="Cost", probability_low="0.5", overlap_group="G1", owner="Primary"),
              dict(title="B", impact="1000", basis="Cost", probability_low="0.5", overlap_group="g1", owner="Contributing"), selected="500", basis="x")
    r = mr.compute(b, F)
    assert r["weighted_low"] == D("500") and [i["counted"] for i in r["items"]] == [True, False] and not r["issues"]
    two = block(dict(title="A", impact="1000", basis="Cost", probability_low="0.5", overlap_group="G", owner="Primary"),
                dict(title="B", impact="1000", basis="Cost", probability_low="0.5", overlap_group="G", owner="Primary"))
    assert any("2 Primary" in i for i in mr.compute(two, F)["issues"]) and mr.compute(two, F)["status"] == "RED"
    none = block(dict(title="A", impact="1000", basis="Cost", probability_low="0.5", overlap_group="G", owner="Contributing"),
                 dict(title="B", impact="1000", basis="Cost", probability_low="0.5", overlap_group="G", owner="Reference Only"))
    r = mr.compute(none, F)
    assert r["weighted_low"] == 0 and any("no Primary" in i for i in r["issues"])


def test_item_already_provided_in_risk_truth_is_not_counted_again():
    b = block(dict(title="A", impact="1000", basis="Cost", probability_low="0.5", exposure_ref="RT05-001"), selected="1", basis="x")
    r = mr.compute(b, F, [{"ref": "RT05-001", "addition": D("750")}])
    assert r["weighted_low"] == 0 and r["items"][0]["counted"] is False and any("Risk Truth" in i for i in r["issues"])
    assert mr.compute(b, F, [{"ref": "RT05-001", "addition": D("0")}])["weighted_low"] == D("500")


def test_validation():
    for f, bad in (("impact", "-1"), ("impact", "abc"), ("probability_low", "60"), ("probability_high", "-0.1"), ("basis", "Gross"), ("owner", "Boss"),
                   ("impact_status", "Maybe"), ("prob_status", "SURE")):
        with pytest.raises(mr.ReserveError):
            mr.set_item_field({**{k: "" for k in mr.ITEM_FIELDS}, "id": "M-x"}, f, bad)
    with pytest.raises(mr.ReserveError):
        mr.build_item("M-x", dict(title="x", probability_low="0.6", probability_high="0.4"), [])
    with pytest.raises(mr.ReserveError):
        mr.build_item("M-x", {}, [])
    with pytest.raises(mr.ReserveError):
        mr.set_block_field(mr.new_block(), "selected", "-5")
    i = mr.build_item("M-abcd1", dict(title="x", probability_low="0.6"), [])
    assert i["probability_high"] == "0.6" and i["ref"] == "MR-01" and i["prob_status"] == "AMBER"


@needs_private
def test_hobsonville_import_keeps_the_total_and_the_rationale():
    m = load_master_workbook(PRIVATE)
    assert m.management_reserve["selected"].startswith("18269.06") and "Rick Jones approved 4.0%" in m.management_reserve["selected_basis"]
    e = compute_estimate(m)
    assert e["reconciled"] is True and abs(e["summary"]["all_in"] - 1226916.81) < 0.01 and e["summary"]["management_reserve"] > 18269
    r = e["management_reserve"]
    assert abs(r["selected_sell"] - 23642.32) < 0.01 and r["status"] == "AMBER" and r["position"] is None
    # the four red items from the workbook's own "MANAGEMENT RESERVE - ADJUDICATION BASIS" block; no probabilities are invented
    its = {i["ref"]: i for i in r["items"]}
    assert [i["title"] for i in r["items"]] == ["Earthworks (red item)", "Ramp/stairs (red item)", "Retaining (red item)", "PV01 productivity (red item)"]
    assert (its["MR-01"]["impact"], its["MR-01"]["impact_status"]) == ("28600", "Quantified") and (its["MR-02"]["impact"], its["MR-02"]["impact_status"]) == ("9500", "Proxy")
    assert its["MR-03"]["impact"] == "0" and its["MR-04"]["impact_status"] == "Unquantified" and all(i["prob_status"] == "UNKNOWN" for i in r["items"])
    assert r["weighted_high"] == 0 and r["unknown_items"] == 2 and r["unquantified_items"] == 1
    assert "Probabilities are not independently evidenced" in r["selected_basis"] and "Rick Jones approved 4.0%" in r["selected_basis"]
    assert next(c for c in e["commercial"] if c["ref"] == "CA16")["method"] == "Management Reserve"


@needs_private
def test_selected_reserve_drives_ca16_once_and_commercial_edit_is_blocked():
    m = load_master_workbook(PRIVATE)
    base = compute_estimate(m)["summary"]["all_in"]
    m2, ch = apply_edits(m, [{"target": "reserve", "key": "block", "field": "selected", "value": "20000"}])
    e2 = compute_estimate(m2)
    assert e2["summary"]["management_reserve"] == 20000 and e2["summary"]["all_in"] > base
    assert abs((e2["summary"]["all_in"] - base) - (20000 - 18269.0625917) * 1.1 / 0.85) < 0.01
    assert [(c["target"], c["field"]) for c in ch if c["target"] == "reserve"] == [("reserve", "selected")]
    with pytest.raises(EditError, match="Management Reserve page"):
        apply_edits(m, [{"target": "commercial", "key": "CA16", "field": "pc_sum", "value": "1"}])
    # switching the adjudication off keeps the selected amount as a plain fixed line: total unchanged
    m3, _ = apply_edits(m2, [{"target": "reserve", "op": "delete", "key": "setup"}])
    e3 = compute_estimate(m3)
    assert m3.management_reserve is None and e3["management_reserve"] is None and abs(e3["summary"]["all_in"] - e2["summary"]["all_in"]) < 0.005
    m4, _ = apply_edits(m3, [{"target": "reserve", "op": "add", "key": "setup"}])
    assert m4.management_reserve["selected"] == "20000"


@needs_private
def test_items_flow_through_edit_save_and_range_check():
    m = load_master_workbook(PRIVATE)
    edits = [{"target": "reserve_item", "op": "add", "key": "M-it000001", "value": {"title": "Rev17 vs Yodha earthworks", "impact": "28600", "probability_low": "0.55",
                                                                                    "probability_high": "0.65", "exposure_ref": "RT01-001"}},
             {"target": "reserve_item", "op": "add", "key": "M-it000002", "value": {"title": "Ramp ownership", "impact": "9500", "probability_low": "0.3", "probability_high": "0.4"}},
             {"target": "reserve", "key": "block", "field": "selected", "value": "17000"}]
    m2, ch = apply_edits(m, edits)
    r = compute_estimate(m2)["management_reserve"]
    assert [i["ref"] for i in r["items"]][-2:] == ["MR-05", "MR-06"]
    assert abs(r["weighted_low_sell"] - 18580) < 0.01 and abs(r["weighted_high_sell"] - 22390) < 0.01 and r["position"] == "within"
    assert any(c["target"] == "reserve_item" and c["field"] == "added" for c in ch)
    back = from_json(to_json(m2))
    assert back.management_reserve == m2.management_reserve
    # an item linked to a Risk Truth exposure that has a positive provision is not counted twice
    prov = [{"target": "exposure", "op": "add", "key": "X-pr000001", "value": {"ref": "RT01-777", "risk_id": "RT01", "consequence": "p", "mode": "Fixed Allowance", "provision": "5000",
                                                                       "include": "Yes", "distinct": "Yes", "target": "CA02", "evidence": "AMBER", "integration_complete": "Yes"}},
            {"target": "reserve_item", "key": "M-it000001", "field": "exposure_ref", "value": "RT01-777"}]
    r3 = compute_estimate(apply_edits(m2, prov)[0])["management_reserve"]
    assert r3["items"][0]["counted"] is False and r3["status"] == "RED" and abs(r3["weighted_high_sell"] - 3800) < 0.01
    # old saved inputs without the block still load
    d = to_json(m); d.pop("management_reserve"); assert from_json(d).management_reserve is None


@needs_private
def test_supplying_probabilities_to_the_workbook_items_gives_the_policy_range():
    """Rick's policy example ranges (55-65% earthworks, 30-40% ramp/stairs) applied to the imported workbook items give the policy's $18.6k-$22.4k."""
    m = load_master_workbook(PRIVATE)
    ed = []
    for iid, lo, hi in (("M-wb0001", "0.55", "0.65"), ("M-wb0002", "0.3", "0.4")):
        ed += [{"target": "reserve_item", "key": iid, "field": "probability_low", "value": lo}, {"target": "reserve_item", "key": iid, "field": "probability_high", "value": hi},
               {"target": "reserve_item", "key": iid, "field": "prob_status", "value": "AMBER"}]
    r = compute_estimate(apply_edits(m, ed)[0])["management_reserve"]
    assert abs(r["weighted_low_sell"] - 18580) < 0.01 and abs(r["weighted_high_sell"] - 22390) < 0.01 and abs(r["weighted_mid_sell"] - 20485) < 0.01
    assert r["position"] == "above" and r["unknown_items"] == 0 and r["unquantified_items"] == 1
