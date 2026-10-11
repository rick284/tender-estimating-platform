import io, re, sys
sys.path.insert(0, "/home/user/tender-estimating-platform/engine")
import openpyxl
from playwright.sync_api import sync_playwright, expect
from tender_engine.importers import load_master_workbook
from tender_engine.edits import apply_edits
from tender_engine.estimate import compute_estimate

base = load_master_workbook("/home/user/tender-estimating-platform/private/Rev34E.xlsx")
p0 = compute_estimate(base)["programme"]
ew02 = next(t for t in p0["tasks"] if t["code"] == "EW02")
E1 = [{"target": "programme_task", "key": ew02["id"], "field": "override_days", "value": "30"}]            # EW02 (not critical) stretched to 30 days
p1 = compute_estimate(apply_edits(base, E1)[0])["programme"]
print("engine:", p0["duration"], "->", p1["duration"], "| EW02 float", ew02["float"])
assert p1["duration"] > p0["duration"] == 55 and ew02["float"] > 0

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
    nav("Programme")
    expect(pg.locator("main")).to_contain_text("55 WD"); expect(pg.locator("main")).to_contain_text("finishes 2026-12-16")
    expect(pg.locator("main")).to_contain_text("ESC01  ›  EW01  ›  PRG-RF01  ›  EW03")
    assert pg.get_by_text("Critical", exact=True).count() == 10
    pg.screenshot(path="/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/pr_0.png", full_page=True)
    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_label("EW02 days").fill("30"); pg.wait_for_timeout(1500)
    expect(pg.locator("main")).to_contain_text(f"{p1['duration']} WD")
    pg.get_by_role("button", name="Add control task").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_role("button", name="Add task").click(); expect(dlg.get_by_role("alert")).to_contain_text("task code")
    dlg.get_by_label("Code", exact=True).fill("PRG-TEST"); dlg.get_by_label("Name", exact=True).fill("Test hold"); dlg.get_by_label("Working days").fill("2"); dlg.get_by_label("Follows (task codes)").fill("RH01")
    dlg.get_by_role("button", name="Add task").click(); pg.wait_for_timeout(1500)
    expect(pg.locator("main")).to_contain_text(f"{p1['duration'] + 2} WD")
    pg.get_by_role("button", name="Remove PRG-TEST").click(); pg.wait_for_timeout(1500)
    expect(pg.locator("main")).to_contain_text(f"{p1['duration']} WD")
    pg.get_by_role("button", name="Review & save").click()
    d = pg.locator("dialog[open]").last
    d.locator("textarea").fill("Stretched EW02 to 30 days"); d.get_by_role("button", name="Save revision").click()
    try:
        expect(pg.get_by_text(re.compile(r"changes? from #"))).to_be_visible(timeout=15000)
    except AssertionError:
        pg.screenshot(path="/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/pr_fail.png"); print("MAIN:", pg.locator("main").inner_text()[:700]); raise
    nav("Client Outputs")
    with pg.expect_download() as dl:
        pg.get_by_role("button", name="Download Excel").nth(1).click()
    wb = openpyxl.load_workbook(io.BytesIO(open(dl.value.path(), "rb").read()))
    assert wb.sheetnames == ["Programme", "MS Project Import"] and f"{p1['duration']} working days" in wb["Programme"]["A2"].value
    print("OK programme | console errors:", errs[:3]); b.close()
