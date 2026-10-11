from __future__ import annotations
import io
from typing import Any, Callable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .context import OutputContext, money, pct

INK = colors.HexColor("#111111")
GREY = colors.HexColor("#555555")
RULE = colors.HexColor("#BBBBBB")
BAND = colors.HexColor("#EDEDED")
W = A4[0] - 36 * mm

BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK)
SMALL = ParagraphStyle("small", parent=BASE, fontSize=8, leading=10.5, textColor=GREY)
CELL = ParagraphStyle("cell", parent=BASE, fontSize=8.5, leading=11)
CELLR = ParagraphStyle("cellr", parent=CELL, alignment=2)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")
CELLBR = ParagraphStyle("cellbr", parent=CELLB, alignment=2)
H1 = ParagraphStyle("h1", parent=BASE, fontName="Helvetica-Bold", fontSize=20, leading=24, spaceAfter=2)
H2 = ParagraphStyle("h2", parent=BASE, fontName="Helvetica-Bold", fontSize=12.5, leading=16, spaceBefore=12, spaceAfter=5)
H3 = ParagraphStyle("h3", parent=BASE, fontName="Helvetica-Bold", fontSize=9.5, leading=13, spaceBefore=6, spaceAfter=2)
BUL = ParagraphStyle("bul", parent=BASE, leftIndent=11, bulletIndent=1, spaceAfter=1.5)


def _esc(t: Any) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _p(t: Any, st: ParagraphStyle = CELL) -> Paragraph:
    return Paragraph(_esc(t), st)


def _table(rows: list[list[Any]], widths: list[float], head: bool = True, bold_rows: tuple[int, ...] = (), right: tuple[int, ...] = (), band_rows: tuple[int, ...] = ()) -> Table:
    data = []
    for i, row in enumerate(rows):
        out = []
        for j, v in enumerate(row):
            st = (CELLBR if j in right else CELLB) if (i in bold_rows or (head and i == 0)) else (CELLR if j in right else CELL)
            if head and i == 0:
                st = ParagraphStyle("hd", parent=st, textColor=colors.white)
            out.append(v if isinstance(v, Paragraph) else _p(v, st))
        data.append(out)
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if head:
        style.append(("BACKGROUND", (0, 0), (-1, 0), INK))
    style += [("BACKGROUND", (0, i), (-1, i), BAND) for i in band_rows]
    t.setStyle(TableStyle(style))
    return t


def _bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(_esc(x), BUL, bulletText="•") for x in items if x]


def _first_sentence(text: str, limit: int = 220) -> str:
    t = " ".join((text or "").split())
    head, sep, rest = t.partition(": ")
    if sep and len(head) <= 90 and (head.upper() == head or head.upper().startswith(("RFI-", "RT"))):        # drop a repeated "RFI-06 / EARTHWORKS - OPEN RED:" label
        t = rest
    cut = t[:limit]
    i = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[: i + 1] if 60 < i < limit else cut + ("..." if len(t) > limit else "")).strip()


def _lines(text: str) -> list[str]:
    return [x.strip(" -•\t") for x in text.replace("\r", "").split("\n") if x.strip()]


def _doc(title: str, ctx: OutputContext, story: list, header_right: str) -> bytes:
    buf = io.BytesIO()
    foot = f"{ctx.project} | {ctx.revision} | {ctx.issue_date}"

    def deco(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(GREY)
        canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 11 * mm, f"{(ctx.company or '').upper()}  |  {header_right}".strip(" |"))
        canvas.setStrokeColor(RULE)
        canvas.line(18 * mm, A4[1] - 13 * mm, A4[0] - 18 * mm, A4[1] - 13 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(18 * mm, 10 * mm, foot)
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm, bottomMargin=17 * mm, title=title,
                      author=ctx.prepared_by or ctx.company or "").build(story, onFirstPage=deco, onLaterPages=deco)
    return buf.getvalue()


