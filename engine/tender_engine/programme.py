"""Tender programme: working-day durations, predecessors and the critical path (finish-to-start, no lags).

task = {"id", "code", "name", "qs_code" ("" for a control task with no cost), "override_days" (str|None), "predecessors" [codes],
        "hammock" (bool), "basis", "note"}

A task's duration is its override when one is entered, otherwise the QS item's derived duration: the slowest linked resource row, in hours,
divided by the working day (default 8) and rounded UP -- exactly the Master Estimate Workbook's Programme Export rule. A hammock task
(preliminaries) runs across the whole job; it is shown on the programme but is not on the critical path.
Dates count Monday-to-Friday (or the stated days per week); public holidays and shutdowns are not modelled.
"""
from __future__ import annotations
import datetime as dt
import math
import re
from decimal import Decimal
from typing import Any, Optional, Sequence

from .money import D

CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,19}$")
TASK_ID = re.compile(r"^P-[A-Za-z0-9]{4,12}$")
MAX_TASKS = 400
FIELDS = ("code", "name", "override_days", "predecessors", "hammock", "basis", "note")


class ProgrammeError(ValueError):
    pass


def derived_days(hours: Optional[Decimal], hours_per_day: int = 8) -> Optional[int]:
    if hours is None or hours <= 0:
        return None
    return int(math.ceil(D(hours) / D(hours_per_day)))


def working_date(start: dt.date, index: int, days_per_week: int = 5) -> dt.date:
    """Date of the index-th (0-based) working day counting from `start` (a non-working start rolls forward)."""
    d = start
    while d.isoweekday() > days_per_week:
        d += dt.timedelta(days=1)
    n = 0
    while n < index:
        d += dt.timedelta(days=1)
        if d.isoweekday() <= days_per_week:
            n += 1
    return d


def new_programme(start: str = "", days_per_week: int = 5, hours_per_day: int = 8) -> dict[str, Any]:
    return {"start": start, "days_per_week": days_per_week, "hours_per_day": hours_per_day, "tasks": []}


def set_config(p: dict[str, Any], field: str, value: Any) -> None:
    if field == "start":
        v = str(value or "").strip()
        if v:
            try:
                dt.date.fromisoformat(v[:10])
            except ValueError:
                raise ProgrammeError("The programme start isn't a valid date (use year-month-day).")
            v = v[:10]
        p["start"] = v
    elif field in ("days_per_week", "hours_per_day"):
        lo, hi = (1, 7) if field == "days_per_week" else (1, 24)
        try:
            n = int(str(value).strip())
        except ValueError:
            raise ProgrammeError("That needs a whole number.")
        if not lo <= n <= hi:
            raise ProgrammeError(f"{field.replace('_', ' ').capitalize()} must be between {lo} and {hi}.")
        p[field] = n
    else:
        raise ProgrammeError(f"{field!r} can't be edited on the programme.")


def set_task_field(t: dict[str, Any], field: str, value: Any, all_tasks: list[dict[str, Any]]) -> None:
    if field not in FIELDS:
        raise ProgrammeError(f"{field!r} can't be edited on a programme task.")
    if field == "code":
        v = str(value or "").strip()
        if not CODE.match(v):
            raise ProgrammeError("A task code is letters, numbers and dashes, for example PRG-RF01.")
        if any(x is not t and x["code"] == v for x in all_tasks):
            raise ProgrammeError(f"Task code {v} is already used.")
        t["code"] = v
    elif field == "override_days":
        s = "" if value is None else str(value).strip()
        if s == "":
            t["override_days"] = None
        else:
            try:
                n = Decimal(s)
            except Exception:
                raise ProgrammeError("Days needs a whole number.")
            if n != n.to_integral_value() or n < 0 or n > 3000:
                raise ProgrammeError("Days needs a whole number from 0 to 3000.")
            t["override_days"] = str(int(n))
    elif field == "predecessors":
        codes = [c for c in re.split(r"[,;\s]+", value) if c] if isinstance(value, str) else [str(c) for c in (value or [])]
        if t["code"] in codes:
            raise ProgrammeError("A task can't follow itself.")
        t["predecessors"] = list(dict.fromkeys(codes))
    elif field == "hammock":
        t["hammock"] = value if isinstance(value, bool) else str(value).strip().lower() in ("yes", "true", "1")
    else:
        v = "" if value is None else str(value).strip()
        if field == "name" and not v:
            raise ProgrammeError("A task needs a name.")
        if len(v) > (200 if field == "name" else 500):
            raise ProgrammeError(f"{field.capitalize()} is too long.")
        t[field] = v


