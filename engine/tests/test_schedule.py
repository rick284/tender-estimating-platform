from decimal import Decimal as Dc
from pathlib import Path
import pytest

from tender_engine import D
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook
from tender_engine.schedule import ScheduleError, compute_schedule, default_schedule, auto_map

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"


def L(ref, trade, kind="work"):
    return {"ref": ref, "trade": trade, "kind": kind}


def src(key, amount, own=True, label=None):
    return {"key": key, "label": label or key, "amount": D(amount), "own": own}


def test_simple_schedule_reconciles_exactly_and_margin_line_carries_overhead_and_profit():
    s = {"groups": [{"id": "g", "name": "G", "lines": [L("1", "Earthworks"), L("2", "Prelims", "pg"), L("3", "Margin", "margin")]}],
         "map": {"qs:A": "line:1", "qs:B": "line:2"}}
    r = compute_schedule(s, [src("qs:A", "1000"), src("qs:B", "200")], D("0.10"), D("0.15"), D("1200") * D("1.1") / D("0.85"))
    g = r["groups"][0]
    assert g["subtotal"] == Dc("1000.00") and g["lines"][1]["amount"] == Dc("200.00")
    assert g["total"] == Dc("1552.94") and g["lines"][2]["amount"] == Dc("352.94") and r["reconciles"] and r["difference"] == 0


def test_unmapped_sources_and_bad_targets_are_reported_not_hidden():
    s = {"groups": [{"id": "g", "name": "G", "lines": [L("1", "W"), L("2", "M", "margin")]}], "map": {"qs:A": "line:1", "qs:C": "line:9"}}
    r = compute_schedule(s, [src("qs:A", "100"), src("qs:B", "50"), src("qs:C", "25")], D(0), D(0), D("175"))
    assert not r["reconciles"] and {u["key"] for u in r["unmapped"]} == {"qs:B", "qs:C"} and r["problems"]


def test_split_parts_and_remainder():
    s = {"groups": [{"id": "g", "name": "G", "lines": [L("1", "A"), L("2", "B"), L("3", "M", "margin")]}],
         "map": {"overlay:X": [{"to": "line:1", "amount": "30"}, {"to": "line:2"}]}}
    r = compute_schedule(s, [src("overlay:X", "100", own=False)], D(0), D(0), D("100"))
    assert [x["amount"] for x in r["groups"][0]["lines"][:2]] == [Dc("30.00"), Dc("70.00")] and r["reconciles"]
    s["map"]["overlay:X"] = [{"to": "line:1", "amount": "130"}]
    assert compute_schedule(s, [src("overlay:X", "100", own=False)], D(0), D(0), D("100"))["problems"]      # 130 > 100


def test_validation():
    with pytest.raises(ScheduleError):
        compute_schedule({"groups": []}, [], D(0), D(0), D(0))
    with pytest.raises(ScheduleError):
        compute_schedule({"groups": [{"id": "g", "name": "G", "lines": [L("1", "W")]}]}, [], D(0), D(0), D(0))
    with pytest.raises(ScheduleError):
        compute_schedule({"groups": [{"id": "g", "name": "G", "lines": [L("1", "W"), L("1", "X"), L("2", "M", "margin")]}]}, [], D(0), D(0), D(0))


def test_spread_is_shared_by_own_works_weight_inside_margin_lines():
    s = {"groups": [{"id": "a", "name": "A", "lines": [L("1", "W"), L("2", "M", "margin")]},
                    {"id": "b", "name": "B", "lines": [L("3", "W"), L("4", "M", "margin")]}],
         "map": {"qs:A": "line:1", "qs:B": "line:3", "ca:CA16": "spread", "overlay:S": "line:3"}}
    r = compute_schedule(s, [src("qs:A", "100"), src("qs:B", "300"), src("ca:CA16", "40"), src("overlay:S", "500", own=False)], D(0), D(0), D("940"))
    a, b = r["groups"]
    assert a["hidden"] == Dc("10.00") and b["hidden"] == Dc("30.00")            # 40 shared 100:300; the overlay doesn't count as own works
    assert a["total"] == Dc("110.00") and b["total"] == Dc("830.00") and r["reconciles"]


