"""Validated edits to estimate inputs. The ONLY way an in-app change reaches the numbers.

An edit is {"target", "key", "field", "value"} (set a value) or {"target", "op": "add"|"delete", "key", "value"?}.

  row        set    key = row uid        fields: productivity_rate, duration_override_hrs, count, manual_qty, utilisation,
                                                 waste, job_rate_override, verified, weather_exposed
             add    key = new uid ("N-xxxxxx")  value: qs_code, mode, resource_code ("" only for Lump Sum), task
             delete key = row uid
  qs         set    key = QS code        field: quantity
             add    key = new code       value: section, description, unit, quantity, basis, source?, notes?
             delete key = QS code        (also removes its build-up rows)
  library    add    key = new code       value: description, unit, base_rate, category, source?
  commercial set    key = CA ref         fields: include, pct, pc_sum
  overlay    set    key = package name   field : amount
             add    key = new package name   value: amount, kind? (default QUOTED)
             delete key = package name
  setting    set    key = weather|consolidated  field: recovery_allowance | confirmed_overlap
  weather    add    key = "setup"   value: station, start, working_days_per_week?, baseline_wd?   (turns the live weather tool on)
             delete key = "setup"   (back to the recorded tool outputs)
             set    key = "setup"   field: station | start | working_days_per_week | baseline_wd | local_factor | local_basis |
                                           wind_override | include_wind
             set    key = "links"   field: daily_uid | hours_per_day | weekly_uids   (rows that drive daily prelims / weekly hire)
  weather_activity  add key = new id ("W-xxxxxx")  value: task, start, finish, critical?, qs_codes?, labour?, plant?, note?, ov_*?
             set    key = id   field: task | start | finish | critical | qs_codes | labour | plant | note | ov_<factor>
             delete key = id

Edits apply in order; identities never shift while applying (rows are found by permanent uid, not position).
The returned change list is the NET difference between the original and the edited inputs.
"""
from __future__ import annotations
import copy
import re
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Any

from .ids import display_ids
from .importers.master_workbook import MasterWorkbookImport
from .models import BuildUpRow, LibraryRate, Overlay, QSItem, MODES
from .money import D
from . import weather_setup as wx

ROW_NUMERIC_NULLABLE = {"productivity_rate", "duration_override_hrs", "count", "manual_qty", "utilisation", "waste", "job_rate_override"}
ROW_YESNO = {"verified", "weather_exposed"}
BASIS_LABELS = ("MEASURED", "PROVIDED", "CALCULATED", "ALLOWANCE-PC", "QUOTED")
LIBRARY_CATEGORIES = ("Labour", "Plant", "Material", "Subcontract", "Other")
MAX_EDITS = 500
MAX_VALUE = Decimal("1e12")
QS_CODE = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")
LIB_CODE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,23}$")
NEW_UID = re.compile(r"^N-[A-Za-z0-9]{4,12}$")


class EditError(ValueError):
    pass


def _text(value: Any, what: str, *, maxlen: int, required=True) -> str:
    v = "" if value is None else str(value).strip()
    if required and not v:
        raise EditError(f"{what} can't be blank.")
    if len(v) > maxlen:
        raise EditError(f"{what} is too long (limit {maxlen} characters).")
    return v


def _num(value: Any, what: str, *, nullable=False, lo: Decimal | None = Decimal(0), hi: Decimal | None = None) -> Decimal | None:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        if nullable:
            return None
        raise EditError(f"{what} needs a number.")
    if isinstance(value, bool):
        raise EditError(f"{what} needs a number.")
    try:
        v = D(str(value).strip().replace(",", "") if isinstance(value, str) else value)
    except (InvalidOperation, ValueError):
        raise EditError(f"{what} must be a number.")
    if not v.is_finite():
        raise EditError(f"{what} must be a number.")
    if lo is not None and v < lo:
        raise EditError(f"{what} can't be less than {lo}.")
    if hi is not None and v > hi:
        raise EditError(f"{what} can't be more than {hi}.")
    if abs(v) > MAX_VALUE:
        raise EditError(f"{what} is too large.")
    return v


