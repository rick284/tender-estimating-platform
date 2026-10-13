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
  commercial set    key = CA ref         fields: include, pct, pc_sum, method (only between the bases in COMMERCIAL_METHODS), name, note
  commercial add    key = "" (next free CX01..) or a CX ref, value {name, method (% | PC Sum), pct | pc_sum, include, note}: an allowance added by the estimator, before overhead and margin
  commercial delete key = CX ref         (platform lines CA01..CA25 can be switched off but not removed)
  overlay    set    key = package name   field : amount
             add    key = new package name   value: amount, kind? (default QUOTED)
             delete key = package name
  setting    set    key = weather|consolidated  field: recovery_allowance | confirmed_overlap
  weather    add    key = "setup"   value: station, start, working_days_per_week?, baseline_wd?   (turns the live weather tool on)
             delete key = "setup"   (back to the recorded tool outputs)
             set    key = "setup"   field: station | start | working_days_per_week | baseline_wd | local_factor | local_basis |
                                           wind_override | include_wind
             set    key = "links"   field: daily_uid | hours_per_day | weekly_uids   (rows that drive daily prelims / weekly hire)
  schedule   add    key = "format"  value: text (pasted lines, see schedule.parse_format), name?, client?   (client price schedule format)
             delete key = "format"  (back to the automatic schedule by QS section)
  schedule_map set  key = source ("qs:EW01" | "ca:CA10" | "overlay:Name")  field = "to"  value: "line:REF" | "group:ID" | "spread" |
                       JSON list of parts | "" (unmap)
  register   add    key = new id ("R-xxxxxx")  value: kind (document|inclusion|exclusion|assumption|rfi|risk), title / detail / ref / ...
             set    key = id   field: ref | title | detail | action | status | rag | owner | likelihood | impact | rating
             delete key = id
  quote      add    key = new id ("S-xxxxxx")  value: package / supplier / amount / ... (see quotes.FIELDS)
             set    key = id   field: any of quotes.FIELDS
             delete key = id
  exposure   add    key = new id ("X-xxxxxx")  value: risk_id / consequence / mode / ... (see risk_truth.FIELDS)   (Risk Truth exposure)
             set    key = id   field: any of risk_truth.FIELDS
             delete key = id
  reserve    add    key = "setup"  (switch the Management Reserve adjudication on; the selected reserve starts at the current CA16 amount)
             set    key = "block"  field: selected | selected_basis | adjudicated_by | adjudicated_on
             delete key = "setup"  (back to a plain CA16 line holding the selected amount)
  reserve_item  add key = new id ("M-xxxxxx")  value: title, impact, basis (Sell|Cost), probability_low/high, prob_status, ... (see management_reserve.ITEM_FIELDS)
             set    key = id   field: any of management_reserve.ITEM_FIELDS
             delete key = id
  programme  add    key = "setup"   value: start?, days_per_week?, hours_per_day?  (one task per QS item, no predecessors yet)
             delete key = "setup"
             set    key = "config"  field: start | days_per_week | hours_per_day
  programme_task  add key = new id ("P-xxxxxx")  value: code, name, qs_code?, override_days?, predecessors?, hammock?, basis?, note?
             set    key = id   field: code | name | override_days | predecessors | hammock | basis | note
             delete key = id
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

