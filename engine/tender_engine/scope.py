"""Scope coverage and interface schedule: everything the job needs, each with an owner and an explicit treatment.

A detailed workbook is not proof of completeness. Every requirement (permanent works, enabling works, access, temporary works, testing, reinstatement,
interfaces with others) must say WHO delivers it and HOW the price treats it, and the platform checks that the treatment is actually backed up:

owner       OWN WORKS | SUBCONTRACT | CLIENT | OTHERS | SHARED | TBC
treatment   PRICED | ALLOWANCE | PC SUM | EXCLUDED | BY OTHERS | UNRESOLVED
cost_refs   QS codes (EW01) and / or commercial lines (CA09) that carry the cost
register_refs   assumption / exclusion / inclusion / RFI references (A3, EX-02, RFI-05) that explain it
quote_refs  quote references (Q-02) that support a subcontract or supplied item

Item: id ("C-xxxxxx"), ref ("SC-001"), group, title, detail, source (document / sheet / page), owner, treatment, cost_refs, register_refs, quote_refs, basis (what was priced and why), action.
The platform never decides a treatment: it checks it. Status per item: COMPLETE (backed up), CHECK (something to confirm), MISSING (no treatment, or unresolved with no RFI).
"""
from __future__ import annotations
import re
from decimal import Decimal
from typing import Any

GROUPS = ("Permanent works", "Enabling works", "Access and site establishment", "Temporary works", "Testing and inspection", "Reinstatement and handover",
          "Preliminaries and management", "Interface with others", "Other")
OWNERS = ("OWN WORKS", "SUBCONTRACT", "CLIENT", "OTHERS", "SHARED", "TBC")
TREATMENTS = ("PRICED", "ALLOWANCE", "PC SUM", "EXCLUDED", "BY OTHERS", "UNRESOLVED")
FIELDS = ("ref", "group", "title", "detail", "source", "owner", "treatment", "cost_refs", "register_refs", "quote_refs", "basis", "action")
LIMITS = {"ref": 20, "group": 60, "title": 300, "detail": 3000, "source": 500, "owner": 20, "treatment": 20, "cost_refs": 300, "register_refs": 300, "quote_refs": 200, "basis": 3000, "action": 3000}
ITEM_ID = re.compile(r"^C-[A-Za-z0-9]{4,12}$")
MAX_ITEMS = 600
LIST_FIELDS = ("cost_refs", "register_refs", "quote_refs")


class ScopeError(ValueError):
    pass


def tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[,;\s]+", str(text or "").strip()) if t]


def set_field(item: dict[str, Any], field: str, value: Any) -> None:
    if field not in FIELDS:
        raise ScopeError(f"{field!r} can't be edited on a scope item.")
    v = "" if value is None else str(value).strip()
    if field == "group":
        match = next((g for g in GROUPS if g.lower() == v.lower()), None)
        if v and not match:
            raise ScopeError(f"Group must be one of: {', '.join(GROUPS)}.")
        v = match or ""
    elif field == "owner":
        v = v.upper()
        if v and v not in OWNERS:
            raise ScopeError(f"Owner must be one of: {', '.join(OWNERS)}.")
    elif field == "treatment":
        v = v.upper()
        if v and v not in TREATMENTS:
            raise ScopeError(f"Treatment must be one of: {', '.join(TREATMENTS)}.")
    elif field in LIST_FIELDS:
        v = ", ".join(dict.fromkeys(t.upper() for t in tokens(v)))
    if len(v) > LIMITS[field]:
        raise ScopeError(f"{field.replace('_', ' ').capitalize()} is too long (limit {LIMITS[field]} characters).")
    item[field] = v


