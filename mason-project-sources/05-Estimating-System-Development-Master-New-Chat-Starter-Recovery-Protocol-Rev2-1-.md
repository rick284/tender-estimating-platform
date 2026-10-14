# ESTIMATING SYSTEM DEVELOPMENT  
## MASTER NEW CHAT STARTER & RECOVERY PROTOCOL — REV2

**Purpose:**  
Use this document whenever starting a new ChatGPT conversation to develop, test, audit or improve one component of the estimating system.

The objective of the overall system is to produce the **best evidence-based forecast of what a project will genuinely cost and how long it will take, based on the information reasonably available at estimate date**.

The objective is not to produce the cheapest tender, the highest tender, a target number or an artificially precise number.

Where uncertainty exists, expose it, classify it and deal with it appropriately.

---

# 1. WORKSTREAM FOR THIS CHAT

**Workstream / Tool Name:**  
[INSERT — e.g. Risk Truth Engine]

**Primary Objective:**  
[INSERT]

**Problem this tool is intended to solve:**  
[INSERT]

**Expected final deliverable:**  
[INSERT — e.g. approved methodology + integrated master workbook module + Master Prompt amendments + test against Clevedon]

**Test project where applicable:**  
[INSERT — default to Clevedon Civil Works Tender Estimate unless another project is nominated]

**Current approved starting file/version:**  
[INSERT]

---

# 2. PERMANENT PROJECT RULE — READ REFERENCES FIRST

Before undertaking any development, estimating, pricing, risk modelling, programme modelling, workbook changes or recommendations:

Locate and read the current approved versions in Project Files of:

1. Estimate Intake Block
2. Estimate Master Prompt
3. Estimating Triple Verification Standard
4. Current Company Resource Rate Library, if applicable
5. Current Productivity and Crew Library, if applicable
6. NZ Weather Risk Estimating Tool, if applicable
7. Current Master Estimate Workbook/template
8. Any tool or source directly relevant to this workstream

Return this checklist before proceeding:

**Intake file read: Yes/No**  
**Master prompt file read: Yes/No**  
**Triple Verification Standard read: Yes/No**  
**Relevant existing tools/source files read: Yes/No**  
**Master Estimate Workbook read: Yes/No**  
**Test workbook/project received: Yes/No**

If a required permanent reference is missing, unreadable or clearly obsolete, STOP and identify what is missing.

Do not silently recreate it from memory.

---

# 3. ABSOLUTE TRUTH PRINCIPLE

Every development decision must support the following principle:

> The estimate must represent the best evidence-based forecast possible using the information reasonably available at estimate date.

Never manipulate:

- quantities
- productivity
- crew composition
- rates
- programme duration
- allowances
- risk
- contingency
- margin
- escalation
- temporary works
- weather
- commercial inputs

to achieve a preferred tender total.

Do not use false precision where evidence is incomplete.

Uncertainty must be visible.

---

# 4. RISK PHILOSOPHY

Apply the same philosophy established for weather to all project risks.

Every identified risk must first be classified.

### A. Known and measurable

Price directly.

### B. Normal foreseeable construction variability

Model the expected effect and include it in the estimate where justified.

Examples:

- normal weather
- normal plant downtime
- normal waste
- reasonable productivity variation
- normal minor rework
- normal access inefficiency

### C. Evidence-supported uncertainty

Model scenarios or provide a transparent allowance.

Examples:

- unsuitable material
- groundwater
- rock
- variable haul distance
- uncertain productivity caused by known site constraints

### D. Known possible item with unknown extent

Treat as:

- Provisional
- PC Sum
- schedule rate
- RFI

as appropriate.

### E. Missing information

Do not invent the answer.

Raise an RFI and identify:

- cost impact
- quantity impact
- programme impact
- methodology impact
- whether an allowance or exclusion is required

### F. Other-party responsibility

Identify as an interface or exclusion rather than automatically pricing it.

### G. Genuine abnormal / unforeseeable event

Do not invent an arbitrary tender allowance merely because the event is theoretically possible.

Record the tender baseline.

Contractual treatment of events outside that baseline is a separate matter.

---

# 5. ESTIMATE RISK IS NOT THE SAME AS CONTRACT ENTITLEMENT

Keep these two concepts separate.

## Estimating question

**What do we reasonably expect to happen and what should we allow for now?**

## Contract question

**If actual conditions fall outside that tender basis, who carries the resulting time and cost under the contract?**

