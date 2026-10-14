from pathlib import Path
import pytest

from tender_engine import D, cents
from tender_engine.blank import IntakeError, blank_from_template
from tender_engine.edits import EditError, apply_edits
from tender_engine.estimate import compute_estimate
from tender_engine.importers import load_master_workbook
from tender_engine.inputs import from_json, to_json

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"
pytestmark = pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")


@pytest.fixture(scope="module")
def template():
    return load_master_workbook(PRIVATE)


def test_blank_tender_is_empty_and_prices_to_zero(template):
    b = blank_from_template(template, "New job", {"client": "ACME", "tender_level": "Tender"})
    e = compute_estimate(b)
    assert e["summary"]["all_in"] == 0 and e["qs"] == [] and e["buildup"] == []
    assert e["consolidated"]["overlays"] == [] and e["edited"] is True and e["reconciled"] is None
    assert e["meta"]["project"] == "New job" and e["meta"]["client"] == "ACME"


def test_blank_keeps_rates_and_commercial_settings_but_no_job_dollars(template):
    b = blank_from_template(template, "New job", {})
    assert set(b.library) == set(template.library)
    by = {c["ref"]: c for c in b.commercial}
    assert by["CA17"]["pct"] == D("0.1") and by["CA18"]["pct"] == D("0.15")        # overhead and margin carried over
    assert all(c["pc_sum"] == 0 for c in b.commercial)                              # allowances are not
    assert b.overlays == [] and b.recovery == 0


def test_blank_does_not_touch_the_template(template):
    before = len(template.qs), len(template.rows), len(template.overlays)
    blank_from_template(template, "x", {})
    assert before == (len(template.qs), len(template.rows), len(template.overlays))


def test_blank_round_trips_and_can_be_built_up(template):
    b = from_json(to_json(blank_from_template(template, "New job", {})))
    edits = [
        {"target": "qs", "op": "add", "key": "EW01", "value": {"section": "Earthworks", "description": "Strip", "unit": "m2", "quantity": "1000", "basis": "MEASURED"}},
        {"target": "row", "op": "add", "key": "N-abc123", "value": {"qs_code": "EW01", "mode": "Time x Count", "resource_code": "PL-EXC-13", "task": "Strip"}},
        {"target": "row", "key": "N-abc123", "field": "productivity_rate", "value": "100"},
        {"target": "overlay", "op": "add", "key": "Pipes Ltd", "value": {"amount": "5000"}},
    ]
    m, changes = apply_edits(b, edits)
    e = compute_estimate(m)
    assert e["summary"]["base_direct"] > 0 and e["consolidated"]["overlays_total"] == 5000
    assert {c["field"] for c in changes} >= {"added"}


def test_intake_validation(template):
    with pytest.raises(IntakeError):
        blank_from_template(template, "  ", {})
    with pytest.raises(IntakeError):
        blank_from_template(template, "x", {"tender_level": "Guess"})
    with pytest.raises(IntakeError):
        blank_from_template(template, "x", {"scope": "a" * 3000})


def test_overlay_add_delete_rules(template):
    b = blank_from_template(template, "x", {})
    m, _ = apply_edits(b, [{"target": "overlay", "op": "add", "key": "Pipes Ltd", "value": {"amount": "5000"}}])
    for bad in ({"target": "overlay", "op": "add", "key": "pipes ltd", "value": {"amount": "1"}},
                {"target": "overlay", "op": "add", "key": "", "value": {"amount": "1"}},
                {"target": "overlay", "op": "add", "key": "Neg", "value": {"amount": "-5"}},
                {"target": "overlay", "op": "delete", "key": "Nope"}):
        with pytest.raises(EditError):
            apply_edits(m, [bad])
    m2, changes = apply_edits(m, [{"target": "overlay", "op": "delete", "key": "Pipes Ltd"}])
    assert m2.overlays == [] and changes[0]["field"] == "removed"
    m3, changes = apply_edits(m, [{"target": "overlay", "op": "add", "key": "Other", "value": {"amount": "10"}},
                                  {"target": "overlay", "op": "delete", "key": "Other"}])
    assert changes == []                                                            # add then delete nets to nothing


def test_brief_fields_edit_and_round_trip(template):
    base = blank_from_template(template, "Job", {})
    m, changes = apply_edits(base, [
        {"target": "brief", "field": "owner", "value": " Acme Developments "},
        {"target": "brief", "field": "known", "value": "Site is flat."},
        {"target": "brief", "field": "tender_level", "value": "Tender"},
    ])
    assert m.meta["owner"] == "Acme Developments" and "owner" not in base.meta
    assert {c["field"] for c in changes if c["target"] == "brief"} == {"owner", "known", "tender_level"}
    assert from_json(to_json(m)).meta["known"] == "Site is flat."
    m2, _ = apply_edits(m, [{"target": "brief", "field": "owner", "value": ""}])
    assert "owner" not in m2.meta
    with pytest.raises(EditError):
        apply_edits(base, [{"target": "brief", "field": "tender_level", "value": "Huge"}])
    with pytest.raises(EditError):
        apply_edits(base, [{"target": "brief", "field": "nope", "value": "x"}])
