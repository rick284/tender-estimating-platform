# 3Bears Outbound Data & Privacy Release Standard

**Revision:** 1  
**Date:** 7 September 2026  
**Status:** Current source standard  
**Owner:** 3Bears Projects  
**Applies to:** Master Estimating project and any system, workflow or person preparing external project communications

## 1. Purpose

This standard controls what information may leave the 3Bears estimating environment and how that release is checked.

It applies to information sent or shared by:

- email
- attachment
- RFQ
- tender submission
- report
- spreadsheet
- PDF
- cloud link
- shared folder
- message
- copied text
- exported data
- automated workflow
- AI assisted workflow
- any other external communication channel

The objective is to prevent unnecessary, unauthorised or accidental disclosure of:

- personal information
- client confidential information
- project confidential information
- internal commercial information
- supplier and subcontractor confidential information
- third party information
- restricted information

The core operating principle is:

> Right information -> right recipient -> right purpose -> minimum necessary disclosure -> human accountability.

A second permanent rule applies:

> Access to information does not itself create authority to disclose it.

---

## 2. Relationship to Other Estimating Standards

This standard is a supporting control for the Master Estimating system.

It must be read with:

- `3Bears_Master_Estimating_Email_Standard_Rev3.md`
- current approved Estimate Master Prompt
- current approved Estimating Triple Verification Standard
- current Master Estimate Workbook
- current client issue / Estimate Basis & Tender Report standard where applicable

This standard does not replace estimating verification.

A commercially correct estimate can still fail the release gate if the wrong information is sent to the wrong person.

---

## 3. Legal and Governance Basis

For New Zealand operations, this standard is designed to support compliance with the Privacy Act 2020 and the Information Privacy Principles.

Particular operational relevance includes:

- Principle 5: reasonable safeguards for storage and security of personal information
- Principle 11: limits on disclosure of personal information
- Principle 12: controls applying to certain disclosures of personal information outside New Zealand

Every New Zealand organisation must have a privacy officer or person fulfilling that function.

This document is an operational control standard and does not replace project specific legal advice where required.

Official reference source:

- New Zealand Office of the Privacy Commissioner
- https://www.privacy.org.nz/

Where operations occur in Australia or another jurisdiction, the applicable local privacy and data requirements must also be checked.

---

## 4. Definitions

### Personal information

Information about an identifiable individual.

This may include:

- name
- personal email
- private phone number
- home address
- correspondence
- photographs
- insurance information
- identity details
- financial information
- access information
- employment information
- other information capable of identifying or describing an individual

### Project confidential information

Information supplied or created for a project that is not intended for unrestricted public release.

Examples:

- drawings
- specifications
- quantities
- site constraints
- tender documents
- programme information
- consultant reports
- client instructions
- project correspondence

### Commercial sensitive information

Information that could prejudice 3Bears, a client, contractor, supplier or subcontractor if improperly disclosed.

Examples:

- labour costs
- plant costs
- internal rates
- margins
- overhead
- profit
- tender strategy
- negotiation targets
- supplier comparison
- competitor pricing
- alternative tender scenarios
- raw risk analysis

### Restricted information

Information that should not be externally released without explicit authority.

Examples:

- passwords
- access credentials
- identity documents
- bank details
- highly private correspondence
- health information
- legal advice
- insurance claim records
- other information classified RED by a project or organisational control

### Third party information

Information belonging to or concerning a person or organisation other than 3Bears and the intended recipient.

---

## 5. Data Classification

Every material outbound communication must be assessed using the highest classification present.

| Classification | Description | Examples | Default release |
|---|---|---|---|
| PUBLIC / BUSINESS | Information intended for public or normal business use | published product data, supplier business contact, public specification | GREEN |
| PROJECT CONFIDENTIAL | Legitimate project information not intended for unrestricted circulation | drawings, quantities, programme, scope, site constraints | GREEN or AMBER |
| COMMERCIAL SENSITIVE | Information capable of affecting commercial position | internal rates, margin, profit, tender strategy, supplier comparison | AMBER / normally withhold |
| PERSONAL INFORMATION | Information about an identifiable individual | personal email, phone, address, correspondence | AMBER / minimum necessary |
| RESTRICTED | Information requiring explicit approval or special handling | bank details, ID, credentials, insurance claim detail, legal advice, health information | RED / HOLD by default |

