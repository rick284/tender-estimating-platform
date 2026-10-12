"""AI takeoff proposals from drawings. Pure functions: prompt, output schema, deterministic checking.

The AI only PROPOSES a takeoff line: what it is, which numbers it used and where they come from. The PLATFORM does the arithmetic (sum / product of the
stated components), checks that every number the AI says it READ is really written on the cited page, and marks anything scaled off a picture or counted
by eye as needing the estimator's check. Nothing is locked (rule 2) and nothing reaches the estimate until the estimator approves it (rule 3).
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from typing import Any

PROMPT_VERSION = "takeoff-v1"
SECTIONS = ("earthworks", "pavements", "retaining", "kerbs_external", "drainage", "parking", "esc", "other")
SOURCES = ("read_text", "schedule", "stated_area", "counted", "scaled", "constant")
CONSTANTS = (Decimal("3.14159265"), Decimal("0.78539816"), Decimal("0.7854"), Decimal("3.1416"), Decimal("3.14159"), Decimal("0.785398"))   # pi, pi/4: the only constants a component may be without a quote
CHECKED_SOURCES = ("read_text", "schedule", "stated_area")          # these must quote text that is on the page
TOL = Decimal("0.005")                                              # claimed quantity may differ from the recomputed one by 0.5%
MIN_QUOTE = 4

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "description": {"type": "string"}, "section": {"type": "string", "enum": list(SECTIONS)}, "unit": {"type": "string", "enum": ["m2", "m3", "lm", "ea", "LS"]},
            "operation": {"type": "string", "enum": ["single", "sum", "product"]},
            "components": {"type": "array", "items": {"type": "object", "properties": {
                "label": {"type": "string"}, "value": {"type": "number"}, "unit": {"type": "string"}, "doc": {"type": "string"}, "sheet": {"type": "string"}, "page": {"type": "integer"},
                "source": {"type": "string", "enum": list(SOURCES)}, "quote": {"type": "string"}},
                "required": ["label", "value", "unit", "doc", "sheet", "page", "source", "quote"], "additionalProperties": False}},
            "quantity": {"type": "number"}, "method": {"type": "string", "enum": ["READ", "COUNTED", "SCALED", "CALCULATED"]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]}, "notes": {"type": "string"}},
            "required": ["description", "section", "unit", "operation", "components", "quantity", "method", "confidence", "notes"], "additionalProperties": False}},
        "not_measurable": {"type": "array", "items": {"type": "object", "properties": {"what": {"type": "string"}, "why": {"type": "string"}}, "required": ["what", "why"], "additionalProperties": False}},
    },
    "required": ["items", "not_measurable"], "additionalProperties": False,
}

SYSTEM = """You are assisting a senior NZ civil and commercial estimator with a quantity takeoff. You PROPOSE takeoff lines; the estimator checks and approves every one.

