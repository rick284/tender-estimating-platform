"""AI Drafting page with the AI endpoints stubbed in the browser (no key needed). The accepted proposal goes into the REAL edit draft and the REAL preview."""
import json
from playwright.sync_api import sync_playwright, expect

SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
state = {"enabled": False, "props": [], "decided": {}}
EV = lambda ok: {"file_id": "F1", "file": "Civil Drawings Rev C.pdf", "page": 2, "quote": "Retaining walls maximum height 1.5m (Civil DWG301)" if ok else "All rock excavation is included", "verified": ok}
P = lambda i, title, status, ok: {"id": i, "batch": "b1", "kind": "rfi", "title": title, "detail": "Civil and architectural drawings disagree.", "impact": "Allowance or exclusion needed until resolved.", "rag": "RED",
                                  "basis": "quoted", "evidence": [EV(ok)], "status": status, "problems": [] if ok else ["The quote is not on page 2 of Civil Drawings Rev C.pdf"], "decision": state["decided"].get(i), "created_at": "2026-10-14T01:00:00"}

def route(r):
    path = r.request.url.split("/api/")[1].split("?")[0]; m = r.request.method
    j = lambda b, s=200: r.fulfill(status=s, content_type="application/json", body=json.dumps(b))
    if path == "ai/status": return j({"configured": True, "enabled": state["enabled"], "model": "claude-opus-5-5", "can_change": True, "acknowledged_at": None, "max_files": 12})
    if path == "ai/settings": state["enabled"] = json.loads(r.request.post_data)["enabled"]; return j({"enabled": state["enabled"]})
    if path.endswith("/texts") and path.startswith("drive/"): return j({"texts": [{"file_id": "F1", "name": "Civil Drawings Rev C.pdf", "path": "01 Client Issue Pack", "revision": "C", "status": "ok", "pages": 4, "chars": 12000}]})
    if path.startswith("ai/tenders/") and path.endswith("/draft"):
        state["props"] = [P("p1", "Retaining height conflict", "verified", True), P("p2", "Rock excavation allowance", "unverified", False)]
        return j({"batch": "b1", "coverage_notes": "Read one document.", "proposals": [], "files_sent": ["Civil Drawings Rev C.pdf"]})
    if path.startswith("ai/tenders/") and path.endswith("/proposals"):
        return j({"proposals": [{**p, "decision": state["decided"].get(p["id"])} for p in state["props"]]})
    if path.startswith("ai/proposals/"):
        body = json.loads(r.request.post_data); pid = path.split("/")[2]
        if body["decision"] == "rejected": state["decided"][pid] = {"decision": "rejected", "reason": body["reason"]}; return j({"decision": "rejected"})
        state["decided"][pid] = {"decision": "accepted", "edit_key": "R-e2e00001"}
        return j({"decision": "accepted", "edit": {"target": "register", "op": "add", "key": "R-e2e00001", "value": {"kind": "rfi", "title": "Retaining height conflict", "detail": "Civil and architectural drawings disagree.\n\nAI-drafted from the documents; verified quotes:\n- Civil Drawings Rev C.pdf p.2: “Retaining walls maximum height 1.5m (Civil DWG301)”", "action": "Allowance or exclusion needed until resolved.", "rag": "RED", "status": "OPEN"}}})
    return j({"detail": "unexpected " + path}, 500)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/api/ai/**", route); pg.route("**/api/drive/tenders/*/texts", route)
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.locator("aside").get_by_role("button", name="AI Drafting").click()
    expect(pg.get_by_role("button", name="Switch on")).to_be_disabled()                       # needs the acknowledgement first
    pg.get_by_label("I understand that the text").check() if False else pg.locator("input[type=checkbox]").first.check()
    pg.get_by_role("button", name="Switch on").click()
    expect(pg.get_by_text("Model claude-opus-5-5")).to_be_visible()
    pg.get_by_label("Select Civil Drawings Rev C.pdf").check()
    pg.get_by_role("button", name="Draft register items (1)").click()
    expect(pg.get_by_text("Retaining height conflict")).to_be_visible(timeout=10000)
    expect(pg.get_by_text("Can't accept: quote not found")).to_be_visible()
    cards = pg.locator("div.border.bg-background.p-4")
    assert cards.nth(1).get_by_role("button", name="Accept into my draft").count() == 0       # an unverified proposal can't be accepted
    cards.nth(0).get_by_role("button", name="Accept into my draft").click()
    expect(pg.get_by_role("alert")).to_contain_text("Press Edit")                               # not in edit mode: it explains
    pg.screenshot(path=SHOT + "ai_1.png", full_page=True)
    pg.get_by_role("button", name="Edit", exact=True).click()
    cards.nth(0).get_by_role("button", name="Accept into my draft").click()
    pg.wait_for_timeout(1500)
    expect(pg.locator("div.fixed.bottom-0")).to_contain_text("1 change")
    # the second proposal is rejected with a reason
    pg.locator("div.border.bg-background.p-4").first.get_by_role("button", name="Reject", exact=True).click()
    pg.get_by_label("Reason for rejecting").fill("Quote is not in the document")
    pg.get_by_role("button", name="Reject", exact=True).last.click()
    pg.wait_for_timeout(800)
    expect(pg.get_by_text("Decided (2)")).to_be_visible()
    # the accepted draft is real in the register preview
    pg.locator("aside").get_by_role("button", name="Register").click()
    expect(pg.get_by_role("tab", name="RFIs 19")).to_be_visible(timeout=10000)
    pg.screenshot(path=SHOT + "ai_2.png", full_page=True)
    print("OK ai drafting | errors:", errs[:3]); b.close()
