"""Project brief: edit who/what/known fields, save a revision, values persist, no sideways scroll on a phone."""
from playwright.sync_api import sync_playwright, expect

SHOTS = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    nav = lambda n: pg.locator("aside").get_by_role("button", name=n).click()
    nav("Project Brief")
    expect(pg.locator("main")).to_contain_text("What the job is")
    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_label("Project owner / developer").fill("Acme Developments Ltd")
    pg.get_by_label("What we know so far").fill("Flat site, services on the street frontage.")
    pg.get_by_label("Estimate level").select_option("Tender")
    pg.get_by_role("button", name="Review & save").click()
    dlg = pg.locator("dialog[open]").last
    dlg.locator("textarea").fill("Recorded the project brief"); dlg.get_by_role("button", name="Save revision").click()
    pg.wait_for_timeout(2500)
    nav("Project Brief")
    expect(pg.locator("main")).to_contain_text("Acme Developments Ltd")
    expect(pg.locator("main")).to_contain_text("Flat site, services")
    pg.screenshot(path=SHOTS + "brief_1.png", full_page=True)
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(400)
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "sideways scroll"
    assert not errs, errs
    print("brief e2e ok")
