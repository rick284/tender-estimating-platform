"""A tender's live weather-tool setup (stored with its inputs) and the bridge to tender_engine.weather_tool.

setup = {"station", "start" (ISO date), "working_days_per_week", "baseline_wd", "local_factor", "local_basis",
         "wind_override" (str|None), "include_wind" (bool),
         "activities": [{"id", "task", "start", "finish", "critical", "qs_codes", "labour", "plant", "overrides", "note"}]}

An activity's exposed labour/plant is, unless typed in, the cost of the build-up rows in its QS items that are tagged
Weather Exposed (Labour rows -> labour, Plant rows -> plant). Strings keep Decimals exact in the saved JSON.
"""
from __future__ import annotations
import copy
import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Sequence

from .money import D, ZERO
from .weather_tool import (Activity, ENGINE_FROM, ENGINE_TO, OVERRIDE_FIELDS, ToolSettings, ToolResult, run_tool, stations,
                           task_names)

ACTIVITY_ID = re.compile(r"^W-[A-Za-z0-9]{4,12}$")
SETUP_FIELDS = ("station", "start", "working_days_per_week", "baseline_wd", "local_factor", "local_basis", "wind_override", "include_wind")
ACTIVITY_FIELDS = ("task", "start", "finish", "critical", "qs_codes", "labour", "plant", "note") + tuple(f"ov_{k}" for k in OVERRIDE_FIELDS)
MAX_ACTIVITIES = 30            # the workbook has 30 activity rows


class SetupError(ValueError):
    pass


def _date(v: Any, what: str, required=True) -> str:
    s = "" if v is None else str(v).strip()
    if not s:
        if required:
            raise SetupError(f"{what} needs a date.")
        return ""
    try:
        d = dt.date.fromisoformat(s[:10])
    except ValueError:
        raise SetupError(f"{what} isn't a valid date (use year-month-day).")
    if d < ENGINE_FROM or d > ENGINE_TO:
        raise SetupError(f"{what} must be between {ENGINE_FROM:%d-%b-%Y} and {ENGINE_TO:%d-%b-%Y} (the range the climate engine covers).")
    return d.isoformat()


def _num(v: Any, what: str, *, lo: Decimal = ZERO, hi: Optional[Decimal] = None, nullable=False) -> Optional[str]:
    if v is None or (isinstance(v, str) and v.strip() == ""):
        if nullable:
            return None
        raise SetupError(f"{what} needs a number.")
    try:
        x = Decimal(str(v).strip())
    except InvalidOperation:
        raise SetupError(f"{what} needs a number.")
    if not x.is_finite() or x < lo or (hi is not None and x > hi):
        raise SetupError(f"{what} must be between {lo} and {hi if hi is not None else 'a large number'}.")
    return str(x)


def new_setup(station: str, start: Any, working_days_per_week: Any = 5, baseline_wd: Any = 0) -> dict[str, Any]:
    s = {"station": "", "start": "", "working_days_per_week": 5, "baseline_wd": 0, "local_factor": "1", "local_basis": "",
         "wind_override": None, "include_wind": False, "activities": []}
    for k, v in (("station", station), ("start", start), ("working_days_per_week", working_days_per_week), ("baseline_wd", baseline_wd)):
        set_field(s, k, v)
    return s


def set_field(s: dict[str, Any], field: str, value: Any) -> None:
    if field == "station":
        v = str(value or "").strip()
        if v not in stations():
            raise SetupError("Choose a weather station from the list.")
        s["station"] = v
    elif field == "start":
        s["start"] = _date(value, "Project start")
    elif field == "working_days_per_week":
        s[field] = int(_num(value, "Working days per week", lo=Decimal(1), hi=Decimal(7)).split(".")[0])
    elif field == "baseline_wd":
        s[field] = int(_num(value, "Baseline working days", lo=ZERO, hi=Decimal(3000)).split(".")[0])
    elif field == "local_factor":
        s[field] = _num(value, "Local wet-day factor", lo=Decimal("0.1"), hi=Decimal(3))
    elif field == "local_basis":
        s[field] = str(value or "").strip()[:500]
    elif field == "wind_override":
        s[field] = _num(value, "Wind probability", lo=ZERO, hi=Decimal(1), nullable=True)
    elif field == "include_wind":
        if isinstance(value, str):
            value = value.strip().lower() in ("yes", "true", "1")
        s[field] = bool(value)
    else:
        raise SetupError(f"{field!r} can't be edited on the weather setup.")


def build_activity(act_id: str, v: dict[str, Any]) -> dict[str, Any]:
    a = {"id": act_id, "task": "", "start": "", "finish": "", "critical": False, "qs_codes": [], "labour": None, "plant": None,
         "overrides": {}, "note": ""}
    for k in ("task", "start", "finish", "critical", "qs_codes", "labour", "plant", "note"):
        if k in v:
            set_activity_field(a, k, v[k])
    for k in OVERRIDE_FIELDS:
        if v.get("ov_" + k) not in (None, ""):
            set_activity_field(a, "ov_" + k, v["ov_" + k])
    check_activity(a)
    return a


