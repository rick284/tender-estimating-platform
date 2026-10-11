"""Fast unit tests with synthetic data (no private files)."""
from decimal import Decimal
import pytest
from tender_engine import (D, cents, LibraryRate, BuildUpRow, QSItem, CommercialInput, Overlay,
                           WeatherToolRun, WeatherInputs, compute_buildup, compute_qs, compute_tender,
                           compute_weather, compute_consolidated)
from tender_engine.buildup import BuildUpError

LIB = {
    "PL-EXC": LibraryRate("PL-EXC", "14 t excavator wet hire", "hr", D(150), operator_included="Yes"),
    "LAB-OP": LibraryRate("LAB-OP", "Excavator operator", "hr", D(60)),
    "LAB": LibraryRate("LAB", "Labourer", "hr", D(38)),
    "MAT": LibraryRate("MAT", "Hardfill", "m3", D(55)),
}
QS = {"EW01": QSItem("EW01", "Earthworks", "Strip", "m2", D(800))}


def row(**kw):
    base = dict(qs_code="EW01", mode="Time x Count", resource_type="Plant", resource_code="PL-EXC",
                productivity_rate=D(80), count=D(1), utilisation=None, waste=None, verified="Yes")
    base.update(kw)
    return BuildUpRow(**base)


def test_time_x_count():
    r = compute_buildup([row()], QS, LIB)[0]
    assert r.calc_duration_hrs == D(10) and r.cost == D(1500) and r.row_id == "EW01-001"


def test_duration_override_and_utilisation():
    r = compute_buildup([row(duration_override_hrs=D(20), utilisation=D("0.5"))], QS, LIB)[0]
    assert r.applied_duration_hrs == D(20) and r.cost == D(1500)


def test_job_rate_override_beats_library():
    r = compute_buildup([row(job_rate_override=D(200))], QS, LIB)[0]
    assert r.applied_rate == D(200) and r.cost == D(2000) and r.library_rate == D(150)


def test_qty_x_factor_with_waste():
    r = compute_buildup([row(mode="QS Qty x Factor", resource_type="Material", resource_code="MAT",
                             productivity_rate=None, count=D("0.3"), waste=D("0.1"))], QS, LIB)[0]
    assert r.cost == D(800) * D("0.3") * D("1.1") * D(55)


def test_direct_and_lump():
    d = compute_buildup([row(mode="Direct Qty", resource_code="MAT", manual_qty=D(10), waste=D("0.05"))], QS, LIB)[0]
    assert d.cost == D(10) * D("1.05") * D(55)
    l = compute_buildup([row(mode="Lump Sum / Quote", resource_code="MAT", manual_qty=D(1), job_rate_override=D(5000))], QS, LIB)[0]
    assert l.cost == D(5000)


def test_blank_numbers_are_zero():
    r = compute_buildup([row(count=None)], QS, LIB)[0]
    assert r.cost == 0


def test_unknown_mode_rejected():
    with pytest.raises(BuildUpError):
        compute_buildup([row(mode="Magic")], QS, LIB)


def test_row_ids_sequence_per_code():
    rs = compute_buildup([row(), row(resource_code="LAB", resource_type="Labour")], QS, LIB)
    assert [x.row_id for x in rs] == ["EW01-001", "EW01-002"]


def test_qa_flags():
    plant = row()
    op = row(resource_code="LAB-OP", resource_type="Labour")
    flags = {r.row_id: r.qa_flag for r in compute_buildup([plant, op], QS, LIB)}
    assert flags["EW01-001"] == "OPERATOR DOUBLE-COUNT"
    assert compute_buildup([row(resource_code="")], QS, LIB)[0].qa_flag == "RESOURCE CODE"
    zero = {"PL-EXC": LibraryRate("PL-EXC", "x", "hr", D(0))}
    assert compute_buildup([row()], QS, zero)[0].qa_flag == "RATE MISSING"
    assert compute_buildup([row(resource_code="LAB", resource_type="Labour", verified="No")], QS, LIB)[0].qa_flag == "VERIFY"


