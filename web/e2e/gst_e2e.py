"""Tender Build-Up: the GST line has its own on/off switch and percentage in edit mode, and the tender is shown incl. GST."""
from playwright.sync_api import sync_playwright, expect

SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.locator("aside").get_by_role("button", name="Tender Build-Up").click()
    row = pg.locator("tr", has_text="CA21")
    expect(row).to_contain_text("GST")                                                           # the GST line is on the page
    expect(row).to_contain_text("Off")
    expect(pg.locator("tr", has_text="Own works tender incl. GST")).to_contain_text("$614,700.22")   # off: incl. = excl.
    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_label("CA21 included").check()                                                      # the switch
    pg.wait_for_timeout(1500)
    expect(pg.locator("tr", has_text="CA21")).to_contain_text("$92,205.03")                       # 15% of 614,700.22
    expect(pg.locator("tr", has_text="Own works tender incl. GST")).to_contain_text("$706,905.26")
    expect(pg.locator("tr", has_text="Own works tender excl. GST")).to_contain_text("$614,700.22")  # excl. unchanged
    bar = pg.locator("div.fixed.bottom-0").inner_text()
    assert "$1,226,916.81" in bar and "(+$0.00)" in bar, bar                                       # the all-in package is excl. GST: no movement
    pg.get_by_label("CA21 percentage").fill("10"); pg.wait_for_timeout(1500)
    expect(pg.locator("tr", has_text="Own works tender incl. GST")).to_contain_text("$676,170.25")
    pg.screenshot(path=SHOT + "gst_on.png", full_page=True)
    pg.get_by_label("CA21 included").uncheck(); pg.wait_for_timeout(1500)
    expect(pg.locator("tr", has_text="Own works tender incl. GST")).to_contain_text("$614,700.22")
    print("OK gst switch | errors:", errs[:3]); b.close()
