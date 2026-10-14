"""AI drafting of register items from document text. Pure functions: prompt building, output checking, conversion to estimate edits.

The AI only DRAFTS. It proposes tender-register items (documents, RFIs, assumptions, exclusions, inclusions, risks). It never proposes a quantity, rate,
price or date, and nothing it proposes enters the estimate until the estimator accepts it into an edit draft and saves a revision with a reason.

Every proposal must carry verbatim source quotes (file, page). The platform checks each quote against the stored page text: a quote that is not really in
that file and page marks the item UNVERIFIED and it cannot be accepted (rule: every item has provenance; the AI may not invent evidence).
"""
from __future__ import annotations
import re
from typing import Any

PROMPT_VERSION = "register-v2"
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
9. Quoted facts and your own inferences are different things. `detail` states what the documents say; if you are inferring a consequence, say "Inferred:" at the start of that sentence. Never present an inference as a quotation.
10. Supplier and subcontractor quotes belong on the Quotes page, not the register: do not propose a document entry for a quote. Do propose RFIs, exclusions or risks that a quote's qualifications raise.
11. The extracts may be one part of a larger tender folder; earlier parts have already produced the items listed above. Only add what is new.
12. Respond with JSON only, matching the schema. `coverage_notes` says in a sentence or two which documents you read and anything you could not read (scanned pages, drawings without text)."""


# ---- scope drafting -------------------------------------------------------------------------------------------------
SCOPE_KINDS = ("scope",)
SCOPE_EXTRA = ("group", "owner", "treatment")
SCOPE_PROMPT_VERSION = "scope-v1"
SCOPE_GROUPS = ("Permanent works", "Enabling works", "Access and site establishment", "Temporary works", "Testing and inspection", "Reinstatement and handover",
                "Preliminaries and management", "Interface with others", "Other")
SCOPE_OWNERS = ("OWN WORKS", "SUBCONTRACT", "CLIENT", "OTHERS", "SHARED", "TBC")
SCOPE_TREATMENTS = ("EXCLUDED", "BY OTHERS", "UNRESOLVED")      # the AI never says a thing is PRICED, an allowance or a PC sum: pricing is the estimator's decision

SCOPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"},
            "detail": {"type": "string"},
            "group": {"type": "string", "enum": list(SCOPE_GROUPS)},
            "owner": {"type": "string", "enum": list(SCOPE_OWNERS)},
            "treatment": {"type": "string", "enum": list(SCOPE_TREATMENTS)},
            "impact": {"type": "string"},
            "rag": {"type": "string", "enum": ["AMBER", "RED"]},
            "basis": {"type": "string", "enum": ["quoted", "gap"]},
            "evidence": {"type": "array", "items": {"type": "object", "properties": {
                "file_id": {"type": "string"}, "page": {"type": "integer"}, "quote": {"type": "string"}},
                "required": ["file_id", "page", "quote"], "additionalProperties": False}},
        }, "required": ["title", "detail", "group", "owner", "treatment", "impact", "rag", "basis", "evidence"], "additionalProperties": False}},
        "coverage_notes": {"type": "string"},
    },
    "required": ["items", "coverage_notes"], "additionalProperties": False,
}

SCOPE_SYSTEM = """You are assisting a senior NZ civil and commercial estimator. You are DRAFTING ONLY. The estimator reviews and approves everything you propose.

Your job: read the document extracts and list the SCOPE REQUIREMENTS of the job: every thing the work needs, so nothing is missed when the price is built. Cover permanent works, enabling works (demolition, clearance, services), access and site establishment, temporary works, testing and inspection, reinstatement and handover, preliminaries and management, and interfaces with other parties.

