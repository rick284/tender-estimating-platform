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
CUSTOM_PREFIX = "CX"             # allowance lines added by the estimator on the Commercial page (CX01, CX02 ...): a % of base direct or a PC sum, before overhead and margin


def is_custom(ref: str) -> bool:
    return ref.startswith(CUSTOM_PREFIX)


def is_pre_margin(ref: str) -> bool:
    return ref in PRE_MARGIN_REFS or is_custom(ref)


def methods_for(ref: str) -> list[str]:
    """Bases a line may be switched between (empty = set by the platform)."""
    return ["%", "PC Sum"] if is_custom(ref) else COMMERCIAL_METHODS.get(ref, [])
# Which bases a commercial line may be switched between in the platform. Weather (CA10), management reserve (CA16) and GST are not listed: those are set on their own pages or are a % only.
COMMERCIAL_METHODS = {**{f"CA{n:02d}": ["%", "PC Sum"] for n in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 19, 20)},
                      "CA01": ["Risk Engine", "%", "PC Sum"], "CA02": ["Risk Engine", "%", "PC Sum"],     # a manual basis replaces what Risk Truth feeds; the screen warns when that leaves approved provisions out
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


def price_stack(cost: Decimal, by_ref: Mapping[str, CommercialInput]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """The one place overhead, profit, bonds and retention finance are applied to a cost base (the own-works subtotal, or the whole
    consolidated package). Returns (overhead, profit, bonds, retention_finance), honouring each line's include switch and basis:
    CA19/CA20 % of the base or a fixed sum; CA17 markup % of the base or a fixed amount; CA18 true margin %, markup % or a fixed amount
    (profit is charged on base + overhead + bonds + finance)."""
    cost = D(cost)

    def pct_or_pc(ref):
        c = by_ref.get(ref)
        if c is None or c.include != "Yes":
            return ZERO
        if c.method == "%":
            return cost * D(c.pct)
        if c.method == "PC Sum":
            return D(c.pc_sum)
        return ZERO

    bonds, ret_fin = pct_or_pc("CA19"), pct_or_pc("CA20")
    overhead = ZERO
    oh_in = by_ref.get("CA17")
    if oh_in and oh_in.include == "Yes":
        if oh_in.method == "Markup %":
            overhead = cost * D(oh_in.pct)
        elif oh_in.method == "Fixed Amount":
            overhead = D(oh_in.pc_sum)
    profit = ZERO
    pr_in = by_ref.get("CA18")
    if pr_in and pr_in.include == "Yes":
        cost_base = cost + overhead + bonds + ret_fin
        if pr_in.method == "Margin %":
            m = D(pr_in.pct)
            if m >= ONE:
                raise ValueError("Margin must be below 100%")
            profit = cost_base / (ONE - m) - cost_base
        elif pr_in.method == "Markup %":
            profit = cost_base * D(pr_in.pct)
        elif pr_in.method == "Fixed Amount":
            profit = D(pr_in.pc_sum)
    return overhead, profit, bonds, ret_fin


def package_sell_line(by_ref: Mapping[str, CommercialInput]) -> tuple[Decimal, Decimal]:
    """The commercial stack as a straight line: sell = a x cost + b, where b is the part that does not move with cost (fixed
    overhead, profit, bond or finance amounts, carried through the margin). Used to share a package's price between client schedule
    groups so the groups add up to the package exactly: group sell = a x group cost + b x (group cost / package cost)."""
    def sell(c):
        oh, pr, bo, rf = price_stack(c, by_ref)
        return c + oh + pr + bo + rf
    b = sell(ZERO)
    return sell(ONE) - b, b


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

    additions = {c.ref: _pre_margin_amount(c, base) for c in inputs if is_pre_margin(c.ref)}
    pre = sum(additions.values(), ZERO)
    subtotal = base + pre

    def get(ref):
        return by_ref.get(ref)

    overhead, profit, bonds, ret_fin = price_stack(subtotal, by_ref)

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
