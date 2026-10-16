# Workbook Builder Instructions — Blackline QSi Pro

**Version:** Rev1 (14 Oct 2026) · **Owner:** Rick (3Bears Projects) · **Status:** living document — see section 14 for how it is improved.

---

## 0. Read this first

You are an external AI assistant. Rick will give you:

1. the **Master Estimate Workbook** (an `.xlsx` template, normally the latest issued job workbook with its job data cleared, or a blank master),
2. **this document**, and
3. the **tender documents** for one job (plans, specs, schedules, addenda, geotech, emails, supplier quotes, notes).

Your job is to produce **one completed Master Estimate Workbook** (`.xlsx`) for that job, in exactly the layout the Blackline QSi Pro app can import, plus a short **handover note**. The app then loads the workbook, recalculates every figure itself and lets Rick review, edit and issue the estimate.

You are **drafting for an experienced estimator.** Rick approves. You never make a commercial decision for him. Everything you cannot prove from the documents is flagged, not guessed.

If any instruction here conflicts with what you were told in the chat, stop and ask Rick which applies. If this document is silent on something, follow the principle in section 1 and write the question down in the handover note.

---

## 1. Non-negotiable rules

These come from Rick's governing standards (Master Prompt Rev5, Triple Verification Standard Rev4, Conclusion & Change Control Rev1, Management Reserve policy Rev1). They override anything else.

1. **No invented numbers.** Every quantity, rate, price, duration and date must come from a document, a supplier quote, the rate library, or a stated calculation. If something is missing, **do not guess**: leave the number blank (or the quantity at 0), mark the row RED, and write an RFI with its decision impact (section 9).
2. **Arithmetic belongs in the workbook's formulas, not in your head.** Type *inputs* (quantities, productivities, rates, counts, percentages). Leave the template's *calculated* columns as formulas. Never overwrite a formula with a typed total.
3. **Every quantity has provenance.** Each QS line records its source (document, sheet/drawing number, revision, page), how it was obtained (status, section 5.3) and a verification colour. A quantity without evidence cannot be GREEN.
4. **One cost chain, no double counting.**
   Resource Rate Library → Resource Build-Up → QS Takeoff → Tender Build-Up → Summary.
   A cost appears once. Risk is routed once (Risk Truth). Weather is its own engine (CA10) — never also add weather inside the build-up rates. Subcontract quotes are overlays added once in the Consolidated Package, never also inside own-works rows.
5. **A quote is evidence, not automatically the controlling amount.** Record quotes, compare them, and state which amount the estimate uses and why.
6. **Verification colours.** GREEN needs three checks: (1) current primary evidence, (2) an independent check, (3) a first-principles reasonableness check. Anything less is AMBER. Anything missing, conflicting or unsupported is RED. **Never mark GREEN on your own authority**; propose it and say what evidence supports it.
7. **Conflicts are RFIs.** If two documents disagree (for example drawing revisions), put both values in the RFI, price the *governing* one only if the documents state which governs, otherwise price the higher-risk reading as an AMBER/RED line and say so. Never silently pick one.
8. **Supersede, never delete.** Library rates, quantities and documents keep their history (source, date, status). Superseded items are marked, not removed.
9. **Confidentiality.** Tender documents, emails and supplier prices are confidential. Work only with what Rick gives you. Do not send, post, forward or reply to anything. Do not copy personal data (phone numbers, home addresses) into the workbook beyond what a log needs. Never put the workbook or its contents on a public site.
10. **No job- or company-specific wording in the structure.** Headings, labels and sheet names stay generic (they are shared across jobs and customers). Job details go in *data cells* only.

---

## 2. What you deliver

1. `<JobName>_Master_Estimate_Rev<NN>.xlsx` — the completed workbook (section 3 onwards).
2. `<JobName>_Handover_Rev<NN>.md` — one page (template in section 12): what is complete, what is RED/AMBER, open RFIs, quotes still needed, assumptions you made, anything in this document that didn't work.

Do not deliver anything else unless Rick asks.

**Revision naming.** Follow the revision Rick gives you (for example `Rev0`, `Rev1`). On a re-run, copy the previous workbook, keep its history, and record what changed in the **Change Log** sheet (section 8.7).

---

## 3. How to work with the template (how the app reads your workbook)

The app reads **cell values by position**, so the layout is a contract.

