import json
from decimal import Decimal
from pathlib import Path
import pytest

from tender_engine import D, cents
from tender_engine.edits import EditError, apply_edits, row_ids
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook
from tender_engine.inputs import from_json, to_json

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"
needs_private = pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")


@pytest.fixture(scope="module")
def base():
    return load_master_workbook(PRIVATE)


# ---------------------------------------------------------------- serialisation
@needs_private
def test_json_roundtrip_recomputes_identically(base):
    a = compute_estimate(base)
    blob = json.loads(json.dumps(to_json(base)))               # through real JSON text
    b = compute_estimate(from_json(blob))
    assert a == b                                              # every figure, flag and string identical
    assert b["reconciled"] is True and b["edited"] is False


# ---------------------------------------------------------------- editing
@needs_private
def test_no_edits_changes_nothing_but_drops_reconciliation(base):
    m, ch = apply_edits(base, [])
    assert ch == []
    e0, e1 = compute_estimate(base), compute_estimate(m)
    assert e1["summary"] == e0["summary"] and e1["edited"] is True and e1["reconciled"] is None and e1["reconciliation"] == []


@needs_private
def test_quantity_edit_flows_to_every_total(base):
    m, ch = apply_edits(base, [{"target": "qs", "key": "EW01", "field": "quantity", "value": "3000"}])
    assert len(ch) == 1 and ch[0]["before"] == "2105" and ch[0]["after"] == "3000"
    e0, e1 = compute_estimate(base), compute_estimate(m)
    q0 = next(q for q in e0["qs"] if q["code"] == "EW01"); q1 = next(q for q in e1["qs"] if q["code"] == "EW01")
    assert q1["amount"] > q0["amount"]
    # EW01 is a Time x Count item: cost scales with quantity (hours = qty / productivity)
    assert round(q1["amount"] / q0["amount"], 6) == round(3000 / 2105, 6)
    assert e1["summary"]["all_in"] > e0["summary"]["all_in"]
    # base direct moved by exactly the EW01 movement
    assert round(e1["tender"]["base_direct"] - e0["tender"]["base_direct"], 2) == round(q1["amount"] - q0["amount"], 2)


@needs_private
def test_rate_override_and_revert_is_exact(base):
    e0 = compute_estimate(base)
    m, ch = apply_edits(base, [{"target": "row", "key": "EW02-001", "field": "job_rate_override", "value": 175}])
    assert [c["field"] for c in ch] == ["job_rate_override"]
    e1 = compute_estimate(m)
    r = next(x for x in e1["buildup"] if x["row_id"] == "EW02-001")
    assert r["applied_rate"] == 175.0 and r["job_override"] == 175.0
    # editing it back (to blank) restores the original numbers and reports no net change
    m2, ch2 = apply_edits(base, [{"target": "row", "key": "EW02-001", "field": "job_rate_override", "value": 175},
                                 {"target": "row", "key": "EW02-001", "field": "job_rate_override", "value": ""}])
    assert ch2 == []
    assert compute_estimate(m2)["summary"] == e0["summary"]


@needs_private
def test_commercial_edits_and_true_margin(base):
    m, ch = apply_edits(base, [{"target": "commercial", "key": "CA18", "field": "pct", "value": "0.2"},
                               {"target": "commercial", "key": "CA17", "field": "pct", "value": "0.05"}])
    e = compute_estimate(m)
    t = e["tender"]
    assert cents(D(t["overhead"])) == cents(D(t["subtotal"]) * D("0.05"))
    assert round(t["profit"] / t["total_excl_gst"], 4) == 0.2          # true margin: share of SELL
    assert e["consolidated"]["margin"] == 0.2 and e["consolidated"]["overhead_rate"] == 0.05


@needs_private
def test_switching_a_provision_on_and_overlay_edit(base):
    m, ch = apply_edits(base, [{"target": "commercial", "key": "CA03", "field": "include", "value": "Yes"},
                               {"target": "commercial", "key": "CA03", "field": "pct", "value": "0.02"},
                               {"target": "overlay", "key": "Coast Concrete foundation / floor", "field": "amount", "value": 220000}])
    e0, e1 = compute_estimate(base), compute_estimate(m)
    ca03 = next(c for c in e1["commercial"] if c["ref"] == "CA03")
    assert ca03["include"] and round(ca03["amount"], 2) == round(e0["tender"]["base_direct"] * 0.02, 2)
    assert round(e1["consolidated"]["overlays_total"] - e0["consolidated"]["overlays_total"], 2) == 220000 - 210606


@needs_private
def test_a_provision_can_be_switched_between_percentage_and_pc_sum(base):
    """CA09 comes from the workbook as a PC Sum. Switching it to a % of base direct, and CA03 (a %) to a PC Sum, both price correctly."""
    m, ch = apply_edits(base, [{"target": "commercial", "key": "CA09", "field": "method", "value": "%"},
                               {"target": "commercial", "key": "CA09", "field": "pct", "value": "0.01"},
                               {"target": "commercial", "key": "CA03", "field": "method", "value": "PC Sum"},
                               {"target": "commercial", "key": "CA03", "field": "include", "value": "Yes"},
                               {"target": "commercial", "key": "CA03", "field": "pc_sum", "value": 4000}])
    e0, e1 = compute_estimate(base), compute_estimate(m)
    by = {c["ref"]: c for c in e1["commercial"]}
    assert by["CA09"]["method"] == "%" and round(by["CA09"]["amount"], 2) == round(e0["tender"]["base_direct"] * 0.01, 2)
    assert by["CA03"]["method"] == "PC Sum" and by["CA03"]["amount"] == 4000
    assert any(c["field"] == "method" and c["key"] == "CA09" for c in ch)            # the change list says the basis changed
    # saved inputs keep the new basis
    from tender_engine import inputs
    again = inputs.from_json(inputs.to_json(m))
    assert next(c for c in again.commercial if c["ref"] == "CA09")["method"] == "%"


