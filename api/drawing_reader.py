"""Read-only drawing reader: turns a drawing PDF into page images (for the AI to look at) and per-page text with positions (dimensions, notes, titles).

Pure functions on PDF bytes. Nothing here measures anything: it only supplies the evidence a takeoff proposal has to point at.
Library: pypdfium2 (Apache/BSD licence) for both page images and text. It reads a 52-page A0 set in a few seconds; pdfplumber took two minutes on the same file.
"""
from __future__ import annotations
import io
import re
from typing import Any

import pypdfium2 as pdfium

SHEET_RE = re.compile(r"\b([A-Z]{1,2}\d{1,2}(?:\.\d{1,2})?)\b")


def page_count(pdf: bytes) -> int:
    return len(pdfium.PdfDocument(pdf))


def render_page(pdf: bytes, n: int, scale: float = 1.5, max_side: int = 3000) -> bytes:
    """PNG of page n (1-based). The scale is reduced so the longest side never exceeds max_side pixels."""
    doc = pdfium.PdfDocument(pdf)
    page = doc[n - 1]
    w, h = page.get_size()
    s = min(scale, max_side / max(w, h))
    buf = io.BytesIO()
    page.render(scale=s).to_pil().save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def crop_page(pdf: bytes, n: int, box: tuple[float, float, float, float], scale: float = 3.0) -> bytes:
    """PNG of a region of page n. box = (x0, y0, x1, y1) as fractions of the page (0-1, origin top left), so a closer look can be asked for."""
    img = pdfium.PdfDocument(pdf)[n - 1].render(scale=scale).to_pil()
    iw, ih = img.size
    x0, y0, x1, y1 = box
    buf = io.BytesIO()
    img.crop((int(iw * x0), int(ih * y0), int(iw * x1), int(ih * y1))).save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def page_texts(pdf: bytes) -> list[dict[str, Any]]:
    """One entry per page: {n, width, height, text, title_block}. title_block is the text in the bottom-right corner, where sheet numbers live."""
    out = []
    doc = pdfium.PdfDocument(pdf)
    for i in range(len(doc)):
        page = doc[i]
        w, h = page.get_size()
        tp = page.get_textpage()
        out.append({"n": i + 1, "width": float(w), "height": float(h), "text": tp.get_text_range(),
                    "title_block": tp.get_text_bounded(left=w * 0.86, bottom=0, right=w, top=h * 0.09)})
    return out


def sheet_map(pages: list[dict[str, Any]]) -> dict[str, int]:
    """Sheet code -> page number. Read the index on page 1 (lines like 'A2 Lower Floor Plan'), then find the page whose title block carries that code.
    Codes that cannot be found are left out; the estimator corrects the map."""
    titles: dict[str, str] = {}
    for line in (pages[0]["text"].splitlines() if pages else []):
        m = re.match(r"^([A-Z]{1,2}\d{1,2}(?:\.\d{1,2})?)\s+(.+)$", line.strip())
        if m:
            titles.setdefault(m.group(1), m.group(2).strip())
    found: dict[str, int] = {}
    for code in titles:
        first = [p for p in pages[1:] if re.match(rf"\s*{re.escape(code)}(?![\w.])", p["title_block"])]
        anywhere = [p for p in pages[1:] if re.search(rf"(?<![\w.]){re.escape(code)}(?![\w.])", p["title_block"])]
        if first or anywhere:
            found[code] = (first or anywhere)[0]["n"]
    return found


def scale_note(page: dict[str, Any]) -> str | None:
    """The drawing scale printed in the title block, e.g. '1:200 @ A2'. None if not found."""
    m = re.search(r"1\s*:\s*\d+\s*@\s*A\d", page.get("title_block", ""))
    return re.sub(r"\s+", "", m.group(0)) if m else None


