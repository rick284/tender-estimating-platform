import io
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")
pytest.importorskip("reportlab")
pypdf = pytest.importorskip("pypdf")

from tender_engine.blank import blank_from_template
from tender_engine.edits import apply_edits
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook
from tender_engine.outputs import OutputContext, pricing_workbook, report_pdf, schedule_pdf

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"
pytestmark = pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")
CTX = OutputContext("3Bears Projects", "Rick Jones", "329 Hobsonville Road Childcare Centre", "Dave Stewart | Siteworks", "Hobsonville", "Rev34E", "12 September 2026")


def text(pdf: bytes) -> str:
    return "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(pdf)).pages)


@pytest.fixture(scope="module")
def est():
    return compute_estimate(load_master_workbook(PRIVATE))


def test_report_contains_the_controlling_numbers(est):
    t = text(report_pdf(est, CTX))
    for needle in ["$1,226,916.81", "$948,072.08", "$94,807.21", "$184,037.52", "22.73%", "$614,700.22", "$18,269.06", "$18,204.69", "8.829",
                   "329 HOBSONVILLE ROAD CHILDCARE CENTRE", "CONTRACT-AWARD HOLD", "Appendix A", "Page 1"]:
        assert needle in t, needle


def test_schedule_pdf_and_workbook_agree_with_the_estimate(est):
    t = text(schedule_pdf(est, CTX))
    assert "$1,226,916.81" in t and "TOTAL (EXCL GST)" in t and "Earthworks" in t
    wb = openpyxl.load_workbook(io.BytesIO(pricing_workbook(est, CTX)))
    assert wb.sheetnames == ["Client Summary", "Price Schedule", "Reconciliation"]
    vals = {r[1]: r[2] for r in wb["Price Schedule"].iter_rows(min_row=5, values_only=True) if r[1]}
    assert abs(vals["TOTAL (EXCL GST)"] - 1226916.81) < 0.005
    summ = {r[0]: r[1] for r in wb["Client Summary"].iter_rows(values_only=True) if r[0]}
    assert abs(summ["WORKING ALL-IN TENDER"] - est["consolidated"]["all_in"]) < 1e-6
    rec = {r[0]: r[1] for r in wb["Reconciliation"].iter_rows(min_row=5, max_row=10, values_only=True)}
    assert rec["Difference"] == 0 and rec["Not yet mapped"] == 0


def test_blank_tender_and_unreconciled_schedule_produce_honest_documents():
    tpl = load_master_workbook(PRIVATE)
    blank = compute_estimate(blank_from_template(tpl, "New job", {"scope": "Civil works", "assumptions": "Normal ground\nWeekday access"}))
    ctx = OutputContext("Acme", "Pat", "New job", "Client", "", "Rev0", "1 January 2027")
    t = text(report_pdf(blank, ctx, {"scope": "Civil works", "assumptions": "Normal ground\nWeekday access"}))
    assert "NEW JOB" in t and "Normal ground" in t and "Civil works" in t and "$0.00" in t
    assert pricing_workbook(blank, ctx)[:2] == b"PK" and text(schedule_pdf(blank, ctx))
    m, _ = apply_edits(blank_from_template(tpl, "x", {}), [
        {"target": "qs", "op": "add", "key": "EW01", "value": {"section": "E", "description": "d", "unit": "m2", "quantity": "1", "basis": "MEASURED"}},
        {"target": "row", "op": "add", "key": "N-abcd1234", "value": {"qs_code": "EW01", "mode": "Lump Sum / Quote", "resource_code": "", "task": "t"}},
        {"target": "row", "key": "N-abcd1234", "field": "manual_qty", "value": "1"}, {"target": "row", "key": "N-abcd1234", "field": "job_rate_override", "value": "500"},
        {"target": "schedule", "op": "add", "key": "format", "value": {"text": "# W\n1  Civil"}}])
    e = compute_estimate(m)
    assert not e["schedule"]["reconciles"]
    assert "DRAFT" in text(schedule_pdf(e, ctx)) and "NOT YET RECONCILED" in text(report_pdf(e, ctx))
