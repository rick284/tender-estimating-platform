"""Commercial page: the one place commercial lines are set up. Add your own allowance, rename/note a line, remove one; everything flows to the Tender Build-Up."""
import json, re, urllib.request
from playwright.sync_api import sync_playwright, expect

SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/audit/"

def api(m, p, b=None, t=None):
    h = {"Content-Type": "application/json"}
    if t: h["Authorization"] = "Bearer " + t
    return json.load(urllib.request.urlopen(urllib.request.Request("http://localhost:8000" + p, data=json.dumps(b).encode() if b else None, method=m, headers=h)))

tok = api("POST", "/api/auth/login", {"email": "rick@3bearsprojects.co.nz", "password": "a long test password"})["token"]
tid = next(t["id"] for t in api("GET", "/api/tenders", t=tok)["tenders"] if "Hobsonville" in t["name"])
money = lambda s: float(re.sub(r"[^0-9.\-]", "", s) or 0)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:5173/"); pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click(); pg.wait_for_timeout(1200)
    pg.evaluate(f"location.hash = '#/tenders/{tid}/overview'"); pg.wait_for_timeout(1500)
    pg.get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_timeout(600)
    pg.get_by_role("button", name="Commercial", exact=True).first.click() if pg.get_by_role("button", name="Commercial", exact=True).count() else pg.evaluate(f"location.hash = '#/tenders/{tid}/commercial'")
    pg.wait_for_timeout(1500)
    expect(pg.get_by_role("heading", name="Commercial")).to_be_visible()
    pg.screenshot(path=SHOT + "commercial_page.png")
    # add two allowances: 1.5% and a PC sum
    pg.get_by_test_id("add-allowance").click()
    pg.get_by_placeholder("e.g. Temporary works").fill("Temporary works"); pg.get_by_label("Percentage (%)").fill("1.5")
    pg.locator("dialog").get_by_role("button", name="Add allowance").click(); pg.wait_for_timeout(1500)
    pg.get_by_test_id("add-allowance").click()
    pg.get_by_placeholder("e.g. Temporary works").fill("Insurance excess"); pg.locator("dialog select").select_option("PC Sum"); pg.get_by_label("Amount ($)").fill("5000")
    pg.locator("dialog").get_by_role("button", name="Add allowance").click(); pg.wait_for_timeout(1500)
    cx1, cx2 = pg.get_by_test_id("line-CX01"), pg.get_by_test_id("line-CX02")
    expect(cx1).to_be_visible(); expect(cx2).to_be_visible()
    assert money(cx2.locator("td").nth(4).inner_text()) == 5000
    # a note and a rename on a platform line
    pg.get_by_label("CA05 note").fill("Agreed with broker"); pg.get_by_label("CA05 description").fill("Contract works insurance"); pg.wait_for_timeout(1200)
    # it flows to the Tender Build-Up
    pg.evaluate(f"location.hash = '#/tenders/{tid}/tender'"); pg.wait_for_timeout(1500)
    expect(pg.get_by_text("Temporary works").first).to_be_visible(); expect(pg.get_by_text("Insurance excess").first).to_be_visible()
    print("flows to Tender Build-Up")
    # remove one again
    pg.evaluate(f"location.hash = '#/tenders/{tid}/commercial'"); pg.wait_for_timeout(1200)
    pg.once("dialog", lambda d: d.accept())
    pg.get_by_label(re.compile("Remove CX02")).click(); pg.wait_for_timeout(1500)
    expect(pg.get_by_test_id("line-CX02")).to_have_count(0)
    # platform lines cannot be removed
    assert pg.get_by_label(re.compile("Remove CA")).count() == 0
    pg.screenshot(path=SHOT + "commercial_edit.png")
    # save as a new revision and reopen
    pg.get_by_role("button", name=re.compile("Review")).click(); pg.wait_for_timeout(600)
    pg.get_by_label(re.compile("reason|Reason", re.I)).first.fill("Added temporary works allowance")
    pg.get_by_role("button", name=re.compile("Save", re.I)).last.click(); pg.wait_for_timeout(3000)
    pg.evaluate(f"location.hash = '#/tenders/{tid}/commercial'"); pg.wait_for_timeout(1500)
    expect(pg.get_by_test_id("line-CX01")).to_be_visible(); expect(pg.get_by_test_id("line-CX02")).to_have_count(0)
    expect(pg.get_by_text("Agreed with broker")).to_be_visible(); expect(pg.get_by_text("Contract works insurance")).to_be_visible()
    print("saved and reopened")
    assert not errs, errs
print("OK")