Rules:
1. Prefer numbers WRITTEN on the drawings (dimensions, area schedules, notes, site calculations) over numbers you scale from the picture. Mark each component's `source`: read_text, schedule, stated_area, counted (items you counted), or scaled (measured off the image).
2. For any number you READ, give a short `quote` copied exactly from that page's text, and the sheet code and page. For counted or scaled components leave `quote` empty and say in `notes` how you counted or scaled (what you measured, which scale bar or printed scale).
3. List the components and the operation (single / sum / product). The platform does the arithmetic from your components; `quantity` must match it.
4. Never invent a number to fill a gap. If a quantity cannot be established, put it in `not_measurable` with the reason (for example: civil drawing not supplied, level information missing).
5. Stay inside the package scope. Do not price anything. Where drawings conflict, propose both readings as separate lines with notes, never silently pick one.
6. `confidence` is high only when the number is written on the drawing and you cross-checked it."""


def _compact(s: str) -> str:
    return re.sub(r"[\W_]+", "", s or "", flags=re.UNICODE).lower()


def _dec(x: Any) -> Decimal | None:
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        return None


def _number_in(v: Decimal, quote: str) -> bool:
    """True if v appears as a whole number in the quote, as written or converted from millimetres (a drawing says 2000, the line uses 2.0)."""
    toks = set()
    for m in re.finditer(r"\d[\d,]*\.?\d*", quote):
        d = _dec(m.group(0).replace(",", "").rstrip("."))
        if d is not None:
            toks.add(d)
    return any(v == t or v * 1000 == t for t in toks)


def compute(operation: str, values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    if operation == "single":
        return values[0] if len(values) == 1 else None
    if operation == "sum":
        return sum(values, Decimal(0))
    if operation == "product":
        r = Decimal(1)
        for v in values:
            r *= v
        return r
    return None


def verify(items: list[dict[str, Any]], pages: dict[Any, Any]) -> list[dict[str, Any]]:
    """pages: page number -> page text for one document, or {document name: {page number: page text}} for several (a component then names its `doc`). Adds to each item: computed (the platform's own arithmetic), components[i].found, status, problems[].
    status: verified (every read number found on its page and the arithmetic agrees), check (scaled or counted components: the estimator must check them on the drawing),
    unverified (a quoted number is not on the page, or the arithmetic disagrees)."""
    multi = bool(pages) and all(isinstance(v, dict) for v in pages.values())
    docs = {k: {n: _compact(t) for n, t in v.items()} for k, v in pages.items()} if multi else {"": {n: _compact(t) for n, t in pages.items()}}
    out = []
    for raw in items:
        it = {k: raw.get(k, "") for k in ("description", "section", "unit", "operation", "method", "confidence", "notes")}
        it["quantity_claimed"] = raw.get("quantity")
        problems, comps = [], []
        vals: list[Decimal] = []
        needs_check = False
        for c in raw.get("components") or []:
            v, pg, src, quote = _dec(c.get("value")), c.get("page"), c.get("source"), str(c.get("quote", ""))
            found = None
            if v is None:
                problems.append(f"Component “{c.get('label', '')}” has no number")
            else:
                vals.append(v)
            compact = docs.get(str(c.get("doc", "")) if multi else "", {})
            if src in CHECKED_SOURCES:
                q = _compact(quote)
                if len(q) < MIN_QUOTE:
                    problems.append(f"“{c.get('label', '')}”: a number read from the drawing needs a quote")
                    found = False
                elif pg not in compact:
                    problems.append(f"“{c.get('label', '')}”: page {pg} does not exist" + (f" in {c.get('doc')}" if multi else ""))
                    found = False
                elif q not in compact[pg]:
                    problems.append(f"“{c.get('label', '')}”: the quote is not on page {pg}")
                    found = False
                else:
                    found = True
                    # the number itself must be inside the quote (the AI may not quote one thing and use another)
                    if v is not None and not _number_in(v, quote):
                        found = False
                        problems.append(f"“{c.get('label', '')}”: the number {v.normalize():f} is not in the quote")
            elif src in ("counted", "scaled"):
                needs_check = True
            elif src == "constant":
                if v is None or not any(abs(v - k) <= Decimal("0.0001") for k in CONSTANTS):
                    problems.append(f"“{c.get('label', '')}”: only pi or pi/4 may be used as a constant")
            else:
                problems.append(f"“{c.get('label', '')}”: unknown source")
            comps.append({**{k: c.get(k) for k in ("label", "value", "unit", "doc", "sheet", "page", "source", "quote")}, "found": found})
        calc = compute(str(raw.get("operation")), vals) if not any(v is None for v in vals) else None
        it["computed"] = float(calc) if calc is not None else None
        claimed = _dec(raw.get("quantity"))
        if calc is None:
            problems.append("The components do not add up to a quantity under the stated operation")
        elif claimed is None or (abs(calc - claimed) > TOL * max(abs(calc), Decimal("1"))):
            problems.append(f"Stated quantity {raw.get('quantity')} does not match the platform's arithmetic ({float(calc):.6g})")
        it["components"], it["problems"] = comps, problems
        it["status"] = "unverified" if problems else ("check" if needs_check else "verified")
        out.append(it)
    return out


def build_user_message(project: str, sheets: dict[str, int], pages: list[dict[str, Any]], numbers_only: bool = False) -> str:
    lines = [f"PROJECT: {project}", "", "SHEET INDEX (code -> page)", ", ".join(f"{k}: p{v}" for k, v in sheets.items()), "", "PAGE TEXT"]
    for p in pages:
        if p["text"].strip():
            lines += [f"[page {p['n']}]", p["text"].strip(), ""]
    return "\n".join(lines)