Where information fits more than one classification, use the highest control level.

---

## 6. Minimum Necessary Disclosure Test

Before any external release, ask:

1. What is the business purpose?
2. Who is the intended recipient?
3. What decision or action does the recipient need to take?
4. What exact information is required for that action?
5. Can less information achieve the same purpose?
6. Can personal information be removed or generalised?
7. Can an exact address be replaced with a suburb or region?
8. Can a source file be replaced with a clean extract?
9. Can an entire email thread be replaced with a short factual summary?
10. Can internal pricing be removed?
11. Does the recipient have a legitimate reason to see third party information?

If the same business result can be achieved with less information, use less information.

---

## 7. Purpose Limitation

Information obtained for one project or business purpose must not be reused in a new outbound context merely because it is accessible.

Examples:

- a homeowner's phone number obtained for site access should not automatically be included in a supplier RFQ
- a supplier quote obtained for internal estimate checking should not be forwarded to a competing supplier
- client correspondence should not be sent to a subcontractor unless the subcontractor needs the relevant content
- information from a prior project should not be reused as current project information without a valid basis

Where uncertain, withhold and review.

---

## 8. Recipient Verification

Before release, verify:

- recipient name
- organisation
- email or destination
- project relationship
- need to know
- CC recipients
- BCC recipients
- reply all recipients
- external domains
- any similarly named contacts

For higher sensitivity communications, perform the recipient check again immediately before send.

If recipient identity or entitlement is uncertain, status is RED / HOLD.

---

## 9. Residential Address Control

Residential project addresses can identify an individual or household and may carry privacy and security sensitivity.

Use the least specific location necessary.

Examples:

### Regional budget pricing

Use:

`Hobsonville, Auckland`

rather than a full street address where the supplier only needs the region to establish pricing.

### Delivery or site inspection

A full address may be used where the supplier genuinely needs it to:

- price freight
- inspect access
- deliver material
- attend site
- coordinate approved work

Do not include resident contact details merely because the site address is being disclosed.

---

## 10. Personal Contact Detail Control

Personal phone numbers and email addresses are not default RFQ information.

Disclose them only where:

- the recipient genuinely needs direct contact
- the disclosure is appropriate for the purpose
- the release has been approved where necessary

Where possible, use:

- 3Bears contact details
- the contractor's project contact
- a generic project role
- a controlled site contact

rather than a homeowner or occupant's private details.

---

## 11. Supplier and Subcontractor Confidentiality

Do not disclose one supplier or subcontractor's confidential information to another competing party unless specifically authorised.

Normally withhold:

- quoted price
- quote document
- discounts
- exclusions
- commercial conditions
- negotiation position
- contact strategy
- evaluation notes
- comparison ranking
- internal comments

For quote comparison, retain this information internally.

When seeking a competing quote, issue the underlying scope and specification rather than another bidder's commercial response.

---

## 12. Internal Commercial Information

The following information is internal by default:

- Resource Rate Library
- Resource Build Up
- internal labour rates
- internal plant rates
- payroll assumptions
- productivity judgement notes
- raw Tender Build Up
- overhead recovery
- profit
- margin
- internal contingency or residual risk logic
- raw Risk Truth
- internal adjudication
- supplier comparison
- unapproved alternatives
- negotiation targets

Do not release these items unless:

1. the procurement model requires open book disclosure, or
2. Rick specifically approves the release, or
3. another approved commercial authority directs release

Even in open book situations, release only the information contractually required.

---

## 13. Attachment Sanitisation

Source files can disclose substantially more than their visible front page.

Before external release, inspect where applicable:

- hidden worksheets
- hidden rows
- hidden columns
- formulas
- cell comments
- notes
- document comments
- tracked changes
- revision history
- author metadata
- internal filenames
- embedded files
- embedded objects
- personal data
- supplier pricing
- commercial assumptions
- alternative prices
- internal review content
- unrelated project information

Preferred external formats are purpose built extracts or clean PDFs where practical.

Do not assume that converting to PDF removes all confidential information. Review the rendered output.

---

## 14. Master Estimate Workbook External Release

The Master Estimate Workbook is an internal controlling cost model by default.

Do not send it externally unless external workbook issue is deliberately required.

Where workbook issue is required:

1. confirm the recipient
2. confirm the commercial model requires it
3. create an approved external issue version where practical
4. remove or protect internal only information
5. check hidden sheets and formulas
6. verify no supplier confidential data is exposed
7. verify no unrelated personal data is exposed
8. record the release
9. retain the issued revision

A normal quote request should not receive the Master Estimate Workbook.

---

## 15. Email Thread Control

Email chains can contain historic personal, commercial and unrelated information.

Before forwarding or replying externally:

1. review the full visible chain
2. review quoted text
3. review all original recipients
4. review embedded contact details
5. review historic attachments
6. remove irrelevant content
7. create a clean new email where safer

Never assume a thread is appropriate to forward in full simply because one part of it is relevant.

---

## 16. Batch RFQ and Automation Rules

Batch communication must be treated as a controlled release process.

### Required setup

Before a batch is sent, define:

- approved recipient list
- approved purpose
- approved merge fields
- approved attachment set
- approved data classification
- message template
- reviewer
- release status

### Mandatory controls

1. Each supplier receives only information intended for that supplier.
2. Competing supplier addresses are not visible to one another.
3. Each attachment is positively matched to its recipient.
4. Merge fields are fully resolved.
5. No personal information is included unless required.
6. No other supplier's quote or pricing is included.
7. No internal commercial data is included.
8. A sample message is reviewed before release.
9. The communication register is updated where required.
10. A failed match or unresolved field stops the batch.

### Hard stop conditions

Batch release status is RED if:

- recipient mapping is uncertain
- an attachment mapping is uncertain
- a merge field is blank or unresolved
- restricted data is present
- competing recipients are exposed
- the wrong project is referenced
- source material has not been reviewed
- external release status is incomplete

---

## 17. AI Assisted Workflow Rules

AI may assist with:

- drafting
- summarising
- extracting
- classifying
- comparing
- preparing attachments
- identifying potential privacy issues
- preparing RFQs

AI access does not create disclosure authority.

Before AI assisted content leaves the business:

1. verify source facts
2. verify recipient
3. verify purpose
4. verify classification
5. verify personal information
6. verify commercial information
7. verify attachments
8. verify no unrelated connected account information has been introduced
9. verify generated assumptions are not presented as facts
10. complete human release review where required

The human reviewer remains accountable for the external release.

---

## 18. Outbound Data & Privacy Release Gate

The release gate should be incorporated into the Master Estimating workflow and, where practical, the Master Estimate Workbook Tender Release QA.

Minimum gate fields:

| Gate item | Required outcome |
|---|---|
| Recipient verified | Yes |
| Recipient organisation verified | Yes |
| Business purpose stated | Yes |
| Minimum necessary disclosure confirmed | Yes |
| Highest data classification recorded | PUBLIC / PROJECT / COMMERCIAL / PERSONAL / RESTRICTED |
| Personal information present | Yes / No |
| Personal information necessary | Yes / No / N/A |
| Commercial sensitive information present | Yes / No |
| Third party confidential information present | Yes / No |
| Restricted information present | Yes / No |
| Attachments reviewed | Yes |
| Email history reviewed where applicable | Yes / N/A |
| Batch mapping verified where applicable | Yes / N/A |
| External release status | GREEN / AMBER / RED |
| Reviewer | Name |
| Review date | Date |
| Exception / approval reference | Reference / N/A |

