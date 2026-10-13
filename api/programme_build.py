"""Pure helpers for programme documents: a first-cut programme from an estimate, and cleaning of saved task lists."""
from __future__ import annotations
from typing import Any

MAX_TASKS = 5000
TASK_FIELDS = {
    "uid", "id", "name", "wbs", "outline_level", "parent_id", "is_summary", "is_milestone", "is_critical", "is_active", "start", "finish",
    "duration", "percent_complete", "actual_start", "actual_finish", "baseline_start", "baseline_finish", "deadline", "constraint_type",
    "constraint_date", "total_slack", "predecessors", "resources", "resource_assignments", "notes", "source_ref",
}


class BadProgramme(ValueError):
    pass


def clean_tasks(tasks: Any) -> list[dict[str, Any]]:
    if not isinstance(tasks, list):
        raise BadProgramme("Tasks must be a list.")
    if len(tasks) > MAX_TASKS:
        raise BadProgramme(f"Too many tasks (maximum {MAX_TASKS}).")
    out, seen = [], set()
    for t in tasks:
        if not isinstance(t, dict) or t.get("uid") is None or t["uid"] in seen:
            raise BadProgramme("Every task needs its own unique uid.")
        seen.add(t["uid"])
        out.append({k: v for k, v in t.items() if k in TASK_FIELDS})
    return out


def _leaf(uid: int, name: str, days: int, preds: list[dict[str, Any]], note: str, ref: str) -> dict[str, Any]:
    return {"uid": uid, "name": name, "outline_level": 2, "duration": {"value": days, "unit": "D"}, "percent_complete": 0, "predecessors": preds,
            "resources": [], "resource_assignments": [], "constraint_type": None, "constraint_date": None, "notes": note, "is_active": True, "source_ref": ref}


def tasks_from_estimate(est: dict[str, Any]) -> list[dict[str, Any]]:
    """A first-cut programme from an estimate. Sections become summary rows; QS items become tasks, in order.
    The durations are the platform's own (programme page if it is set up, otherwise slowest labour/plant row hours / 8); the order and links are a
    starting point for the estimator to change. Nothing here is AI: the AI drafting step proposes logic separately."""
    prog = est.get("programme") or {}
    out: list[dict[str, Any]] = []
    uid = 0

    def nxt() -> int:
        nonlocal uid
        uid += 1
        return uid

    def summary(name: str) -> int:
        u = nxt()
        out.append({"uid": u, "name": name, "outline_level": 1, "duration": {"value": 1, "unit": "D"}, "percent_complete": 0, "predecessors": [],
                    "resources": [], "resource_assignments": [], "notes": "", "is_active": True})
        return u

    if prog.get("set_up") and prog.get("tasks"):
        by_code: dict[str, int] = {}
        pending: list[tuple[int, list[str]]] = []
        grouped: dict[str, list[dict[str, Any]]] = {}
        for t in prog["tasks"]:
            grouped.setdefault(t.get("section") or "Programme controls", []).append(t)      # rows of a section stay together
        for sec, items in grouped.items():
            summary(sec)
            for t in items:
                u = nxt()
                days = int(t.get("duration") or 0)
                leaf = _leaf(u, f"{t['code']} {t['name']}".strip(), days, [], (t.get("basis") or "").strip(), t["code"])
                if days == 0:
                    leaf["is_milestone"] = True
                out.append(leaf)
                by_code[t["code"]] = u
                pending.append((u, list(t.get("predecessors") or [])))
        index = {x["uid"]: x for x in out}
        for u, preds in pending:
            index[u]["predecessors"] = [{"uid": by_code[p], "type": "FS", "lag_days": 0} for p in preds if p in by_code]
        return out

    hours: dict[str, float] = {}
    for r in est.get("buildup") or []:
        if str(r.get("resource_type", "")).lower() in ("labour", "plant") and (r.get("hours") or 0) > 0:
            hours[r["qs_code"]] = max(hours.get(r["qs_code"], 0.0), float(r["hours"]))
    sections = {}
    prev: int | None = None
    for q in est.get("qs") or []:
        if not (q.get("amount") or 0):
            continue
        sec = q.get("section") or "Works"
        if sec not in sections:
            sections[sec] = summary(sec)
        u = nxt()
        h = hours.get(q["code"])
        days = max(1, -(-int(round(h * 100)) // 800)) if h else 1          # ROUNDUP(hours / 8), at least 1
        note = "Duration from the estimate's labour/plant hours; review." if h else "No labour/plant hours in the estimate for this item: 1 day placeholder; set it."
        out.append(_leaf(u, f"{q['code']} {q.get('description', '')}".strip(), days, [{"uid": prev, "type": "FS", "lag_days": 0}] if prev else [], note, q["code"]))
        prev = u
    return out
