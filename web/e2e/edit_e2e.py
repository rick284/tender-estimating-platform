import sys
sys.path.insert(0, "/home/user/tender-estimating-platform/engine")
from playwright.sync_api import sync_playwright, expect
from tender_engine.importers import load_master_workbook
from tender_engine.edits import apply_edits
from tender_engine.estimate import compute_estimate
base = load_master_workbook("/home/user/tender-estimating-platform/private/Rev34E.xlsx")
m, _ = apply_edits(base, [{"target":"qs","key":"EW01","field":"quantity","value":"3000"},
                          {"target":"row","key":"EW02-001","field":"job_rate_override","value":"175"},
                          {"target":"commercial","key":"CA17","field":"pct","value":"0.12"}])
expected = compute_estimate(m)["summary"]["all_in"]; before = compute_estimate(base)["summary"]["all_in"]
fmt = lambda v: "${:,.2f}".format(v)
print("expected all-in", fmt(before), "->", fmt(expected))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width":1440,"height":900}).new_page()
    errs=[]; pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.get_by_role("button", name="Edit", exact=True).click()
    expect(pg.get_by_text("No changes yet")).to_be_visible()
    nav = lambda n: pg.locator("aside").get_by_role("button", name=n).click()
    nav("QS Takeoff")
    q = pg.get_by_label("EW01 quantity"); q.fill("abc")
    expect(pg.get_by_role("alert")).to_contain_text("must be a number", timeout=8000)
    pg.screenshot(path="tp/e2e/ed_1_invalid.png")
    q.fill("3000")
    expect(pg.get_by_text("1 change")).to_be_visible(timeout=8000)
    nav("Resource Build-Up")
    pg.locator("select[aria-label='QS code']").select_option("EW02")
    pg.locator("tbody tr[aria-expanded]").first.click()
    pg.get_by_label("EW02-001 Job rate override ($/hr)").fill("175")
    pg.screenshot(path="tp/e2e/ed_2_row.png")
    nav("Tender Build-Up")
    pg.get_by_label("CA17 percentage").fill("12")
    expect(pg.get_by_text("3 changes")).to_be_visible(timeout=8000)
    pg.wait_for_timeout(600)
    pg.screenshot(path="tp/e2e/ed_3_tender.png")
    bar = pg.locator("div.fixed.bottom-0").inner_text()
    print("bar:", " | ".join(bar.split("\n")))
    assert fmt(expected) in bar, "bar total does not match engine"
    assert fmt(before) in bar
    # revert one value: change count drops, then restore
    nav("QS Takeoff"); pg.get_by_label("EW01 quantity").fill("2105")
    expect(pg.get_by_text("2 changes")).to_be_visible(timeout=8000)
    pg.get_by_label("EW01 quantity").fill("3000"); expect(pg.get_by_text("3 changes")).to_be_visible(timeout=8000)
    pg.get_by_role("button", name="Review & save").click()
    dlg = pg.locator("dialog")
    expect(dlg.get_by_text("Save as new revision")).to_be_visible()
    dlg.get_by_role("button", name="Save revision").click()                          # no reason typed yet
    expect(dlg.get_by_role("alert")).to_contain_text("Write a short reason")       # must explain, not silently do nothing
    pg.screenshot(path="tp/e2e/ed_4_save.png")
    dlg.locator("textarea").fill("Quantity and rate updated for testing; overhead to 12%")
    dlg.get_by_role("button", name="Save revision").click()
    expect(pg.get_by_role("heading", name="Revisions", exact=True)).to_be_visible(timeout=20000)
    expect(pg.get_by_text("3 changes from #2")).to_be_visible(timeout=15000)
    pg.wait_for_timeout(1200)
    pg.screenshot(path="tp/e2e/ed_5_revisions.png", full_page=True)
    nav("Overview")
    expect(pg.get_by_text("Edited in the platform")).to_be_visible(timeout=15000)
    txt = pg.locator("main").inner_text()
    assert fmt(expected) in txt, "saved revision total differs from engine"
    pg.screenshot(path="tp/e2e/ed_6_overview.png")
    print("OK saved revision shows", fmt(expected), "| errors:", errs[:3]); b.close()