def _yesno(value: Any, what: str) -> str:
    if value in (True, "Yes", "yes", "true", "True"):
        return "Yes"
    if value in (False, "No", "no", "false", "False", "", None):
        return "No"
    raise EditError(f"{what} must be Yes or No.")


@dataclass
class _Row:
    uid: str
    row: BuildUpRow
    extra: dict
    excel: int
    origin: bool                # True = existed in the revision being edited
    deleted: bool = False


@dataclass
class _Qs:
    item: QSItem
    extra: dict
    origin: bool
    deleted: bool = False


def _resource_type(category: str) -> str:
    return category if category in ("Labour", "Plant", "Material") else "Other"


def apply_edits(base: MasterWorkbookImport, edits: list[dict[str, Any]]) -> tuple[MasterWorkbookImport, list[dict[str, Any]]]:
    if len(edits) > MAX_EDITS:
        raise EditError(f"Too many changes in one go (limit {MAX_EDITS}).")

    rows = [_Row(r.uid, r, dict(x), ex, True) for r, x, ex in zip(base.rows, base.row_extra, base.excel_rows)]
    by_uid = {r.uid: r for r in rows}
    qs = [_Qs(q, dict(base.qs_extra.get(q.code, {})), True) for q in base.qs]
    qs_by_code = {q.item.code: q for q in qs}
    library = dict(base.library)
    new_library: list[str] = []
    commercial = [dict(c) for c in base.commercial]
    com_pos = {c["ref"]: i for i, c in enumerate(commercial)}
    overlays = list(base.overlays)
    ov_pos = {o.name: i for i, o in enumerate(overlays)}
    recovery, overlap = base.recovery, base.overlap
    links = copy.deepcopy(base.weather_links)
    setup = wx.clone(base.weather_setup)
    setup_before = wx.clone(base.weather_setup)

    def protected_uids():
        return {u for u in (links.get("daily_uid"), *links.get("weekly_uids", [])) if u}
    used_codes = set(qs_by_code)

    def live_row(uid: str) -> _Row:
        r = by_uid.get(uid)
        if r is None:
            raise EditError(f"Unknown build-up row {uid!r}.")
        if r.deleted:
            raise EditError(f"Build-up row {uid!r} has been deleted.")
        return r

    def live_qs(code: str) -> _Qs:
        q = qs_by_code.get(code)
        if q is None:
            raise EditError(f"Unknown QS item {code!r}.")
        if q.deleted:
            raise EditError(f"QS item {code!r} has been deleted.")
        return q

    def delete_row(r: _Row):
        if r.uid in protected_uids():
            raise EditError(f"{r.row.task or r.uid} drives the weather calculation (daily preliminaries or weekly hire) and can't be deleted.")
        r.deleted = True

    for e in edits:
        if not isinstance(e, dict):
            raise EditError("Each change must be an object.")
        target, key, field, value, op = e.get("target"), e.get("key"), e.get("field"), e.get("value"), e.get("op") or "set"
        if op not in ("set", "add", "delete"):
            raise EditError(f"Unknown operation {op!r}.")

        if target == "row":
            if op == "add":
                uid = str(key or "")
                if not NEW_UID.match(uid) or uid in by_uid:
                    raise EditError("That new row's identity is invalid or already used.")
                v = value if isinstance(value, dict) else {}
                q = live_qs(str(v.get("qs_code", "")))
                mode = str(v.get("mode", ""))
                if mode not in MODES:
                    raise EditError(f"Calculation mode must be one of: {', '.join(MODES)}.")
                code = str(v.get("resource_code") or "").strip()
                if code:
                    if code not in library:
                        raise EditError(f"Rate {code!r} is not in this tender's library.")
                elif mode != "Lump Sum / Quote":
                    raise EditError("Choose a rate from the library (only a Lump Sum row can be priced without one).")
                task = _text(v.get("task"), "Description", maxlen=200)
                rtype = _resource_type(library[code].category) if code else "Other"
                new = BuildUpRow(qs_code=q.item.code, mode=mode, resource_type=rtype, resource_code=code,
                                 count=Decimal(1), utilisation=Decimal(1), waste=Decimal(0), task=task,
                                 verified="No", weather_exposed="No", uid=uid)
                entry = _Row(uid, new, {"productivity_unit": "", "quote_ref": "", "source_date": "",
                                        "confidence": "AMBER - ADDED IN PLATFORM", "assumption": "", "note": "", "workbook_qa": ""}, 0, False)
                last = max((i for i, x in enumerate(rows) if x.row.qs_code == q.item.code), default=len(rows) - 1)
                rows.insert(last + 1, entry)
                by_uid[uid] = entry
            elif op == "delete":
                delete_row(live_row(str(key)))
            else:
                r = live_row(str(key))
                what = f"{key} {field}"
                if field in ROW_NUMERIC_NULLABLE:
                    v = _num(value, what, nullable=True)
                    if field in ("utilisation", "waste") and v is not None and v > 1:
                        raise EditError(f"{what} is a fraction between 0 and 1 (for example 0.1 for 10%).")
                    if field == "productivity_rate" and v is not None and v == 0:
                        v = None
                    r.row = replace(r.row, **{field: v})
                elif field in ROW_YESNO:
                    r.row = replace(r.row, **{field: _yesno(value, what)})
                else:
                    raise EditError(f"{field!r} can't be edited on a build-up row.")

        elif target == "qs":
            if op == "add":
                code = str(key or "").strip().upper()
                if not QS_CODE.match(code):
                    raise EditError("A QS code is letters and numbers starting with a letter, for example EW11 (2 to 12 characters).")
                if code in used_codes:
                    raise EditError(f"QS code {code} is already used.")
                v = value if isinstance(value, dict) else {}
                section = _text(v.get("section"), "Section", maxlen=80)
                description = _text(v.get("description"), "Description", maxlen=200)
                unit = _text(v.get("unit"), "Unit", maxlen=12)
                qty = _num(v.get("quantity"), f"{code} quantity")
                basis = str(v.get("basis", "")).strip().upper()
                if basis not in BASIS_LABELS:
                    raise EditError(f"Classify the quantity as one of: {', '.join(BASIS_LABELS)}.")
                src = _text(v.get("source"), "Source", maxlen=300, required=False)
                notes = _text(v.get("notes"), "Notes", maxlen=500, required=False)
                entry = _Qs(QSItem(code, section, description, unit, qty),
                            {"basis": basis, "source": src, "status": "AMBER - ADDED IN PLATFORM", "notes": notes, "flag": "AMBER",
                             "owner": "", "verification": "NOT VERIFIED", "quote_ref": ""}, False)
                last = max((i for i, x in enumerate(qs) if x.item.section == section), default=len(qs) - 1)
                qs.insert(last + 1, entry)
                qs_by_code[code] = entry
                used_codes.add(code)
            elif op == "delete":
                q = live_qs(str(key))
                for r in rows:
                    if r.row.qs_code == q.item.code and not r.deleted:
                        delete_row(r)
                q.deleted = True
            else:
                if field != "quantity":
                    raise EditError("Only the quantity of a QS item can be edited.")
                q = live_qs(str(key))
                q.item = replace(q.item, quantity=_num(value, f"{key} quantity"))

        elif target == "library":
            if op != "add":
                raise EditError("Library rates can only be added here. Use a job rate override to change a price on one row.")
            code = str(key or "").strip().upper()
            if not LIB_CODE.match(code):
                raise EditError("A rate code is letters, numbers and dashes, for example PL-EXC-20.")
            if code in library:
                raise EditError(f"Rate code {code} already exists.")
            v = value if isinstance(value, dict) else {}
            category = str(v.get("category", ""))
            if category not in LIBRARY_CATEGORIES:
                raise EditError(f"Category must be one of: {', '.join(LIBRARY_CATEGORIES)}.")
            library[code] = LibraryRate(code=code, description=_text(v.get("description"), "Description", maxlen=200),
                                        unit=_text(v.get("unit"), "Unit", maxlen=12), base_rate=_num(v.get("base_rate"), f"{code} rate"),
                                        category=category, source=_text(v.get("source"), "Source", maxlen=300, required=False) or "Added in platform (AMBER: no supplier evidence yet)")
            new_library.append(code)

        elif target == "commercial":
            if key not in com_pos:
                raise EditError(f"Unknown commercial line {key!r}.")
            c = commercial[com_pos[key]]
            if field == "include":
                c["include"] = _yesno(value, f"{key} include")
            elif field == "pct":
                hi = Decimal("0.999999") if c["method"] == "Margin %" else Decimal("10")
                c["pct"] = _num(value, f"{key} percentage", hi=hi)
            elif field == "pc_sum":
                c["pc_sum"] = _num(value, f"{key} amount")
            else:
                raise EditError(f"{field!r} can't be edited on a commercial line.")

        elif target == "overlay":
            name = str(key or "").strip()
            if op == "add":
                name = _text(key, "Package name", maxlen=80)
                if name.lower() in {o.name.lower() for o in overlays}:
                    raise EditError(f"A subcontract package called {name!r} already exists.")
                v = value if isinstance(value, dict) else {}
                overlays.append(Overlay(name, _num(v.get("amount"), f"{name} amount"), _text(v.get("kind") or "QUOTED", "Package type", maxlen=40)))
                ov_pos[name] = len(overlays) - 1
            elif op == "delete":
                if name not in ov_pos:
                    raise EditError(f"Unknown subcontract package {name!r}.")
                overlays = [o for o in overlays if o.name != name]
                ov_pos = {o.name: i for i, o in enumerate(overlays)}
            else:
                if name not in ov_pos:
                    raise EditError(f"Unknown subcontract package {name!r}.")
                if field != "amount":
                    raise EditError("Only the amount of a subcontract package can be edited.")
                i = ov_pos[name]
                overlays[i] = Overlay(overlays[i].name, _num(value, f"{name} amount"), overlays[i].kind)

        elif target == "weather":
            try:
                if key == "setup":
                    if op == "add":
                        if setup is not None:
                            raise EditError("The live weather tool is already switched on for this tender.")
                        v = value if isinstance(value, dict) else {}
                        setup = wx.new_setup(v.get("station"), v.get("start"), v.get("working_days_per_week", 5), v.get("baseline_wd", 0))
                    elif op == "delete":
                        if setup is None:
                            raise EditError("The live weather tool isn't switched on.")
                        setup = None
                    else:
                        if setup is None:
                            raise EditError("Switch the live weather tool on first.")
                        wx.set_field(setup, str(field), value)
                elif key == "links":
                    if field == "hours_per_day":
                        links["hours_per_day"] = int(wx._num(value, "Hours per day", lo=D(1), hi=D(24)).split(".")[0])
                    elif field == "daily_uid":
                        uid = str(value or "")
                        if uid:
                            live_row(uid)
                        links["daily_uid"] = uid
                    elif field == "weekly_uids":
                        uids = [x for x in (re.split(r"[,\s]+", value) if isinstance(value, str) else (value or [])) if x]
                        uids = [str(x) for x in uids]
                        for uid in uids:
                            live_row(uid)
                        links["weekly_uids"] = uids
                    else:
                        raise EditError(f"{field!r} can't be edited on the weather links.")
                else:
                    raise EditError("Unknown weather setting.")
            except wx.SetupError as ex:
                raise EditError(str(ex))

        elif target == "weather_activity":
            if setup is None:
                raise EditError("Switch the live weather tool on first.")
            acts = setup["activities"]
            try:
                if op == "add":
                    aid = str(key or "")
                    if not wx.ACTIVITY_ID.match(aid) or any(a["id"] == aid for a in acts):
                        raise EditError("That new weather activity's identity is invalid or already used.")
                    if len(acts) >= wx.MAX_ACTIVITIES:
                        raise EditError(f"A tender can have at most {wx.MAX_ACTIVITIES} weather activities.")
                    acts.append(wx.build_activity(aid, value if isinstance(value, dict) else {}))
                else:
                    a = next((x for x in acts if x["id"] == str(key)), None)
                    if a is None:
                        raise EditError(f"Unknown weather activity {key!r}.")
                    if op == "delete":
                        acts.remove(a)
                    else:
                        wx.set_activity_field(a, str(field), value)
                        wx.check_activity(a)
            except wx.SetupError as ex:
                raise EditError(str(ex))

        elif target == "setting":
            if (key, field) == ("weather", "recovery_allowance"):
                recovery = _num(value, "Weather recovery allowance")
            elif (key, field) == ("consolidated", "confirmed_overlap"):
                overlap = _num(value, "Confirmed overlap")
            else:
                raise EditError("Unknown setting.")
        else:
            raise EditError(f"Unknown edit target {target!r}.")

    m = copy.copy(base)
    keep_rows = [r for r in rows if not r.deleted]
    keep_qs = [q for q in qs if not q.deleted]
    m.rows = [r.row for r in keep_rows]
    m.row_extra = [r.extra for r in keep_rows]
    m.excel_rows = [r.excel for r in keep_rows]
    m.qs = [q.item for q in keep_qs]
    m.qs_extra = {q.item.code: q.extra for q in keep_qs}
    m.library = library
    m.commercial, m.overlays, m.recovery, m.overlap = commercial, overlays, recovery, overlap
    m.weather_links, m.weather_setup = links, setup
    m.reference = None            # no longer the workbook as received
    return m, _net_changes(base, m, rows, qs, new_library)


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return format(v.normalize(), "f")
    return str(v)


