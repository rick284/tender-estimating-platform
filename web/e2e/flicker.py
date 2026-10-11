import time
from playwright.sync_api import sync_playwright, expect
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width":1440,"height":900}).new_page()
    calls = []
    def slow(route):
        calls.append(route.request.url.split("/api/")[1]); time.sleep(2.5); route.continue_()
    pg.route("**/api/tenders/*", lambda r: slow(r) if "/compare" not in r.request.url else r.continue_())
    pg.route("**/api/tenders/*/revisions/*", slow)
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    initial = len(calls)
    seen_loading = False; blanks = 0
    for label in ["QS Takeoff", "Resource Build-Up", "Weather Risk", "Overview", "Tender Build-Up", "Consolidated Package"]:
        pg.locator("aside").get_by_role("button", name=label).click()
        for _ in range(12):                          # watch for ~1.2 s after each click
            if pg.get_by_text("Loading estimate").count(): seen_loading = True
            if pg.locator("main h1").count() == 0: blanks += 1
            pg.wait_for_timeout(100)
    print("requests after first load:", len(calls) - initial, "| 'Loading estimate' ever shown:", seen_loading, "| blank main samples:", blanks)
    b.close()
