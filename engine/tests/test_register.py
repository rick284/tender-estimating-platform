from collections import Counter
from pathlib import Path
import pytest

from tender_engine.blank import blank_from_template
from tender_engine.edits import EditError, apply_edits
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook
from tender_engine.inputs import from_json, to_json

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"
pytestmark = pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")


@pytest.fixture(scope="module")
def m():
    return load_master_workbook(PRIVATE)


def test_hobsonville_register_is_imported_from_the_cover_sheet(m):
    assert Counter(x["kind"] for x in m.register) == {"rfi": 18, "risk": 11, "document": 9, "assumption": 9, "exclusion": 3}
    rfi = {x["ref"]: x for x in m.register if x["kind"] == "rfi"}
    assert rfi["RFI-15"]["status"] == "OPEN" and rfi["RFI-15"]["rag"] == "RED" and "1,310m3" in rfi["RFI-15"]["detail"]
    assert rfi["RFI-17"]["status"] == "CLOSED" and rfi["RFI-14A"]["status"] == "CLOSED" and rfi["RFI-05"]["status"] == "CLOSED"
    risk = {x["ref"]: x for x in m.register if x["kind"] == "risk"}
    assert risk["RT01"]["rag"] == "RED" and risk["RT01"]["likelihood"] == "High" and risk["RT01"]["rating"] == "Critical" and risk["RT03"]["rag"] == "AMBER"
    ids = [x["id"] for x in m.register]
    assert len(ids) == len(set(ids))
    s = compute_estimate(m)["register_summary"]
    assert s["open_red_rfis"] == 4 and s["red_risks"] == 2 and s["rfis"] == 18        # RFI-06, 14B, 15 and 16 are the open REDs


def test_register_edits_add_set_delete_and_net_changes(m):
    base = load_master_workbook(PRIVATE)
    m2, ch = apply_edits(base, [
        {"target": "register", "op": "add", "key": "R-new00001", "value": {"kind": "rfi", "title": "Confirm crossing width", "detail": "Council to confirm.", "rag": "red"}},
        {"target": "register", "key": "R-rfi001", "field": "status", "value": "closed"},
        {"target": "register", "op": "delete", "key": "R-ass001"}])
    new = next(x for x in m2.register if x["id"] == "R-new00001")
    assert new["ref"] == "RFI-18" and new["status"] == "OPEN" and new["rag"] == "RED"          # next free reference
    assert next(x for x in m2.register if x["id"] == "R-rfi001")["status"] == "CLOSED"
    assert {c["field"] for c in ch if c["target"] == "register"} == {"added", "status", "removed"}
    assert compute_estimate(from_json(to_json(m2)))["register"] == m2.register
    _, none = apply_edits(base, [{"target": "register", "op": "add", "key": "R-tmp00001", "value": {"kind": "risk", "title": "x"}},
                                 {"target": "register", "op": "delete", "key": "R-tmp00001"}])
    assert none == []


@pytest.mark.parametrize("edit,msg", [
    ({"target": "register", "op": "add", "key": "bad", "value": {"kind": "rfi", "title": "x"}}, "identity"),
    ({"target": "register", "op": "add", "key": "R-aaaa0001", "value": {"kind": "nonsense", "title": "x"}}, "must be one of"),
    ({"target": "register", "op": "add", "key": "R-aaaa0001", "value": {"kind": "rfi"}}, "Describe the item"),
    ({"target": "register", "op": "add", "key": "R-aaaa0001", "value": {"kind": "rfi", "title": "x", "ref": "RFI-01"}}, "already used"),
    ({"target": "register", "op": "add", "key": "R-aaaa0001", "value": {"kind": "rfi", "title": "x", "rag": "PURPLE"}}, "RED, AMBER"),
    ({"target": "register", "op": "add", "key": "R-aaaa0001", "value": {"kind": "rfi", "title": "x" * 400}}, "too long"),
    ({"target": "register", "key": "R-rfi001", "field": "status", "value": "maybe"}, "OPEN or CLOSED"),
    ({"target": "register", "key": "R-rfi001", "field": "bogus", "value": "x"}, "can't be edited"),
    ({"target": "register", "key": "R-rfi001", "field": "ref", "value": "RFI-02"}, "already used"),
    ({"target": "register", "key": "R-zzzz9999", "field": "title", "value": "x"}, "Unknown register item"),
])
def test_register_validation(m, edit, msg):
    with pytest.raises(EditError, match=msg):
        apply_edits(load_master_workbook(PRIVATE), [edit])


def test_intake_text_becomes_register_items_on_a_new_tender(m):
    b = blank_from_template(m, "Job", {"drawings": "Arch Rev3\nCivil Rev1", "assumptions": "Normal ground\nWeekday access", "missing_info": "Confirm crossing",
                                      "inclusions_exclusions": "Excavation and fill\nExclude building works"})
    c = Counter(x["kind"] for x in b.register)
    assert c == {"document": 2, "assumption": 2, "rfi": 1, "inclusion": 1, "exclusion": 1}
    assert [x["ref"] for x in b.register if x["kind"] == "assumption"] == ["A1", "A2"] and next(x for x in b.register if x["kind"] == "rfi")["rag"] == "AMBER"
    assert compute_estimate(b)["register_summary"]["open_rfis"] == 1


def test_report_carries_the_register():
    pypdf = pytest.importorskip("pypdf")
    import io
    from tender_engine.outputs import OutputContext, report_pdf
    est = compute_estimate(load_master_workbook(PRIVATE))
    t = "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(report_pdf(est, OutputContext("3Bears", "Rick", "329 Hobsonville Road", "Dave", "", "Rev34E", "12 September 2026")))).pages)
    for needle in ["Current decision blockers", "RFI-15", "RFI-16", "Basis documents", "Estimate Assumptions", "Exclusions and By Others", "Risk Basis",
                   "Pricing Qualifications and RFIs", "RT01", "Critical" if False else "RED", "Keystone"]:
        assert needle in t, needle
