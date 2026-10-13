"""AI proposals for programme LOGIC. Pure functions: prompt, output checking, applying links.

The AI proposes which task depends on which (finish-to-start, or an overlap with a lag) and why. It never changes a duration or a date, never adds or
removes tasks, and never sees prices. The durations are the platform's own (from the estimate's labour and plant hours); the programme scheduler works
the dates out. Every proposal is checked here before the estimator sees it: both tasks must exist and be real work tasks (not section headings), the
link must not already exist, and it must not create a loop. The estimator accepts the ones they want into the programme draft; nothing is saved until they save.
"""
from __future__ import annotations
from typing import Any

PROMPT_VERSION = "programme-v1"
LINK_TYPES = ("FS", "SS", "FF", "SF")
MAX_LAG = 30                      # days either way; anything bigger is a typing mistake or a different programme

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "links": {"type": "array", "items": {"type": "object", "properties": {
            "pred_uid": {"type": "integer"}, "succ_uid": {"type": "integer"},
            "type": {"type": "string", "enum": list(LINK_TYPES)}, "lag_days": {"type": "integer"},
            "reason": {"type": "string"}, "basis": {"type": "string", "enum": ["construction_logic", "tender_document", "inference"]},
            "register_ref": {"type": "string"}, "confidence": {"type": "string", "enum": ["high", "medium", "low"]}},
            "required": ["pred_uid", "succ_uid", "type", "lag_days", "reason", "basis", "register_ref", "confidence"], "additionalProperties": False}},
        "remove_links": {"type": "array", "items": {"type": "object", "properties": {
            "pred_uid": {"type": "integer"}, "succ_uid": {"type": "integer"}, "reason": {"type": "string"}},
            "required": ["pred_uid", "succ_uid", "reason"], "additionalProperties": False}},
        "questions": {"type": "array", "items": {"type": "object", "properties": {"question": {"type": "string"}, "why": {"type": "string"}}, "required": ["question", "why"], "additionalProperties": False}},
        "coverage_notes": {"type": "string"},
    },
    "required": ["links", "remove_links", "questions", "coverage_notes"], "additionalProperties": False,
}

SYSTEM = """You are assisting a senior NZ civil and commercial estimator who is building a construction programme. You are PROPOSING programme logic only. The estimator reviews and accepts each proposal.

You are given the programme's tasks (each with a uid, outline level, name, duration in working days and resources) and the links they currently have. The current links are only a first-cut chain in estimate order: they are often wrong. Section headings (summary rows) are listed for context; they cannot be linked.

Propose:
1. `links`: a dependency between two existing work tasks, by uid. `pred_uid` must finish (FS), start (SS) or finish (FF) before `succ_uid` can ... in the usual way. Use FS unless work genuinely overlaps; for an overlap use SS or FF with a lag in whole working days (a negative lag is a lead). Prefer few, meaningful links over many: every task that has to wait for another should say so; do not add a link that is already implied through other links.
2. `remove_links`: a current link that is wrong or not needed (for example the estimate-order chain between unrelated trades). Give the reason.
3. `questions`: things you could not settle that the estimator should confirm (sequence depends on a design decision, a temporary-works method, a consent, cure or stand-down times, access). Plain, practical questions.

Rules:
- Use only uids that appear in the list. Never create, rename, delete or re-time tasks. Never state or change a duration, date, quantity or price.
- Every link needs a short plain-language `reason` that a site foreman would accept (for example "Subgrade must be proof-rolled and signed off before basecourse is placed").
- `basis`: "construction_logic" for normal construction sequence; "tender_document" only when the tender context below says so (then give its `register_ref`, otherwise an empty string); "inference" when you are guessing from the task names. `confidence`: high only when the sequence is not in doubt.
- Do not link tasks that can happen in parallel just to keep a tidy chain. Do not close loops. Do not link section headings.
- Respond with JSON only, matching the schema. `coverage_notes` says in a sentence or two what you looked at and anything you could not judge."""


def build_user_message(project: str, tasks: list[dict[str, Any]], context: list[dict[str, str]]) -> str:
    by_uid = {t["uid"]: t for t in tasks}
    summary_uids = _summary_uids(tasks)
    lines = [f"PROJECT: {project}", "", "TASKS (uid | level | name | duration | resources | current predecessors)"]
    for t in tasks:
        dur = t.get("duration") or {}
        d = "0 (milestone)" if t.get("is_milestone") else f"{dur.get('value', 1):g} {str(dur.get('unit', 'D')).lower()}"
        preds = ", ".join(_pred_text(p) for p in t.get("predecessors") or []) or "none"
        kind = "SECTION" if t["uid"] in summary_uids else "task"
        res = "; ".join(a["name"] for a in t.get("resource_assignments") or []) or "-"
        lines.append(f"{t['uid']} | {t.get('outline_level', 1)} | {kind}: {t.get('name', '')} | {d} | {res[:90]} | {preds}")
    lines += ["", "TENDER CONTEXT (assumptions, exclusions, open RFIs and risks already recorded)"]
    lines += [f"- {c['ref']} {c['kind']}: {c['title']}" + (f" - {c['detail']}" if c.get("detail") else "") for c in context[:60]] or ["- (none recorded)"]
    return "\n".join(lines)