def test_weather_exposed_only_labour_plant():
    rs = compute_buildup([row(weather_exposed="Yes"), row(mode="Direct Qty", resource_type="Material",
                         resource_code="MAT", manual_qty=D(1), weather_exposed="Yes")], QS, LIB)
    assert rs[0].weather_exposed_cost == D(1500) and rs[1].weather_exposed_cost == 0


def test_qs_rate_and_orphans():
    rs = compute_buildup([row(), row(qs_code="ZZ99", mode="Lump Sum / Quote", resource_code="MAT", manual_qty=D(1), job_rate_override=D(1500))], QS, LIB)
    res = compute_qs([QS["EW01"]], rs)
    assert res.lines[0].amount == D(1500) and res.lines[0].rate == D("1.875") and res.orphan_cost == D(1500)


def ci(ref, method, include="Yes", pct=0, pc=0, ev=0):
    return CommercialInput(ref, ref, method, include, D(pct), D(pc), D(ev))


def test_true_margin_not_markup():
    inputs = [ci("CA17", "Markup %", pct="0.10"), ci("CA18", "Margin %", pct="0.15")]
    t = compute_tender(D(1000), inputs)
    assert cents(t.overhead) == D("100.00")
    assert cents(t.tender_excl_gst) == cents(D(1100) / D("0.85"))          # margin on sell
    assert cents(t.profit / t.tender_excl_gst) == D("0.15")                # profit is 15% of SELL


def test_include_flag_and_methods():
    inputs = [ci("CA03", "%", pct="0.02"), ci("CA09", "PC Sum", pc=3000), ci("CA10", "Weather Engine", ev=500),
              ci("CA16", "Fixed Amount", pc=100), ci("CA04", "PC Sum", include="No", pc=9999)]
    t = compute_tender(D(10000), inputs)
    assert t.additions["CA03"] == D(200) and t.additions["CA09"] == D(3000)
    assert t.additions["CA10"] == D(500) and t.additions["CA16"] == D(100) and t.additions["CA04"] == 0
    assert t.subtotal == D(13800)


def test_margin_100_rejected():
    with pytest.raises(ValueError):
        compute_tender(D(1), [ci("CA18", "Margin %", pct=1)])


def test_gst_and_retention():
    inputs = [ci("CA21", "%", pct="0.15"), ci("CA22", "%", pct="0.05")]
    t = compute_tender(D(1000), inputs)
    assert t.gst == D(150) and t.retention_withheld == D(50) and t.net_after_retention == D(950)


def test_weather_scaling_to_current_pool():
    rows = compute_buildup([row(weather_exposed="Yes")], QS, LIB)   # pool = 1500
    tool = WeatherToolRun(D(3000), D(600), D(2), D(1))
    w = compute_weather(rows, tool, WeatherInputs(D(584), D(295)))
    assert w.direct_productivity == D(300)            # pool halved -> productivity halved
    assert w.critical_path_prelims == D(1168) and w.billed_hire == D(295)
    assert w.allowance == D(300) + D(1168) + D(295)


def test_wind_excluded_unless_included():
    rows = compute_buildup([row(weather_exposed="Yes")], QS, LIB)
    tool = WeatherToolRun(D(1500), D(0), D(0), D(0), wind_sensitivity_cost=D(999))
    assert compute_weather(rows, tool, WeatherInputs(D(0), D(0))).allowance == 0


def test_consolidated_overlay_added_once_and_margin_on_sell():
    c = compute_consolidated(D(500), [Overlay("Coast", D(300)), Overlay("Allied", D(200))], D(0), D("0.10"), D("0.15"))
    assert c.gross_known_package == D(1000)
    assert cents(c.all_in_tender) == cents(D(1100) / D("0.85"))
    assert cents(c.gross_margin_on_sell * 100) == cents(((D(1100) / D("0.85")) - D(1000)) / (D(1100) / D("0.85")) * 100)
    c2 = compute_consolidated(D(500), [Overlay("Coast", D(300)), Overlay("Allied", D(200))], D(100), D("0.10"), D("0.15"))
    assert cents(c2.all_in_if_overlap_removed) == cents(D(990) / D("0.85"))
