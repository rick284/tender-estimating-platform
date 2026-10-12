"""Top bar: its bottom line runs straight across from the side menu's brand block, and every control in it is the same height, before and after pressing Edit."""
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
        for mode in ("view", "edit"):
            if mode == "edit":
                pg.get_by_role("button", name="Edit", exact=True).click(); expect(pg.get_by_text("Editing", exact=True).first).to_be_visible()
            brand = pg.locator("aside > div").first.bounding_box()
            bar = pg.locator("div.min-h-16.border-b").first.bounding_box()
            assert abs((brand["y"] + brand["height"]) - (bar["y"] + bar["height"])) < 0.6, (width, mode, "lines not level", brand, bar)
            assert abs(brand["y"] - bar["y"]) < 0.6
            controls = pg.locator("div.min-h-16.border-b select, div.min-h-16.border-b button, div.min-h-16.border-b span.border")
            hs = [round(controls.nth(i).bounding_box()["height"], 1) for i in range(controls.count())]
            assert controls.count() >= 3 and max(hs) - min(hs) < 0.6, (width, mode, "control heights differ", hs)
            pg.screenshot(path=SHOT + f"header_{width}_{mode}.png", clip={"x": 0, "y": 0, "width": width, "height": 120})
        pg.close()
    print("OK header alignment | errors:", errs[:3]); b.close()
