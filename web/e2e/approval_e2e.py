"""Approve and lock a step, then reopen it with a change note (Steps API stubbed in the browser)."""
import json, copy
from playwright.sync_api import sync_playwright, expect

exec(open("web/e2e/steps_e2e.py").read().split("with sync_playwright()")[0].split("\n", 1)[1])   # STEPS/OVERVIEW/route stubs
APP = {}

def route4(r):
    u = r.request.url.split("?")[0]
    j = lambda b, s=200: r.fulfill(status=s, content_type="application/json", body=json.dumps(b))
    if u.endswith("/approval"):
        d = json.loads(r.request.post_data)
        if d["action"] == "reopen" and len(d["note"].strip()) < 5: return j({"detail": "A reopened step needs a change note."}, 422)
        APP[d["step"]] = "APPROVED-LOCKED" if d["action"] == "approve" else "REOPENED"
        return j({"step": d["step"], "status": APP[d["step"]], "filed": {"name": f"STEP_{d['step']}_{APP[d['step']]}.md", "link": "https://drive.google.com/x"}})
    if u.endswith("/api/steps/tenders/" + u.split("/tenders/")[1]) and "/step" not in u.split("/tenders/")[1] and False: pass
    if "/step/" in u:
        k = u.split("/step/")[1]
        st0 = next(x for x in STEPS if x["key"] == k)
        return j({"key": k, "number": st0["number"], "name": st0["name"], "group": st0["group"], "status": APP.get(k, st0["status"]), "chat_title": st0["chat_title"], "workbook_revision": "", "folder_name": st0["folder_name"], "brief": None, "report": None})
    if "/api/steps/tenders/" in u and u.count("/") == 6:
        o = copy.deepcopy(OVERVIEW)
        for s in o["steps"]:
            if s["key"] in APP: s["status"] = APP[s["key"]]
        o["counts"]["locked"] = sum(1 for s in o["steps"] if s["status"] == "APPROVED-LOCKED")
        return j(o)
    return route(r)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/api/steps/**", route4)
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email", exact=True).fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    bp = pg.get_by_test_id("build-path")
    bp.get_by_role("button", name="03 Document Control").click()
    m = pg.locator("main")
    expect(m.get_by_role("button", name="Approve and lock")).to_be_visible(timeout=10000)
    m.get_by_role("button", name="Approve and lock").click()
    dlg = pg.get_by_role("dialog")
    dlg.get_by_label("Note (optional)").fill("Checked against the register")
    dlg.get_by_role("button", name="Approve and lock").click()
    expect(m).to_contain_text("approved and locked", timeout=10000); expect(m).to_contain_text("Filed in Drive as")
    expect(m.get_by_role("button", name="Reopen with a change note")).to_be_visible(timeout=10000)
    assert bp.get_by_role("img", name="approved, locked").count() == 3                                  # steps 01, 02 and the newly approved 03
    pg.screenshot(path=SHOTS + "approval_1.png", full_page=True)
    m.get_by_role("button", name="Reopen with a change note").click()
    dlg = pg.get_by_role("dialog")
    dlg.get_by_label("Change note (required)").fill("no")
    dlg.get_by_role("button", name="Reopen step").click()
    expect(dlg).to_contain_text("needs a change note")
    dlg.get_by_label("Change note (required)").fill("Retaining wall height changed in Rev17")
    dlg.get_by_role("button", name="Reopen step").click()
    expect(m).to_contain_text("reopened", timeout=10000)
    expect(m.get_by_role("button", name="Approve and lock")).to_be_visible(timeout=10000)
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(400)
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "sideways scroll"
    assert not errs, errs
    print("approval e2e ok")
