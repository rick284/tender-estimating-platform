import sys
sys.path.insert(0, "/home/user/tender-estimating-platform/engine")
from playwright.sync_api import sync_playwright, expect
from tender_engine.importers import load_master_workbook
from tender_engine.edits import apply_edits
from tender_engine.estimate import compute_estimate

base = load_master_workbook("/home/user/tender-estimating-platform/private/Rev34E.xlsx")
QS = {"target": "qs", "op": "add", "key": "EW11", "value": {"section": "Earthworks", "description": "Test stripping", "unit": "m2", "quantity": "1000", "basis": "MEASURED", "source": "DWG 301"}}
ROW = {"target": "row", "op": "add", "key": "N-test01", "value": {"qs_code": "EW11", "mode": "Time x Count", "resource_code": "PL-EXC-13", "task": "Strip with excavator"}}
PROD = {"target": "row", "key": "N-test01", "field": "productivity_rate", "value": "100"}
DEL_ROW = {"target": "row", "op": "delete", "key": "EW02-003"}
DEL_QS = {"target": "qs", "op": "delete", "key": "EW04"}
fmt = lambda v: "${:,.2f}".format(v)
exp = lambda edits: compute_estimate(apply_edits(base, edits)[0])["summary"]["all_in"]
before, final, with_qs_delete = exp([]), exp([QS, ROW, PROD, DEL_ROW]), exp([QS, ROW, PROD, DEL_ROW, DEL_QS])
print("engine:", fmt(before), "->", fmt(final), "(if EW04 also deleted:", fmt(with_qs_delete) + ")")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []; pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.get_by_role("button", name="Edit", exact=True).click()
    nav = lambda n: pg.locator("aside").get_by_role("button", name=n).click()
    bar = lambda: pg.locator("div.fixed.bottom-0").inner_text()

    # 1. add a QS item
    nav("QS Takeoff"); pg.get_by_role("button", name="Add QS item").click()
    dlg = pg.locator("dialog")
    dlg.get_by_role("button", name="Add item").click()
    expect(dlg.get_by_role("alert")).to_contain_text("QS code")                       # validation explains itself
    dlg.get_by_label("Code", exact=True).fill("ew11"); dlg.get_by_label("Description", exact=True).fill("Test stripping")
    dlg.get_by_label("Quantity", exact=True).fill("1000"); dlg.get_by_label("Unit", exact=True).fill("m2")
    dlg.get_by_role("button", name="Add item").click()
    expect(dlg.get_by_role("alert")).to_contain_text("Classify")
    dlg.get_by_label("Where does the quantity come from?").select_option("MEASURED"); dlg.get_by_label("Source or reference (optional)").fill("DWG 301")
    dlg.get_by_role("button", name="Add item").click()
    expect(pg.get_by_text("Test stripping")).to_be_visible(timeout=10000)
    expect(pg.get_by_text("1 change")).to_be_visible(timeout=10000)
    pg.screenshot(path="/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/st_1_qs.png")

    # 2. add a build-up row and price it
    nav("Resource Build-Up"); pg.get_by_role("button", name="Add row").click()
    dlg = pg.locator("dialog")
    dlg.get_by_label("QS item").select_option("EW11")
    dlg.get_by_label("Search the rate library").fill("excavator")
    dlg.get_by_label("Library rate").select_option("PL-EXC-13")
    dlg.get_by_label("Description of the row").fill("Strip with excavator")
    dlg.get_by_role("button", name="Add row").click()
    pg.get_by_label("EW11-001 Productivity (units/hr)").fill("100")
    expect(pg.get_by_text("2 changes")).to_be_visible(timeout=10000)
    pg.screenshot(path="/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/st_2_row.png")

    # 3. delete a row (the numbering of later rows shifts; the app keeps edits attached to the right rows)
    pg.locator("select[aria-label='QS code']").select_option("EW02")
    pg.locator("tbody tr", has_text="EW02-003").first.click()
    pg.get_by_role("button", name="Delete row").click()
    expect(pg.get_by_text("EW02-003")).to_have_count(0, timeout=10000)

    # 4. delete a whole QS item, look at the change list, then undo that deletion
    nav("QS Takeoff"); pg.locator("tbody tr", has_text="EW04").first.click()
    pg.get_by_role("button", name="Delete item").click()
    expect(pg.get_by_text("Grassed OLFP diversion channel")).to_have_count(0, timeout=10000)
    pg.get_by_role("button", name="View changes").click()
    dlg = pg.locator("dialog"); expect(dlg.get_by_text("Removed").first).to_be_visible()
    pg.screenshot(path="/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/st_3_changes.png")
    assert fmt(with_qs_delete) in bar(), ("bar total before undo", bar())
    qs_row = dlg.locator("li", has_text="EW04").first
    qs_row.get_by_role("button", name="Undo").click()
    dlg.get_by_role("button", name="Done").click()
    expect(pg.get_by_text("Grassed OLFP diversion channel")).to_be_visible(timeout=10000)
    pg.wait_for_timeout(800)
    assert fmt(final) in bar() and fmt(before) in bar(), ("bar total after undo", bar())
    print("bar after undo:", " | ".join(bar().split("\n")))

    # 5. save with a reason; compare shows the structure changes
    pg.get_by_role("button", name="Review & save").click()
    dlg = pg.locator("dialog"); expect(dlg.get_by_text("Save as new revision")).to_be_visible()
    dlg.locator("textarea").fill("Added stripping item, removed trim labour row")
    dlg.get_by_role("button", name="Save revision").click()
    expect(pg.get_by_role("heading", name="Revisions", exact=True)).to_be_visible(timeout=20000)
    expect(pg.get_by_text("changes from #2")).to_be_visible(timeout=15000)
    pg.wait_for_timeout(1200)
    pg.screenshot(path="/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/st_4_revisions.png", full_page=True)
    nav("Overview"); expect(pg.get_by_text("Edited in the platform")).to_be_visible(timeout=15000)
    assert fmt(final) in pg.locator("main").inner_text()
    print("OK saved", fmt(final), "| console errors:", errs[:3]); b.close()
