"""JSON round-trip of the estimate INPUTS, so a saved revision can be recalculated and edited
without the original workbook. Decimals are stored as strings (exact); nothing is rounded."""
from __future__ import annotations
from decimal import Decimal
from typing import Any

from dataclasses import replace

from .ids import display_ids
from .importers.master_workbook import MasterWorkbookImport
from .models import BuildUpRow, LibraryRate, Overlay, QSItem, WeatherToolRun
from .money import D

SCHEMA = 1


def _d(x):            # Decimal -> str
    return None if x is None else str(x)


def _u(x):            # str -> Decimal | None
    return None if x is None else D(x)


def _reference(x):
    """Stored as [[name, value], ...] (no dotted keys); older saves used a dict."""
    if x is None:
        return None
    return dict(x)


def to_json(m: MasterWorkbookImport) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "notes": list(m.notes), "meta": m.meta, "controls": m.controls, "weather_meta": m.weather_meta,
        "weather_links": m.weather_links, "excel_rows": m.excel_rows, "qs_extra": m.qs_extra, "row_extra": m.row_extra,
        "recovery": _d(m.recovery), "overlap": _d(D(m.overlap)), "reference": None if m.reference is None else [[k, v] for k, v in m.reference.items()],
        "risk_feed": {k: _d(D(v)) for k, v in m.risk_feed.items()},
        "library": [{"code": r.code, "description": r.description, "unit": r.unit, "base_rate": _d(r.base_rate),
                     "category": r.category, "operator_included": r.operator_included, "fuel_included": r.fuel_included,
                     "source": r.source} for r in m.library.values()],
        "qs": [{"code": q.code, "section": q.section, "description": q.description, "unit": q.unit,
                "quantity": _d(q.quantity)} for q in m.qs],
        "rows": [{"qs_code": r.qs_code, "mode": r.mode, "resource_type": r.resource_type, "resource_code": r.resource_code,
                  "productivity_rate": _d(r.productivity_rate), "duration_override_hrs": _d(r.duration_override_hrs),
                  "count": _d(r.count), "manual_qty": _d(r.manual_qty), "utilisation": _d(r.utilisation),
                  "waste": _d(r.waste), "job_rate_override": _d(r.job_rate_override), "task": r.task,
                  "verified": r.verified, "weather_exposed": r.weather_exposed, "weather_task_type": r.weather_task_type, "uid": r.uid}
                 for r in m.rows],
        "tool": {"exposed_pool": _d(m.tool.exposed_pool), "rain_wet_ground_cost": _d(m.tool.rain_wet_ground_cost),
                 "critical_path_delay_wd": _d(m.tool.critical_path_delay_wd),
                 "additional_billed_weeks": _d(m.tool.additional_billed_weeks),
                 "wind_sensitivity_cost": _d(m.tool.wind_sensitivity_cost), "include_wind": m.tool.include_wind},
        "commercial": [{"ref": c["ref"], "name": c["name"], "method": c["method"], "include": c["include"],
                        "basis": c.get("basis", ""), "note": c.get("note", ""), "pct": _d(c["pct"]), "pc_sum": _d(c["pc_sum"])} for c in m.commercial],
        "overlays": [{"name": o.name, "amount": _d(o.amount), "kind": o.kind} for o in m.overlays],
        "weather_setup": m.weather_setup,
        "schedule": m.schedule,
        "register": m.register,
        "quotes": m.quotes,
        "risk_truth": m.risk_truth,
        "management_reserve": m.management_reserve,
        "programme": m.programme,
    }


def from_json(d: dict[str, Any]) -> MasterWorkbookImport:
    if d.get("schema") != SCHEMA:
        raise ValueError("Unsupported saved-inputs version")
    t = d["tool"]
    m = _build(d, t)
    # saves made before rows had permanent ids: use the display ids they had at the time
    if any(not r.uid for r in m.rows):
        m.rows = [replace(r, uid=u) for r, u in zip(m.rows, display_ids(m.rows))]
    if "daily_uid" not in m.weather_links:
        uid_at = dict(zip(m.excel_rows, (r.uid for r in m.rows)))
        m.weather_links = {**m.weather_links, "daily_uid": uid_at[m.weather_links["daily_row"]],
                           "weekly_uids": [uid_at[x] for x in m.weather_links["weekly_rows"]]}
    return m


def _build(d, t):
    return MasterWorkbookImport(
        notes=list(d.get("notes", [])), meta=d["meta"], controls=d["controls"], weather_meta=d["weather_meta"], weather_links=d["weather_links"],
        excel_rows=list(d["excel_rows"]), qs_extra=d["qs_extra"], row_extra=d["row_extra"],
        recovery=D(d["recovery"]), overlap=D(d["overlap"]), reference=_reference(d.get("reference")),
        risk_feed={k: D(v) for k, v in d["risk_feed"].items()},
        library={r["code"]: LibraryRate(code=r["code"], description=r["description"], unit=r["unit"],
                                        base_rate=D(r["base_rate"]), category=r["category"],
                                        operator_included=r["operator_included"], fuel_included=r["fuel_included"],
                                        source=r["source"]) for r in d["library"]},
        qs=[QSItem(code=q["code"], section=q["section"], description=q["description"], unit=q["unit"],
                   quantity=D(q["quantity"])) for q in d["qs"]],
        rows=[BuildUpRow(qs_code=r["qs_code"], mode=r["mode"], resource_type=r["resource_type"],
                         resource_code=r["resource_code"], productivity_rate=_u(r["productivity_rate"]),
                         duration_override_hrs=_u(r["duration_override_hrs"]), count=_u(r["count"]),
                         manual_qty=_u(r["manual_qty"]), utilisation=_u(r["utilisation"]), waste=_u(r["waste"]),
                         job_rate_override=_u(r["job_rate_override"]), task=r["task"], verified=r["verified"],
                         weather_exposed=r["weather_exposed"], weather_task_type=r["weather_task_type"], uid=r.get("uid", ""))
              for r in d["rows"]],
        tool=WeatherToolRun(exposed_pool=D(t["exposed_pool"]), rain_wet_ground_cost=D(t["rain_wet_ground_cost"]),
                            critical_path_delay_wd=D(t["critical_path_delay_wd"]),
                            additional_billed_weeks=D(t["additional_billed_weeks"]),
                            wind_sensitivity_cost=D(t["wind_sensitivity_cost"]), include_wind=t["include_wind"]),
        commercial=[{"ref": c["ref"], "name": c["name"], "method": c["method"], "include": c["include"],
                     "basis": c.get("basis", ""), "note": c.get("note", ""), "pct": D(c["pct"]), "pc_sum": D(c["pc_sum"])} for c in d["commercial"]],
        overlays=[Overlay(name=o["name"], amount=D(o["amount"]), kind=o["kind"]) for o in d["overlays"]],
        weather_setup=d.get("weather_setup"),
        schedule=d.get("schedule"),
        register=d.get("register") or [],
        quotes=d.get("quotes") or [],
        risk_truth=d.get("risk_truth") or [],
        management_reserve=d.get("management_reserve"),
        programme=d.get("programme"),
    )
