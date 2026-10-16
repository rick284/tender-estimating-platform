# 3Bears Master Estimating Email Standard

**Revision:** 3  
**Date:** 7 September 2026  
**Status:** Current source standard  
**Owner:** 3Bears Projects  
**Applies to:** Master Estimating project and all external construction estimating correspondence

## 1. Purpose

This document controls the presentation, sender identity, privacy, confidentiality and release behaviour for emails produced through the 3Bears Master Estimating system.

It applies to:

- client emails
- tender correspondence
- supplier and subcontractor enquiries
- quote requests
- tender clarifications
- estimating updates
- commercial review messages
- report delivery
- construction related outreach
- batch RFQs
- replies and forwards containing project information

The objective is that every email:

1. looks and reads as though Rick wrote it personally from his laptop
2. contains only information that is necessary for the business purpose
3. protects personal information, project confidentiality, commercial information and third party data
4. is traceable and defensible if reviewed later

Where this document conflicts with a newer approved 3Bears brand, privacy, security or communication standard, the newer approved standard controls.

This standard must be read together with:

- `3Bears_Outbound_Data_Privacy_Release_Standard_Rev1.md`
- the current approved Estimate Master Prompt
- the current approved Estimating Triple Verification Standard
- the controlling Master Estimate Workbook release controls

---

## 2. Core Rules

### 2.1 Natural business email

Emails should look as though Rick wrote them personally from his laptop.

The presentation should be clean, professional and natural.

Do not turn normal business correspondence into a marketing email.

### 2.2 Minimum necessary disclosure

Only send information reasonably necessary for the stated business purpose.

Access to information inside the estimating system does not itself create authority to disclose it.

### 2.3 Need to know

Before including project, personal, commercial or third party information, ask:

> Does this recipient genuinely need this information to complete the purpose of this email?

If the answer is no, remove it.

If the answer is uncertain, withhold it and escalate for review.

### 2.4 No automatic forwarding of source material

Do not automatically forward:

- entire email threads
- whole tender folders
- complete client correspondence chains
- internal estimate workbooks
- unrelated drawings
- other suppliers' quotations
- internal review notes
- source files containing more information than the recipient requires

Build a clean outbound pack containing only the information needed.

---

## 3. Sender Identity

For new 3Bears estimating correspondence, use:

`rick@3bearsprojects.co.nz`

If an existing email thread began from another approved mailbox, keep the reply inside that original thread unless Rick instructs otherwise.

Do not send external estimating correspondence from an unintended personal or test account.

---

## 4. Writing Standard

Write in a professional, experienced, curious and approachable voice.

Use natural contractions where Rick would normally use them.

Examples include:

- I've
- I'd
- we're
- that's
- there's
- can't
- don't
- you're

Avoid stiff repeated constructions such as `I am`, `I have` and `I would` when the contracted form reads more naturally.

Do not use hyphens in normal 3Bears prose unless technically necessary in a product name, drawing reference, specification, email address, filename or established technical term.

Write for the phone first while making sure the same message reads naturally on desktop.

Use short paragraphs and natural sentence lengths.

Do not force line breaks inside sentences to control wrapping.

---

## 5. Email Presentation Standard

Use minimal rich text formatting.

The email should resemble a normal message written in Gmail or Outlook.

Use a standard readable font such as Arial.

Use natural paragraph spacing.

Do not use:

- banners above the body
- coloured buttons
- decorative panels
- marketing blocks
- campaign style presentation
- additional logos above or beside the written signature

The only logo treatment in the approved construction email is inside the approved footer image beneath the mission statement.

---

## 6. Approved Closing and Signature

The approved construction closing and signature is:

Regards,  
Rick Jones  
3Bears Projects  
Construction Estimating, Tender & Commercial Review  
*AI assisted. Evidence based. Human verified.*  
rick@3bearsprojects.co.nz

The following mission statement appears below the signature in smaller italic text:

> We do not add AI because a business should have AI. We use it where it can materially improve the business, with evidence, human judgement and accountability at every step.

