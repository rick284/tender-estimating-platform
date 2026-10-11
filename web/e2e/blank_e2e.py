import sys
sys.path.insert(0, "/home/user/tender-estimating-platform/engine")
from playwright.sync_api import sync_playwright, expect
from tender_engine.importers import load_master_workbook
from tender_engine.blank import blank_from_template
from tender_engine.edits import apply_edits
from tender_engine.estimate import compute_estimate

SHOTS = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
tpl = load_master_workbook("/home/user/tender-estimating-platform/private/Rev34E.xlsx")
EDITS = [
    {"target": "qs", "op": "add", "key": "EW01", "value": {"section": "Earthworks", "description": "Bulk strip", "unit": "m2", "quantity": "1000", "basis": "MEASURED", "source": "DWG 1"}},
    {"target": "row", "op": "add", "key": "N-blank001", "value": {"qs_code": "EW01", "mode": "Lump Sum / Quote", "resource_code": "", "task": "Bulk strip"}},
    {"target": "row", "key": "N-blank001", "field": "manual_qty", "value": "1"},
    {"target": "row", "key": "N-blank001", "field": "job_rate_override", "value": "10000"},
    {"target": "overlay", "op": "add", "key": "Smith Concrete", "value": {"amount": "5000", "kind": "QUOTED"}},
]
fmt = lambda v: "${:,.2f}".format(v)
expected = compute_estimate(apply_edits(blank_from_template(tpl, "x", {}), EDITS)[0])["summary"]["all_in"]
print("engine expects", fmt(expected))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []; pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    expect(pg.get_by_role("button", name="New tender")).to_be_visible(timeout=15000)
    pg.get_by_role("button", name="New tender").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_role("button", name="Start tender").click()
    expect(dlg.get_by_role("alert")).to_contain_text("name")
    dlg.get_by_label("Tender name").fill("12 Smith Road Subdivision")
    dlg.get_by_label("Client or head contractor").fill("Smith Developments")
    dlg.get_by_label("Location").fill("Albany")
    dlg.locator("summary").click()
    dlg.get_by_label("Scope summary").fill("Civil works for 12 lots.\nIncludes roading.")
    pg.screenshot(path=SHOTS + "bl_0_dialog.png")
    dlg.get_by_role("button", name="Start tender").click()
    expect(pg.get_by_text("Getting started")).to_be_visible(timeout=20000)
    expect(pg.get_by_text("Smith Developments").first).to_be_visible()
    pg.wait_for_timeout(500); pg.screenshot(path=SHOTS + "bl_1_overview.png", full_page=True)

    nav = lambda n: pg.locator("aside").get_by_role("button", name=n).click()
    for edit in (False, True):
        if edit: pg.get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_timeout(400)
        for n in ["Overview", "Consolidated Package", "Tender Build-Up", "QS Takeoff", "Resource Build-Up", "Weather Risk", "Rate Library", "Revisions"]:
            nav(n); pg.wait_for_timeout(500)
            assert pg.get_by_text("This page hit a problem").count() == 0, ("crash on", n, edit)
            txt = pg.locator("main").inner_text()
            assert "NaN" not in txt and "undefined" not in txt, ("bad text on", n, [l for l in txt.split("\n") if "NaN" in l or "undefined" in l][:3])
        if not edit: pg.screenshot(path=SHOTS + "bl_2_revisions.png")

    # build it up
    nav("QS Takeoff"); pg.screenshot(path=SHOTS + "bl_3_qs_empty.png")
    pg.get_by_role("button", name="Add QS item").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_label("Section").select_option("__new"); dlg.get_by_label("New section name").fill("Earthworks")
    dlg.get_by_label("Code", exact=True).fill("EW01"); dlg.get_by_label("Description", exact=True).fill("Bulk strip")
    dlg.get_by_label("Quantity", exact=True).fill("1000"); dlg.get_by_label("Unit", exact=True).fill("m2")
    dlg.get_by_label("Where does the quantity come from?").select_option("MEASURED"); dlg.get_by_label("Source or reference (optional)").fill("DWG 1")
    dlg.get_by_placeholder("Leave blank to price it with build-up rows next").fill("10000")
    dlg.get_by_role("button", name="Add item").click()
    pg.wait_for_timeout(800)
    nav("Consolidated Package")
    pg.get_by_role("button", name="Add subcontract package").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_role("button", name="Add package").click(); expect(dlg.get_by_role("alert")).to_contain_text("Name the package")
    dlg.get_by_label("Package").fill("Smith Concrete"); dlg.get_by_label("Amount excl. GST").fill("5000")
    dlg.get_by_role("button", name="Add package").click()
    pg.wait_for_timeout(1000)
    bar = pg.locator("div.fixed.bottom-0").inner_text()
    assert fmt(expected) in bar, ("bar", bar)
    pg.screenshot(path=SHOTS + "bl_4_consolidated.png")
    pg.get_by_role("button", name="Review & save").click()
    dlg = pg.locator("dialog[open]").last
    dlg.locator("textarea").fill("First pass: strip and concrete sub")
    dlg.get_by_role("button", name="Save revision").click()
    expect(pg.get_by_text("changes from #1")).to_be_visible(timeout=20000)
    nav("Overview"); pg.wait_for_timeout(800)
    assert fmt(expected) in pg.locator("main").inner_text()
    pg.screenshot(path=SHOTS + "bl_5_overview_built.png", full_page=True)
    print("OK", fmt(expected), "console errors:", errs[:3]); b.close()
