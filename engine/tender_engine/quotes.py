"""Supplier and subcontractor quote register: the evidence behind the rates and packages in the estimate.

A quote is evidence, not automatically the controlling tender amount: scope, quantity, exclusions, delivery basis, validity, duplication and
specification compliance must reconcile to the estimate before use. Each item records where the evidence lives (`source`, e.g. a Drive file,
a Gmail message id or a quote number) so it can be traced.

Item: id ("S-xxxxxx"), ref ("Q-01"), package, supplier, estimate_ref (QS codes it feeds), qty, unit, amount (control $ excl GST, string),
scope (what was asked for), documents (what was issued), status, action (due / next step), notes (quote reference and what it says),
treatment (how the tender uses it), verification (the key point to verify), source, quote_date, valid_until.
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from typing import Any

FIELDS = ("ref", "package", "supplier", "estimate_ref", "qty", "unit", "amount", "scope", "documents", "status", "action", "notes", "treatment",
          "verification", "source", "quote_date", "valid_until")
LIMITS = {"ref": 20, "package": 200, "supplier": 200, "estimate_ref": 120, "qty": 30, "unit": 20, "amount": 30, "scope": 3000, "documents": 3000, "status": 300,
          "action": 3000, "notes": 3000, "treatment": 3000, "verification": 3000, "source": 500, "quote_date": 20, "valid_until": 20}
ITEM_ID = re.compile(r"^S-[A-Za-z0-9]{4,12}$")
MAX_ITEMS = 300


class QuoteError(ValueError):
    pass


def set_field(item: dict[str, Any], field: str, value: Any) -> None:
    if field not in FIELDS:
        raise QuoteError(f"{field!r} can't be edited on a quote.")
    v = "" if value is None else str(value).strip()
    if field == "amount" and v:
        try:
            x = Decimal(v.replace(",", "").lstrip("$"))
        except InvalidOperation:
            raise QuoteError("The amount needs a number.")
        if not x.is_finite() or x < 0:
            raise QuoteError("The amount can't be negative.")
        v = str(x)
    if len(v) > LIMITS[field]:
        raise QuoteError(f"{field.replace('_', ' ').capitalize()} is too long (limit {LIMITS[field]} characters).")
    item[field] = v


def build_item(item_id: str, v: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    item = {"id": item_id, **{f: "" for f in FIELDS}}
    for f in FIELDS:
        if f in v and v[f] not in (None, ""):
            set_field(item, f, v[f])
    if not item["package"] and not item["supplier"]:
        raise QuoteError("Name the package or the supplier.")
    if not item["ref"]:
        n = 1 + max([int(m.group(1)) for x in existing if (m := re.search(r"(\d+)\s*$", x["ref"]))] or [0])
        item["ref"] = f"Q-{n:02d}"
    if any(x["ref"] == item["ref"] for x in existing):
        raise QuoteError(f"{item['ref']} is already used.")
    return item
