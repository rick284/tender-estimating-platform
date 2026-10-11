"""Test-only helper: read INPUT cells (constants) from a Master Estimate Workbook.
Never reads cached formula results for inputs, so the engine is genuinely recomputing."""
from __future__ import annotations
from pathlib import Path
import openpyxl

from tender_engine.models import (
    LibraryRate, BuildUpRow, QSItem, CommercialInput, WeatherToolRun, WeatherInputs, Overlay,
)
from tender_engine.money import D


def _s(v):
    return "" if v is None else str(v)


def _n(v):
    return None if v in (None, "") else D(v)


def load_inputs(path: Path):
    f = openpyxl.load_workbook(path)              # formulas (constants are the inputs)
    v = openpyxl.load_workbook(path, data_only=True)  # cached results (only for linked engine feeds)

    lib = {}
    ws = f["Resource Rate Library"]
    for r in range(5, 86):
        code = ws.cell(r, 1).value
        if code:
            lib[code] = LibraryRate(
                code=code, category=_s(ws.cell(r, 2).value), description=_s(ws.cell(r, 3).value),
                unit=_s(ws.cell(r, 5).value), operator_included=_s(ws.cell(r, 7).value),
                fuel_included=_s(ws.cell(r, 8).value), base_rate=D(ws.cell(r, 9).value),
                source=_s(ws.cell(r, 14).value),
            )

    qs = []
    ws = f["QS Takeoff"]
    for r in range(3, 41):
        code = ws.cell(r, 2).value
        if code:
            qs.append(QSItem(code=code, section=_s(ws.cell(r, 1).value), description=_s(ws.cell(r, 3).value),
                             unit=_s(ws.cell(r, 4).value), quantity=D(ws.cell(r, 5).value)))

    rows, excel_rows = [], []
    ws = f["Resource Build-Up"]
    for r in range(7, 307):
        code = ws.cell(r, 2).value
        if not code:
            continue
        c = lambda col: ws[f"{col}{r}"].value
        rows.append(BuildUpRow(
            qs_code=code, mode=_s(c("N")), resource_type=_s(c("O")), resource_code=_s(c("P")),
            productivity_rate=_n(c("I")), duration_override_hrs=_n(c("L")), count=_n(c("R")),
            manual_qty=_n(c("S")), utilisation=_n(c("U")), waste=_n(c("V")),
            job_rate_override=_n(c("X")), task=_s(c("H")), verified=_s(c("AH")),
            weather_exposed=_s(c("AK")), weather_task_type=_s(c("AL")),
        ))
        excel_rows.append(r)

    wr = f["Weather Risk"]
    tool = WeatherToolRun(
        exposed_pool=D(wr["B23"].value), rain_wet_ground_cost=D(wr["B24"].value),
        critical_path_delay_wd=D(wr["B26"].value), additional_billed_weeks=D(wr["B27"].value),
        wind_sensitivity_cost=D(wr["B28"].value), include_wind=(wr["B29"].value == "Yes"),
    )
    recovery = D(wr["B16"].value)

    ci = f["Commercial Inputs"]
    risk_truth = v["Risk Truth"]
    commercial = []
    for r in range(5, 29):
        ref = ci.cell(r, 1).value
        if not ref or not str(ref).startswith("CA"):
            continue
        commercial.append(dict(
            ref=ref, name=_s(ci.cell(r, 2).value), method=_s(ci.cell(r, 3).value),
            pct=D(ci.cell(r, 4).value), pc_sum=D(ci.cell(r, 5).value), include=_s(ci.cell(r, 6).value),
        ))
    risk_feed = {"CA01": D(risk_truth["B12"].value), "CA02": D(risk_truth["B13"].value)}

    cp = f["Consolidated Package"]
    overlays = [
        Overlay("Coast Concrete foundation/floor", D(cp["B6"].value)),
        Overlay("Allied public base", D(cp["B7"].value)),
        Overlay("Allied public setout/as-built/signoff", D(cp["B8"].value)),
        Overlay("Allied private drainage", D(cp["B10"].value)),
    ]
    return dict(library=lib, qs=qs, rows=rows, excel_rows=excel_rows, tool=tool, recovery=recovery,
                commercial=commercial, risk_feed=risk_feed, overlays=overlays,
                overlap=D(cp["B13"].value), cached=v)


def build_commercial(raw, weather_allowance):
    out = []
    for c in raw:
        ev = raw_engine_value(c["ref"], weather_allowance)
        out.append(CommercialInput(ref=c["ref"], name=c["name"], method=c["method"], include=c["include"],
                                   pct=c["pct"], pc_sum=c["pc_sum"], engine_value=ev))
    return out


def raw_engine_value(ref, weather_allowance, _risk={}):
    return weather_allowance if ref == "CA10" else D(0)