**Do**
- Start from the template Rick supplied. Keep every sheet name, every header row, every column position and every formula exactly as they are.
- Add rows by **copying a complete existing row** (so its formulas come with it) and inserting it inside the existing block.
- Put **numbers in number cells** as true numbers (`1250.5`, not `"$1,250.50"`, not `"approx 1250"`). Percentages as decimals or % formatted cells (`0.1` or `10%`).
- Use one code per item, no spaces: letters + digits (`EW01`, `PG01`, `SW-12`).
- After editing, **recalculate and save** so formulas hold calculated values (LibreOffice headless: `soffice --headless --convert-to xlsx --outdir out file.xlsx` works; or open and save in Excel). The app uses those saved values for display and reconciliation.
- Keep text in cells short and plain (under about 300 characters); longer evidence goes in the log sheets.

**Don't**
- Don't rename, delete, hide or reorder the required sheets or their columns.
- Don't put words in a number cell (`TBC`, `n/a`, `?`). Leave it empty and flag the row. The app refuses a workbook whose number cell holds words and tells Rick the sheet, row and text.
- Don't merge cells in data tables. Don't add blank spacer rows inside a table.
- Don't type totals over formulas. Don't use macros, external links, pivot tables or images.
- Don't put job names, client names or places into headings or labels (data cells only).

**Sheets and what they are for** (the first four are essential; the app refuses a workbook without them)

| Sheet | Needed by app? | Purpose |
|---|---|---|
| Resource Rate Library | **Essential** | Every rate the estimate can use |
| QS Takeoff | **Essential** | Scope items with quantities and provenance |
| Resource Build-Up | **Essential** | How each QS item is built: labour, plant, materials, subcontract |
| Commercial Inputs | **Essential** | Allowances, overhead, margin, GST controls |
| Cover & Instructions | Optional (strongly wanted) | Job details, document register, assumptions, exclusions, RFIs |
| Tender Build-Up | Optional (strongly wanted) | The commercial stack; lets the app prove its totals match the workbook's |
| Consolidated Package | Optional | Own works + subcontract packages = all-in price |
| Weather Risk | Optional | Project weather inputs and tool-run record |
| Risk Truth | Optional | Risk register and exposures; the controlling risk layer |
| Supplier Quote Register | Optional | Quotes to obtain / received |
| Programme Export | Optional | Task durations and predecessor logic |
| Rate Verification | Optional | Rate evidence counts |
| Source & Markup Register | Optional | Source drawings and markups |
| **Email Log, RFI Log, Quote Log, Document Register, Decision Log, Change Log, Contacts** | New (section 8) | Full record of the job's communications and decisions |

A missing optional sheet is not an error, but the app then has less to show Rick. **Complete every sheet that applies to the job.**

---

## 4. Process — in this order

### Step 1 — Intake (before any pricing)
Fill the **Intake** block on *Cover & Instructions* (or the Intake sheet if the template has one) from Rick's message and the documents. These are Rick's 20 intake fields:

1 Job name · 2 Location · 3 Client / head contractor · 4 Job type · 5 Work package required · 6 Estimate purpose · 7 Estimate level (Concept / Feasibility / Tender / Variation) · 8 Pricing basis (own rates / allowances only / mix) · 9 Contract type · 10 What "done" looks like · 11 Programme constraints · 12 Site constraints · 13 Scope boundaries known · 14 Documents provided · 15 Missing documents suspected · 16 Key assumptions to lock early · 17 Known risks / red flags · 18 Interfaces to confirm · 19 Inclusions wording style · 20 Top three unknowns.

If a field is not in Rick's message or the documents, write `NOT PROVIDED` and add it to the RFI Log as a question to Rick. Do not fill it with a plausible guess.

### Step 2 — Document register
List every document you were given on **Document Register** (section 8.4): title, reference/drawing number, revision, date, status (CURRENT / SUPERSEDED / UNCLEAR), where it came from (file name or Email ID). Decide which revision is current only from the documents themselves (revision tables, dates, addenda). If two revisions conflict and nothing says which governs, raise an RFI.

### Step 3 — Scope and exclusions
Write the scope as the documents define it. Record **assumptions**, **exclusions**, **interfaces / by others** and **inclusions** on *Cover & Instructions* (section 6). Each assumption carries a reference (`A1`, `A2` …), each exclusion `EX-01` …

### Step 4 — Quantities (QS Takeoff)
One row per priced item. Take quantities from the documents. Read printed dimensions and schedules; **do not scale off drawings unless you state the scale and mark the line `CALCULATED` / AMBER**. Show your arithmetic in the *Quantity Basis* column (for example `2 × 14.5 m × 3.2 m`). Where documents conflict, create separate lines or an RFI — never average.

