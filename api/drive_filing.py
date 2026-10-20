"""Small decision and scope files the app saves for the next chat to read: new text files in `00 Project Admin / Reviews and Decisions` of the linked job folder.
Create only: nothing is overwritten or deleted. Best effort and always reported: when Drive cannot be written to, the caller says the record is in the app only."""
from __future__ import annotations
from typing import Any

import httpx
from fastapi import HTTPException

import drive_client as dc
import drive_index

SCOPE_FIELDS = (("owner", "Owner"), ("treatment", "Treatment"), ("source", "Source"), ("cost_refs", "Cost lines"), ("register_refs", "Register"), ("quote_refs", "Quotes"), ("basis", "Basis"), ("action", "Action"))


async def file_to_reviews(user: dict[str, Any], tender: dict[str, Any], filename: str, text: str) -> dict[str, Any]:
    """Save `text` as a NEW file in Reviews and Decisions. Returns {name, link} or {error}."""
    from routes_drive import _integration, _token
    link = tender.get("drive_folder")
    doc = await _integration(user)
    if not (link and doc and dc.can_write_anywhere(doc.get("scopes", ""))):
        return {"error": "Drive has not been given permission to save files here, so this is recorded in the app only."}
    try:
        tok = await _token(user)
        top = await dc.list_children(tok, link["id"])
        admin = next((x for x in top if x["mimeType"] == dc.FOLDER_MIME and drive_index._has_number(x["name"], "00")), None)
        if not admin:
            return {"error": "The job folder has no 00 Project Admin folder, so no file was saved."}
        dest = await dc.find_folder(tok, admin["id"], "Reviews and Decisions") or await dc.create_folder(tok, "Reviews and Decisions", admin["id"])
        f = await dc.create_text_file(tok, filename, dest["id"], text)
        return {"name": f.get("name", filename), "link": f.get("webViewLink", "")}
    except HTTPException as e:
        return {"error": str(e.detail)}
    except dc.DriveError as e:
        return {"error": str(e)}
    except httpx.HTTPError:
        return {"error": "The connection to Google Drive dropped, so no file was saved."}


def _cell(v: Any) -> str:
    return " ".join(str(v or "").split()).replace("|", "/")


def scope_markdown(job: str, rev_label: str, who: str, at: str, note: str, changes: list[dict[str, Any]], items: list[dict[str, Any]]) -> str:
    """The CURRENT scope (every item, in order) plus what changed in this revision. Nothing here is priced."""
    out = [f"# SCOPE: CURRENT, {job}", "", f"Revision: {rev_label}", f"Saved by: {who or 'Estimator'} in Blackline QSi Pro", f"When: {at}", "",
           "**This is the current scope. It replaces any earlier scope document or table the chat wrote. Read this file first, and treat the table below as the scope.**", ""]
    if note:
        out += ["## Reason for the change", note, ""]
    sc = [c for c in changes if c.get("target") == "scope"]
    if sc:
        out += ["## What changed in this revision", ""]
        for c in sc:
            if c["field"] == "added":
                out.append(f"- ADDED: {c['label']} ({c['after']})")
            elif c["field"] == "removed":
                out.append(f"- REMOVED: {c['label']}")
            else:
                out.append(f"- CHANGED: {c['label']}, {c['field']}: {c['before'] or '(blank)'} -> {c['after'] or '(blank)'}")
        out.append("")
    out += [f"## Current scope ({len(items)} items)", "", "| Ref | Group | Item | Owner | Treatment | Detail | Source |", "|---|---|---|---|---|---|---|"]
    for it in items:
        out.append(f"| {_cell(it.get('ref'))} | {_cell(it.get('group'))} | {_cell(it.get('title'))} | {_cell(it.get('owner'))} | {_cell(it.get('treatment'))} | {_cell(it.get('detail'))[:300]} | {_cell(it.get('source'))[:160]} |")
    extra = [it for it in items if any(it.get(k) for k, _ in SCOPE_FIELDS[3:])]
    if extra:
        out += ["", "## Links and notes", ""]
        for it in extra:
            bits = [f"{lab}: {_cell(it.get(k))}" for k, lab in SCOPE_FIELDS[3:] if it.get(k)]
            out.append(f"- {it.get('ref')} {_cell(it.get('title'))}: " + "; ".join(bits))
    out += ["", "Treatment words: PRICED / ALLOWANCE / PC SUM / EXCLUDED / BY OTHERS / UNRESOLVED. UNRESOLVED means the scope item is not yet decided or priced.",
            "This file was created by the app. Nothing was sent to anyone.", ""]
    return "\n".join(out)


def revision_markdown(job: str, rev_label: str, rev_n: int, parent_n: int | None, who: str, at: str, note: str, all_in: Any, changes: list[dict[str, Any]]) -> str:
    """What one saved revision changed, for the chat. Every change (not only scope) with before and after. The app's revision is a newer working copy than any workbook the chat holds."""
    out = [f"# REVISION NOTE: {job}", "", f"Revision saved in Blackline QSi Pro: {rev_label} (revision {rev_n}" + (f", built on revision {parent_n}" if parent_n else "") + ")",
           f"Saved by: {who or 'Estimator'}", f"When: {at}", f"All-in price excl. GST after this revision: {all_in if all_in is not None else 'not available'}", "",
           "**The app's saved revisions hold the estimator's latest working copy. A workbook the chat built earlier does not include these changes. Do not overwrite them: build from the app's current figures, or ask Rick which to follow.**", ""]
    if note:
        out += ["## Reason", note, ""]
    out += [f"## Changes ({len(changes)})", "", "| Area | Item | Field | Before | After |", "|---|---|---|---|---|"]
    for c in changes[:300]:
        out.append(f"| {_cell(c.get('target'))} | {_cell(c.get('label'))[:90]} | {_cell(c.get('field'))} | {_cell(c.get('before'))[:60]} | {_cell(c.get('after'))[:60]} |")
    if len(changes) > 300:
        out.append(f"\n(+{len(changes) - 300} more changes not listed.)")
    out += ["", "This file was created by the app. Nothing was sent to anyone.", ""]
    return "\n".join(out)