def set_activity_field(a: dict[str, Any], field: str, value: Any) -> None:
    if field == "task":
        v = str(value or "").strip()
        if v not in task_names():
            raise SetupError("Choose a task from the weather task library.")
        a["task"] = v
    elif field in ("start", "finish"):
        a[field] = _date(value, "Activity " + field)
    elif field == "critical":
        a[field] = value if isinstance(value, bool) else str(value).strip().lower() in ("yes", "true", "1")
    elif field == "qs_codes":
        if isinstance(value, str):
            value = [x for x in re.split(r"[,\s]+", value) if x]
        if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
            raise SetupError("QS items must be a list of codes.")
        a[field] = [x.strip().upper() for x in value][:40]
    elif field in ("labour", "plant"):
        a[field] = _num(value, "Exposed " + field, nullable=True, hi=Decimal("1e12"))
    elif field == "note":
        a[field] = str(value or "").strip()[:300]
    elif field.startswith("ov_") and field[3:] in OVERRIDE_FIELDS:
        name = field[3:]
        a["overrides"] = {**a["overrides"]}
        v = _num(value, name.replace("_", " "), nullable=True, hi=Decimal(1))
        if v is None:
            a["overrides"].pop(name, None)
        else:
            a["overrides"][name] = v
    else:
        raise SetupError(f"{field!r} can't be edited on a weather activity.")


def check_activity(a: dict[str, Any]) -> None:
    if not a["task"]:
        raise SetupError("Choose a task from the weather task library.")
    if not a["start"] or not a["finish"]:
        raise SetupError("An activity needs a start and a finish date.")
    if a["finish"] < a["start"]:
        raise SetupError("An activity can't finish before it starts.")


def exposed_by_qs(buildup: Sequence[Any], results: Sequence[Any]) -> dict[str, tuple[Decimal, Decimal]]:
    """qs_code -> (exposed labour, exposed plant) from the weather-exposed rows."""
    out: dict[str, list[Decimal]] = {}
    for row, res in zip(buildup, results):
        if row.weather_exposed != "Yes":
            continue
        e = out.setdefault(row.qs_code, [ZERO, ZERO])
        if row.resource_type == "Labour":
            e[0] += res.cost
        elif row.resource_type == "Plant":
            e[1] += res.cost
    return {k: (v[0], v[1]) for k, v in out.items()}


def run_setup(setup: dict[str, Any], exposed: dict[str, tuple[Decimal, Decimal]], daily_prelims: Decimal, weekly_hire: Decimal,
              recovery: Decimal) -> tuple[ToolResult, list[dict[str, Any]], list[str]]:
    """Returns (tool result, per-activity inputs used, warnings)."""
    warnings: list[str] = []
    acts: list[Activity] = []
    used: list[dict[str, Any]] = []
    linked: set[str] = set()
    for a in setup["activities"]:
        lab = D(a["labour"]) if a["labour"] is not None else None
        pla = D(a["plant"]) if a["plant"] is not None else None
        if lab is None or pla is None:
            auto_l = sum((exposed.get(c, (ZERO, ZERO))[0] for c in a["qs_codes"]), ZERO)
            auto_p = sum((exposed.get(c, (ZERO, ZERO))[1] for c in a["qs_codes"]), ZERO)
            lab = auto_l if lab is None else lab
            pla = auto_p if pla is None else pla
            linked.update(a["qs_codes"])
        if lab + pla == 0:
            warnings.append(f"{a['task']} ({a['start']} to {a['finish']}) has no weather-exposed labour or plant, so it adds no direct cost"
                            + (" (it still counts for delay if it is on the critical path)." if a["critical"] else "."))
        acts.append(Activity(a["task"], dt.date.fromisoformat(a["start"]), dt.date.fromisoformat(a["finish"]), bool(a["critical"]),
                             lab, pla, {k: D(v) for k, v in a["overrides"].items()}, a.get("note", "")))
        used.append({"labour": lab, "plant": pla})
    covered = sum((l + p for l, p in used), ZERO)
    all_exposed = sum((l + p for l, p in exposed.values()), ZERO)
    gap = all_exposed - sum((sum(exposed.get(c, (ZERO, ZERO))) for c in linked), ZERO)
    if gap > Decimal("0.005"):
        warnings.append(f"${gap:,.2f} of weather-exposed labour and plant is not linked to any weather activity, so it carries no weather allowance.")
    settings = ToolSettings(setup["station"], int(setup["working_days_per_week"]), D(setup["local_factor"]),
                            None if setup["wind_override"] is None else D(setup["wind_override"]), daily_prelims, weekly_hire, recovery)
    return run_tool(settings, acts, include_wind=bool(setup["include_wind"])), used, warnings


def clone(setup: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    return copy.deepcopy(setup)
