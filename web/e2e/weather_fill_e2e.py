import re, sys
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
    errs = []; pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    nav = lambda n: pg.locator("aside").get_by_role("button", name=n).click()
    nav("Weather Risk"); pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_role("button", name="Switch on").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_label("Assumed start").fill("2026-10-01"); dlg.get_by_label("Dry programme (WD)").fill("55"); dlg.get_by_role("button", name="Switch on").click()
    expect(pg.get_by_text("Weather tool settings")).to_be_visible(timeout=15000)
    pg.get_by_role("button", name="Fill from programme").click(); pg.wait_for_timeout(2500)
    rows = pg.locator("table").last.locator("tbody tr")
    n = rows.count(); print("activities:", n)
    assert n == 6, n
    txt = pg.locator("main").inner_text()
    assert "NaN" not in txt and "undefined" not in txt
    crit = {r.locator("select").first.input_value() + "|" + r.locator("input[type=date]").first.input_value(): r.locator("input[type=checkbox]").first.is_checked() for r in [rows.nth(i) for i in range(n)]}
    print(crit)
    assert crit["Bulk earthworks|2026-11-05"] is True and crit["Bulk earthworks|2026-10-12"] is False
    pg.get_by_role("button", name="Fill from programme").click()      # nothing left to add: tells you so, adds nothing
    pg.wait_for_timeout(800); assert pg.locator("table").last.locator("tbody tr").count() == 6
    print("OK weather fill | console errors:", errs[:3]); b.close()