def _net_changes(a: MasterWorkbookImport, b: MasterWorkbookImport, rows: list[_Row], qs: list[_Qs], new_library: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def add(target, key, field, label, before, after):
        if before != after:
            out.append({"target": target, "key": key, "field": field, "label": label, "before": _fmt(before), "after": _fmt(after)})

    base_ids = dict(zip((r.uid for r in a.rows), display_ids(a.rows)))
    final_ids = dict(zip((r.uid for r in b.rows), display_ids(b.rows)))
    base_rows = {r.uid: r for r in a.rows}

    for code in new_library:
        lr = b.library[code]
        add("library", code, "added", f"{code} {lr.description}", "", f"{_fmt(lr.base_rate)} per {lr.unit}")

    # QS items
    for q in qs:
        code = q.item.code
        if q.origin and q.deleted:
            old = next(x for x in a.qs if x.code == code)
            add("qs", code, "removed", f"{code} {old.description}", f"{_fmt(old.quantity)} {old.unit}", "")
        elif not q.origin and not q.deleted:
            add("qs", code, "added", f"{code} {q.item.description}", "", f"{_fmt(q.item.quantity)} {q.item.unit} · {q.extra['basis']}")
        elif q.origin and not q.deleted:
            old = next(x for x in a.qs if x.code == code)
            add("qs", code, "quantity", f"{code} {old.description}", old.quantity, q.item.quantity)

    # build-up rows
    for r in rows:
        if r.origin and r.deleted:
            add("row", r.uid, "removed", f"{base_ids[r.uid]} {r.row.task}", f"{r.row.mode} · {r.row.resource_code or 'no rate'}", "")
        elif not r.origin and not r.deleted:
            add("row", r.uid, "added", f"{final_ids[r.uid]} {r.row.task}", "", f"{r.row.mode} · {r.row.resource_code or 'no rate'}")
        elif r.origin and not r.deleted:
            old = base_rows[r.uid]
            for f in sorted(ROW_NUMERIC_NULLABLE | ROW_YESNO):
                add("row", r.uid, f, f"{base_ids[r.uid]} {old.task}", getattr(old, f), getattr(r.row, f))

    for x, y in zip(a.commercial, b.commercial):
        for f in ("include", "pct", "pc_sum"):
            add("commercial", x["ref"], f, f"{x['ref']} {x['name']}", x[f], y[f])
    a_ov, b_ov = {o.name: o for o in a.overlays}, {o.name: o for o in b.overlays}
    for name, x in a_ov.items():
        if name not in b_ov:
            add("overlay", name, "removed", name, f"{_fmt(x.amount)} · {x.kind}", "")
        else:
            add("overlay", name, "amount", name, x.amount, b_ov[name].amount)
    for name, y in b_ov.items():
        if name not in a_ov:
            add("overlay", name, "added", name, "", f"{_fmt(y.amount)} · {y.kind}")
    _weather_changes(a, b, add)
    add("setting", "weather", "recovery_allowance", "Weather recovery allowance", D(a.recovery), D(b.recovery))
    add("setting", "consolidated", "confirmed_overlap", "Confirmed Siteworks / Coast overlap", D(a.overlap), D(b.overlap))
    return out


def row_ids(rows):  # backwards-compatible alias
    return display_ids(rows)


def _weather_changes(a: MasterWorkbookImport, b: MasterWorkbookImport, add) -> None:
    sa, sb = a.weather_setup, b.weather_setup
    if sa is None and sb is not None:
        add("weather", "setup", "added", "Live weather tool switched on", "", f"{sb['station']} from {sb['start']}")
    elif sa is not None and sb is None:
        add("weather", "setup", "removed", "Live weather tool switched off", f"{sa['station']} from {sa['start']}", "")
    if sa is not None and sb is not None:
        labels = {"station": "Weather station", "start": "Project start", "working_days_per_week": "Working days per week",
                  "baseline_wd": "Baseline working days", "local_factor": "Local wet-day factor", "local_basis": "Local factor basis",
                  "wind_override": "Wind probability override", "include_wind": "Include wind proxy"}
        for f, label in labels.items():
            add("weather", "setup", f, label, sa[f], sb[f])
    ia = {x["id"]: x for x in (sa["activities"] if sa else [])}
    ib = {x["id"]: x for x in (sb["activities"] if sb else [])}
    desc = lambda x: f"{x['task']} {x['start']} to {x['finish']}" + (" (critical path)" if x["critical"] else "")
    for aid, x in ia.items():
        if aid not in ib:
            add("weather_activity", aid, "removed", f"Weather activity {x['task']}", desc(x), "")
        else:
            y = ib[aid]
            for f in ("task", "start", "finish", "critical", "labour", "plant", "note"):
                add("weather_activity", aid, f, f"Weather activity {x['task']}", x[f], y[f])
            add("weather_activity", aid, "qs_codes", f"Weather activity {x['task']}", ",".join(x["qs_codes"]), ",".join(y["qs_codes"]))
            for k in sorted(set(x["overrides"]) | set(y["overrides"])):
                add("weather_activity", aid, "ov_" + k, f"Weather activity {x['task']}", x["overrides"].get(k, ""), y["overrides"].get(k, ""))
    for aid, y in ib.items():
        if aid not in ia:
            add("weather_activity", aid, "added", f"Weather activity {y['task']}", "", desc(y))
    for f in ("daily_uid", "hours_per_day"):
        add("weather", "links", f, "Daily preliminaries link" if f == "daily_uid" else "Hours per day", a.weather_links.get(f), b.weather_links.get(f))
    add("weather", "links", "weekly_uids", "Weekly hire links", ",".join(a.weather_links.get("weekly_uids", [])), ",".join(b.weather_links.get("weekly_uids", [])))
