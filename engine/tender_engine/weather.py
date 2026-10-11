"""Weather allowance (CA10) integration. The climate maths lives in the approved Weather Tool
(NZ_Weather_Risk_Estimating_Tool); this module reproduces the workbook's LIVE integration of
the tool outputs, scaled to the current weather-exposed labour+plant pool:

  direct productivity = tool rain/wet-ground cost x (current exposed pool / tool-run pool)
  critical-path prelims = critical-path delay (WD) x daily time-related prelims
  billed hire/facilities = additional billed weeks x weekly hire
  allowance = productivity + prelims + hire + recovery (+ wind only if included)
Delay is NOT summed across concurrent tasks (the tool takes the critical path).
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Iterable

from .models import RowResult, WeatherToolRun, WeatherInputs
from .money import D, ZERO


@dataclass(frozen=True)
class WeatherResult:
    exposed_pool: Decimal
    direct_productivity: Decimal
    critical_path_prelims: Decimal
    billed_hire: Decimal
    recovery: Decimal
    rain_wet_ground_allowance: Decimal      # excludes wind
    wind_sensitivity: Decimal               # shown separately; added only if included
    allowance: Decimal                      # value feeding CA10


def baseline_billed_weeks(baseline_wd: Decimal, wd_per_week: Decimal) -> int:
    if D(wd_per_week) == 0:
        return 0
    return int((D(baseline_wd) / D(wd_per_week)).to_integral_value(rounding=ROUND_CEILING))


def compute_weather(rows: Iterable[RowResult], tool: WeatherToolRun, inputs: WeatherInputs) -> WeatherResult:
    pool = sum((r.weather_exposed_cost for r in rows), ZERO)
    scale = (pool / tool.exposed_pool) if tool.exposed_pool != 0 else ZERO
    productivity = tool.rain_wet_ground_cost * scale
    prelims = tool.critical_path_delay_wd * inputs.daily_prelims
    hire = tool.additional_billed_weeks * inputs.weekly_hire
    recovery = D(inputs.recovery_allowance)
    rain = productivity + prelims + hire + recovery
    wind = D(tool.wind_sensitivity_cost)
    return WeatherResult(pool, productivity, prelims, hire, recovery, rain, wind,
                         rain + (wind if tool.include_wind else ZERO))