---

## 19. Release Status Rules

### GREEN

Release may proceed when:

- recipient is verified
- business purpose is clear
- information is necessary
- attachments are reviewed
- no unresolved restricted information exists
- controlled personal or project information is appropriate for the recipient
- no third party confidentiality conflict exists

### AMBER

Human approval is required where:

- personal information is necessary
- commercially sensitive information must be disclosed
- a full residential address is required in a context that increases sensitivity
- third party information is necessary
- a project specific exception is required
- open book disclosure is required
- overseas disclosure requires additional assessment
- another judgement based release issue exists

The approval and reason must be recorded.

### RED / HOLD

Do not release where:

- recipient is wrong or uncertain
- restricted information has no approval
- personal information is unnecessary
- competing supplier information is exposed
- internal commercial information is exposed unintentionally
- an attachment contains uncontrolled hidden data
- batch recipient or attachment mapping is uncertain
- a reply or forward contains unreviewed sensitive history
- the purpose is unclear
- the release gate is incomplete
- required approval has not been obtained

---

## 20. Outbound Communication Register

Use a register where communication volume, sensitivity or audit value makes it appropriate.

Recommended minimum fields:

| Field | Description |
|---|---|
| Communication ID | Unique ID |
| Date | Date released |
| Project | Project name or code |
| Purpose | Business purpose |
| Recipient | Person |
| Organisation | Organisation |
| Channel | Email / link / report / other |
| Data Classification | Highest classification |
| Attachments | Files released |
| Personal Data Present | Yes / No |
| Commercial Sensitive Data Present | Yes / No |
| Restricted Data Present | Yes / No |
| Release Status | GREEN / AMBER / RED |
| Reviewed By | Human reviewer |
| Approval Reference | Where applicable |
| Message Reference | Gmail/thread/message identifier where available |
| Notes | Exceptions or context |

Do not duplicate full sensitive content in the register merely for audit purposes.

A reference to the controlled source is preferable.

---

## 21. Master Workbook Integration

The Master Estimate Workbook should not become a repository for unnecessary personal information.

Recommended integration is a release control, not a full personal data database.

Add or maintain a Tender Release QA item equivalent to:

> External issue pack reviewed for personal information, client confidential information, internal commercial information, third party information and unnecessary attachments. Minimum necessary disclosure confirmed.

Recommended status:

- Not Started
- GREEN
- AMBER
- RED

A RED privacy or data release status blocks external issue.

Do not create a second estimate or cost chain to implement this control.

---

## 22. Source File and Document Handling

When a project file contains personal or confidential information:

- keep the source intact where it forms part of the project record
- do not alter evidential source files merely to make external release easier
- create a controlled external extract where required
- preserve original source and revision
- record what was issued
- avoid creating uncontrolled duplicate copies

This aligns with the estimating system's existing source traceability and change control philosophy.

---

## 23. External Links and Shared Folders

Before sending a cloud link or shared folder:

1. confirm the link target
2. confirm folder contents
3. confirm access permissions
4. confirm whether access is recipient specific or public
5. remove unrelated files
6. check personal and commercial information
7. confirm expiry settings where available and appropriate
8. confirm the recipient cannot browse into unrelated project areas

A link to a folder is a disclosure of everything the recipient can access through that link, not merely the file named in the email.

---

## 24. Overseas Disclosure Check

Where personal information may be disclosed to a person or organisation outside New Zealand, perform an additional privacy review.

Do not assume that normal domestic release rules are sufficient.

Consider:

- who the overseas recipient is
- why the information is being disclosed
- what protections apply
- whether the recipient is acting only as a service provider or is receiving the information for its own use
- whether additional authority or safeguards are required

Escalate uncertainty to the nominated privacy officer or appropriate adviser.

---

## 25. Privacy Officer

3Bears Projects should nominate a person responsible for the privacy officer function.

The role should include:

- maintaining privacy awareness
- overseeing this release standard
- handling privacy concerns
- coordinating access or correction requests
- assessing privacy incidents
- liaising with the Office of the Privacy Commissioner where required
- approving or escalating unusual disclosure decisions

The role does not require every ordinary email to be individually approved.

The purpose is to create a clear owner for privacy governance and exceptions.

---

## 26. Privacy Incident and Mis-Send Response

If information is sent to the wrong recipient or an inappropriate disclosure is suspected:

1. stop further release
2. do not conceal the incident
3. record what was sent
4. record who received it
5. record when it occurred
6. attempt practical containment where possible
7. notify the nominated privacy officer immediately
8. assess the nature and sensitivity of the information
9. assess the likely harm
10. determine whether client, affected person, insurer, lawyer, regulator or other notification is required
11. preserve the evidence and decision record
12. identify the process failure
13. implement corrective action

Do not rely on message recall as proof that information was recovered.

---

## 27. Retention and Duplication

Do not create unnecessary copies of personal information.

Where a communication can be referenced by:

- message ID
- controlled source file
- project document reference

prefer the reference rather than copying full content into multiple registers.

Retention and deletion must remain consistent with project, contractual, legal, insurance and company record requirements.

---

## 28. Human Review Thresholds

### Routine GREEN communication

Examples:

- public supplier enquiry
- generic pricing request without personal information
- normal client correspondence using already approved project data

May proceed under the normal email quality check.

### AMBER communication

Examples:

- personal contact details
- exact residential address where not obviously necessary
- commercially sensitive material
- third party information
- sensitive reply or forward
- unusual external sharing

Requires explicit human review before send.

### RED communication

Examples:

- restricted information
- uncertain recipient
- unreviewed confidential attachment
- possible competitor data leak
- batch mapping failure
- credential or bank information
- unexplained private information

Must not be sent until the RED condition is removed or formally resolved.

---

## 29. Practical RFQ Example

### Information normally appropriate

A drainage supplier may reasonably need:

- project name or controlled project code
- region
- pipe type
- diameter
- class
- quantity
- fittings
- relevant specification
- delivery timing
- freight requirement
- required quote validity

### Information normally unnecessary

The same supplier would not normally need:

- homeowner's private email
- homeowner's phone number
- entire client email chain
- client's budget
- 3Bears labour cost
- 3Bears margin
- another supplier's quote
- raw Risk Truth
- unrelated drawings
- insurance correspondence

If the supplier later needs the site address for freight or inspection, provide it at that point if appropriate.

---

## 30. System Design Requirement

Any future estimating automation capable of sending, sharing or exporting external information should be designed so that:

1. source access and disclosure authority are separate concepts
2. recipient is explicit
3. purpose is explicit
4. outbound fields are controlled
5. attachments are controlled
6. personal data can be detected or flagged
7. commercial sensitive content can be flagged
8. RED items block release
9. AMBER items require human judgement
10. batch jobs cannot leak one recipient's data to another
11. an audit record can be retained
12. the system defaults to minimum necessary disclosure

Privacy should be designed into the workflow, not left entirely to a final visual check.

---

## 31. Standing Instruction

For all external communications produced from the Master Estimating project:

> Use only the information reasonably necessary for the recipient's stated purpose. Protect personal information, client confidentiality, internal commercial information, supplier confidentiality and third party data. Verify the recipient and attachments. Treat replies, forwards, shared links and batch communications as new disclosures. RED means HOLD.

---

## 32. Review and Change Control

Review this standard when:

- a privacy incident occurs
- a batch email process changes
- a new communication automation is introduced
- a new external data connector is introduced
- the Master Estimate Workbook release architecture changes
- relevant privacy law or official guidance materially changes
- live use exposes a gap

Changes should record:

- revision
- date
- reason
- reviewer
- material control change

---

## 33. Revision History

| Revision | Date | Change |
|---|---|---|
| Rev1 | 7 September 2026 | Initial outbound privacy, confidentiality, batch RFQ and data release standard for the Master Estimating system |
