"""Golden test: the engine, fed only the INPUTS of the Hobsonville Rev34E workbook, must reproduce
the workbook's calculated results to the cent. Requires private/Rev34E.xlsx (not committed)."""
from decimal import Decimal
import pytest

from tender_engine import (compute_buildup, compute_qs, compute_tender, compute_weather,
                           compute_consolidated, cents, D, WeatherInputs, CommercialInput)
from workbook_import import build_commercial

TOL = Decimal("0.005")   # half a cent


def close(a, b, tol=TOL):
    return abs(D(a) - D(b)) <= tol


@pytest.fixture(scope="module")
def run(rev34e):
    d = rev34e
    rows = compute_buildup(d["rows"], {q.code: q for q in d["qs"]}, d["library"])
    qs = compute_qs(d["qs"], rows)
    by_excel = dict(zip(d["excel_rows"], rows))
    wi = WeatherInputs(
        daily_prelims=by_excel[22].applied_rate * 8,
        weekly_hire=by_excel[48].applied_rate + by_excel[49].applied_rate,
        recovery_allowance=d["recovery"],
    )
    weather = compute_weather(rows, d["tool"], wi)
    commercial = []
    for c in d["commercial"]:
        ev = weather.allowance if c["ref"] == "CA10" else d["risk_feed"].get(c["ref"], D(0))
        commercial.append(CommercialInput(c["ref"], c["name"], c["method"], c["include"], c["pct"], c["pc_sum"], ev))
    tender = compute_tender(qs.total_direct, commercial)
    comm = {c.ref: c for c in commercial}
    cons = compute_consolidated(tender.subtotal, d["overlays"], d["overlap"],
                                comm["CA17"].pct, comm["CA18"].pct)
    return dict(d=d, rows=rows, qs=qs, weather=weather, tender=tender, cons=cons, by_excel=by_excel)


def test_every_buildup_row_matches_workbook(run):
    d, ws = run["d"], run["d"]["cached"]["Resource Build-Up"]
    bad = []
    for r, res in run["by_excel"].items():
        cached = {"id": ws[f"A{r}"].value, "applied_hrs": ws[f"M{r}"].value, "rate": ws[f"Y{r}"].value,
                  "cost": ws[f"Z{r}"].value, "exposed": ws[f"AN{r}"].value, "flag": ws[f"AI{r}"].value}
        if res.row_id != cached["id"]:
            bad.append((r, "id", res.row_id, cached["id"]))
        if not close(res.applied_duration_hrs, cached["applied_hrs"] or 0, Decimal("0.000001")):
            bad.append((r, "hrs", res.applied_duration_hrs, cached["applied_hrs"]))
        if not close(res.applied_rate, cached["rate"], Decimal("0.000001")):
            bad.append((r, "rate", res.applied_rate, cached["rate"]))
        if not close(res.cost, cached["cost"], Decimal("0.000001")):
            bad.append((r, "cost", res.cost, cached["cost"]))
        if not close(res.weather_exposed_cost, cached["exposed"] or 0, Decimal("0.000001")):
            bad.append((r, "exposed", res.weather_exposed_cost, cached["exposed"]))
    assert not bad, bad[:10]
    assert len(run["by_excel"]) == 64


# Finding (not a calculation difference): in Rev34E the QA column (AI) is partly hand-typed and two
# formula cells hold cached text that contradicts their own formula. The engine derives the flag from
# the rules; these are the only rows where it differs from the workbook's displayed text.
KNOWN_QA_DISPLAY_DIFFERENCES = {21, 26, 33, 41, 42, 44, 45, 46, 47}
BLOCKING = {"RESOURCE CODE", "RATE MISSING", "OPERATOR DOUBLE-COUNT", "FUEL DOUBLE-COUNT"}


def test_qa_flags_derived_and_known_differences(run):
    ws = run["d"]["cached"]["Resource Build-Up"]
    diff = {r for r, res in run["by_excel"].items() if res.qa_flag != ws[f"AI{r}"].value}
    assert diff == KNOWN_QA_DISPLAY_DIFFERENCES
    assert not any(res.qa_flag in BLOCKING for res in run["rows"]), "no blocking QA flags expected"
    # rows shown OK in the workbook but not marked Verified are surfaced as VERIFY by the engine
    assert {r for r, res in run["by_excel"].items() if res.qa_flag == "VERIFY" and ws[f"AI{r}"].value == "OK"} >= {21, 44, 45}


