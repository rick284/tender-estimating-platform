import io
import pypdf
from playwright.sync_api import sync_playwright, expect

def pdf_text(b): return "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(b)).pages)

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
    nav("Quotes")
    expect(pg.locator("main")).to_contain_text("Quotes recorded"); expect(pg.locator("main")).to_contain_text("Q-14")
    assert pg.locator("tbody tr").count() == 14
    pg.screenshot(path="/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/q_0.png", full_page=True)
    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_label("Q-05 status").fill("RECEIVED 14-Oct - FORMCON $52,400")
    pg.get_by_role("button", name="Add quote").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_role("button", name="Add quote").click(); expect(dlg.get_by_role("alert")).to_contain_text("Name the package")
    dlg.get_by_label("Supplier").fill("Acme Aggregates"); dlg.get_by_label("Package or item").fill("AP40 delivered"); dlg.get_by_label("Amount excl. GST").fill("12345.5")
    dlg.get_by_label("Notes (quote number, date, what it says)").fill("Quote 123 dated 1 Oct"); dlg.get_by_role("button", name="Add quote").click()
    pg.wait_for_timeout(1200)
    assert pg.locator("tbody tr").count() == 15
    pg.get_by_role("button", name="Delete Q-14").click(); pg.wait_for_timeout(1200)
    assert pg.locator("tbody tr").count() == 14
    pg.get_by_role("button", name="Review & save").click()
    dlg = pg.locator("dialog[open]").last
    dlg.locator("textarea").fill("Formcon quote received, added Acme aggregates, removed Q-14"); dlg.get_by_role("button", name="Save revision").click()
    expect(pg.get_by_text("changes from #")).to_be_visible(timeout=20000)
    nav("Client Outputs")
    with pg.expect_download() as d:
        pg.get_by_role("button", name="Download PDF").nth(2).click()
    t = pdf_text(open(d.value.path(), "rb").read())
    assert "Acme Aggregates" in t and "Quote 123" in t and "Verification Index" in t
    with pg.expect_download() as d:
        pg.get_by_role("button", name="Download PDF").nth(3).click()
    t = pdf_text(open(d.value.path(), "rb").read())
    assert "FORMCON" in t and "$12,345.50" in t and "Control note" in t
    print("OK quotes | console errors:", errs[:3]); b.close()
