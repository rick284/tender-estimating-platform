from __future__ import annotations
from collections import Counter

from .models import BuildUpRow


def display_ids(rows: list[BuildUpRow]) -> list[str]:
    """Human row ids (EW01-001...), derived from position. They shift when rows are added or removed;
    BuildUpRow.uid is the permanent identity used by edits."""
    seq: Counter[str] = Counter()
    out = []
    for r in rows:
        seq[r.qs_code] += 1
        out.append(f"{r.qs_code}-{seq[r.qs_code]:03d}")
    return out