### Step 5 — Build-Up
For **every** active QS code create one or more Resource Build-Up rows that explain how it is built and priced (section 5.2). The QS rate and amount come from the build-up through the template's formulas. A QS line with a quantity and no build-up row is a defect.

### Step 6 — Rates
Use rates from the **Resource Rate Library** first. Add a new library rate only with a **source, date, supplier/source name and verification status** (section 5.1). Supplier quotes (Quote Log) are a source; a market benchmark is AMBER until firmed.

### Step 7 — Subcontract and supplier quotes
Record every quote on the **Quote Log** and **Supplier Quote Register**. Subcontract packages go on **Consolidated Package** as separate lines (section 5.6). If a quote is not received yet, put a placeholder PC amount marked `ALLOWANCE-PC`, AMBER or RED, and record "quote required" on the Quote Log.

### Step 8 — Commercial
Set the allowances on *Commercial Inputs* (section 5.4). Overhead and profit are separate inputs. Do not apply a default contingency percentage.

### Step 9 — Risk and weather
Complete *Risk Truth* (section 5.7) and *Weather Risk* project inputs (section 5.8). Weather and risk are computed by their own engines; you supply inputs and evidence.

### Step 10 — Programme
Fill *Programme Export* (section 5.9): durations come from build-up hours, not guesses; predecessors are task codes.

### Step 11 — Logs
Complete the **Email Log, RFI Log, Quote Log, Decision Log, Change Log, Contacts** (section 8) from the emails and documents Rick provided.

### Step 12 — Self-check, then deliver
Run the checklist in section 11. Fix what you can. Report what you cannot in the handover note.

---

## 5. Sheet specifications (the contract with the app)

Row numbers below match the current template. If Rick's template differs, tell him; do not change the layout yourself.

### 5.1 Resource Rate Library
Header on **row 4**; rates from **row 5** down.

| Col | Header | Rule |
|---|---|---|
| A | Resource Code | Unique, no spaces. Prefix by type: `LAB-`, `PL-`, `MAT-`, `SUB-`, `OTH-` |
| B | Resource Category | Labour / Plant / Material / Subcontract / Other |
| C | Resource Description | Specific: size, grade, hire basis |
| D | Default Cost Type | Same list as B |
| E | Unit | `hr`, `day`, `week`, `m`, `m2`, `m3`, `t`, `ea`, `LS` … |
| F | Procurement Mode | Hire / Purchase / Internal / Subcontract |
| G | Operator Included? | Yes / No / N/A |
| H | Fuel Included? | Yes / No / N/A |
| **I** | **Base Rate excl. GST** | **Number.** Read by the app |
| J | Region / Market | e.g. `Auckland / NZ` |
| K | Effective Date | Date the rate applies from |
| L | Source Type | Supplier quote / Published price list / Company actual / Market benchmark |
| M | Supplier / Source | Who or what |
| N | Source URL / Quote Ref | Link, Email ID or Quote ID |
| O–Q | Minimum / inclusions / exclusions | Short text |
| R | Confidence | High / Medium / Low |
| S | Verification Status | `GREEN`, `AMBER - reason`, or `RED - reason` |
| T | Notes | |

Rules: **labour rates are true direct cost per productive hour** (wage + employer on-costs + recovered paid non-productive time — see the Management Reserve & Labour True-Cost policy). Do not add margin, overhead or contingency to a library rate. GST is excluded everywhere.

### 5.2 Resource Build-Up
Header on **row 6**; rows from **row 7** down. Columns the app **reads as inputs** are in bold. Everything else is formula or description.