from .commercial import COMMERCIAL_METHODS, is_custom, is_pre_margin, methods_for
from .ids import display_ids
from .importers.master_workbook import MasterWorkbookImport
from .models import BuildUpRow, LibraryRate, Overlay, QSItem, MODES
from .money import D
from . import weather_setup as wx
from . import schedule as sch
from . import register as reg
from . import quotes as qt
from . import risk_truth as rtm
from . import management_reserve as mrm
from . import programme as prg
import json

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
    sched = copy.deepcopy(base.schedule)
    register = copy.deepcopy(base.register)
    quotes = copy.deepcopy(base.quotes)
    exposures = copy.deepcopy(base.risk_truth)
    reserve = copy.deepcopy(base.management_reserve)
    programme = copy.deepcopy(base.programme)
    sched_before = copy.deepcopy(base.schedule)
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

        elif target == "commercial" and op == "add":
            v = value if isinstance(value, dict) else {}
            ref = str(key or "").strip().upper()
            if not ref:
                n = 1
                while f"CX{n:02d}" in com_pos:
                    n += 1
                ref = f"CX{n:02d}"
            if not re.fullmatch(r"CX\d{2}", ref):
                raise EditError("Added allowances are numbered CX01, CX02 ...")
            if ref in com_pos:
                raise EditError(f"{ref} already exists.")
            method = str(v.get("method") or "%").strip()
            if method not in ("%", "PC Sum"):
                raise EditError("An added allowance is either a percentage of base direct or a PC sum.")
            name = _text(v.get("name"), "Description", maxlen=80)
            if name.lower() in {c["name"].lower() for c in commercial}:
                raise EditError(f"There is already a commercial line called {name!r}.")
            pos = max([i for i, c in enumerate(commercial) if is_pre_margin(c["ref"])] or [-1]) + 1          # sits with the other pre-margin allowances
            commercial.insert(pos, {"ref": ref, "name": name, "method": method, "include": _yesno(v.get("include", "Yes"), f"{ref} include"),
                                    "basis": "", "note": _text(v.get("note"), "Note", maxlen=500, required=False),
                                    "pct": _num(v.get("pct"), f"{ref} percentage", hi=Decimal("10")) if method == "%" else D(0),
                                    "pc_sum": _num(v.get("pc_sum"), f"{ref} amount") if method == "PC Sum" else D(0)})
            com_pos = {c["ref"]: i for i, c in enumerate(commercial)}

        elif target == "commercial" and op == "delete":
            if key not in com_pos:
                raise EditError(f"Unknown commercial line {key!r}.")
            if not is_custom(key):
                raise EditError(f"{key} is a platform line: switch it off instead of removing it.")
            commercial = [c for c in commercial if c["ref"] != key]
            com_pos = {c["ref"]: i for i, c in enumerate(commercial)}

        elif target == "commercial":
            if key not in com_pos:
                raise EditError(f"Unknown commercial line {key!r}.")
            c = commercial[com_pos[key]]
            if key == "CA16" and reserve is not None and field in ("pc_sum", "pct"):
                raise EditError("The Management Reserve amount is set on the Management Reserve page (selected reserve), not here.")
            if field == "include":
                c["include"] = _yesno(value, f"{key} include")
            elif field == "pct":
                hi = Decimal("0.999999") if c["method"] == "Margin %" else Decimal("10")
                c["pct"] = _num(value, f"{key} percentage", hi=hi)
            elif field == "pc_sum":
                c["pc_sum"] = _num(value, f"{key} amount")
            elif field == "name":
                new = _text(value, "Description", maxlen=80)
                if new.lower() in {x["name"].lower() for x in commercial if x["ref"] != key}:
                    raise EditError(f"There is already a commercial line called {new!r}.")
                c["name"] = new
            elif field == "note":
                c["note"] = _text(value, "Note", maxlen=500, required=False)
            elif field == "method":
                allowed = methods_for(key)
                if not allowed or c["method"] not in allowed:
                    raise EditError(f"{key} is calculated by the platform (its basis can't be changed here).")
                new = str(value or "").strip()
                if new not in allowed:
                    raise EditError(f"{key} can be set to: {', '.join(allowed)}.")
                if new == "Margin %" and Decimal(str(c["pct"])) >= 1:
                    raise EditError("Set the margin below 100% before choosing Margin %.")
                c["method"] = new
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

        elif target == "schedule":
            try:
                if op == "add":
                    v = value if isinstance(value, dict) else {}
                    sched = sch.parse_format(str(v.get("text", "")), str(v.get("name", "")), str(v.get("client", "")))
                elif op == "delete":
                    sched = None
                else:
                    raise EditError("Use add or delete for the price schedule format.")
            except sch.ScheduleError as ex:
                raise EditError(str(ex))

        elif target == "schedule_map":
            src_key = str(key or "")
            if not re.match(r"^(qs|ca|overlay):.+", src_key) or field != "to":
                raise EditError("Unknown price schedule mapping.")
            if sched is None:                                   # first change: freeze the automatic schedule so it can be edited
                live_qs = [q for q in qs if not q.deleted]
                sched = sch.default_schedule(list(dict.fromkeys(q.item.section for q in live_qs)), [o.name for o in overlays])
                sched["map"] = sch.auto_map(sched, [{"code": q.item.code, "section": q.item.section} for q in live_qs],
                                            [{"name": o.name} for o in overlays], [c["ref"] for c in commercial if is_pre_margin(c["ref"])])
                sched["auto_map"] = dict(sched["map"])
            v = value
            if isinstance(v, str) and v.strip().startswith("["):
                try:
                    v = json.loads(v)
                except ValueError:
                    raise EditError("The split isn't valid.")
            if v in (None, "", []):
                sched["map"].pop(src_key, None)
            else:
                parts = [v] if isinstance(v, str) else [p_.get("to") if isinstance(p_, dict) else None for p_ in v]
                if not all(isinstance(t, str) and sch.valid_target(sched, t) for t in parts):
                    raise EditError("Choose a line from this price schedule.")
                if isinstance(v, list):
                    for p_ in v:
                        if p_.get("amount") not in (None, ""):
                            wx._num(p_["amount"], "Split amount", hi=D("1e12"))
                sched["map"][src_key] = v

        elif target == "register":
            try:
                if op == "add":
                    rid = str(key or "")
                    if not reg.ITEM_ID.match(rid) or any(x["id"] == rid for x in register):
                        raise EditError("That new register item's identity is invalid or already used.")
                    if len(register) >= reg.MAX_ITEMS:
                        raise EditError(f"The register can hold at most {reg.MAX_ITEMS} items.")
                    register.append(reg.build_item(rid, value if isinstance(value, dict) else {}, register))
                else:
                    item = next((x for x in register if x["id"] == str(key)), None)
                    if item is None:
                        raise EditError(f"Unknown register item {key!r}.")
                    if op == "delete":
                        register.remove(item)
                    else:
                        reg.set_field(item, str(field), value)
                        if item["ref"] and sum(1 for x in register if x["kind"] == item["kind"] and x["ref"] == item["ref"]) > 1:
                            raise EditError(f"{item['ref']} is already used.")
            except reg.RegisterError as ex:
                raise EditError(str(ex))

        elif target == "quote":
            try:
                if op == "add":
                    qid = str(key or "")
                    if not qt.ITEM_ID.match(qid) or any(x["id"] == qid for x in quotes):
                        raise EditError("That new quote's identity is invalid or already used.")
                    if len(quotes) >= qt.MAX_ITEMS:
                        raise EditError(f"The quote register can hold at most {qt.MAX_ITEMS} quotes.")
                    quotes.append(qt.build_item(qid, value if isinstance(value, dict) else {}, quotes))
                else:
                    item = next((x for x in quotes if x["id"] == str(key)), None)
                    if item is None:
                        raise EditError(f"Unknown quote {key!r}.")
                    if op == "delete":
                        quotes.remove(item)
                    else:
                        qt.set_field(item, str(field), value)
                        if item["ref"] and sum(1 for x in quotes if x["ref"] == item["ref"]) > 1:
                            raise EditError(f"{item['ref']} is already used.")
            except qt.QuoteError as ex:
                raise EditError(str(ex))

        elif target == "reserve":
            try:
                if key == "setup":
                    if op == "add":
                        if reserve is not None:
                            raise EditError("The Management Reserve adjudication is already switched on.")
                        ca = commercial[com_pos["CA16"]] if "CA16" in com_pos else None
                        reserve = mrm.new_block(str(ca["pc_sum"]) if ca and ca["method"] in ("Fixed Amount", "PC Sum") and D(ca["pc_sum"]) > 0 else "")
                    elif op == "delete":
                        if reserve is None:
                            raise EditError("The Management Reserve adjudication isn't switched on.")
                        if "CA16" in com_pos:                       # keep the selected amount as a plain fixed line
                            ca = commercial[com_pos["CA16"]]
                            ca["method"] = "Fixed Amount"; ca["pc_sum"] = D(mrm._num(reserve.get("selected")) or 0)
                        reserve = None
                    else:
                        raise EditError("Use add or delete on the reserve setup.")
                else:
                    if reserve is None:
                        raise EditError("Switch the Management Reserve adjudication on first.")
                    if key != "block" or op != "set":
                        raise EditError("Unknown reserve setting.")
                    mrm.set_block_field(reserve, str(field), value)
            except mrm.ReserveError as ex:
                raise EditError(str(ex))

        elif target == "reserve_item":
            try:
                if reserve is None:
                    raise EditError("Switch the Management Reserve adjudication on first.")
                items = reserve["items"]
                if op == "add":
                    mid = str(key or "")
                    if not mrm.ITEM_ID.match(mid) or any(x["id"] == mid for x in items):
                        raise EditError("That new item's identity is invalid or already used.")
                    if len(items) >= mrm.MAX_ITEMS:
                        raise EditError(f"The reserve can hold at most {mrm.MAX_ITEMS} items.")
                    items.append(mrm.build_item(mid, value if isinstance(value, dict) else {}, items))
                else:
                    item = next((x for x in items if x["id"] == str(key)), None)
                    if item is None:
                        raise EditError(f"Unknown reserve item {key!r}.")
                    if op == "delete":
                        items.remove(item)
                    else:
                        mrm.set_item_field(item, str(field), value)
                        if item["ref"] and sum(1 for x in items if x["ref"] == item["ref"]) > 1:
                            raise EditError(f"{item['ref']} is already used.")
            except mrm.ReserveError as ex:
                raise EditError(str(ex))

        elif target == "exposure":
            try:
                if op == "add":
                    xid = str(key or "")
                    if not rtm.ITEM_ID.match(xid) or any(x["id"] == xid for x in exposures):
                        raise EditError("That new exposure's identity is invalid or already used.")
                    if len(exposures) >= rtm.MAX_ITEMS:
                        raise EditError(f"Risk Truth can hold at most {rtm.MAX_ITEMS} exposures.")
                    exposures.append(rtm.build_item(xid, value if isinstance(value, dict) else {}, exposures))
                else:
                    item = next((x for x in exposures if x["id"] == str(key)), None)
                    if item is None:
                        raise EditError(f"Unknown exposure {key!r}.")
                    if op == "delete":
                        exposures.remove(item)
                    else:
                        rtm.set_field(item, str(field), value)
                        if item["ref"] and sum(1 for x in exposures if x["ref"] == item["ref"]) > 1:
                            raise EditError(f"{item['ref']} is already used.")
            except rtm.RiskTruthError as ex:
                raise EditError(str(ex))

        elif target == "programme":
            try:
                if key == "setup":
                    if op == "add":
                        if programme is not None:
                            raise EditError("The programme is already set up for this tender.")
                        v = value if isinstance(value, dict) else {}
                        programme = prg.new_programme("", 5, 8)
                        for k_ in ("start", "days_per_week", "hours_per_day"):
                            if v.get(k_) not in (None, ""):
                                prg.set_config(programme, k_, v[k_])
                        for q_ in (x for x in qs if not x.deleted):
                            programme["tasks"].append({"id": "P-" + re.sub(r"[^A-Za-z0-9]", "", q_.item.code)[:10].ljust(4, "x"), "code": q_.item.code, "name": q_.item.description[:200],
                                                       "qs_code": q_.item.code, "override_days": None, "predecessors": [], "hammock": q_.item.section.upper().startswith("PRELIMINARIES"),
                                                       "basis": "", "note": ""})
                    elif op == "delete":
                        if programme is None:
                            raise EditError("The programme isn't set up.")
                        programme = None
                    else:
                        raise EditError("Use add or delete for the programme setup.")
                elif key == "config":
                    if programme is None:
                        raise EditError("Set up the programme first.")
                    prg.set_config(programme, str(field), value)
                else:
                    raise EditError("Unknown programme setting.")
            except prg.ProgrammeError as ex:
                raise EditError(str(ex))

        elif target == "programme_task":
            if programme is None:
                raise EditError("Set up the programme first.")
            try:
                tasks_ = programme["tasks"]
                if op == "add":
                    tid = str(key or "")
                    if not prg.TASK_ID.match(tid) or any(x["id"] == tid for x in tasks_):
                        raise EditError("That new programme task's identity is invalid or already used.")
                    if len(tasks_) >= prg.MAX_TASKS:
                        raise EditError(f"A programme can have at most {prg.MAX_TASKS} tasks.")
                    tasks_.append(prg.build_task(tid, value if isinstance(value, dict) else {}, tasks_))
                else:
                    t_ = next((x for x in tasks_ if x["id"] == str(key)), None)
                    if t_ is None:
                        raise EditError(f"Unknown programme task {key!r}.")
                    if op == "delete":
                        tasks_.remove(t_)
                        for x in tasks_:
                            x["predecessors"] = [c for c in x["predecessors"] if c != t_["code"]]
                    else:
                        old_code = t_["code"]
                        prg.set_task_field(t_, str(field), value, tasks_)
                        if field == "code" and t_["code"] != old_code:
                            for x in tasks_:
                                x["predecessors"] = [t_["code"] if c == old_code else c for c in x["predecessors"]]
            except prg.ProgrammeError as ex:
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
    if programme is not None:                      # tasks and links of QS items that no longer exist go with them
        live = {q.item.code for q in keep_qs}
        gone = {t["code"] for t in programme["tasks"] if t["qs_code"] and t["qs_code"] not in live}
        programme["tasks"] = [t for t in programme["tasks"] if t["code"] not in gone]
        for t in programme["tasks"]:
            t["predecessors"] = [c for c in t["predecessors"] if c not in gone]
    m.weather_links, m.weather_setup, m.schedule, m.register, m.quotes, m.programme = links, setup, sched, register, quotes, programme
    m.risk_truth = exposures
    m.management_reserve = reserve
    m.reference = None            # no longer the workbook as received
    return m, _net_changes(base, m, rows, qs, new_library)


