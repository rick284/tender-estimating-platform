# Project Time and Activity Recording

**Applies to:** Mason Reid and the Blackline estimating tool

**Intended source path:** `sources/BLACKLINE_PROJECT_TIME_AND_ACTIVITY_STANDARD.md`

**Version:** 1.1

**Date:** 14 October 2026

**Status:** REVIEW — source document prepared; deployment and acceptance pending

Purpose: record the work performed for each client and project as it happens, so Rick can verify the history, assess what should be charged and map every invoice line back to its supporting work.

Maintain one canonical project time and activity ledger in Google Drive, inside the relevant project folder, and update it continuously throughout project work. Keep human time, AI execution and billing decisions separate. Capture all relevant activity, including nonchargeable work, without treating every logged event as a charge.

### What must be recorded

Project chats and instructions; drawing and specification review; takeoffs; resource build-ups; pricing and quote comparison; RFQs and RFIs; emails drafted, reviewed, sent and received; meetings, calls and site work; programme work; QA; corrections; revisions; reports and handovers. Log substantive changes and outcomes, rather than every keystroke.

| Record | Meaning | Billing treatment |
| --- | --- | --- |
| Human time | Rick’s measured or explicitly declared working intervals, including review and manual work. | Eligible only after review against the engagement basis. |
| AI activity | Measured job execution, tool activity, outputs and available usage or cost data. | Separate record. No default conversion into human hours. |
| Charge decision | Approved hours, fixed fee or other agreed basis mapped to underlying entries. | Rick chooses the charge and any discount or write-off. |

### Success condition

For any proposed charge, Rick can see who did the work, when it occurred, what changed, which project benefited, how the time was established and which evidence supports it. Recorded work must remain visible even when its charge is zero.

### Status and authority

This is a proposed operating and implementation specification, not an installed timer or a deployed Mason runtime change. Preparing it does not modify the production estimating app, approve rates or authorise invoices or external messages.

## 1 Capture time without inventing it

### Human work sessions

Provide Start, Pause, Resume, Switch project and Finish controls. Selecting a project chat may open a session and offer a timer, but opening a chat alone is not proof of active work. Show the selected project, activity and timer clearly. Manual work can use the same timer or a later declared entry.

Store time as intervals, with UTC timestamps and the original local timezone. Calculate duration deterministically from accepted intervals. Exclude paused time; flag idle periods and unclosed sessions for review. Proposed default: flag inactivity after five minutes and stop accruing verified time until Rick confirms the interval. Idle signals are prompts, not proof that work stopped.

A disconnected browser, closed tab or crashed app must not leave an indefinite billable timer. Record the last reliable checkpoint and mark the uncertain remainder. Do not silently infer continuous work overnight or between messages.

### Concurrent work and interruptions

Only one active human timer per person across all projects and devices. Switching projects closes or pauses the prior interval. Overlapping imported or manual intervals require reconciliation before approval. Allocate shared work explicitly across projects; total allocation must equal the underlying human time.

If AI runs while Rick works elsewhere, record both independently. AI waiting time is not automatically Rick’s time. If Rick is actively monitoring or reviewing, he can record that human activity; a passive open window does not establish it.

### AI execution

For each instrumented job, record the agent, job and parent IDs, request and completion timestamps, outcome, source events and output references. Separate total job elapsed time from queued or waiting time and measured model or tool execution when the platform supplies those measures. Capture tokens, model identifier and actual attributable cost only when available.

Parallel jobs may produce a summed execution duration greater than the elapsed session. Report both clearly and never add AI duration to human hours as a combined labour total. Retries and failures remain visible with their own outcome and billing treatment.

### Evidence status

| Time basis | Rule |
| --- | --- |
| Measured | Captured by an instrumented timer or execution system; retain measurement method. |
| Declared | Entered or confirmed by Rick; retain who supplied it and when. |
| Estimated | Reconstructed from evidence; retain basis, uncertainty and review decision. |
| Unknown | Activity is known but duration is not. Leave duration blank, not zero. |

Email timestamps and file revision dates prove an event, not preparation duration. Historical reconstruction must never be relabelled as measured time.

## 2 Connect work to project evidence

### Ledger structure

The canonical time and activity record must live in the relevant project folder in Google Drive. Use one Google Sheet named `<Project ID> Project Time and Activity Ledger`, with tabs for Activity, Human Time, AI Jobs, Billing Allocations, Audit History and Session Summaries. The estimating app and Mason must write to that same record through a controlled logging interface. An app database may support operational processing and recovery, but it must not become an independently edited competing ledger. Source documents remain in their existing authoritative homes; retain references and revision identifiers rather than copying entire mailboxes or drawings into the log.

### Mandatory Drive persistence

