"""Build path: grouped Steps in the sidebar, Job Record page and a step page, with the Steps API stubbed in the browser (no Drive needed)."""
import json
from playwright.sync_api import sync_playwright, expect

SHOTS = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
S = lambda k, n, g, st, brief=True, report=True: {"key": k, "number": int(k[:2]), "suffix": k[2:], "name": n, "group": g, "status": st, "chat_title": f"329 Hobsonville Rd | Step {k} {n} | Dave Stewart",
    "workbook_revision": "Rev00" if st == "APPROVED-LOCKED" else "", "folder_id": "F" + k, "folder_name": f"Step {k} {n}", "brief": {"id": "b" + k, "name": f"STEP_{k}_BRIEF.md"} if brief else None,
    "report": {"id": "r" + k, "name": f"STEP_{k}_REPORT.md"} if report else None, "in_record": True}
STEPS = [S("01", "Scope of Work and Effort", "Scope and plan", "APPROVED-LOCKED"), S("02", "Production Programme", "Scope and plan", "APPROVED-LOCKED"),
         S("03", "Document Control", "Documents", "DRAFT"), S("04", "Take-off - Earthworks", "Takeoff", "REPORTED"), S("05", "Take-off - Drainage", "Takeoff", "REOPENED"),
         S("06", "Quotes", "Quotes and correspondence", "READY", report=False)]
REC = "# JOB RECORD: 329 Hobsonville Road\n\n- Revision: Rev00   Release status: HOLD\n\n## Steps\n| Step | Status |\n|---|---|\n| 01 | APPROVED-LOCKED |\n"
OVERVIEW = {"folder_found": True, "groups": ["Scope and plan", "Documents", "Scope coverage", "Takeoff", "Quotes and correspondence", "Build-up and workbook", "Programme and weather", "Review and release", "Client pack", "Other"],
            "steps": STEPS, "counts": {"steps": 6, "locked": 2, "draft": 2, "reopened": 1},
            "job_record": {"found": True, "name": "JOB_RECORD.md", "link": "https://drive.google.com/jr", "text": REC, "fields": {"revision": "Rev00", "release_status": "HOLD", "mode": "STEP", "stage": "1C"}}}

def route(r):
    path = r.request.url.split("/api/steps/")[1].split("?")[0]
    j = lambda b, s=200: r.fulfill(status=s, content_type="application/json", body=json.dumps(b))
    if "/step/" in path:
        k = path.split("/step/")[1]; st = next(x for x in STEPS if x["key"] == k)
        return j({**{x: st[x] for x in ("key", "number", "name", "group", "status", "chat_title", "workbook_revision", "folder_name")},
                  "brief": {"name": f"STEP_{k}_BRIEF.md", "text": f"# STEP {k} BRIEF\n\n- Do the work\n- **Locked** inputs\n\n| Result | Where |\n|---|---|\n| Quantities | Rev00 |\n"} if st["brief"] else None,
                  "report": {"name": f"STEP_{k}_REPORT.md", "text": f"# STEP {k} REPORT\n\nDone. Hours 2.5 against 3."} if st["report"] else None})
    return j(OVERVIEW)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/api/steps/**", route)
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    bp = pg.get_by_test_id("build-path")
    expect(bp).to_contain_text("Build path"); expect(bp).to_contain_text("Scope and plan"); expect(bp).to_contain_text("Takeoff")
    expect(bp.get_by_role("button", name="01 Scope of Work and Effort")).to_be_visible()
    assert bp.get_by_role("img", name="approved, locked").count() == 2 and bp.get_by_role("img", name="reopened").count() == 1       # status markers have words, not just colour
    pg.screenshot(path=SHOTS + "steps_1_sidebar.png")
    bp.get_by_role("button", name="Job Record").click()
    expect(pg.locator("main")).to_contain_text("Whole record"); expect(pg.locator("main")).to_contain_text("Rev00"); expect(pg.locator("main")).to_contain_text("Take-off - Drainage")
    pg.screenshot(path=SHOTS + "steps_2_record.png", full_page=True)
    pg.locator("main tr", has_text="Take-off - Earthworks").click()
    expect(pg.locator("main")).to_contain_text("Step 04: Take-off - Earthworks"); expect(pg.locator("main")).to_contain_text("Reported, not yet approved")
    expect(pg.locator("main")).to_contain_text("Hours 2.5 against 3."); expect(pg.locator("main")).to_contain_text("Quantities")
    pg.screenshot(path=SHOTS + "steps_3_step.png", full_page=True)
    bp.get_by_role("button", name="01 Scope of Work and Effort").click()
    expect(pg.locator("main")).to_contain_text("Locked: later steps build on this result")
    # the existing workbook pages are still there under the build path
    pg.locator("aside").get_by_role("button", name="QS Takeoff").click()
    expect(pg.get_by_text("EW01").first).to_be_visible(timeout=10000)
    # phone: drawer shows the same path, no sideways scroll
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(400)
    pg.get_by_role("button", name="Open navigation").click()
    expect(pg.get_by_test_id("build-path")).to_be_visible()
    pg.get_by_test_id("build-path").get_by_role("button", name="03 Document Control").click(); pg.wait_for_timeout(600)
    expect(pg.locator("main")).to_contain_text("Step 03: Document Control")
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "sideways scroll"
    assert not errs, errs
    print("steps e2e ok")
