"""Timekeeper: when the estimator had a tender open, how long they were actually working, what they did, and how long the AI worked.

The browser sends a small heartbeat while a tender is open and the person is active (mouse, keys, scrolling). The server adds up the active seconds;
elapsed time is first-seen to last-seen. What was done is NOT typed in: it is read back from the platform's own records (revisions saved with their
reason, audit events, AI runs) that fall inside the session. Billable time is rounded UP to the company's unit per tender per day; the actual time is always
shown beside it. Nothing here touches an estimate.
"""
from __future__ import annotations
import csv
import datetime as dt
import io
import math
import re
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel

from db import get_db
from security import current_user
from services import audit, new_id, now

router = APIRouter(prefix="/api/time", tags=["time"])

ROUND_CHOICES = (1, 5, 6, 10, 15, 30, 60)
DEFAULT_ROUND = 6
ZONE = ZoneInfo("Pacific/Auckland")
MAX_DELTA = 65                         # a heartbeat can add at most this many active seconds
SLACK = 120                            # activity is matched to a session from this many seconds before its start to after its end
PAGE_LABELS = {"overview": "Overview", "qs": "QS Takeoff", "buildup": "Resource Build-Up", "commercial": "Commercial", "tender": "Tender Build-Up", "consolidated": "Consolidated Package",
               "programme": "Programme", "gantt": "Programme Gantt", "weather": "Weather Risk", "risk": "Risk Truth", "reserve": "Management Reserve", "register": "Register",
               "quotes": "Quotes", "emails": "Emails", "drive": "Drive Documents", "ai": "AI Drafting", "takeoff": "AI Takeoff", "outputs": "Client Outputs", "library": "Rate Library", "revisions": "Revisions"}
AUDIT_TEXT = {"revision.create": "Uploaded workbook", "revision.add_register": "Added register data to a revision", "revision.enable_editing": "Enabled editing on a revision",
              "output.download": "Downloaded", "drive.read": "Read Drive documents", "drive.link_folder": "Linked a Drive folder", "ai.draft": "Ran AI drafting", "ai.accept": "Accepted an AI proposal",
              "ai.reject": "Rejected an AI proposal", "takeoff.run": "Ran AI takeoff", "takeoff.accept": "Accepted a takeoff line", "takeoff.reject": "Rejected a takeoff line",
              "programme.ai_propose": "Asked the AI for programme logic", "programme.ai_decision": "Decided on AI programme logic", "programme.upload": "Opened a programme file",
              "tender.create": "Created the tender", "tender.update": "Updated the tender details", "register": "Updated the register"}
SKIP_AUDIT = {"revision.edit", "ai.draft_failed", "takeoff.failed", "programme.ai_failed", "tender.create_blank"}   # revisions are listed from the revision records; failures aren't work


def _utc(d: Any) -> dt.datetime:
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)      # mongomock returns naive datetimes


async def _round_unit(user: dict[str, Any]) -> int:
    org = await get_db().orgs.find_one({"_id": user["org_id"]}) or {}
    return int(org.get("time_round_minutes") or DEFAULT_ROUND)


async def timed_ai(user: dict[str, Any], tender_id: str, kind: str, model: str, fn, *args) -> Any:
    """Run one AI call in a worker thread and keep how long it took (and tokens used) for the timesheet. A failed call is kept too: the time was spent."""
    import time
    from starlette.concurrency import run_in_threadpool as pool
    started, t0, ok, data = now(), time.monotonic(), False, None
    try:
        data = await pool(fn, *args)
        ok = True
        return data
    finally:
        usage = (data.pop("_usage", None) if isinstance(data, dict) else None) or {}
        await get_db().ai_runs.insert_one({"_id": new_id(), "org_id": user["org_id"], "user_id": user["_id"], "tender_id": tender_id, "kind": kind, "model": model, "started_at": started,
                                           "seconds": round(time.monotonic() - t0, 1), "ok": ok, "input_tokens": usage.get("input", 0), "output_tokens": usage.get("output", 0)})