- Resolve the existing project folder and ledger before beginning substantive work. Reuse their stable Drive IDs; never create a new ledger for each chat or rely only on folder names.
- If the known project folder has no ledger, create the ledger there and record its file ID and link against the project. Do not create a competing project folder. If the project destination is ambiguous or unavailable, preserve the entry in a recovery queue and resolve the destination; do not silently assign it to another project.
- Save a session opening entry when project work starts. Append or amend records after every substantive action or result, including emails, takeoffs, RFIs, estimate changes, reviews and approvals. Do not wait until the end of the chat, end of the day or billing.
- Save human timer state at start, pause, resume, switch and finish, with durable checkpoints during active work. Proposed application checkpoint interval: 60 seconds. A checkpoint is recording, not evidence that the whole interval is chargeable.
- Save AI job start and completion/failure when observable, with only the timing and usage the execution platform actually supplies.
- Maintain the session summary and project totals as work progresses, and reconcile them at session close. Derive totals from accepted underlying records rather than independently typing totals.
- Each successful write must return or verify the project ID, ledger file ID, event/interval ID and save timestamp. Store the Drive record link in the app project record and session context so later chats resume the same history.
- A record is **SAVED TO DRIVE** only after the Drive write succeeds. Local capture or an app-only save is **PENDING DRIVE SYNC**. Failed writes are **DRIVE SAVE FAILED** and must remain visible with the last successful save time and pending entry count.
- On connection failure, retain entries durably, retry with stable IDs and replay once access returns. Warn Rick promptly. End-of-session summaries must identify any unsaved entries. Do not describe the recording requirement as satisfied while Drive updates are pending.
- Before billing, reconcile the Drive ledger with queued and app events; resolve missing writes, duplicates and project mismatches. Hold billing approval for affected entries until their Drive evidence is saved and verified.

Continuous updating means event-by-event capture and timer checkpoints while an instrumented session is active. It does not mean an AI can monitor unconnected apps or keep running after a chat ends without a deployed automation. Record unsupported coverage explicitly.

| Object | Minimum fields |
| --- | --- |
| Project | Stable project ID; client ID; name; Drive project folder ID; Drive ledger file ID and link; last successful Drive save and pending sync count; project timezone; engagement reference; currency; approved billing basis and rate version when set. |
| Activity event | Stable event ID; project ID; actor; activity category; source system and source ID; occurrence and capture times; action; outcome; evidence link and revision; parent task; capture status. |
| Human interval | Interval ID; person; session and task IDs; start and stop; pause or allocation details; duration; measured/declared/estimated/unknown basis; evidence; review status. |
| AI job | Job ID; agent; parent/root job; start and finish; execution/wait measurements when available; model/tools; outcome; usage/cost provenance; input/output references. |
| Billing allocation | Allocation ID; linked event/interval/job IDs; approved quantity and unit; rate and currency; charge basis; excluded amount or time and reason; approver/time; invoice ID and line ID. |
| Audit amendment | Original record ID; before/after values; reason; actor; timestamp; approval where needed. |

### Identity and completeness

Carry the project ID through chat sessions, emails, takeoff lines, RFIs, quotes, estimate revisions and exported reports. Link to the relevant work package and task where available; preserve existing estimate identifiers. If a project cannot be resolved confidently, capture to an unassigned queue and exclude it from billing until resolved.

Use a stable source event key to deduplicate imports. Draft creation, draft revision and email sending are distinct events, but importing the same sent email twice must not create duplicate work or time. One time interval can support several outputs without being charged several times.

### Reliable writes and correction

Logging must use durable storage, safe retries and idempotent writes. Show pending, saved and failed states. Preserve failed capture in a recovery queue, notify Rick and retry safely. A successful AI answer does not prove that its ledger write succeeded.

Keep an append-only event history. Correct mistakes by a linked amendment or superseding record; preserve original values. Approved invoice snapshots remain locked. Later corrections create an adjustment or new version rather than rewriting an issued invoice.

### Privacy and access

Capture only project-relevant evidence. Restrict clients and users to authorised projects. Store references without credentials or expiring access tokens; preserve source access controls. Back up the ledger and support tested restoration. Set retention and deletion policy before production use.

## 3 Mason operating instructions and billing

### Instruction block for Mason

At the start of substantive project work, resolve the client and project ID from the current context and records. If ambiguous, ask only for the missing project identity. Resolve and reuse the project’s Drive ledger, then reuse the active session or open a new one through the logging interface. Save the session opening entry to Drive. Do not repeatedly ask Rick to identify a known project.

Log each substantive action and outcome to the project’s Drive ledger as it occurs. Confirm persistence after each write, not only at chat completion. Include source references, controlling revisions, actor, task and evidence status. Record drafts as drafts, sent messages as sent only after verified sending, and proposed changes separately from implemented changes. Preserve existing approval gates.

Capture your execution metrics only from supplied telemetry. Do not estimate Rick’s time from message spacing, your own run time or the complexity of an output. If timing is absent, record the activity with unknown duration and invite a short declaration during session review.

Continuously update the project’s Drive records during work. At natural completion, reconcile the session and save a compact summary to the same ledger: work completed, human time by basis, AI metrics available, outputs, unresolved items and capture failures. If the write fails, state that the log is not saved. Never claim durable recording unless the logging interface confirms it.

Do not approve charges, change agreed rates, send invoices or contact anyone merely because an activity is logged. Rick retains the charge decision. If no Drive logging interface is available, preserve an unsaved ledger draft in the recovery queue and disclose the limitation. An unsaved draft is a fallback, not compliance with the mandatory Drive recording requirement.