Do not contaminate the estimating model with unsupported legal conclusions.

Where useful, build a separate Contract Risk Matrix, but do not use contractual entitlement to distort the factual estimate.

The estimate records the reasonable tender baseline.

The contract determines what happens when actual events materially depart from that baseline.

---

# 6. NO GENERIC PERCENTAGES WITHOUT A BASIS

Do not default to arbitrary allowances such as:

- 5% contingency
- 2% weather
- 10% ground risk
- 5% wastage
- 3% escalation

unless there is an explicit evidence-based reason for doing so.

Where possible, calculate the underlying exposure.

Example:

Instead of:

**Weather = 1.5%**

use:

- weather-exposed labour
- weather-exposed plant
- activity sensitivity
- climate probability
- critical-path effect
- time-related preliminaries
- hire extension
- recovery/remediation

Apply the same thinking to every new risk tool.

---

# 7. REQUIRED NUMBER CLASSIFICATION

Every inserted numerical input must be identifiable as:

**MEASURED**  
Traceable to drawing/specification and measurement.

**PROVIDED**  
Supplied by client, consultant, contractor or supplier.

**CALCULATED**  
Derived from visible inputs using a reproducible calculation.

**ALLOWANCE / PC SUM**  
Explicit temporary budget pending stronger evidence.

**QUOTED**  
Supported by a current project-specific written quotation.

Where relevant also assign:

**GREEN**  
Fully verified.

**AMBER**  
Usable but with disclosed limitations.

**RED**  
Evidence missing, contradictory or unacceptable for final release.

---

# 8. THREE-WAY VERIFICATION

Important rates, quantities, productivities and allowances should progressively be tested against:

### Check 1 — Primary evidence

Current project quote, controlling drawing/specification, payroll/cost record or approved primary source.

### Check 2 — Independent check

Second supplier, comparable project, published source, separate measurement or other independent evidence.

### Check 3 — First principles

Rebuild the number from:

- quantity
- crew
- hours
- productivity
- plant
- materials
- waste
- haulage
- methodology
- arithmetic

A plausible number is not automatically a verified number.

---

# 9. SINGLE MASTER ESTIMATE WORKBOOK RULE

Each project must operate from **one Master Estimate Workbook**.

Specialist estimating tools may be developed and tested separately, and central reference libraries may exist independently, but no tool is considered complete until its required inputs, outputs, assumptions, source basis and verification status are integrated into the Master Estimate Workbook without creating duplicate cost chains or requiring manual reconciliation between separate job workbooks.

### Central libraries and backend tools are intelligence sources

Examples include:

- NZ Weather Risk Estimating Tool
- Company Resource Rate Library
- Productivity and Crew Library
- Actual Cost and Productivity Database
- Supplier Quote Register
- escalation datasets
- geotechnical/geological reference sources

These may remain separate central sources where that is the best architecture.

They are **not competing project estimates**.

The project-specific result must ultimately be visible and traceable through the single Master Estimate Workbook.

### Permanent rule

> One project = one controlling Master Estimate Workbook.

Do not create a permanent operating model where an estimator must manually reconcile:

- Weather.xlsx
- Risk.xlsx
- Ground.xlsx
- Haulage.xlsx
- Programme.xlsx
- TemporaryWorks.xlsx
- Estimate.xlsx

or similar independent job-costing files.

Separate development prototypes are acceptable.

Separate permanent project cost chains are not.

---

# 10. MODULAR MASTER WORKBOOK PRINCIPLE

The Master Estimate Workbook should become more intelligent without becoming unnecessarily cluttered.

Modules should be capable of being classified as:

**ACTIVE**  
Required and in use for this project.

**NOT APPLICABLE**  
Reviewed and not relevant to the project.

**INCOMPLETE**  
Applicable, but information or setup remains incomplete.

**GREEN**  
Applicable and sufficiently verified.

**AMBER**  
Applicable and usable with disclosed limitations.

**RED**  
Applicable but unresolved information or contradictions prevent reliable release.

Core estimating sheets remain permanently available.

Specialist modules should activate only where relevant.

Typical core sheets may include:

- Document Control
- Intake / Job Setup
- Resource Rate Library / project snapshot
- Resource Build-Up
- QS Takeoff
- Tender Build-Up
- Commercial Inputs
- Programme
- Risk Register
- Summary
- Cashflow
- Source / Verification Register

