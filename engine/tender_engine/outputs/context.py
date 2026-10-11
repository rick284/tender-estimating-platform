from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class OutputContext:
    company: str = ""            # the contractor issuing the documents
    prepared_by: str = ""
    project: str = ""
    client: str = ""
    location: str = ""
    revision: str = ""
    issue_date: str = ""         # as it should read on the document, e.g. "12 September 2026"


def money(v: float | None, dash: str | None = None) -> str:
    """$1,234.56. Zero reads $0.00 unless a `dash` (e.g. "" or "-") is given for empty cells."""
    if v is None or abs(v) < 0.005:
        return "$0.00" if dash is None and v is not None else (dash or "")
    return f"${v:,.2f}" if v >= 0 else f"-${abs(v):,.2f}"


def pct(v: float | None, dp: int = 2) -> str:
    return "" if v is None else f"{v * 100:.{dp}f}%"
