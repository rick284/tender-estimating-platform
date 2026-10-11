# Tender Estimating Platform

Standalone tender-estimating platform (working title). See `CLAUDE.md` for the project rules and
`docs/` for the specification, standards and golden test.

| Folder | What it is |
|---|---|
| `engine/` | Deterministic calculation engine (Python, no AI). Golden-tested against Hobsonville Rev34E. |
| `api/` | FastAPI service: upload a Master Estimate Workbook, get the recalculated estimate. |
| `web/` | React + Tailwind web app (Blackline design language). Phase 1a: read-only workbench. |
| `docs/` | Specification, governing standards, golden-test numbers. |
| `private/` | Git-ignored. Client workbooks used for local testing only. |

## Run locally

    # tests
    cd engine && pip install pytest openpyxl && python -m pytest -q
    cd ../api && pip install -r requirements.txt httpx && python -m pytest -q

    # API (optional DEMO_WORKBOOK enables the "Open the demo workbook" button; development only)
    cd api && DEMO_WORKBOOK=../private/Rev34E.xlsx uvicorn app:app --port 8000

    # web (proxies /api to :8000)
    cd web && npm install && npm run dev        # http://localhost:5173
    npm run build                               # type-check + production build

## Phase 1a status
Import a workbook -> every figure recalculated by the engine -> Overview, Consolidated Package, Tender Build-Up,
QS Takeoff, Resource Build-Up, Weather Risk, Rate Library, plus a "reconciled to workbook" check.
Not yet: editing, saving, users/tenants, the weather tool port, Risk Truth, outputs. See `docs/SPEC.md` phases.
