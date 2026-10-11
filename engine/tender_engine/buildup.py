"""Resource Build-Up: per-row cost. Mirrors the workbook formulas exactly.

  calc duration hrs   = QS qty / productivity rate          (blank if no productivity)
  applied duration    = override if > 0 else calc duration
  applied rate        = job override if > 0 else library rate
  Time x Count        = applied hrs x count x (utilisation, blank=1) x applied rate
  QS Qty x Factor     = QS qty x count x (1 + waste) x applied rate
  Direct Qty          = manual qty x (1 + waste) x applied rate
  Lump Sum / Quote    = manual qty x applied rate
Blank numeric inputs behave as 0 (spreadsheet semantics) except utilisation (blank = 1).
"""
from __future__ import annotations
from collections import Counter
from decimal import Decimal
from typing import Iterable, Mapping, Sequence

from .models import (
    BuildUpRow, LibraryRate, QSItem, RowResult,
    MODE_TIME, MODE_QTY, MODE_DIRECT, MODE_LUMP,
)
from .money import D, ZERO, ONE


class BuildUpError(ValueError):
    pass


def _applied_duration(override, calc):
    o = D(override)
    if o > 0:
        return o
    return calc if calc is not None else ZERO


def row_cost(row: BuildUpRow, qs_qty: Decimal, applied_hrs: Decimal, applied_rate: Decimal) -> Decimal:
    waste = D(row.waste)
    if row.mode == MODE_TIME:
        util = ONE if row.utilisation is None else D(row.utilisation)
        return applied_hrs * D(row.count) * util * applied_rate
    if row.mode == MODE_QTY:
        return qs_qty * D(row.count) * (ONE + waste) * applied_rate
    if row.mode == MODE_DIRECT:
        return D(row.manual_qty) * (ONE + waste) * applied_rate
    if row.mode == MODE_LUMP:
        return D(row.manual_qty) * applied_rate
    return ZERO  # unknown mode: workbook returns 0 (QA flag below does not cover it; surfaced separately)


def compute_buildup(
    rows: Sequence[BuildUpRow],
    qs_items: Mapping[str, QSItem] | Iterable[QSItem],
    library: Mapping[str, LibraryRate] | Iterable[LibraryRate],
) -> list[RowResult]:
    qs = qs_items if isinstance(qs_items, Mapping) else {q.code: q for q in qs_items}
    lib = library if isinstance(library, Mapping) else {r.code: r for r in library}

    seq: Counter[str] = Counter()
    # Operator/fuel double-count checks look across rows of the same QS code.
    labour_operator = Counter()
    fuel_rows = Counter()
    for r in rows:
        desc = (lib[r.resource_code].description if r.resource_code in lib else "").lower()
        if r.resource_type == "Labour" and "operator" in desc:
            labour_operator[r.qs_code] += 1
        if "fuel" in desc:
            fuel_rows[r.qs_code] += 1

    out: list[RowResult] = []
    for r in rows:
        if not r.qs_code:
            continue
        if r.mode not in (MODE_TIME, MODE_QTY, MODE_DIRECT, MODE_LUMP):
            raise BuildUpError(f"Unknown calculation mode {r.mode!r} on {r.qs_code}")
        seq[r.qs_code] += 1
        row_id = f"{r.qs_code}-{seq[r.qs_code]:03d}"

        q = qs.get(r.qs_code)
        qty = q.quantity if q else ZERO
        lib_rec = lib.get(r.resource_code)
        lib_rate = lib_rec.base_rate if lib_rec else ZERO
        unit = lib_rec.unit if lib_rec else ""

        prod = D(r.productivity_rate)
        calc_hrs = (qty / prod) if prod != 0 else None
        applied_hrs = _applied_duration(r.duration_override_hrs, calc_hrs)
        override = D(r.job_rate_override)
        applied_rate = override if override > 0 else lib_rate
        cost = row_cost(r, qty, applied_hrs, applied_rate)

        exposed = cost if (r.weather_exposed == "Yes" and r.resource_type in ("Labour", "Plant")) else ZERO

        if r.resource_code == "" and r.mode != MODE_LUMP:
            flag = "RESOURCE CODE"
        elif applied_rate == 0:
            flag = "RATE MISSING"
        elif (r.resource_type == "Plant" and lib_rec and lib_rec.operator_included == "Yes"
              and labour_operator[r.qs_code] > 0):
            flag = "OPERATOR DOUBLE-COUNT"
        elif (r.resource_type != "" and lib_rec and lib_rec.fuel_included == "Yes"
              and r.resource_type == "Plant" and fuel_rows[r.qs_code] > 0):
            flag = "FUEL DOUBLE-COUNT"
        elif r.verified != "Yes":
            flag = "VERIFY"
        else:
            flag = "OK"

        out.append(RowResult(
            row_id=row_id, qs_code=r.qs_code, qs_qty=qty, calc_duration_hrs=calc_hrs,
            applied_duration_hrs=applied_hrs, library_rate=lib_rate, applied_rate=applied_rate,
            unit=unit, cost=cost, weather_exposed_cost=exposed, qa_flag=flag,
        ))
    return out