Specialist modules may include:

- Weather Risk
- Ground / Geotechnical Risk
- Earthworks Balance / Haulage
- Temporary Works
- Escalation
- Quote Comparison
- Design Maturity
- Programme Risk
- other specialist estimating engines

Do not add tabs merely because a tool exists.

Add or activate them because the project requires them.

---

# 11. SYSTEM ARCHITECTURE — NEVER BREAK THE COST CHAIN

Permanent estimating architecture:

**Resource Rate Library  
→ Resource Build-Up  
→ QS Takeoff  
→ Tender Build-Up  
→ Summary  
→ Cashflow / Programme**

Supporting engines such as:

- Weather
- Risk
- Haulage
- Ground
- Escalation
- Temporary Works
- Quote Comparison
- Programme Risk

must integrate into this architecture without creating unexplained duplicate costs.

A value changed once should flow to every appropriate dependent location.

Do not create competing hard-coded versions of the same number.

Where an engine produces an allowance rather than a measured direct cost, its integration point must be explicitly identified and tested so it cannot duplicate a cost already captured elsewhere.

---

# 12. NEVER LOSE FUNCTIONALITY

Permanent rule:

> Never lose functionality. Only improve it.

Before changing any existing workbook or tool:

1. Audit the existing structure.
2. Identify formulas and dependencies.
3. Identify user-editable cells.
4. Identify protected/control cells.
5. Identify source evidence.
6. Record existing totals.
7. Confirm the intended integration point.
8. Identify possible duplicated costs.
9. Identify all downstream sheets affected.
10. Only then modify.

After changing it:

1. Reconcile previous versus new totals.
2. Check the full cost chain.
3. Check formulas.
4. Check for broken references.
5. Check for duplicate allowances.
6. Check programme/cost consistency.
7. Check client-facing formatting.
8. Check document control/version.
9. Explain every material movement.
10. Confirm source and verification status.
11. Confirm that changing the primary input flows through every correct dependent location.

Never delete useful functionality simply because it appears unused on the current test project.

---

# 13. DEVELOPMENT METHOD FOR THIS WORKSTREAM

Work through the following stages.

## Stage 1 — Define the problem

Explain:

- what currently happens
- why it is inadequate
- what estimating truth should look like instead
- what decision the new tool must support

Do not build anything until the problem is clearly understood.

## Stage 2 — Define the estimating methodology

Determine:

- required inputs
- calculations
- evidence sources
- assumptions
- outputs
- uncertainty classifications
- verification status
- tender baseline
- outside-baseline triggers
- rerun/change-control triggers

## Stage 3 — Identify authoritative sources

Use primary or authoritative sources wherever possible.

Examples include:

- NIWA
- Stats NZ
- MBIE
- WorkSafe NZ
- NZTA
- GNS Science
- council GIS/data
- supplier quotations
- manufacturer data
- company actual cost records
- project-specific consultants

Record:

- source
- date
- geography
- units
- currency
- GST basis
- delivery basis
- limitations
- status

## Stage 4 — Prototype

Build the smallest working version capable of testing the methodology.

Do not over-engineer the first version.

A separate prototype workbook or calculation tool may be used during development where this is safer.

It is a development tool only.

## Stage 5 — Test against a real estimate

Default test project where relevant:

**Clevedon Civil Works Tender Estimate**

Test:

- cost effect
- programme effect
- resource effect
- commercial effect
- sensitivity
- double counting
- existing allowances that should be replaced
- downstream formula flow
- client-facing implications

## Stage 6 — Red-team the result

Ask:

- Are we pricing the same risk twice?
- Have we mistaken uncertainty for certainty?
- Have we priced something belonging to another party?
- Have we ignored a genuine foreseeable cost?
- Is the programme treatment realistic?
- Are the source assumptions actually comparable?
- Is the result distorted by a target total?
- Would we be willing to defend this basis six months later in a dispute?
- Is the tool producing real insight or merely disguising judgement with formulas?
- Is the result more truthful than an experienced estimator's reasoned manual assessment?

## Stage 7 — Integrate

Only once methodology passes testing:

Integrate the approved tool into the **single Master Estimate Workbook architecture**.

Integration does **not** mean creating another permanent project workbook.

A tool is not considered complete merely because its standalone prototype works.

Integration is complete only when:

