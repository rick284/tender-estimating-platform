"""Risk Truth page: gate banner on the real Hobsonville Rev34E, then add an exposure with a distinct CA02 provision and check the live total equals the engine's."""
import sys
sys.path.insert(0, "/home/user/tender-estimating-platform/engine")
from playwright.sync_api import sync_playwright, expect
from tender_engine.importers import load_master_workbook
from tender_engine.edits import apply_edits
from tender_engine.estimate import compute_estimate

base = load_master_workbook("/home/user/tender-estimating-platform/private/Rev34E.xlsx")
ADD = {"target": "exposure", "op": "add", "key": "X-e2e00001", "value": {"consequence": "Distinct residual", "cost_ref": "ZZ99", "mode": "Fixed Allowance", "evidence": "AMBER", "include": "No"}}
SETS = [("provision", "10000"), ("include", "Yes"), ("target", "CA02"), ("distinct", "Yes"), ("integration_complete", "Yes")]
edits = [ADD] + [{"target": "exposure", "key": "X-e2e00001", "field": f, "value": v} for f, v in SETS]
fmt = lambda v: "${:,.2f}".format(v)
before = compute_estimate(base)["summary"]["all_in"]
after = compute_estimate(apply_edits(base, edits)[0])["summary"]["all_in"]
print("engine:", fmt(before), "->", fmt(after))
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
    nav = lambda n: pg.locator("aside").get_by_role("button", name=n).click()
    nav("Risk Truth")
    expect(pg.get_by_text("Release hold")).to_be_visible()
    expect(pg.get_by_text("4 red risk(s) and 4 red exposure(s); 11 amber.")).to_be_visible()
    expect(pg.locator("tbody tr", has_text="RT13-001").first).to_contain_text("RED")
    pg.screenshot(path=SHOT + "risk_1.png", full_page=True)
    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_role("button", name="Add exposure").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_placeholder("e.g. EW02 / ES03 / CA10").fill("ZZ99")
    dlg.get_by_label("Cost consequence").fill("Distinct residual")
    dlg.get_by_label("Calculation mode").select_option("Fixed Allowance")
    dlg.get_by_role("button", name="Add exposure").click()
    row = pg.locator("tbody tr", has_text="RT-001").first if False else pg.locator("tbody tr", has_text="Distinct residual").first
    row.click()
    ref = row.locator("td").first.inner_text().strip()
    pg.get_by_label(f"{ref} provision").fill("10000")
    pg.get_by_label(f"{ref} include new risk cost").select_option("Yes")
    pg.get_by_label(f"{ref} integration target").select_option("CA02")
    pg.get_by_label(f"{ref} residual distinct").select_option("Yes")
    pg.get_by_label(f"{ref} integration complete").select_option("Yes")
    pg.wait_for_timeout(1500)
    bar = pg.locator("div.fixed.bottom-0").inner_text()
    assert fmt(after) in bar and fmt(before) in bar, ("bar", bar)
    pg.screenshot(path=SHOT + "risk_2.png", full_page=True)
    print("OK risk truth | bar:", " | ".join(bar.split("\n")), "| errors:", errs[:3]); b.close()
