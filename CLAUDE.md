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
7. Rick's earlier lesson (Emergent build): scope creep and buggy bespoke UI wasted time. Keep each phase small, testable, and demonstrable.

## Related repo
`rick284/blackline-estimating-standalone` — separate product (Blackline Estimating PRO). Reusable patterns: FastAPI + MongoDB (motor), JWT multi-tenant orgs, React + shadcn/Tailwind, PWA, Netlify (frontend) + Render (backend) + Atlas. Stripe deliberately removed; billing deferred.

## Source material (Rick's Google Drive, folder "Dave Stewart"; Gmail is the 3bears Google account)
Hobsonville job Rev34E workbook (Drive id 1oIV0Z3yomrz6-GydmOPdiMsP7RnBNX8i), Master Estimate Workbook Rev4.1, NZ Weather Risk Estimating Tool Rev2.1, decision register, pre-response check protocol, supplier pricing evidence register, outputs 03/04/05/06. Not yet seen: Master Prompt, Triple Verification prompts, other estimating know-how documents — ask Rick for them.
Do NOT commit client/tender files into this repo without asking; the Rev34E values needed for tests live in `docs/GOLDEN_TEST_HOBSONVILLE.md`.
