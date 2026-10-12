"""Tender Build-Up: when a commercial line is switched on it can be priced as a % or a PC sum (not only the basis it arrived with)."""
from playwright.sync_api import sync_playwright, expect

SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.locator("aside").get_by_role("button", name="Tender Build-Up").click()
    pg.get_by_role("button", name="Edit", exact=True).click()
    # CA09 arrives as a PC sum of $3,000: switch it to 1% of base direct
    expect(pg.get_by_label("CA09 basis")).to_have_value("PC Sum")
    pg.get_by_label("CA09 basis").select_option(label="Percentage")
    pg.get_by_label("CA09 percentage").fill("1"); pg.wait_for_timeout(1500)
    expect(pg.locator("tr", has_text="CA09")).to_contain_text("of base direct")
    expect(pg.locator("tr", has_text="CA09")).to_contain_text("$4,355.22")                      # 1% of 435,521.88
    # CA03 arrives as a % (off): turn it on as a PC sum
    expect(pg.get_by_label("CA03 basis")).to_have_value("%")
    pg.get_by_label("CA03 included").check()
    pg.get_by_label("CA03 basis").select_option(label="PC sum ($)")
    pg.get_by_label("CA03 amount").fill("4000"); pg.wait_for_timeout(1500)
    expect(pg.locator("tr", has_text="CA03")).to_contain_text("$4,000.00")
    # lines the platform calculates itself offer no choice of basis
    assert pg.get_by_label("CA10 basis").count() == 0 and pg.get_by_label("CA16 basis").count() == 0 and pg.get_by_label("CA21 basis").count() == 0
    # overhead and profit can be a fixed amount too
    assert [o for o in pg.get_by_label("CA17 basis").locator("option").all_inner_texts()] == ["Markup %", "Fixed amount ($)"]
    pg.screenshot(path=SHOT + "basis.png", full_page=True)
    pg.get_by_role("button", name="View changes").click()
    expect(pg.get_by_role("dialog")).to_contain_text("Basis")
    print("OK basis choice | errors:", errs[:3]); b.close()
