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


ROWS = [{"ref": str(i), "title": t, "detail": "d", "proposal": "Included", "source": "Email E01", "owner": "OWN WORKS", "treatment": "UNRESOLVED"} for i, t in enumerate(["EARTHWORKS CUT TO FILL", "RETAINING WALLS", "DRAINAGE"], 1)]
GO = {"v": None}
STEP01 = lambda: {"files": {"scope": {"name": "Scope_Rev_A.docx", "link": "#"}}, "card": "# Card\n\nTest only.", "go_ahead": GO["v"],
    "scope": {"rows": ROWS, "questions": [{"ref": "Q1", "title": "Who owns excavation", "question": "Who excavates?"}]},
    "proposal": {"cases": [{"label": "Low", "hours": 30, "rate": 125, "fee": 3750}, {"label": "High", "hours": 40, "rate": 125, "fee": 5000}], "rate": 125, "low_hours": 30, "high_hours": 40, "low_fee": 3750, "high_fee": 5000, "revision": "Rev A", "text": ""}}

def route2(r):
    u = r.request.url
    if u.split("?")[0].endswith("/step01"): return r.fulfill(status=200, content_type="application/json", body=json.dumps(STEP01()))
    if u.split("?")[0].endswith("/go-ahead"):
        if r.request.method == "PUT":
            d = json.loads(r.request.post_data); GO["v"] = {**d, "at": "2026-10-20T01:00:00Z", "by": "rick"}
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"go_ahead": GO["v"]}))
        GO["v"] = None; return r.fulfill(status=200, content_type="application/json", body=json.dumps({"go_ahead": None}))
    return route(r)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/api/steps/**", route2)
    pg.route("**/scope/file", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"filed": {"name": "SCOPE_CURRENT_2026-10-20_0900.md", "link": ""}, "items": 3})))
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.get_by_test_id("build-path").get_by_role("button", name="01 Scope of Work and Effort").click()
    m = pg.locator("main")
    expect(m).to_contain_text("$3,750.00 to $5,000.00", timeout=10000)
    expect(m).to_contain_text("earthworks cut to fill", ignore_case=True)
    pg.screenshot(path=SHOTS + "step01_1.png", full_page=True)
    pg.get_by_role("button", name="Set up from Step 01 (3 scope items, 1 questions)").click(); pg.wait_for_timeout(1500); assert "invalid" not in pg.locator("body").inner_text(), "the edit draft was rejected"
    expect(pg.get_by_role("button", name="All in Scope Coverage")).to_be_visible(timeout=10000)
    expect(pg.get_by_role("button", name="All in the Register")).to_be_visible()
    pg.locator("aside").get_by_role("button", name="Project Brief").click()
    expect(pg.locator("main")).to_contain_text("Q1: Who owns excavation", timeout=10000)
    pg.get_by_role("button", name="Fill empty fields from the scope").click()
    expect(pg.locator("main")).to_contain_text("Filled", timeout=10000)
    assert "Scope: 3 items." in pg.locator("main").inner_text() or any("Scope: 3 items." in v for v in pg.evaluate("[...document.querySelectorAll('main textarea')].map(t => t.value)"))     # the overview is built from the scope rows
    pg.get_by_test_id("build-path").get_by_role("button", name="01 Scope of Work and Effort").click()
    pg.locator("aside").get_by_role("button", name="Scope Coverage").click()
    expect(pg.locator("main")).to_contain_text("Retaining walls", timeout=10000)
    titles = pg.evaluate("[...document.querySelectorAll('[data-testid=scope-row]')].map(r => (r.querySelector('textarea')?.value || r.innerText).toLowerCase())")
    assert [("earthworks" in t, "retaining" in t, "drainage" in t) for t in titles] == [(True, False, False), (False, True, False), (False, False, True)], titles     # as imported
    pg.get_by_label("Order").select_option("group")
    expect(pg.locator("main")).to_contain_text("Permanent works")                                                                  # group headings only in the grouped view
    pg.get_by_label("Order").select_option("imported")
    pg.get_by_role("button", name="Save scope to Drive").click()
    expect(pg.locator("main")).to_contain_text("Filed in Drive as SCOPE_CURRENT_2026-10-20_0900.md", timeout=10000)
    # go-ahead
    pg.get_by_test_id("build-path").get_by_role("button", name="Job Record").click()
    pg.get_by_role("button", name="Record", exact=True).click()   # no note needed for a client go
    expect(pg.locator("main")).to_contain_text("go-ahead", ignore_case=True)
    pg.get_by_role("button", name="Clear").click()
    expect(pg.get_by_role("button", name="Record", exact=True)).to_be_visible(timeout=10000)
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(400)
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "sideways scroll"
    assert not errs, errs
    print("step01 e2e ok")
