"""Port of NZ_Weather_Risk_Estimating_Tool_Rev2 ("Activity Allowances" method) -- pure, deterministic, no I/O.

For each weather-exposed activity (a task from the Task Library, a date window, exposed labour + plant cost):

  wet-day probability   = average NIWA 1991-2020 daily wet-day probability over the activity's WORKDAYS
  adjusted probability  = min(1, wet-day probability x local wet-day factor)
  wind probability      = override, else average of the daily wind proxy (Auckland only, AMBER) over the workdays
  rain impact           = adjusted prob x rain exposure x rain productivity loss x non-recoverable share
  wet-ground carryover  = adjusted prob x carryover equivalent days x non-recoverable share
  wind impact           = wind prob x wind sensitivity x wind productivity loss x non-recoverable share
  combined impact       = min(1, rain + carryover + wind)
  direct allowance      = (labour + plant) x combined impact
  equivalent lost WD    = workdays x combined impact;  critical-path delay = that, ONLY if the activity is on the critical path

Project totals: direct allowance, critical-path delay (WD; never summed across concurrent non-critical activities),
time-related preliminaries = delay x daily preliminaries, additional billed hire weeks = ROUNDUP(delay / days-per-week),
hire = weeks x weekly hire, plus any project-specific recovery allowance.

`include_wind=False` (the platform default, per the Master Prompt: wind is separate and AMBER) computes the totals
without the wind term and reports the wind sensitivity separately; `include_wind=True` reproduces the workbook's own
Activity Allowances totals exactly. Public holidays and shutdowns are not modelled (same as the workbook).
"""
from __future__ import annotations
import datetime as dt
import json
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Sequence

from .money import D, ZERO, ONE

DATA_FILE = Path(__file__).resolve().parent / "data" / "weather_rev2.json"
ENGINE_FROM = dt.date(2025, 1, 1)
ENGINE_TO = dt.date(2040, 12, 31)
OVERRIDE_FIELDS = ("rain_exposure", "rain_loss", "carryover", "wind_sensitivity", "wind_loss", "nonrecoverable")


@lru_cache(maxsize=1)
def tool_data() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def stations() -> list[str]:
    return [s["name"] for s in tool_data()["stations"]]


def task_names() -> list[str]:
    return [t["name"] for t in tool_data()["tasks"]]


@lru_cache(maxsize=1)
def _tasks() -> dict[str, dict[str, Decimal]]:
    return {t["name"]: {"category": t["category"], "rain_exposure": D(t["rain_exposure"]), "rain_loss": D(t["rain_loss"]),
                        "carryover": D(t["carryover"]), "wind_sensitivity": D(t["wind_sensitivity"]),
                        "wind_loss": D(t["wind_loss"]), "nonrecoverable": D(t["nonrecoverable"])}
            for t in tool_data()["tasks"]}


@lru_cache(maxsize=64)
def _monthly(station: str) -> tuple[tuple[Decimal, ...], tuple[Decimal, ...]]:
    """(daily wet-day probability by month 1..12, daily wind-proxy probability by month 1..12) for a station."""
    d = tool_data()
    if station not in d["climate"]:
        raise ValueError(f"Unknown weather station {station!r}.")
    cal = {m["month"]: D(m["calendar_days"]) for m in d["climate"][station]}
    wet = tuple(D(m["wet_days"]) / cal[m["month"]] if cal[m["month"]] else ZERO for m in d["climate"][station])
    wp = d["wind_proxy"].get(station)
    if not wp:
        return wet, tuple(ZERO for _ in range(12))
    by = {m["month"]: m for m in wp}
    base = sum((D(by[mm]["season_share"]) for mm in (1, 4, 7, 10)), ZERO)       # one month per season, as in the workbook
    wind = tuple(D(by[mm]["annual_gust_days"]) * (D(by[mm]["season_share"]) / base) / 3 / cal[mm] for mm in range(1, 13))
    return wet, wind


@dataclass(frozen=True)
class ToolSettings:
    station: str
    working_days_per_week: int = 5
    local_factor: Decimal = ONE
    wind_override: Optional[Decimal] = None        # daily wind-event probability; replaces the proxy
    daily_prelims: Decimal = ZERO                  # supervisor rate x hours per day
    weekly_hire: Decimal = ZERO                    # weekly billed hire + facilities
    recovery: Decimal = ZERO                       # project-specific recovery / remediation allowance


@dataclass(frozen=True)
class Activity:
    task: str
    start: dt.date
    finish: dt.date
    critical: bool = False
    labour: Decimal = ZERO
    plant: Decimal = ZERO
    overrides: dict = field(default_factory=dict)  # any of OVERRIDE_FIELDS -> Decimal
    note: str = ""


@dataclass(frozen=True)
class ActivityResult:
    task: str
    workdays: int
    wet_probability: Decimal
    adjusted_wet_probability: Decimal
    wind_probability: Decimal
    rain_impact: Decimal
    carryover_impact: Decimal
    wind_impact: Decimal
    combined_impact: Decimal            # as the workbook (includes wind)
    combined_impact_excl_wind: Decimal
    direct_allowance: Decimal           # as the workbook (includes wind)
    direct_allowance_excl_wind: Decimal
    lost_wd: Decimal                    # as the workbook (includes wind)
    lost_wd_excl_wind: Decimal
    status: str