| Col | Header | Rule |
|---|---|---|
| A | Build-Up Row ID | `<QS code>-001`, `-002` … unique |
| **B** | **QS Code** | Must exist on QS Takeoff |
| C | WBS / Section | |
| D | Task Description | |
| E | QS Qty | *Formula* (lookup from QS Takeoff) — do not type |
| F | QS Unit | *Formula* |
| G | Estimate Class | Colour + short reason |
| **H** | **Methodology / Work Step** | One plain sentence: what this row is |
| **I** | **Productivity Rate** | Number: output per hour (unit in J) |
| J | Productivity Unit | e.g. `m3/hr` |
| K | Calc Duration hrs | *Formula* `= QS qty / productivity` |
| **L** | **Duration Override hrs** | Number, only where evidence justifies; otherwise empty |
| M | Applied Duration hrs | *Formula* (override if >0, else K) |
| **N** | **Calculation Mode** | Exactly one of: `Time x Count`, `QS Qty x Factor`, `Direct Qty`, `Lump Sum / Quote` |
| **O** | **Resource Type** | `Labour`, `Plant`, `Material`, `Subcontract`, `Other` |
| **P** | **Resource Code** | Must exist in the library (or a Lump Sum row with no library code) |
| Q | Resource Description | |
| **R** | **Resource Count / Factor** | Number |
| **S** | **Manual Resource Qty** | Number (used by `Direct Qty` and `Lump Sum / Quote`) |
| T | Resource Unit | |
| **U** | **Utilisation %** | Decimal, blank = 100% |
| **V** | **Waste %** | Decimal, blank = 0 |
| W | Library Rate | *Formula* (lookup) |
| **X** | **Job Rate Override** | Number, only with a quote/evidence in AB |
| Y | Applied Rate | *Formula* (override if >0, else library) |
| Z | Extended Cost | *Formula* — see modes below |
| AA | Library Source | |
| AB | Job Quote / Source Ref | Quote ID, Email ID, document + page |
| AC | Source Date | |
| AD / AE | Operator / Fuel included? | Yes / No / N/A |
| AF | Confidence | colour + reason |
| AG | Assumption / RFI | Reference `A#` or `RFI-##` where relevant |
| **AH** | **Verified?** | `Yes` / `No` (Yes only when the evidence supports GREEN) |
| AI | QA / Double-Count Check | `OK`, `VERIFY`, or explanation of what was removed |
| AJ | Notes | |
| **AK** | **Weather Exposed?** | `Yes` for weather-sensitive labour/plant on outdoor works; else `No` |
| **AL** | **Weather Task Type** | The weather tool's task type (Earthworks, Concrete, Bored piles / drilled holes, Erosion & sediment controls …) or `None` |
| AM / AN… | Weather basis / exposed amounts | Formulas — do not type |

**How Extended Cost (Z) is calculated, by mode** (so you pick the right mode):
- `Time x Count` = applied hours × count × utilisation × applied rate. Use for crews and plant working for a duration.
- `QS Qty x Factor` = QS quantity × factor × (1 + waste) × rate. Use for materials sold per unit of the scope item.
- `Direct Qty` = manual quantity × (1 + waste) × rate. Use for materials/hire counted directly.
- `Lump Sum / Quote` = manual quantity × rate (usually quantity 1 and the quoted price as the rate). Use for quoted packages and allowances.

Rules: one row per resource (a crew = one row per labour type, one for each plant item). Include operators with plant only when the library rate says *Operator Included = Yes* (otherwise add the operator as labour). Never include the same cost on two rows (QA column AI records the check). Preliminaries and general are itemised here too (not as a bare lump sum).

### 5.3 QS Takeoff
Header on **row 2**; items from **row 3**.

| Col | Header | Rule |
|---|---|---|
| A | Civil Scope / WBS | Section name (repeat on each row) |
| **B** | **Code** | Unique item code |
| C | Description | What is being priced |
| **D** | **Unit** | `m`, `m2`, `m3`, `t`, `ea`, `LS`, `hr`, `week` … |
| **E** | **Quantity** | **Number** (a constant) |
| F | Rate excl. GST | *Formula* (amount ÷ quantity) |
| G | Amount excl. GST | *Formula* (sum of build-up cost for this code) |
| H | Quantity Basis | The arithmetic or the schedule/dimension used |
| I | Source drawing / scope | Document, sheet number, **revision**, page |
| J | Status | One of `MEASURED`, `PROVIDED`, `CALCULATED`, `ALLOWANCE-PC`, `QUOTED` — then ` - GREEN/AMBER/RED` and a short reason |
| K | Notes / Assumptions | |
| L–O | Pricing method, basis, source type, URLs | Descriptive |
| P | Pricing Flag | `GREEN`, `AMBER`, `RED` |
| Q | Confidence / Firm-up Action | What would raise confidence |
| R | Owner | |
| S | Verification Status | |
| T | Quote / Reference | Quote ID or Email ID |

Status meanings: **MEASURED** you measured it (state method: vector PDF, scaled with stated scale, count) · **PROVIDED** the documents give the number · **CALCULATED** derived from other numbers (show formula) · **ALLOWANCE-PC** an allowance or provisional sum, no measured basis · **QUOTED** supplied by a quote.