def build_item(item_id: str, v: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    item = {"id": item_id, **{f: "" for f in FIELDS}}
    for f in FIELDS:
        if f in v and v[f] not in (None, ""):
            set_field(item, f, v[f])
    if not item["title"]:
        raise ScopeError("Describe the requirement (a short title).")
    if not item["ref"]:
        n = 1 + max([int(m.group(1)) for x in existing if (m := re.search(r"(\d+)\s*$", x["ref"]))] or [0])
        item["ref"] = f"SC-{n:03d}"
    if any(x["ref"] == item["ref"] for x in existing):
        raise ScopeError(f"{item['ref']} is already used.")
    return item


def _amount(v: Any) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:                                            # noqa: BLE001
        return Decimal(0)


def compute(items: list[dict[str, Any]], costs: dict[str, Any], register: list[dict[str, Any]], quote_refs: set[str]) -> dict[str, Any]:
    """costs: {code or CA line: amount carried}; register: the tender register; quote_refs: references of the quote register. Returns items with status and problems, counts, gate."""
    reg = {x["ref"].upper(): x for x in register if x.get("ref")}
    out: list[dict[str, Any]] = []
    for it in items:
        missing: list[str] = []
        check: list[str] = []
        t, owner = it["treatment"], it["owner"]
        cost_refs, reg_refs, q_refs = tokens(it["cost_refs"]), tokens(it["register_refs"]), tokens(it["quote_refs"])
        known = [c for c in cost_refs if c in costs]
        for c in cost_refs:
            if c not in costs:
                check.append(f"{c} isn't in the estimate.")
        carried = [c for c in known if _amount(costs[c]) != 0]
        for c in known:
            if c not in carried:
                check.append(f"{c} carries no cost.")
        regs = [reg[r] for r in reg_refs if r in reg]
        for r in reg_refs:
            if r not in reg:
                check.append(f"{r} isn't in the register.")
        for q in q_refs:
            if q not in quote_refs:
                check.append(f"Quote {q} isn't in the quote register.")
        if not owner:
            missing.append("No owner: say who delivers it.")
        elif owner == "TBC":
            check.append("Owner still to be confirmed.")
        if not t:
            missing.append("No treatment: say how the price treats it.")
        elif t == "PRICED":
            if not cost_refs:
                missing.append("Priced, but no QS item or commercial line is linked.")
            elif not carried and not [c for c in cost_refs if c not in costs]:
                pass
        elif t in ("ALLOWANCE", "PC SUM"):
            if not cost_refs:
                missing.append(f"{t.title()} with no QS item or commercial line carrying it.")
            if not it["basis"]:
                check.append("State what the allowance is based on.")
            if not [x for x in regs if x["kind"] in ("assumption", "rfi")]:
                check.append("Link the assumption or RFI that explains this allowance.")
        elif t == "EXCLUDED":
            if not [x for x in regs if x["kind"] == "exclusion"]:
                check.append("Record the exclusion in the register and link it.")
            if carried:
                check.append("Excluded, but a cost is linked to it.")
        elif t == "BY OTHERS":
            if owner == "OWN WORKS":
                check.append("By others, but the owner is own works.")
            if not [x for x in regs if x["kind"] in ("exclusion", "assumption", "inclusion")]:
                check.append("Record the interface (exclusion or assumption) in the register and link it.")
            if carried:
                check.append("By others, but a cost is linked to it.")
        elif t == "UNRESOLVED":
            rfis = [x for x in regs if x["kind"] == "rfi"]
            if not rfis:
                missing.append("Unresolved with no RFI: raise one.")
            elif all(x.get("status") == "CLOSED" for x in rfis):
                check.append("The RFI is closed: update the treatment.")
            else:
                check.append("Waiting on an open RFI.")
        if owner == "SUBCONTRACT" and t in ("PRICED", "ALLOWANCE", "PC SUM") and not q_refs:
            check.append("Subcontract work with no quote linked.")
        problems = missing + check
        out.append({**it, "status": "MISSING" if missing else "CHECK" if check else "COMPLETE", "problems": problems})
    counts = {s: sum(1 for x in out if x["status"] == s) for s in ("COMPLETE", "CHECK", "MISSING")}
    referenced = {c for it in items for c in tokens(it["cost_refs"])}
    unhomed = sorted(c for c, a in costs.items() if re.fullmatch(r"[A-Z]{1,4}\d+[A-Z]?", c) and not c.startswith("CA") and _amount(a) != 0 and c not in referenced) if items else []
    by_treatment = {t: sum(1 for x in out if x["treatment"] == t) for t in TREATMENTS}
    if not items:
        gate = "NOT STARTED - no scope items recorded"
    elif counts["MISSING"] or unhomed:
        gate = f"HOLD - {counts['MISSING']} item(s) without a proper treatment" + (f"; {len(unhomed)} priced item(s) not in the scope schedule" if unhomed else "")
    elif counts["CHECK"]:
        gate = f"REVIEW - {counts['CHECK']} item(s) to confirm"
    else:
        gate = "PASS - every requirement has an owner and a backed-up treatment"
    return {"items": out, "counts": {**counts, "total": len(out)}, "by_treatment": by_treatment, "unhomed_qs": unhomed, "gate": gate}
