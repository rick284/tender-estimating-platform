# Instructions for external AI assistants

This folder holds the documents that tell an outside AI how to produce estimates that the **Blackline QSi Pro** app can import.

| File | Purpose |
|---|---|
| `Workbook_Builder_Instructions.md` | The full instruction set: rules, process, the exact sheet/column contract the app reads, the logs (email, RFI, quotes, documents, decisions), a self-check and a handover template. |

## How to use it (Rick)

1. Open a new chat with the external AI (one job per chat).
2. Upload: **(a)** the Master Estimate Workbook template, **(b)** `Workbook_Builder_Instructions.md` (or give it the GitHub link if it can read the repository), **(c)** the job's tender documents and emails.
3. Paste the starter prompt from section 13 of the instructions.
4. When it delivers the completed `.xlsx` and handover note, upload the workbook in the app (Tenders → New tender → Upload a workbook).
5. The app tells you what it could not read (Overview → "Imported from the workbook"). Note anything the AI got wrong and add it to the handover section "Problems with these instructions" — that is how the document improves.

## Keeping it up to date

- Edit the file in GitHub; record each change in the revision history at the end of the document.
- If a change touches the **sheet/column contract** (section 5) or the logs (section 8), the app's importer must change with it. Tell the developer assistant so both move together.
- Do not put client names, prices or tender documents in this folder. The repository should stay **private**; if the external AI cannot read a private repository, upload the file to the chat instead.
