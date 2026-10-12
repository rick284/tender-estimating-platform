"""Risk Truth: the risk-reconciliation layer (Master Prompt Rev5, Triple Verification Rev4, workbook tab "Risk Truth").

Risk Truth is a CONTROL layer, not a second direct-cost estimate. Each exposure records where the risk is already priced (baseline), what residual
remains, how (if at all) the residual is modelled, and where it would be integrated. Only an approved, DISTINCT residual provision aimed at
CA01 (design / scope residual) or CA02 (construction / execution residual) adds cost to the tender. Likelihood and impact never create dollars.

Formulas follow the approved workbook (verified against it by tools/make_risk_golden.py + tests/test_risk_truth.py):
  modelled residual : Already in Base -> 0 | Unit Rate Delta -> qty x rate | Probability x Impact -> probability x amount |
                      Fixed Allowance / Specialist Engine -> typed provision | By Others / Excluded -> 0 | RFI Hold, Scenario Weighted -> none
  addition          : typed provision when "Include new risk cost" = Yes, else 0
  duplication check : RED residual not distinct | RED undeclared overlap (same cost ref on several rows, no overlap group) | declared overlap | OK
  final status      : RED duplication; RED evidence; RFI Hold; Unit Rate Delta without a quantity -> RED | AMBER evidence, CHECK embedded variability -> AMBER | GREEN
  CA01 / CA02 total : SUM of additions whose integration target is CA01 / CA02
  release gate      : HOLD when red risks > 0, red exposures > 0, duplicate-cost RED, or programme reconciliation RED; otherwise PASS

Deliberate platform differences from the workbook (the workbook's formulas are weaker than the standards):
  1. Evidence status is a controlled value (RED / AMBER / GREEN). A populated exposure with NO evidence status is RED, not GREEN
     (Master Prompt: missing evidence remains RED; Triple Verification: GREEN needs the three checks).
  2. A positive addition whose integration target is not CA01 or CA02 is RED: the workbook would silently drop it from every total.
  3. A positive addition that is not marked "integration complete" holds the platform release gate (Triple Verification, Risk Truth item 14).
  4. Negative provisions are rejected.
  `gate_workbook` carries the workbook's exact gate for comparison.
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .money import D, ZERO

MODES = ("Already in Base / No Add", "Unit Rate Delta", "Probability x Impact", "Scenario Weighted", "Fixed Allowance", "Specialist Engine",
         "By Others / Excluded", "RFI Hold")
OWNERS = ("Primary", "Contributing", "Reference Only")
YESNO = ("Yes", "No", "N/A")
EVIDENCE = ("GREEN", "AMBER", "RED")
FIELDS = ("ref", "risk_id", "consequence", "driver", "cost_ref", "treatment", "baseline_amount", "residual", "mode", "qty", "unit", "unit_rate",
          "probability", "provision", "owner", "distinct", "target", "include", "overlap_group", "embedded", "evidence", "evidence_note",
          "integration_complete", "basis", "action", "source")
LIMITS = {"ref": 30, "risk_id": 30, "consequence": 1500, "driver": 120, "cost_ref": 200, "treatment": 1500, "baseline_amount": 30, "residual": 1500,
          "mode": 40, "qty": 30, "unit": 20, "unit_rate": 30, "probability": 10, "provision": 30, "owner": 20, "distinct": 5, "target": 120,
          "include": 5, "overlap_group": 80, "embedded": 600, "evidence": 5, "evidence_note": 600, "integration_complete": 5, "basis": 3000,
          "action": 3000, "source": 800}
NUMERIC = ("baseline_amount", "qty", "unit_rate", "provision")
ITEM_ID = re.compile(r"^X-[A-Za-z0-9]{4,12}$")
MAX_ITEMS = 200


class RiskTruthError(ValueError):
    pass


def _num(v: Any) -> Decimal | None:
    """Blank -> None. Anything else must be a finite number."""
    if v is None or str(v).strip() == "":
        return None
    try:
        x = Decimal(str(v).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return None
    return x if x.is_finite() else None


def set_field(item: dict[str, Any], field: str, value: Any) -> None:
    if field not in FIELDS:
        raise RiskTruthError(f"{field!r} can't be edited on a risk exposure.")
    v = "" if value is None else str(value).strip()
    if field in NUMERIC and v:
        x = _num(v)
        if x is None:
            raise RiskTruthError(f"{field.replace('_', ' ').capitalize()} needs a number.")
        if x < 0:
            raise RiskTruthError(f"{field.replace('_', ' ').capitalize()} can't be negative.")
        v = str(x)
    if field == "probability" and v:
        x = _num(v)
        if x is None or x < 0 or x > 1:
            raise RiskTruthError("Probability must be between 0 and 1 (for example 0.6 for 60%).")
        v = str(x)
    if field == "mode" and v and v not in MODES:
        raise RiskTruthError(f"Calculation mode must be one of: {', '.join(MODES)}.")
    if field == "owner" and v and v not in OWNERS:
        raise RiskTruthError("Cost treatment owner must be Primary, Contributing or Reference Only.")
    if field in ("distinct", "include", "integration_complete") and v and v not in YESNO:
        raise RiskTruthError(f"{field.replace('_', ' ').capitalize()} must be Yes, No or N/A.")
    if field == "evidence" and v:
        v = v.upper()
        if v not in EVIDENCE:
            raise RiskTruthError("Evidence status must be GREEN, AMBER or RED.")
    if len(v) > LIMITS[field]:
        raise RiskTruthError(f"{field.replace('_', ' ').capitalize()} is too long (limit {LIMITS[field]} characters).")
    item[field] = v


def build_item(item_id: str, v: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    item = {"id": item_id, **{f: "" for f in FIELDS}}
    item["include"] = "No"
    for f in FIELDS:
        if f in v and v[f] not in (None, ""):
            set_field(item, f, v[f])
    if not item["consequence"] and not item["ref"]:
        raise RiskTruthError("Describe the exposure (what the cost consequence is).")
    if not item["ref"]:
        base = item["risk_id"] or "RT"
        n = 1 + sum(1 for x in existing if x["risk_id"] == item["risk_id"])
        item["ref"] = f"{base}-{n:03d}"
    if any(x["ref"] == item["ref"] for x in existing):
        raise RiskTruthError(f"{item['ref']} is already used.")
    return item


def _norm(s: str) -> str:
    return s.strip().casefold()


def modelled_residual(it: dict[str, Any]) -> Decimal | None:
    mode = it["mode"]
    if mode == "Already in Base / No Add" or mode == "By Others / Excluded":
        return ZERO
    if mode == "Unit Rate Delta":
        q, r = _num(it["qty"]), _num(it["unit_rate"])
        return None if q is None or r is None else q * r
    if mode == "Probability x Impact":
        p, r = _num(it["probability"]), _num(it["unit_rate"])
        return None if p is None or r is None else p * r
    if mode in ("Fixed Allowance", "Specialist Engine"):
        return _num(it["provision"]) or ZERO
    return None                       # RFI Hold, Scenario Weighted, blank mode: no modelled value


def is_target(t: str, ca: str) -> bool:
    return _norm(t) == ca.casefold()


def compute(items: list[dict[str, Any]], risks: list[dict[str, Any]] | None = None, programme_ok: bool | None = None) -> dict[str, Any]:
    """items: stored exposures. risks: register items of kind 'risk' (their rag drives the RED risk count). Pure; returns display floats as strings-free Decimals."""
    cost_counts: dict[str, int] = {}
    for it in items:
        k = _norm(it["cost_ref"])
        if k:
            cost_counts[k] = cost_counts.get(k, 0) + 1
    out, issues = [], []
    for it in items:
        modelled = modelled_residual(it)
        prov = _num(it["provision"]) or ZERO
        include = it["include"] == "Yes"
        addition = prov if include else ZERO
        k = _norm(it["cost_ref"])
        if include and prov > 0 and it["distinct"] != "Yes":
            dup = "RED - RESIDUAL NOT DISTINCT"
        elif k and cost_counts[k] > 1 and not it["overlap_group"].strip():
            dup = "RED - UNDECLARED OVERLAP"
        elif k and cost_counts[k] > 1:
            dup = "DECLARED OVERLAP"
        else:
            dup = "OK"
        ev = it["evidence"]
        reasons = []
        if dup.startswith("RED"):
            status = "RED"; reasons.append(dup.title().replace("Red - ", ""))
        elif ev == "RED" or it["mode"] == "RFI Hold" or (it["mode"] == "Unit Rate Delta" and _num(it["qty"]) is None):
            status = "RED"
            reasons.append("Evidence is RED" if ev == "RED" else "RFI hold: the residual can't yet be responsibly quantified" if it["mode"] == "RFI Hold"
                           else "Unit-rate delta has no quantity")
        elif ev == "":
            status = "RED"; reasons.append("No evidence status recorded")
        elif ev == "AMBER" or it["embedded"].strip().upper().startswith("CHECK"):
            status = "AMBER"; reasons.append("Evidence is AMBER" if ev == "AMBER" else "Check whether variability is already embedded")
        else:
            status = "GREEN"
        # the workbook's own Z formula (exact-match evidence, blank evidence passes) for comparison with the platform status
        if dup.startswith("RED"):
            workbook_status = "RED"
        elif ev == "RED" or it["mode"] == "RFI Hold" or (it["mode"] == "Unit Rate Delta" and _num(it["qty"]) is None):
            workbook_status = "RED"
        elif ev == "AMBER" or it["embedded"].strip().upper().startswith("CHECK"):
            workbook_status = "AMBER"
        else:
            workbook_status = "GREEN"
        flows = is_target(it["target"], "CA01") or is_target(it["target"], "CA02")
        if addition > 0 and not flows:
            status = "RED"; reasons.append("Positive provision has no CA01/CA02 integration target, so it would not reach the tender")
        if addition > 0 and it["integration_complete"] != "Yes":
            issues.append(f"{it['ref']}: positive provision is not marked integration complete")
        out.append({"id": it["id"], "modelled": modelled, "addition": addition, "duplication": dup, "status": status, "workbook_status": workbook_status,
                    "reasons": reasons, "flows": flows, "provision_unused": include is False and prov > 0})
    ca1 = sum((o["addition"] for it, o in zip(items, out) if is_target(it["target"], "CA01")), ZERO)
    ca2 = sum((o["addition"] for it, o in zip(items, out) if is_target(it["target"], "CA02")), ZERO)
    red_risks = sum(1 for r in (risks or []) if str(r.get("rag", "")).upper() == "RED")
    red_exp = sum(1 for o in out if o["status"] == "RED")
    red_exp_wb = sum(1 for o in out if o["workbook_status"] == "RED")
    dup_red = any(o["duplication"].startswith("RED") for o in out)
    prog_red = programme_ok is False
    gate_wb = "HOLD - RED ITEMS / INTEGRATION CHECK" if (red_risks > 0 or red_exp_wb > 0 or dup_red or prog_red) else "PASS"
    incomplete = bool(issues)
    gate = "HOLD - RED ITEMS / INTEGRATION CHECK" if (red_risks > 0 or red_exp > 0 or dup_red or prog_red or incomplete) else "PASS"
    return {"exposures": out, "ca01": ca1, "ca02": ca2, "residual_total": ca1 + ca2, "red_risks": red_risks, "red_exposures": red_exp,
            "red_exposures_workbook": red_exp_wb, "amber_exposures": sum(1 for o in out if o["status"] == "AMBER"),
            "duplicate_gate": "RED" if dup_red else "OK", "programme_gate": "RED - PROGRAMME COST RECONCILIATION" if prog_red else "OK",
            "gate": gate, "gate_workbook": gate_wb, "issues": issues}
