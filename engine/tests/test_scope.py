from pathlib import Path

import pytest

from tender_engine import scope as sc
from tender_engine.edits import EditError, apply_edits
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"
needs_private = pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")

COSTS = {"EW01": 1000, "EW02": 0, "PV01": 5000, "CA09": 3000}
REG = [{"ref": "A1", "kind": "assumption", "status": ""}, {"ref": "EX-01", "kind": "exclusion", "status": ""}, {"ref": "RFI-01", "kind": "rfi", "status": "OPEN"},
       {"ref": "RFI-02", "kind": "rfi", "status": "CLOSED"}]


def item(**kw):
    base = {"id": "C-aaaaaa", **{f: "" for f in sc.FIELDS}, "ref": "SC-001", "title": "x"}
    base.update(kw)
    return base


def status(**kw):
    out = sc.compute([item(**kw)], COSTS, REG, {"Q-01"})
    return out["items"][0]["status"], out["items"][0]["problems"]


def test_each_treatment_must_be_backed_up():
    assert status(owner="OWN WORKS", treatment="PRICED", cost_refs="EW01")[0] == "COMPLETE"
    s, p = status(owner="OWN WORKS", treatment="PRICED", cost_refs="")
    assert s == "MISSING" and "no QS item" in p[0]
    s, p = status(owner="OWN WORKS", treatment="PRICED", cost_refs="EW02")
    assert s == "CHECK" and "carries no cost" in p[0]
    s, p = status(owner="OWN WORKS", treatment="PRICED", cost_refs="ZZ99")
    assert s == "CHECK" and "isn't in the estimate" in p[0]
    assert status(owner="OWN WORKS", treatment="ALLOWANCE", cost_refs="CA09", basis="Rate x days", register_refs="A1")[0] == "COMPLETE"
    assert status(owner="OWN WORKS", treatment="PC SUM", cost_refs="CA09")[0] == "CHECK"              # no basis, no assumption
    assert status(owner="OTHERS", treatment="EXCLUDED", register_refs="EX-01")[0] == "COMPLETE"
    assert status(owner="OTHERS", treatment="EXCLUDED", register_refs="EX-01", cost_refs="PV01")[0] == "CHECK"   # excluded but priced
    assert status(owner="OTHERS", treatment="BY OTHERS", register_refs="A1")[0] == "COMPLETE"
    assert status(owner="OWN WORKS", treatment="BY OTHERS", register_refs="A1")[0] == "CHECK"
    assert status(owner="TBC", treatment="UNRESOLVED", register_refs="RFI-01")[0] == "CHECK"           # waiting on an open RFI
    s, p = status(owner="OWN WORKS", treatment="UNRESOLVED")
    assert s == "MISSING" and "raise one" in p[0]
    assert status(owner="OWN WORKS", treatment="UNRESOLVED", register_refs="RFI-02")[1] == ["The RFI is closed: update the treatment."]
    assert status(owner="OWN WORKS", treatment="")[0] == "MISSING" and status(owner="", treatment="PRICED", cost_refs="EW01")[0] == "MISSING"
    s, p = status(owner="SUBCONTRACT", treatment="PRICED", cost_refs="EW01")
    assert s == "CHECK" and "no quote" in p[0]
    assert status(owner="SUBCONTRACT", treatment="PRICED", cost_refs="EW01", quote_refs="Q-01")[0] == "COMPLETE"
    assert status(owner="OWN WORKS", treatment="PRICED", cost_refs="EW01", register_refs="A9")[0] == "CHECK"   # a register reference that doesn't exist


def test_gate_counts_missing_items_and_priced_items_with_no_scope_home():
    assert sc.compute([], COSTS, REG, set())["gate"].startswith("NOT STARTED")
    ok = item(owner="OWN WORKS", treatment="PRICED", cost_refs="EW01")
    r = sc.compute([ok], COSTS, REG, set())
    assert r["gate"].startswith("HOLD") and r["unhomed_qs"] == ["PV01"]                                # PV01 is priced but nothing in the schedule covers it
    both = item(id="C-bbbbbb", ref="SC-002", owner="OWN WORKS", treatment="PRICED", cost_refs="PV01")
    r = sc.compute([ok, both], COSTS, REG, set())
    assert r["gate"].startswith("PASS") and r["counts"] == {"COMPLETE": 2, "CHECK": 0, "MISSING": 0, "total": 2}
    r = sc.compute([ok, both, item(id="C-cccccc", ref="SC-003")], COSTS, REG, set())
    assert r["gate"].startswith("HOLD") and r["counts"]["MISSING"] == 1


def test_fields_are_validated_and_normalised():
    it = sc.build_item("C-dddddd", {"title": "Silt fencing", "group": "enabling works", "owner": "own works", "treatment": "priced", "cost_refs": "esc01  ESC01, ew01"}, [])
    assert (it["group"], it["owner"], it["treatment"], it["cost_refs"], it["ref"]) == ("Enabling works", "OWN WORKS", "PRICED", "ESC01, EW01", "SC-001")
    with pytest.raises(sc.ScopeError):
        sc.set_field(it, "treatment", "MAYBE")
    with pytest.raises(sc.ScopeError):
        sc.set_field(it, "owner", "the client")
    with pytest.raises(sc.ScopeError):
        sc.build_item("C-eeeeee", {"detail": "no title"}, [])
    with pytest.raises(sc.ScopeError):
        sc.build_item("C-ffffff", {"title": "dup", "ref": "SC-001"}, [it])


@needs_private
def test_edits_add_set_delete_and_the_estimate_reports_coverage():
    base = load_master_workbook(PRIVATE)
    first = compute_estimate(base)["qs"][0]["code"]
    m, ch = apply_edits(base, [{"target": "scope", "key": "C-newone1", "op": "add", "value": {"title": "Site establishment", "group": "Access and site establishment", "owner": "OWN WORKS",
                                                                                                "treatment": "PRICED", "cost_refs": first}}])
    assert any(c["target"] == "scope" for c in ch) if ch and isinstance(ch[0], dict) and "target" in ch[0] else len(ch) >= 1
    est = compute_estimate(m)["scope"]
    assert est["counts"]["total"] == 1 and est["items"][0]["status"] == "COMPLETE" and est["gate"].startswith("HOLD")      # other priced items have no scope home yet
    m2, _ = apply_edits(m, [{"target": "scope", "key": "C-newone1", "field": "treatment", "value": "EXCLUDED"}])
    assert compute_estimate(m2)["scope"]["items"][0]["status"] == "CHECK"                                                  # excluded but a cost is linked
    m3, _ = apply_edits(m2, [{"target": "scope", "key": "C-newone1", "op": "delete"}])
    assert compute_estimate(m3)["scope"]["counts"]["total"] == 0
    with pytest.raises(EditError):
        apply_edits(base, [{"target": "scope", "key": "C-newone1", "field": "treatment", "value": "PRICED"}])               # unknown item
    with pytest.raises(EditError):
        apply_edits(base, [{"target": "scope", "key": "bad id", "op": "add", "value": {"title": "x"}}])
