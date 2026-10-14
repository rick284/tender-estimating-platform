# Instructions for external AI assistants

This folder holds the documents that tell an outside AI how to produce estimates that the **Blackline QSi Pro** app can import.

| File | Purpose |
|---|---|
| `Master_Estimate_Workbook_TEMPLATE.xlsx` | The clean master workbook: every formula in place, no job data, the logs added. Upload this with the instructions. |
| `NZ_Weather_Risk_Estimating_Tool_Rev2.xlsx` | The approved NZ weather tool (NIWA normals). Upload it as well when the AI is to do the weather run. |
| `Workbook_Builder_Instructions.md` | The full instruction set: rules, process, the exact sheet/column contract the app reads, the logs (email, RFI, quotes, documents, decisions), a self-check and a handover template. |

## How to use it (Rick)

1. Open a new chat with the external AI (one job per chat).
2. Upload: **(a)** `Master_Estimate_Workbook_TEMPLATE.xlsx` (and `NZ_Weather_Risk_Estimating_Tool_Rev2.xlsx` if it is to run the weather), **(b)** `Workbook_Builder_Instructions.md` (or give it the GitHub link if it can read the repository), **(c)** the job's tender documents and emails.
3. Paste the starter prompt from section 13 of the instructions.
4. When it delivers the completed `.xlsx` and handover note, upload the workbook in the app (Tenders → New tender → Upload a workbook).
5. The app tells you what it could not read (Overview → "Imported from the workbook"). Note anything the AI got wrong and add it to the handover section "Problems with these instructions" — that is how the document improves.

## Keeping it up to date

- Edit the file in GitHub; record each change in the revision history at the end of the document.
- If a change touches the **sheet/column contract** (section 5) or the logs (section 8), the app's importer must change with it. Tell the developer assistant so both move together.
- Do not put client names, prices or tender documents in this folder. The repository should stay **private**; if the external AI cannot read a private repository, upload the file to the chat instead.

## Rebuilding the template

The template is generated, not hand-edited, so it can be rebuilt after the method changes:

`python engine/tools/make_master_template.py <a real job workbook> instructions/Master_Estimate_Workbook_TEMPLATE.xlsx`

(The donor workbook supplies the styles, validations and formulas; every job-specific value is removed.) `engine/tests/test_master_template.py` fills a small job into the committed template, recalculates it in LibreOffice and checks that the platform imports it and reconciles to the workbook's own totals. Run it after any change.
