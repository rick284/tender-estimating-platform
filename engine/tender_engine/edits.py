"""Validated edits to estimate inputs. The ONLY way an in-app change reaches the numbers.

An edit is {"target", "key", "field", "value"}. Targets:
  row        key = build-up row id (e.g. EW01-001)   fields: productivity_rate, duration_override_hrs, count,
                                                      manual_qty, utilisation, waste, job_rate_override, verified, weather_exposed
  qs         key = QS code                            field : quantity
  commercial key = CA ref (e.g. CA09)                 fields: include, pct, pc_sum
  overlay    key = subcontract package name           field : amount
  setting    key = "weather"/"consolidated"           fields: recovery_allowance / confirmed_overlap

Edits are applied in order (last one wins per field); the returned change list is the NET difference between the
original and edited inputs, so reverting a value removes it from the list. Nothing is rounded.
"""
from __future__ import annotations
import copy
from collections import Counter
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Any

from .importers.master_workbook import MasterWorkbookImport
from .models import BuildUpRow, Overlay, QSItem
from .money import D

ROW_NUMERIC_NULLABLE = {"productivity_rate", "duration_override_hrs", "count", "manual_qty", "utilisation", "waste", "job_rate_override"}
ROW_YESNO = {"verified", "weather_exposed"}
MAX_EDITS = 500
MAX_VALUE = Decimal("1e12")


class EditError(ValueError):
    pass


def row_ids(rows: list[BuildUpRow]) -> list[str]:
    seq: Counter[str] = Counter()
    out = []
    for r in rows:
        seq[r.qs_code] += 1
        out.append(f"{r.qs_code}-{seq[r.qs_code]:03d}")
    return out


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


def apply_edits(base: MasterWorkbookImport, edits: list[dict[str, Any]]) -> tuple[MasterWorkbookImport, list[dict[str, Any]]]:
    if len(edits) > MAX_EDITS:
        raise EditError(f"Too many changes in one go (limit {MAX_EDITS}).")
    m = copy.copy(base)
    m.rows = list(base.rows)
    m.qs = list(base.qs)
    m.commercial = [dict(c) for c in base.commercial]
    m.overlays = list(base.overlays)
    ids = row_ids(m.rows)
    row_pos = {rid: i for i, rid in enumerate(ids)}
    qs_pos = {q.code: i for i, q in enumerate(m.qs)}
    com_pos = {c["ref"]: i for i, c in enumerate(m.commercial)}
    ov_pos = {o.name: i for i, o in enumerate(m.overlays)}

    for e in edits:
        if not isinstance(e, dict):
            raise EditError("Each change must be an object.")
        target, key, field, value = e.get("target"), e.get("key"), e.get("field"), e.get("value")
        if target == "row":
            if key not in row_pos:
                raise EditError(f"Unknown build-up row {key!r}.")
            what = f"{key} {field}"
            i = row_pos[key]
            if field in ROW_NUMERIC_NULLABLE:
                v = _num(value, what, nullable=True)
                if field in ("utilisation", "waste") and v is not None and v > 1:
                    raise EditError(f"{what} is a fraction between 0 and 1 (for example 0.1 for 10%).")
                if field == "productivity_rate" and v is not None and v == 0:
                    v = None
                m.rows[i] = replace(m.rows[i], **{field: v})
            elif field in ROW_YESNO:
                m.rows[i] = replace(m.rows[i], **{field: _yesno(value, what)})
            else:
                raise EditError(f"{field!r} can't be edited on a build-up row.")
        elif target == "qs":
            if key not in qs_pos:
                raise EditError(f"Unknown QS item {key!r}.")
            if field != "quantity":
                raise EditError("Only the quantity of a QS item can be edited.")
            i = qs_pos[key]
            m.qs[i] = replace(m.qs[i], quantity=_num(value, f"{key} quantity"))
        elif target == "commercial":
            if key not in com_pos:
                raise EditError(f"Unknown commercial line {key!r}.")
            c = m.commercial[com_pos[key]]
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
            if key not in ov_pos:
                raise EditError(f"Unknown subcontract package {key!r}.")
            if field != "amount":
                raise EditError("Only the amount of a subcontract package can be edited.")
            i = ov_pos[key]
            m.overlays[i] = Overlay(m.overlays[i].name, _num(value, f"{key} amount"), m.overlays[i].kind)
        elif target == "setting":
            if (key, field) == ("weather", "recovery_allowance"):
                m.recovery = _num(value, "Weather recovery allowance")
            elif (key, field) == ("consolidated", "confirmed_overlap"):
                m.overlap = _num(value, "Confirmed overlap")
            else:
                raise EditError("Unknown setting.")
        else:
            raise EditError(f"Unknown edit target {target!r}.")

    m.reference = None            # no longer the workbook as received
    return m, _net_changes(base, m, ids)


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        s = format(v.normalize(), "f")
        return s
    return str(v)


def _net_changes(a: MasterWorkbookImport, b: MasterWorkbookImport, ids: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def add(target, key, field, label, before, after):
        if before != after:
            out.append({"target": target, "key": key, "field": field, "label": label, "before": _fmt(before), "after": _fmt(after)})

    for rid, x, y in zip(ids, a.rows, b.rows):
        for f in sorted(ROW_NUMERIC_NULLABLE | ROW_YESNO):
            add("row", rid, f, f"{rid} {x.task}", getattr(x, f), getattr(y, f))
    for x, y in zip(a.qs, b.qs):
        add("qs", x.code, "quantity", f"{x.code} {x.description}", x.quantity, y.quantity)
    for x, y in zip(a.commercial, b.commercial):
        for f in ("include", "pct", "pc_sum"):
            add("commercial", x["ref"], f, f"{x['ref']} {x['name']}", x[f], y[f])
    for x, y in zip(a.overlays, b.overlays):
        add("overlay", x.name, "amount", x.name, x.amount, y.amount)
    add("setting", "weather", "recovery_allowance", "Weather recovery allowance", D(a.recovery), D(b.recovery))
    add("setting", "consolidated", "confirmed_overlap", "Confirmed Siteworks / Coast overlap", D(a.overlap), D(b.overlap))
    return out