def _variants(value: Any) -> list[str]:
    """The ways a drawing may write a number: 2105, 2,105, 2105.0 and, for a metre value read from millimetres, 2000 for 2.0."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return []
    out: list[str] = []
    for x in (v, v * 1000):
        if abs(x - round(x)) < 1e-9:
            out += [str(int(round(x))), f"{int(round(x)):,}"]
        else:
            out += [f"{x:g}", f"{x:.2f}", f"{x:.1f}"]
    return list(dict.fromkeys(s for s in out if s))


def locate(pdf: bytes, n: int, quote: str, value: Any = None) -> dict[str, Any]:
    """Where on page n (1-based) the quoted text is written. Returns {"how": "quote"|"number"|"none", "rects": [{"x0","y0","x1","y1"}], "width", "height"},
    rectangles as fractions of the page, origin top-left, so they can be drawn over an image of any size.
    Deterministic text search (no AI): first the whole quote, then the number itself, preferring the occurrence whose surroundings share the most words with the quote."""
    doc = pdfium.PdfDocument(pdf)
    page = doc[n - 1]
    w, h = page.get_size()
    tp = page.get_textpage()
    full = tp.get_text_range()

    def boxes(idx: int, cnt: int) -> dict[str, float]:
        bs = [tp.get_charbox(i) for i in range(idx, idx + cnt)]
        l, b, r, t = min(x[0] for x in bs), min(x[1] for x in bs), max(x[2] for x in bs), max(x[3] for x in bs)
        padx, pady = 6.0, 4.0
        return {"x0": max(0.0, (l - padx) / w), "x1": min(1.0, (r + padx) / w), "y0": max(0.0, 1 - (t + pady) / h), "y1": min(1.0, 1 - (b - pady) / h)}

    def hits(text: str) -> list[tuple[int, int]]:
        if not text.strip():
            return []
        s, out = tp.search(text, match_case=False), []
        while len(out) < 50:
            r = s.get_next()
            if not r:
                break
            out.append(r)
        return out

    q = re.sub(r"\s+", " ", quote or "").strip()
    for cand in ((q, q[:80]) if len(re.sub(r"\W", "", q)) >= 6 else ()):      # a very short quote would match anywhere
        hs = hits(cand)
        if hs:
            return {"how": "quote", "rects": [boxes(*hs[0])], "width": float(w), "height": float(h)}
    words = {x for x in re.findall(r"[a-z]{4,}", q.lower())}
    best: tuple[float, tuple[int, int]] | None = None
    for var in _variants(value):
        for idx, cnt in hits(var):
            before, after = full[max(0, idx - 80):idx].lower(), full[idx + cnt: idx + cnt + 80].lower()
            near = sum(1 for x in words if x in before or x in after)
            # a number must stand alone: not part of a longer number
            prev2, next2 = full[max(0, idx - 2):idx], full[idx + cnt: idx + cnt + 2]
            if (prev2[-1:].isdigit()) or (next2[:1].isdigit()) or (len(prev2) == 2 and prev2[1] in ",." and prev2[0].isdigit()) or (len(next2) == 2 and next2[0] in ",." and next2[1].isdigit()):
                continue
            if best is None or near > best[0]:
                best = (near, (idx, cnt))
        if best:
            break
    if best:
        return {"how": "number", "rects": [boxes(*best[1])], "width": float(w), "height": float(h)}
    return {"how": "none", "rects": [], "width": float(w), "height": float(h)}


def sheet_list(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """[{page, code, title}] for every page that can be tied to the sheet index on page 1; the rest are listed as plain pages with no code."""
    titles: dict[str, str] = {}
    for line in (pages[0]["text"].splitlines() if pages else []):
        m = re.match(r"^([A-Z]{1,2}\d{1,2}(?:\.\d{1,2})?)\s+(.+)$", line.strip())
        if m:
            titles.setdefault(m.group(1), m.group(2).strip())
    by_page = {n: c for c, n in sheet_map(pages).items()}
    return [{"page": p["n"], "code": by_page.get(p["n"], ""), "title": titles.get(by_page.get(p["n"], ""), "")} for p in pages]
