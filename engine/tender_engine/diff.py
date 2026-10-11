"""Revision comparison: what changed between two computed estimates, and by how much.

Pure function over the dicts produced by compute_estimate(). Nothing here changes any number;
it explains movements so the estimator (and the change-control record) can see exactly why a
price moved between revisions.
"""
from __future__ import annotations
from typing import Any

HEADLINE = [
    ("all_in", "Working all-in tender"),
    ("siteworks_tender", "Siteworks tender"),
    ("known_cost", "Known cost before OH/profit"),
    ("base_direct", "Base direct estimate"),
    ("management_reserve", "Management Reserve"),
    ("weather_allowance", "Weather allowance"),
]
EPS = 0.005


def _delta(a, b):
    """Difference of the cent-rounded values, so a delta always equals what the user sees (b - a)."""
    return round(round(b or 0, 2) - round(a or 0, 2), 2)


def diff_estimates(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Describe the change from estimate `a` (earlier) to `b` (later)."""
    headline = [{"key": k, "label": label, "a": a["summary"].get(k), "b": b["summary"].get(k),
                 "delta": _delta(a["summary"].get(k), b["summary"].get(k))} for k, label in HEADLINE]

    # sections
    sa = {s["section"]: s["amount"] for s in a["sections"]}
    sb = {s["section"]: s["amount"] for s in b["sections"]}
    sections = []
    for name in list(sb) + [n for n in sa if n not in sb]:
        d = _delta(sa.get(name), sb.get(name))
        sections.append({"section": name, "a": sa.get(name), "b": sb.get(name), "delta": d})

    # QS items
    qa = {q["code"]: q for q in a["qs"]}
    qb = {q["code"]: q for q in b["qs"]}
    qs_changes = []
    for code in list(qb) + [c for c in qa if c not in qb]:
        x, y = qa.get(code), qb.get(code)
        if x is None:
            kind = "added"
        elif y is None:
            kind = "removed"
        elif abs(_delta(x["amount"], y["amount"])) > EPS or abs((y["quantity"] or 0) - (x["quantity"] or 0)) > 1e-9:
            kind = "changed"
        else:
            continue
        ref = y or x
        qs_changes.append({
            "code": code, "description": ref["description"], "unit": ref["unit"], "kind": kind,
            "qty_a": x["quantity"] if x else None, "qty_b": y["quantity"] if y else None,
            "amount_a": x["amount"] if x else None, "amount_b": y["amount"] if y else None,
            "delta": _delta(x["amount"] if x else 0, y["amount"] if y else 0)})
    qs_changes.sort(key=lambda c: -abs(c["delta"]))

    # build-up rows
    ra = {r["row_id"]: r for r in a["buildup"]}
    rb = {r["row_id"]: r for r in b["buildup"]}
    row_changes = []
    for rid in list(rb) + [r for r in ra if r not in rb]:
        x, y = ra.get(rid), rb.get(rid)
        ref = y or x
        if x is None:
            kind = "added"
        elif y is None:
            kind = "removed"
        elif abs(_delta(x["cost"], y["cost"])) > EPS or abs((y["applied_rate"] or 0) - (x["applied_rate"] or 0)) > 1e-9 \
                or abs((y["hours"] or 0) - (x["hours"] or 0)) > 1e-9:
            kind = "changed"
        else:
            continue
        row_changes.append({
            "row_id": rid, "qs_code": ref["qs_code"], "task": ref["task"], "resource": ref["resource"], "kind": kind,
            "rate_a": x["applied_rate"] if x else None, "rate_b": y["applied_rate"] if y else None,
            "hours_a": x["hours"] if x else None, "hours_b": y["hours"] if y else None,
            "cost_a": x["cost"] if x else None, "cost_b": y["cost"] if y else None,
            "delta": _delta(x["cost"] if x else 0, y["cost"] if y else 0)})
    row_changes.sort(key=lambda c: -abs(c["delta"]))

    # commercial inputs
    ca = {c["ref"]: c for c in a["commercial"]}
    cb = {c["ref"]: c for c in b["commercial"]}
    commercial = []
    for ref in cb:
        x, y = ca.get(ref), cb[ref]
        if x is None or x["include"] != y["include"] or x["method"] != y["method"] \
                or abs(_delta(x["amount"], y["amount"])) > EPS or abs(x["pct"] - y["pct"]) > 1e-12:
            commercial.append({"ref": ref, "name": y["name"], "include_a": x["include"] if x else None, "include_b": y["include"],
                               "amount_a": x["amount"] if x else None, "amount_b": y["amount"], "delta": _delta(x["amount"] if x else 0, y["amount"])})

    # subcontract overlays (by name)
    oa = {o["name"]: o["amount"] for o in a["consolidated"]["overlays"]}
    ob = {o["name"]: o["amount"] for o in b["consolidated"]["overlays"]}
    overlays = [{"name": n, "a": oa.get(n), "b": ob.get(n), "delta": _delta(oa.get(n), ob.get(n))}
                for n in list(ob) + [n for n in oa if n not in ob] if abs(_delta(oa.get(n), ob.get(n))) > EPS]

    # commercial settings that move the price without touching any cost
    settings = []
    for key, label in (("overhead_rate", "Company overhead (markup on cost)"), ("margin", "Profit (true margin on sell)")):
        x, y = a["consolidated"].get(key), b["consolidated"].get(key)
        if x is not None and y is not None and abs(x - y) > 1e-12:
            settings.append({"key": key, "label": label, "a": x, "b": y})

    return {
        "settings": settings, "headline": headline, "sections": sections, "qs": qs_changes, "buildup": row_changes,
        "commercial": commercial, "overlays": overlays,
        "counts": {
            "qs_changed": len(qs_changes), "buildup_changed": len(row_changes),
            "commercial_changed": len(commercial), "overlays_changed": len(overlays),
            "settings_changed": len(settings)},
        "identical": not (qs_changes or row_changes or commercial or overlays or settings)
                     and all(abs(h["delta"]) <= EPS for h in headline),
    }
