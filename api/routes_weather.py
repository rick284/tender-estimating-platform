from __future__ import annotations
from typing import Any

from fastapi import APIRouter, Depends

from security import current_user
from tender_engine.weather_tool import tool_data

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/catalog")
async def catalog(user: dict[str, Any] = Depends(current_user)):
    """Stations and the task library of the weather tool (public NIWA normals + the company task defaults)."""
    d = tool_data()
    return {"version": d["version"], "engine_from": d["engine_from"], "engine_to": d["engine_to"], "attribution": d["attribution"],
            "stations": [s["name"] for s in d["stations"]], "wind_proxy_stations": sorted(d["wind_proxy"]),
            "tasks": [{"name": t["name"], "category": t["category"], "rain_exposure": float(t["rain_exposure"]),
                       "rain_loss": float(t["rain_loss"]), "carryover": float(t["carryover"]), "wind_sensitivity": float(t["wind_sensitivity"]),
                       "wind_loss": float(t["wind_loss"]), "nonrecoverable": float(t["nonrecoverable"]), "basis": t["basis"]} for t in d["tasks"]]}
