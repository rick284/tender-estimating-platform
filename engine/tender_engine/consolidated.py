"""Consolidated Package: own works (pre-commercial, incl. Management Reserve) + subcontract
overlays added ONCE, less confirmed overlap; overhead and TRUE-MARGIN profit applied across
the whole package. Gross margin is measured on sell.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .commercial import price_stack
from .models import CommercialInput, Overlay
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
    bonds: Decimal = ZERO                 # bonds and retention finance carried by the package (zero when switched off)
    retention_finance: Decimal = ZERO


def _price(cost: Decimal, by_ref):
    oh, profit, bonds, fin = price_stack(cost, by_ref)
    sub = cost + oh + bonds + fin
    return oh, sub, profit, sub + profit


def compute_consolidated(own_works_precommercial: Decimal, overlays: Sequence[Overlay],
                         confirmed_overlap: Decimal, overhead_rate: Decimal | None = None,
                         margin: Decimal | None = None, *,
                         commercial: Sequence[CommercialInput] | None = None) -> ConsolidatedResult:
    """Prices the whole package. Pass `commercial` (the tender's commercial inputs) so the package carries exactly the overhead, profit,
    bond and finance choices (include switch and basis) the own-works tender uses: one authority, `commercial.price_stack`.
    The older rate-only form (overhead_rate, margin) means markup-% overhead and true-margin profit, both on."""
    if commercial is not None:
        by_ref = {c.ref: c for c in commercial}
    else:
        if margin is None or overhead_rate is None:
            raise ValueError("Give the commercial inputs, or an overhead rate and a margin.")
        if D(margin) >= ONE:
            raise ValueError("Margin must be below 100%")
        by_ref = {"CA17": CommercialInput("CA17", "Overhead", "Markup %", "Yes", D(overhead_rate), ZERO, ZERO),
                  "CA18": CommercialInput("CA18", "Profit", "Margin %", "Yes", D(margin), ZERO, ZERO)}
    own = D(own_works_precommercial)
    ov = sum((D(o.amount) for o in overlays), ZERO)
    gross = own + ov
    overlap = D(confirmed_overlap)
    after = gross - overlap
    oh, sub, profit, total = _price(gross, by_ref)
    _, _, _, total_after = _price(after, by_ref)
    _oh, _pr, bonds, fin = price_stack(gross, by_ref)
    gm = (total - gross) / total if total != 0 else ZERO
    return ConsolidatedResult(own, ov, gross, overlap, after, oh, sub, profit, total, gm, total_after, bonds, fin)