def build_task(task_id: str, v: dict[str, Any], all_tasks: list[dict[str, Any]]) -> dict[str, Any]:
    t = {"id": task_id, "code": "", "name": "", "qs_code": str(v.get("qs_code") or ""), "override_days": None, "predecessors": [], "hammock": False, "basis": "", "note": ""}
    for f in FIELDS:
        if f in v and v[f] not in (None, ""):
            set_task_field(t, f, v[f], all_tasks)
    if not t["code"]:
        raise ProgrammeError("A task needs a code.")
    if not t["name"]:
        raise ProgrammeError("A task needs a name.")
    if any(x["code"] == t["code"] for x in all_tasks):
        raise ProgrammeError(f"Task code {t['code']} is already used.")
    return t


def compute_programme(prog: dict[str, Any], hours_by_qs: dict[str, Decimal], qs_info: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Critical path method. hours_by_qs: code -> slowest linked row (hours). qs_info: code -> {section, description, amount}."""
    tasks = prog["tasks"]
    hpd, dpw = int(prog.get("hours_per_day", 8)), int(prog.get("days_per_week", 5))
    by_code = {t["code"]: t for t in tasks}
    problems: list[str] = []
    dur: dict[str, int] = {}
    derived: dict[str, Optional[int]] = {}
    for t in tasks:
        d = derived_days(hours_by_qs.get(t["qs_code"]) if t["qs_code"] else None, hpd)
        derived[t["code"]] = d
        dur[t["code"]] = int(t["override_days"]) if t["override_days"] is not None else (d or 0)
    preds: dict[str, list[str]] = {}
    for t in tasks:
        ok = []
        for p in t["predecessors"]:
            if p in by_code:
                ok.append(p)
            else:
                problems.append(f"{t['code']} follows {p}, which isn't in the programme.")
        preds[t["code"]] = ok
    es: dict[str, int] = {}
    state: dict[str, int] = {}

    def forward(c: str) -> int:
        if c in es:
            return es[c]
        if state.get(c) == 1:
            problems.append(f"{c} is part of a loop of predecessors.")
            return 0
        state[c] = 1
        es[c] = max([forward(p) + dur[p] for p in preds[c]] or [0])
        state[c] = 2
        return es[c]

    for t in tasks:
        forward(t["code"])
    ef = {c: es[c] + dur[c] for c in es}
    ham = {t["code"] for t in tasks if t["hammock"]}
    project = max([v for c, v in ef.items() if c not in ham] or list(ef.values()) or [0])
    succ: dict[str, list[str]] = {c: [] for c in es}
    for c, ps in preds.items():
        for p in ps:
            succ[p].append(c)
    lf: dict[str, int] = {}

    def backward(c: str, depth: int = 0) -> int:
        if c in lf:
            return lf[c]
        if depth > len(tasks) + 1:
            return project
        lf[c] = project if not succ[c] else min(backward(s, depth + 1) - dur[s] for s in succ[c])
        return lf[c]

    for t in tasks:
        backward(t["code"])
    start = dt.date.fromisoformat(prog["start"]) if prog.get("start") else None
    out = []
    for t in tasks:
        c = t["code"]
        slack = lf[c] - dur[c] - es[c]
        info = qs_info.get(t["qs_code"], {}) if t["qs_code"] else {}
        out.append({
            "id": t["id"], "code": c, "name": t["name"], "qs_code": t["qs_code"], "section": info.get("section") or "Programme controls",
            "amount": info.get("amount"), "duration": dur[c], "derived": derived[c], "override": t["override_days"], "predecessors": t["predecessors"],
            "hammock": t["hammock"], "basis": t["basis"], "note": t["note"], "es": es[c], "ef": ef[c], "float": slack,
            "critical": slack == 0 and dur[c] > 0 and not t["hammock"],
            "start": working_date(start, es[c], dpw).isoformat() if start else None,
            "finish": working_date(start, max(ef[c] - 1, es[c]), dpw).isoformat() if start else None})
    chain = sorted((x for x in out if x["critical"]), key=lambda x: (x["es"], x["ef"]))
    hammock_days = [x["duration"] for x in out if x["hammock"]]
    path_days = project
    missing = [{"code": c, "description": i.get("description", ""), "amount": i.get("amount")} for c, i in qs_info.items()
               if c not in {t["qs_code"] for t in tasks} and (i.get("amount") or 0) != 0]
    if hammock_days and any(h != path_days for h in hammock_days):
        problems.append(f"Preliminaries run {max(hammock_days)} days but the programme chain is {path_days} days.")
    return {"tasks": out, "duration": path_days, "critical_path": [x["code"] for x in chain], "problems": problems,
            "missing": missing, "start": prog.get("start") or "", "days_per_week": dpw, "hours_per_day": hpd,
            "finish": working_date(start, max(path_days - 1, 0), dpw).isoformat() if start and path_days else None}