def _line_text(c: dict[str, Any]) -> str:
    return f"{Decimal(str(c['pct'])) * 100:g}% of base direct" if c["method"] == "%" else f"PC sum ${Decimal(str(c['pc_sum'])):,.2f}"


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

    a_com, b_com = {c["ref"]: c for c in a.commercial}, {c["ref"]: c for c in b.commercial}
    for ref, x in a_com.items():
        if ref not in b_com:
            add("commercial", ref, "removed", f"{ref} {x['name']}", _line_text(x), "")
            continue
        for f in ("include", "method", "pct", "pc_sum", "name"):
            add("commercial", ref, f, f"{ref} {x['name']}", x[f], b_com[ref][f])
    for ref, y in b_com.items():
        if ref not in a_com:
            add("commercial", ref, "added", f"{ref} {y['name']}", "", _line_text(y))
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
    _schedule_changes(a, b, add)
    _register_changes(a, b, add)
    _quote_changes(a, b, add)
    _exposure_changes(a, b, add)
    _reserve_changes(a, b, add)
    _programme_changes(a, b, add)
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


def _schedule_changes(a: MasterWorkbookImport, b: MasterWorkbookImport, add) -> None:
    sa, sb = a.schedule, b.schedule
    fmt = lambda x: None if x is None else [(g["id"], g["name"], [(ln["ref"], ln["trade"], ln["kind"]) for ln in g["lines"]]) for g in x["groups"]]
    custom = lambda x: x is not None and not x.get("auto")
    if custom(sa) != custom(sb) or (custom(sb) and fmt(sa) != fmt(sb)):
        add("schedule", "format", "format", "Client price schedule format",
            (sa or {}).get("name", "") or ("custom" if custom(sa) else "automatic"), (sb or {}).get("name", "") or ("custom" if custom(sb) else "automatic"))
    if sb is None:
        return
    base_map = sa["map"] if sa is not None else sb.get("auto_map", {})
    dump = lambda v: "" if v is None else (v if isinstance(v, str) else json.dumps(v))
    for k in sorted(set(base_map) | set(sb["map"])):
        add("schedule_map", k, "to", f"Price schedule: {k.split(':', 1)[1]}", dump(base_map.get(k)), dump(sb["map"].get(k)))


