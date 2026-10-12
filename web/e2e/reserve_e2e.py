"""Management Reserve page: the policy's Hobsonville worked example entered through the screen, range and selected reserve checked, live total equals the engine's."""
import sys
sys.path.insert(0, "/home/user/tender-estimating-platform/engine")
from playwright.sync_api import sync_playwright, expect
from tender_engine.importers import load_master_workbook
from tender_engine.edits import apply_edits
from tender_engine.estimate import compute_estimate

base = load_master_workbook("/home/user/tender-estimating-platform/private/Rev34E.xlsx")
fmt = lambda v: "${:,.2f}".format(v)
edits = [{"target": "reserve", "key": "block", "field": "selected", "value": "17000"}]
before = compute_estimate(base)["summary"]["all_in"]
after = compute_estimate(apply_edits(base, edits)[0])["summary"]["all_in"]
SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.locator("aside").get_by_role("button", name="Management Reserve").click()
    expect(pg.get_by_text("No unresolved items recorded").first).to_be_visible()
    expect(pg.get_by_text("$23,642.32").first).to_be_visible()                 # 18,269.06 pre-margin = $23,642.32 tender effect at 10% / 15%
    pg.screenshot(path=SHOT + "mr_1.png", full_page=True)
    pg.get_by_role("button", name="Edit", exact=True).click()

    def add(title, src, impact, lo, hi, basis="Sell"):
        pg.get_by_role("button", name="Add item").click()
        d = pg.locator("dialog[open]").last
        d.get_by_label("Unresolved item").fill(title); d.get_by_label("Where it comes from (RFI, risk, quote)").fill(src)
        d.get_by_label("Extra cost if adverse ($)").fill(impact); d.get_by_label("Entered as").select_option(basis)
        d.get_by_label("Probability, low (%)").fill(lo); d.get_by_label("Probability, high (%)").fill(hi)
        d.get_by_role("button", name="Add item").click()
    add("Rev17 vs Yodha earthworks", "RFI-15 / RT01", "28600", "55", "65")
    add("Ramp / entry / stairs ownership", "RFI-14B", "9500", "30", "40")
    pg.wait_for_timeout(1200)
    expect(pg.get_by_text("$18,580.00 – $22,390.00")).to_be_visible()
    expect(pg.get_by_text("Midpoint $20,485.00")).to_be_visible()
    pg.get_by_label("selected reserve").fill("17000")
    pg.get_by_label("rationale").fill("Upper end of the weighted range less the unquantified tails")
    pg.wait_for_timeout(1500)
    expect(pg.get_by_text("Within the weighted range")).to_be_visible()
    bar = pg.locator("div.fixed.bottom-0").inner_text()
    assert fmt(after) in bar and fmt(before) in bar, ("bar", bar)
    pg.screenshot(path=SHOT + "mr_2.png", full_page=True)
    print("OK management reserve | engine", fmt(before), "->", fmt(after), "| errors:", errs[:3]); b.close()
