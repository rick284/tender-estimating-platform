# Saving email threads so the app can show them (instruction for Mason)

Rev1, 20 Oct 2026. The app has no mailbox connection. It reads the text files you save in the job's Drive folder, read only. If a thread is not saved here, the app cannot show it.

## Where
- Received emails: `04 RFIs Correspondence and Clarifications / 04.1 Emails In /`
- Drafts we wrote (never sent from here): `04 RFIs Correspondence and Clarifications / 04.2 Emails Out - DRAFT ONLY /`
- Attachments stay where they belong (quotes in `03`, tender documents in `02`). The thread file only names them and links to them.

## One file per thread
File name: `YYYY-MM-DD_In_<Sender>_<Subject>` (or `_Out_` for a draft). A Google Doc or a .md/.txt file both work. The date is the first message's date.

Inside, one block per message, separated by a line `=== NEXT MESSAGE ===`. Each block starts with:

```
Source: <Sender name (company)>, <d-Mon-yyyy>, subject: <subject>
Original Gmail message ID: <id>
Attachment: <file name>; <file name>
```
then the message text. Keep the substantive text word for word; leave out signatures and footers.

## References
Write the app's references in the text wherever they apply, exactly as the app prints them: `RFI-06`, `Q-03` (quote register), `SC-012` (scope item), `DOC-004` (document), `RT01`, `MR-01`. The app turns these into links: green when the item exists in the estimate, amber when it does not (a useful warning).

## Rules
- Never overwrite or delete a thread file: a later reply goes in a new file or as a new block with a new message ID (the app keeps the newest saved copy of each file).
- Mark drafts clearly (`DRAFT - NOT SENT` in the first line). Sending is always Rick's decision, outside the app.
- Keep the Email Log (Registers and Logs) up to date; the app will later check it against the files.
