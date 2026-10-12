"""QS Takeoff: the Unit column is wide enough for 'week' and 'visit' (it used to wrap to 'wee / k') and the Qty box fits, in view and edit mode."""
from playwright.sync_api import sync_playwright, expect

SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    errs = []
    for width in (1440, 1100, 820):
        pg = b.new_context(viewport={"width": width, "height": 900}).new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:5173/")
        pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
        pg.get_by_role("button", name="Sign in").click()
        pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
        expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
        if width < 1024:                                                         # below this the side menu is a drawer
            pg.get_by_role("button", name="Open navigation").click()
        pg.locator("aside").get_by_role("button", name="QS Takeoff").click()
        expect(pg.locator("td[data-col=unit]").first).to_be_visible(timeout=20000)
        for mode in ("view", "edit"):
            if mode == "edit":
                pg.get_by_role("button", name="Edit", exact=True).click(); expect(pg.get_by_text("Editing", exact=True).first).to_be_visible()
            cells = pg.locator("td[data-col=unit]")
            n = cells.count(); assert n > 20
            for i in range(n):
                el = cells.nth(i)
                one_line = el.evaluate("e => { const r = document.createRange(); r.selectNodeContents(e); return r.getClientRects().length <= 1; }")
                assert one_line, (width, mode, "unit text wraps", el.inner_text())
            if mode == "edit":
                qty = pg.get_by_label("PG01 quantity"); cell = qty.locator("xpath=ancestor::td")
                qb, cb = qty.bounding_box(), cell.bounding_box()
                assert qb["x"] >= cb["x"] - 0.5 and qb["x"] + qb["width"] <= cb["x"] + cb["width"] + 0.5, (width, "qty box overflows its column", qb, cb)
            pg.screenshot(path=SHOT + f"qs_cols_{width}_{mode}.png", clip={"x": 0, "y": 0, "width": width, "height": 520})
        pg.close()
    print("OK qs columns | errors:", errs[:3]); b.close()