def test_default_schedule_for_any_estimate_reconciles():
    s = default_schedule(["Earthworks", "Pavements"], ["Coast Concrete"])
    qs = [{"code": "EW01", "section": "Earthworks"}, {"code": "PV01", "section": "Pavements"}]
    s["map"] = auto_map(s, qs, [{"name": "Coast Concrete"}], ["CA10"])
    srcs = [src("qs:EW01", "100"), src("qs:PV01", "200"), src("overlay:Coast Concrete", "300", own=False), src("ca:CA10", "50")]
    r = compute_schedule(s, srcs, D("0.1"), D("0.15"), D("650") * D("1.1") / D("0.85"))
    assert r["reconciles"] and len(r["groups"][0]["lines"]) == 5


@pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")
def test_hobsonville_tpw_schedule_matches_the_client_return_to_the_cent():
    """The TPW price schedule issued with Rev34E (04 Client Pricing / 05 Tender Submission), rebuilt from the platform's numbers."""
    m = load_master_workbook(PRIVATE); e = compute_estimate(m)
    qs_amt = {q["code"]: q["amount"] for q in e["qs"]}
    cons = e["consolidated"]
    sources = [src(f"qs:{c}", repr(a)) for c, a in qs_amt.items() if a]
    sources += [src(f"ca:{c['ref']}", repr(c["amount"])) for c in e["commercial"] if c["amount"] and c["ref"] <= "CA16" and c["ref"] not in ("CA17", "CA18")]
    sources += [src(f"overlay:{o['name']}", repr(o["amount"]), own=False) for o in cons["overlays"]]
    bld = [L("MB/001", "Excavation"), L("MB/002", "Concrete"), L("MB/003", "Reinforcing"), L("MB/025", "Preliminaries & General", "pg"), L("MB/026", "Margin", "margin")]
    civ = [L("CW/001", "Site Preparation/Silt Fencing"), L("CW/002", "Site Clearance/Demolition"), L("CW/003", "Retaining Walls"), L("CW/004", "Bulk Earthworks"),
           L("CW/005", "Stormwater Drainage"), L("CW/006", "Wastewater Drainage"), L("CW/008", "Services Trenching"),
           L("CW/009", "Driveways/Car Parking/Vehicle Crossing/Pavements"), L("CW/011", "Fencing/Street Furniture"),
           L("CW/012", "Preliminaries & General", "pg"), L("CW/013", "Margin", "margin")]
    mp = {"qs:EW05": "line:MB/001", "qs:EW07": "line:MB/001",
          "overlay:Coast Concrete foundation / floor": [{"to": "line:MB/003", "amount": "28400"}, {"to": "line:MB/002"}],
          "qs:ESC01": "line:CW/001", "qs:EW01": "line:CW/002",
          "qs:RW01": "line:CW/003", "qs:RW02": "line:CW/003", "qs:RW03": "line:CW/003", "qs:RW04": "line:CW/003",
          "qs:EW02": "line:CW/004", "qs:EW03": "line:CW/004", "qs:EW04": "line:CW/004", "qs:EW08": "line:CW/004", "qs:EW09": "line:CW/004",
          "qs:ES02": "line:CW/005", "qs:ES03": "line:CW/005", "qs:ES01": "line:CW/008",
          "qs:PV01": "line:CW/009", "qs:PV02": "line:CW/009", "qs:PV04": "line:CW/009", "qs:PV05": "line:CW/009", "qs:ES04": "line:CW/011",
          "qs:PG01": "line:CW/012", "qs:TC01": "line:CW/012", "qs:RH01": "line:CW/012", "ca:CA09": "line:CW/012", "ca:CA10": "line:CW/012",
          "ca:CA16": "spread",
          "overlay:Allied public stormwater / detention base": "line:CW/005", "overlay:Allied public setout / as-built / signoff": "line:CW/005",
          "overlay:Allied private drainage": [{"to": "line:CW/003", "amount": "19211.04"}, {"to": "line:CW/006", "amount": "26864.36"}, {"to": "line:CW/005"}]}
    sched = {"name": "TPW", "groups": [{"id": "mb", "name": "MAIN BUILDING", "code": "A", "lines": bld}, {"id": "cw", "name": "CIVIL WORKS", "code": "B", "lines": civ}], "map": mp}
    r = compute_schedule(sched, sources, D(cons["overhead_rate"]), D(cons["margin"]), D(repr(cons["all_in"])))
    by = {x["ref"]: x["amount"] for g in r["groups"] for x in g["lines"]}
    expect = {"MB/001": "15000.00", "MB/002": "182206.00", "MB/003": "28400.00", "MB/026": "67131.18", "CW/001": "7750.14", "CW/002": "4946.75",
              "CW/003": "90879.88", "CW/004": "96118.43", "CW/005": "263895.05", "CW/006": "26864.36", "CW/008": "15000.00", "CW/009": "119034.31",
              "CW/011": "2500.00", "CW/012": "77208.09"}
    assert {k: str(by[k]) for k in expect} == expect
    g = {x["id"]: x for x in r["groups"]}
    assert str(g["mb"]["subtotal"]) == "225606.00" and str(g["mb"]["total"]) == "292737.18"
    # The issued sheet prints a civil sub-total of 626,988.93 and a Margin of 229,982.61, but its printed lines add to 626,988.92.
    # The platform's printed lines always add up, so the sub-total is 626,988.92 and the Margin line 229,982.62; the group total is the same.
    assert str(g["cw"]["subtotal"]) == "626988.92" and by["CW/013"] == Dc("229982.62") and str(g["cw"]["total"]) == "934179.63"
    assert str(r["total"]) == "1226916.81" and r["reconciles"] and not r["unmapped"] and r["difference"] == 0