### 5.4 Commercial Inputs
Header **row 4**; lines `CA01` … `CA24` from **row 5**. Do not add or delete rows. Set only:

| Col | Rule |
|---|---|
| C Input method | Allowed values per line (below) |
| D Input % | Decimal when method is a percentage |
| E PC Sum excl. GST | Number when method is PC Sum / Fixed Amount |
| F Include? | `Yes` / `No` |
| I / J | Notes and firm-up action: say *why* the line is on or off |

Allowed methods: **CA03–CA09, CA11–CA15, CA19, CA20:** `%` or `PC Sum` · **CA16 Management Reserve:** `Fixed Amount` (see below) · **CA17 overhead:** `Markup %` or `Fixed Amount` · **CA18 profit:** `Margin %`, `Markup %` or `Fixed Amount` · **CA01/CA02:** `Risk Engine` (fed from Risk Truth; leave) · **CA10:** `Weather Engine` (fed from the weather tool; leave) · **CA21 GST:** `%`.

Rules:
- **Overhead and profit are separate inputs.** Margin, markup, contingency and risk are never interchangeable. Use the percentages Rick gives you; do not choose them.
- **CA16 Management Reserve is not a percentage** and has no default. Leave it off (`No`, 0) unless Rick instructs an amount. If unresolved items exist, list them (section 5.7) so Rick can adjudicate.
- A PC Sum line must name what it covers in column I and must not duplicate anything already in the build-up or in Risk Truth.

### 5.5 Cover & Instructions
Keep the template's layout. The app reads:

- **Job details** (label in one cell, value in the next cell to its right): `Project`, `Location`, `Current drawings`, `Issue date`, `Scope`, `GST`, `Programme`, `Weather`, `Price status`, `Commercial`.
- **DRAWING / DOCUMENT REGISTER** section: one row per document — A title, B reference/revision, C detail.
- **ASSUMPTIONS / QUALIFICATIONS / RFIs** section: assumptions `A1`, `A2` … and exclusions `EX-01`, `EX-02` … — A reference, B the full wording.
- **PRICING QUALIFICATIONS / RFIs** section: `RFI-01`, `RFI-02` … — A reference, B text that **begins** with the status in capitals: `OPEN RED`, `OPEN`, or `CLOSED`, then the RFI (what is missing, where expected, why it matters, decision impact).
- **KEY RISKS / WATCHOUTS**: `RT01` … (the Risk Truth sheet controls; keep these consistent with it).

The RFI Log (section 8.2) is the master; generate these Cover rows from it so the two cannot disagree.

### 5.6 Consolidated Package
Rows from **row 5**: A label · B amount excl. GST (number) · C classification · D "Included in own-works direct?" · E status · F release.

- Row 5: own-works pre-commercial package — D `Yes`.
- **One row per subcontract package**: amount as a number, D = `No`, C = `QUOTED`, `QUOTED BASE`, `CONFIRMED ADDITIONAL` or `ALLOCATED`. Never `CALCULATED` for a package (calculated rows are totals and are ignored).
- A row whose label contains the word **overlap** records a confirmed overlap between own works and a package (a positive number is deducted once).
- The totals rows (label starts `Gross` …) are formulas; leave them.
- A package with no price yet: record it on the Quote Log and leave a placeholder row with amount 0 and classification `UNPRICED` so it is visible, not forgotten.

### 5.7 Risk Truth
Risk register (risk ID `RT01`…): description, class, likelihood, impact, rating, owner, treatment. Then the **exposure table** (header row begins `Exposure ID`; rows `RT01-001` …):

Columns: A Exposure ID · B Risk ID · C Exposure / cost consequence · D Affected driver · E Affected cost ref (QS codes) · F Existing treatment · G Existing baseline amount · H Residual exposure (words) · **I Calculation Mode** · J Residual qty · K Unit · L Unit rate / impact · **M Probability** · N *(formula)* · **O Selected tender provision** · **P Cost treatment owner** (`Primary` / `Contributing` / `Reference Only`) · Q Residual distinct? (`Yes`/`No`/`N/A`) · **R Integration target** (`CA01` design/scope residual or `CA02` construction/execution residual) · **S Include new risk cost?** (`Yes`/`No`) · T *(formula)* · U Overlap group · V Embedded variability · **W Evidence status** (`GREEN`/`AMBER`/`RED` + reason) · X *(formula)* · **Y Integration complete?** · Z *(formula)* · AA Sensitivity / basis · AB Firm-up action · AC Source.

