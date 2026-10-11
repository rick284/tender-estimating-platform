"""Assemble a complete, display-ready estimate from imported inputs by running the engine.

Every number returned is recomputed by the engine. 'reconciliation' compares key engine totals to the
values the source workbook displayed, so the estimator can see the platform agrees with the workbook.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any

from .buildup import compute_buildup
from .commercial import compute_tender
from .consolidated import compute_consolidated
from .importers.master_workbook import MasterWorkbookImport
from .models import CommercialInput, WeatherInputs
from .money import D, cents
from .qs import compute_qs
from .weather import compute_weather, baseline_billed_weeks
from .weather_setup import exposed_by_qs, run_setup
from .schedule import auto_map, compute_schedule, default_schedule
from .models import WeatherToolRun


def _f(x: Decimal | None) -> float | None:
    return None if x is None else float(x)


def _rag(text: str) -> str:
    t = (text or "").upper()
    for k in ("RED", "AMBER", "GREEN"):
        if t.startswith(k):
            return k
    return ""


def compute_estimate(m: MasterWorkbookImport) -> dict[str, Any]:
    qs_by_code = {q.code: q for q in m.qs}
    rows = compute_buildup(m.rows, qs_by_code, m.library)
    qs = compute_qs(m.qs, rows)
    by_uid = {src.uid: res for src, res in zip(m.rows, rows)}

    wl = m.weather_links
    # a tender started from scratch has no weather-linked rows until the weather tool is set up for it
    rate_of = lambda u: by_uid[u].applied_rate if u in by_uid else D(0)
    wi = WeatherInputs(
        daily_prelims=rate_of(wl["daily_uid"]) * wl["hours_per_day"],
        weekly_hire=sum((rate_of(u) for u in wl["weekly_uids"]), D(0)),
        recovery_allowance=m.recovery)
    tool, wm, tool_out = m.tool, dict(m.weather_meta), None
    if m.weather_setup:
        # live weather tool: the platform's own run of the Rev2 method replaces the recorded tool outputs
        setup = m.weather_setup
        tr, used, warns = run_setup(setup, exposed_by_qs(m.rows, rows), wi.daily_prelims, wi.weekly_hire, m.recovery)
        rain = tr.direct_allowance - (tr.wind_sensitivity if tr.include_wind else D(0))
        tool = WeatherToolRun(exposed_pool=sum((r.weather_exposed_cost for r in rows), D(0)), rain_wet_ground_cost=rain,
                              critical_path_delay_wd=tr.critical_path_delay_wd, additional_billed_weeks=D(tr.additional_billed_weeks),
                              wind_sensitivity_cost=tr.wind_sensitivity, include_wind=tr.include_wind, live=True)
        wm.update({"station": setup["station"], "tool_station": f"{setup['station']} - NIWA 1991-2020 normals", "start": setup["start"],
                   "baseline_wd": str(setup["baseline_wd"]), "wd_per_week": str(setup["working_days_per_week"]),
                   "tool_version": "NZ_Weather_Risk_Estimating_Tool_Rev2 (live in platform)", "confidence": tr.confidence,
                   "delay_wd": str(tr.critical_path_delay_wd), "dry_programme_wd": str(setup["baseline_wd"]),
                   "rerun_status": "LIVE - recalculated by the platform whenever activities, dates or exposed costs change."})
        tool_out = {
            "settings": {k: setup[k] for k in ("station", "start", "working_days_per_week", "baseline_wd", "local_factor", "local_basis",
                                                 "wind_override", "include_wind")},
            "activities": [{
                "id": a["id"], "task": a["task"], "start": a["start"], "finish": a["finish"], "critical": a["critical"],
                "qs_codes": a["qs_codes"], "labour_input": a["labour"], "plant_input": a["plant"], "overrides": a["overrides"],
                "note": a.get("note", ""), "labour": _f(u["labour"]), "plant": _f(u["plant"]), "workdays": r.workdays,
                "wet_probability": _f(r.wet_probability), "wind_probability": _f(r.wind_probability),
                "rain_impact": _f(r.rain_impact), "carryover_impact": _f(r.carryover_impact), "wind_impact": _f(r.wind_impact),
                "combined_impact": _f(r.combined_impact if tr.include_wind else r.combined_impact_excl_wind),
                "direct_allowance": _f(r.direct_allowance if tr.include_wind else r.direct_allowance_excl_wind),
                "lost_wd": _f(r.lost_wd if tr.include_wind else r.lost_wd_excl_wind), "status": r.status}
                for a, u, r in zip(setup["activities"], used, tr.activities)],
            "red_flags": list(tr.red_flags), "warnings": warns, "confidence": tr.confidence,
            "exposed_pool_activities": _f(tr.exposed_pool)}
    weather = compute_weather(rows, tool, wi)

    commercial = []
    for c in m.commercial:
        ev = weather.allowance if c["method"] == "Weather Engine" else m.risk_feed.get(c["ref"], D(0))
        commercial.append(CommercialInput(c["ref"], c["name"], c["method"], c["include"], c["pct"], c["pc_sum"], ev))
    tender = compute_tender(qs.total_direct, commercial)
    cmap = {c.ref: c for c in commercial}
    cons = compute_consolidated(tender.subtotal, m.overlays, m.overlap, cmap["CA17"].pct, cmap["CA18"].pct)

    # ---- QS lines with their build-up rows
    rows_by_code: dict[str, list[str]] = {}
    for r in rows:
        rows_by_code.setdefault(r.qs_code, []).append(r.row_id)
    qs_out = []
    for line in qs.lines:
        x = m.qs_extra.get(line.code, {})
        qs_out.append({
            "code": line.code, "section": line.section, "description": line.description, "unit": line.unit,
            "quantity": _f(line.quantity), "amount": _f(line.amount), "rate": _f(line.rate),
            "basis": x.get("basis", ""), "source": x.get("source", ""), "status": x.get("status", ""),
            "rag": _rag(x.get("status", "")) or _rag(x.get("flag", "")), "owner": x.get("owner", ""),
            "verification": x.get("verification", ""), "quote_ref": x.get("quote_ref", ""),
            "notes": x.get("notes", ""), "rows": rows_by_code.get(line.code, [])})

    sections = []
    for sec, total in qs.section_totals.items():
        sections.append({"section": sec, "amount": _f(total),
                         "items": [q["code"] for q in qs_out if q["section"] == sec]})

    # ---- Build-up rows with display columns
    lib = m.library
    buildup = []
    for res, src, ex in zip(rows, m.rows, m.row_extra):
        rec = lib.get(src.resource_code)
        buildup.append({
            "row_id": res.row_id, "uid": src.uid, "qs_code": res.qs_code, "task": src.task, "mode": src.mode,
            "resource_type": src.resource_type, "resource_code": src.resource_code,
            "resource": rec.description if rec else "", "unit": res.unit,
            "qs_qty": _f(res.qs_qty), "productivity": _f(src.productivity_rate), "productivity_unit": ex["productivity_unit"],
            "hours": _f(res.applied_duration_hrs), "duration_override": _f(src.duration_override_hrs), "count": _f(src.count), "manual_qty": _f(src.manual_qty),
            "utilisation": _f(src.utilisation), "waste": _f(src.waste),
            "library_rate": _f(res.library_rate), "job_override": _f(src.job_rate_override),
            "applied_rate": _f(res.applied_rate), "cost": _f(res.cost),
            "weather_exposed": src.weather_exposed == "Yes", "qa": res.qa_flag, "workbook_qa": ex["workbook_qa"],
            "verified": src.verified == "Yes", "confidence": ex["confidence"], "rag": _rag(ex["confidence"]),
            "quote_ref": ex["quote_ref"], "source_date": ex["source_date"], "assumption": ex["assumption"],
            "note": ex["note"], "library_source": rec.source if rec else ""})

    library = [{"code": r.code, "category": r.category, "description": r.description, "unit": r.unit,
                "rate": _f(r.base_rate), "operator_included": r.operator_included, "fuel_included": r.fuel_included,
                "source": r.source} for r in lib.values()]

    # ---- Commercial / tender build-up lines
    commercial_out = []
    for c in commercial:
        amt = tender.additions.get(c.ref)
        if amt is None:
            amt = {"CA17": tender.overhead, "CA18": tender.profit, "CA19": tender.bonds, "CA20": tender.retention_finance,
                   "CA21": tender.gst, "CA22": tender.retention_withheld}.get(c.ref, D(0))
        commercial_out.append({"ref": c.ref, "name": c.name, "method": c.method, "include": c.include == "Yes",
                               "pct": _f(c.pct), "pc_sum": _f(c.pc_sum), "amount": _f(amt)})
    stage = lambda r: ("pre" if r <= 16 else "commercial" if r <= 21 else "cashflow")
    for c in commercial_out:
        c["stage"] = stage(int(c["ref"][2:]))

    weather_out = {
        "meta": wm, "exposed_pool": _f(weather.exposed_pool), "tool_pool": _f(tool.exposed_pool),
        "tool_rain_cost": _f(tool.rain_wet_ground_cost), "direct_productivity": _f(weather.direct_productivity),
        "critical_path_delay_wd": _f(tool.critical_path_delay_wd), "daily_prelims": _f(wi.daily_prelims),
        "critical_path_prelims": _f(weather.critical_path_prelims), "additional_weeks": _f(tool.additional_billed_weeks),
        "weekly_hire": _f(wi.weekly_hire), "billed_hire": _f(weather.billed_hire), "recovery": _f(weather.recovery),
        "wind_sensitivity": _f(weather.wind_sensitivity), "wind_included": tool.include_wind, "live": tool.live, "tool": tool_out,
        "links": {"daily_uid": m.weather_links.get("daily_uid", ""), "hours_per_day": m.weather_links.get("hours_per_day", 8),
                  "weekly_uids": list(m.weather_links.get("weekly_uids", []))},
        "allowance": _f(weather.allowance),
        "baseline_weeks": baseline_billed_weeks(D(wm["baseline_wd"]), D(wm["wd_per_week"])),
        "planning_wd": _f(D(wm["baseline_wd"]) + tool.critical_path_delay_wd)}

    consolidated_out = {
        "own_works": _f(cons.own_works), "overlays": [{"name": o.name, "amount": _f(o.amount), "kind": o.kind} for o in m.overlays],
        "overlays_total": _f(cons.overlays_total), "gross_known_package": _f(cons.gross_known_package),
        "confirmed_overlap": _f(cons.confirmed_overlap), "known_after_overlap": _f(cons.known_after_overlap),
        "overhead": _f(cons.overhead), "profit": _f(cons.profit), "all_in": _f(cons.all_in_tender),
        "gross_margin_on_sell": _f(cons.gross_margin_on_sell),
        "overhead_rate": _f(cmap["CA17"].pct), "margin": _f(cmap["CA18"].pct)}

    tender_out = {
        "base_direct": _f(tender.base_direct), "pre_margin_total": _f(tender.pre_margin_total),
        "subtotal": _f(tender.subtotal), "overhead": _f(tender.overhead), "profit": _f(tender.profit),
        "commercial_total": _f(tender.commercial_total), "total_excl_gst": _f(tender.tender_excl_gst),
        "gst": _f(tender.gst), "total_incl_gst": _f(tender.tender_incl_gst)}

    # ---- Reconciliation against what the source workbook displayed (only for an unedited import)
    engine_totals = {
        "Base direct estimate": qs.total_direct, "Pre-margin additions": tender.pre_margin_total,
        "Subtotal before commercial adjustments": tender.subtotal, "Company overhead (CA17)": tender.overhead,
        "Contractor profit (CA18)": tender.profit, "Siteworks tender excl. GST": tender.tender_excl_gst,
        "Weather allowance (CA10)": weather.allowance, "Gross known package": cons.gross_known_package,
        "Working all-in tender excl. GST": cons.all_in_tender,
    }
    reconciliation = []
    if m.reference is not None:
        for name, engine in engine_totals.items():
            wbd = D(m.reference[name])
            reconciliation.append({"name": name, "engine": _f(cents(engine)), "workbook": _f(cents(wbd)),
                                   "difference": _f(cents(engine) - cents(wbd)), "ok": abs(engine - wbd) < Decimal("0.005")})

    # ---- client price schedule (custom format, or an automatic one by QS section)
    schedule_out = _schedule(m, qs, tender, cons, cmap)

    flag_counts: dict[str, int] = {}
    for r in rows:
        flag_counts[r.qa_flag] = flag_counts.get(r.qa_flag, 0) + 1

    return {
        "meta": m.meta, "controls": m.controls,
        "summary": {
            "all_in": _f(cons.all_in_tender), "siteworks_tender": _f(tender.tender_excl_gst),
            "known_cost": _f(cons.gross_known_package), "siteworks_precommercial": _f(tender.subtotal),
            "management_reserve": _f(tender.additions.get("CA16")), "weather_allowance": _f(weather.allowance),
            "gross_margin_on_sell": _f(cons.gross_margin_on_sell), "base_direct": _f(tender.base_direct),
            "dry_programme_wd": _f(D(wm["baseline_wd"])), "planning_wd": weather_out["planning_wd"]},
        "consolidated": consolidated_out, "tender": tender_out, "commercial": commercial_out,
        "qs": qs_out, "sections": sections, "buildup": buildup, "library": library, "weather": weather_out,
        "reconciliation": reconciliation, "qa_counts": flag_counts, "schedule": schedule_out,
        "reconciled": all(r["ok"] for r in reconciliation) if m.reference is not None else None,
        "edited": m.reference is None,
    }


def _schedule(m, qs, tender, cons, cmap) -> dict[str, Any]:
    ca_refs = [ref for ref, amt in tender.additions.items() if amt != 0]
    sources = [{"key": f"qs:{ln.code}", "label": f"{ln.code} {ln.description}", "amount": ln.amount, "own": True, "section": ln.section} for ln in qs.lines]
    sources += [{"key": f"ca:{ref}", "label": f"{ref} {cmap[ref].name}", "amount": tender.additions[ref], "own": True, "section": ""} for ref in ca_refs]
    sources += [{"key": f"overlay:{o.name}", "label": o.name, "amount": o.amount, "own": False, "section": ""} for o in m.overlays]
    auto = m.schedule is None
    if auto:
        sched = default_schedule(list(dict.fromkeys(ln.section for ln in qs.lines)), [o.name for o in m.overlays])
        sched["map"] = auto_map(sched, [{"code": ln.code, "section": ln.section} for ln in qs.lines], [{"name": o.name} for o in m.overlays], ca_refs)
    else:
        sched = m.schedule
    r = compute_schedule(sched, sources, cmap["CA17"].pct, cmap["CA18"].pct, cons.all_in_tender)
    f = _f
    mp = sched.get("map", {})
    return {
        "auto": auto or bool(sched.get("auto")), "name": r["name"], "client": r["client"], "reconciles": r["reconciles"], "problems": r["problems"],
        "total": f(r["total"]), "all_in": f(r["all_in"]), "difference": f(r["difference"]), "gross_package": f(r["gross_package"]),
        "groups": [{"id": g["id"], "name": g["name"], "code": g["code"], "subtotal": f(g["subtotal"]), "total": f(g["total"]), "cost": f(g["cost"]),
                    "hidden": f(g["hidden"]),
                    "lines": [{"ref": x["ref"], "trade": x["trade"], "kind": x["kind"], "amount": f(x["amount"]),
                               "sources": [{"key": y["key"], "label": y["label"], "amount": f(y["amount"])} for y in x["sources"]]} for x in g["lines"]]}
                   for g in r["groups"]],
        "unmapped": [{"key": u["key"], "label": u["label"], "amount": f(u["amount"])} for u in r["unmapped"]],
        "sources": [{"key": s["key"], "label": s["label"], "amount": f(s["amount"]), "own": s["own"], "map": mp.get(s["key"])} for s in sources if s["amount"] != 0],
        "targets": [{"value": f"line:{ln['ref']}", "label": f"{ln['ref']}  {ln['trade']}", "group": g["name"]} for g in sched["groups"] for ln in g["lines"] if ln["kind"] != "margin"]
                   + [{"value": f"group:{g['id']}", "label": f"Inside {g['name']} margin", "group": g["name"]} for g in sched["groups"]] + [{"value": "spread", "label": "Spread across all groups (inside the margin lines)", "group": ""}],
    }