@dataclass(frozen=True)
class ToolResult:
    activities: tuple[ActivityResult, ...]
    include_wind: bool
    exposed_pool: Decimal
    direct_allowance: Decimal           # on the chosen basis
    wind_sensitivity: Decimal           # extra direct cost if wind were included (always reported)
    critical_path_delay_wd: Decimal     # on the chosen basis
    additional_billed_weeks: int
    prelims_allowance: Decimal
    hire_allowance: Decimal
    recovery: Decimal
    total_allowance: Decimal
    red_flags: tuple[str, ...]
    confidence: str


def _eff(task: dict[str, Decimal], overrides: dict, key: str) -> Decimal:
    v = overrides.get(key)
    return task[key] if v is None or v == "" else D(v)


def _window(station: str, wpw: int, start: dt.date, finish: dt.date, wind_override: Optional[Decimal]):
    wet_m, wind_m = _monthly(station)
    n = 0
    wet = wind = ZERO
    d = start
    one = dt.timedelta(days=1)
    while d <= finish:
        if d.isoweekday() <= wpw:
            n += 1
            wet += wet_m[d.month - 1]
            wind += wind_m[d.month - 1]
        d += one
    if n == 0:
        return 0, None, None
    return n, wet / n, (wind_override if wind_override is not None else wind / n)


def run_tool(settings: ToolSettings, activities: Sequence[Activity], include_wind: bool = False) -> ToolResult:
    if not 1 <= settings.working_days_per_week <= 7:
        raise ValueError("Working days per week must be between 1 and 7.")
    if settings.local_factor < 0:
        raise ValueError("Local wet-day factor can't be negative.")
    tasks = _tasks()
    res: list[ActivityResult] = []
    flags: list[str] = []
    wpw = settings.working_days_per_week
    for a in activities:
        if a.task not in tasks:
            raise ValueError(f"{a.task!r} is not in the task library.")
        t = tasks[a.task]
        bad_date = a.start < ENGINE_FROM or a.finish > ENGINE_TO or a.finish < a.start
        n, wet, wind = (0, None, None) if bad_date else _window(settings.station, wpw, a.start, a.finish, settings.wind_override)
        if n == 0:
            flags.append(f"{a.task}: dates outside the engine range ({ENGINE_FROM:%d-%b-%Y} to {ENGINE_TO:%d-%b-%Y}) or no working days in the window")
            res.append(ActivityResult(a.task, 0, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, "RED - date input"))
            continue
        adj = min(ONE, wet * settings.local_factor)
        e = lambda k: _eff(t, a.overrides, k)
        rain = adj * e("rain_exposure") * e("rain_loss") * e("nonrecoverable")
        carry = adj * e("carryover") * e("nonrecoverable")
        wnd = wind * e("wind_sensitivity") * e("wind_loss") * e("nonrecoverable")
        comb = min(ONE, rain + carry + wnd)
        comb_x = min(ONE, rain + carry)
        pool = D(a.labour) + D(a.plant)
        if e("wind_sensitivity") >= Decimal("0.2") and wind == 0:
            status = "RED - wind input"
            flags.append(f"{a.task}: wind-sensitive task with no wind data for {settings.station}; enter a sourced wind probability or exclude wind")
        elif settings.local_factor != 1:
            status = "AMBER - local factor requires basis"
        else:
            status = "AMBER - task factors uncalibrated"
        res.append(ActivityResult(a.task, n, wet, adj, wind, rain, carry, wnd, comb, comb_x, pool * comb, pool * comb_x,
                                  n * comb, n * comb_x, status))
    pool_total = sum((D(a.labour) + D(a.plant) for a in activities), ZERO)
    crit = [r for a, r in zip(activities, res) if a.critical]
    direct_wind = sum((r.direct_allowance for r in res), ZERO)
    direct_x = sum((r.direct_allowance_excl_wind for r in res), ZERO)
    delay_wind = sum((r.lost_wd for r in crit), ZERO)
    delay_x = sum((r.lost_wd_excl_wind for r in crit), ZERO)
    direct, delay = (direct_wind, delay_wind) if include_wind else (direct_x, delay_x)
    weeks = int((delay / settings.working_days_per_week).to_integral_value(rounding=ROUND_CEILING)) if delay > 0 else 0
    prelims = delay * D(settings.daily_prelims)
    hire = weeks * D(settings.weekly_hire)
    rec = D(settings.recovery)
    amber = "AMBER - NIWA data GREEN; task factors uncalibrated"
    conf = "RED - resolve flagged inputs before issue" if flags else ("INCOMPLETE - no activities" if not activities else amber)
    return ToolResult(tuple(res), include_wind, pool_total, direct, direct_wind - direct_x, delay, weeks, prelims, hire, rec,
                      direct + prelims + hire + rec, tuple(flags), conf)
