import io

from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas

import drawing_reader as dr


def make_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A3))
    c.drawString(100, 700, "Sheet index  A1 Site Plan")
    c.drawString(100, 600, "Actual earthworks area 2,105m2 (see table)")
    c.drawString(100, 500, "Cut 113m3 Fill 1,310m3")
    c.drawString(1020, 40, "A1 25237  Site Plan  1:200 @ A3")
    c.showPage()
    c.drawString(100, 700, "Second page: fence 65.65m")
    c.save()
    return buf.getvalue()


def test_the_quote_is_found_where_it_is_written_as_fractions_of_the_page():
    pdf = make_pdf()
    r = dr.locate(pdf, 1, "Actual earthworks area 2,105m2", 2105)
    assert r["how"] == "quote" and len(r["rects"]) == 1
    b = r["rects"][0]
    assert 0 < b["x0"] < b["x1"] < 1 and 0 < b["y0"] < b["y1"] < 1
    assert b["x0"] < 0.1 and 0.25 < b["y0"] < 0.35                      # drawn at x=100pt, y=600pt up a 842pt page: about 29% down from the top


def test_falls_back_to_the_number_and_never_matches_part_of_a_longer_number():
    pdf = make_pdf()
    r = dr.locate(pdf, 1, "area is 2105 square metres", 2105)         # the page writes 2,105 so the whole quote is not there
    assert r["how"] == "number"
    assert dr.locate(pdf, 1, "x", 105)["how"] == "none"                # 105 only appears inside 2,105 / 1,310 etc.
    assert dr.locate(pdf, 1, "fence", 65.65)["how"] == "none"          # that number is on page 2, not page 1
    assert dr.locate(pdf, 2, "fence 65.65m", 65.65)["how"] == "quote"


def test_render_and_scale_and_sheet_map():
    pdf = make_pdf()
    assert dr.page_count(pdf) == 2
    png = dr.render_page(pdf, 1)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    pg = dr.page_texts(pdf)
    assert dr.scale_note(pg[0]) == "1:200@A3"
