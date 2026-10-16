"""NZ labour true-cost build-up (Management Reserve & Labour True-Cost Policy Rev1, sections 6-12).

A library labour rate is the true direct employer cost of making a person available for productive work, per productive hour:

  weekly pay (paid hours x gross hourly rate)
  + employer KiwiSaver               % of weekly pay
  + holiday, statutory and sick leave   % of weekly pay (worked out from the leave days: non-working weeks / worked weeks)
  + insurance and ACC levies         % of the running total
  + redundancy provision (optional)  % of the running total
  + weekly allowances (tools, clothing, phone ...) $ per week
  + supervision (leading hand) loading   % of the running total
  = weekly true cost  ->  divided by PRODUCTIVE hours per week  = $ per productive hour

PAYE is not an employer cost and is never added. Corporate overhead, profit, fleet and preliminaries are not labour and are not in here.
The structure follows the NZIQS Quantity Surveyor's Handbook labour-rate build-up; every percentage is the company's own input (nothing is
assumed). Pure Decimal, no I/O. Status follows the policy: GREEN needs a company actual (current or reviewed historical) AND an independent
check; a normalised market or comparable rate is AMBER; a raw wage, or an unknown basis, is RED.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .money import D, ZERO, ONE

EVIDENCE = ("company actual", "company historical", "comparable contractor", "market normalised", "raw wage")
WEEKS_PER_YEAR = Decimal(365) / Decimal(7)
NUMERIC = ("hourly_rate", "paid_hours_week", "productive_hours_week", "kiwisaver_pct", "annual_leave_days", "stat_days", "sick_days", "other_paid_days",
           "days_per_week", "levy_pct", "redundancy_pct", "weekly_allowance", "supervision_pct")
TEXT = ("role", "jurisdiction", "employment_basis", "source_date", "evidence", "source_note", "reviewer")
FIELDS = TEXT + NUMERIC + ("independent_check",)
PCT = ("kiwisaver_pct", "levy_pct", "redundancy_pct", "supervision_pct")


class LabourError(ValueError):
    pass


def clean(raw: dict[str, Any]) -> dict[str, Any]:
    """Validated inputs (numbers as Decimal-safe strings kept as typed, percentages as fractions: 0.03 = 3%)."""
    out: dict[str, Any] = {}
    for k in TEXT:
        v = str(raw.get(k) or "").strip()
        if len(v) > 300:
            raise LabourError(f"{k.replace('_', ' ').capitalize()} is too long.")
        out[k] = v
    if not out["role"]:
        raise LabourError("Say which role this rate is for.")
    if out["evidence"] not in EVIDENCE:
        raise LabourError(f"Evidence must be one of: {', '.join(EVIDENCE)}.")
    for k in NUMERIC:
        try:
            v = D(str(raw.get(k) if raw.get(k) not in (None, "") else "0").replace(",", ""))
        except Exception:                                                       # noqa: BLE001
            raise LabourError(f"{k.replace('_', ' ').capitalize()} must be a number.")
        if v < 0:
            raise LabourError(f"{k.replace('_', ' ').capitalize()} can't be negative.")
        if k in PCT and v > ONE:
            raise LabourError(f"{k.replace('_', ' ').capitalize()} is a fraction (0.03 means 3%).")
        out[k] = str(v)
    out["independent_check"] = bool(raw.get("independent_check"))
    for k in ("hourly_rate", "paid_hours_week", "productive_hours_week", "days_per_week"):
        if D(out[k]) <= 0:
            raise LabourError(f"{k.replace('_', ' ').capitalize()} must be more than zero.")
    if D(out["productive_hours_week"]) > D(out["paid_hours_week"]):
        raise LabourError("Productive hours can't exceed paid hours.")
    return out


def leave_loading(i: dict[str, Any]) -> tuple[Decimal, Decimal, Decimal]:
    """(non-working weeks, worked weeks, loading %) from the leave days: loading = non-working / worked."""
    dpw = D(i["days_per_week"])
    nonwork = (D(i["annual_leave_days"]) + D(i["stat_days"]) + D(i["sick_days"]) + D(i["other_paid_days"])) / dpw
    worked = WEEKS_PER_YEAR - nonwork
    if worked <= 0:
        raise LabourError("The leave days leave no working weeks in the year.")
    return nonwork, worked, nonwork / worked


def compute(raw: dict[str, Any]) -> dict[str, Any]:
    i = clean(raw)
    pay = D(i["paid_hours_week"]) * D(i["hourly_rate"])
    nonwork, worked, leave_pct = leave_loading(i)
    steps: list[dict[str, Any]] = []
    run = pay

    def step(label: str, basis: str, amount: Decimal, add: bool = True):
        nonlocal run
        if add:
            run += amount
        steps.append({"label": label, "basis": basis, "amount": amount, "running": run})

    steps.append({"label": "Weekly pay", "basis": f"{i['paid_hours_week']} paid hours x ${D(i['hourly_rate']):,.2f}", "amount": pay, "running": pay})
    step("Employer KiwiSaver", f"{D(i['kiwisaver_pct']) * 100:.2f}% of weekly pay", pay * D(i["kiwisaver_pct"]))
    step("Holiday, statutory and sick leave", f"{leave_pct * 100:.2f}% of weekly pay ({nonwork:.2f} non-working weeks / {worked:.2f} worked weeks)", pay * leave_pct)
    step("Insurance and ACC levies", f"{D(i['levy_pct']) * 100:.2f}% of the total so far", run * D(i["levy_pct"]))
    step("Redundancy provision", f"{D(i['redundancy_pct']) * 100:.2f}% of the total so far", run * D(i["redundancy_pct"]))
    step("Weekly allowances (tools, clothing)", "per week", D(i["weekly_allowance"]))
    step("Supervision (leading hand) loading", f"{D(i['supervision_pct']) * 100:.2f}% of the total so far", run * D(i["supervision_pct"]))
    weekly = run
    rate = weekly / D(i["productive_hours_week"])
    paid_rate = weekly / D(i["paid_hours_week"])
    return {"inputs": i, "steps": steps, "weekly_cost": weekly, "rate": rate, "rate_rounded": rate.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "per_paid_hour": paid_rate, "leave_pct": leave_pct, "productivity": D(i["productive_hours_week"]) / D(i["paid_hours_week"]),
            **status(i)}


def status(i: dict[str, Any]) -> dict[str, Any]:
    if i["evidence"] == "raw wage":
        return {"status": "RED", "status_note": "A raw wage is not a true-cost rate. Use the build-up with real on-costs and a source."}
    if not i["employment_basis"] or not i["source_date"]:
        return {"status": "RED", "status_note": "The employment basis and the source date must be recorded."}
    if i["evidence"] in ("company actual", "company historical") and i["independent_check"]:
        return {"status": "GREEN", "status_note": "Company actual with an independent check."}
    if i["evidence"] in ("company actual", "company historical"):
        return {"status": "AMBER", "status_note": "Company actual, but the independent check isn't recorded yet."}
    return {"status": "AMBER", "status_note": "Normalised from market or comparable evidence: AMBER until company actuals are available."}


def description(i: dict[str, Any]) -> str:
    base = f"{i['role']} - true direct employment cost per productive hour"
    if i["evidence"] in ("market normalised", "comparable contractor"):
        return (base + " (external market normalised benchmark: excludes corporate overhead, profit and costs priced elsewhere)")[:200]
    return (base + " (excludes overhead and profit)")[:200]


def library_source(i: dict[str, Any], st: dict[str, Any]) -> str:
    return (f"Labour build-up: {i['evidence']}, {i['jurisdiction'] or 'NZ'}, {i['employment_basis']}, source dated {i['source_date']}, "
            f"{st['status']}" + (f", reviewed by {i['reviewer']}" if i["reviewer"] else ""))[:300]


def to_json(c: dict[str, Any]) -> dict[str, Any]:
    """Plain numbers for the API / screen."""
    f = float
    return {"inputs": c["inputs"], "weekly_cost": f(c["weekly_cost"]), "rate": f(c["rate_rounded"]), "per_paid_hour": f(c["per_paid_hour"].quantize(Decimal("0.01"))),
            "leave_pct": f(c["leave_pct"]), "productivity": f(c["productivity"]), "status": c["status"], "status_note": c["status_note"],
            "steps": [{"label": s["label"], "basis": s["basis"], "amount": f(s["amount"]), "running": f(s["running"])} for s in c["steps"]]}