# ------------------------------------------------------------------------------------------------ price schedule
def schedule_pdf(est: dict[str, Any], ctx: OutputContext) -> bytes:
    sch = est["schedule"]
    meta = est["meta"]
    story: list[Any] = [Paragraph(_esc((sch["client"] or ctx.client or ctx.company or "").upper()), H3),
                        Paragraph(_esc((ctx.project or meta.get("project", "")).upper()), H1),
                        Paragraph(_esc((sch["name"] or "Price schedule").upper()), ParagraphStyle("sub", parent=BASE, fontName="Helvetica-Bold", fontSize=10, spaceAfter=8))]
    rows: list[list[Any]] = [["Ref", "Trade", "Total ($)"]]
    bold, band = [], []
    for g in sch["groups"]:
        band.append(len(rows)); bold.append(len(rows)); rows.append([g["name"], "", ""])
        for x in g["lines"]:
            if x["kind"] == "work":
                rows.append([x["ref"], x["trade"], money(x["amount"], "")])
        bold.append(len(rows)); rows.append(["", "SUB-TOTAL", money(g["subtotal"], "-")])
        for x in g["lines"]:
            if x["kind"] != "work":
                rows.append([x["ref"], x["trade"], money(x["amount"], "")])
        bold.append(len(rows)); band.append(len(rows))
        rows.append(["", ("TOTAL (EXCL GST)" if len(sch["groups"]) == 1 else f"{g['name']} SUB-TOTAL (EXCL GST)") + (f"  {g['code']}" if g["code"] else ""), money(g["total"], "-")])
    if len(sch["groups"]) > 1:
        codes = "+".join(g["code"] for g in sch["groups"] if g["code"])
        bold.append(len(rows)); band.append(len(rows))
        rows.append(["", "COMBINED TOTAL (EXCL GST)" + (f"  {codes}" if codes else ""), money(sch["total"])])
    story.append(_table(rows, [24 * mm, W - 24 * mm - 36 * mm, 36 * mm], bold_rows=tuple(bold), right=(2,), band_rows=tuple(band)))
    story.append(Spacer(1, 6))
    if not sch["reconciles"]:
        story.append(Paragraph(_esc("DRAFT: this schedule does not yet reconcile to the tender. " + " ".join(sch["problems"]) +
                                    (f" {len(sch['unmapped'])} item(s) are not yet mapped." if sch["unmapped"] else "")), ParagraphStyle("warn", parent=SMALL, textColor=colors.HexColor("#B00020"))))
    story.append(Paragraph(_esc(f"{ctx.revision} tender price schedule | all amounts exclude GST. Overhead, profit and any allowances without their own line are included in the Margin lines."), SMALL))
    return _doc("Price schedule", ctx, story, "TENDER PRICE SCHEDULE")


