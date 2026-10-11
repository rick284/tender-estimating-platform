"""Start a tender from scratch: an empty estimate (no quantities, no build-up rows, no subcontract
packages) that carries over only the reusable parts of an earlier tender -- the rate library,
the commercial settings (overhead and margin rates, bonds, GST ... but not dollar allowances) and the weather-tool station.
Nothing job-specific is copied, and nothing is priced until the estimator adds it.
"""
from __future__ import annotations
import copy
from decimal import Decimal
from typing import Any

from .importers.master_workbook import MasterWorkbookImport
from .models import WeatherToolRun
from .money import D

TENDER_LEVELS = ("Concept", "Feasibility", "Tender", "Variation")

# (key, label, max length). The platform's version of the Estimate Intake Block's core fields.
INTAKE_FIELDS: tuple[tuple[str, str, int], ...] = (
    ("client", "Client or head contractor", 160),
    ("location", "Location", 160),
    ("tender_level", "Estimate level", 20),
    ("contract_type", "Contract type", 120),
    ("pricing_basis", "Pricing basis", 200),
    ("scope", "Scope summary", 2000),
    ("drawings", "Drawings and documents received", 1000),
    ("programme", "Programme constraints", 1000),
    ("site_constraints", "Site constraints", 1000),
    ("inclusions_exclusions", "Inclusions and exclusions", 2000),
    ("assumptions", "Locked assumptions", 2000),
    ("missing_info", "Missing information (becomes RFIs)", 2000),
)


class IntakeError(ValueError):
    pass


def clean_intake(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, label, maxlen in INTAKE_FIELDS:
        v = str(raw.get(key) or "").strip()
        if len(v) > maxlen:
            raise IntakeError(f"{label} is too long (limit {maxlen} characters).")
        out[key] = v
    if out["tender_level"] and out["tender_level"] not in TENDER_LEVELS:
        raise IntakeError(f"Estimate level must be one of: {', '.join(TENDER_LEVELS)}.")
    return out


def blank_from_template(template: MasterWorkbookImport, project: str, intake: dict[str, Any]) -> MasterWorkbookImport:
    fields = clean_intake(intake)
    project = (project or "").strip()
    if not project:
        raise IntakeError("Give the tender a name.")
    meta = {"project": project, "gst": template.meta.get("gst", ""), "price_status": "DRAFT - started in platform",
            "snapshot": "Rev0 - started from scratch", **{k: v for k, v in fields.items() if v}}
    wm = dict(template.weather_meta)
    wm.update({"baseline_wd": "0", "delay_wd": "0", "dry_programme_wd": "0", "confidence": "NOT RUN",
               "rerun_status": "Weather tool not yet run for this tender"})
    # keep rates and switches (overhead, margin, GST ...), clear every job-specific dollar amount
    commercial = [{**c, "pc_sum": D(0)} for c in copy.deepcopy(template.commercial)]
    register = _register_from_intake(fields)
    controls = {k: "" for k in template.controls}
    controls["release_status"] = "NOT RELEASED"
    return MasterWorkbookImport(
        meta=meta, library=dict(template.library), qs=[], qs_extra={}, rows=[], row_extra=[], excel_rows=[],
        tool=WeatherToolRun(exposed_pool=D(0), rain_wet_ground_cost=D(0), critical_path_delay_wd=D(0),
                            additional_billed_weeks=D(0), wind_sensitivity_cost=D(0), include_wind=False),
        recovery=D(0), commercial=commercial,
        risk_feed={k: D(0) for k in template.risk_feed}, overlays=[], overlap=D(0), weather_meta=wm,
        weather_links={"daily_row": 0, "hours_per_day": template.weather_links.get("hours_per_day", 8),
                       "weekly_rows": [], "daily_uid": "", "weekly_uids": []},
        controls=controls, reference=None, register=register)


def _register_from_intake(fields: dict[str, str]) -> list[dict[str, Any]]:
    """The intake form's free-text boxes become register items, one per line, so they can be tracked and reported."""
    import uuid
    from . import register as reg
    new_id = lambda: "R-" + uuid.uuid4().hex[:8]
    items: list[dict[str, Any]] = []
    items += reg.from_text("document", fields.get("drawings", ""), items, new_id)
    items += reg.from_text("assumption", fields.get("assumptions", ""), items, new_id)
    for line in fields.get("inclusions_exclusions", "").replace("\r", "").split("\n"):
        text = line.strip(" -\u2022\t")
        if text:
            kind = "exclusion" if text.lower().startswith(("exclu", "excl", "by others", "not included", "no ")) else "inclusion"
            items += reg.from_text(kind, text, items, new_id)
    items += reg.from_text("rfi", fields.get("missing_info", ""), items, new_id)
    for it in items:
        if it["kind"] == "rfi":
            it["rag"] = "AMBER"
    return items