### Billing review

Prepare a work review by client, project, date and activity category. Show recorded human time, estimated or unknown time, AI work and costs separately. Include nonchargeable work, corrections, internal development and written-off time with reasons. Rate and currency must come from the approved engagement, not a model assumption.

Rick can approve, reduce, defer or exclude a charge without changing the recorded work history. For hourly work, calculate the approved billable duration at the approved rate. Fixed-fee and value-based work retain the same evidence trail but do not convert automatically into hours. Any AI charge requires an explicit agreed billing basis; absent that, retain it as internal delivery evidence.

Store exact durations and apply any agreed rounding once at the defined billing aggregation level. Preview exclusions, unresolved overlaps, missing project links and prior invoicing before approval. Prevent the same approved time or charge allocation being invoiced twice.

### Illustrative example

A takeoff has 35 measured human minutes and an AI job with 12 minutes elapsed. Rick then spends 10 measured minutes reviewing it and five drafting an RFI. The human total is 50 minutes; the AI job remains separate. The RFI and takeoff both link to those intervals, without duplicating them.

If Rick chooses to charge 40 minutes, retain 50 recorded minutes, 40 approved chargeable minutes and 10 excluded minutes with his reason. The invoice line links to the approved allocation and its underlying takeoff, revision and RFI evidence.

### Outputs

Provide a project timeline, daily and project time summaries, a billing review, an invoice evidence schedule and CSV/XLSX export. Totals must reconcile to the underlying approved allocations. Keep internal telemetry separate from the client-facing schedule unless its disclosure is appropriate and authorised.

## 4 Implementation and acceptance

### Build the smallest dependable version first

First implement the canonical Drive ledger and reliable write/recovery interface, human timer, manual declarations, evidence links, amendments and billing review/export. Then connect Mason chats, AI job telemetry, email events, takeoffs, RFIs and estimate revisions. For every connection, document what it can observe and what remains manual.

Use one project as a pilot through a complete work session and billing review. Do not treat capture coverage as complete until the connected sources reconcile. This document specifies behaviour; it does not establish that the current app or chat platform supports every hook.

### Acceptance checks

| Case | Required result |
| --- | --- |
| Pause and resume | 20 active minutes, a 10-minute break and 15 active minutes produce 35 human minutes. |
| AI in parallel | A 15-minute AI job runs while Rick spends 10 minutes on another project. Human time is allocated once; AI remains separate. |
| Duplicate event | The same email imported twice creates one source event and no extra duration. |
| Several outputs | One 30-minute interval supports a takeoff and an RFI; human total stays 30 minutes. |
| Missing telemetry | A known activity with no timing has unknown duration and cannot masquerade as measured time. |
| Crash or disconnection | The reliable portion is preserved; the uncertain tail is flagged and not auto-approved. |
| Unknown project | The event enters the unassigned queue and cannot enter a bill until resolved. |
| Write failure | Capture failure is visible; retry saves once; neither Mason nor the app claims an unsaved log is saved. |
| Billing adjustment | 50 recorded minutes and 40 approved minutes remain distinguishable with the exclusion reason. |
| Invoice integrity | Previously invoiced allocation cannot be reused; later amendment leaves the issued snapshot intact. |
| Evidence navigation | Each sample charge opens the correct source event, output and revision with authorised access. |
| New chat on existing project | Reuses the same Drive folder and ledger IDs; prior records remain available. |
| Continuous Drive capture | Session opening, substantive actions and timer state changes are saved before session close; active timer checkpoints meet the configured interval. |
| Drive outage and recovery | Entries remain pending and visible; restored access replays each once; no false saved status is shown. |
| Project separation | Switching projects writes to the correct separate ledgers without duplicating human intervals. |
| Billing persistence | An affected entry cannot be approved for billing while its Drive write is unresolved. |
| Export reconciliation | Exported project totals equal the ledger and approved billing allocation totals. |

### Rollout and source control

Maintain approved Mason operating logic and schemas in rick-ai-os. Maintain production implementation in the existing Blackline application project/repository. Keep project evidence and correspondence in their current authoritative homes. This review document is a handoff artifact, not a competing live ledger.

After implementation, test a fresh Mason session and the full pilot billing cycle. Baseline only after critical capture, time integrity, write recovery and invoice mapping checks pass. Record unsupported connections explicitly rather than promising universal automatic coverage.

### Recommended next action

Use this specification for a controlled implementation task in the existing estimating app: establish the project Drive ledger, reliable continuous writes and timer first, then connect Mason to that same record. This directly prevents future billing reviews from relying on retrospective guesses.

### Basis of this specification

Prepared from Rick’s request of 14 October 2026, the supplied Atlas Runtime Pack and Blackline estimating evidence and approval principles. Timing thresholds and application behaviour above are proposed design choices, not verified capabilities or existing billing agreements.


### Revision history

- v1.1 — 14 October 2026: Rick requires all project work to be recorded in Drive against the relevant project and continuously updated. Drive is mandatory; app-only or chat-only records do not satisfy persistence.
- v1.0 — Initial specification.