def _pred_text(p: dict[str, Any]) -> str:
    typ, lag = p.get("type") or "FS", int(p.get("lag_days") or 0)
    return f"{p.get('uid')}" + ("" if typ == "FS" else typ) + (f"{lag:+d}d" if lag else "")


def _summary_uids(tasks: list[dict[str, Any]]) -> set[int]:
    """A row followed by a deeper row is a section heading (same rule the programme editor uses)."""
    out = set()
    for i, t in enumerate(tasks[:-1]):
        if int(tasks[i + 1].get("outline_level", 1)) > int(t.get("outline_level", 1)):
            out.add(t["uid"])
    return out


def _has_path(preds: dict[int, set[int]], start: int, goal: int) -> bool:
    """Is `goal` reachable from `start` following predecessor edges?"""
    seen, stack = set(), [start]
    while stack:
        n = stack.pop()
        if n == goal:
            return True
        if n in seen:
            continue
        seen.add(n)
        stack.extend(preds.get(n, ()))
    return False


def verify(data: dict[str, Any], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Check what the AI said against the saved programme. Returns {proposals: [...], questions: [...]}.
    Each proposal: kind link|remove, pred_uid, succ_uid, type, lag_days, reason, basis, confidence, register_ref, status (ok | exists | invalid), problems[].
    Loop check runs in order against the existing links (less the removals that are themselves valid) plus the links already accepted as ok above it."""
    by_uid = {t["uid"]: t for t in tasks}
    leaf = set(by_uid) - _summary_uids(tasks)
    preds: dict[int, set[int]] = {u: {p["uid"] for p in t.get("predecessors") or [] if p.get("uid") in by_uid} for u, t in by_uid.items()}
    cur = {(p["uid"], u): p for u, t in by_uid.items() for p in t.get("predecessors") or [] if p.get("uid") in by_uid}
    out: list[dict[str, Any]] = []

    def base(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
        return {"kind": kind, "pred_uid": raw.get("pred_uid"), "succ_uid": raw.get("succ_uid"), "type": str(raw.get("type") or "FS"), "lag_days": int(raw.get("lag_days") or 0),
                "reason": str(raw.get("reason") or "").strip()[:600], "basis": str(raw.get("basis") or "inference"), "confidence": str(raw.get("confidence") or "low"),
                "register_ref": str(raw.get("register_ref") or "")[:40], "problems": [], "status": "ok"}

    removed: set[tuple[int, int]] = set()
    for raw in data.get("remove_links") or []:
        p = base("remove", raw)
        key = (raw.get("pred_uid"), raw.get("succ_uid"))
        if key not in cur:
            p["problems"].append("That link is not in the programme.")
        elif not p["reason"]:
            p["problems"].append("No reason given.")
        else:
            removed.add(key)
            preds[key[1]].discard(key[0])
        p["status"] = "invalid" if p["problems"] else "ok"
        out.append(p)
    for raw in data.get("links") or []:
        p = base("link", raw)
        a, b = raw.get("pred_uid"), raw.get("succ_uid")
        if a not in by_uid or b not in by_uid:
            p["problems"].append("A task in this link does not exist in the programme.")
        elif a == b:
            p["problems"].append("A task cannot depend on itself.")
        elif a not in leaf or b not in leaf:
            p["problems"].append("Links go between work tasks, not section headings.")
        if p["type"] not in LINK_TYPES:
            p["problems"].append(f"Unknown link type {p['type']}.")
        if abs(p["lag_days"]) > MAX_LAG:
            p["problems"].append(f"A lag of {p['lag_days']} days is outside the allowed ±{MAX_LAG}.")
        if not p["reason"]:
            p["problems"].append("No reason given.")
        if p["basis"] == "tender_document" and not p["register_ref"]:
            p["problems"].append("Says a tender document requires it but cites none.")
        if not p["problems"]:
            if a in preds.get(b, ()) and (a, b) not in removed:
                p["status"] = "exists"
            elif _has_path(preds, a, b):                  # b already (indirectly) feeds a: adding a -> b would close a loop
                p["problems"].append("This would make the programme loop back on itself.")
            else:
                preds.setdefault(b, set()).add(a)
        if p["problems"]:
            p["status"] = "invalid"
        out.append(p)
    qs = [{"question": str(q.get("question", ""))[:400], "why": str(q.get("why", ""))[:400]} for q in (data.get("questions") or [])[:30] if q.get("question")]
    return {"proposals": out, "questions": qs}


def apply_to_predecessors(preds: list[dict[str, Any]], adds: list[dict[str, Any]], removes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The new predecessor list for ONE task: its current list less the removals plus the additions (no duplicates). adds: {pred_uid,type,lag_days}; removes: {pred_uid}."""
    gone = {r["pred_uid"] for r in removes}
    out = [dict(p) for p in preds if p.get("uid") not in gone]
    have = {p["uid"] for p in out}
    for a in adds:
        if a["pred_uid"] not in have:
            out.append({"uid": a["pred_uid"], "type": a["type"], "lag_days": a["lag_days"]})
            have.add(a["pred_uid"])
    return out