The approved branded construction footer image sits beneath the mission statement.

---

## 7. Signature Spacing Rule

The signature is one tight block.

There is no separate first name sign off.

`Regards,` is followed immediately by `Rick Jones` on the next line.

There is no blank line between:

- Regards and Rick Jones
- Rick Jones and 3Bears Projects
- the remaining signature lines

The mission statement may have a small visual separation beneath the email address.

The footer image may have a small visual separation beneath the mission statement.

Do not add any other logo above the footer.

---

## 8. Approved Footer Asset

Use this file as the approved construction email footer:

`3Bears_Projects_Construction_Email_Footer_Approved.png`

The footer uses the original 3Bears logo artwork.

Only the former legal suffix has been removed.

The emblem, 3BEARS lettering, font, proportions and overall identity must remain unchanged.

The word PROJECTS must retain the right alignment used in the approved logo.

For normal email use, use the black logo on a white background because most recipients are expected to use a light email theme.

Do not redesign or regenerate the logo for routine email use.

---

## 9. Exact Visual Order

The end of a normal estimating email should appear in this order:

Body text

Regards,  
Rick Jones  
3Bears Projects  
Construction Estimating, Tender & Commercial Review  
*AI assisted. Evidence based. Human verified.*  
rick@3bearsprojects.co.nz

> We do not add AI because a business should have AI. We use it where it can materially improve the business, with evidence, human judgement and accountability at every step.

Approved construction footer image

---

## 10. HTML Sending Pattern

When sending through a connected Gmail account, use a plain text fallback and a minimal HTML body.

The HTML structure should keep the signature lines tight and preserve the visual hierarchy without looking like a campaign template.

Use this pattern as the starting point:

```html
<div style="font:14px Arial,Helvetica;color:#222222;">
  <p style="margin:0 0 16px 0;">Hi [Name],</p>

  <p style="margin:0 0 16px 0;">[Paragraph one]</p>

  <p style="margin:0 0 16px 0;">[Paragraph two]</p>

  <p style="margin:0 0 16px 0;">[Paragraph three]</p>

  <p style="margin:0;">Regards,</p>
  <div><strong>Rick Jones</strong></div>
  <div>3Bears Projects</div>
  <div>Construction Estimating, Tender &amp; Commercial Review</div>
  <div><em>AI assisted. Evidence based. Human verified.</em></div>
  <div><a href="mailto:rick@3bearsprojects.co.nz">rick@3bearsprojects.co.nz</a></div>

  <p style="margin:14px 0 12px 0;"><small><em>We do not add AI because a business should have AI. We use it where it can materially improve the business, with evidence, human judgement and accountability at every step.</em></small></p>

  <img src="[APPROVED FOOTER IMAGE]" width="720" alt="3Bears Projects construction footer" style="display:block;border:0;">
</div>
```

The footer image should be embedded inline in the email rather than appearing as a normal file attachment when the sending method supports inline images.

---

## 11. Plain Text Fallback

If rich text or the footer image cannot be used, the email must still contain the complete written signature:

```text
Regards,
Rick Jones
3Bears Projects
Construction Estimating, Tender & Commercial Review
AI assisted. Evidence based. Human verified.
rick@3bearsprojects.co.nz

We do not add AI because a business should have AI. We use it where it can materially improve the business, with evidence, human judgement and accountability at every step.
```

---

## 12. Outbound Data Classification

Before an external email is sent, identify the highest data classification contained in the body, quoted thread and attachments.

| Classification | Typical examples | Default treatment |
|---|---|---|
| PUBLIC / BUSINESS | Published specifications, supplier business details, generic scope description, public product data | GREEN |
| PROJECT CONFIDENTIAL | Drawings, quantities, programme, project scope, site constraints, tender documentation | GREEN or AMBER depending on recipient and purpose |
| COMMERCIAL SENSITIVE | Internal rates, resource build ups, margin, profit, tender strategy, negotiation position, competitor or supplier quotes | AMBER and normally withheld |
| PERSONAL INFORMATION | Names, private phone numbers, private email addresses, residential details, correspondence concerning identifiable individuals | AMBER and disclose only where necessary and authorised |
| RESTRICTED | Bank details, identity documents, insurance claim records, health information, legal advice, passwords, credentials, highly private correspondence | RED / HOLD unless specifically approved |

