from pathlib import Path
import pytest

PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"


@pytest.fixture(scope="session")
def rev34e():
    if not PRIVATE.exists():
        pytest.skip("private/Rev34E.xlsx not present (client workbook is not stored in the repo)")
    from workbook_import import load_inputs
    return load_inputs(PRIVATE)
