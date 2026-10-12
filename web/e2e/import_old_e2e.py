"""Upload an OLDER job's workbook (no Consolidated Package sheet, quantities below row 40) through the New tender dialog: it loads, reconciles, and says what was left out."""
from playwright.sync_api import sync_playwright, expect

PRIV = "/home/user/tender-estimating-platform/private/Drainage_Rev3.xlsx"
BRIDLE = "/home/user/tender-estimating-platform/private/Bridle_Trail.xlsx"
SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    expect(pg.get_by_role("button", name="New tender")).to_be_visible(timeout=15000)
    pg.get_by_role("button", name="New tender").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_text("Upload a workbook", exact=True).first.click()
    dlg.locator("input[type=file]").set_input_files(PRIV)
    dlg.get_by_role("button", name="Create tender").click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=60000)
    expect(pg.get_by_text("Imported from the workbook: what was left out")).to_be_visible()
    expect(pg.get_by_text("No Consolidated Package sheet")).to_be_visible()
    expect(pg.get_by_text("Reconciled to workbook")).to_be_visible()                                # every figure the workbook shows is reproduced
    pg.screenshot(path=SHOT + "import_old.png", full_page=True)
    pg.locator("aside").get_by_role("button", name="Tender Build-Up").click()
    expect(pg.locator("tr", has_text="Siteworks tender excl. GST")).to_contain_text("$232,838.98")
    pg.locator("aside").get_by_role("button", name="QS Takeoff").click()
    expect(pg.get_by_text("TC01").first).to_be_visible()                                            # the items below row 40 are there
    expect(pg.get_by_text("TC02").first).to_be_visible()
    pg.locator("aside").get_by_role("button", name="Consolidated Package").click()                  # the page opens fine with no packages
    expect(pg.get_by_text("Consolidated").first).to_be_visible()
    # Rick's Bridle Trail Master Rev4.1 (JW Transfer): a formula in the profit cell, rates below row 85, no Consolidated Package
    pg.locator("aside").get_by_role("button", name="All tenders").click()
    expect(pg.get_by_role("button", name="New tender")).to_be_visible(timeout=15000)
    pg.get_by_role("button", name="New tender").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_text("Upload a workbook", exact=True).first.click()
    dlg.locator("input[type=file]").set_input_files(BRIDLE)
    dlg.get_by_role("button", name="Create tender").click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=60000)
    expect(pg.get_by_text("Reconciled to workbook")).to_be_visible()
    expect(pg.get_by_text("held a formula")).to_be_visible()
    pg.locator("aside").get_by_role("button", name="Tender Build-Up").click()
    expect(pg.locator("tr", has_text="Siteworks tender excl. GST")).to_contain_text("$1,622,010.25")
    pg.screenshot(path=SHOT + "import_bridle.png", full_page=True)
    print("OK old workbook import | errors:", errs[:3]); b.close()
