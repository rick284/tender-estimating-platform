"""Extract the data tables of NZ_Weather_Risk_Estimating_Tool_Rev2.xlsx into tender_engine/data/weather_rev2.json.

Run:  python tools/extract_weather_tool.py private/NZ_Weather_Tool_Rev2.xlsx
Only data is extracted (NIWA 1991-2020 normals, station register, Auckland wind proxy inputs, the task library).
The calculation lives in tender_engine/weather_tool.py and is tested against the workbook itself.
"""
from __future__ import annotations
import json
import sys
import warnings
from pathlib import Path

import openpyxl

warnings.filterwarnings("ignore")
OUT = Path(__file__).resolve().parents[1] / "tender_engine" / "data" / "weather_rev2.json"


def s(x):
    return "" if x is None else str(x).strip()


def main(src: str) -> None:
    wb = openpyxl.load_workbook(src, data_only=True)
    stations = []
    for r in wb["Station Register"].iter_rows(min_row=7, values_only=True):
        if r[0]:
            stations.append({"name": s(r[0]), "rain_station": s(r[1]), "rain_network": s(r[2]), "wet_day_station": s(r[3]),
                             "wet_day_network": s(r[4]), "lat": r[5], "lon": r[6], "height_m": r[7]})
    climate: dict[str, list] = {}
    for r in wb["Climate Data"].iter_rows(min_row=7, values_only=True):
        if r[0]:
            climate.setdefault(s(r[0]), []).append({"month": int(r[1]), "wet_days": repr(float(r[3])), "rain_mm": repr(float(r[4])),
                                                    "calendar_days": repr(float(r[5]))})
    for rows in climate.values():
        rows.sort(key=lambda x: x["month"])
        assert [x["month"] for x in rows] == list(range(1, 13))
    wind: dict[str, list] = {}
    for r in wb["Wind Proxy"].iter_rows(min_row=8, values_only=True):
        if r[0]:
            wind.setdefault(s(r[0]), []).append({"month": int(r[1]), "season": s(r[3]), "season_share": repr(float(r[4])),
                                                 "annual_gust_days": repr(float(r[5])), "basis": s(r[9])})
    tasks = []
    for r in wb["Task Library"].iter_rows(min_row=7, values_only=True):
        if r[0]:
            tasks.append({"name": s(r[0]), "category": s(r[1]), "rain_exposure": s(r[2]), "rain_loss": s(r[3]), "carryover": repr(float(r[4])),
                          "wind_sensitivity": s(r[5]), "wind_loss": s(r[6]), "nonrecoverable": s(r[7]), "status": s(r[8]), "basis": s(r[11])})
    sources = [{"id": s(r[0]), "use": s(r[1]), "source": s(r[2]), "period": s(r[3]), "status": s(r[5]), "url": s(r[6]), "limitation": s(r[7])}
               for r in wb["Source Register"].iter_rows(min_row=4, max_row=9, values_only=True) if r[0]]
    data = {"version": "NZ_Weather_Risk_Estimating_Tool_Rev2", "engine_from": "2025-01-01", "engine_to": "2040-12-31",
            "attribution": "Climate normals: NIWA / Earth Sciences New Zealand, 1991-2020, Creative Commons Attribution 4.0. "
                           "Task factors: company estimating judgement (AMBER until calibrated).",
            "stations": stations, "climate": climate, "wind_proxy": wind, "tasks": tasks, "sources": sources}
    assert len(stations) == 30 and len(climate) == 30 and len(tasks) == 39
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main(sys.argv[1])