def _register_changes(a: MasterWorkbookImport, b: MasterWorkbookImport, add) -> None:
    ia, ib = {x["id"]: x for x in a.register}, {x["id"]: x for x in b.register}
    label = lambda x: f"{x['kind'].upper()} {x['ref']} {x['title']}".strip()[:120]
    for rid, x in ia.items():
        if rid not in ib:
            add("register", rid, "removed", label(x), x["title"][:80], "")
        else:
            for f in reg.FIELDS:
                add("register", rid, f, label(x), x[f], ib[rid][f])
    for rid, y in ib.items():
        if rid not in ia:
            add("register", rid, "added", label(y), "", y["title"][:80])


def _quote_changes(a: MasterWorkbookImport, b: MasterWorkbookImport, add) -> None:
    ia, ib = {x["id"]: x for x in a.quotes}, {x["id"]: x for x in b.quotes}
    label = lambda x: f"Quote {x['ref']} {x['supplier'] or x['package']}".strip()[:120]
    for qid, x in ia.items():
        if qid not in ib:
            add("quote", qid, "removed", label(x), x["package"][:80], "")
        else:
            for f in qt.FIELDS:
                add("quote", qid, f, label(x), x[f], ib[qid][f])
    for qid, y in ib.items():
        if qid not in ia:
            add("quote", qid, "added", label(y), "", y["package"][:80] or y["supplier"][:80])


