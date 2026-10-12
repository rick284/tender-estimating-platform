"""Assemble a complete, display-ready estimate from imported inputs by running the engine.

Every number returned is recomputed by the engine. 'reconciliation' compares key engine totals to the
values the source workbook displayed, so the estimator can see the platform agrees with the workbook.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any

from .buildup import compute_buildup
from .commercial import compute_tender
from . import risk_truth as rtm
from . import management_reserve as mrm
from .consolidated import compute_consolidated
from .importers.master_workbook import MasterWorkbookImport
from .models import CommercialInput, WeatherInputs
from .money import D, cents
from .qs import compute_qs
from .weather import compute_weather, baseline_billed_weeks
from .weather_setup import exposed_by_qs, run_setup
from .schedule import auto_map, compute_schedule, default_schedule
from .register import status_summary as register_status_summary
from .programme import compute_programme
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

    risks = [x for x in m.register if x["kind"] == "risk"]
    rtr = rtm.compute(m.risk_truth, risks)
    # live Risk Truth feeds CA01 / CA02 once exposures exist (and always on a tender edited in the platform); a workbook that has no
    # Risk Truth tab keeps its recorded feed
    live_rt = bool(m.risk_truth) or m.reference is None
    commercial = []
    for c in m.commercial:
        if c["method"] == "Weather Engine":
            ev = weather.allowance
        elif live_rt and c["ref"] in ("CA01", "CA02"):
            ev = rtr["ca01"] if c["ref"] == "CA01" else rtr["ca02"]
        elif m.management_reserve is not None and c["ref"] == "CA16":
            ev = mrm._num(m.management_reserve.get("selected")) or D(0)
            c = {**c, "method": "Management Reserve"}
        else:
            ev = m.risk_feed.get(c["ref"], D(0))
        commercial.append(CommercialInput(c["ref"], c["name"], c["method"], c["include"], c["pct"], c["pc_sum"], ev))
    tender = compute_tender(qs.total_direct, commercial)
    cmap = {c.ref: c for c in commercial}
    mr_out = _reserve_out(m, commercial, qs.total_direct, tender, rtr)
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
            "weather_exposed": src.weather_exposed == "Yes", "weather_task_type": src.weather_task_type, "qa": res.qa_flag, "workbook_qa": ex["workbook_qa"],
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

    programme_out = _programme(m, qs, rows)

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
        "risk_truth": _risk_truth_out(m, rtr), "management_reserve": mr_out, "register": m.register, "register_summary": register_status_summary(m.register), "quotes": m.quotes, "programme": programme_out,
        "reconciled": all(r["ok"] for r in reconciliation) if m.reference is not None else None,
        "edited": m.reference is None,
    }


def _reserve_out(m, commercial, base_direct, tender, rtr) -> dict[str, Any] | None:
    """Management Reserve adjudication: weighted exposures vs the selected reserve. The markup factor is the tender's own sell effect of one more
    dollar of pre-margin cost, taken from the commercial engine."""
    blk = m.management_reserve
    if blk is None:
        return None
    from dataclasses import replace as _rep
    bump = D(1000)
    ca16 = next((c for c in commercial if c.ref == "CA16"), None)
    if ca16 is None:
        factor = D(1)
    else:          # sell effect of one more dollar of pre-margin reserve, through the commercial engine itself
        more = [_rep(c, include="Yes", method="Management Reserve", engine_value=(c.engine_value if c.include == "Yes" else D(0)) + bump) if c.ref == "CA16" else c
                for c in commercial]
        factor = (compute_tender(base_direct, more).tender_excl_gst - compute_tender(base_direct, [_rep(c, include="Yes", method="Management Reserve", engine_value=c.engine_value if c.include == "Yes" else D(0))
                                                                                                    if c.ref == "CA16" else c for c in commercial]).tender_excl_gst) / bump
    exposures = [{"ref": x["ref"], "addition": o["addition"]} for x, o in zip(m.risk_truth, rtr["exposures"])]
    r = mrm.compute(blk, factor, exposures, tender.subtotal)
    items = []
    for it, o in zip(blk["items"], r["items"]):
        items.append({**it, "cost_impact": None if o["cost_impact"] is None else _f(o["cost_impact"]), "weighted_low": None if o["weighted_low"] is None else _f(o["weighted_low"]),
                      "weighted_high": None if o["weighted_high"] is None else _f(o["weighted_high"]),
                      "weighted_low_sell": None if o["weighted_low_sell"] is None else _f(o["weighted_low_sell"]),
                      "weighted_high_sell": None if o["weighted_high_sell"] is None else _f(o["weighted_high_sell"]),
                      "sensitivity": None if o["sensitivity"] is None else _f(o["sensitivity"]), "counted": o["counted"], "status": o["status"], "reasons": o["reasons"]})
    g = lambda k: None if r[k] is None else _f(r[k])
    return {"items": items, "selected": g("selected"), "selected_sell": g("selected_sell"), "selected_pct": g("selected_pct"), "selected_basis": blk.get("selected_basis", ""),
            "adjudicated_by": blk.get("adjudicated_by", ""), "adjudicated_on": blk.get("adjudicated_on", ""),
            "weighted_low": g("weighted_low"), "weighted_high": g("weighted_high"), "weighted_mid": g("weighted_mid"), "weighted_low_sell": g("weighted_low_sell"),
            "weighted_high_sell": g("weighted_high_sell"), "weighted_mid_sell": g("weighted_mid_sell"), "position": r["position"], "factor": g("factor"),
            "unknown_items": r["unknown_items"], "unquantified_items": r["unquantified_items"], "issues": r["issues"], "notes": r["notes"], "status": r["status"]}


def _risk_truth_out(m, r) -> dict[str, Any]:
    items = []
    for it, o in zip(m.risk_truth, r["exposures"]):
        items.append({**it, "modelled": None if o["modelled"] is None else _f(o["modelled"]), "addition": _f(o["addition"]), "duplication": o["duplication"],
                      "status": o["status"], "reasons": o["reasons"], "flows": o["flows"], "provision_unused": o["provision_unused"]})
    return {"exposures": items, "ca01": _f(r["ca01"]), "ca02": _f(r["ca02"]), "residual_total": _f(r["residual_total"]), "red_risks": r["red_risks"],
            "red_exposures": r["red_exposures"], "amber_exposures": r["amber_exposures"], "duplicate_gate": r["duplicate_gate"],
            "programme_gate": r["programme_gate"], "gate": r["gate"], "issues": r["issues"], "live": bool(m.risk_truth) or m.reference is None}


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


def _programme(m, qs, rows) -> dict[str, Any]:
    qs_info = {ln.code: {"section": ln.section, "description": ln.description, "amount": _f(ln.amount)} for ln in qs.lines}
    if m.programme is None:
        return {"set_up": False, "missing": [{"code": c, "description": i["description"], "amount": i["amount"]} for c, i in qs_info.items() if i["amount"]]}
    hours: dict[str, Decimal] = {}
    for r in rows:
        if not qs_info.get(r.qs_code, {}).get("amount"):                 # reference-only items (no cost) carry no duration of their own
            continue
        if r.applied_duration_hrs and r.applied_duration_hrs > hours.get(r.qs_code, D(0)):
            hours[r.qs_code] = r.applied_duration_hrs
    out = compute_programme(m.programme, hours, qs_info)
    for t in out["tasks"]:
        t["derived"] = t["derived"]
    out["set_up"] = True
    return out
