"""Tender Build-Up commercial layer (Commercial Inputs CA01..CA25).

Pre-margin additions (CA01..CA16), each only when Include? = Yes:
  Risk Engine / Weather Engine -> value delivered by that engine
  PC Sum / Fixed Amount        -> entered amount
  %                            -> base direct x %
Subtotal = base direct + pre-margin additions.
CA17 overhead  : Markup % -> subtotal x %  | Fixed Amount -> amount
CA18 profit    : Margin % -> (S+OH+CA19+CA20)/(1-m) - (S+OH+CA19+CA20)   [TRUE MARGIN]
                 Markup % -> base x %      | Fixed Amount -> amount
CA19 bonds, CA20 retention finance: % of subtotal | PC Sum
Tender total = subtotal + commercial adjustments. GST optional (CA21).
Retention (CA22..CA25) is cashflow visibility only.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from .models import CommercialInput
from .money import D, ZERO, ONE

PRE_MARGIN_REFS = tuple(f"CA{n:02d}" for n in range(1, 17))
# Which bases a commercial line may be switched between in the platform. Engine-fed lines (risk, weather, management reserve) and GST are not listed.
COMMERCIAL_METHODS = {**{f"CA{n:02d}": ["%", "PC Sum"] for n in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 19, 20)},
                      "CA17": ["Markup %", "Fixed Amount"], "CA18": ["Margin %", "Markup %", "Fixed Amount"]}


@dataclass(frozen=True)
class TenderResult:
    base_direct: Decimal
    additions: dict[str, Decimal]
    pre_margin_total: Decimal
    subtotal: Decimal
    overhead: Decimal
    profit: Decimal
    bonds: Decimal
    retention_finance: Decimal
    commercial_total: Decimal
    tender_excl_gst: Decimal
    gst: Decimal
    tender_incl_gst: Decimal
    retention_withheld: Decimal
    net_after_retention: Decimal


def _pre_margin_amount(ci: CommercialInput, base: Decimal) -> Decimal:
    if ci.include != "Yes":
        return ZERO
    m = ci.method
    if m in ("Risk Engine", "Weather Engine", "Management Reserve"):
        return D(ci.engine_value)
    if m in ("PC Sum", "Fixed Amount"):
        return D(ci.pc_sum)
    if m == "%":
        return base * D(ci.pct)
    return ZERO


def compute_tender(base_direct: Decimal, inputs: Sequence[CommercialInput]) -> TenderResult:
    by_ref: Mapping[str, CommercialInput] = {c.ref: c for c in inputs}
    base = D(base_direct)

    additions = {ref: _pre_margin_amount(by_ref[ref], base) for ref in PRE_MARGIN_REFS if ref in by_ref}
    pre = sum(additions.values(), ZERO)
    subtotal = base + pre

    def get(ref):
        return by_ref.get(ref)

    # CA19 / CA20 (on subtotal)
    def pct_or_pc(ref):
        c = get(ref)
        if c is None or c.include != "Yes":
            return ZERO
        if c.method == "%":
            return subtotal * D(c.pct)
        if c.method == "PC Sum":
            return D(c.pc_sum)
        return ZERO

    bonds = pct_or_pc("CA19")
    ret_fin = pct_or_pc("CA20")

    oh_in = get("CA17")
    overhead = ZERO
    if oh_in and oh_in.include == "Yes":
        if oh_in.method == "Markup %":
            overhead = subtotal * D(oh_in.pct)
        elif oh_in.method == "Fixed Amount":
            overhead = D(oh_in.pc_sum)

    pr_in = get("CA18")
    profit = ZERO
    if pr_in and pr_in.include == "Yes":
        cost_base = subtotal + overhead + bonds + ret_fin
        if pr_in.method == "Margin %":
            m = D(pr_in.pct)
            if m >= ONE:
                raise ValueError("Margin must be below 100%")
            profit = cost_base / (ONE - m) - cost_base
        elif pr_in.method == "Markup %":
            profit = cost_base * D(pr_in.pct)
        elif pr_in.method == "Fixed Amount":
            profit = D(pr_in.pc_sum)

    commercial = overhead + profit + bonds + ret_fin
    total = subtotal + commercial

    gst_in = get("CA21")
    gst = total * D(gst_in.pct) if gst_in and gst_in.include == "Yes" else ZERO

    # Retention: cashflow visibility only (CA22 rate, CA24 deposit offset, CA25 deposit-retention flag)
    ret_in, dep_in, dep_ret = get("CA22"), get("CA24"), get("CA25")
    retention = ZERO
    if ret_in and ret_in.include == "Yes":
        offset = D(dep_in.pct) if (dep_in and dep_in.include == "Yes" and not (dep_ret and dep_ret.include == "Yes")) else ZERO
        retention = total * D(ret_in.pct) * (ONE - offset)

    return TenderResult(
        base_direct=base, additions=additions, pre_margin_total=pre, subtotal=subtotal,
        overhead=overhead, profit=profit, bonds=bonds, retention_finance=ret_fin,
        commercial_total=commercial, tender_excl_gst=total, gst=gst, tender_incl_gst=total + gst,
        retention_withheld=retention, net_after_retention=total - retention,
    )