Non-negotiable rules:
1. One requirement per line, in plain practical language (for example "Temporary retaining to the cut face", "Producer statements and as-builts at completion"). Do not copy whole paragraphs.
2. You do not price, measure or choose a pricing treatment. `treatment` is only "EXCLUDED" or "BY OTHERS" when the documents say so in so many words, otherwise "UNRESOLVED". The estimator decides how each requirement is priced.
3. `owner` is who delivers it according to the documents: OWN WORKS (the contractor pricing), SUBCONTRACT, CLIENT, OTHERS (another party), SHARED, or TBC when the documents do not say. Never guess an owner: use TBC.
4. Every requirement that comes from the documents (`basis` = "quoted") must carry `evidence`: the `file_id` exactly as given, the `page` number, and a `quote` copied EXACTLY, word for word, from that page (one to three sentences). If you cannot quote it, you cannot propose it that way.
5. Use `basis` = "gap" only for a requirement you expect the job to have that the documents do not mention (for example testing that is normally required). Say in `detail` where you expected it to be mentioned and why you think it applies, and start that sentence with "Inferred:". Put what the estimator should confirm in `impact`. `evidence` may be empty for a gap.
6. Quoted facts and your own inferences are different: never present an inference as a quotation. If documents contradict each other on a requirement, do not resolve it: say so in `detail`, quote both sides, and set `rag` to RED.
7. `rag`: AMBER by default. RED only where a conflict or missing information blocks a responsible price. Never GREEN.
8. Do not repeat requirements already in the scope schedule (listed below) or ones already proposed. Prefer fewer, sharper lines to many vague ones.
9. Respond with JSON only, matching the schema. `coverage_notes` says in a sentence or two which documents you read and anything you could not read (scanned pages, drawings without text)."""


def build_scope_message(meta: dict[str, str], docs: list[dict[str, Any]], existing: list[dict[str, Any]]) -> str:
    """Like build_user_message, with the project brief as context and the existing scope lines (ref, title) in place of the register."""
    lines = ["PROJECT BRIEF"]
    for k in ("project", "job_summary", "scope", "location", "client", "owner", "consultants", "contract_type", "pricing_basis", "known", "unknown", "site_constraints", "programme"):
        if meta.get(k):
            lines.append(f"{k.replace('_', ' ').capitalize()}: {meta[k]}")
    lines += ["", "ALREADY IN THE SCOPE SCHEDULE (do not repeat)"]
    lines += [f"- {x['ref']}: {x['title']}" for x in existing[:300]] or ["- (nothing yet)"]
    body = build_user_message({}, docs, [])
    return "\n".join(lines) + "\n\n" + body.split("ALREADY IN THE REGISTER (do not repeat)\n- (nothing yet)\n\n", 1)[-1]


def to_scope_edit(item: dict[str, Any], key: str) -> dict[str, Any]:
    """The scope edit that accepting this proposal would add to the estimator's draft. Quotes travel in `source`/`basis` so provenance is kept."""
    src = "; ".join(f"{e['file']} p.{e['page']}" for e in item["evidence"] if e["verified"])
    quotes = "\n".join(f"- {e['file']} p.{e['page']}: “{e['quote'].strip()}”" for e in item["evidence"] if e["verified"])
    note = "AI-drafted from the documents; verified quotes:\n" + quotes if quotes else "AI-drafted: no source quote (inferred; not stated in the documents supplied)."
    return {"target": "scope", "op": "add", "key": key, "value": {
        "title": item["title"][:300], "detail": item["detail"].strip()[:3000], "group": item.get("group") or "Other", "owner": item.get("owner") or "TBC",
        "treatment": item.get("treatment") or "UNRESOLVED", "source": src[:500], "basis": note[:3000], "action": item["impact"].strip()[:3000]}}


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


def plan_batches(docs: list[dict[str, Any]], budget: int, max_files: int) -> list[list[dict[str, Any]]]:
    """Split documents into batches that each stay under `budget` characters and `max_files` files.
    A single document larger than the budget is cut at page boundaries into parts. Parts keep file_id and carry only their own pages.
    docs: [{file_id, name, revision, pages:[{n, text}]}] -> [[doc-part, ...], ...]. Documents with no text are left out (the caller reports them)."""
    parts: list[dict[str, Any]] = []
    for d in docs:
        cur, size = [], 0
        for p in d["pages"]:
            n = len(p["text"])
            if cur and size + n > budget:
                parts.append({**d, "pages": cur}); cur, size = [], 0
            cur.append(p); size += n
        if cur and size:
            parts.append({**d, "pages": cur})
    batches: list[list[dict[str, Any]]] = []
    cur, size = [], 0
    for part in parts:
        n = sum(len(p["text"]) for p in part["pages"])
        if cur and (size + n > budget or len(cur) >= max_files):
            batches.append(cur); cur, size = [], 0
        cur.append(part); size += n
    if cur:
        batches.append(cur)
    return batches


def verify(items: list[dict[str, Any]], docs: list[dict[str, Any]], existing: list[dict[str, Any]], *, kinds: tuple[str, ...] = KINDS) -> list[dict[str, Any]]:
    """Check the AI's output. Adds to each item: evidence[i].verified, status (verified | gap | unverified | duplicate), problems[]."""
    pages = {d["file_id"]: {p["n"]: _compact(p["text"]) for p in d["pages"]} for d in docs}
    names = {d["file_id"]: d["name"] for d in docs}
    have = {(x["kind"], _compact(x["title"])) for x in existing}
    out, seen = [], set()
    for raw in items:
        it = {k: raw.get(k, "") for k in ("kind", "title", "detail", "impact", "rag", "basis")}
        it["kind"] = it["kind"] if it["kind"] in kinds else kinds[0] if kinds == SCOPE_KINDS else "rfi"
        for extra in SCOPE_EXTRA:
            if extra in raw:
                it[extra] = str(raw.get(extra) or "")
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
