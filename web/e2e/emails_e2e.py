"""Emails page: list, search, direction filter, thread view with linked references, empty state, phone width (Emails API stubbed in the browser)."""
import json
from playwright.sync_api import sync_playwright, expect

SHOTS = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
TH = [
    {"file_id": "E1", "name": "2026-09-04_In_Dave_Stewart_Initial_Tender_Enquiry", "link": "https://drive.google.com/e1", "path": "04/04.1 Emails In", "direction": "in", "date": "2026-09-04", "subject": "FW: Childcare Centre - 329 Hobsonville Road", "party": "Dave Stewart (Siteworks)", "count": 2, "refs": ["RFI-06", "Q-01", "RFI-99"], "attachments": ["Channel drain detail.pdf"], "links": [], "gmail_ids": ["1a0693e3"], "modified": "x"},
    {"file_id": "E2", "name": "2026-10-01_Out_Quote_request", "link": "", "path": "04/04.2 Emails Out - DRAFT ONLY", "direction": "out", "date": "2026-10-01", "subject": "Quote request: concrete", "party": "Rick", "count": 1, "refs": ["Q-01"], "attachments": [], "links": [], "gmail_ids": [], "modified": "x"}]
FULL = {"E1": {**TH[0], "text": "t", "messages": [{"from": "Dave Stewart", "date": "2026-09-04", "subject": "FW: Childcare Centre", "gmail_id": "1a0693e3", "body": "Earth works including sediment and silt control."},
                                               {"from": "Dave Stewart", "date": "2026-09-04", "subject": "hobsonville childcare.", "gmail_id": "1a0694", "body": "Please allow for the channel drains."}]}}
state = {"empty": True}

def route(r):
    u = r.request.url; path = u.split("/api/emails/")[1].split("?")[0]
    j = lambda b: r.fulfill(status=200, content_type="application/json", body=json.dumps(b))
    if path.endswith("/refresh"): state["empty"] = False; return j({"found": 2, "read": 2, "removed": 0, "problems": [], "truncated": False})
    if "/thread/" in path: return j(FULL[path.split("/thread/")[1]])
    from urllib.parse import parse_qs, urlparse
    q = parse_qs(urlparse(u).query); qq = (q.get("q") or [""])[0].lower(); d = (q.get("direction") or [""])[0]; ref = (q.get("ref") or [""])[0]
    rows = [] if state["empty"] else [t for t in TH if (not d or t["direction"] == d) and (not ref or ref in t["refs"]) and (not qq or qq in ("channel drains " + t["subject"]).lower())]
    return j({"threads": rows, "total": 0 if state["empty"] else 2, "refs": [] if state["empty"] else ["Q-01", "RFI-06", "RFI-99"]})

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/api/emails/**", route)
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email", exact=True).fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.locator("aside").get_by_role("button", name="Emails").click()
    m = pg.locator("main")
    expect(m).to_contain_text("No emails saved yet", timeout=10000)
    m.get_by_role("button", name="Refresh from Drive").click()
    expect(m).to_contain_text("2 email files found", timeout=10000)
    expect(m.get_by_role("list", name="Email threads").get_by_role("listitem")).to_have_count(2)
    m.get_by_role("button", name="FW: Childcare Centre").click()
    expect(m).to_contain_text("Earth works including sediment"); expect(m).to_contain_text("Channel drain detail.pdf")
    known = m.locator('button[title^="Open in"]').first; unknown = m.locator('button[title^="Mentioned"]').first
    assert "green" in (known.get_attribute("class") or "") and "amber" in (unknown.get_attribute("class") or "")      # in the estimate vs mentioned only
    pg.screenshot(path=SHOTS + "emails_1.png", full_page=True)
    m.get_by_label("Direction").select_option("out")
    expect(m.get_by_role("list", name="Email threads").get_by_role("listitem")).to_have_count(1)
    m.get_by_label("Direction").select_option("")
    m.get_by_label("Search emails").fill("channel drains")
    expect(m.get_by_role("list", name="Email threads").get_by_role("listitem")).to_have_count(1, timeout=5000)
    m.get_by_label("Search emails").fill("")
    m.get_by_role("button", name="RFI-06", exact=True).first.click()                       # filter by a mentioned reference
    expect(m.get_by_role("list", name="Email threads").get_by_role("listitem")).to_have_count(1, timeout=5000)
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(400)
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "sideways scroll"
    pg.screenshot(path=SHOTS + "emails_phone.png", full_page=True)
    assert not errs, errs
    print("emails e2e ok")