TPW_TEXT = """
# MAIN BUILDING | A
MB/001\tExcavation
MB/002\tConcrete
MB/003\tReinforcing
MB/004  Structural Steel
MB/025  Preliminaries & General   [pg]
MB/026  Margin   [margin]
# CIVIL WORKS | B
CW/001  Site Preparation/Silt Fencing
CW/002  Site Clearance/Demolition
CW/003  Retaining Walls
CW/004  Bulk Earthworks
CW/005  Stormwater Drainage
CW/006  Wastewater Drainage
CW/007  Water Supply
CW/008  Services Trenching
CW/009  Driveways/Car Parking/Vehicle Crossing/Pavements
CW/010  Planting/Soft Landscaping
CW/011  Fencing/Street Furniture
CW/012  Preliminaries & General  [pg]
CW/013  Margin  [margin]
"""


def test_parse_format_from_pasted_text():
    from tender_engine.schedule import parse_format
    s = parse_format(TPW_TEXT, "TPW", "HLC PROPERTY LIMITED")
    assert [g["name"] for g in s["groups"]] == ["MAIN BUILDING", "CIVIL WORKS"] and s["groups"][0]["code"] == "A"
    assert [ln["kind"] for ln in s["groups"][1].get("lines")][-2:] == ["pg", "margin"] and len(s["groups"][1]["lines"]) == 13
    # a group with no Margin line gets one
    s2 = parse_format("# WORKS | W\n1  Earthworks\n2  Pavements")
    assert s2["groups"][0]["lines"][-1] == {"ref": "W/M", "trade": "Margin", "kind": "margin"}
    for bad in ("", "1  No heading", "# G\n1", "# G\n1  A\n1  B", "# G\n1  A [margin]\n2  B [margin]", "# \n1  A"):
        with pytest.raises(ScheduleError):
            parse_format(bad)


@pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")
def test_tpw_schedule_built_through_edits_reconciles_and_reports_changes():
    from tender_engine.edits import EditError, apply_edits
    m = load_master_workbook(PRIVATE)
    e0 = compute_estimate(m)
    assert e0["schedule"]["auto"] and e0["schedule"]["reconciles"]
    mp = {"qs:EW05": "line:MB/001", "qs:EW07": "line:MB/001", "overlay:Coast Concrete foundation / floor": [{"to": "line:MB/003", "amount": "28400"}, {"to": "line:MB/002"}],
          "qs:ESC01": "line:CW/001", "qs:EW01": "line:CW/002", "qs:RW01": "line:CW/003", "qs:RW02": "line:CW/003", "qs:RW03": "line:CW/003", "qs:RW04": "line:CW/003",
          "qs:EW02": "line:CW/004", "qs:EW03": "line:CW/004", "qs:EW04": "line:CW/004", "qs:EW08": "line:CW/004", "qs:EW09": "line:CW/004",
          "qs:ES02": "line:CW/005", "qs:ES03": "line:CW/005", "qs:ES01": "line:CW/008", "qs:PV01": "line:CW/009", "qs:PV02": "line:CW/009", "qs:PV04": "line:CW/009",
          "qs:PV05": "line:CW/009", "qs:ES04": "line:CW/011", "qs:PG01": "line:CW/012", "qs:TC01": "line:CW/012", "qs:RH01": "line:CW/012",
          "ca:CA09": "line:CW/012", "ca:CA10": "line:CW/012", "ca:CA16": "spread",
          "overlay:Allied public stormwater / detention base": "line:CW/005", "overlay:Allied public setout / as-built / signoff": "line:CW/005",
          "overlay:Allied private drainage": [{"to": "line:CW/003", "amount": "19211.04"}, {"to": "line:CW/006", "amount": "26864.36"}, {"to": "line:CW/005"}]}
    edits = [{"target": "schedule", "op": "add", "key": "format", "value": {"text": TPW_TEXT, "name": "TPW Main Contract Tender Submission"}}]
    # before mapping, everything is unmapped and the schedule says so
    m1, _ = apply_edits(m, edits)
    s1 = compute_estimate(m1)["schedule"]
    assert not s1["reconciles"] and len(s1["unmapped"]) > 20 and not s1["auto"]
    edits += [{"target": "schedule_map", "key": k, "field": "to", "value": v if isinstance(v, str) else __import__("json").dumps(v)} for k, v in mp.items()]
    m2, changes = apply_edits(m, edits)
    s2 = compute_estimate(m2)["schedule"]
    assert s2["reconciles"] and s2["total"] == 1226916.81 and not s2["unmapped"]
    assert {g["id"]: g["total"] for g in s2["groups"]} == {"g1": 292737.18, "g2": 934179.63}
    assert changes[0]["target"] == "schedule" and sum(1 for c in changes if c["target"] == "schedule_map") == len(mp)
    for bad in ({"target": "schedule_map", "key": "qs:EW01", "field": "to", "value": "line:NOPE"},
                {"target": "schedule_map", "key": "nonsense", "field": "to", "value": "spread"},
                {"target": "schedule", "op": "add", "key": "format", "value": {"text": "no heading"}}):
        with pytest.raises(EditError):
            apply_edits(m2, [bad])
    # unmapping a source is reported, and going back to automatic restores the default
    m3, ch3 = apply_edits(m2, [{"target": "schedule_map", "key": "qs:EW01", "field": "to", "value": ""}])
    assert not compute_estimate(m3)["schedule"]["reconciles"] and ch3[0]["after"] == ""
    m4, _ = apply_edits(m2, [{"target": "schedule", "op": "delete", "key": "format"}])
    assert compute_estimate(m4)["schedule"]["auto"] and compute_estimate(m4)["schedule"]["reconciles"]


@pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")
def test_auto_schedule_edits_only_report_real_changes_and_round_trip():
    from tender_engine.edits import apply_edits
    from tender_engine.inputs import from_json, to_json
    m = load_master_workbook(PRIVATE)
    m2, ch = apply_edits(m, [{"target": "schedule_map", "key": "qs:EW02", "field": "to", "value": "line:01"}])
    assert [c["key"] for c in ch] == ["qs:EW02"]                       # only the one that really moved, not the whole frozen default
    s = compute_estimate(from_json(to_json(m2)))["schedule"]
    assert s["reconciles"]