def _exposure_changes(a: MasterWorkbookImport, b: MasterWorkbookImport, add) -> None:
    ia, ib = {x["id"]: x for x in a.risk_truth}, {x["id"]: x for x in b.risk_truth}
    label = lambda x: f"Risk Truth {x['ref']} {x['consequence']}".strip()[:120]
    for xid, x in ia.items():
        if xid not in ib:
            add("exposure", xid, "removed", label(x), x["consequence"][:80], "")
        else:
            for f in rtm.FIELDS:
                add("exposure", xid, f, label(x), x[f], ib[xid][f])
    for xid, y in ib.items():
        if xid not in ia:
            add("exposure", xid, "added", label(y), "", y["consequence"][:80])


def _reserve_changes(a: MasterWorkbookImport, b: MasterWorkbookImport, add) -> None:
    ra, rb = a.management_reserve, b.management_reserve
    if ra is None and rb is not None:
        add("reserve", "setup", "added", "Management Reserve adjudication", "", "switched on")
    elif ra is not None and rb is None:
        add("reserve", "setup", "removed", "Management Reserve adjudication", "switched on", "")
    if ra is not None and rb is not None:
        for f in mrm.BLOCK_FIELDS:
            add("reserve", "block", f, "Management Reserve", ra.get(f, ""), rb.get(f, ""))
        ia, ib = {x["id"]: x for x in ra["items"]}, {x["id"]: x for x in rb["items"]}
        label = lambda x: f"Reserve {x['ref']} {x['title']}".strip()[:120]
        for xid, x in ia.items():
            if xid not in ib:
                add("reserve_item", xid, "removed", label(x), x["title"][:80], "")
            else:
                for f in mrm.ITEM_FIELDS:
                    add("reserve_item", xid, f, label(x), x[f], ib[xid][f])
        for xid, y in ib.items():
            if xid not in ia:
                add("reserve_item", xid, "added", label(y), "", y["title"][:80])