class Ping(BaseModel):
    session_id: str
    tender_id: str
    page: str = ""
    active_seconds: int = 0
    draft_edits: int = 0
    end: bool = False


@router.post("/ping")
async def ping(body: Ping, user: dict[str, Any] = Depends(current_user)):
    """Heartbeat from an open tender. Adds the active seconds the browser measured (capped), never more than the real time since the last ping."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", body.session_id):
        raise HTTPException(422, "Bad session id.")
    db = get_db()
    t = await db.tenders.find_one({"_id": body.tender_id, "org_id": user["org_id"]})
    if not t:
        raise HTTPException(404, "Tender not found.")
    ts = now()
    s = await db.time_sessions.find_one({"_id": body.session_id, "org_id": user["org_id"], "user_id": user["_id"]})
    delta = max(0, min(int(body.active_seconds), MAX_DELTA))
    page = re.sub(r"[^a-z_]", "", body.page.lower())[:30]
    if s is None:
        started = ts - dt.timedelta(seconds=delta)
        await db.time_sessions.insert_one({"_id": body.session_id, "org_id": user["org_id"], "user_id": user["_id"], "tender_id": t["_id"], "tender_name": t["name"], "started_at": started,
                                           "last_seen": ts, "active_seconds": delta, "pages": {page: delta} if page else {}, "draft_edits": int(body.draft_edits), "ended": body.end, "note": ""})
        return {"ok": True}
    since = (ts - _utc(s["last_seen"])).total_seconds()
    delta = int(min(delta, since + 1))
    upd: dict[str, Any] = {"$set": {"last_seen": ts, "ended": body.end}, "$inc": {"active_seconds": delta}, "$max": {"draft_edits": int(body.draft_edits)}}
    if page and delta:
        upd["$inc"][f"pages.{page}"] = delta
    await db.time_sessions.update_one({"_id": body.session_id}, upd)
    return {"ok": True}


def _fmt_span(sec: float) -> str:
    m = int(round(sec / 60))
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"


async def _summary(db: Any, user: dict[str, Any], s: dict[str, Any], runs: list[dict[str, Any]]) -> list[str]:
    a, b = _utc(s["started_at"]) - dt.timedelta(seconds=SLACK), _utc(s["last_seen"]) + dt.timedelta(seconds=SLACK)
    lines: list[str] = []
    pages = sorted((s.get("pages") or {}).items(), key=lambda kv: -kv[1])
    where = [f"{PAGE_LABELS.get(p, p)} ({_fmt_span(sec)})" for p, sec in pages[:5] if sec >= 30]
    if where:
        lines.append("Time in: " + ", ".join(where))
    revs = await db.revisions.find({"tender_id": s["tender_id"], "org_id": user["org_id"], "created_by": user["_id"], "created_at": {"$gte": a, "$lte": b}}).to_list(50)
    for r in revs:
        if r.get("changes") is not None and r.get("note"):
            lines.append(f"Saved {r['label']} ({len(r['changes'])} change{'s' if len(r['changes']) != 1 else ''}): {r['note']}")
    events = await db.audit.find({"org_id": user["org_id"], "user_id": user["_id"], "target": s["tender_id"], "ts": {"$gte": a, "$lte": b}}).sort("ts", 1).to_list(200)
    seen: dict[str, int] = {}
    for e in events:
        if e["action"] in SKIP_AUDIT or e["action"].startswith("time."):
            continue
        text = AUDIT_TEXT.get(e["action"]) or e["action"].replace(".", " ").replace("_", " ").capitalize()
        d = (e.get("detail") or "").strip()
        full = f"{text}: {d}" if d and e["action"] in ("output.download", "revision.create", "drive.read") else text
        seen[full] = seen.get(full, 0) + 1
    lines += [f"{t}" + (f" (x{n})" if n > 1 else "") for t, n in seen.items()]
    mine = [r for r in runs if a <= _utc(r["started_at"]) <= b and r["tender_id"] == s["tender_id"]]
    if mine:
        lines.append(f"AI worked {_fmt_span(sum(r['seconds'] for r in mine))} across {len(mine)} run{'s' if len(mine) != 1 else ''}")
    saved = any(r.get("changes") is not None and r.get("note") for r in revs)
    if not saved and not s.get("draft_edits") and s["active_seconds"] >= 60:
        lines.append("Review only: read and looked through the estimate, no changes made")
    if s.get("draft_edits"):
        lines.append(f"Edit draft reached {s['draft_edits']} change{'s' if s['draft_edits'] != 1 else ''}" + ("" if any(r.get("note") for r in revs) else " (not saved in this session)"))
    return lines


def _day(d: dt.datetime) -> str:
    return _utc(d).astimezone(ZONE).strftime("%Y-%m-%d")


def _rng(start: str, end: str) -> tuple[dt.datetime, dt.datetime]:
    try:
        a = dt.datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=ZONE)
        b = dt.datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=ZONE) + dt.timedelta(days=1)
    except ValueError:
        raise HTTPException(422, "Dates must look like 2026-10-14.")
    if b - a > dt.timedelta(days=400):
        raise HTTPException(422, "Choose a range of 400 days or less.")
    return a.astimezone(dt.timezone.utc), b.astimezone(dt.timezone.utc)


async def build_timesheet(user: dict[str, Any], start: str, end: str, tender_id: str = "") -> dict[str, Any]:
    db = get_db()
    unit = await _round_unit(user)
    a, b = _rng(start, end)
    q: dict[str, Any] = {"org_id": user["org_id"], "user_id": user["_id"]}
    if tender_id:
        q["tender_id"] = tender_id
    sessions = await db.time_sessions.find({**q, "started_at": {"$gte": a, "$lt": b}}).sort("started_at", 1).to_list(5000)
    manual = await db.time_entries.find({**q, "date": {"$gte": start, "$lte": end}}).to_list(2000)
    runs = await db.ai_runs.find({**q, "started_at": {"$gte": a - dt.timedelta(seconds=SLACK), "$lt": b + dt.timedelta(seconds=SLACK)}}).sort("started_at", 1).to_list(5000)
    names = {t["_id"]: t["name"] async for t in db.tenders.find({"org_id": user["org_id"]})}
    entries: list[dict[str, Any]] = []
    for s in sessions:
        st, en = _utc(s["started_at"]), _utc(s["last_seen"])
        entries.append({"kind": "session", "id": s["_id"], "date": _day(st), "tender_id": s["tender_id"], "tender_name": names.get(s["tender_id"], s.get("tender_name", "(deleted tender)")),
                        "start": st.isoformat(), "end": en.isoformat(), "elapsed_seconds": max(int((en - st).total_seconds()), int(s["active_seconds"])), "active_seconds": int(s["active_seconds"]), "note": s.get("note", ""),
                        "summary": await _summary(db, user, s, runs), "open": not s.get("ended") and (now() - en).total_seconds() < 120})
    for m in manual:
        entries.append({"kind": "manual", "id": m["_id"], "date": m["date"], "tender_id": m.get("tender_id", ""), "tender_name": names.get(m.get("tender_id", ""), "No tender") if m.get("tender_id") else "No tender",
                        "start": "", "end": "", "elapsed_seconds": int(m["minutes"]) * 60, "active_seconds": int(m["minutes"]) * 60, "note": m.get("note", ""), "summary": [], "open": False})
    ai_by: dict[tuple[str, str], dict[str, Any]] = {}
    for r in runs:
        d = _day(r["started_at"])
        if not (start <= d <= end):
            continue
        x = ai_by.setdefault((d, r["tender_id"]), {"seconds": 0.0, "runs": 0, "input_tokens": 0, "output_tokens": 0})
        x["seconds"] += r["seconds"]; x["runs"] += 1; x["input_tokens"] += r.get("input_tokens", 0); x["output_tokens"] += r.get("output_tokens", 0)
    entries.sort(key=lambda e: (e["date"], e["start"] or "~"))
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for e in entries:
        g = groups.setdefault((e["date"], e["tender_id"]), {"date": e["date"], "tender_id": e["tender_id"], "tender_name": e["tender_name"], "active_seconds": 0, "elapsed_seconds": 0, "sessions": 0, "work": []})
        g["active_seconds"] += e["active_seconds"]; g["elapsed_seconds"] += e["elapsed_seconds"]; g["sessions"] += 1
        g["work"] += e["summary"] + ([e["note"]] if e["note"] else [])
    for (d, tid), x in ai_by.items():                       # a day with only AI activity still shows
        groups.setdefault((d, tid), {"date": d, "tender_id": tid, "tender_name": names.get(tid, "(deleted tender)"), "active_seconds": 0, "elapsed_seconds": 0, "sessions": 0, "work": []})
    days = []
    for (d, tid), g in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[1]["tender_name"]), reverse=True):
        g["billable_minutes"] = math.ceil(g["active_seconds"] / 60 / unit) * unit if g["active_seconds"] else 0
        g["ai"] = {k: (round(v, 1) if k == "seconds" else v) for k, v in ai_by.get((d, tid), {"seconds": 0, "runs": 0, "input_tokens": 0, "output_tokens": 0}).items()}
        days.append(g)
    tot = {"active_seconds": sum(g["active_seconds"] for g in days), "elapsed_seconds": sum(g["elapsed_seconds"] for g in days), "billable_minutes": sum(g["billable_minutes"] for g in days),
           "ai_seconds": round(sum(g["ai"]["seconds"] for g in days), 1), "ai_runs": sum(g["ai"]["runs"] for g in days)}
    return {"round_minutes": unit, "start": start, "end": end, "groups": days, "entries": sorted(entries, key=lambda e: (e["date"], e["start"] or "~"), reverse=True), "totals": tot}


@router.get("/timesheet")
async def timesheet(start: str, end: str, tender_id: str = "", user: dict[str, Any] = Depends(current_user)):
    return await build_timesheet(user, start, end, tender_id)


def _mins(sec: float) -> str:
    return f"{sec / 60:.1f}"


@router.get("/timesheet.csv")
async def timesheet_csv(start: str, end: str, tender_id: str = "", detail: bool = False, user: dict[str, Any] = Depends(current_user)):
    """One row per tender per day (rounded up as well as actual), or with detail=true one row per session / manual entry."""
    ts = await build_timesheet(user, start, end, tender_id)
    out = io.StringIO()
    w = csv.writer(out)
    if detail:
        w.writerow(["Date", "Tender", "Type", "Start", "End", "Elapsed minutes", "Active minutes", "What was done"])
        for e in reversed(ts["entries"]):
            fmt = lambda s: _utc(dt.datetime.fromisoformat(s)).astimezone(ZONE).strftime("%H:%M") if s else ""      # noqa: E731
            w.writerow([e["date"], e["tender_name"], "Manual" if e["kind"] == "manual" else "Session", fmt(e["start"]), fmt(e["end"]), _mins(e["elapsed_seconds"]), _mins(e["active_seconds"]),
                        "; ".join(e["summary"] + ([e["note"]] if e["note"] else []))])
    else:
        w.writerow(["Date", "Tender", "Elapsed minutes", "Active minutes", f"Billable minutes (rounded up to {ts['round_minutes']})", "AI runs", "AI minutes", "What was done"])
        for g in reversed(ts["groups"]):
            w.writerow([g["date"], g["tender_name"], _mins(g["elapsed_seconds"]), _mins(g["active_seconds"]), g["billable_minutes"], g["ai"]["runs"], _mins(g["ai"]["seconds"]), "; ".join(g["work"])])
    await audit(get_db(), user, "time.export", "", f"{start} to {end}")
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="timesheet_{start}_to_{end}.csv"'})


class NoteIn(BaseModel):
    note: str = ""


class ManualIn(BaseModel):
    date: str
    minutes: int
    note: str = ""
    tender_id: str = ""


async def _check_manual(user: dict[str, Any], b: ManualIn) -> None:
    try:
        dt.datetime.strptime(b.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(422, "The date must look like 2026-10-14.")
    if not 1 <= b.minutes <= 1440:
        raise HTTPException(422, "Minutes must be between 1 and 1440.")
    if not b.note.strip():
        raise HTTPException(422, "Say what the time was for.")
    if b.tender_id and not await get_db().tenders.find_one({"_id": b.tender_id, "org_id": user["org_id"]}):
        raise HTTPException(404, "Tender not found.")


@router.post("/entries")
async def add_entry(b: ManualIn, user: dict[str, Any] = Depends(current_user)):
    await _check_manual(user, b)
    doc = {"_id": new_id(), "org_id": user["org_id"], "user_id": user["_id"], "tender_id": b.tender_id, "date": b.date, "minutes": b.minutes, "note": b.note.strip()[:500], "created_at": now()}
    await get_db().time_entries.insert_one(doc)
    await audit(get_db(), user, "time.manual_add", b.tender_id, f"{b.date} {b.minutes} min")
    return {"id": doc["_id"]}


@router.put("/entries/{eid}")
async def edit_entry(eid: str, b: ManualIn, user: dict[str, Any] = Depends(current_user)):
    await _check_manual(user, b)
    r = await get_db().time_entries.update_one({"_id": eid, "org_id": user["org_id"], "user_id": user["_id"]}, {"$set": {"tender_id": b.tender_id, "date": b.date, "minutes": b.minutes, "note": b.note.strip()[:500]}})
    if not r.matched_count:
        raise HTTPException(404, "Entry not found.")
    await audit(get_db(), user, "time.manual_edit", b.tender_id, f"{b.date} {b.minutes} min")
    return {"ok": True}


@router.delete("/entries/{eid}")
async def delete_entry(eid: str, user: dict[str, Any] = Depends(current_user)):
    r = await get_db().time_entries.delete_one({"_id": eid, "org_id": user["org_id"], "user_id": user["_id"]})
    if not r.deleted_count:
        raise HTTPException(404, "Entry not found.")
    await audit(get_db(), user, "time.manual_delete", "", eid)
    return {"ok": True}


@router.put("/sessions/{sid}")
async def session_note(sid: str, b: NoteIn, user: dict[str, Any] = Depends(current_user)):
    r = await get_db().time_sessions.update_one({"_id": sid, "org_id": user["org_id"], "user_id": user["_id"]}, {"$set": {"note": b.note.strip()[:500]}})
    if not r.matched_count:
        raise HTTPException(404, "Session not found.")
    return {"ok": True}


@router.delete("/sessions/{sid}")
async def session_delete(sid: str, user: dict[str, Any] = Depends(current_user)):
    db = get_db()
    s = await db.time_sessions.find_one({"_id": sid, "org_id": user["org_id"], "user_id": user["_id"]})
    if not s:
        raise HTTPException(404, "Session not found.")
    await db.time_sessions.delete_one({"_id": sid})
    await audit(db, user, "time.session_delete", s["tender_id"], f"{_utc(s['started_at']).isoformat()} {int(s['active_seconds'])}s active")
    return {"ok": True}


@router.get("/settings")
async def get_settings(user: dict[str, Any] = Depends(current_user)):
    return {"round_minutes": await _round_unit(user), "choices": list(ROUND_CHOICES), "can_change": user.get("role") == "owner"}


@router.put("/settings")
async def put_settings(body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    if user.get("role") != "owner":
        raise HTTPException(403, "Only the company owner can change how time is rounded.")
    m = body.get("round_minutes")
    if m not in ROUND_CHOICES:
        raise HTTPException(422, f"Round to one of {', '.join(map(str, ROUND_CHOICES))} minutes.")
    await get_db().orgs.update_one({"_id": user["org_id"]}, {"$set": {"time_round_minutes": m}})
    await audit(get_db(), user, "time.settings", "", f"round to {m} min")
    return {"round_minutes": m}
