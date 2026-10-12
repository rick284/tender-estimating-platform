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
