"""Management Reserve adjudication (policy "Evidence-Weighted Uncertainty, Management Reserve & Labour True-Cost Policy", Rev1, sections 3-5).

The reserve is NOT a percentage or a pulled-out sum. It is selected, once per estimate revision, after reviewing the items that cannot realistically
be closed out before the price has to go in, each with a probability and an adverse consequence:

  weighted exposure = probability x adverse consequence   (consequence = the DELTA against the current priced baseline, not the item's whole value)

Rules enforced here:
  - probability is a range (low / high; one number = low = high). It has its own evidence status GREEN / AMBER / UNKNOWN. UNKNOWN is never turned into a
    dollar value (no default 50/50): the full consequence is kept as a sensitivity and the item is listed as unweighted.
  - an item whose consequence is not quantified gets no dollar value; it is listed as an unquantified tail for the adjudicator to consider.
  - consequences may be entered as SELL (what the client price moves by) or COST (pre overhead and margin). The reserve line CA16 is a pre-margin cost,
    so sell amounts are converted with the tender's own markup factor (taken from the commercial engine, not re-derived here).
  - overlapping items (same overlap group): only the PRIMARY item is counted; contributing / reference items are shown but not added. A group with no
    Primary, or with two, is an issue. An item already provided for in Risk Truth (CA01 / CA02) is not counted again.
  - the selected reserve is a FIXED amount for the revision with a recorded rationale; it does not grow when other lines change. It is compared with
    the weighted range (below / within / above) but is never computed from it.
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .money import D, ZERO

ITEM_FIELDS = ("ref", "title", "source_ref", "exposure_ref", "description", "basis", "impact", "impact_status", "probability_low", "probability_high",
               "prob_status", "prob_basis", "overlap_group", "owner", "action")
BLOCK_FIELDS = ("selected", "selected_basis", "adjudicated_by", "adjudicated_on")
LIMITS = {"ref": 30, "title": 300, "source_ref": 200, "exposure_ref": 30, "description": 3000, "basis": 10, "impact": 30, "impact_status": 20,
          "probability_low": 10, "probability_high": 10, "prob_status": 10, "prob_basis": 3000, "overlap_group": 80, "owner": 20, "action": 3000,
          "selected": 30, "selected_basis": 3000, "adjudicated_by": 120, "adjudicated_on": 40}
BASES = ("Sell", "Cost")
IMPACT_STATUS = ("Quantified", "Proxy", "Unquantified")
PROB_STATUS = ("GREEN", "AMBER", "UNKNOWN")
OWNERS = ("Primary", "Contributing", "Reference Only")
ITEM_ID = re.compile(r"^M-[A-Za-z0-9]{4,12}$")
MAX_ITEMS = 100


class ReserveError(ValueError):
    pass


def _num(v: Any) -> Decimal | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        x = Decimal(str(v).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return None
    return x if x.is_finite() else None


def new_block(selected: Any = "", basis: str = "") -> dict[str, Any]:
    return {"items": [], "selected": "" if selected in (None, "") else str(selected), "selected_basis": basis, "adjudicated_by": "", "adjudicated_on": ""}


def set_block_field(block: dict[str, Any], field: str, value: Any) -> None:
    if field not in BLOCK_FIELDS:
        raise ReserveError(f"{field!r} can't be edited on the management reserve.")
    v = "" if value is None else str(value).strip()
    if field == "selected" and v:
        x = _num(v)
        if x is None or x < 0:
            raise ReserveError("The selected reserve needs a number that is not negative.")
        v = str(x)
    if len(v) > LIMITS[field]:
        raise ReserveError(f"{field.replace('_', ' ').capitalize()} is too long (limit {LIMITS[field]} characters).")
    block[field] = v


def set_item_field(item: dict[str, Any], field: str, value: Any) -> None:
    if field not in ITEM_FIELDS:
        raise ReserveError(f"{field!r} can't be edited on a reserve item.")
    v = "" if value is None else str(value).strip()
    if field == "impact" and v:
        x = _num(v)
        if x is None or x < 0:
            raise ReserveError("The adverse consequence needs a number that is not negative (enter the extra cost against the current price).")
        v = str(x)
    if field in ("probability_low", "probability_high") and v:
        x = _num(v)
        if x is None or x < 0 or x > 1:
            raise ReserveError("A probability must be between 0 and 1 (for example 0.6 for 60%).")
        v = str(x)
    for fld, allowed, msg in (("basis", BASES, "Basis must be Sell or Cost."), ("impact_status", IMPACT_STATUS, "Impact status must be Quantified, Proxy or Unquantified."),
                              ("owner", OWNERS, "Owner must be Primary, Contributing or Reference Only.")):
        if field == fld and v and v not in allowed:
            raise ReserveError(msg)
    if field == "prob_status" and v:
        v = v.upper()
        if v not in PROB_STATUS:
            raise ReserveError("Probability evidence must be GREEN, AMBER or UNKNOWN.")
    if len(v) > LIMITS[field]:
        raise ReserveError(f"{field.replace('_', ' ').capitalize()} is too long (limit {LIMITS[field]} characters).")
    item[field] = v
    lo, hi = _num(item.get("probability_low")), _num(item.get("probability_high"))
    if lo is not None and hi is not None and hi < lo:
        raise ReserveError("The high probability can't be below the low probability.")


def build_item(item_id: str, v: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    item = {"id": item_id, **{f: "" for f in ITEM_FIELDS}}
    item["basis"], item["owner"], item["impact_status"], item["prob_status"] = "Sell", "Primary", "Quantified", "AMBER"
    for f in ITEM_FIELDS:
        if f in v and v[f] not in (None, ""):
            set_item_field(item, f, v[f])
    if item["probability_low"] and not item["probability_high"]:
        item["probability_high"] = item["probability_low"]
    if not item["title"]:
        raise ReserveError("Name the unresolved item.")
    if not item["ref"]:
        n = 1 + max([int(m.group(1)) for x in existing if (m := re.search(r"(\d+)\s*$", x["ref"]))] or [0])
        item["ref"] = f"MR-{n:02d}"
    if any(x["ref"] == item["ref"] for x in existing):
        raise ReserveError(f"{item['ref']} is already used.")
    return item


def compute(block: dict[str, Any], factor: Decimal, risk_exposures: list[dict[str, Any]] | None = None, subtotal: Decimal | None = None) -> dict[str, Any]:
    """block: stored reserve block. factor: sell effect of one dollar of pre-margin cost (from the commercial engine). risk_exposures: Risk Truth
    exposures (stored fields + 'addition') so an item already provided for in CA01/CA02 is not counted twice. subtotal: pre-OH/profit subtotal (for the
    reserve as a percentage, display only)."""
    f = D(factor) if D(factor) > 0 else Decimal(1)
    items = block["items"]
    provided = {x["ref"] for x in (risk_exposures or []) if D(x.get("addition", 0)) > 0}
    groups: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        g = it["overlap_group"].strip().casefold()
        if g:
            groups.setdefault(g, []).append(it)
    issues: list[str] = []
    for g, members in groups.items():
        prim = [m for m in members if m["owner"] == "Primary"]
        if len(members) > 1 and not prim:
            issues.append(f"Overlap group '{members[0]['overlap_group']}' has no Primary item, so none of it is counted")
        if len(prim) > 1:
            issues.append(f"Overlap group '{members[0]['overlap_group']}' has {len(prim)} Primary items: only one may carry the cost")
    out = []
    lo_c = hi_c = ZERO
    unknown = unquantified = amber = 0
    for it in items:
        impact = _num(it["impact"])
        cost_impact = None if impact is None or it["impact_status"] == "Unquantified" else (impact / f if it["basis"] == "Sell" else impact)
        plo, phi = _num(it["probability_low"]), _num(it["probability_high"])
        if plo is not None and phi is None:
            phi = plo
        prob_known = it["prob_status"] != "UNKNOWN" and plo is not None
        g = it["overlap_group"].strip().casefold()
        reasons = []
        counted = True
        if g and it["owner"] != "Primary":
            counted = False; reasons.append("Overlaps with another item: only the Primary item is counted")
        if g and not any(m["owner"] == "Primary" for m in groups[g]):
            counted = False
        if it["exposure_ref"] and it["exposure_ref"] in provided:
            counted = False; reasons.append(f"Already provided for in Risk Truth ({it['exposure_ref']})")
            issues.append(f"{it['ref']}: already provided for in Risk Truth {it['exposure_ref']}, not counted again")
        w_lo = w_hi = None
        sensitivity = cost_impact
        if cost_impact is None:
            reasons.append("Consequence not quantified: an unquantified tail")
            if counted:
                unquantified += 1
        elif not prob_known:
            reasons.append("Probability unknown: no dollar value assigned (the full consequence is shown as a sensitivity)")
            if counted:
                unknown += 1
        else:
            w_lo, w_hi = plo * cost_impact, phi * cost_impact
            if counted:
                lo_c += w_lo; hi_c += w_hi
        if counted and it["prob_status"] == "AMBER":
            amber += 1
        status = "RED" if (it["prob_status"] == "UNKNOWN" or not counted and any("Risk Truth" in r for r in reasons)) else "AMBER" if it["prob_status"] == "AMBER" else "GREEN"
        out.append({"id": it["id"], "cost_impact": cost_impact, "weighted_low": w_lo, "weighted_high": w_hi, "counted": counted and w_lo is not None,
                    "sensitivity": sensitivity if (not prob_known and cost_impact is not None) else None, "status": status, "reasons": reasons,
                    "weighted_low_sell": None if w_lo is None else w_lo * f, "weighted_high_sell": None if w_hi is None else w_hi * f})
    selected = _num(block.get("selected"))
    position = None
    if selected is not None and out:
        position = "below" if selected < lo_c else "above" if selected > hi_c else "within"
    notes = []
    if selected is not None and not block.get("selected_basis", "").strip():
        notes.append("No rationale recorded for the selected reserve")
    if selected is None:
        notes.append("No reserve selected yet")
    if selected is not None and not out:
        notes.append("No unresolved items recorded: nothing yet supports the selected reserve")
    if position == "below":
        notes.append("The selected reserve is below the lowest weighted exposure: record why")
    if unknown:
        notes.append(f"{unknown} item(s) with unknown probability carry no dollar value")
    if unquantified:
        notes.append(f"{unquantified} item(s) have an unquantified consequence (tails for the adjudicator)")
    status = "RED" if issues else "AMBER" if (notes or amber or position in ("below",)) else "GREEN"
    if selected is None and not out:
        status = "AMBER"
    return {"items": out, "weighted_low": lo_c, "weighted_high": hi_c, "weighted_mid": (lo_c + hi_c) / 2, "weighted_low_sell": lo_c * f, "weighted_high_sell": hi_c * f,
            "weighted_mid_sell": (lo_c + hi_c) / 2 * f, "selected": selected, "selected_sell": None if selected is None else selected * f,
            "selected_pct": None if (selected is None or not subtotal) else selected / D(subtotal), "position": position, "factor": f,
            "unknown_items": unknown, "unquantified_items": unquantified, "issues": issues, "notes": notes, "status": status}
