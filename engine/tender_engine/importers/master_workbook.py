"""Import INPUTS (constants) and display metadata from a Master Estimate Workbook (.xlsx).

Inputs are read from constant cells only, so the engine genuinely recomputes every figure.
Cached workbook values are read solely for display-only status text (release gates, etc.)
and are always labelled as 'from workbook' in the API output.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, BinaryIO

import openpyxl

from dataclasses import replace
from ..ids import display_ids
from ..models import LibraryRate, BuildUpRow, QSItem, WeatherToolRun, Overlay
from ..money import D


def _s(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _n(v: Any):
    return None if v in (None, "") else D(v)


@dataclass
class MasterWorkbookImport:
    meta: dict[str, str]
    library: dict[str, LibraryRate]
    qs: list[QSItem]
    qs_extra: dict[str, dict[str, str]]
    rows: list[BuildUpRow]
    row_extra: list[dict[str, str]]
    excel_rows: list[int]
    tool: WeatherToolRun
    recovery: Decimal
    commercial: list[dict]
    risk_feed: dict[str, Any]
    overlays: list[Overlay]
    overlap: Any
    weather_meta: dict[str, str]
    weather_links: dict[str, Any]
    controls: dict[str, str]
    reference: dict[str, float] | None = None   # totals the source workbook displayed (None once edited)
    weather_setup: dict | None = None            # live weather-tool setup (tender_engine.weather_setup); None = recorded tool outputs
    schedule: dict | None = None                 # client price schedule format + mapping (tender_engine.schedule); None = automatic
    register: list = field(default_factory=list)  # tender register items (tender_engine.register)
    quotes: list = field(default_factory=list)    # supplier / subcontractor quote register (tender_engine.quotes)
    risk_truth: list = field(default_factory=list)  # Risk Truth exposures (tender_engine.risk_truth)
    management_reserve: dict | None = None         # Management Reserve adjudication (tender_engine.management_reserve); None = CA16 stays a plain line
    programme: dict | None = None                # programme tasks, predecessors and calendar (tender_engine.programme); None = not set up
    notes: list = field(default_factory=list)    # plain-language notes from the import (a sheet was missing, rows were left unread ...)
    cached: Any = field(repr=False, default=None)


def _cover_meta(v) -> dict[str, str]:
    ws = v["Cover & Instructions"]
    wanted = {"Project": "project", "Location": "location", "Current drawings": "drawings",
              "Issue date": "issue_date", "Scope": "scope", "GST": "gst", "Programme": "programme",
              "Weather": "weather", "Price status": "price_status", "Commercial": "commercial"}
    meta: dict[str, str] = {}
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        cells = [(c.column, c.value) for c in row if c.value not in (None, "")]
        for i, (_, val) in enumerate(cells):
            if isinstance(val, str) and val in wanted and wanted[val] not in meta and i + 1 < len(cells):
                nxt = cells[i + 1][1]
                if isinstance(nxt, str) and nxt in wanted:          # the value cell is empty and the next filled cell is another label
                    continue
                meta[wanted[val]] = _s(nxt)
    snap = _s(ws["A2"].value)
    if snap:
        meta["snapshot"] = snap
    return meta


def _title(text: str, limit: int = 140) -> str:
    t = " ".join(text.split())
    m = re.search(r"[:.](?:\s|$)", t[:limit]) or re.search(r"\s-\s", t[:limit])
    cut = t[:m.start()] if m else t[:limit]
    return (cut if len(cut) >= 12 else t[:limit]).strip(" -:")


def _register_from_cover(ws) -> list[dict]:
    """Document register, assumptions / exclusions, RFIs and key risks from the Cover & Instructions sheet (tolerant: nothing found -> [])."""
    items: list[dict] = []
    counts: dict[str, int] = {}

    def add(kind: str, **kw: str) -> None:
        counts[kind] = counts.get(kind, 0) + 1
        item = {"id": f"R-{kind[:3]}{counts[kind]:03d}", "kind": kind, **{f: "" for f in ("ref", "title", "detail", "action", "status", "rag", "owner", "likelihood", "impact", "rating")}}
        item.update({k: v[:3000] for k, v in kw.items()})
        items.append(item)

    def rfi(ref: str, text: str, title: str | None = None) -> None:
        head = text.upper()[:200]
        closed = bool(re.search(r"\bCLOSED\b", head))
        red = bool(re.search(r"\bRED\b", head))
        if title is None:
            t = re.sub(r"^RFI-\d+[A-Z]?(\s*/\s*RFI-\d+[A-Z]?)*\s*[:/-]?\s*", "", text)
            t = t.split(":", 1)[0] if ":" in t[:130] else _title(t)
            t = re.sub(r"\b(CLOSED|OPEN RED|OPEN)\b", "", t)
            t = re.sub(r"\s+", " ", re.sub(r"(\s[-/]\s*)+$", "", t)).strip(" -/:")
            title = (t.title() if t.isupper() else t)[:200] or ref
        add("rfi", ref=ref, title=title, detail=text, status="CLOSED" if closed else "OPEN", rag="" if closed else ("RED" if red else "AMBER"))

    section = None
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        a = _s(row[0].value)
        b = _s(row[1].value) if len(row) > 1 else ""
        c = _s(row[2].value) if len(row) > 2 else ""
        up = a.upper()
        if up.startswith("DRAWING / DOCUMENT REGISTER"):
            section = "doc"; continue
        if up.startswith("ASSUMPTIONS / QUALIFICATIONS"):
            section = "assume"; continue
        if up.startswith("PRICING QUALIFICATIONS"):
            section = "rfi"; continue
        if up.startswith("KEY RISKS"):
            section = "risk"; continue
        if up.startswith(("TENDER RELEASE QA", "ARCHIVE")):
            section = None; continue
        if not section or not a:
            continue
        if section == "doc" and up != "DOCUMENT / DRAWING" and b:
            add("document", title=a, ref=b, detail=c, status="CURRENT")
        elif section == "assume" and b:
            if re.fullmatch(r"A\d+", a):
                add("assumption", ref=a, title=_title(b), detail=b)
            elif re.fullmatch(r"EX-\d+", a):
                add("exclusion", ref=a, title=_title(b), detail=b)
        elif section == "rfi" and b:
            if re.fullmatch(r"RFI-\d+[A-Z]?", a):
                rfi(a, b)
            elif up.startswith("NEW STAMPED RC"):
                for part in b.split(" | "):
                    m = re.match(r"^(RFI-\d+[A-Z]?)\s+(.*?)\s+-\s+((?:CLOSED|OPEN)[^:]*):\s*(.*)$", part.strip(), re.S)
                    if m:
                        rfi(m.group(1), f"{m.group(1)} {m.group(2)} - {m.group(3)}: {m.group(4)}", title=m.group(2).title())
        elif section == "risk" and re.fullmatch(r"RT\d+", a):
            status = _s(row[7].value) if len(row) > 7 else ""
            add("risk", ref=a, title=b, likelihood=c, impact=_s(row[3].value), rating=_s(row[4].value), detail=_s(row[5].value), owner=_s(row[6].value),
                status=status, rag=status.upper() if status.upper() in ("RED", "AMBER", "GREEN") else "")
    return items


def _risks_and_exposures_from_risk_truth(ws) -> tuple[list[dict], list[dict]]:
    """Risk Truth tab: risks (rows from 25: ID, description, class, likelihood, impact, rating, response, owner, RFI/action, baseline, status)
    and exposures (header row 'Exposure ID' onwards). Tolerant of the one-column shift that some workbook rows carry from column G."""
    from .. import risk_truth as rt
    risks, exposures = [], []
    top = None
    for r in range(1, ws.max_row + 1):
        if _s(ws.cell(r, 1).value) == "Risk ID":
            top = r
        if _s(ws.cell(r, 1).value) == "Exposure ID":
            hdr = r
            break
    else:
        return [], []
    for r in range(top + 1 if top else hdr, hdr):
        a = _s(ws.cell(r, 1).value)
        if not re.fullmatch(r"[A-Z]{2}\d+", a):
            continue
        g = lambda c: _s(ws.cell(r, c).value)
        status = g(11)
        detail = g(7) + (f"\n\nTender baseline: {g(10)}" if g(10) else "") + (f"\n\nClass: {g(3)}" if g(3) else "")
        risks.append({"id": f"R-{a}", "kind": "risk", "ref": a, "title": g(2)[:3000], "detail": detail[:3000], "action": g(9)[:3000], "status": status,
                      "rag": status.upper() if status.upper() in ("RED", "AMBER", "GREEN") else "", "owner": g(8)[:3000], "likelihood": g(4), "impact": g(5), "rating": g(6)})
    L = lambda n: n
    for r in range(hdr + 1, ws.max_row + 1):
        ref = _s(ws.cell(r, 1).value)
        if not ref or not re.fullmatch(r"[A-Z]{2}\d+-\d+", ref):
            continue
        c = lambda col, off=0: _s(ws.cell(r, col + off).value)
        off = 1 if (c(10) in rt.MODES and c(9) not in rt.MODES) else 0
        n = lambda v: v if re.fullmatch(r"-?\d+(\.\d+)?", v or "") else ""
        def rag(t):
            u = t.upper()
            return "RED" if re.search(r"\bRED\b", u) else "AMBER" if re.search(r"\bAMBER\b", u) else "GREEN" if re.search(r"\bGREEN\b", u) else ""
        yn = lambda v: v if v in rt.YESNO else ""
        treat = c(6) + (f" | {c(7)}" if off and c(7) else "")
        item = {"id": "X-" + re.sub(r"[^A-Za-z0-9]", "", ref)[:12], **{f: "" for f in rt.FIELDS}}
        item.update({
            "ref": ref, "risk_id": c(2), "consequence": c(3), "driver": c(4), "cost_ref": c(5), "treatment": treat,
            "baseline_amount": n(c(7, off)), "residual": c(8, off), "mode": c(9, off) if c(9, off) in rt.MODES else "", "qty": n(c(10, off)),
            "unit": c(11, off), "unit_rate": n(c(12, off)), "probability": n(c(13, off)), "provision": n(c(15, off)),
            "owner": c(16, off) if c(16, off) in rt.OWNERS else "", "distinct": yn(c(17, off)), "target": c(18, off), "include": yn(c(19, off)) or "No",
            "overlap_group": c(21, off), "embedded": c(22, off), "evidence": rag(c(23, off)), "evidence_note": c(23, off),
            "integration_complete": yn(c(25, off)), "basis": c(27, off), "action": c(28, off), "source": c(29, off)})
        for f in rt.FIELDS:
            item[f] = item[f][: rt.LIMITS[f]]
        exposures.append(item)
    return risks, exposures


def _quotes_from_sheet(ws) -> list[dict]:
    """Supplier Quote Register: header row has 'Quote ID'; rows Q-01.. follow."""
    head = None
    out: list[dict] = []
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        a = _s(row[0].value)
        if a == "Quote ID":
            head = True
            continue
        if head and re.fullmatch(r"Q-\d+", a):
            g = lambda i: _s(row[i].value) if len(row) > i else ""
            try:
                amount = str(D(row[5].value).quantize(Decimal("0.01"))) if row[5].value not in (None, "") else ""
            except Exception:
                amount = ""
            out.append({"id": f"S-q{len(out) + 1:03d}", "ref": a, "package": g(1), "estimate_ref": g(2), "qty": g(3), "unit": g(4), "amount": amount, "scope": g(6),
                        "documents": g(7), "supplier": g(8), "status": g(9), "action": g(10), "notes": g(11), "treatment": "", "verification": "",
                        "source": "", "quote_date": "", "valid_until": ""})
        elif head and a and not re.fullmatch(r"Q-\d+", a):
            break
    return out


def _programme_from_sheet(ws, qs_codes: set[str], start: str, days_per_week: int) -> dict | None:
    """Programme Export: one row per QS code plus control tasks (PRG-..., DRN-...); override days, predecessor codes, basis and notes."""
    if ws is None:
        return None
    tasks: list[dict] = []
    for row in ws.iter_rows(min_row=7, max_row=ws.max_row):
        code = row[3].value
        if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,19}", code.strip()):
            continue
        code = code.strip()
        name = _s(row[4].value)
        if not name:
            continue
        over = row[11].value
        try:
            override = str(int(Decimal(str(over)))) if over not in (None, "") else None
        except Exception:
            override = None
        preds = [c for c in re.split(r"[,;\s]+", _s(row[15].value)) if c]
        section = _s(row[2].value)
        tasks.append({"id": f"P-{len(tasks) + 1:05d}", "code": code, "name": name[:200], "qs_code": code if code in qs_codes else "", "override_days": override,
                      "predecessors": preds, "hammock": section.upper().startswith("PRELIMINARIES"), "basis": _s(row[14].value)[:500], "note": _s(row[23].value)[:500]})
    if not tasks:
        return None
    return {"start": start, "days_per_week": days_per_week, "hours_per_day": 8, "tasks": tasks}


def _reserve_from_commercial(commercial: list[dict], ws=None) -> dict | None:
    """A workbook whose CA16 Management Reserve is an included fixed amount becomes an adjudication block whose selected reserve is that amount
    (total unchanged). The workbook's own "MANAGEMENT RESERVE - ADJUDICATION BASIS" block on Commercial Inputs supplies the unresolved items (its
    four red-item columns: consequence text), and the rationale. Probabilities are NOT invented: the workbook records none (UNKNOWN)."""
    from .. import management_reserve as mr
    ca = next((c for c in commercial if c["ref"] == "CA16"), None)
    if ca is None or ca["include"] != "Yes" or ca["method"] != "Fixed Amount" or D(ca["pc_sum"]) <= 0:
        return None
    basis = (ca.get("note") or "")
    items: list[dict] = []
    if ws is not None:
        top = next((r for r in range(1, ws.max_row + 1) if _s(ws.cell(r, 1).value).upper().startswith("MANAGEMENT RESERVE - ADJUDICATION BASIS")), None)
        if top:
            hdr, row = top + 1, top + 2
            rows = {_s(ws.cell(r, 1).value): r for r in range(top + 2, top + 9)}
            rate = rows.get("Selected reserve rate")
            note = rows.get("Probability note")
            extra = " ".join(x for x in (_s(ws.cell(rate, 4).value) if rate else "", _s(ws.cell(note, 4).value) if note else "") if x)
            if extra:
                basis = f"{basis}\n\nWorkbook adjudication basis: {extra}".strip()
            for col in range(5, 9):
                head, text = _s(ws.cell(hdr, col).value), _s(ws.cell(row, col).value)
                if not head or not text:
                    continue
                m_ = re.search(r"\$\s*([\d.,]+)\s*k\b", text, re.I)
                zero = bool(re.match(r"^[~+]?\$0\b", text))
                impact = ""
                if m_:
                    impact = str(int(round(float(m_.group(1).replace(",", "")) * 1000))) if not zero else "0"
                elif zero:
                    impact = "0"
                unq = bool(re.search(r"unquantified", text, re.I)) and (zero or not m_)
                status = "Unquantified" if unq else "Proxy" if re.search(r"proxy|floor", text, re.I) else "Quantified"
                it = mr.build_item(f"M-wb{col - 4:04d}", {
                    "title": re.sub(r"\s+RED$", "", head).strip() + " (red item)", "description": text, "basis": "Sell", "impact": "" if status == "Unquantified" else impact,
                    "impact_status": status, "prob_status": "UNKNOWN",
                    "prob_basis": "Workbook records no evidenced probability (an earlier 50/50 discussion was a heuristic only). Enter a supportable range to weight this item."}, items)
                items.append(it)
    blk = mr.new_block(str(ca["pc_sum"]), basis[:3000])
    blk["items"] = items
    return blk


def _register_with_risk_truth(v) -> list[dict]:
    """Register from the Cover sheet; where the workbook has a Risk Truth tab its risk list (the controlling one) replaces the Cover's older key risks."""
    reg = _register_from_cover(v["Cover & Instructions"]) if "Cover & Instructions" in v.sheetnames else []
    if "Risk Truth" in v.sheetnames:
        risks, _ = _risks_and_exposures_from_risk_truth(v["Risk Truth"])
        if risks:
            reg = [x for x in reg if x["kind"] != "risk"] + risks
    return reg