The full classification and release rules are controlled by `3Bears_Outbound_Data_Privacy_Release_Standard_Rev1.md`.

---

## 13. Supplier and Subcontractor RFQ Rules

For supplier and subcontractor quote requests:

1. Give the recipient the scope, quantity, specification, programme and delivery information needed to quote.
2. Use the least specific location that still allows an accurate quote.
3. Provide an exact residential address only where needed for delivery, access, inspection, logistics or another legitimate quote requirement.
4. Do not include a homeowner or occupant's private contact details unless there is a clear need and authority to do so.
5. Do not include our internal estimate, labour cost, overhead, profit, markup, Risk Truth notes or tender strategy.
6. Do not include another supplier's price, quotation or negotiation position.
7. Do not expose the supplier distribution list.
8. Send separate emails to competing suppliers unless there is an approved reason for a shared distribution.
9. Do not use CC for competing quote recipients.
10. If a bulk process is used, each supplier must receive only their own intended message and attachments.
11. Do not attach every drawing simply because they are available.
12. Build a purpose specific RFQ pack.

---

## 14. Recipient Control

Before sending:

1. confirm the intended recipient
2. confirm the recipient's organisation
3. confirm the email address
4. check autocomplete has not selected a similarly named contact
5. confirm CC and BCC fields
6. confirm the recipient is entitled to receive the information
7. for sensitive material, perform a second recipient check immediately before send

A wrong recipient is a release failure even if the email content itself was correct.

---

## 15. Reply and Forward Control

A reply or forward is treated as a fresh external disclosure.

Before sending a reply or forward:

- inspect the visible message
- inspect the quoted history
- inspect attachments
- inspect inline images
- inspect any forwarded contact details
- remove unrelated or sensitive historic content
- confirm all current recipients should see the full chain

Do not assume information is safe to resend merely because it already exists in the thread.

Where the current message requires only a small portion of prior correspondence, create a clean new message or quote only the relevant passage.

---

## 16. Attachment Release Control

Before attaching a file, ask:

> Does the recipient need this exact file, or only some information from it?

Check for:

- hidden worksheets
- hidden rows or columns
- internal cost sheets
- formula tabs
- comments and notes
- tracked changes
- document properties where material
- internal revision history
- supplier quotes
- client correspondence
- personal information
- bank details
- internal Risk Truth data
- internal overhead and profit
- unrelated project information
- embedded attachments or objects
- filenames that reveal unnecessary information

Where practical, issue a clean PDF, extract or purpose built RFQ schedule instead of the source workbook.

Do not send a Master Estimate Workbook externally unless the procurement model specifically requires it and the file has been approved for external issue.

---

## 17. Personal Information Control

Personal information should not be copied into an external email merely because it is available in:

- Gmail
- project files
- drawings
- an intake record
- a previous project
- connected contacts
- correspondence
- an AI context
- the Master Estimate Workbook

Only use personal information where it is necessary for the current business purpose and its disclosure is appropriate.

Where an individual's identity is not required, use a role or project description instead.

Examples:

- use `site contact` rather than publishing a private number unless the supplier needs to coordinate access
- use `Hobsonville, Auckland` rather than a full residential address where regional pricing is sufficient
- use `client` rather than the homeowner's name where identity adds no value

---

## 18. Commercial Confidentiality Control

Do not disclose internal commercial information by accident.

Normally withhold:

- internal labour cost
- plant ownership economics
- resource charge out logic
- overhead recovery
- profit
- margin
- raw Resource Build Up
- internal Tender Build Up
- alternate internal tender scenarios
- supplier comparison sheets
- competitor quotes
- negotiation targets
- raw Risk Truth scoring
- internal risk strategy
- adjudication notes
- unapproved commercial alternatives

