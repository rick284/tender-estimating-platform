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
    weather = compute_weather(rows, m.tool, wi)

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
        "meta": m.weather_meta, "exposed_pool": _f(weather.exposed_pool), "tool_pool": _f(m.tool.exposed_pool),
        "tool_rain_cost": _f(m.tool.rain_wet_ground_cost), "direct_productivity": _f(weather.direct_productivity),
        "critical_path_delay_wd": _f(m.tool.critical_path_delay_wd), "daily_prelims": _f(wi.daily_prelims),
        "critical_path_prelims": _f(weather.critical_path_prelims), "additional_weeks": _f(m.tool.additional_billed_weeks),
        "weekly_hire": _f(wi.weekly_hire), "billed_hire": _f(weather.billed_hire), "recovery": _f(weather.recovery),
        "wind_sensitivity": _f(weather.wind_sensitivity), "wind_included": m.tool.include_wind,
        "allowance": _f(weather.allowance),
        "baseline_weeks": baseline_billed_weeks(D(m.weather_meta["baseline_wd"]), D(m.weather_meta["wd_per_week"])),
        "planning_wd": _f(D(m.weather_meta["baseline_wd"]) + m.tool.critical_path_delay_wd)}

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
            "dry_programme_wd": _f(D(m.weather_meta["baseline_wd"])), "planning_wd": weather_out["planning_wd"]},
        "consolidated": consolidated_out, "tender": tender_out, "commercial": commercial_out,
        "qs": qs_out, "sections": sections, "buildup": buildup, "library": library, "weather": weather_out,
        "reconciliation": reconciliation, "qa_counts": flag_counts,
        "reconciled": all(r["ok"] for r in reconciliation) if m.reference is not None else None,
        "edited": m.reference is None,
    }