class _Values:
    """The workbook seen through its values: a cell that holds a formula gives the value Excel last calculated for it (None if it was never calculated).
    The platform recalculates everything downstream itself; an input cell that is a formula is only ever a frozen number to it. Counts what was substituted."""
    def __init__(self, formulas, values):
        self._f, self._v = formulas, values
        self.subs: dict[str, list[str]] = {}
        self.uncalculated: dict[str, list[str]] = {}

    def __getitem__(self, name):
        return _VSheet(self, name)


class _VSheet:
    def __init__(self, book, name):
        self._b, self._name = book, name
        self._f, self._v = book._f[name], book._v[name]
        self.max_row = self._f.max_row

    def cell(self, r, c):
        return self._at(self._f.cell(r, c), self._v.cell(r, c))

    def __getitem__(self, addr):
        return self._at(self._f[addr], self._v[addr])

    def _at(self, fc, vc):
        class _C:
            pass
        out = _C()
        val = fc.value
        if isinstance(val, str) and val.startswith("="):
            val = vc.value
            (self._b.subs if val is not None else self._b.uncalculated).setdefault(self._name, []).append(fc.coordinate)
        out.value = val
        return out


class _Either:
    """Cell access that prefers the value Excel calculated and falls back to what was typed into the cell (a workbook never opened in Excel has no calculated
    values; a formula that was never calculated is never returned as a value)."""
    def __init__(self, formulas, values):
        self._f, self._v = formulas, values

    def __getitem__(self, addr):
        class _C:
            pass
        c = _C()
        val = self._v[addr].value
        if val is None:
            val = self._f[addr].value
            if isinstance(val, str) and val.startswith("="):
                val = None
        c.value = val
        return c