Calculation modes (exact words): `Already in Base / No Add`, `Unit Rate Delta`, `Probability x Impact`, `Scenario Weighted`, `Fixed Allowance`, `Specialist Engine`, `By Others / Excluded`, `RFI Hold`.

Rules:
- Quantifiable physical consequences go **back into the build-up / QS** and the exposure is `Already in Base / No Add`. Only the *residual* goes to CA01/CA02.
- Weather is `Specialist Engine` and is **referenced, never re-added**.
- **No default probabilities. 50/50 is not evidence.** If you have no evidence for a probability, leave it blank: an unknown probability produces no expected value (it stays a sensitivity). An unknown impact is an unquantified tail.
- Include a provision (`S = Yes`) only when the exposure is distinct (Q = Yes), not already in base, evidence is not RED, and the overlap group has exactly one `Primary`.
- Every RED risk or RED exposure holds the release gate. List them in the handover note.

**Management reserve items.** For each item that cannot realistically be closed before the price goes in, record: title, source (RFI / risk ref), adverse consequence as a **cost delta** against the priced baseline (not sell), whether quantified / proxy / unquantified, and any evidenced probability range. Put them in the Notes column of *Commercial Inputs* CA16 or the Decision Log. Rick adjudicates the selected amount.

### 5.8 Weather Risk
Fill **project inputs** only: B6 station / representative location · B7 assumed construction start (date) · B8 baseline working days · B9 working days per week · B16 project-specific recovery allowance. B13 (daily time-related preliminaries) and B14 (weekly billed hire) are formulas pointing at the build-up rows that carry daily preliminaries and weekly hire (for example `=Y584*8`, `=Y295+Y330`) — **keep them pointing at the correct rows** if you add or move rows, or the app cannot link weather costs.

Do not compute the weather allowance yourself. Mark weather-exposed labour/plant rows on the build-up (columns AK/AL). Wind is excluded by default and stays AMBER. Record which weather tool version and station the run used if Rick gives you a run.

### 5.9 Programme Export
Header **row 6**; tasks from **row 7**: C WBS/section (a section that starts `PRELIMINARIES` is treated as a full-duration hammock) · **D QS code (or a control code such as `PRG-CURE`)** · E task name · L programme override days · **P predecessor QS codes** (comma or space separated) · O duration basis · X notes.

Durations derive from build-up hours (slowest resource row ÷ hours per day). Use an override (L) only where a real constraint exists (cure time, inspection hold, stand-down) and say what it is in O or X. Logic is finish-to-start unless noted. Do not create loops.

### 5.10 Other sheets
*Tender Build-Up, Summary, Stage Cashflow, Rate Verification, Estimate Review Board:* keep the template's formulas; do not type over them. If the template includes a **Supplier Quote Register** (header row 4: Quote ID, Package, Estimate Ref, Current Qty, Unit, Current PC / Control excl. GST, Required Quote Scope, Documents to Issue, Preferred Supplier / Recipient, Status, Due / Action, Quote Ref / Notes), keep one row per `Q-nn`, and keep it consistent with the Quote Log.

---

## 6. Evidence, colours and wording

- **Colour + reason, always.** `AMBER - market benchmark; firm to payroll`. A bare colour is not acceptable.
- Quantity sources name the **document, sheet, revision and page**. "Drawings" is not a source.
- Where you read a number from a drawing image rather than text, say so (`read from image`) and mark it AMBER.
- Use plain construction wording. No marketing language. No unexplained abbreviations in client-facing text.
- Dates as `DD-Mon-YYYY` in text cells; real dates in date cells.

---

## 7. Things you must never do

- Never put a price, quantity or rate in the workbook that you cannot trace to a document or a stated calculation.
- Never "round to make it balance".
- Never apply a blanket percentage for contingency, risk or "unknowns".
- Never use a rate from a reference book or an example in a standards document as a live rate.
- Never mark GREEN without the three checks.
- Never delete a superseded document, quote, rate or RFI — mark it.
- Never contact anyone, send email, or reply to a thread.
- Never summarise an email in a way that changes its meaning; quote the key sentence where wording matters (price, scope, validity, exclusions).

---

## 8. Logs (new sheets — the full record of the job)

These sheets give Rick one searchable record instead of pages of documents. Add them **after** the existing sheets. Header on **row 1**, data from **row 2**. One row per item. Do not delete rows: close them.