Open book procurement requirements must be confirmed before any of this information is released.

---

## 19. AI Use and Disclosure Control

AI may assist with drafting, extracting, checking and preparing communications.

AI assistance does not remove human accountability for disclosure.

Before sending externally:

1. verify facts, names, quantities, dates and attachments
2. verify no private or confidential information has been inserted from unrelated context
3. verify that information available through connected accounts is necessary for the current recipient
4. verify that inferred or generated statements are not presented as project facts without evidence
5. complete the outbound data release check

The approved signature statement remains:

*AI assisted. Evidence based. Human verified.*

---

## 20. Batch Email and Automated RFQ Control

Batch or automated external correspondence carries higher release risk.

Before a batch is released:

1. define the recipient list
2. define the purpose
3. define the approved data fields
4. define the approved attachment set
5. prohibit cross recipient data leakage
6. prohibit exposing competing recipient addresses
7. complete a sample message review
8. verify merge fields against each recipient
9. confirm personal and commercial information is minimised
10. log the release where the Outbound Communication Register is required

A batch send must stop if:

- a merge field is unresolved
- an attachment cannot be positively matched to its recipient
- recipient identity is uncertain
- data classification is RED
- a restricted item is detected
- the release gate is incomplete

---

## 21. Outbound Communication Register

Use the Outbound Communication Register for:

- batch RFQs
- sensitive client issue
- material tender issue
- commercial review delivery
- issue of personal information
- issue of restricted or specially approved information
- any communication where an audit trail is prudent

Minimum fields:

| Field | Requirement |
|---|---|
| Communication ID | Unique identifier |
| Date | Sent or proposed send date |
| Project | Project name or code |
| Purpose | Why the communication is being sent |
| Recipient | Intended recipient |
| Organisation | Recipient organisation |
| Data Classification | Highest classification in issue |
| Attachments | Files released |
| Personal Data Present | Yes / No |
| Commercial Sensitive Data Present | Yes / No |
| Restricted Data Present | Yes / No |
| Release Status | GREEN / AMBER / RED |
| Reviewed By | Human reviewer |
| Message Reference | Gmail/thread/message reference where available |
| Notes | Exceptions, approvals or limitations |

Do not duplicate full sensitive content in the register where a message reference is sufficient.

---

## 22. Normal Estimating Email Behaviour

The body of the email changes to suit the actual purpose.

The signature does not.

Examples include:

- sending an estimate for review
- requesting a supplier quote
- asking for missing tender information
- sending a tender clarification
- delivering a pricing workbook
- explaining an estimate assumption
- sending an estimate report
- providing a commercial review
- following up a client query
- construction related outreach

Do not force outreach language into normal project correspondence.

Use the same signature and presentation while keeping the body appropriate to the relationship and task.

---

## 23. New Email Versus Reply

For a new email, use the full approved signature and footer.

For a normal reply inside an active thread, the full signature may still be used where it looks natural and useful.

For very short back and forth replies, the footer image may be omitted if repeating it would make the conversation visually heavy.

Do not omit the written identity where the recipient may reasonably need to know who is replying.

Privacy and data release checks apply equally to new emails, replies and forwards.

---

## 24. Subject Line Standard

Subject lines should be plain, useful and specific.

Good examples include:

- Hobsonville Road estimate review
- Pricing request for drainage pipe
- Tender clarification for [Project Name]
- Revised estimate for [Project Name]
- Commercial review for [Project Name]

Avoid promotional or exaggerated subject lines.

Do not place unnecessary personal or sensitive information in the subject line.

---

## 25. Attachment Naming Standard

Name attachments clearly and professionally.

Make the filename understandable without opening the email.

Where practical, include:

- project name or code
- document purpose
- revision

Do not include unnecessary personal information in filenames.

Do not attach files the recipient does not need.

When sending a revised file, make it clear in the body what changed.

---

## 26. Approval Rule

Any material change to the construction email format, signature, logo treatment, footer image, mission statement, privacy release behaviour or overall presentation requires a new test email to Rick before live use.