def _numstr(x, default: str) -> str:
    """A cell that should hold a number, as text for the weather settings; anything else (a formula that was never calculated, 'TBC') gives the default."""
    n = _num_or0(x) if not (isinstance(x, str) and x.strip() == "") else 0
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return str(x)
    try:
        float(str(x).replace(",", "").strip())
        return str(x).strip()
    except ValueError:
        return default


def _check_numbers(sheet: str, row: int, code: Any, cells: list[tuple[str, Any]]) -> None:
    """A number cell that holds words (TBC, n/a, a stray note) stops the import with the sheet, row and item named, instead of a technical error."""
    for what, val in cells:
        if val in (None, "") or isinstance(val, (int, float)) and not isinstance(val, bool):
            continue
        try:
            float(str(val).replace(",", "").replace("$", "").strip())
        except ValueError:
            raise ValueError(f"{sheet} row {row} ({code}): the {what} is \"{str(val)[:40]}\", which is not a number. Change it to a number in the workbook and upload it again.") from None


_CODE_LIKE = re.compile(r"^[A-Za-z0-9]+(?:[-_./][A-Za-z0-9]+){0,4}$")    # one word, no spaces: PG01, JW-PG01, ALLIED-SUB-SURVEY-ASB


def _num_or0(x):
    """A cell that should hold a number: text such as 'TBC' or a stray error counts as 0 rather than stopping the import."""
    if isinstance(x, bool) or x is None or x == "":
        return 0
    if isinstance(x, (int, float)):
        return x
    try:
        return float(str(x).replace(",", "").replace("$", "").strip())
    except ValueError:
        return 0


