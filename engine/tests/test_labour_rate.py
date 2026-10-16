from decimal import Decimal
import pytest
from tender_engine import labour_rate as lr, D
from tender_engine.edits import EditError, apply_edits
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook
from tender_engine.inputs import from_json, to_json
from pathlib import Path

# NZIQS Quantity Surveyor's Handbook (5th ed.) carpenter example: 45 paid h x $25, KiwiSaver 2%, leave days 20 + 11 + 5, levies 6.35%,
# redundancy 2%, $45 tools per week. The book's own totals are reproduced to the cent up to the leading-hand line.
BOOK = dict(role="Carpenter", jurisdiction="NZ", employment_basis="permanent full time", source_date="2012", evidence="market normalised", hourly_rate=25,
            paid_hours_week=45, productive_hours_week=38, kiwisaver_pct="0.02", annual_leave_days=20, stat_days=11, sick_days=5, days_per_week=5,
            levy_pct="0.0635", redundancy_pct="0.02", weekly_allowance=45, supervision_pct="0.05")


def test_reproduces_the_handbook_build_up_to_the_cent():
    c = lr.compute(BOOK)
    st = {s["label"]: s for s in c["steps"]}
    assert round(c["leave_pct"], 4) == Decimal("0.1602")
    assert round(st["Employer KiwiSaver"]["amount"], 2) == D("22.50")
    assert round(st["Holiday, statutory and sick leave"]["amount"], 2) == D("180.23") and round(st["Holiday, statutory and sick leave"]["running"], 2) == D("1327.73")
    assert round(st["Insurance and ACC levies"]["amount"], 2) == D("84.31") and round(st["Insurance and ACC levies"]["running"], 2) == D("1412.04")
    assert round(st["Redundancy provision"]["running"], 2) == D("1440.28")
    assert round(st["Weekly allowances (tools, clothing)"]["running"], 2) == D("1485.28")
    assert c["rate_rounded"] == D("41.04") and c["per_paid_hour"] < c["rate"]       # book prints 41.07: it adds a $21.38 charge allowance to the leading-hand base


def test_status_follows_the_policy():
    assert lr.compute(BOOK)["status"] == "AMBER"                                                     # normalised market evidence
    assert lr.compute({**BOOK, "evidence": "raw wage"})["status"] == "RED"
    assert lr.compute({**BOOK, "evidence": "company actual"})["status"] == "AMBER"                   # no independent check yet
    assert lr.compute({**BOOK, "evidence": "company actual", "independent_check": True})["status"] == "GREEN"
    assert lr.compute({**BOOK, "source_date": ""})["status"] == "RED"


def test_input_checks():
    for bad, msg in (({"role": ""}, "role"), ({"evidence": "guess"}, "Evidence"), ({"hourly_rate": 0}, "more than zero"),
                     ({"productive_hours_week": 50}, "exceed paid"), ({"kiwisaver_pct": 3}, "fraction"), ({"levy_pct": "abc"}, "number"), ({"stat_days": -1}, "negative")):
        with pytest.raises(lr.LabourError, match=msg):
            lr.compute({**BOOK, **bad})


PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"


@pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")
def test_edit_adds_a_library_rate_keeps_history_and_round_trips():
    base = load_master_workbook(PRIVATE)
    m, changes = apply_edits(base, [{"target": "labour", "op": "add", "key": "lab-carp", "value": BOOK}])
    r = m.library["LAB-CARP"]
    assert r.base_rate == D("41.04") and r.unit == "hr" and r.category == "Labour" and "AMBER" in r.source
    assert any(c["target"] == "library" for c in changes)
    e = compute_estimate(m)
    assert e["labour_builds"]["LAB-CARP"]["rate"] == 41.04 and e["labour_builds"]["LAB-CARP"]["steps"][0]["label"] == "Weekly pay"
    assert e["summary"]["all_in"] == compute_estimate(base)["summary"]["all_in"]                    # a library rate nobody uses changes no price
    m2, ch2 = apply_edits(from_json(to_json(m)), [{"target": "labour", "op": "set", "key": "LAB-CARP", "value": {**BOOK, "hourly_rate": 26, "evidence": "company actual", "independent_check": True}}])
    assert m2.library["LAB-CARP"].base_rate > D("41.04") and len(m2.labour_builds["LAB-CARP"]["history"]) == 1
    assert {c["field"] for c in ch2 if c["target"] == "labour"} == {"rate", "status"}
    assert compute_estimate(m2)["labour_builds"]["LAB-CARP"]["history"][0]["rate"] == "41.04"
    with pytest.raises(EditError):
        apply_edits(base, [{"target": "labour", "op": "set", "key": "LAB-OP", "value": BOOK}])        # a rate not built here is never overwritten
    with pytest.raises(EditError):
        apply_edits(m, [{"target": "labour", "op": "add", "key": "LAB-CARP", "value": BOOK}])
    with pytest.raises(EditError):
        apply_edits(m, [{"target": "labour", "op": "delete", "key": "LAB-CARP"}])
