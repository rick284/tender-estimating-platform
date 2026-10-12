"""A read that fails to connect (server waking or restarting) is retried quietly; only a failure that persists shows the plain-language message."""
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1280, "height": 800}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    expect(pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first).to_be_visible(timeout=20000)
    calls = {"n": 0}
    def flaky(route):
        calls["n"] += 1
        route.abort("connectionreset") if calls["n"] == 1 else route.continue_()
    pg.route("**/api/tenders", flaky)
    pg.reload()
    expect(pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first).to_be_visible(timeout=20000)   # the first request was dropped, the retry worked
    assert calls["n"] >= 2, calls
    assert pg.get_by_text("Can't reach the server").count() == 0                                                     # and the user never saw a message
    # a failure that persists does show the message, in plain language
    pg.unroute("**/api/tenders")
    pg.route("**/api/tenders", lambda r: r.abort("connectionreset"))
    pg.reload()
    expect(pg.get_by_text("Can't reach the server")).to_be_visible(timeout=30000)
    expect(pg.get_by_text("restarting")).to_be_visible()
    print("OK retry | errors:", errs[:3]); b.close()