# The overlay names the platform already uses (so schedules, mappings and saved work keep working) for the Hobsonville wording of each package.
_LEGACY_OVERLAY_NAMES = (("coast concrete foundation", "Coast Concrete foundation / floor"), ("public stormwater", "Allied public stormwater / detention base"),
                         ("public setout", "Allied public setout / as-built / signoff"), ("private drainage", "Allied private drainage"))


def _overlays_from_consolidated(ws) -> tuple[list[Overlay], Any]:
    """Subcontract packages from the Consolidated Package sheet by reading what the rows say, not fixed cell addresses: a package is a row with an amount
    that is NOT in the siteworks direct cost (column D = No) and is not a calculated total. The confirmed overlap is the row whose label says overlap."""
    overlays: list[Overlay] = []
    overlap = D(0)
    for r in range(5, min(ws.max_row, 60) + 1):
        label, amount, cls, inc = _s(ws.cell(r, 1).value), ws.cell(r, 2).value, _s(ws.cell(r, 3).value), _s(ws.cell(r, 4).value)
        low = label.lower()
        if low.startswith(("gross", "current known package", "working all-in")):
            if low.startswith("gross"):
                break
            continue
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            continue
        if "overlap" in low:
            overlap = D(amount)
            continue
        if inc.strip().lower() == "no" and "CALCULATED" not in cls.upper():
            name = next((n for key, n in _LEGACY_OVERLAY_NAMES if key in low), label[:80])
            overlays.append(Overlay(name, D(amount), cls or "QUOTED"))
    return overlays, overlap