def _programme_changes(a: MasterWorkbookImport, b: MasterWorkbookImport, add) -> None:
    pa, pb = a.programme, b.programme
    if pa is None and pb is not None:
        add("programme", "setup", "added", "Programme set up", "", f"{len(pb['tasks'])} tasks")
    elif pa is not None and pb is None:
        add("programme", "setup", "removed", "Programme removed", f"{len(pa['tasks'])} tasks", "")
    if pa is not None and pb is not None:
        for f in ("start", "days_per_week", "hours_per_day"):
            add("programme", "config", f, "Programme " + f.replace("_", " "), pa[f], pb[f])
    ia = {x["id"]: x for x in (pa["tasks"] if pa else [])}
    ib = {x["id"]: x for x in (pb["tasks"] if pb else [])}
    if (pa is None) != (pb is None):
        return                                             # whole programme added or removed: reported once above
    label = lambda x: f"Programme task {x['code']} {x['name']}"[:120]
    for tid, x in ia.items():
        if tid not in ib:
            add("programme_task", tid, "removed", label(x), x["code"], "")
        else:
            y = ib[tid]
            for f in prg.FIELDS:
                add("programme_task", tid, f, label(x), ",".join(x[f]) if f == "predecessors" else x[f], ",".join(y[f]) if f == "predecessors" else y[f])
    for tid, y in ib.items():
        if tid not in ia:
            add("programme_task", tid, "added", label(y), "", y["code"])
