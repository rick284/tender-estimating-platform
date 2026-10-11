from pathlib import Path
import pytest

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"


@pytest.fixture(scope="session")
def rev34e():
    if not PRIVATE.exists():
        pytest.skip("private/Rev34E.xlsx not present (client workbook is not stored in the repo)")
    from tender_engine.importers import load_master_workbook
    m = load_master_workbook(PRIVATE)
    keys = ["library", "qs", "rows", "excel_rows", "tool", "recovery", "commercial", "risk_feed",
            "overlays", "overlap", "cached", "weather_links"]
    return {k: getattr(m, k) for k in keys}