1. Required project inputs have a controlled home.
2. Source/basis information is retained.
3. Outputs flow into the correct existing cost chain.
4. Programme impacts flow correctly where relevant.
5. Assumptions and status are visible.
6. Duplicate cost pathways have been eliminated.
7. Changes flow automatically to all appropriate downstream outputs.
8. The module can be marked Active / N/A / Green / Amber / Red.
9. The project can still be estimated from one controlling Master Estimate Workbook.

## Stage 8 — Update governing instructions

Determine whether changes are required to:

- Estimate Master Prompt
- Triple Verification Standard
- Intake Block
- Master Estimate Workbook
- Resource Rate Library
- Productivity Library
- programme workflow
- estimating source library

Do not modify permanent instructions merely because an idea sounds useful.

Validate it first.

---

# 14. REQUIRED TOOL DESIGN PRINCIPLES

Every new estimating tool should, where applicable, provide:

### Inputs

Clearly identified editable inputs.

### Source / Basis

Where each important input came from.

### Calculation

Visible and reproducible logic.

### Output

Cost and/or programme result.

### Sensitivity

What assumptions materially move the result.

### Status

GREEN / AMBER / RED.

### Tender Baseline

What conditions the estimate assumes.

### Outside-Baseline Trigger

What occurrence would materially differ from what was priced.

### Rerun Trigger

What change requires recalculation.

### Integration Point

Exactly where the output enters the Master Estimate Workbook cost/programme chain.

### Duplication Check

Which existing allowances or costs could overlap with this tool.

### Actual Feedback

Where practical, allow real project outcomes to be fed back into the model after construction.

---

# 15. FUTURE ACTUALS LOOP

Every tool should be designed with the eventual feedback loop in mind:

**Estimate  
→ Construction  
→ Actual result  
→ Variance  
→ Cause  
→ Reviewed actual  
→ Library calibration  
→ Better next estimate**

Do not overwrite historic assumptions with actual results.

Retain both so estimated versus actual performance can be analysed.

The ultimate objective is to progressively replace generic industry assumptions with verified company/project actuals where sufficient data exists.

---

# 16. CURRENT PRIORITY WORKSTREAMS

Develop each of these in a **SEPARATE CHAT**.

1. Risk Truth Engine
2. Actual Cost & Productivity Feedback Engine
3. Productivity & Crew Library
4. Ground / Geotechnical Risk Tool
5. Earthworks Balance / Haulage / Disposal Tool
6. Supplier Quote & Market Intelligence Register
7. Escalation / Price Exposure Tool
8. Temporary Works / Constructability Engine
9. Design Maturity / Scope Completeness Tool
10. Programme Risk Engine
11. Subcontractor Quote Comparison Tool
12. Contract Risk Allocation Matrix

Do not attempt to develop all of these in one conversation.

Development may occur independently.

Approved outputs must ultimately integrate into the one Master Estimate Workbook or approved central source architecture as appropriate.

---

# 17. WORKSTREAM-SPECIFIC SUCCESS TEST

Before declaring this workstream finished, answer:

1. What problem did we solve?
2. What evidence drives the tool?
3. What parts are MEASURED / PROVIDED / CALCULATED / ALLOWANCE / QUOTED?
4. What remains AMBER?
5. What remains RED?
6. Can the tool accidentally double count another estimate allowance?
7. Does it integrate into the permanent cost chain?
8. Does a changed input flow correctly?
9. Does programme impact flow correctly where applicable?
10. Can the result be explained to a client?
11. Could the tender basis be defended later?
12. Can actual project results eventually improve the model?
13. Have all modified workbook formulas and outputs been reconciled?
14. Have we preserved existing functionality?
15. Does the tool require another permanent project workbook?
16. Can the estimator still operate the project from one Master Estimate Workbook?
17. Is the tool genuinely better than experienced estimator judgement alone?

If the answer to Question 15 is **Yes**, redesign the integration unless there is a compelling approved technical reason.

If the answer to Question 17 is **No**, do not add the tool simply for the sake of having another tool.

---

# 18. MASTER WORKBOOK RELEASE TEST

Whenever a workstream changes the Master Estimate Workbook, perform a release test before approval.

Confirm:

