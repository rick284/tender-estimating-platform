from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .money import D

MODE_TIME = "Time x Count"
MODE_QTY = "QS Qty x Factor"
MODE_DIRECT = "Direct Qty"
MODE_LUMP = "Lump Sum / Quote"
MODES = (MODE_TIME, MODE_QTY, MODE_DIRECT, MODE_LUMP)


@dataclass(frozen=True)
class LibraryRate:
    """Resource Rate Library record (true direct cost, excl. GST)."""
    code: str
    description: str = ""
    unit: str = ""
    base_rate: Decimal = Decimal(0)
    category: str = ""
    operator_included: str = ""   # "Yes"/"No"
    fuel_included: str = ""
    source: str = ""              # supplier / quote reference


@dataclass(frozen=True)
class QSItem:
    code: str
    section: str                  # WBS section
    description: str
    unit: str
    quantity: Decimal


@dataclass(frozen=True)
class BuildUpRow:
    """One Resource Build-Up row (inputs only; everything else is derived)."""
    qs_code: str
    mode: str
    resource_type: str            # Labour / Plant / Material / Subcontract / Other
    resource_code: str
    productivity_rate: Optional[Decimal] = None   # QS unit per hour
    duration_override_hrs: Optional[Decimal] = None
    count: Optional[Decimal] = None               # resource count / factor
    manual_qty: Optional[Decimal] = None
    utilisation: Optional[Decimal] = None         # blank -> 1
    waste: Optional[Decimal] = None               # blank -> 0
    job_rate_override: Optional[Decimal] = None   # > 0 replaces library rate
    task: str = ""
    verified: str = ""
    weather_exposed: str = ""
    weather_task_type: str = ""


@dataclass(frozen=True)
class RowResult:
    row_id: str
    qs_code: str
    qs_qty: Decimal
    calc_duration_hrs: Optional[Decimal]
    applied_duration_hrs: Decimal
    library_rate: Decimal
    applied_rate: Decimal
    unit: str
    cost: Decimal
    weather_exposed_cost: Decimal
    qa_flag: str


@dataclass(frozen=True)
class CommercialInput:
    """Commercial Inputs line (CA01..CA25)."""
    ref: str
    name: str
    method: str                   # Risk Engine | Weather Engine | PC Sum | Fixed Amount | % | Markup % | Margin %
    include: str                  # "Yes" / "No"
    pct: Decimal = Decimal(0)
    pc_sum: Decimal = Decimal(0)
    engine_value: Decimal = Decimal(0)   # value delivered by a linked engine (Risk Truth / Weather)


@dataclass(frozen=True)
class WeatherToolRun:
    """Outputs recorded from the approved Weather Tool run (to be replaced by a ported engine)."""
    exposed_pool: Decimal                 # weather-exposed labour+plant pool at the time of the run
    rain_wet_ground_cost: Decimal         # direct productivity output at that pool
    critical_path_delay_wd: Decimal
    additional_billed_weeks: Decimal
    wind_sensitivity_cost: Decimal = Decimal(0)
    include_wind: bool = False


@dataclass(frozen=True)
class WeatherInputs:
    daily_prelims: Decimal                # supervisor rate x hours/day
    weekly_hire: Decimal                  # weekly billed hire + facilities
    recovery_allowance: Decimal = Decimal(0)


@dataclass(frozen=True)
class Overlay:
    """Subcontract / other package added once to the consolidated package."""
    name: str
    amount: Decimal
    kind: str = "QUOTED"