> **App status:** Today the app imports the sheets in section 5 and ignores unknown sheets, so adding these is safe. Importing the logs into the app is being built next; **keep the exact headers below** so nothing needs re-doing.

### 8.1 Email Log
| Column | Content |
|---|---|
| Email ID | `EM-0001`, running |
| Date / time | As received or sent |
| Direction | `In` / `Out` |
| From / To / Cc | Names or organisations (email addresses allowed; no phone numbers or home addresses) |
| Subject | As in the email |
| Source reference | Mail thread/message ID or link, or the file name of the saved email |
| Category | `Tender documents` / `Addendum` / `RFI` / `Clarification` / `Quote` / `Programme` / `Commercial` / `Internal` / `Other` |
| Linked refs | RFI IDs, Quote IDs, QS codes (comma-separated) |
| Summary | 1–3 neutral sentences |
| Key wording | Exact words that matter (price, scope, validity, exclusions), in quotation marks |
| Attachments | File names and which Document Register IDs they became |
| Action required | `Yes` / `No` and what |
| Action owner / Due | |
| Status | `Open` / `Closed` / `Info only` |
| Estimate impact | `None` / `Quantity` / `Rate` / `Scope` / `Programme` / `Commercial` |
| Applied in estimate | Revision and line where it changed the estimate (or `Not yet`) |

### 8.2 RFI Log (master list of RFIs)
RFI ID (`RFI-01`) · Date raised · Raised by · Addressed to · Subject · **Question — what is missing** · **Where expected** (document / drawing) · **Why it matters** · **Decision impact** (cost, programme, scope — with a dollar or day range only if evidence supports it) · QS codes / risk IDs affected · **Assumption in force until answered** · Status (`OPEN` / `CLOSED` / `SUPERSEDED`) · RAG · Date answered · Answer summary · Answer source (Email ID / document) · Resulting estimate change (revision, line) · Owner.

Rules: every RED or AMBER item that depends on missing information has an RFI. An RFI states the **assumption priced** while it is open. Close an RFI only with the answer's source recorded. Generate the *Cover & Instructions* RFI rows from this log.

### 8.3 Quote Log
Quote ID (`Q-01`) · Package / scope · Supplier / subcontractor · Contact (name only) · Quote number · Quote date · **Valid until** · Source (Email ID or file) · Scope included · **Exclusions and qualifications** · Price excl. GST · GST basis · Unit rates (if given) · Payment / retention terms · Lead time · QS codes fed · **Treatment** (`Overlay in Consolidated Package` / `Fed into library rate` / `Reference only`) · **Amount used in estimate** and **why** · Comparison with other quotes for the same scope · Evidence strength (`GREEN` / `AMBER` / `RED`) · Status (`Requested` / `Received` / `Clarification required` / `Accepted for pricing` / `Superseded` / `Declined`) · Next action / due · Notes.

A quote is **evidence, not the controlling amount**: record scope gaps against the tender documents. Never add a quote twice (once as overlay, once inside own-works rows).

### 8.4 Document Register
Doc ID (`DOC-001`) · Title · Type (`Plan` / `Specification` / `Schedule` / `Geotech` / `Consent` / `Addendum` / `Photo` / `Email` / `Other`) · Reference / drawing number · **Revision** · Date · Status (`CURRENT` / `SUPERSEDED` / `UNCLEAR`) · Superseded by · Source (file name, link, Email ID) · Received date · Used for (QS codes) · Notes.

### 8.5 Decision Log
Decision ID (`DEC-001`) · Date · Decision · Made by · Options considered · Basis / evidence · Estimate impact · Revision applied · Status (`Proposed` / `Approved by estimator` / `Superseded`). Everything you propose is `Proposed`; Rick approves.

### 8.6 Contacts
Organisation · Person · Role · Package/trade · Source of the contact (Email ID) · Notes. Names and roles only; **no phone numbers or home addresses**.

### 8.7 Change Log (between revisions)
Revision · Date · What changed (scope / quantity / rate / quote / commercial / risk / programme) · Reason (document, email, decision) · Lines affected · Cost movement excl. GST (from the Summary, not estimated) · Recorded by.

---

## 9. RFIs — how to write them
Every gap becomes an RFI with all four parts:
1. **What is missing** (specific: "Retaining wall height between grids B and D").
2. **Where it was expected** (document and section).
3. **Why it matters** (what cannot be priced).
4. **Decision impact** (which cost, programme or scope decision changes; the assumption priced meanwhile).