Send format tests to:

`rick.2wolves@outlook.com`

Rick should review desktop and mobile view where practical.

Routine emails using the approved format do not require a fresh presentation test every time.

A privacy or data release exception may still require specific approval under the Outbound Data & Privacy Release Standard.

---

## 27. Quality Check Before Sending

Before sending an external estimating email, check:

### Recipient and purpose

1. Is the correct recipient selected?
2. Is the correct sender account being used?
3. Is the purpose of the email clear?
4. Does each recipient need the information being sent?
5. Are CC and BCC fields correct?

### Content

6. Does the body sound like Rick rather than a generic business template?
7. Are the facts, figures, project names and claims supported?
8. Is the subject useful and specific?
9. Does the subject avoid unnecessary personal or sensitive information?
10. Are paragraphs short enough to read comfortably on a phone?

### Privacy and confidentiality

11. What is the highest data classification in the email?
12. Is any personal information included?
13. Is that personal information necessary for this purpose?
14. Is any commercial sensitive information included?
15. Is any third party information included?
16. Is any restricted information included?
17. Has unnecessary information been removed?
18. If this is a reply or forward, has the quoted history been reviewed?
19. Are competing suppliers hidden from one another?

### Attachments

20. Are the correct attachments included?
21. Does the recipient need every attachment?
22. Have hidden sheets, comments, internal costs and unrelated data been checked?
23. Are filenames appropriate?
24. Is the attachment intended for this exact recipient?

### Presentation

25. Are there any accidental hyphens in normal 3Bears prose?
26. Is there only one logo in the email?
27. Is the logo contained inside the approved footer image?
28. Does PROJECTS retain the approved right alignment?
29. Is there no separate Rick sign off above the full signature?
30. Is there no blank line between Regards and Rick Jones?
31. Is there no blank line between Rick Jones and 3Bears Projects?
32. Are all signature lines tight and consecutive?
33. Is the mission statement present in quieter italic text?
34. Does the footer image display correctly?

### Release

35. Has the Outbound Data & Privacy Release Gate been completed where required?
36. Is release status GREEN, or is an AMBER exception explicitly approved?
37. If the format materially changed, has Rick approved a test email?
38. If a communication register entry is required, has it been recorded?

---

## 28. Release Status

### GREEN

The recipient, purpose, content and attachments are verified.

Only necessary information is included.

No unresolved restricted data issue exists.

Email may be sent.

### AMBER

A legitimate business need exists but the message contains personal, commercially sensitive or otherwise controlled information that requires human judgement.

The limitation and approval must be explicit before sending.

### RED / HOLD

Do not send.

Examples include:

- wrong or uncertain recipient
- unexplained personal information
- restricted data without approval
- competitor or supplier confidential data exposed to another supplier
- internal estimate workbook attached unintentionally
- unresolved merge field
- mismatched attachment
- visible bulk recipient list that should be private
- unknown data classification
- unreviewed sensitive email chain
- release gate incomplete where required

---

## 29. Standing Instruction for the Master Estimating Project

When asked to draft or send an external construction email from the Master Estimating project:

1. use this standard automatically unless Rick gives a specific instruction otherwise
2. apply `3Bears_Outbound_Data_Privacy_Release_Standard_Rev1.md`
3. use the minimum information necessary for the recipient's purpose
4. do not infer permission to disclose information merely because it exists in project context or a connected account
5. stop and seek human approval where the release status is RED or where an AMBER exception requires judgement

The default outcome should be a clean, natural business email with the approved 3Bears signature, correct recipient, controlled attachments and minimum necessary disclosure.

---

## 30. Revision History

| Revision | Date | Change |
|---|---|---|
| Rev1 | Prior issue | Initial construction estimating email standard |
| Rev2 | 6 September 2026 | Approved sender identity, signature, footer, presentation and quality control standard |
| Rev3 | 7 September 2026 | Added privacy, personal information, commercial confidentiality, recipient, attachment, reply/forward, batch RFQ, AI disclosure and outbound release controls |