# ------------------------------------------------------------------------------------------------ tender report
def report_pdf(est: dict[str, Any], ctx: OutputContext, intake: dict[str, str] | None = None) -> bytes:
    intake = intake or {}
    meta, s, c, t, w = est["meta"], est["summary"], est["consolidated"], est["tender"], est["weather"]
    ct = est["controls"]
    release = ct.get("cover_release") or ct.get("release_status") or ""
    story: list[Any] = [Paragraph(_esc((ctx.project or meta.get("project", "")).upper()), H1),
                        Paragraph(_esc("Estimate Basis & Tender Report"), ParagraphStyle("t2", parent=BASE, fontName="Helvetica", fontSize=13, leading=17, spaceAfter=6))]
    if release:
        story.append(Paragraph(_esc(release.upper()), ParagraphStyle("rel", parent=BASE, fontName="Helvetica-Bold", fontSize=9, textColor=colors.HexColor("#B00020") if "HOLD" in release.upper() else GREY, spaceAfter=6)))
    ctrl = [["Control", "Issue"], ["Prepared for", ctx.client or "-"], ["Prepared by", f"{ctx.prepared_by} | {ctx.company}".strip(" |") or "-"],
            ["Estimate revision", ctx.revision or "-"], ["Issue date", ctx.issue_date or "-"], ["Location", ctx.location or meta.get("location", "") or "-"],
            ["GST basis", "All monetary values exclude GST unless stated otherwise"]]
    if meta.get("programme") or (w.get("meta") or {}).get("baseline_wd", "0") not in ("0", "", None):
        wm = w["meta"]
        ctrl.append(["Programme", meta.get("programme") or f"{wm['baseline_wd']} dry working days" + (f"; start assumption {wm['start']}" if wm.get("start") else "")])
    story.append(_table(ctrl, [42 * mm, W - 42 * mm]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(_esc("This report explains the controlling estimate, consolidated package, programme and tender qualifications. The estimating platform "
                                "calculates every figure from the quantities, rates and commercial settings recorded in the estimate; nothing here is typed in by hand."), SMALL))

    # 1 executive summary
    n = 0
    def sec(title: str) -> None:
        nonlocal n
        n += 1
        story.append(Paragraph(_esc(f"{n}. {title}"), H2))

    sec("Executive Summary")
    parts = [f"The current working all-in package is {money(c['all_in'])} excl. GST"]
    if c["overlays"]:
        parts.append(f"comprising own works plus {len(c['overlays'])} subcontract package{'s' if len(c['overlays']) != 1 else ''}")
    parts.append(f"with {pct(c['overhead_rate'], 1)} company overhead recovery and {pct(c['margin'], 1)} contractor profit calculated as a true margin. "
                 f"The resulting gross margin on the all-in sell price is {pct(c['gross_margin_on_sell'])}")
    story.append(Paragraph(_esc(", ".join(parts[:-1]) + (", " if len(parts) > 1 else "") + parts[-1] + "."), BASE))
    if s.get("management_reserve"):
        story.append(Spacer(1, 3))
        story.append(Paragraph(_esc(f"A management reserve of {money(s['management_reserve'])} is held pre-margin. It is a separate management judgement and does not close any open risk item."), BASE))
    if release:
        story.append(Spacer(1, 3))
        story.append(Paragraph(_esc(f"Release status: {release}. {money(c['all_in'])} is a working figure until any open items in the release controls are resolved, excluded or formally accepted."), BASE))
    rows = [["Commercial position", "Amount excl. GST", "Status"],
            ["WORKING ALL-IN PACKAGE", money(c["all_in"]), "Current answer to: what will this cost?"],
            ["Current known cost before OH/profit", money(c["gross_known_package"]), "Own works plus subcontract packages"],
            ["Own works before OH/profit", money(c["own_works"]), "Includes allowances and any management reserve"]]
    rows += [[o["name"], money(o["amount"]), f"Subcontract package ({o['kind'].lower()})"] for o in c["overlays"]]
    rows += [[f"Company OH, {pct(c['overhead_rate'], 1)}", money(c["overhead"]), "Applied to the consolidated known cost"],
             [f"Profit, {pct(c['margin'], 1)} true margin", money(c["profit"]), f"Overall gross margin on sell = {pct(c['gross_margin_on_sell'])}"]]
    story.append(Spacer(1, 6))
    story.append(KeepTogether(_table(rows, [62 * mm, 38 * mm, W - 100 * mm], bold_rows=(1,), right=(1,))))

    reg = est.get("register") or []
    of = lambda kind: [x for x in reg if x["kind"] == kind]
    blockers = [x for x in of("rfi") if x["status"] != "CLOSED" and x["rag"] == "RED"]
    if blockers:
        story.append(Paragraph("Current decision blockers", H3))
        story += _bullets([f"{x['ref']} - {x['title']}: {_first_sentence(x['detail'] or x['title'])}" for x in blockers])

    # 2 scope / project understanding (only what the estimator has recorded)
    scope_bits = [("Scope", intake.get("scope") or meta.get("scope", "")), ("Contract type", intake.get("contract_type", "")), ("Pricing basis", intake.get("pricing_basis", ""))]
    docs = of("document")
    if any(v for _, v in scope_bits) or docs or intake.get("drawings") or meta.get("drawings"):
        sec("Project Understanding and Basis Documents")
        for k, v in scope_bits:
            if v:
                story.append(Paragraph(_esc(k), H3))
                story += _bullets(_lines(v)) if "\n" in v else [Paragraph(_esc(v), BASE)]
        if docs:
            story.append(Paragraph("Basis documents", H3))
            rows = [["Source", "Revision / date", "Estimate use", "Status"]] + [[x["title"], x["ref"], x["detail"][:300], x["status"]] for x in docs]
            story.append(_table(rows, [48 * mm, 52 * mm, W - 48 * mm - 52 * mm - 22 * mm, 22 * mm]))
        elif intake.get("drawings") or meta.get("drawings"):
            story.append(Paragraph("Drawings and documents", H3))
            v = intake.get("drawings") or meta.get("drawings", "")
            story += _bullets(_lines(v)) if "\n" in v else [Paragraph(_esc(v), BASE)]
    if of("inclusion"):
        sec("Scope Included")
        story += _bullets([x["title"] + (f": {x['detail']}" if x["detail"] and x["detail"] != x["title"] else "") for x in of("inclusion")])
    if of("exclusion"):
        sec("Exclusions and By Others")
        story += _bullets([x["detail"] or x["title"] for x in of("exclusion")])

    # 3 pricing basis
    sec("Pricing Basis and Summary")
    story.append(Paragraph(_esc("The price is built from the linked Resource Build-Up, QS Takeoff, Tender Build-Up and Consolidated Package. Material and supplier costs "
                                "inside the build-up are already included and are not added again. Each subcontract package is added once."), BASE))
    def basis_label(text: str) -> str:
        u = (text or "").upper()
        for keys, label in ((("MEASURED", "COUNTED"), "measured"), (("PROVIDED",), "provided"), (("CALCULATED",), "calculated"), (("QUOTED", "QUOTE"), "quoted"),
                            (("ALLOWANCE", "PC", "PROVISIONAL"), "allowance / PC")):
            if any(u.startswith(k) for k in keys):
                return label
        return "other"

    basis_by_sec: dict[str, dict[str, int]] = {}
    for q in est["qs"]:
        label = basis_label(q.get("basis", ""))
        basis_by_sec.setdefault(q["section"], {})
        basis_by_sec[q["section"]][label] = basis_by_sec[q["section"]].get(label, 0) + 1
    rows = [["Section", "Amount excl. GST", "Basis of quantities"]]
    for sc in est["sections"]:
        mix = ", ".join(f"{v} {k}" for k, v in sorted(basis_by_sec.get(sc["section"], {}).items()))
        rows.append([sc["section"], money(sc["amount"]), mix])
    rows += [["Base direct estimate", money(t["base_direct"]), "Sum of the QS items above"]]
    additions = [x for x in est["commercial"] if x["amount"] and x["stage"] == "pre" and x["ref"] != "CA17"]
    for x in additions:
        rows.append([f"{x['ref']} {x['name']}", money(x["amount"]), "Pre-margin allowance"])
    rows += [["Own works before overhead and profit", money(t["subtotal"]), ""], [f"Company overhead ({pct(c['overhead_rate'], 1)})", money(t["overhead"]), "Own works only (standalone view)"],
             [f"Profit ({pct(c['margin'], 1)} true margin)", money(t["profit"]), "True margin on cost plus overhead"], ["Own works tender", money(t["total_excl_gst"]), "Standalone, before subcontract packages"]]
    bold = tuple(i for i, r in enumerate(rows) if r[0] in ("Base direct estimate", "Own works before overhead and profit", "Own works tender"))
    story.append(Spacer(1, 4))
    story.append(_table(rows, [70 * mm, 36 * mm, W - 106 * mm], bold_rows=bold, right=(1,)))
    story.append(Spacer(1, 3))
    story.append(Paragraph(_esc("True margin means profit is a share of the selling price: sell = (cost + overhead) / (1 - margin). A markup on cost would give a different answer."), SMALL))

    # 4 price schedule summary
    sch = est["schedule"]
    sec("Price Schedule Summary")
    story.append(Paragraph(_esc(f"{sch['name'] or 'Price schedule'}: " + ("reconciles exactly to the working all-in tender." if sch["reconciles"] else "NOT YET RECONCILED - items are unmapped or the totals differ.")), BASE))
    rows = [["Group", "Schedule lines", "Held in margin", "Group total"]]
    for g in sch["groups"]:
        rows.append([g["name"], money(sum(x["amount"] for x in g["lines"] if x["kind"] != "margin")), money(g["hidden"], "-"), money(g["total"])])
    rows.append(["Total", "", "", money(sch["total"])])
    story.append(Spacer(1, 4))
    story.append(_table(rows, [60 * mm, 38 * mm, 36 * mm, W - 134 * mm], bold_rows=(len(rows) - 1,), right=(1, 2, 3)))

    # 5 PC sums / allowances
    pcs = [q for q in est["qs"] if (q.get("basis") or "").upper().startswith("ALLOWANCE") or "PC" in (q.get("status") or "").upper().split()]
    if pcs:
        sec("PC Sums, Provisional Quantities and Allowances")
        rows = [["Item", "Amount", "Classification", "Note"]]
        for q in pcs:
            rows.append([f"{q['code']} {q['description']}", money(q["amount"]), (q.get("basis") or "").split(" - ")[0][:40], (q.get("status") or "")[:70]])
        story.append(_table(rows, [64 * mm, 28 * mm, 34 * mm, W - 126 * mm], right=(1,)))

    # 6 programme and weather
    wm = w["meta"]
    if wm.get("baseline_wd") not in ("0", "", None) or w["allowance"]:
        sec("Programme and Weather Basis")
        rows = [["Programme control", "Basis"], ["Dry site working duration", f"{wm.get('baseline_wd', '')} working days"],
                ["Working calendar", f"{wm.get('wd_per_week', '5')} days per week"], ["Programme start assumption", wm.get("start", "") or "-"],
                ["Modelled normal-weather delay", f"{w['critical_path_delay_wd']:.3f} critical-path working days"],
                ["Weather-adjusted planning duration", f"approx. {w['planning_wd']:.1f} working days"]]
        story.append(_table(rows, [62 * mm, W - 62 * mm]))
        story.append(Spacer(1, 4))
        story.append(Paragraph(_esc(f"Normal weather is modelled with the NZ Weather Risk Estimating Tool Rev2 using NIWA 1991-2020 climate normals for {wm.get('station', '')}. "
                                    "It applies only to identified weather-exposed labour and plant and to critical-path tasks; it is not a flat percentage of project value. "
                                    "Weather allowance is an estimating cost view and does not establish any entitlement to an extension of time."), BASE))
        rows = [["Weather component", "Result"], ["Weather-exposed labour + plant", money(w["exposed_pool"], "-")], ["Direct productivity allowance", money(w["direct_productivity"], "-")],
                ["Critical-path time-related preliminaries", money(w["critical_path_prelims"], "-")], ["Additional billed hire / facilities", money(w["billed_hire"], "-")],
                ["Recovery / remediation", money(w["recovery"], "-")], ["Total normal-weather allowance included", money(w["allowance"], "-")]]
        story.append(Spacer(1, 4))
        story.append(_table(rows, [90 * mm, W - 90 * mm], bold_rows=(len(rows) - 1,), right=(1,)))
        if w.get("tool"):
            tl = w["tool"]
            story.append(Spacer(1, 4))
            rows = [["Activity", "Dates", "Critical", "Allowance", "Lost WD"]]
            for a in tl["activities"]:
                rows.append([a["task"], f"{a['start']} to {a['finish']}", "Yes" if a["critical"] else "No", money(a["direct_allowance"], "-"), f"{a['lost_wd']:.2f}"])
            story.append(_table(rows, [58 * mm, 50 * mm, 18 * mm, 30 * mm, W - 156 * mm], right=(3, 4)))
        elif wm.get("rerun_status"):
            story.append(Spacer(1, 3))
            story.append(Paragraph(_esc(wm["rerun_status"]), SMALL))

    # 7 assumptions, constraints, risks and open information (from the register, else the intake text)
    if of("assumption"):
        sec("Estimate Assumptions")
        story += _bullets([x["detail"] or x["title"] for x in of("assumption")])
    elif intake.get("assumptions", "").strip():
        sec("Estimate Assumptions")
        story += _bullets(_lines(intake["assumptions"]))
    for title, key in (("Programme Constraints", "programme"), ("Site Constraints", "site_constraints")):
        if intake.get(key, "").strip():
            sec(title)
            story += _bullets(_lines(intake[key]))
    if not of("exclusion") and not of("inclusion") and intake.get("inclusions_exclusions", "").strip():
        sec("Inclusions and Exclusions")
        story += _bullets(_lines(intake["inclusions_exclusions"]))
    if of("risk"):
        sec("Risk Basis")
        rows = [["Material uncertainty", "Tender baseline / treatment", "Outside baseline / closeout", "Rating"]]
        for x in of("risk"):
            rows.append([f"{x['ref']} {x['title']}", x["detail"][:420], x["action"][:300], x["rag"] or x["status"]])
        story.append(_table(rows, [50 * mm, 62 * mm, W - 50 * mm - 62 * mm - 18 * mm, 18 * mm]))
    if of("rfi"):
        sec("Pricing Qualifications and RFIs")
        rows = [["Ref", "Item", "Status", "Detail"]]
        for x in sorted(of("rfi"), key=lambda r: (r["status"] == "CLOSED", r["ref"])):
            rows.append([x["ref"], x["title"], (x["status"] + (f" / {x['rag']}" if x["rag"] else "")), _first_sentence(x["detail"], 260)])
        story.append(_table(rows, [20 * mm, 46 * mm, 24 * mm, W - 90 * mm]))
    elif intake.get("missing_info", "").strip():
        sec("Information Still Required (RFIs)")
        story += _bullets(_lines(intake["missing_info"]))

    # release controls
    if ct.get("red_risks") not in (None, "") or ct.get("rate_green") not in (None, ""):
        sec("Release Controls and Verification Status")
        rows = [["Control", "Result"]]
        for k, label in (("red_risks", "Open RED risks"), ("red_exposures", "Open RED exposures"), ("duplicate_gate", "Duplicate-cost gate"), ("programme_gate", "Programme / cost gate"),
                         ("tender_equals_risk_truth", "Tender equals Risk Truth")):
            if ct.get(k) not in (None, ""):
                rows.append([label, ct[k]])
        if ct.get("rate_green") not in (None, ""):
            rows.append(["Rates verified GREEN / AMBER / RED", f"{ct.get('rate_green', '0')} / {ct.get('rate_amber', '0')} / {ct.get('rate_red', '0')}"])
        story.append(_table(rows, [80 * mm, W - 80 * mm]))
        story.append(Spacer(1, 3))
        story.append(Paragraph(_esc("AMBER means a benchmark, allowance or quotation with a check still open and a firm-up action assigned."), SMALL))

    # appendix: QS schedule
    story.append(PageBreak())
    story.append(Paragraph("Appendix A: Quantity and Pricing Schedule", H2))
    rows = [["Code", "Description", "Quantity", "Amount", "Basis / status"]]
    for q in est["qs"]:
        qty = f"{q['quantity']:,.2f}".rstrip("0").rstrip(".") + f" {q['unit']}"
        rows.append([q["code"], q["description"], qty, money(q["amount"], "-"), " | ".join(x for x in ((q.get("basis") or "").split(" - ")[0][:28], (q.get("rag") or "")) if x)])
    story.append(_table(rows, [16 * mm, 74 * mm, 24 * mm, 28 * mm, W - 142 * mm], right=(2, 3)))
    return _doc("Estimate basis and tender report", ctx, story, "ESTIMATE BASIS & TENDER REPORT")
