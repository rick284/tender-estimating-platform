from __future__ import annotations
import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .context import OutputContext, pct

MONEY = '"$"#,##0.00;[Red]-"$"#,##0.00;;@'
HEAD = PatternFill("solid", fgColor="111111")
BAND = PatternFill("solid", fgColor="EDEDED")
THIN = Side(style="thin", color="BBBBBB")
BOLD = Font(name="Calibri", bold=True)


def _title(ws, text: str, sub: str) -> None:
    ws["A1"] = text
    ws["A1"].font = Font(name="Calibri", bold=True, size=14)
    ws["A2"] = sub
    ws["A2"].font = Font(name="Calibri", italic=True, color="555555")


def _head(ws, row: int, labels: list[str]) -> None:
    for i, label in enumerate(labels, start=1):
        c = ws.cell(row, i, label)
        c.font = Font(name="Calibri", bold=True, color="FFFFFF")
        c.fill = HEAD
        c.alignment = Alignment(horizontal="right" if i > 1 and label in ("Total ($)", "Amount excl GST", "Amount") else "left", vertical="center", wrap_text=True)


def _widths(ws, widths: list[float]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def pricing_workbook(est: dict[str, Any], ctx: OutputContext) -> bytes:
    """Client pricing pack: Client Summary, Price Schedule and Reconciliation sheets."""
    wb = Workbook()
    s, c, sch, meta = est["summary"], est["consolidated"], est["schedule"], est["meta"]
    sub = f"{ctx.revision} | {ctx.issue_date} | all values exclude GST"

    # ---- Client Summary
    ws = wb.active
    ws.title = "Client Summary"
    _title(ws, f"{ctx.project or meta.get('project', '')} - Client Pricing", sub)
    info = [("Project", ctx.project or meta.get("project", "")), ("Client", ctx.client), ("Location", ctx.location or meta.get("location", "")),
            ("Prepared by", f"{ctx.prepared_by} | {ctx.company}".strip(" |")), ("GST", "All values exclude GST"),
            ("Programme", meta.get("programme", "")), ("Release", est["controls"].get("cover_release") or est["controls"].get("release_status", ""))]
    r = 4
    for k, v in info:
        if v:
            ws.cell(r, 1, k).font = BOLD
            ws.cell(r, 2, v).alignment = Alignment(wrap_text=True, vertical="top")
            r += 1
    r += 1
    _head(ws, r, ["Package", "Amount excl GST", "Treatment"])
    rows = [("Own works before overhead and profit", c["own_works"], "Quantities priced from the build-up, including allowances and reserve")]
    rows += [(o["name"], o["amount"], f"Subcontract package ({o['kind'].lower()})") for o in c["overlays"]]
    if c["confirmed_overlap"]:
        rows.append(("Confirmed overlap", -c["confirmed_overlap"], "Removed from the known package"))
    rows += [("Current known package before overhead and profit", c["gross_known_package"] - (c["confirmed_overlap"] or 0), "Own works plus subcontract packages"),
             (f"Company overhead ({pct(c['overhead_rate'], 1)})", c["overhead"], "Applied across the known package"),
             (f"Profit ({pct(c['margin'], 1)} true margin)", c["profit"], "Applied after overhead; true margin, not markup"),
             ("WORKING ALL-IN TENDER", c["all_in"], "Current answer to: what will this cost?")]
    for label, amount, note in rows:
        r += 1
        ws.cell(r, 1, label)
        a = ws.cell(r, 2, amount)
        a.number_format = MONEY
        ws.cell(r, 3, note).alignment = Alignment(wrap_text=True, vertical="top")
        if label.isupper() or label.startswith("Current known"):
            for col in (1, 2, 3):
                ws.cell(r, col).font = BOLD
                ws.cell(r, col).fill = BAND
    r += 2
    ws.cell(r, 1, "Gross margin on sell").font = BOLD
    ws.cell(r, 2, c["gross_margin_on_sell"]).number_format = "0.00%"
    _widths(ws, [52, 20, 70])

    # ---- Price Schedule
    ws = wb.create_sheet("Price Schedule")
    _title(ws, (sch["client"] or ctx.client or "").upper() or (ctx.project or meta.get("project", "")).upper(), f"{sch['name'] or 'Price schedule'} | {sub}")
    r = 4
    _head(ws, r, ["Ref", "Trade", "Total ($)"])
    totals_rows = []
    for g in sch["groups"]:
        r += 1
        ws.cell(r, 1, g["name"]).font = BOLD
        for col in (1, 2, 3):
            ws.cell(r, col).fill = BAND
        pre = [x for x in g["lines"] if x["kind"] == "work"]
        post = [x for x in g["lines"] if x["kind"] != "work"]
        for x in pre:
            r += 1
            ws.cell(r, 1, x["ref"])
            ws.cell(r, 2, x["trade"])
            ws.cell(r, 3, x["amount"] if abs(x["amount"]) >= 0.005 else None).number_format = MONEY
        r += 1
        ws.cell(r, 2, "SUB-TOTAL").font = BOLD
        ws.cell(r, 3, g["subtotal"]).number_format = MONEY
        ws.cell(r, 3).font = BOLD
        for x in post:
            r += 1
            ws.cell(r, 1, x["ref"])
            ws.cell(r, 2, x["trade"])
            ws.cell(r, 3, x["amount"] if abs(x["amount"]) >= 0.005 else None).number_format = MONEY
        r += 1
        label = ("TOTAL (EXCL GST)" if len(sch["groups"]) == 1 else f"{g['name']} SUB-TOTAL (EXCL GST)") + (f" {g['code']}" if g["code"] else "")
        ws.cell(r, 2, label).font = BOLD
        ws.cell(r, 3, g["total"]).number_format = MONEY
        ws.cell(r, 3).font = BOLD
        for col in (1, 2, 3):
            ws.cell(r, col).border = Border(top=THIN, bottom=THIN)
        totals_rows.append(g)
    if len(sch["groups"]) > 1:
        r += 2
        codes = "+".join(g["code"] for g in sch["groups"] if g["code"])
        ws.cell(r, 2, "COMBINED TOTAL (EXCL GST)" + (f" {codes}" if codes else "")).font = Font(name="Calibri", bold=True, size=12)
        ws.cell(r, 3, sch["total"]).number_format = MONEY
        ws.cell(r, 3).font = Font(name="Calibri", bold=True, size=12)
    r += 2
    ws.cell(r, 1, "This schedule reconciles to the working all-in tender. Where the schedule headings do not match the underlying breakdown, allocations are "
                  "disclosed in the Client Summary rather than inventing a false split.").alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    ws.row_dimensions[r].height = 42
    _widths(ws, [14, 62, 20])

    # ---- Reconciliation
    ws = wb.create_sheet("Reconciliation")
    _title(ws, "Price schedule reconciliation", sub)
    _head(ws, 4, ["Control", "Amount", "Note"])
    ctrl = [("Known package (own works + subcontract)", sch["gross_package"], "Every dollar must be mapped to a schedule line"),
            ("Mapped to schedule lines or margin", sch["gross_package"] - sum(u["amount"] for u in sch["unmapped"]), ""),
            ("Not yet mapped", sum(u["amount"] for u in sch["unmapped"]), "Must be nil before issue"),
            ("Schedule total", sch["total"], "Sum of the group totals"),
            ("Working all-in tender", sch["all_in"], "From the consolidated package"),
            ("Difference", sch["difference"], "OK" if sch["reconciles"] else "CHECK")]
    r = 4
    for k, v, note in ctrl:
        r += 1
        ws.cell(r, 1, k)
        ws.cell(r, 2, v).number_format = MONEY if k != "Difference" else '"$"#,##0.00'
        ws.cell(r, 3, note)
    r += 2
    _head(ws, r, ["Group", "Schedule lines (excl margin)", "Held inside margin / spread", "Cost", "Group total"])
    for g in sch["groups"]:
        r += 1
        lines = sum(x["amount"] for x in g["lines"] if x["kind"] != "margin")
        for col, v in enumerate([g["name"], lines, g["hidden"], g["cost"], g["total"]], start=1):
            cell = ws.cell(r, col, v)
            if col > 1:
                cell.number_format = MONEY
    r += 2
    _head(ws, r, ["Schedule line", "Source", "Amount"])
    for g in sch["groups"]:
        for x in g["lines"]:
            for src in x["sources"]:
                r += 1
                ws.cell(r, 1, f"{x['ref']}  {x['trade']}")
                ws.cell(r, 2, src["label"])
                ws.cell(r, 3, src["amount"]).number_format = MONEY
    _widths(ws, [46, 52, 22, 20, 20])

    for w in wb.worksheets:
        w.sheet_view.showGridLines = False
        w.freeze_panes = None
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
