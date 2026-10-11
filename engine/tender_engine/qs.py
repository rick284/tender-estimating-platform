"""QS Takeoff: item amount = sum of build-up cost for its code; rate = amount / qty.
Total direct cost = sum of coded items. Section totals group by WBS section."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Sequence

from .models import QSItem, RowResult
from .money import D, ZERO


@dataclass(frozen=True)
class QSLine:
    code: str
    section: str
    description: str
    unit: str
    quantity: Decimal
    amount: Decimal
    rate: Decimal


@dataclass(frozen=True)
class QSResult:
    lines: list[QSLine]
    section_totals: dict[str, Decimal]
    total_direct: Decimal
    orphan_cost: Decimal      # build-up cost whose QS code is not in the takeoff (must be 0)


def compute_qs(items: Sequence[QSItem], rows: Iterable[RowResult]) -> QSResult:
    by_code: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for r in rows:
        by_code[r.qs_code] += r.cost
    lines: list[QSLine] = []
    sections: dict[str, Decimal] = defaultdict(lambda: ZERO)
    known = set()
    for it in items:
        known.add(it.code)
        amt = by_code.get(it.code, ZERO)
        rate = (amt / it.quantity) if it.quantity != 0 else ZERO
        lines.append(QSLine(it.code, it.section, it.description, it.unit, it.quantity, amt, rate))
        sections[it.section] += amt
    orphan = sum((v for k, v in by_code.items() if k not in known), ZERO)
    return QSResult(lines, dict(sections), sum((l.amount for l in lines), ZERO), orphan)
