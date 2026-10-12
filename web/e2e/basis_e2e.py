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
    # the risk lines: from Risk Truth, or by hand as a percentage or PC sum (also when switched off)
    assert pg.get_by_label("CA01 basis").locator("option").all_inner_texts() == ["From Risk Truth (platform)", "Percentage", "PC sum ($)"]
    pg.get_by_label("CA01 basis").select_option(label="PC sum ($)")
    pg.get_by_label("CA01 amount").fill("5000"); pg.wait_for_timeout(1500)
    expect(pg.locator("tr", has_text="CA01")).to_contain_text("$5,000.00")
    pg.get_by_label("CA02 basis").select_option(label="Percentage"); pg.get_by_label("CA02 percentage").fill("0.5"); pg.wait_for_timeout(1500)
    expect(pg.locator("tr", has_text="CA02")).to_contain_text("$2,177.61")                      # 0.5% of 435,521.88
    # the switch, the basis and the value boxes line up down the page
    xs = lambda label: [pg.get_by_label(l).bounding_box()["x"] for l in label]
    assert max(xs(["CA03 basis", "CA04 basis", "CA09 basis", "CA11 basis", "CA01 basis"])) - min(xs(["CA03 basis", "CA04 basis", "CA09 basis", "CA11 basis", "CA01 basis"])) < 1.5, "basis boxes not aligned"
    amounts = xs(["CA04 amount", "CA05 amount", "CA09 percentage", "CA03 amount", "CA01 amount", "CA02 percentage"])
    assert max(amounts) - min(amounts) < 1.5, ("value boxes not aligned", amounts)
    assert max(xs(["CA03 included", "CA04 included", "CA10 included"])) - min(xs(["CA03 included", "CA04 included", "CA10 included"])) < 1.5
    # lines the platform calculates itself elsewhere offer no choice of basis
    assert pg.get_by_label("CA10 basis").count() == 0 and pg.get_by_label("CA16 basis").count() == 0 and pg.get_by_label("CA21 basis").count() == 0
    # overhead and profit can be a fixed amount too
    assert [o for o in pg.get_by_label("CA17 basis").locator("option").all_inner_texts()] == ["Markup %", "Fixed amount ($)"]
    pg.screenshot(path=SHOT + "basis.png", full_page=True)
    pg.get_by_role("button", name="View changes").click()
    expect(pg.get_by_role("dialog")).to_contain_text("Basis")
    print("OK basis choice | errors:", errs[:3]); b.close()
