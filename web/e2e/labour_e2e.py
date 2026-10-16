"""Labour true-cost builder: live build-up, add to the library through the edit draft, save, reopen the build-up, rebuild with history."""
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
    nav("Rate Library")
    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_role("button", name="Build labour rate").click()
    d = pg.locator("dialog[open]").last
    d.get_by_label("Rate code").fill("LAB-CARP"); d.get_by_label("Role").fill("Carpenter")
    d.get_by_label("Employment basis").fill("Permanent, full time"); d.get_by_label("Source date").fill("2012")
    for label, v in (("Gross hourly rate", "25"), ("Paid hours a week", "45"), ("Productive hours", "38"), ("KiwiSaver", "2"), ("Insurance and ACC levies", "6.35"),
                     ("Redundancy provision", "2"), ("Leading-hand loading", "5"), ("Weekly allowances (tools, clothing, phone)", "45")):
        d.get_by_label(label, exact=True).fill(v)
    expect(d.get_by_text("$41.04")).to_be_visible(timeout=8000)            # the NZIQS handbook example (its leading-hand line differs by 3c: see tests)
    expect(d.get_by_text("AMBER", exact=True)).to_be_visible()
    d.get_by_label("Gross hourly rate").fill("0"); expect(d.get_by_role("alert")).to_contain_text("more than zero"); d.get_by_label("Gross hourly rate").fill("25")
    pg.screenshot(path=SHOTS + "lab_1.png")
    d.get_by_role("button", name="Add to rate library").click()
    expect(pg.get_by_text("LAB-CARP")).to_be_visible()
    pg.get_by_role("button", name="Review & save").click()
    dlg = pg.locator("dialog[open]").last
    dlg.locator("textarea").fill("Added carpenter labour rate"); dlg.get_by_role("button", name="Save revision").click(); pg.wait_for_timeout(2500)
    nav("Rate Library")
    expect(pg.get_by_text("build-up AMBER")).to_be_visible()
    pg.get_by_text("build-up AMBER").click()
    expect(pg.locator("dialog[open]").last.get_by_text("$41.04")).to_be_visible()
    pg.locator("dialog[open]").last.get_by_role("button", name="Close", exact=True).last.click()
    # rebuild with a company actual: history is kept, status moves
    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_text("build-up AMBER").click()
    d = pg.locator("dialog[open]").last
    d.get_by_label("Gross hourly rate").fill("26"); d.locator("select").select_option("company actual"); d.get_by_text("An independent check").click()
    expect(d.get_by_text("GREEN", exact=True)).to_be_visible(timeout=8000)
    d.get_by_role("button", name="Update this rate").click(); pg.wait_for_timeout(1500)
    expect(pg.locator("div.fixed.bottom-0")).to_contain_text("change")
    pg.screenshot(path=SHOTS + "lab_2.png")
    assert not errs, errs
    print("labour e2e ok")
