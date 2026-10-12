import io, sys
import pypdf
from playwright.sync_api import sync_playwright, expect

SHOTS = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
def pdf_text(b): return "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(b)).pages)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True).new_page()
    errs = []; pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    nav = lambda n: pg.locator("aside").get_by_role("button", name=n).click()
    nav("Register")
    expect(pg.get_by_role("tab", name="RFIs 18")).to_be_visible()
    expect(pg.locator("main")).to_contain_text("Open RED RFIs")
    expect(pg.locator("main")).to_contain_text("RFI-15")
    pg.screenshot(path=SHOTS + "rg_0_rfis.png", full_page=True)
    for tab, n in [("Risks", 15), ("Assumptions", 9), ("Exclusions", 3), ("Inclusions", 0), ("Documents", 9)]:
        pg.get_by_role("tab", name=f"{tab} {n}").click(); pg.wait_for_timeout(200)
        assert pg.locator("main").inner_text().count("NaN") == 0
    pg.get_by_role("tab", name="Risks 15").click(); pg.screenshot(path=SHOTS + "rg_1_risks.png", full_page=True)

    # edit: close RFI-15, add an RFI, delete an assumption
    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_role("tab", name="RFIs 18").click()
    pg.get_by_label("RFI-15 status").select_option("CLOSED")
    pg.get_by_role("button", name="Add RFI").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_role("button", name="Add RFI").click(); expect(dlg.get_by_role("alert")).to_contain_text("Describe the RFI")
    dlg.get_by_label("Title").fill("Confirm crossing width with Council"); dlg.get_by_label("Detail").fill("Council to confirm the public crossing width before pricing is released.")
    dlg.get_by_label("Rating").select_option("RED"); dlg.get_by_role("button", name="Add RFI").click()
    pg.wait_for_timeout(1500)
    expect(pg.get_by_role("tab", name="RFIs 19")).to_be_visible()
    pg.get_by_role("tab", name="Assumptions 9").click()
    pg.get_by_role("button", name="Delete A9").click(); pg.wait_for_timeout(1200)
    expect(pg.get_by_role("tab", name="Assumptions 8")).to_be_visible()
    pg.get_by_role("button", name="Review & save").click()
    dlg = pg.locator("dialog[open]").last
    dlg.locator("textarea").fill("Closed RFI-15, added crossing RFI, removed A9"); dlg.get_by_role("button", name="Save revision").click()
    expect(pg.get_by_text("changes from #")).to_be_visible(timeout=20000)
    nav("Register"); pg.wait_for_timeout(800)
    expect(pg.get_by_role("tab", name="RFIs 19")).to_be_visible(); expect(pg.get_by_role("tab", name="Assumptions 8")).to_be_visible()
    # the report follows the register
    nav("Client Outputs")
    with pg.expect_download() as d:
        pg.get_by_role("button", name="Download PDF").first.click()
    t = pdf_text(open(d.value.path(), "rb").read())
    assert "Confirm crossing width with Council" in t and "RFI-18" in t and "Current decision blockers" in t
    blockers = t.split("Current decision blockers")[1][:1800]
    assert "RFI-15" not in blockers and "RFI-16" in blockers and "RFI-18" in blockers, blockers
    print("OK register | console errors:", errs[:3]); b.close()
