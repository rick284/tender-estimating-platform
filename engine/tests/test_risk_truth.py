"""Risk Truth engine vs the approved Master Estimate Workbook's own Risk Truth formulas (golden fixture recalculated in LibreOffice),
plus the platform's deliberate differences and the real Hobsonville Rev34E data."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from tender_engine import risk_truth as rt

GOLD = json.loads((Path(__file__).parent / "golden_risk_truth.json").read_text())["scenarios"]
FIELDS = {f: "" for f in rt.FIELDS}


def items_of(sc):
    out = []
    for i, it in enumerate(sc["items"]):
        d = {"id": f"X-{i:04d}", **FIELDS, **{k: ("" if v is None else str(v)) for k, v in it.items()}}
        out.append(d)
    return out


@pytest.mark.parametrize("i", range(len(GOLD)))
def test_matches_workbook(i):
    sc = GOLD[i]; exp = sc["expected"]
    res = rt.compute(items_of(sc), [{"rag": r} for r in sc["risk_rags"]], programme_ok=exp["programme_gate"] == "OK")
    for j, (o, e) in enumerate(zip(res["exposures"], exp["rows"])):
        label = f"scenario {i} row {j}: {sc['items'][j]}"
        em = e["modelled"]
        if em in (None, ""):
            assert o["modelled"] is None, label
        else:
            assert o["modelled"] == Decimal(str(em)), label
        assert o["addition"] == Decimal(str(e["addition"] or 0)), label
        assert o["duplication"] == e["duplication"], label
        assert o["workbook_status"] == e["status"], label
    assert res["ca01"] == Decimal(str(exp["ca01"] or 0)) and res["ca02"] == Decimal(str(exp["ca02"] or 0))
    assert res["red_risks"] == exp["red_risks"] and res["red_exposures_workbook"] == exp["red_exposures"]
    assert res["duplicate_gate"] == exp["duplicate_gate"]
    assert res["gate_workbook"] == exp["gate"]


def test_golden_covers_the_interesting_cases():
    rows = [(it, e) for sc in GOLD for it, e in zip(sc["items"], sc["expected"]["rows"])]
    assert len(rows) > 150
    assert {e["duplication"] for _, e in rows} >= {"OK", "RED - RESIDUAL NOT DISTINCT", "RED - UNDECLARED OVERLAP", "DECLARED OVERLAP"}
    assert {e["status"] for _, e in rows} == {"RED", "AMBER", "GREEN"}
    assert {sc["expected"]["gate"] for sc in GOLD} == {"PASS", "HOLD - RED ITEMS / INTEGRATION CHECK"}
    assert any(sc["expected"]["ca01"] for sc in GOLD) and any(sc["expected"]["ca02"] for sc in GOLD)


def item(**kw):
    d = {"id": "X-0001", **FIELDS, "include": "No", "evidence": "GREEN", "mode": "Already in Base / No Add", **kw}
    return d


def test_platform_differences_from_the_workbook():
    # 1. blank evidence status is RED here (the workbook passes it as GREEN)
    r = rt.compute([item(evidence="")])["exposures"][0]
    assert r["status"] == "RED" and r["workbook_status"] == "GREEN" and "No evidence status recorded" in r["reasons"]
    # 2. a positive provision aimed at something other than CA01/CA02 would be silently dropped by the workbook: RED here
    r = rt.compute([item(mode="Fixed Allowance", provision="1000", include="Yes", distinct="Yes", target="PV01 direct QS", integration_complete="Yes")])
    assert r["exposures"][0]["status"] == "RED" and r["ca01"] == 0 and r["ca02"] == 0
    # 3. a positive provision not marked integration-complete holds the platform gate but not the workbook gate
    r = rt.compute([item(mode="Fixed Allowance", provision="1000", include="Yes", distinct="Yes", target="CA02")])
    assert r["ca02"] == 1000 and r["gate_workbook"] == "PASS" and r["gate"].startswith("HOLD") and r["issues"]
    r = rt.compute([item(mode="Fixed Allowance", provision="1000", include="Yes", distinct="Yes", target="CA02", integration_complete="Yes")])
    assert r["gate"] == "PASS" and r["ca02"] == Decimal(1000)


def test_validation():
    it = rt.build_item("X-abc123", {"risk_id": "RT05", "consequence": "Allproof quantity", "mode": "Probability x Impact", "probability": "0.6", "unit_rate": "9500"}, [])
    assert it["ref"] == "RT05-001" and it["include"] == "No"
    assert rt.build_item("X-abc124", {"risk_id": "RT05", "consequence": "again"}, [it])["ref"] == "RT05-002"
    for field, bad in (("probability", "60"), ("probability", "-0.1"), ("provision", "-5"), ("provision", "abc"), ("mode", "Guess"), ("owner", "Boss"),
                       ("include", "Maybe"), ("evidence", "PINK")):
        with pytest.raises(rt.RiskTruthError):
            rt.set_field(dict(it), field, bad)
    with pytest.raises(rt.RiskTruthError):
        rt.build_item("X-abc125", {"risk_id": "RT05"}, [])
    assert rt.compute([it])["exposures"][0]["modelled"] == Decimal("5700.0")        # modelled, but NOT added: include is No
    assert rt.compute([it])["ca02"] == 0


# ---- real Hobsonville Rev34E + editing + the CA01/CA02 feed -------------------------------------------------------------------------------
from tender_engine.edits import EditError, apply_edits  # noqa: E402
from tender_engine.estimate import compute_estimate  # noqa: E402
from tender_engine.importers import load_master_workbook  # noqa: E402
from tender_engine.inputs import from_json, to_json  # noqa: E402

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"
needs_private = pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")


@pytest.fixture(scope="module")
def hob():
    return load_master_workbook(PRIVATE)


@needs_private
def test_hobsonville_risk_truth_import_and_gate(hob):
    assert [x["ref"] for x in hob.risk_truth][:3] == ["RT01-001", "RT02-001", "RT03-001"] and len(hob.risk_truth) == 15
    # row RT01-001 is shifted one column right in the workbook; the importer still reads mode / quantity / evidence correctly
    x = next(x for x in hob.risk_truth if x["ref"] == "RT01-001")
    assert x["mode"] == "RFI Hold" and x["qty"] == "274" and x["unit"] == "m3" and x["evidence"] == "RED" and x["cost_ref"] == "EW08/EW09/EW10"
    est = compute_estimate(hob)
    r = est["risk_truth"]
    # the workbook's own gate cell counts 3 RED exposures (the shifted RT01-001 row is missed); the platform counts all 4
    assert r["red_risks"] == 4 and r["red_exposures"] == 4 and r["amber_exposures"] == 11 and r["gate"].startswith("HOLD")
    assert r["ca01"] == 0 and r["ca02"] == 0 and r["duplicate_gate"] == "OK"
    assert [e["status"] for e in r["exposures"] if e["status"] == "RED"] == ["RED"] * 4
    # nothing changes in the tender: still the Rev34E all-in
    assert est["reconciled"] is True and abs(est["summary"]["all_in"] - 1226916.81) < 0.01


@needs_private
def test_provision_flows_to_ca02_and_totals_once(hob):
    base = compute_estimate(hob)
    sell = lambda e: e["summary"]["all_in"]
    add = {"target": "exposure", "op": "add", "key": "X-new00001", "value": {
        "risk_id": "RT05", "consequence": "Distinct residual after PCs", "mode": "Fixed Allowance", "provision": "10000", "include": "Yes", "distinct": "Yes",
        "target": "CA02", "evidence": "AMBER", "integration_complete": "Yes", "owner": "Primary", "cost_ref": "ZZ99"}}
    m2, ch = apply_edits(hob, [add])
    e2 = compute_estimate(m2)
    assert e2["risk_truth"]["ca02"] == 10000 and e2["risk_truth"]["ca01"] == 0
    ca02 = next(c for c in e2["commercial"] if c["ref"] == "CA02")
    assert ca02["amount"] == 10000
    assert sell(e2) > sell(base)                                   # overhead and margin are applied on top, exactly once
    assert [c["field"] for c in ch if c["target"] == "exposure"] == ["added"]
    # not distinct -> RED, still counted in the tender figure but blocks the gate (workbook behaviour: the amount flows, the gate holds)
    m3, _ = apply_edits(hob, [add, {"target": "exposure", "key": "X-new00001", "field": "distinct", "value": "No"}])
    r3 = compute_estimate(m3)["risk_truth"]
    assert r3["duplicate_gate"] == "RED" and r3["gate"].startswith("HOLD")
    # removing it again returns to the original total
    m4, _ = apply_edits(m2, [{"target": "exposure", "op": "delete", "key": "X-new00001"}])
    assert abs(sell(compute_estimate(m4)) - sell(base)) < 0.005


@needs_private
def test_exposure_edit_validation_and_round_trip(hob):
    with pytest.raises(EditError):
        apply_edits(hob, [{"target": "exposure", "key": "X-RT01001", "field": "probability", "value": "60"}])
    with pytest.raises(EditError):
        apply_edits(hob, [{"target": "exposure", "key": "X-nope", "field": "mode", "value": "Fixed Allowance"}])
    with pytest.raises(EditError):
        apply_edits(hob, [{"target": "exposure", "op": "add", "key": "bad id", "value": {"consequence": "x"}}])
    m2, ch = apply_edits(hob, [{"target": "exposure", "key": "X-RT03001", "field": "evidence", "value": "green"}])
    assert next(x for x in m2.risk_truth if x["id"] == "X-RT03001")["evidence"] == "GREEN"
    assert [(c["target"], c["field"], c["before"], c["after"]) for c in ch if c["target"] == "exposure"] == [("exposure", "evidence", "AMBER", "GREEN")]
    back = from_json(to_json(m2))
    assert back.risk_truth == m2.risk_truth and compute_estimate(back)["risk_truth"]["amber_exposures"] == 10
    # a tender whose saved inputs predate Risk Truth still loads
    d = to_json(hob); d.pop("risk_truth"); assert from_json(d).risk_truth == []
