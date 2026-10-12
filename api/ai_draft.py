"""AI drafting of register items from document text. Pure functions: prompt building, output checking, conversion to estimate edits.

The AI only DRAFTS. It proposes tender-register items (documents, RFIs, assumptions, exclusions, inclusions, risks). It never proposes a quantity, rate,
price or date, and nothing it proposes enters the estimate until the estimator accepts it into an edit draft and saves a revision with a reason.

Every proposal must carry verbatim source quotes (file, page). The platform checks each quote against the stored page text: a quote that is not really in
that file and page marks the item UNVERIFIED and it cannot be accepted (rule: every item has provenance; the AI may not invent evidence).
"""
from __future__ import annotations
import re
from typing import Any

PROMPT_VERSION = "register-v1"
KINDS = ("document", "rfi", "assumption", "exclusion", "inclusion", "risk")
MIN_QUOTE = 12                       # compact characters; shorter quotes prove nothing

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": list(KINDS)},
            "title": {"type": "string"},
            "detail": {"type": "string"},
            "impact": {"type": "string"},
            "rag": {"type": "string", "enum": ["AMBER", "RED"]},
            "basis": {"type": "string", "enum": ["quoted", "gap"]},
            "evidence": {"type": "array", "items": {"type": "object", "properties": {
                "file_id": {"type": "string"}, "page": {"type": "integer"}, "quote": {"type": "string"}},
                "required": ["file_id", "page", "quote"], "additionalProperties": False}},
        }, "required": ["kind", "title", "detail", "impact", "rag", "basis", "evidence"], "additionalProperties": False}},
        "coverage_notes": {"type": "string"},
    },
    "required": ["items", "coverage_notes"], "additionalProperties": False,
}

SYSTEM = """You are assisting a senior NZ civil and commercial estimator. You are DRAFTING ONLY. The estimator reviews and approves everything you propose.

Your job: read the document extracts and propose entries for the tender register: documents (drawing / specification / report numbers, titles, revisions and dates that appear in the text), RFIs, assumptions, exclusions, inclusions and risks.

Non-negotiable rules:
1. Do not guess. If information the estimate needs is missing, raise an RFI. An RFI states what is missing or unclear, where you expected to find it, why it matters (quantity, method, temporary works, sequencing, cost, risk or programme) and the decision impact if it stays unresolved (allowance required, exclusion required, or stop estimate). Put the whole of that in `detail` and `impact`.
2. If documents contradict each other, do not resolve it. Raise an RFI quoting both sides.
3. Never state a quantity, rate, price, programme duration or date that is not written in the quoted text. You do not price anything and you do not measure anything.
4. Every item based on the documents (`basis` = "quoted") must carry one or more `evidence` entries: the `file_id` exactly as given, the `page` number, and a `quote` copied EXACTLY, word for word, from that page. Never paraphrase inside a quote. Quotes should be one to three sentences. If you cannot quote it, you cannot propose it that way.
5. Use `basis` = "gap" only for an RFI about information that is absent from the documents provided (for example a document that should exist but was not supplied). Say where you expected to find it. `evidence` may be empty for a gap, but include a quote wherever one shows the gap.
6. Stay inside the work package and scope described. Where another party's work touches it, record the interface as an exclusion or an RFI that says who owns it.
7. `rag`: AMBER by default. RED only where a conflict or missing information blocks a responsible price. Never GREEN: nothing you draft is verified.
8. Do not repeat items already in the register (listed below). Prefer fewer, sharper items to many vague ones. Plain, practical language, written for site and commercial readers.
9. Respond with JSON only, matching the schema. `coverage_notes` says in a sentence or two which documents you read and anything you could not read (scanned pages, drawings without text)."""


def _compact(s: str) -> str:
    return re.sub(r"[\W_]+", "", s or "", flags=re.UNICODE).lower()


