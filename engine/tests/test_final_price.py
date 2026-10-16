"""The all-in package price must carry the same overhead / profit / bond / finance choices as the own-works tender (found by an independent
review: fixed or markup choices were ignored once the package was consolidated). Small-number oracles, worked by hand."""
from decimal import Decimal
import itertools
import pytest
from tender_engine import D, cents, CommercialInput, Overlay, compute_tender, compute_consolidated
from tender_engine.commercial import package_sell_line
from tender_engine.schedule import compute_schedule


def stack(oh=("Markup %", "Yes", "0.10", "0"), pr=("Margin %", "Yes", "0.15", "0"), bonds=None, fin=None):
    out = [CommercialInput("CA17", "Overhead", oh[0], oh[1], D(oh[2]), D(oh[3])),
           CommercialInput("CA18", "Profit", pr[0], pr[1], D(pr[2]), D(pr[3]))]
    if bonds:
        out.append(CommercialInput("CA19", "Bonds", bonds[0], "Yes", D(bonds[1]), D(bonds[2])))
    if fin:
        out.append(CommercialInput("CA20", "Retention finance", fin[0], "Yes", D(fin[1]), D(fin[2])))
    return out


OVERLAYS = [Overlay("Sub A", D(100))]


def test_fixed_amounts_are_not_scaled_or_replaced_by_rates():
    t = compute_tender(D(200), stack(("Fixed Amount", "Yes", "0", "30"), ("Fixed Amount", "Yes", "0", "40")))
    c = compute_consolidated(t.subtotal, [], D(0), commercial=stack(("Fixed Amount", "Yes", "0", "30"), ("Fixed Amount", "Yes", "0", "40")))
    assert t.tender_excl_gst == D(270) and c.all_in_tender == D(270)          # the review's example P01: was 258.82


def test_profit_markup_basis_is_respected_in_the_all_in():
    com = stack(pr=("Markup %", "Yes", "0.15", "0"))
    t = compute_tender(D(200), com)
    c = compute_consolidated(t.subtotal, [], D(0), commercial=com)
    assert t.tender_excl_gst == D(253) and c.all_in_tender == D(253)           # the review's example P02: was 258.82


def test_with_overlays_the_package_carries_the_chosen_basis():
    c = compute_consolidated(D(200), OVERLAYS, D(0), commercial=stack(("Fixed Amount", "Yes", "0", "30"), ("Fixed Amount", "Yes", "0", "40")))
    assert c.all_in_tender == D(370)                                           # 300 cost + 30 + 40, nothing scaled
    c = compute_consolidated(D(200), OVERLAYS, D(0), commercial=stack(pr=("Markup %", "Yes", "0.15", "0")))
    assert c.all_in_tender == D("379.5")                                       # 300 + 30 overhead, then 15% of 330
    c = compute_consolidated(D(200), OVERLAYS, D(0), commercial=stack())
    assert cents(c.all_in_tender) == cents(D(330) / D("0.85"))                 # unchanged Hobsonville method
    c = compute_consolidated(D(200), OVERLAYS, D(0), commercial=stack(("Markup %", "No", "0.10", "0"), ("Markup %", "Yes", "0.10", "0")))
    assert c.all_in_tender == D(330)                                           # overhead switched off is off in the package too


def test_bonds_and_finance_reach_the_package():
    com = stack(pr=("Markup %", "Yes", "0.10", "0"), bonds=("%", "0.02", "0"), fin=("PC Sum", "0", "5"))
    t = compute_tender(D(200), com)
    assert t.tender_excl_gst == D("1.1") * (D(200) + 20 + 4 + 5)
    c = compute_consolidated(D(200), [], D(0), commercial=com)
    assert c.all_in_tender == t.tender_excl_gst
    c2 = compute_consolidated(D(200), OVERLAYS, D(0), commercial=com)          # percentages follow the bigger base, the fixed finance sum does not
    assert c2.all_in_tender == D("1.1") * (D(300) + 30 + 6 + 5)


@pytest.mark.parametrize("oh,pr", list(itertools.product(
    [("Markup %", "Yes", "0.10", "0"), ("Fixed Amount", "Yes", "0", "30"), ("Markup %", "No", "0.10", "0")],
    [("Margin %", "Yes", "0.15", "0"), ("Markup %", "Yes", "0.15", "0"), ("Fixed Amount", "Yes", "0", "40"), ("Margin %", "No", "0.15", "0")])))
def test_no_overlays_all_in_equals_own_works_tender_for_every_combination(oh, pr):
    com = stack(oh, pr)
    t = compute_tender(D(200), com)
    assert compute_consolidated(t.subtotal, [], D(0), commercial=com).all_in_tender == t.tender_excl_gst


@pytest.mark.parametrize("oh,pr", list(itertools.product(
    [("Markup %", "Yes", "0.10", "0"), ("Fixed Amount", "Yes", "0", "30")],
    [("Margin %", "Yes", "0.15", "0"), ("Markup %", "Yes", "0.15", "0"), ("Fixed Amount", "Yes", "0", "40")])))
def test_client_schedule_groups_add_up_to_the_all_in_for_every_basis(oh, pr):
    com = stack(oh, pr)
    by = {c.ref: c for c in com}
    cons = compute_consolidated(D(200), OVERLAYS, D(0), commercial=com)
    sched = {"name": "S", "client": "", "groups": [
        {"id": "g1", "name": "Own", "code": "", "lines": [{"ref": "1", "trade": "Works", "kind": "work"}, {"ref": "2", "trade": "Margin", "kind": "margin"}]},
        {"id": "g2", "name": "Sub", "code": "", "lines": [{"ref": "3", "trade": "Sub A", "kind": "work"}, {"ref": "4", "trade": "Margin", "kind": "margin"}]}],
        "map": {"qs:A": "line:1", "overlay:Sub A": "line:3"}}
    sources = [{"key": "qs:A", "label": "A", "amount": D(200), "own": True}, {"key": "overlay:Sub A", "label": "Sub A", "amount": D(100), "own": False}]
    r = compute_schedule(sched, sources, None, None, cons.all_in_tender, line=package_sell_line(by))
    assert r["reconciles"], r["problems"]
    assert abs(sum(g["total"] for g in r["groups"]) - cents(cons.all_in_tender)) < D("0.011")


def test_whole_estimate_follows_the_chosen_basis_and_reports_say_so():
    """End to end on the Hobsonville workbook: fixed overhead and profit amounts set on the Commercial page reach the all-in and the PDF wording."""
    from pathlib import Path
    from tender_engine.edits import apply_edits
    from tender_engine.estimate import compute_estimate
    from tender_engine.importers import load_master_workbook
    p = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"
    if not p.exists():
        pytest.skip("private workbook not present")
    base = load_master_workbook(p)
    m, _ = apply_edits(base, [{"target": "commercial", "key": "CA17", "field": "method", "value": "Fixed Amount"},
                              {"target": "commercial", "key": "CA17", "field": "pc_sum", "value": "30000"},
                              {"target": "commercial", "key": "CA18", "field": "method", "value": "Fixed Amount"},
                              {"target": "commercial", "key": "CA18", "field": "pc_sum", "value": "40000"}])
    e = compute_estimate(m)
    c = e["consolidated"]
    assert abs(c["all_in"] - (c["gross_known_package"] + 70000)) < 0.005          # package cost + the two fixed amounts, nothing scaled
    assert c["overhead_basis"] == "fixed amount $30,000.00" and c["profit_basis"] == "fixed amount $40,000.00"
    assert e["schedule"]["reconciles"]
