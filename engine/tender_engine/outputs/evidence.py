from __future__ import annotations
from typing import Any

from reportlab.platypus import Paragraph, Spacer

from .context import OutputContext, money
from .report import BASE, H1, H2, SMALL, W, _bullets, _doc, _esc, _first_sentence, _table, mm

CONTROL = ("A supplier rate or quote is evidence, not automatically the controlling tender amount. Scope, quantity, exclusions, delivery basis, "
           "validity, duplication and specification compliance must reconcile to the estimate before use.")


def _who(q: dict[str, Any]) -> str:
    return q["supplier"] or q["package"]


def verification_index_pdf(est: dict[str, Any], ctx: OutputContext) -> bytes:
    """Supplier and subcontractor verification index: each package traced to its evidence and how the tender uses it."""
    quotes = est.get("quotes") or []
    story: list[Any] = [Paragraph(_esc(ctx.project or est["meta"].get("project", "")), H1),
                        Paragraph(_esc(f"Supplier and Subcontractor Verification Index | {ctx.issue_date}"), H2),
                        Paragraph(_esc("Purpose. Trace the material supplier and subcontractor inputs used in the current tender back to formal quotes, supplier emails and supporting evidence."), BASE),
                        Spacer(1, 3), Paragraph(_esc("Release control. " + CONTROL), BASE), Spacer(1, 8)]
    if not quotes:
        story.append(Paragraph("No supplier or subcontractor quotes have been recorded for this tender yet.", BASE))
    else:
        rows = [["Supplier / package", "Primary evidence", "Key verification point", "Current tender treatment"]]
        for q in quotes:
            evidence = " ".join(x for x in (q["notes"], f"Source: {q['source']}" if q["source"] else "") if x)
            verif = q["verification"] or (f"{money(float(q['amount']))} excl GST. " if q["amount"] else "") + _first_sentence(q["scope"], 200)
            treat = q["treatment"] or q["action"] or q["status"]
            rows.append([f"{_who(q)}" + (f" | {q['package']}" if q["supplier"] and q["package"] else ""), _first_sentence(evidence, 330), _first_sentence(verif, 300), _first_sentence(treat, 280)])
        story.append(_table(rows, [38 * mm, 52 * mm, 42 * mm, W - 132 * mm]))
    return _doc("Supplier and subcontractor verification index", ctx, story, "SUPPLIER VERIFICATION")


def evidence_notes_pdf(est: dict[str, Any], ctx: OutputContext) -> bytes:
    """Supplier evidence notes: how each piece of evidence has been interpreted in the estimate."""
    quotes = est.get("quotes") or []
    story: list[Any] = [Paragraph(_esc(ctx.project or est["meta"].get("project", "")), H1), Paragraph(_esc(f"Supplier Evidence Notes | {ctx.issue_date}"), H2),
                        Paragraph(_esc("This document explains how the supplier and subcontractor evidence has been interpreted in the estimate. Read it with the formal source documents."), BASE)]
    for i, q in enumerate(quotes, start=1):
        story.append(Paragraph(_esc(f"{i}. {_who(q)}" + (f" ({q['ref']})" if q["ref"] else "")), H2))
        bits = []
        if q["amount"]:
            bits.append(f"{money(float(q['amount']))} excl GST" + (f" for {q['qty']} {q['unit']}".rstrip() if q["qty"] else "") + f" ({q['package']}).")
        elif q["package"]:
            bits.append(q["package"] + ".")
        bits += [x for x in (q["notes"], q["treatment"] or q["action"]) if x]
        story.append(Paragraph(_esc(" ".join(bits) or q["scope"]), BASE))
        if q["status"]:
            story.append(Paragraph(_esc(f"Status: {q['status']}"), SMALL))
    story.append(Paragraph("Control note", H2))
    story.append(Paragraph(_esc("Where a supplier email conflicts with a formal attachment, the formal project-specific quotation controls unless the supplier explicitly revises it. " + CONTROL), BASE))
    return _doc("Supplier evidence notes", ctx, story, "SUPPLIER EVIDENCE NOTES")