def build_user_message(meta: dict[str, str], docs: list[dict[str, Any]], existing: list[dict[str, Any]]) -> str:
    """docs: [{file_id, name, revision, pages:[{n, text}]}]. existing: current register items (ref, kind, title)."""
    lines = ["TENDER CONTEXT"]
    for k in ("project", "location", "client", "job_type", "work_package", "estimate_level", "contract_type", "pricing_basis", "documents_provided", "known_scope"):
        if meta.get(k):
            lines.append(f"{k.replace('_', ' ').capitalize()}: {meta[k]}")
    lines += ["", "ALREADY IN THE REGISTER (do not repeat)"]
    lines += [f"- {x['kind']} {x['ref']}: {x['title']}" for x in existing[:200]] or ["- (nothing yet)"]
    lines += ["", "DOCUMENT EXTRACTS"]
    for d in docs:
        lines.append(f"=== file_id: {d['file_id']} | name: {d['name']}" + (f" | revision: {d['revision']}" if d.get("revision") else "") + " ===")
        for p in d["pages"]:
            if p["text"].strip():
                lines += [f"[page {p['n']}]", p["text"].strip(), ""]
    return "\n".join(lines)


def verify(items: list[dict[str, Any]], docs: list[dict[str, Any]], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check the AI's output. Adds to each item: evidence[i].verified, status (verified | gap | unverified | duplicate), problems[]."""
    pages = {d["file_id"]: {p["n"]: _compact(p["text"]) for p in d["pages"]} for d in docs}
    names = {d["file_id"]: d["name"] for d in docs}
    have = {(x["kind"], _compact(x["title"])) for x in existing}
    out, seen = [], set()
    for raw in items:
        it = {k: raw.get(k, "") for k in ("kind", "title", "detail", "impact", "rag", "basis")}
        it["kind"] = it["kind"] if it["kind"] in KINDS else "rfi"
        it["rag"] = "RED" if it["rag"] == "RED" else "AMBER"
        it["title"] = str(it["title"]).strip()[:300]
        problems, ev_out = [], []
        for e in raw.get("evidence") or []:
            fid, pg, quote = str(e.get("file_id", "")), e.get("page"), str(e.get("quote", ""))
            q = _compact(quote)
            ok = False
            if fid not in pages:
                problems.append(f"Quote cites a file that was not supplied ({fid[:20]})")
            elif len(q) < MIN_QUOTE:
                problems.append("A quote is too short to prove anything")
            elif not isinstance(pg, int) or pg not in pages[fid]:
                problems.append(f"Page {pg} does not exist in {names[fid]}")
            elif q not in pages[fid][pg]:
                problems.append(f"The quote is not on page {pg} of {names[fid]}")
            else:
                ok = True
            ev_out.append({"file_id": fid, "file": names.get(fid, ""), "page": pg, "quote": quote, "verified": ok})
        it["evidence"] = ev_out
        quoted = it["basis"] != "gap"
        if not it["title"]:
            problems.append("No title")
        if quoted and not ev_out:
            problems.append("Based on the documents but gives no source quote")
        if (it["kind"], _compact(it["title"])) in have or (it["kind"], _compact(it["title"])) in seen:
            status = "duplicate"
        elif problems or (quoted and not all(e["verified"] for e in ev_out)):
            status = "unverified"
        else:
            status = "gap" if (not quoted and not ev_out) else "verified"
        seen.add((it["kind"], _compact(it["title"])))
        it["status"], it["problems"] = status, problems
        out.append(it)
    return out


def to_edit(item: dict[str, Any], key: str) -> dict[str, Any]:
    """The register edit that accepting this item would add to the estimator's edit draft. Source quotes travel in the item text so provenance is kept."""
    src = "\n".join(f"- {e['file']} p.{e['page']}: “{e['quote'].strip()}”" for e in item["evidence"] if e["verified"])
    note = "AI-drafted from the documents; verified quotes:\n" + src if src else "AI-drafted: no source quote (information absent from the documents supplied)."
    detail = f"{item['detail'].strip()}\n\n{note}"[:3000]
    action = item["impact"].strip()[:3000]
    return {"target": "register", "op": "add", "key": key, "value": {"kind": item["kind"], "title": item["title"], "detail": detail, "action": action,
                                                                    "rag": item["rag"], "status": "OPEN" if item["kind"] == "rfi" else ""}}
