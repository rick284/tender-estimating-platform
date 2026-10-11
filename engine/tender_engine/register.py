"""Tender register: the narrative record behind an estimate, kept as structured items instead of loose text.

kinds   document   a basis document / drawing / specification        ref = revision or date, detail = how the estimate uses it
        inclusion  something the price includes                      title = area, detail = what is included
        exclusion  something excluded or by others
        assumption an estimating assumption or qualification
        rfi        a request for information / clarification         status OPEN | CLOSED, rag, action = closeout action
        risk       a key risk or watch-out                           detail = treatment in the price, action = outside-baseline / closeout,
                                                                     likelihood / impact / rating / owner
Every item: id ("R-xxxxxx"), kind, ref (display reference, e.g. RFI-15), title, detail, action, status, rag, owner, likelihood, impact, rating.
"""
from __future__ import annotations
import re
from typing import Any

KINDS = ("document", "inclusion", "exclusion", "assumption", "rfi", "risk")
FIELDS = ("ref", "title", "detail", "action", "status", "rag", "owner", "likelihood", "impact", "rating")
LIMITS = {"ref": 40, "title": 300, "detail": 3000, "action": 3000, "status": 80, "rag": 10, "owner": 80, "likelihood": 20, "impact": 20, "rating": 20}
ITEM_ID = re.compile(r"^R-[A-Za-z0-9]{4,12}$")
RAGS = ("", "RED", "AMBER", "GREEN")
MAX_ITEMS = 500
PREFIX = {"document": "DOC", "inclusion": "INC", "exclusion": "EX", "assumption": "A", "rfi": "RFI", "risk": "RT"}


class RegisterError(ValueError):
    pass


def set_field(item: dict[str, Any], field: str, value: Any) -> None:
    if field not in FIELDS:
        raise RegisterError(f"{field!r} can't be edited on a register item.")
    v = "" if value is None else str(value).strip()
    if field == "rag":
        v = v.upper()
        if v not in RAGS:
            raise RegisterError("Rating must be RED, AMBER, GREEN or blank.")
    if field == "status" and item["kind"] == "rfi":
        v = v.upper()
        if v not in ("OPEN", "CLOSED"):
            raise RegisterError("An RFI is OPEN or CLOSED.")
    if len(v) > LIMITS[field]:
        raise RegisterError(f"{field.capitalize()} is too long (limit {LIMITS[field]} characters).")
    item[field] = v


def build_item(item_id: str, v: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    kind = str(v.get("kind", ""))
    if kind not in KINDS:
        raise RegisterError(f"A register item must be one of: {', '.join(KINDS)}.")
    item = {"id": item_id, "kind": kind, **{f: "" for f in FIELDS}}
    if kind == "rfi":
        item["status"] = "OPEN"
    for f in FIELDS:
        if f in v and v[f] not in (None, ""):
            set_field(item, f, v[f])
    if not item["ref"]:                                         # next reference for the kind, e.g. RFI-05
        n = 1 + max([int(m.group(1)) for x in existing if x["kind"] == kind and (m := re.search(r"(\d+)", x["ref"]))] or [0])
        item["ref"] = f"{PREFIX[kind]}-{n:02d}" if kind != "assumption" else f"A{n}"
    if not item["title"] and not item["detail"]:
        raise RegisterError("Describe the item: it needs a title or some detail.")
    if any(x["ref"] == item["ref"] and x["kind"] == kind for x in existing):
        raise RegisterError(f"{item['ref']} is already used.")
    return item


def status_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    rfis = [x for x in items if x["kind"] == "rfi"]
    return {"rfis": len(rfis), "open_rfis": sum(1 for x in rfis if x["status"] != "CLOSED"),
            "open_red_rfis": sum(1 for x in rfis if x["status"] != "CLOSED" and x["rag"] == "RED"),
            "red_risks": sum(1 for x in items if x["kind"] == "risk" and x["rag"] == "RED")}


def from_text(kind: str, text: str, existing: list[dict[str, Any]], new_id) -> list[dict[str, Any]]:
    """One item per non-empty line of free text (used to turn the intake form's boxes into register items)."""
    out: list[dict[str, Any]] = []
    for raw in text.replace("\r", "").split("\n"):
        line = raw.strip(" -•\t")
        if line:
            out.append(build_item(new_id(), {"kind": kind, "title": line[:300], "detail": line if len(line) > 300 else ""}, existing + out))
    return out
