import sys
sys.path.insert(0, "/home/user/tender-estimating-platform/engine")
from playwright.sync_api import sync_playwright, expect
from tender_engine.importers import load_master_workbook
from tender_engine.blank import blank_from_template
from tender_engine.edits import apply_edits
from tender_engine.estimate import compute_estimate

SHOTS = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
tpl = load_master_workbook("/home/user/tender-estimating-platform/private/Rev34E.xlsx")
fmt = lambda v: "${:,.2f}".format(v)
BASE = [
    {"target": "qs", "op": "add", "key": "EW01", "value": {"section": "Earthworks", "description": "Bulk strip", "unit": "m2", "quantity": "1000", "basis": "MEASURED", "source": ""}},
    {"target": "row", "op": "add", "key": "N-wxrow001", "value": {"qs_code": "EW01", "mode": "Time x Count", "resource_code": "PL-EXC-13", "task": "Strip with excavator"}},
    {"target": "row", "key": "N-wxrow001", "field": "productivity_rate", "value": "20"},
    {"target": "row", "key": "N-wxrow001", "field": "weather_exposed", "value": "Yes"},
]
WX = [
    {"target": "weather", "op": "add", "key": "setup", "value": {"station": "Auckland", "start": "2026-10-01", "working_days_per_week": "5", "baseline_wd": "55"}},
    {"target": "weather_activity", "op": "add", "key": "W-wxact001", "value": {"task": "Bulk earthworks", "start": "2026-10-01", "finish": "2026-10-30", "critical": True, "qs_codes": ["EW01"]}},
]
LINK = [{"target": "weather", "key": "links", "field": "daily_uid", "value": "N-wxrow001"}]
def expect_for(edits): return compute_estimate(apply_edits(blank_from_template(tpl, "x", {}), edits)[0])
e_noweather = expect_for(BASE); e_wx = expect_for(BASE + WX); e_link = expect_for(BASE + WX + LINK)
print("engine: no weather", fmt(e_noweather["summary"]["all_in"]), "| live", fmt(e_wx["summary"]["all_in"]), "| with daily link", fmt(e_link["summary"]["all_in"]),
      "| CA10", fmt(e_wx["weather"]["allowance"]), "->", fmt(e_link["weather"]["allowance"]))
assert e_wx["weather"]["allowance"] > 0 and e_link["weather"]["allowance"] > e_wx["weather"]["allowance"]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
    errs = []; pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    expect(pg.get_by_role("button", name="New tender")).to_be_visible(timeout=15000)
    pg.get_by_role("button", name="New tender").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_label("Tender name").fill("Weather test job"); dlg.get_by_role("button", name="Start tender").click()
    expect(pg.get_by_text("Getting started")).to_be_visible(timeout=20000)
    nav = lambda n: pg.locator("aside").get_by_role("button", name=n).click()
    pg.get_by_role("button", name="Edit", exact=True).click()

    # price one exposed plant row
    nav("QS Takeoff"); pg.get_by_role("button", name="Add QS item").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_label("Section").select_option("__new"); dlg.get_by_label("New section name").fill("Earthworks")
    dlg.get_by_label("Code", exact=True).fill("EW01"); dlg.get_by_label("Description", exact=True).fill("Bulk strip")
    dlg.get_by_label("Quantity", exact=True).fill("1000"); dlg.get_by_label("Unit", exact=True).fill("m2")
    dlg.get_by_label("Where does the quantity come from?").select_option("MEASURED")
    dlg.get_by_role("button", name="Add item").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_label("Search the rate library").fill("excavator"); dlg.get_by_label("Library rate").select_option("PL-EXC-13")
    dlg.get_by_label("Description of the row").fill("Strip with excavator"); dlg.get_by_role("button", name="Add row").click()
    pg.get_by_label("EW01-001 Productivity (units/hr)").fill("20")
    pg.get_by_label("EW01-001 weather exposed").check()
    pg.wait_for_timeout(800)

    # weather page: switch on
    nav("Weather Risk")
    expect(pg.get_by_text("Live weather tool")).to_be_visible()
    pg.screenshot(path=SHOTS + "wx_0_off.png", full_page=True)
    pg.get_by_role("button", name="Switch on").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_role("button", name="Switch on").click(); expect(dlg.get_by_role("alert")).to_contain_text("start date")
    dlg.get_by_label("Assumed start").fill("2026-10-01"); dlg.get_by_label("Dry programme (WD)").fill("55")
    dlg.get_by_role("button", name="Switch on").click()
    expect(pg.get_by_text("Weather tool settings")).to_be_visible(timeout=15000)
    # add activity (validation first)
    pg.get_by_role("button", name="Add activity").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_role("button", name="Add activity").click(); expect(dlg.get_by_role("alert")).to_contain_text("type of work")
    dlg.get_by_label("Type of work").select_option("Bulk earthworks")
    dlg.get_by_label("Start", exact=True).fill("2026-10-01"); dlg.get_by_label("Finish", exact=True).fill("2026-10-30")
    dlg.get_by_label("On the critical path").check()
    dlg.get_by_label("EW01").check() if dlg.get_by_label("EW01").count() else dlg.locator("label", has_text="EW01").locator("input").check()
    dlg.get_by_role("button", name="Add activity").click()
    pg.wait_for_timeout(1500)
    expect(pg.get_by_label("Bulk earthworks task")).to_have_value("Bulk earthworks")
    bar = lambda: pg.locator("div.fixed.bottom-0").inner_text()
    assert fmt(e_wx["summary"]["all_in"]) in bar(), ("bar (live, unlinked)", bar(), fmt(e_wx["summary"]["all_in"]))
    # link the daily preliminaries row
    pg.get_by_label("Daily preliminaries row").select_option(pg.get_by_label("Daily preliminaries row").locator("option", has_text="EW01-001").get_attribute("value"))
    pg.wait_for_timeout(1500)
    assert fmt(e_link["summary"]["all_in"]) in bar(), ("bar (daily link)", bar(), fmt(e_link["summary"]["all_in"]))
    pg.screenshot(path=SHOTS + "wx_1_live.png", full_page=True)

    # save and reload
    pg.get_by_role("button", name="Review & save").click()
    dlg = pg.locator("dialog[open]").last
    dlg.locator("textarea").fill("Weather tool switched on with one activity"); dlg.get_by_role("button", name="Save revision").click()
    expect(pg.get_by_text("changes from #1")).to_be_visible(timeout=20000)
    nav("Weather Risk"); pg.wait_for_timeout(2500)
    pg.screenshot(path=SHOTS + "wx_2_saved.png", full_page=True)
    txt = pg.locator("main").inner_text()
    assert "weather tool settings" in txt.lower(), txt[:600]
    assert "NaN" not in txt and "undefined" not in txt, [l for l in txt.split("\n") if "NaN" in l or "undefined" in l]
    assert fmt(e_link["weather"]["allowance"]) in txt, ("allowance on page", fmt(e_link["weather"]["allowance"]))
    # undo path: switch off and back
    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_role("button", name="Switch off").click(); pg.wait_for_timeout(1200)
    expect(pg.get_by_text("Live weather tool").first).to_be_visible()
    # a plain remove of an activity (also checks Remove works for generic targets)
    print("OK", "console errors:", errs[:3]); b.close()