- Master workbook opens without repair warnings.
- Existing formulas remain functional.
- Existing workbook functionality has not been lost.
- Resource Build-Up reconciles to QS Takeoff.
- QS Takeoff reconciles to Tender Build-Up.
- Tender Build-Up reconciles to Summary.
- Summary reconciles to Cashflow.
- Programme quantities and time-related costs use the same programme basis.
- New module outputs enter the cost chain once only.
- No unexplained hard-coded duplicate has been introduced.
- Editable inputs are clearly identifiable.
- Formula/control cells are protected or difficult to overwrite accidentally.
- Source status is retained.
- Document control has been updated.
- Previous release total is retained for reconciliation.
- Material changes have an explanation.
- Specialist modules show the correct Active / N/A / Green / Amber / Red status.

Any unexplained reconciliation difference is **RED** and blocks approval.

---

# 19. MANDATORY END-OF-CHAT RECOVERY RECORD

Before this conversation finishes, create a final recovery record using the following structure.

## WORKSTREAM HANDOFF

**Workstream:**  
[NAME]

**Status:**  
[NOT STARTED / DEVELOPMENT / TESTING / AMBER / APPROVED]

**Objective:**  
[SHORT DESCRIPTION]

**What was completed:**  
[DETAIL]

**Methodology agreed:**  
[DETAIL]

**Key decisions made:**  
[DETAIL]

**Files created or modified:**  
- Filename
- Revision
- Purpose

**Current approved file:**  
[FILENAME]

**Current approved Master Estimate Workbook:**  
[FILENAME / REVISION]

**Permanent Project Files that need updating:**  
[LIST OR NONE]

**Source data used:**  
[LIST]

**GREEN items:**  
[LIST]

**AMBER items:**  
[LIST]

**RED / unresolved items:**  
[LIST]

**Known defects / limitations:**  
[LIST]

**Testing completed:**  
[DETAIL]

**Test results:**  
[DETAIL]

**Master Workbook integration status:**  
[NOT STARTED / PROTOTYPE ONLY / PARTIAL / COMPLETE]

**Master Prompt changes required:**  
[YES/NO + DETAILS]

**Triple Verification changes required:**  
[YES/NO + DETAILS]

**Workbook/template changes required:**  
[YES/NO + DETAILS]

**Central library/source changes required:**  
[YES/NO + DETAILS]

**Next exact action:**  
[ONE CLEAR NEXT STEP]

**Important instructions for next chat:**  
[ANYTHING THAT MUST NOT BE LOST]

---

# 20. RECOVERY RULE

If a chat becomes slow, stalls or becomes unreliable:

Do not try to reconstruct months of development from memory.

Start a new chat.

Paste:

1. This Master New Chat Starter.
2. The latest WORKSTREAM HANDOFF.
3. Upload or nominate the current approved workstream file.
4. Upload or nominate the current approved Master Estimate Workbook if applicable.
5. State:

> Continue this workstream from the attached handoff. Audit the current files and reported state before modifying anything. Do not rebuild completed work unless the audit proves it is defective. Maintain the single Master Estimate Workbook architecture.

The new conversation should first verify the recovery state before continuing.

---

# 21. FINAL OPERATING PRINCIPLE

The purpose of this system is not to remove estimator judgement.

It is to make estimator judgement:

- visible
- evidence-based
- repeatable
- measurable
- auditable
- improvable

The final estimate should answer:

> Based on everything we reasonably knew at the time, what did we genuinely believe this project would cost and how long would it take?

And the system should be able to demonstrate:

- what we knew
- what we measured
- what we calculated
- what we assumed
- what risks we expected
- what risks we did not price
- what remained uncertain
- what evidence supported the decision
- where the resulting cost sits in the estimate
- what changed after tender

If we can answer those questions clearly and demonstrate how we reached the answer, the estimating system is doing its job.

---

# 22. OPENING INSTRUCTION FOR A NEW WORKSTREAM CHAT

After uploading this document into a fresh conversation, use:

> **Start Workstream [NUMBER] — [WORKSTREAM NAME]. Read the attached Master New Chat Starter and all current Project Files first. Audit the existing estimating architecture and current Master Estimate Workbook before proposing or changing anything. Maintain the single Master Estimate Workbook rule. Do not modify permanent files until the proposed methodology has been tested and reported.**

For the first workstream:

> **Start Workstream 1 — Risk Truth Engine. Read the attached Master New Chat Starter and all current Project Files first. Audit the existing estimating architecture and current Master Estimate Workbook before proposing or changing anything. Maintain the single Master Estimate Workbook rule. Do not modify permanent files until the proposed methodology has been tested and reported.**