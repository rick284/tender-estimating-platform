"""Programme: the 'throughout' tick and the Remove button never wrap onto several lines, at normal and narrower widths."""
from playwright.sync_api import sync_playwright, expect

SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    errs = []
    for width in (1440, 1100):
        pg = b.new_context(viewport={"width": width, "height": 900}).new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:5173/")
        pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
        pg.get_by_role("button", name="Sign in").click()
        pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
        expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
        pg.locator("aside").get_by_role("button", name="Programme").click()
        pg.get_by_role("button", name="Edit", exact=True).click(); expect(pg.get_by_text("Editing", exact=True).first).to_be_visible()
        expect(pg.locator("td[data-col=remove]").first).to_be_visible(timeout=20000)
        for col in ("flag", "remove"):
            cells = pg.locator(f"td[data-col={col}]")
            for i in range(cells.count()):
                lines = cells.nth(i).evaluate("""e => { let most = 0; const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
                    while (w.nextNode()) { if (!w.currentNode.textContent.trim()) continue; const r = document.createRange(); r.selectNodeContents(w.currentNode); most = Math.max(most, r.getClientRects().length); } return most; }""")
                assert lines <= 1, (width, col, i, "wraps onto several lines", cells.nth(i).inner_text())
        task = pg.locator("table.grid-table tbody tr").nth(1).locator("td").nth(1).bounding_box()
        assert task["width"] >= 250, (width, "Task column crushed", task)                   # the task name needs room to read
        wrap = pg.locator("table.grid-table").first.evaluate("t => [t.parentElement.scrollWidth, t.parentElement.clientWidth]")
        if width >= 1440:
            assert wrap[0] <= wrap[1] + 1, (width, "needs sideways scrolling to reach the Remove button", wrap)
        rb = pg.locator("td[data-col=remove] button").first.bounding_box()
        assert rb["height"] < 40, ("Remove button too tall", rb)
        pg.screenshot(path=SHOT + f"programme_{width}.png", clip={"x": 0, "y": 0, "width": width, "height": 600})
        pg.close()
    print("OK programme layout | errors:", errs[:3]); b.close()
