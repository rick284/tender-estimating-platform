from __future__ import annotations
import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .context import OutputContext

HEAD = PatternFill("solid", fgColor="111111")
CRIT = PatternFill("solid", fgColor="FBE4E4")
MONEY = '"$"#,##0.00;[Red]-"$"#,##0.00;;@'


def _head(ws, row: int, labels: list[str]) -> None:
    for i, label in enumerate(labels, start=1):
        c = ws.cell(row, i, label)
        c.font = Font(name="Calibri", bold=True, color="FFFFFF")
        c.fill = HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center")


def programme_workbook(est: dict[str, Any], ctx: OutputContext) -> bytes:
    """Programme (with the critical path) and an MS Project import sheet: Tasks > Import: map Name, Duration, Predecessors, Start, Finish."""
    pr = est["programme"]
    if not pr.get("set_up"):
        raise ValueError("The programme hasn't been set up for this tender yet.")
    wb = Workbook()
    ws = wb.active
    ws.title = "Programme"
    ws["A1"] = f"{ctx.project or est['meta'].get('project', '')} - Programme"
    ws["A1"].font = Font(name="Calibri", bold=True, size=14)
    ws["A2"] = (f"{ctx.revision} | start {pr['start'] or 'not set'} | {pr['days_per_week']}-day week, {pr['hours_per_day']}-hour day | "
                f"dry duration {pr['duration']} working days" + (f" | finish {pr['finish']}" if pr.get("finish") else "") + " | no public holidays or shutdowns modelled")
    ws["A2"].font = Font(name="Calibri", italic=True, color="555555")
    ws["A3"] = "Critical path: " + (" > ".join(pr["critical_path"]) or "none")
    _head(ws, 5, ["Code", "Task", "Section", "Days", "Derived days", "Predecessors", "Start", "Finish", "Float (days)", "Critical", "Basis", "Notes"])
    r = 5
    for t in pr["tasks"]:
        r += 1
        vals = [t["code"], t["name"], t["section"], t["duration"], t["derived"], ", ".join(t["predecessors"]), t["start"], t["finish"], t["float"],
                "Yes" if t["critical"] else ("Runs throughout" if t["hammock"] else ""), t["basis"], t["note"]]
        for i, v in enumerate(vals, start=1):
            c = ws.cell(r, i, v)
            c.alignment = Alignment(wrap_text=i in (2, 11, 12), vertical="top")
            if t["critical"]:
                c.fill = CRIT
    for i, w in enumerate([12, 54, 26, 8, 12, 22, 12, 12, 11, 15, 34, 50], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "C6"

    # MS Project import: summary task per section, then its tasks; predecessors by ID (finish-to-start)
    mp = wb.create_sheet("MS Project Import")
    _head(mp, 1, ["ID", "Outline Level", "WBS", "Task Name", "Duration", "Predecessors", "Fixed Cost", "Start", "Finish", "Category", "Source Estimate", "Quantity", "Unit", "Notes"])
    sections: dict[str, list[dict[str, Any]]] = {}
    for t in pr["tasks"]:
        sections.setdefault(t["section"], []).append(t)
    ids: dict[str, int] = {}
    n = 0
    plan: list[tuple[str, dict[str, Any] | None]] = []
    for sec, ts in sections.items():
        n += 1
        plan.append((sec, None))
        for t in ts:
            n += 1
            ids[t["code"]] = n
            plan.append((sec, t))
    qs = {q["code"]: q for q in est["qs"]}
    row = 1
    for i, (sec, t) in enumerate(plan, start=1):
        row += 1
        if t is None:
            vals = [i, 1, "", sec, "0 days", "", None, None, None, "Summary", ctx.revision, None, "", "Summary task"]
        else:
            q = qs.get(t["qs_code"], {})
            vals = [i, 2, t["code"], t["name"], f"{t['duration']} days", ";".join(str(ids[p]) for p in t["predecessors"] if p in ids), t["amount"] if t["amount"] else None,
                    t["start"], t["finish"], sec, ctx.revision, q.get("quantity"), q.get("unit", ""), t["note"] or t["basis"]]
        for j, v in enumerate(vals, start=1):
            c = mp.cell(row, j, v)
            if j == 7 and v is not None:
                c.number_format = MONEY
    for i, w in enumerate([6, 8, 12, 56, 11, 14, 14, 12, 12, 26, 12, 11, 8, 48], start=1):
        mp.column_dimensions[get_column_letter(i)].width = w
    for w in wb.worksheets:
        w.sheet_view.showGridLines = False
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
