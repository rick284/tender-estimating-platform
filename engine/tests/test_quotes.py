import io
from pathlib import Path
import pytest

from tender_engine.edits import EditError, apply_edits
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook
from tender_engine.inputs import from_json, to_json

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"
pytestmark = pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")


@pytest.fixture(scope="module")
def m():
    return load_master_workbook(PRIVATE)


def test_hobsonville_quotes_are_imported(m):
    assert [q["ref"] for q in m.quotes] == [f"Q-{i:02d}" for i in range(1, 15)]
    q = {x["ref"]: x for x in m.quotes}
    assert q["Q-01"]["amount"] == "40000.00" and q["Q-01"]["estimate_ref"] == "ES03" and "Allproof" in q["Q-01"]["supplier"]
    assert q["Q-11"]["amount"] == "210606.00" and q["Q-14"]["amount"] == "6500.00" and q["Q-08"]["supplier"] == "Gibb Ritchie Geotechnical"
    assert len({x["id"] for x in m.quotes}) == 14 and compute_estimate(m)["quotes"] == m.quotes


def test_quote_edits(m):
    m2, ch = apply_edits(m, [{"target": "quote", "op": "add", "key": "S-new00001", "value": {"supplier": "Acme", "amount": "1,250.5"}},
                             {"target": "quote", "key": "S-q001", "field": "status", "value": "ACCEPTED"}, {"target": "quote", "op": "delete", "key": "S-q014"}])
    new = next(x for x in m2.quotes if x["id"] == "S-new00001")
    assert new["ref"] == "Q-15" and new["amount"] == "1250.5" and len(m2.quotes) == 14
    assert {c["field"] for c in ch if c["target"] == "quote"} == {"added", "status", "removed"}
    assert from_json(to_json(m2)).quotes == m2.quotes
    assert apply_edits(m, [{"target": "quote", "op": "add", "key": "S-tmp00001", "value": {"supplier": "x"}}, {"target": "quote", "op": "delete", "key": "S-tmp00001"}])[1] == []


@pytest.mark.parametrize("edit,msg", [
    ({"target": "quote", "op": "add", "key": "nope", "value": {"supplier": "x"}}, "identity"),
    ({"target": "quote", "op": "add", "key": "S-aaaa0001", "value": {}}, "Name the package"),
    ({"target": "quote", "op": "add", "key": "S-aaaa0001", "value": {"supplier": "x", "amount": "abc"}}, "needs a number"),
    ({"target": "quote", "op": "add", "key": "S-aaaa0001", "value": {"supplier": "x", "amount": "-5"}}, "negative"),
    ({"target": "quote", "op": "add", "key": "S-aaaa0001", "value": {"supplier": "x", "ref": "Q-01"}}, "already used"),
    ({"target": "quote", "key": "S-q001", "field": "ref", "value": "Q-02"}, "already used"),
    ({"target": "quote", "key": "S-q001", "field": "bogus", "value": "x"}, "can't be edited"),
    ({"target": "quote", "key": "S-zzzz9999", "field": "status", "value": "x"}, "Unknown quote"),
])
def test_quote_validation(edit, msg):
    with pytest.raises(EditError, match=msg):
        apply_edits(load_master_workbook(PRIVATE), [edit])


def test_evidence_pdfs_trace_every_quote(m):
    pypdf = pytest.importorskip("pypdf")
    from tender_engine.outputs import OutputContext, evidence_notes_pdf, verification_index_pdf
    est = compute_estimate(m)
    ctx = OutputContext("3Bears", "Rick", "329 Hobsonville Road", "Dave", "", "Rev34E", "12 September 2026")
    text = lambda b: "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(b)).pages)
    idx, notes = text(verification_index_pdf(est, ctx)), text(evidence_notes_pdf(est, ctx))
    for needle in ["Supplier and Subcontractor Verification Index", "not automatically the controlling tender amount", "Coast Concrete", "Allied Civil Earthworks", "Traffic Safe", "Gibb Ritchie"]:
        assert needle in idx, needle
    assert "Control note" in notes and "$210,606.00" in notes and "Q-14" in notes
    empty = compute_estimate(load_master_workbook(PRIVATE)); empty["quotes"] = []
    assert "No supplier or subcontractor quotes" in text(verification_index_pdf(empty, ctx))
