# Brief for the Mason chat: email thread filing for Blackline QSi Pro

Paste everything below the line into the Mason chat. Rev1, 20 Oct 2026.

---

You are working on the Mason senior estimator instruction set. Your task is to add an instruction for filing email threads so that the Blackline QSi Pro app can show them, and then to follow it on a real job.

## Why
The app has no mailbox connection and will not get one. It reads files that you save in the job's Google Drive folder, read only. Rick wants every email thread, quote and RFI for a job to be traceable in one place without opening several systems. Anything you do not save to Drive, the app cannot show.

## Before you write anything
1. Read the existing instructions first: START_HERE, the Email Standard (Rev5), the Outbound Release Gate, 17_Job_Filing_Standard and 18_One_Step_One_Chat. Do not contradict them. Where the new instruction needs something they do not say, add it as an extension and name the file it extends.
2. Read `instructions/Email_Thread_Files.md` from the QSi Pro repo (rick284/tender-estimating-platform). It is the layout the app reads today. Treat it as a requirement. If you think it should change, say so to Rick; do not quietly diverge, because the app's reader is built to that layout.

## Write the instruction
Create the next free numbered file in `instructions/senior-estimator/` (for example `19_Email_Thread_Filing.md`) and list it in START_HERE. Keep to the style and length of the other numbered files. It must cover:
- Where threads go: `04 RFIs Correspondence and Clarifications / 04.1 Emails In` (received) and `04.2 Emails Out - DRAFT ONLY` (drafts). Attachments stay in `02` (tender documents) or `03` (quotes); the thread file names them and links to them.
- One file per thread, named `YYYY-MM-DD_In_<Sender>_<Subject>` (`_Out_` for drafts). Google Doc or .md/.txt both work.
- Inside: one block per message separated by `=== NEXT MESSAGE ===`, each starting with `Source: <Sender (company)>, <d-Mon-yyyy>, subject: <subject>`, `Original Gmail message ID: <id>`, and `Attachment: <name>; <name>`, then the message text word for word (no signatures or footers).
- References: write `RFI-06`, `Q-03` (quote register), `SC-012` (scope item), `DOC-004`, `RT01`, `MR-01` exactly as the app prints them, wherever the email relates to them.
- Rules: never overwrite or delete a thread file (a later reply is a new file or a new block); drafts are marked `DRAFT - NOT SENT` on the first line; sending is only ever Rick's decision, outside the app; keep the Email Log in `00 Project Admin / Registers and Logs` up to date.
- How this fits the steps: say at which steps threads are filed (at the latest, when a quote or RFI is logged), and that the Job Record notes "emails filed up to <date>".

## Then do the email work on a real job
Use the test job: Drive > Dave Stewart > `329 Hobsonville Road - APP WORKFLOW TEST - NOT LIVE`. Rick has said nothing may be sent and the live job folder must not be touched.
1. Search the 3Bears Gmail (read only) for the threads on this job (Dave Stewart's 04-Sep-2026 enquiry and follow-ups, supplier and subcontractor replies).
2. Save each thread to `04.1 Emails In` in the layout above. Keep the two test transcriptions already there; add new files rather than editing them.
3. Update the Email Log and the filing index.
4. Report to Rick: how many threads were filed, which references you linked, and anything you could not file and why.
Do not send, reply, label, move or delete any email.

## Check your work
Before telling Rick it is done, re-read your own files against `Email_Thread_Files.md`: names, the `=== NEXT MESSAGE ===` separators, the `Source:` lines, and the references. Then ask Rick to open the Emails page in the app and press "Refresh from Drive". Report what the app shows, including any threads it did not pick up.

Finally, save the new instruction file in the Mason senior estimator repository (rick284/Mason-Senior-Estimator, branch `claude/mason-senior-estimator-review-pxs6m9`) and in the ChatGPT Mason source folder, so both copies are identical.
