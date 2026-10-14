"""Project brief: what the job is, who owns it, who is involved and what we know about it.
Stored in the estimate's meta (same place as the start-from-scratch intake), so it also shows on the Overview and in reports.
Free text only -- nothing here is priced or calculated.
"""
from __future__ import annotations
from typing import Any

# (key, label, max length, group). Keys that already exist in blank.INTAKE_FIELDS keep the same name.
FIELDS: tuple[tuple[str, str, int, str], ...] = (
    ("job_summary", "What the job is", 3000, "The job"),
    ("location", "Location / site address", 160, "The job"),
    ("tender_level", "Estimate level", 20, "The job"),
    ("purpose", "Purpose of this estimate", 400, "The job"),
    ("client", "Client or head contractor", 160, "Who"),
    ("owner", "Project owner / developer", 160, "Who"),
    ("consultants", "Designers and consultants", 1000, "Who"),
    ("contacts", "Key contacts (name, role, email/phone)", 2000, "Who"),
    ("contract_type", "Contract type", 120, "Commercial"),
    ("pricing_basis", "Pricing basis", 200, "Commercial"),
    ("tender_due", "Tender due (date / time)", 120, "Commercial"),
    ("submission", "How and where to submit", 400, "Commercial"),
    ("validity", "Price validity / start and completion", 300, "Commercial"),
    ("history", "History with this client / job", 1500, "What we know"),
    ("known", "What we know so far", 3000, "What we know"),
    ("unknown", "What we do not know yet", 3000, "What we know"),
)
KEYS = {k for k, _l, _n, _g in FIELDS}
LIMITS = {k: n for k, _l, n, _g in FIELDS}
LABELS = {k: l for k, l, _n, _g in FIELDS}
LEVELS = ("Concept", "Feasibility", "Tender", "Variation")


class BriefError(ValueError):
    pass


def set_field(meta: dict[str, Any], field: str, value: Any) -> None:
    if field not in KEYS:
        raise BriefError(f"Unknown brief field {field!r}.")
    v = str(value or "").strip()
    if len(v) > LIMITS[field]:
        raise BriefError(f"{LABELS[field]} is too long (limit {LIMITS[field]} characters).")
    if field == "tender_level" and v and v not in LEVELS:
        raise BriefError(f"Estimate level must be one of: {', '.join(LEVELS)}.")
    if v:
        meta[field] = v
    else:
        meta.pop(field, None)
