# Platform Specification v0.1

Status: draft for Rick's review. Derived from Master Estimate Workbook Rev4.1, Hobsonville Rev34E, NZ Weather Risk Tool Rev2.1, and Rick's descriptions.

## 1. Goal
Upload tender documents -> platform drafts the estimate using Rick's method -> sources quotes via mailbox -> estimator verifies and locks -> client outputs. After award, track actuals (Xero) against the locked baseline and feed variances back into the rate library. It must not depend on a chat session: methods, rules, rates and decisions are stored data.

## 2. Principles
- Deterministic calculation engine, unit-tested against the Hobsonville golden test. AI never computes totals.
- AI drafts/flags/explains; estimator approves. Every override logged with reason.
- Evidence everywhere: quantities, rates, quotes, assumptions all cite a source document and date.
- Versioned methods/rates/sources; each estimate records the versions used.
- Immutable locked revisions (snapshots); changes create a new revision with a diff.
- Model-agnostic AI layer (swap providers). Multi-tenant from day one (reuse Blackline's org model).

## 3. Core data model
Organisation, User, Project (Tender), Revision (snapshot), Document (file, type, rev, date, hash), SourceRef (document, sheet, page, region, status).
- **QSItem**: code (e.g. EW02), WBS section, description, unit, quantity, quantity basis (PROVIDED / MEASURED / CALCULATED / ASSUMED), SourceRefs, status/flag (GREEN/AMBER/RED), pricing method, owner, verification status, quote ref. Rate and amount are derived from build-up rows.
- **BuildUpRow**: QS code, methodology/work step, productivity (rate + unit), calc duration hrs, override hrs, applied hrs, calc mode, resource type (Labour/Plant/Material/Subcontract/Other), resource code, count/factor, manual qty, unit, utilisation %, waste %, library rate, job override rate, applied rate (= override if >0 else library), extended cost, library source, job quote ref, source date, operator included?, fuel included?, confidence, assumption/RFI, verified?, double-count check, weather exposed?, weather task type.
- **Calculation modes (exact):** 
  - Time x Count: applied hrs x count x (utilisation or 1) x applied rate
  - QS Qty x Factor: QS qty x count x (1+waste) x applied rate
  - Direct Qty: manual qty x (1+waste) x applied rate
  - Lump Sum / Quote: manual qty x applied rate
  - calc duration hrs = QS qty / productivity rate.
- **ResourceRate (library)**: code, category, description, cost type, unit, procurement mode, operator/fuel included, base rate, region, effective date, source type/supplier/URL, min/mobilisation, inclusions, exclusions, confidence, verification status. Job override never edits the library; library updates only via approved learning proposals.
- **Quote / SupplierQuoteRegister**: quote id, package, estimate ref, current qty, unit, current PC/control, required scope, documents issued, recipient, status, due, quote ref, received date, inclusions/exclusions, validity. Linked to Email threads and attachments.
- **CommercialInput (CA01–CA25)**: ref, name, method (Risk Engine / Weather Engine / % / PC Sum / Fixed Amount / Markup % / Margin %), value, include?, stage (pre-margin / commercial / tax / cashflow-only).
- **Risk, RFI, Decision, Assumption, RateVerification, ReviewBoardItem, Programme, WeatherRun, PriceScheduleMap, ActualCost, LearningProposal, AuditLog.**

## 4. Calculation rules (reproduce Rev34E)
- Section totals = sum of build-up extended cost by QS code; base direct = sum of sections.
- Pre-margin additions CA01–CA16 each included only if Include?=Yes. CA01/02 from Risk Truth residuals, CA10 from Weather Engine, CA16 fixed management reserve.
- Management Reserve = rate (4%) x reserve base (frozen pre-OH subtotal); frozen at lock, never auto-consumed.
- Subtotal = base direct + pre-margin additions.
- Overhead = subtotal x 10% (markup). Profit = TRUE MARGIN: (subtotal + OH + bonds + retention finance)/(1 - margin) - that base. Sell = cost/(1-margin) after overhead.
- GST optional display (15%); retention/deposit are cashflow-only.
- Consolidated package = own works (pre-commercial) + subcontract overlays (quoted, added once) - confirmed overlap; OH and margin applied across the whole consolidated cost.
- Allocation checks must reconcile to zero (e.g. Allied private allocation vs attachment total).
- Operator double-count check: plant row with operator included + a labour "operator" row for same QS code -> flag.
- Row QA flags: missing resource code, missing rate, operator double-count, others per Rev4.1.

## 5. Modules
1. **Document intake**: upload tender set; classify (drawings, spec, geotech, BOQ/price schedule, emails); record revision/date; document register; supersession tracking (e.g. Rev16 -> Rev17).
2. **Quantity provenance**: see section 6.
3. **Estimate engine**: QS takeoff, resource build-up, rate library, calc modes, QA flags.
4. **Rate verification**: per-row three-evidence test (primary/current, independent check, build-up/scope); score; status GREEN (3-point checked) / AMBER (company cost rate or quote required) / RED (live quote/design needed). RED items must be disclosed and resolved/excluded/accepted before award.
5. **Weather engine**: section 7.
6. **Risk Truth**: risk register with class (D/E missing/contradictory info etc.), baseline vs residual, each risk routed once to QS, CA01/CA02 or a specialist engine; duplicate-cost gate; programme dependency gate; recalculation check (tender total equals Risk Truth recalculation).
7. **Estimate Review Board**: primary estimate frozen -> independent blind reviews -> adjudication record -> decisions applied as new revision.
8. **Blind verification (triple verification)**: section 8.
9. **Supplier quote register + mailbox**: section 9.
10. **Decision control + pre-response check**: decision register with memory; before any email reply/RFI/quote chase is drafted, platform checks decisions, open RFIs and quotes to avoid contradicting earlier positions.
11. **Consolidated package + client price-schedule mapping**: map QS items to client schedule lines (e.g. TPW CW/001...) with exact reconciliation to the cent; handle splits where a trade covers two headings.
12. **Programme**: dry programme from build-up durations; weather-adjusted; export to MS Project (CSV import format).
13. **Outputs**: tender submission, client pricing schedule, basis-of-estimate report, scope/markup report, clarifications/exclusions, RFI register, quote comparison. Excel + PDF.
14. **Release gates**: Risk Truth gate, rate verification gate, duplicate-cost gate, programme gate, review-board gate, price-schedule reconciliation gate. Status: WORKING / TENDER-ISSUE / CONTRACT-AWARD HOLD / RELEASED.
15. **Revisions**: immutable snapshots, diff between revisions (what changed and why), restore as new revision.
16. **Learning loop**: section 10.
17. **Live job tracking + Xero**: section 11.

## 6. Quantity provenance and markup
- Each quantity: SourceRef(s) (document, sheet, revision, page), method (SCHEDULE/BOQ, VECTOR-PDF MEASURE, IMAGE MEASURE, CALCULATED, ASSUMED), confidence, verifier, date. ASSUMED stays red until confirmed. Cannot lock with unevidenced quantities.
- Scale rule: any measurement requires a confirmed scale/calibration from a known dimension on that sheet.
- **Outbound**: export annotated PDF with standard PDF annotations (highlighted runs/areas/counts, label "QS code - qty - unit - source") openable in Bluebeam/Acrobat. Each markup carries ID matching the platform register (cf. Rev34E "Source & Markup Register": SRC id, QS code, document, sheet/pages, revision, URL, markup file, status, quantities, notes).
- **Inbound**: import Bluebeam/other markup-summary CSV; match to QS items; flag differences vs AI proposal; accept/reject.
- No on-screen measuring/markup editor. Phase 1 = schedules/BOQs + references + export/import. Phase 2 = vector-PDF AI measurement trial against Hobsonville drawings with an accuracy report; continue only if accuracy is acceptable; otherwise stay with estimator-measures.

## 7. Weather engine
Replicates NZ Weather Risk Estimating Tool Rev2.1; NIWA 1991–2020 climate normals (CC BY 4.0; keep attribution); NZ public holidays (Employment NZ).
Inputs: station/location, start date, baseline working days, working days/week, weather-exposed labour+plant cost (rows tagged Weather Exposed=Yes with task type), daily time-related prelims (supervisor rate x 8h), weekly billed hire/facilities, shutdown/holiday calendar, recovery allowance (default 0), wind proxy (excluded by default).
Outputs: rain/wet-ground direct productivity cost; critical-path weather delay (WD; not summed across concurrent tasks); additional billed weeks; weather-adjusted duration; CA10 = productivity + delay x daily prelims + extra weeks x weekly hire + recovery (+ wind if included).
Rerun triggers: start date, baseline duration, exposed mix, calendar or critical path changes. Keep run records (tool version, station, start, baseline, exposed pool, outputs, confidence). Open item: obtain tool Rev2.1 task library and probability tables to port exactly.

## 8. Blind verification
At lock, build a blind pack: scope, quantities, productivities, conditions, crews, site constraints — no prices/totals. Send to N independent AI runs (ideally different models) with no access to the estimate; each returns its own build-up/price. Compare line-by-line and by section to the locked estimate; flag variances above configurable tolerance (e.g. 10% line, 3% section); estimator accepts flags or reopens. All results stored; separate from the Review Board; both can be lock gates. Prompts versioned (Rick to supply current Triple Verification prompts).

## 9. Mailbox and quotes
Read-only Gmail integration (OAuth; request narrowest scopes; note Google restricted-scope security assessment is required for public distribution — plan for it, or use a per-tenant read-only/forwarding approach first).
- Match threads to project (by project name, supplier, quote ref); extract quotes (supplier, scope, price, inclusions/exclusions, validity, date) as DRAFT register entries with link to message/attachment; estimator confirms.
- Flag contradictions between email body and attachment (e.g. Allied body total typo) and unpriced extras (CCTV, trench shields).
- Outbound: drafts only, never auto-send; pre-response check against decision register first.
- Full-correspondence archive per project saved for audit.

## 10. Learning loop
Capture: rate overrides, productivity changes, accepted/rejected AI flags, RFI answers, quote outcomes, review/blind-verification differences, actual cost variances. Each becomes a LearningProposal with evidence and a status (proposed / approved / rejected). Approved proposals update the rate library, productivity benchmarks, checklists or rules (versioned). AI context for future jobs is built from approved library only. No silent model training.

## 11. Live tracking and Xero
On award: freeze baseline revision; create job cost codes mapped to QS codes/WBS and to Xero tracking categories/accounts (design the mapping now). Xero API (OAuth2): pull bills, invoices, payroll/timesheets, tracking category actuals. Dashboard: budget vs actual vs forecast per QS item and section, labour hours vs allowance, plant, materials, subcontract; light/heavy flags; missed items; margin to date; variance reasons recorded. Closeout feeds productivity and rate evidence into the learning loop. Also stage cashflow (retention, deposit, payment timing) as in the Rev34E Stage Cashflow tab.

## 12. Architecture (proposed, reuse Blackline stack)
React + shadcn/Tailwind frontend (Netlify); FastAPI backend (Render, paid tier needed for background jobs); MongoDB Atlas for documents/metadata; object storage (S3-compatible/R2) for tender files; a calculation package with its own unit tests; background worker for document parsing, email sync and AI jobs; provider-agnostic AI client. PDF/XLSX parsing, annotated-PDF export libraries to be selected in phase 1.

## 13. Phases
0. Foundations: repo, CI, calculation engine core + golden test for the cost chain (Rev34E totals) from JSON inputs. 
1. Estimate workbench: QS/build-up/rate library CRUD, import Rev34E workbook, reproduce totals in UI, QA flags, revisions.
2. Commercial layer, consolidated package, price-schedule mapping, outputs (Excel/PDF).
3. Weather engine port + Risk Truth + release gates.
4. Document intake + quantity provenance + annotated PDF export/CSV import.
5. Mailbox + quote register + decision control.
6. Review Board + blind verification.
7. AI-drafted estimates from tender docs (schedules/BOQ first), measuring trial.
8. Live tracking, Xero sync, learning loop dashboards.
9. Commercial readiness: multi-tenant, security review, billing (Stripe), terms/privacy, backups.

## 14. Risks and open questions
- AI quantities from drawings: accuracy unproven; staged as in section 6.
- Calculation fidelity: workbook has 5,349 build-up formulas; port and test row-by-row.
- Licensing: published rate sources (supplier price books, NZ Machine Hire etc.) may not be redistributable; customers should use their own rates; ship method + empty/placeholder library.
- Gmail restricted scopes and Xero app approval take time.
- Confidential tender documents: storage, retention, tenant isolation, deletion.
- Data ownership/terms with customers; AI provider data-use terms.
- Rick's IP: Master Prompt and Triple Verification prompts not yet seen.
- Which Rev is the benchmark (34E assumed). Rev34C was uploaded earlier; 34E on Drive.
- Need from Rick: Master Prompt, Triple Verification prompts, other resource docs, weather tool Rev2.1 internals (already supplied as xlsx — port next), permission to hold a private copy of Rev34E for line-level tests.
