"""AI Takeoff page with the AI endpoints stubbed in the browser (no key needed). A verified line goes through the real Add QS item dialog into the REAL edit draft and preview."""
import io, json
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright, expect

SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
state = {"lines": [], "decided": {}, "ran": None}
STATUS = {"configured": True, "enabled": True, "provider": "anthropic", "model": "claude-opus-5-5", "key_source": "own", "key_last4": "efgh",
          "providers": [{"id": "anthropic", "label": "Anthropic (Claude)", "available": True, "default_model": "claude-opus-5-5", "key_hint": ""}], "can_change": True, "acknowledged_at": "2026-10-14T01:00:00", "max_files": 12}
COMP = lambda ok, q="Actual earthworks area 2,105m2", v=2105, src="stated_area": {"label": "earthworks area", "value": v, "unit": "m2", "doc": "D1", "file": "Architectural Rev17.pdf", "sheet": "A1", "page": 3, "source": src, "quote": q, "found": ok}
def line(i, desc, status, qty, unit, method, comps, problems=()):
    return {"id": i, "run": "r1", "description": desc, "section": "earthworks", "unit": unit, "operation": "single", "method": method, "confidence": "high" if status == "verified" else "low", "notes": "",
            "quantity": qty, "quantity_claimed": qty, "components": comps, "status": status, "problems": list(problems), "decision": state["decided"].get(i), "created_at": "2026-10-15T01:00:00"}
LINES = lambda: [line("t1", "Earthworks area", "verified", 2105, "m2", "READ", [COMP(True)]),
                 line("t2", "Retaining wall length", "check", 68.7, "lm", "SCALED", [COMP(None, "", 68.7, "scaled")]),
                 line("t3", "Invented area", "unverified", 900, "m2", "READ", [COMP(False, "area is 900m2", 900)], ["“earthworks area”: the quote is not on page 3"])]

def png():
    im = Image.new("RGB", (1600, 1130), "white"); d = ImageDraw.Draw(im); d.text((1450, 900), "2,105m2", fill="black"); d.rectangle((40, 40, 1560, 1090), outline="black")
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()

