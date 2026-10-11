import io, json, sys
sys.path.insert(0, "/home/user/tender-estimating-platform/engine")
import pypdf, openpyxl
from playwright.sync_api import sync_playwright, expect

SHOTS = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
TPW = """# MAIN BUILDING | A
MB/001\tExcavation
MB/002\tConcrete
MB/003\tReinforcing
MB/004  Structural Steel
MB/025  Preliminaries & General   [pg]
MB/026  Margin   [margin]
# CIVIL WORKS | B
CW/001  Site Preparation/Silt Fencing
CW/002  Site Clearance/Demolition
CW/003  Retaining Walls
CW/004  Bulk Earthworks
CW/005  Stormwater Drainage
CW/006  Wastewater Drainage
CW/007  Water Supply
CW/008  Services Trenching
CW/009  Driveways/Car Parking/Vehicle Crossing/Pavements
CW/010  Planting/Soft Landscaping
CW/011  Fencing/Street Furniture
CW/012  Preliminaries & General  [pg]
CW/013  Margin  [margin]"""
SIMPLE = {"EW05": "MB/001", "EW07": "MB/001", "ESC01": "CW/001", "EW01": "CW/002", "RW01": "CW/003", "RW02": "CW/003", "RW03": "CW/003", "RW04": "CW/003",
          "EW02": "CW/004", "EW03": "CW/004", "EW04": "CW/004", "EW08": "CW/004", "EW09": "CW/004", "ES02": "CW/005", "ES03": "CW/005", "ES01": "CW/008",
          "PV01": "CW/009", "PV02": "CW/009", "PV04": "CW/009", "PV05": "CW/009", "ES04": "CW/011", "PG01": "CW/012", "TC01": "CW/012", "RH01": "CW/012",
          "CA09": "CW/012", "CA10": "CW/012"}

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
    nav("Client Outputs")
    expect(pg.get_by_text("Reconciles", exact=True)).to_be_visible()
    expect(pg.locator("main")).to_contain_text("$1,226,916.81")
    pg.screenshot(path=SHOTS + "out_0_auto.png", full_page=True)

    # downloads
    got = {}
    for label, key in [("Download PDF", "report"), ("Download Excel", "xlsx")]:
        with pg.expect_download() as d:
            pg.get_by_role("button", name=label).first.click()
        path = d.value.path(); got[key] = open(path, "rb").read(); print(key, d.value.suggested_filename, len(got[key]))
    assert got["report"].startswith(b"%PDF") and "$1,226,916.81" in pdf_text(got["report"])
    wb = openpyxl.load_workbook(io.BytesIO(got["xlsx"])); assert wb.sheetnames == ["Client Summary", "Price Schedule", "Reconciliation"]

    # client format + mapping
    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.get_by_role("button", name="Use the client's format").click()
    dlg = pg.locator("dialog[open]").last
    dlg.get_by_role("button", name="Use this format").click(); expect(dlg.get_by_role("alert")).to_contain_text("Paste")
    dlg.get_by_label("Schedule name").fill("TPW Main Contract Tender Submission"); dlg.get_by_label("Issued by (client)").fill("HLC PROPERTY LIMITED")
    dlg.get_by_label("Schedule lines").fill(TPW)
    dlg.get_by_role("button", name="Use this format").click()
    expect(pg.get_by_text("Not reconciled", exact=True)).to_be_visible(timeout=15000)
    expect(pg.get_by_text("not mapped").first).to_be_visible()
    for code, line in SIMPLE.items():
        pg.locator(f'select[aria-label^="Schedule line for {code} "]').select_option(f"line:{line}")
    pg.locator('select[aria-label^="Schedule line for CA16 "]').select_option("spread")
    for name in ("Allied public stormwater / detention base", "Allied public setout / as-built / signoff"):
        pg.locator(f'select[aria-label="Schedule line for {name}"]').select_option("line:CW/005")
    # splits through the dialog
    def split(name, parts):
        row = pg.locator("tr", has=pg.locator(f'select[aria-label="Schedule line for {name}"]'))
        row.get_by_role("button", name="Split").click()
        d = pg.locator("dialog[open]").last
        for i in range(len(parts) - 2): d.get_by_role("button", name="Add a part").click()
        for i, (line, amt) in enumerate(parts):
            d.get_by_label(f"Line for part {i + 1}").select_option(f"line:{line}")
            if amt: d.get_by_label(f"Amount for part {i + 1}").fill(amt)
        d.get_by_role("button", name="Save split").click(); pg.wait_for_timeout(500)
    split("Coast Concrete foundation / floor", [("MB/003", "28400"), ("MB/002", "")])
    split("Allied private drainage", [("CW/003", "19211.04"), ("CW/006", "26864.36"), ("CW/005", "")])
    pg.wait_for_timeout(2000)
    expect(pg.get_by_text("Reconciles", exact=True)).to_be_visible(timeout=15000)
    expect(pg.locator("main")).to_contain_text("$292,737.18"); expect(pg.locator("main")).to_contain_text("$934,179.63")
    pg.screenshot(path=SHOTS + "out_1_tpw.png", full_page=True)

    # save, reload, download the client schedule
    pg.get_by_role("button", name="Review & save").click()
    dlg = pg.locator("dialog[open]").last
    dlg.locator("textarea").fill("Set up the TPW price schedule format and mapping"); dlg.get_by_role("button", name="Save revision").click()
    expect(pg.get_by_text("changes from #")).to_be_visible(timeout=20000)
    nav("Client Outputs"); pg.wait_for_timeout(1000)
    expect(pg.get_by_text("Reconciles", exact=True)).to_be_visible(); expect(pg.locator("main")).to_contain_text("TPW Main Contract Tender Submission")
    with pg.expect_download() as d:
        pg.get_by_role("button", name="Download PDF").nth(1).click()
    t = pdf_text(open(d.value.path(), "rb").read())
    for needle in ["HLC PROPERTY LIMITED", "MB/026", "$67,131.18", "$292,737.18", "CW/013", "$934,179.63", "COMBINED TOTAL (EXCL GST)", "$1,226,916.81", "$182,206.00", "$263,895.05"]:
        assert needle in t, needle
    assert "DRAFT" not in t
    print("OK TPW schedule PDF matches the issued return | console errors:", errs[:3]); b.close()
