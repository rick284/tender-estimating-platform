# tender-engine

Deterministic calculation engine for the tender estimating platform. No AI, no database, no I/O.
Reproduces the Master Estimate Workbook cost chain exactly (see `../docs/GOLDEN_TEST_HOBSONVILLE.md`).

    cd engine && pip install pytest openpyxl && python -m pytest -q

- `tests/test_engine_unit.py` — fast synthetic tests (always run).
- `tests/test_golden_hobsonville.py` — recomputes Hobsonville Rev34E from the workbook's inputs and
  compares every build-up row, QS item, section total, weather allowance, tender build-up and consolidated
  total to the cent. Needs `private/Rev34E.xlsx` (git-ignored, client confidential); skipped if absent.

Money uses `Decimal`; nothing is rounded during calculation (the workbook carries full precision and
displays 2dp), `cents()` is for presentation and reconciliation only.
