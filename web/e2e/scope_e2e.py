"""Scope coverage: empty state, add requirements in edit mode, the gate and per-item checks respond, change list, save, report section."""
import io
import pypdf
from playwright.sync_api import sync_playwright, expect

SHOTS = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
def pdf_text(b): return "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(b)).pages)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    nav = lambda n: pg.locator("aside").get_by_role("button", name=n).click()
    nav("Scope Coverage")
    expect(pg.get_by_test_id("scope-gate")).to_contain_text("NOT STARTED")
    expect(pg.locator("main")).to_contain_text("No scope requirements recorded yet")
    pg.screenshot(path=SHOTS + "sc_0_empty.png", full_page=True)

    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_role("button", name="Add requirement").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_role("button", name="Add requirement").click(); expect(dlg.get_by_role("alert")).to_contain_text("Describe the requirement")
    dlg.get_by_label("Requirement", exact=True).fill("Site clearance and strip"); dlg.get_by_label("Priced in (QS codes, CA lines)").fill("EW01"); dlg.get_by_label("Where the requirement comes from").fill("Civil set sheet C3 Rev B")
    dlg.get_by_role("button", name="Add requirement").click(); pg.wait_for_timeout(1500)
    expect(pg.get_by_test_id("scope-row")).to_have_count(1)
    expect(pg.get_by_test_id("scope-row").first).to_contain_text("Complete")
    expect(pg.get_by_test_id("scope-gate")).to_contain_text("HOLD")                         # other priced QS items have no scope home yet
    expect(pg.locator("main")).to_contain_text("QS items with a cost that no requirement refers to")
    # a requirement with no treatment is MISSING; excluding something that carries a cost is CHECK
    pg.get_by_role("button", name="Add requirement").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_label("Requirement", exact=True).fill("Temporary retaining to cut face"); dlg.get_by_label("Price treatment").select_option("")
    dlg.get_by_role("button", name="Add requirement").click(); pg.wait_for_timeout(1200)
    expect(pg.get_by_test_id("scope-row")).to_have_count(2)
    expect(pg.get_by_test_id("scope-row").nth(1)).to_contain_text("Missing")
    pg.get_by_label("SC-001 treatment").select_option("EXCLUDED"); pg.wait_for_timeout(1500)
    expect(pg.get_by_test_id("scope-row").first).to_contain_text("Check")
    expect(pg.get_by_test_id("scope-row").first).to_contain_text("Excluded, but a cost is linked")
    pg.get_by_label("SC-001 treatment").select_option("PRICED"); pg.wait_for_timeout(1500)
    expect(pg.get_by_test_id("scope-row").first).to_contain_text("Complete")
    pg.screenshot(path=SHOTS + "sc_1_edit.png", full_page=True)
    pg.get_by_role("button", name="Review & save").click()
    dlg = pg.locator("dialog[open]").last
    dlg.locator("textarea").fill("Started the scope coverage schedule"); dlg.get_by_role("button", name="Save revision").click()
    pg.wait_for_timeout(2500)
    nav("Scope Coverage")
    expect(pg.get_by_test_id("scope-row")).to_have_count(2)
    # the issued report carries the schedule
    nav("Client Outputs")
    with pg.expect_download() as d: pg.get_by_role("button", name="Download PDF").first.click()
    txt = pdf_text(open(d.value.path(), "rb").read())
    assert "Scope Coverage and Interfaces" in txt and "Site clearance and strip" in txt, txt[:500]
    # phone width: no sideways page scroll
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(400)
    pg.get_by_role("button", name="Open navigation").click(); pg.locator("aside").get_by_role("button", name="Scope Coverage").click(); pg.wait_for_timeout(600)
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    pg.screenshot(path=SHOTS + "sc_2_phone.png", full_page=True)
    assert not errs, errs
print("OK")