def test_qs_item_amounts_and_total(run):
    ws = run["d"]["cached"]["QS Takeoff"]
    amounts = {ws.cell(r, 2).value: ws.cell(r, 7).value for r in range(3, 41) if ws.cell(r, 2).value}
    for line in run["qs"].lines:
        assert close(line.amount, amounts[line.code], Decimal("0.000001")), line.code
    assert cents(run["qs"].total_direct) == Decimal("435521.88")
    assert run["qs"].orphan_cost == 0


def test_section_totals_match_tender_buildup(run):
    expected = {
        "Preliminaries & General": "48403.40", "Erosion & Sediment Control": "7750.14",
        "Earthworks": "116065.18", "Pavements & Concrete": "119034.31",
        "Kerbs, Channels & External Sitework": "65000.00", "Retaining Walls": "71668.84",
        "Testing, As-Builts & Compliance": "4600.00", "Reinstatement & Handover": "3000.00",
    }
    got = {k: cents(v) for k, v in run["qs"].section_totals.items()}
    assert got == {k: Decimal(v) for k, v in expected.items()}


def test_weather_allowance_ca10(run):
    w = run["weather"]
    assert cents(w.exposed_pool) == Decimal("54070.63")
    assert cents(w.direct_productivity) == Decimal("12458.56")
    assert cents(w.critical_path_prelims) == Decimal("5156.13")
    assert cents(w.billed_hire) == Decimal("590.00")
    assert cents(w.allowance) == Decimal("18204.69")
    cached = run["d"]["cached"]["Weather Risk"]["B38"].value
    assert close(w.allowance, cached, Decimal("0.000001"))


def test_tender_build_up_chain(run):
    t = run["tender"]
    assert cents(t.base_direct) == Decimal("435521.88")
    assert cents(t.additions["CA09"]) == Decimal("3000.00")
    assert cents(t.additions["CA10"]) == Decimal("18204.69")
    assert cents(t.additions["CA16"]) == Decimal("18269.06")
    assert cents(t.pre_margin_total) == Decimal("39473.75")
    assert cents(t.subtotal) == Decimal("474995.63")
    assert cents(t.overhead) == Decimal("47499.56")
    assert cents(t.profit) == Decimal("92205.03")
    assert cents(t.tender_excl_gst) == Decimal("614700.22")
    assert t.gst == 0


def test_tender_matches_every_cached_cell(run):
    ws = run["d"]["cached"]["Tender Build-Up"]
    t = run["tender"]
    pairs = {"B20": t.base_direct, "B39": t.pre_margin_total, "B40": t.subtotal, "B42": t.overhead,
             "B43": t.profit, "B46": t.commercial_total, "B47": t.tender_excl_gst}
    for cell, val in pairs.items():
        assert close(val, ws[cell].value, Decimal("0.000001")), cell


def test_consolidated_package_and_margin(run):
    c = run["cons"]
    assert cents(c.overlays_total) == Decimal("473076.45")        # Coast 210,606.00 + Allied 262,470.45
    assert cents(c.gross_known_package) == Decimal("948072.08")
    assert cents(c.overhead) == Decimal("94807.21")
    assert cents(c.profit) == Decimal("184037.52")
    assert cents(c.all_in_tender) == Decimal("1226916.81")
    assert round(c.gross_margin_on_sell * 100, 2) == Decimal("22.73")
    cached = run["d"]["cached"]["Consolidated Package"]
    assert close(c.all_in_tender, cached["F56"].value, Decimal("0.000001"))
    assert close(c.gross_known_package, cached["B12"].value, Decimal("0.000001"))


def test_allied_allocation_reconciles(run):
    """Allied public + private must equal the workbook's combined known total (source of truth)."""
    cp = run["d"]["cached"]["Consolidated Package"]
    allied = sum((o.amount for o in run["d"]["overlays"] if o.name.startswith("Allied")), D(0))
    assert cents(allied) == cents(cp["B11"].value) == Decimal("262470.45")


def test_management_reserve_is_fixed_not_default(run):
    ci = run["d"]["cached"]["Commercial Inputs"]
    reserve = D(ci["E20"].value)
    base = D(ci["B34"].value)
    assert cents(reserve) == Decimal("18269.06")
    assert close(base * Decimal("0.04"), reserve, Decimal("0.000001"))
