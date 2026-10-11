from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 34
ZERO = Decimal(0)
ONE = Decimal(1)


def D(x) -> Decimal:
    """Convert to Decimal. Blank/None -> 0 (spreadsheet semantics). Floats use repr (shortest exact)."""
    if x is None or x == "":
        return ZERO
    if isinstance(x, Decimal):
        return x
    if isinstance(x, bool):
        raise TypeError("bool is not a number")
    if isinstance(x, float):
        return Decimal(repr(x))
    return Decimal(str(x))


def cents(x) -> Decimal:
    """Round to cents, half-up. Only for presentation/reconciliation; calculations stay unrounded
    exactly as the workbook does (it displays 2dp but carries full precision)."""
    return D(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