Conflicts: quote both sources with their references and revisions. Do not resolve.

---

## 10. Verification (GREEN / AMBER / RED)

| Colour | Meaning |
|---|---|
| GREEN | Current primary evidence + an independent check + a first-principles reasonableness check, all recorded |
| AMBER | Reasonable, partly evidenced, or evidenced by a single source or an old/benchmark source |
| RED | Missing, conflicting, unsupported, or an unpriced exposure |

A workbook with RED items is still delivered. It is **not released**: the handover note lists every RED item as the release blocker.

---

## 11. Self-check before delivering
Tick each; report failures in the handover note.

- [ ] Every sheet name, header row and column position matches the template; no formulas overwritten; no merged cells in tables.
- [ ] Every number cell is a number. No `TBC` / `n/a` in numeric cells.
- [ ] Workbook recalculated and saved; no `#REF!`, `#NAME?`, `#VALUE!`, `#DIV/0!` anywhere.
- [ ] Every QS code with a quantity has at least one build-up row; every build-up `QS Code` exists on QS Takeoff; every `Resource Code` exists in the library (except lump-sum rows).
- [ ] QS amount for each code equals the sum of its build-up rows (formula intact).
- [ ] No cost appears twice (build-up vs quote overlay vs risk vs weather vs reserve). QA column filled.
- [ ] Every quantity names document, sheet, revision and page; every status uses the allowed words.
- [ ] Library rates added this job each have source, date, supplier/source and verification status.
- [ ] Commercial Inputs: only allowed methods; overhead and profit separate; CA16 not set by percentage.
- [ ] Risk Truth: no invented probabilities; every provision has Primary owner, distinct = Yes, evidence not RED; weather is `Specialist Engine`.
- [ ] Programme: every predecessor code exists; no loops; overrides explained.
- [ ] Every Cover RFI exists in the RFI Log and vice versa; every quote on the Supplier Quote Register is on the Quote Log.
- [ ] Email Log covers every email Rick provided; nothing was sent or replied to.
- [ ] Document Register marks the current revision of every document; conflicts have RFIs.
- [ ] Handover note written (section 12).

---

## 12. Handover note template

```markdown
# Handover — <Job name> — Rev<NN>

## Position
- Estimate level / purpose:
- Own works pre-commercial: $…   All-in (from the workbook's Consolidated Package): $…   excl. GST
- Release status: HOLD / READY — because …

## Complete
- …

## RED items (release blockers)
| Ref | What | Why RED | What would close it |

## AMBER items worth Rick's attention first
- …

## Open RFIs (count) — top 5 by decision impact
- RFI-xx — …

## Quotes
- Received: … | Outstanding: … | Placeholders in the price: …

## Assumptions I made (each also on the register)
- …

## Things in the documents that conflict
- …

## Problems with these instructions or the template
- (anything unclear, contradictory or impossible — this feeds section 14)
```

---

## 13. Starter prompt Rick can paste with the files

> You are building a Master Estimate Workbook for one job. I have attached (1) the Master Estimate Workbook template, (2) `Workbook_Builder_Instructions.md`, and (3) the tender documents and emails. Follow the instructions document exactly: do not guess any number, keep the template's sheets, rows and columns, complete the logs, and deliver the completed `.xlsx` plus the handover note. If anything in the instructions conflicts with what I say here, ask me before proceeding. Do not send or reply to any email.

---

## 14. Improving this document

This document improves from real runs. At the end of each job:

1. The assistant lists, in the handover note, every point where these instructions were unclear, wrong, missing or impossible.
2. Rick and the platform's developer assistant review the list and update this file.
3. Each change is recorded below with the revision, date and reason. **Never silently change the contract in section 5** — the app reads those positions.

When the app's importer learns to read a new sheet or column, section 5 / 8 is updated in the same change.

### Revision history
| Rev | Date | Change | Reason |
|---|---|---|---|
| Rev1 | 14 Oct 2026 | First issue: process, sheet contract, logs, handover | Rick requested an external-AI instruction set to build job workbooks for the app |

### Open improvement ideas (not yet adopted)
- Add a Productivity & Crew Library sheet and rules once Rick confirms it exists (Starter workstream 3).
- Import Email / RFI / Quote logs into the app (Register and Quotes pages) so the workbook is the single hand-over.
- Add worked, anonymised examples of a good QS row, build-up row and RFI.
- Add a rule set per work type (earthworks, drainage, pavements, retaining) for typical build-up rows.