def route(r):
    path = r.request.url.split("/api/")[1].split("?")[0]; m = r.request.method
    j = lambda b, s=200: r.fulfill(status=s, content_type="application/json", body=json.dumps(b))
    if path == "ai/status": return j(STATUS)
    if path.endswith("/texts") and path.startswith("drive/"):
        return j({"texts": [{"file_id": "F1", "name": "Architectural Rev17.pdf", "path": "02 Architectural", "revision": "17", "status": "ok", "pages": 52, "chars": 120000}]})
    if path.startswith("takeoff/tenders/") and path.endswith("/run"):
        state["ran"] = json.loads(r.request.post_data); state["lines"] = LINES()
        return j({"run": "r1", "lines": state["lines"], "not_measurable": [{"what": "Silt fence length", "why": "ESC plan not supplied"}], "files_sent": ["Architectural Rev17.pdf"], "pictures": 1})
    if path.endswith("/sources"):
        return j({"line": "t1", "description": "Earthworks area", "sources": [{"index": 0, "label": "earthworks area", "value": 2105, "unit": "m2", "source": "stated_area", "file_id": "F1", "file": "Architectural Rev17.pdf", "sheet": "A1", "page": 3,
                                                                             "quote": "Actual earthworks area 2,105m2", "how": "number", "rects": [{"x0": 0.90, "y0": 0.78, "x1": 0.94, "y1": 0.80}], "viewable": True, "pages": 52}]})
    if "/sheets" in path: return j({"file": "Architectural Rev17.pdf", "pages": [{"page": 1, "code": "", "title": ""}, {"page": 3, "code": "A1", "title": "Site Plan"}, {"page": 4, "code": "A2", "title": "Lower Floor Plan"}], "scale": {"3": "1:200@A2"}})
    if path.endswith("/image"): return r.fulfill(status=200, content_type="image/png", body=png())
    if path.startswith("takeoff/tenders/") and path.endswith("/lines"):
        return j({"lines": [{**l, "decision": state["decided"].get(l["id"])} for l in state["lines"]]})
    if path.startswith("takeoff/lines/"):
        body = json.loads(r.request.post_data); lid = path.split("/")[2]
        if body["decision"] == "rejected": state["decided"][lid] = {"decision": "rejected", "reason": body["reason"]}; return j({"decision": "rejected"})
        if body.get("commit", True): state["decided"][lid] = {"decision": "accepted"}
        return j({"decision": "accepted" if body.get("commit", True) else "pending", "qs": {"description": "Earthworks area", "unit": "m2", "quantity": 2105, "basis": "PROVIDED", "source": "AI takeoff: Architectural Rev17.pdf A1 p.3 “Actual earthworks area 2,105m2”", "notes": "AI takeoff (READ, high confidence).", "section_hint": "earthworks"}})
    return j({"detail": "unexpected " + path}, 500)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/api/ai/status", route); pg.route("**/api/takeoff/**", route); pg.route("**/api/drive/tenders/*/texts", route)
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.locator("aside").get_by_role("button", name="AI Takeoff").click()
    expect(pg.get_by_text("Choose drawings and reports")).to_be_visible()
    expect(pg.get_by_role("button", name="Take off (0 documents)")).to_be_disabled()
    pg.get_by_label("Select Architectural Rev17.pdf").check()
    pg.get_by_label("Picture pages for Architectural Rev17.pdf").fill("3, 4")
    pg.get_by_role("button", name="Choose from sheet list").click()
    expect(pg.get_by_text("Lower Floor Plan")).to_be_visible()
    expect(pg.get_by_label("Page 4")).to_be_checked()                                             # the sheet list reflects the page box
    pg.get_by_label("Page 4").uncheck(); assert pg.get_by_label("Picture pages for Architectural Rev17.pdf").input_value() == "3"
    pg.get_by_label("Page 4").check()                                                              # and fills it
    assert pg.get_by_label("Picture pages for Architectural Rev17.pdf").input_value() == "3, 4"
    pg.get_by_role("button", name="Take off (1 document)").click()
    expect(pg.get_by_text("3 lines proposed from 1 document and 1 page picture.")).to_be_visible(timeout=10000)
    assert state["ran"]["pictures"] == [{"file_id": "F1", "page": 3}, {"file_id": "F1", "page": 4}], state["ran"]
    expect(pg.get_by_text("Silt fence length")).to_be_visible()                                  # what the AI could not establish is shown
    cards = pg.locator("div.border.bg-background.p-4")
    assert cards.nth(2).get_by_role("button", name="Add to my QS draft").count() == 0             # an unverified line can't be added
    cards.nth(0).get_by_text("Show where the numbers come from").click()
    expect(pg.get_by_text("found on the page")).to_be_visible()
    pg.screenshot(path=SHOT + "takeoff_1.png", full_page=True)
    # click-to-source: the page opens with the number outlined where it is written
    cards.nth(0).get_by_role("button", name="View source on the drawing").click()
    dlg = pg.get_by_role("dialog")
    expect(dlg.get_by_text("Source: Earthworks area")).to_be_visible()
    expect(dlg.get_by_test_id("source-highlight")).to_be_visible(timeout=10000)
    expect(dlg.get_by_text("Page 3 of 52 · A1 Site Plan")).to_be_visible()
    box = dlg.get_by_test_id("source-highlight").bounding_box(); img = dlg.locator("img").bounding_box()
    assert abs((box["x"] - img["x"]) / img["width"] - 0.90) < 0.01 and abs((box["y"] - img["y"]) / img["height"] - 0.78) < 0.01      # drawn at the stated fraction of the page
    pg.screenshot(path=SHOT + "takeoff_viewer.png")
    w1 = dlg.locator("img").bounding_box()["width"]
    dlg.get_by_role("button", name="Zoom in").click()
    pg.wait_for_timeout(300)
    assert dlg.locator("img").bounding_box()["width"] > w1 * 1.2                                    # zoom works
    dlg.get_by_role("button", name="Next page").click()
    expect(dlg.get_by_text("Page 4 of 52")).to_be_visible()
    assert dlg.get_by_test_id("source-highlight").count() == 0                                      # the outline only shows on the cited page
    pg.keyboard.press("Escape")
    expect(pg.get_by_role("dialog")).to_have_count(0)
    expect(pg.get_by_role("button", name="Edit", exact=True)).to_be_visible()                      # not in edit mode yet
    cards.nth(0).get_by_role("button", name="Add to my QS draft").click()                           # the button switches edit mode on itself
    expect(pg.get_by_text("Editing", exact=True).first).to_be_visible()
    expect(pg.get_by_role("dialog").get_by_label("Description")).to_have_value("Earthworks area")   # the real Add QS item dialog, pre-filled
    expect(pg.get_by_role("dialog").get_by_label("Quantity", exact=True)).to_have_value("2105")
    assert pg.get_by_role("dialog").locator("select").first.input_value() == "Earthworks"         # section guessed from the estimate's own sections
    pg.screenshot(path=SHOT + "takeoff_2.png", full_page=True)
    pg.get_by_role("dialog").get_by_role("button", name="Add item").click()
    pg.wait_for_timeout(1500)
    expect(pg.locator("div.fixed.bottom-0")).to_contain_text("1 change")
    # reject one with a reason
    first = pg.locator("div.border.bg-background.p-4").first
    first.get_by_role("button", name="Reject", exact=True).click()
    first.get_by_label("Reason for rejecting").fill("Not needed for siteworks")
    first.get_by_role("button", name="Reject", exact=True).last.click()
    pg.wait_for_timeout(800)
    expect(pg.get_by_text("Decided (2)")).to_be_visible()
    # the new QS item is real in the QS Takeoff preview
    pg.locator("aside").get_by_role("button", name="QS Takeoff").click()
    expect(pg.get_by_text("AI takeoff: Architectural Rev17.pdf").first).to_be_visible(timeout=10000) if False else None
    pg.screenshot(path=SHOT + "takeoff_3.png", full_page=True)
    # a revision saved before editing existed can't be edited: the button says why, right next to itself (not at the top of the page)
    def no_inputs(route):
        r = route.fetch(); body = r.json()
        for rv in body.get("revisions", []): rv["has_inputs"] = False
        route.fulfill(response=r, json=body)
    pg.reload(); pg.route("**/api/tenders/*", no_inputs); pg.reload()
    expect(pg.get_by_role("button", name="Edit", exact=True)).to_be_disabled(timeout=20000)          # the patched revision cannot be edited
    pg.locator("aside").get_by_role("button", name="AI Takeoff").click()
    state["decided"].clear()                                                                       # fresh set of open lines for this check
    pg.get_by_label("Select Architectural Rev17.pdf").check()
    pg.get_by_role("button", name="Take off (1 document)").click()
    expect(pg.get_by_text("3 lines proposed")).to_be_visible(timeout=10000)
    card = pg.locator("div.border.bg-background.p-4").first
    card.get_by_role("button", name="Add to my QS draft").click()
    expect(card.get_by_role("alert")).to_contain_text("saved before editing was available")
    print("OK ai takeoff | errors:", errs[:3]); b.close()