@needs_private
def test_risk_lines_can_be_set_by_hand_and_back_and_the_screen_is_told_what_the_engine_would_have_added(base):
    m, _ = apply_edits(base, [{"target": "commercial", "key": "CA01", "field": "method", "value": "PC Sum"},
                              {"target": "commercial", "key": "CA01", "field": "pc_sum", "value": 5000}])
    by = {c["ref"]: c for c in compute_estimate(m)["commercial"]}
    assert by["CA01"]["method"] == "PC Sum" and by["CA01"]["amount"] == 5000 and by["CA01"]["engine_value"] == 0   # Rev34E has no approved provisions
    back, _ = apply_edits(m, [{"target": "commercial", "key": "CA01", "field": "method", "value": "Risk Engine"}])
    assert next(c for c in compute_estimate(back)["commercial"] if c["ref"] == "CA01")["method"] == "Risk Engine"
    # with an approved provision on the risk register, a manual basis leaves it out of the price and says how much (engine_value)
    withrisk, _ = apply_edits(base, [{"target": "exposure", "op": "add", "key": "X-test01", "value": {"ref": "RT99-001", "mode": "Fixed Allowance", "baseline": "0", "residual": "1000", "provision": "1000", "include": "Yes", "distinct": "Yes", "target": "CA01", "evidence": "GREEN", "integration": "Yes", "description": "test"}}])
    e_engine = compute_estimate(withrisk)
    manual, _ = apply_edits(withrisk, [{"target": "commercial", "key": "CA01", "field": "method", "value": "PC Sum"}])
    e_manual = compute_estimate(manual)
    ca = lambda e: next(c for c in e["commercial"] if c["ref"] == "CA01")
    assert ca(e_engine)["amount"] == 1000 and ca(e_manual)["amount"] == 0 and ca(e_manual)["engine_value"] == 1000


@needs_private
@pytest.mark.parametrize("edit,msg", [
    ({"target": "commercial", "key": "CA10", "field": "method", "value": "PC Sum"}, "calculated by the platform"),     # weather engine line
    ({"target": "commercial", "key": "CA21", "field": "method", "value": "PC Sum"}, "calculated by the platform"),     # GST is a % only
    ({"target": "commercial", "key": "CA09", "field": "method", "value": "Markup %"}, "can be set to"),
    ({"target": "commercial", "key": "CA17", "field": "method", "value": "Margin %"}, "can be set to"),
])
def test_only_sensible_basis_changes_are_accepted(base, edit, msg):
    with pytest.raises(EditError, match=msg):
        apply_edits(base, [edit])


@needs_private
@pytest.mark.parametrize("edit,msg", [
    ({"target": "qs", "key": "NOPE", "field": "quantity", "value": 1}, "Unknown QS item"),
    ({"target": "qs", "key": "EW01", "field": "quantity", "value": -5}, "less than"),
    ({"target": "qs", "key": "EW01", "field": "quantity", "value": "abc"}, "must be a number"),
    ({"target": "qs", "key": "EW01", "field": "quantity", "value": "NaN"}, "must be a number"),
    ({"target": "qs", "key": "EW01", "field": "quantity", "value": "1e99"}, "too large"),
    ({"target": "qs", "key": "EW01", "field": "description", "value": "x"}, "Only the quantity"),
    ({"target": "row", "key": "ZZ-001", "field": "count", "value": 1}, "Unknown build-up row"),
    ({"target": "row", "key": "EW01-001", "field": "waste", "value": 10}, "fraction"),
    ({"target": "row", "key": "EW01-001", "field": "resource_code", "value": "X"}, "can't be edited"),
    ({"target": "commercial", "key": "CA18", "field": "pct", "value": 1}, "more than"),
    ({"target": "commercial", "key": "CA99", "field": "pct", "value": 1}, "Unknown commercial"),
    ({"target": "overlay", "key": "Coast Concrete foundation / floor", "field": "amount", "value": -1}, "less than"),
    ({"target": "bogus"}, "Unknown edit target"),
    ("not an object", "must be an object"),
])
def test_invalid_edits_rejected_with_plain_messages(base, edit, msg):
    with pytest.raises(EditError, match=msg):
        apply_edits(base, [edit])


@needs_private
def test_original_is_never_mutated(base):
    before = json.dumps(to_json(base), sort_keys=True)
    apply_edits(base, [{"target": "qs", "key": "EW01", "field": "quantity", "value": 1},
                       {"target": "commercial", "key": "CA17", "field": "pct", "value": 0.5},
                       {"target": "row", "key": "EW01-001", "field": "count", "value": 9}])
    assert json.dumps(to_json(base), sort_keys=True) == before


@needs_private
def test_edit_limit(base):
    with pytest.raises(EditError, match="Too many"):
        apply_edits(base, [{"target": "qs", "key": "EW01", "field": "quantity", "value": 1}] * 501)


@needs_private
def test_edited_estimate_survives_json_roundtrip(base):
    m, _ = apply_edits(base, [{"target": "qs", "key": "PV01", "field": "quantity", "value": 500}])
    a = compute_estimate(m)
    b = compute_estimate(from_json(json.loads(json.dumps(to_json(m)))))
    assert a == b and b["edited"] is True
