"""Tender estimating calculation engine.

Pure, deterministic arithmetic reproducing the Master Estimate Workbook cost chain:
Resource Rate Library -> Resource Build-Up -> QS Takeoff -> Tender Build-Up
-> Consolidated Package. The AI never computes totals; it only proposes inputs.
"""
from .money import D, cents
from .models import (
    LibraryRate, BuildUpRow, QSItem, CommercialInput, WeatherToolRun, WeatherInputs,
    Overlay, RowResult,
)
from .buildup import compute_buildup
from .qs import compute_qs
from .commercial import compute_tender
from .weather import compute_weather
from .consolidated import compute_consolidated

__all__ = [
    "D", "cents", "LibraryRate", "BuildUpRow", "QSItem", "CommercialInput",
    "WeatherToolRun", "WeatherInputs", "Overlay", "RowResult",
    "compute_buildup", "compute_qs", "compute_tender", "compute_weather",
    "compute_consolidated",
]
