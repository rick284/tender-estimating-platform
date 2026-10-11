"""Consolidated Package: own works (pre-commercial, incl. Management Reserve) + subcontract
overlays added ONCE, less confirmed overlap; overhead and TRUE-MARGIN profit applied across
the whole package. Gross margin is measured on sell.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .models import Overlay
from .money import D, ZERO, ONE


@dataclass(frozen=True)
class ConsolidatedResult:
    own_works: Decimal
    overlays_total: Decimal
    gross_known_package: Decimal          # own + overlays (before overlap)
    confirmed_overlap: Decimal
    known_after_overlap: Decimal
    overhead: Decimal
    subtotal_after_overhead: Decimal
    profit: Decimal
    all_in_tender: Decimal                # working all-in (gross package basis, as the workbook)
    gross_margin_on_sell: Decimal
    all_in_if_overlap_removed: Decimal


def _price(cost: Decimal, oh_rate: Decimal, margin: Decimal):
    oh = cost * oh_rate
    sub = cost + oh
    profit = sub / (ONE - margin) - sub
    return oh, sub, profit, sub + profit


def compute_consolidated(own_works_precommercial: Decimal, overlays: Sequence[Overlay],
                         confirmed_overlap: Decimal, overhead_rate: Decimal,
                         margin: Decimal) -> ConsolidatedResult:
    if D(margin) >= ONE:
        raise ValueError("Margin must be below 100%")
    own = D(own_works_precommercial)
    ov = sum((D(o.amount) for o in overlays), ZERO)
    gross = own + ov
    overlap = D(confirmed_overlap)
    after = gross - overlap
    oh, sub, profit, total = _price(gross, D(overhead_rate), D(margin))
    _, _, _, total_after = _price(after, D(overhead_rate), D(margin))
    gm = (total - gross) / total if total != 0 else ZERO
    return ConsolidatedResult(own, ov, gross, overlap, after, oh, sub, profit, total, gm, total_after)