def load_master_workbook(source: str | Path | BinaryIO) -> MasterWorkbookImport:
    f = openpyxl.load_workbook(source)
    if hasattr(source, "seek"):
        source.seek(0)
    v = openpyxl.load_workbook(source, data_only=True)

    # Only these four sheets are essential. Everything else is optional: a workbook from an older or different job that lacks a sheet still loads,
    # and the notes below say what was left out and how to fill it in on the platform.
    required = {"Resource Rate Library": "the rates", "QS Takeoff": "the quantities", "Resource Build-Up": "the cost build-up rows", "Commercial Inputs": "overhead, margin and allowances"}
    missing = [f"{n} ({what})" for n, what in required.items() if n not in f.sheetnames]
    if missing:
        raise ValueError(f"This doesn't look like a Master Estimate Workbook. These sheets are needed and are missing: {', '.join(missing)}. "
                         f"The sheets found were: {', '.join(f.sheetnames[:12])}{'…' if len(f.sheetnames) > 12 else ''}.")
    notes: list[str] = []
    have = set(f.sheetnames)

    lib: dict[str, LibraryRate] = {}
    fm = _Values(f, v)
    ws = fm["Resource Rate Library"]
    for r in range(5, ws.max_row + 1):
        code = ws.cell(r, 1).value
        if code and (r <= 85 or (_CODE_LIKE.match(_s(code)) and len(_s(code)) <= 40 and isinstance(ws.cell(r, 9).value, (int, float)))):   # beyond the template's own rows: a code with a numeric rate
            _check_numbers("Resource Rate Library", r, code, [("rate", ws.cell(r, 9).value)])
            lib[str(code)] = LibraryRate(
                code=str(code), category=_s(ws.cell(r, 2).value), description=_s(ws.cell(r, 3).value),
                unit=_s(ws.cell(r, 5).value), operator_included=_s(ws.cell(r, 7).value),
                fuel_included=_s(ws.cell(r, 8).value), base_rate=D(ws.cell(r, 9).value),
                source=_s(ws.cell(r, 13).value))

    qs: list[QSItem] = []
    qs_extra: dict[str, dict[str, str]] = {}
    ws, wv = fm["QS Takeoff"], v["QS Takeoff"]
    for r in range(3, ws.max_row + 1):
        code = ws.cell(r, 2).value
        if code and (r <= 40 or (_CODE_LIKE.match(_s(code)) and len(_s(code)) <= 24 and isinstance(ws.cell(r, 5).value, (int, float)))):   # items below the template's rows are read too (a code with a numeric quantity)
            _check_numbers("QS Takeoff", r, code, [("quantity", ws.cell(r, 5).value)])
            qs.append(QSItem(code=str(code), section=_s(ws.cell(r, 1).value), description=_s(ws.cell(r, 3).value),
                             unit=_s(ws.cell(r, 4).value), quantity=D(ws.cell(r, 5).value)))
            qs_extra[str(code)] = {
                "basis": _s(wv.cell(r, 8).value), "source": _s(wv.cell(r, 9).value),
                "status": _s(wv.cell(r, 10).value), "notes": _s(wv.cell(r, 11).value),
                "flag": _s(wv.cell(r, 16).value), "owner": _s(wv.cell(r, 18).value),
                "verification": _s(wv.cell(r, 19).value), "quote_ref": _s(wv.cell(r, 20).value),
            }

    rows: list[BuildUpRow] = []
    extra: list[dict[str, str]] = []
    excel_rows: list[int] = []
    ws, wv = fm["Resource Build-Up"], v["Resource Build-Up"]
    for r in range(7, ws.max_row + 1):
        code = ws.cell(r, 2).value
        if not code or (r > 306 and not (_CODE_LIKE.match(_s(code)) and _s(ws[f"N{r}"].value))):
            continue
        c = lambda col: ws[f"{col}{r}"].value
        _check_numbers("Resource Build-Up", r, code, [(h, c(col)) for col, h in (("I", "productivity"), ("L", "duration override"), ("R", "count"), ("S", "quantity"), ("U", "utilisation"), ("V", "waste"), ("X", "job rate"))])
        rows.append(BuildUpRow(
            qs_code=str(code), mode=_s(c("N")), resource_type=_s(c("O")), resource_code=_s(c("P")),
            productivity_rate=_n(c("I")), duration_override_hrs=_n(c("L")), count=_n(c("R")),
            manual_qty=_n(c("S")), utilisation=_n(c("U")), waste=_n(c("V")), job_rate_override=_n(c("X")),
            task=_s(c("H")), verified=_s(c("AH")), weather_exposed=_s(c("AK")), weather_task_type=_s(c("AL"))))
        extra.append({"productivity_unit": _s(c("J")), "quote_ref": _s(c("AB")), "source_date": _s(wv[f"AC{r}"].value),
                      "confidence": _s(wv[f"AF{r}"].value), "assumption": _s(wv[f"AG{r}"].value),
                      "note": _s(c("AJ")), "workbook_qa": _s(wv[f"AI{r}"].value)})
        excel_rows.append(r)

    rows = [replace(r, uid=u) for r, u in zip(rows, display_ids(rows))]      # permanent row identities (initially the display id)
    uid_at = dict(zip(excel_rows, (r.uid for r in rows)))
    no_links = {"daily_row": 0, "hours_per_day": 8, "weekly_rows": [], "daily_uid": "", "weekly_uids": []}
    if "Weather Risk" not in have:
        notes.append("No Weather Risk sheet in the workbook: the weather allowance is zero. Set the weather tool up on the Weather Risk page.")
        tool = WeatherToolRun(exposed_pool=D(0), rain_wet_ground_cost=D(0), critical_path_delay_wd=D(0), additional_billed_weeks=D(0), wind_sensitivity_cost=D(0), include_wind=False)
        weather_meta = {"station": "", "start": "", "baseline_wd": "0", "wd_per_week": "5", "tool_version": "", "tool_station": "", "confidence": "NOT RUN",
                        "rerun_status": "No weather sheet in the imported workbook", "delay_wd": "0", "dry_programme_wd": "0"}
        weather_links, recovery = dict(no_links), D(0)
    else:
        wr, wv_ = f["Weather Risk"], _Either(f["Weather Risk"], v["Weather Risk"])
        tool = WeatherToolRun(
            exposed_pool=D(_num_or0(wv_["B23"].value)), rain_wet_ground_cost=D(_num_or0(wv_["B24"].value)),
            critical_path_delay_wd=D(_num_or0(wv_["B26"].value)), additional_billed_weeks=D(_num_or0(wv_["B27"].value)),
            wind_sensitivity_cost=D(_num_or0(wv_["B28"].value)), include_wind=(wv_["B29"].value == "Yes"))
        weather_meta = {
            "station": _s(wv_["B6"].value), "start": _s(wv_["B7"].value)[:10], "baseline_wd": _numstr(wv_["B8"].value, "0"),
            "wd_per_week": _numstr(wv_["B9"].value, "5"), "tool_version": _s(wv_["B19"].value), "tool_station": _s(wv_["B20"].value),
            "confidence": _s(wv_["B30"].value), "rerun_status": _s(wv_["B31"].value),
            "delay_wd": _numstr(wv_["B26"].value, "0"), "dry_programme_wd": _numstr(wv_["B8"].value, "0"),
        }
        recovery = D(_num_or0(wv_["B16"].value))
        # The workbook derives daily time-related prelims and weekly hire from specific build-up rows (formulas like =Y584*8 and =Y295+Y330).
        m13 = re.search(r"Y(\d+)\*(\d+)", _s(wr["B13"].value))
        m14 = re.findall(r"Y(\d+)", _s(wr["B14"].value))
        if m13 and m14 and int(m13.group(1)) in uid_at and all(int(x) in uid_at for x in m14):
            weather_links = {"daily_row": int(m13.group(1)), "hours_per_day": int(m13.group(2)), "weekly_rows": [int(x) for x in m14]}
            weather_links["daily_uid"] = uid_at[weather_links["daily_row"]]
            weather_links["weekly_uids"] = [uid_at[r] for r in weather_links["weekly_rows"]]
        else:
            weather_links = dict(no_links)
            notes.append("The workbook's weather sheet does not point at build-up rows for daily preliminaries and weekly hire, so the weather costs are not linked. "
                         "Link them on the Weather Risk page if you want the platform to work the weather allowance out.")

    ci = fm["Commercial Inputs"]
    commercial: list[dict] = []
    for r in range(5, 29):
        ref = ci.cell(r, 1).value
        if ref and str(ref).startswith("CA"):
            _check_numbers("Commercial Inputs", r, ref, [("percentage", ci.cell(r, 4).value), ("amount", ci.cell(r, 5).value)])
            commercial.append(dict(ref=str(ref), name=_s(ci.cell(r, 2).value), method=_s(ci.cell(r, 3).value),
                                   pct=D(ci.cell(r, 4).value), pc_sum=D(ci.cell(r, 5).value),
                                   include=_s(ci.cell(r, 6).value), basis=_s(v["Commercial Inputs"].cell(r, 8).value),
                                   note=_s(v["Commercial Inputs"].cell(r, 13).value)))
    if "Risk Truth" in have:
        rt = v["Risk Truth"]
        risk_feed = {"CA01": D(_num_or0(rt["B12"].value)), "CA02": D(_num_or0(rt["B13"].value))}
    else:
        rt = None
        risk_feed = {"CA01": D(0), "CA02": D(0)}
        notes.append("No Risk Truth sheet: no risk exposures were loaded and the risk allowances CA01 and CA02 are zero. Record exposures on the Risk Truth page.")

    cp, overlays, overlap = None, [], D(0)
    if "Consolidated Package" in have:
        cp = f["Consolidated Package"]
        overlays, overlap = _overlays_from_consolidated(v["Consolidated Package"])
        if not overlays:
            notes.append("The Consolidated Package sheet lists no subcontract packages that could be recognised. Add them on the Consolidated Package page.")
    else:
        notes.append("No Consolidated Package sheet: no subcontract packages were loaded, so the all-in package equals the siteworks tender. Add subcontract quotes on the Consolidated Package page.")

    cv = v["Cover & Instructions"] if "Cover & Instructions" in have else None
    rv = v["Rate Verification"] if "Rate Verification" in have else None
    if rv is None:
        notes.append("No Rate Verification sheet: the rate-evidence counts are blank.")
    g = lambda ws, cell: _s(ws[cell].value) if ws is not None else ""
    controls = {
        "release_status": g(rt, "B15"),
        "red_risks": g(rt, "B16"), "red_exposures": g(rt, "B17"),
        "duplicate_gate": g(rt, "B18"), "programme_gate": g(rt, "B19"),
        "tender_equals_risk_truth": g(rt, "B21"),
        "rate_green": g(rv, "B4"), "rate_amber": g(rv, "B5"), "rate_red": g(rv, "F4"),
        "rate_green_cost": g(rv, "C4"), "rate_amber_cost": g(rv, "C5"), "rate_red_cost": g(rv, "G4"),
        "cover_release": "",
    }
    for row in (cv.iter_rows(min_row=1, max_row=60) if cv is not None else []):
        for cell in row:
            if cell.value == "Release status":
                nxt = [c.value for c in row if c.column > cell.column and c.value not in (None, "")]
                if nxt:
                    controls["cover_release"] = _s(nxt[0])

    # What the source workbook displayed, so the platform can prove it reproduces it. Only the figures the workbook actually has are compared.
    reference: dict[str, float] | None = None
    if "Tender Build-Up" in have:
        tb = v["Tender Build-Up"]
        reference = {
            "Base direct estimate": float(D(_num_or0(tb["B20"].value))), "Pre-margin additions": float(D(_num_or0(tb["B39"].value))),
            "Subtotal before commercial adjustments": float(D(_num_or0(tb["B40"].value))),
            "Company overhead (CA17)": float(D(_num_or0(tb["B42"].value))), "Contractor profit (CA18)": float(D(_num_or0(tb["B43"].value))),
            "Siteworks tender excl. GST": float(D(_num_or0(tb["B47"].value)))}
        if "Weather Risk" in have:
            reference["Weather allowance (CA10)"] = float(D(_num_or0(v["Weather Risk"]["B38"].value)))
        if "Consolidated Package" in have:
            cp_v = v["Consolidated Package"]
            reference["Gross known package"] = float(D(_num_or0(cp_v["B12"].value)))
            reference["Working all-in tender excl. GST"] = float(D(_num_or0(cp_v["F56"].value)))
    else:
        notes.append("No Tender Build-Up sheet: the platform's totals could not be compared with the workbook's own, so the revision shows no reconciliation.")

    for sheet, cells in fm.subs.items():
        notes.append(f"{len(cells)} input cell{'s' if len(cells) != 1 else ''} on {sheet} held a formula (for example {', '.join(cells[:3])}). The value Excel last calculated was used as the input; "
                     "the platform recalculates everything from those numbers.")
    for sheet, cells in fm.uncalculated.items():
        notes.append(f"{len(cells)} input cell{'s' if len(cells) != 1 else ''} on {sheet} held a formula that had never been calculated (for example {', '.join(cells[:3])}) and was read as blank. "
                     "Open the workbook in Excel, save it, and upload it again if those cells matter.")
    return MasterWorkbookImport(
        reference=reference,
        meta=_cover_meta(v) if cv is not None else {}, library=lib, qs=qs, qs_extra=qs_extra, rows=rows, row_extra=extra,
        excel_rows=excel_rows, tool=tool, recovery=recovery, commercial=commercial,
        risk_feed=risk_feed, overlays=overlays, overlap=overlap, weather_meta=weather_meta, weather_links=weather_links,
        controls=controls, register=_register_with_risk_truth(v), notes=notes,
        risk_truth=_risks_and_exposures_from_risk_truth(v["Risk Truth"])[1] if "Risk Truth" in v.sheetnames else [],
        management_reserve=_reserve_from_commercial(commercial, v["Commercial Inputs"]),
        quotes=_quotes_from_sheet(v["Supplier Quote Register"]) if "Supplier Quote Register" in v.sheetnames else [],
        programme=_programme_from_sheet(v["Programme Export"] if "Programme Export" in v.sheetnames else None, {q.code for q in qs}, weather_meta.get("start", ""),
                                        int(weather_meta["wd_per_week"]) if str(weather_meta.get("wd_per_week", "")).isdigit() else 5), cached=v)
