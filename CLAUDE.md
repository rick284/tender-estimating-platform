# Tender Estimating Platform — handoff for Claude

Owner: Rick (non-technical; wants step-by-step walkthroughs, plain language, no unexplained jargon).
Purpose: a standalone, sellable (managed web subscription) tender-estimating platform for smaller NZ civil/commercial contractors. It recreates Rick's ChatGPT-built estimating system without depending on a chat session.

Read first: `docs/STANDARDS_TO_PLATFORM.md` (Rick's governing standards as requirements; OVERRIDES SPEC.md where they differ), then `docs/SPEC.md` and `docs/GOLDEN_TEST_HOBSONVILLE.md` (acceptance test numbers). Original standards: `docs/standards/`.

## Non-negotiable rules
1. **Arithmetic is deterministic code**, never the AI. The AI reads documents, drafts, flags and explains. Totals must reproduce the Hobsonville Rev34E workbook to the cent (golden test).
2. **Every quantity has provenance** (document, sheet, revision, page, method, status). A quantity without evidence cannot be locked.
3. **Estimator approves**: AI output is a proposal until Rick approves. Overrides are logged with a reason (feeds the learning loop).
4. **No double counting**: risk is routed once; subcontract quotes are overlays added once in the consolidated package.
5. **No on-screen measuring/markup tool (Rick decided: Bluebeam/Methvin quality is not achievable now; parked).** Build a READ-ONLY drawing viewer instead: click a quantity -> opens the referenced sheet/page with an overlay highlight of the source region (from imported markups or AI-suggested regions). Export annotated PDFs (standard PDF annotations) for use in Bluebeam/Acrobat, and import marked-up quantity CSVs back. AI measuring from drawings is "prove first, then decide"; if it fails after a couple of attempts, fall back to "estimator measures, platform checks and records". Do not loop on it.
6. Confidentiality: tender documents, mailbox and Xero data are sensitive. Read-only by default; never send/delete mail without explicit instruction. Privacy and data-ownership terms are required before any other customer uses it.
7. **Professional product quality (Rick, 11 Oct 2026):** the finished software must look and feel like professional commercial software, not a generic AI-generated app. Benchmark = the current Blackline Estimating build (repo rick284/blackline-estimating-standalone: React + shadcn/Tailwind, clean tables, responsive, PWA). Before building any screen: define a design system (tokens for colour/type/spacing/density, table and form patterns, empty/loading/error states, status chips for GREEN/AMBER/RED and lifecycle, print/PDF styles), review every screen with real data via Playwright screenshots at desktop and phone widths, and compare against Blackline. No placeholder lorem, no default-template look, no inconsistent spacing. Estimators work dense numeric tables all day: prioritise legibility, keyboard use and trustworthy numbers over decoration.
8. Rick's earlier lesson (Emergent build): scope creep and buggy bespoke UI wasted time. Keep each phase small, testable, and demonstrable.

## Related repo
`rick284/blackline-estimating-standalone` — separate product (Blackline Estimating PRO). Reusable patterns: FastAPI + MongoDB (motor), JWT multi-tenant orgs, React + shadcn/Tailwind, PWA, Netlify (frontend) + Render (backend) + Atlas. Stripe deliberately removed; billing deferred.

## Source material (Rick's Google Drive, folder "Dave Stewart"; Gmail is the 3bears Google account)
Hobsonville job Rev34E workbook (Drive id 1oIV0Z3yomrz6-GydmOPdiMsP7RnBNX8i), Master Estimate Workbook Rev4.1, NZ Weather Risk Estimating Tool Rev2.1, decision register, pre-response check protocol, supplier pricing evidence register, outputs 03/04/05/06. Not yet seen: Master Prompt, Triple Verification prompts, other estimating know-how documents — ask Rick for them.
Do NOT commit client/tender files into this repo without asking; the Rev34E values needed for tests live in `docs/GOLDEN_TEST_HOBSONVILLE.md`.

## Source status (updated 11 Oct 2026)
- Benchmark = Rev34E (confirmed). Drive search found NO files titled/containing "Master New Chat Starter", "Productivity and Crew Library" or a crew library — they probably live only in Rick's ChatGPT project files or under other names; ask Rick to export them. Decision Control Register (id 1uo-584QBu9705od8y2nwgFgPeURL9hO8) and Pre-Response Check Protocol (id 1KY3rZwqTIaJevxRJ-lF0ZhH28iDc5KwY) ARE on Drive (folder 1U-ebLzIftoPfpXwfaRTghjQDO4UibdJV) and were read.
- Other completed jobs on Drive usable as additional test cases later: Goodman Felix Street Civil Estimate (Rev0, Rev3, Rev4 report), Bridle Trail (Rev11/14, Master Rebuild Rev1), Orion Point stage 5 villas (Rev C-G). Hobsonville revs 24-34 show the revision history (good for revision/diff tests).
- IP model decided: see docs/STANDARDS_TO_PLATFORM.md section G. Rick's Construction Intelligence Register is NOT resold.

## Build status (updated 12 Oct 2026)
- Phase 0 done: `engine/` deterministic calculation engine, golden test vs Hobsonville Rev34E (to the cent) + unit tests.
- Phase 1a done: read-only estimate workbench (`web/`, `api/`), recalculates from an uploaded Master Estimate Workbook.
- Phase 1b (part 1) done: sign-in, company workspaces (tenant isolation tested), saved tenders + immutable revisions, Tenders list with pipeline KPIs, revision compare that explains movements. Deploy recipe in `docs/DEPLOY.md` (Atlas + Render + Netlify), not yet deployed.
- Real finding to remember: Hobsonville Rev34C -> Rev34E changed NO costs; the +$63,373.81 is entirely OH 8%->10% and margin 12%->15%.
- Not yet: editing/saving estimates in the app, weather tool port, Risk Truth recalculation, outputs (reports/price schedule), mailbox, review board, Knowledge Bank, Xero.
- Run tests: `cd engine && python -m pytest -q` and `cd api && python -m pytest -q` (private workbooks in `private/` enable the golden tests).

## DEPLOYED (12 Oct 2026) — first live run succeeded
- Website: https://tender-estimating-platform.netlify.app (Netlify, site builds from `web/`, env `VITE_API_URL`).
- API: https://tender-platform-api.onrender.com (Render free web service via `render.yaml`; Docker; sleeps after ~15 min idle).
- Database: Rick's Atlas free cluster "Cluster0" (project "Blackline", AP-Southeast-2), database `tender_platform`, user `tender_app` (readWrite on that DB only). Shares the 512 MB free quota with Blackline.
- Render env: ENV=production, MONGO_URL (secret), JWT_SECRET (generated), CORS_ORIGINS=https://tender-estimating-platform.netlify.app, BOOTSTRAP_EMAIL=Rick's email, REGISTRATION_OPEN=false.
- Rick's account exists (workspace "Three Bears Projects Ltd"); Hobsonville Rev34E imported in production. Original .xlsx files are NOT stored; revisions store computed results only (inputs are not yet stored — needed for in-app editing, so re-upload after that ships).
- Lesson: a wrong MONGO_URL password produced `bad auth` in Render logs while /api/health stayed 200 (startup is deliberately resilient). Check logs for "Could not create database indexes" after any DB change.
- Known open item: Rick has a Render email "Blueprint Sync Failed for blackline" (Blackline app, unrelated to this repo) not yet investigated.
