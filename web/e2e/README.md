# End-to-end checks (run by hand, need Playwright + the private workbooks)

These drive the real interface in a browser against a local dev stack. They are not part of CI because they need
client workbooks in `private/` and a running server.

    # terminal 1: API with an in-memory database          terminal 2: web
    cd api && USE_MOCK_DB=true uvicorn app:app --port 8000      cd web && npx vite --port 5173
    pip install playwright && playwright install chromium       # or point executable_path at an installed Chromium

    python web/e2e/seed_real.py        # fresh API only: creates the account and uploads Rev34C + Rev34E
    python web/e2e/flicker.py          # menu switching must make 0 requests and never blank the page (2.5 s latency)
    python web/e2e/edit_e2e.py         # edit qty/rate/overhead, check live total == engine, save with a reason

Paths inside the scripts point at `/opt/pw-browsers/...` and `/home/user/...`; adjust for your machine.
