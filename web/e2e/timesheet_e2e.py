"""Timekeeper: open a tender and work in it, then the Timesheet shows the session, what was done, rounded billable time and AI time; manual entry; CSV."""
import json, re, urllib.request
from playwright.sync_api import sync_playwright, expect

SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/audit/"

def api(m, p, b=None, t=None):
    h = {"Content-Type": "application/json"}
    if t: h["Authorization"] = "Bearer " + t
    return json.load(urllib.request.urlopen(urllib.request.Request("http://localhost:8000" + p, data=json.dumps(b).encode() if b else None, method=m, headers=h)))

tok = api("POST", "/api/auth/login", {"email": "rick@3bearsprojects.co.nz", "password": "a long test password"})["token"]
tid = next(t["id"] for t in api("GET", "/api/tenders", t=tok)["tenders"] if "Hobsonville" in t["name"])

with sync_playwright() as p:
    b_ = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    ctx = b_.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pings = []; pg.on("request", lambda r: pings.append(json.loads(r.post_data)) if r.url.endswith("/api/time/ping") else None)
    pg.goto("http://localhost:5173/"); pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click(); pg.wait_for_timeout(1200)
    pg.evaluate(f"location.hash = '#/tenders/{tid}/qs'"); pg.wait_for_timeout(1500)
    for i in range(12):                                                    # ~12 s of real activity
        pg.mouse.move(100 + i * 10, 200); pg.wait_for_timeout(1000)
    pg.evaluate(f"location.hash = '#/tenders/{tid}/commercial'"); pg.wait_for_timeout(1500)
    pg.get_by_role("button", name="All tenders").click(); pg.wait_for_timeout(1500)       # leaving the tender sends the closing ping
    assert pings and pings[0]["tender_id"] == tid and pings[-1]["end"] is True, pings
    assert sum(p["active_seconds"] for p in pings) >= 8, pings
    pg.get_by_role("button", name="Timesheet").click(); pg.wait_for_timeout(1500)
    expect(pg.get_by_role("heading", name="Timesheet")).to_be_visible()
    expect(pg.get_by_test_id("time-group")).to_have_count(1)
    expect(pg.get_by_test_id("time-group")).to_contain_text("Hobsonville")
    expect(pg.get_by_test_id("time-group")).to_contain_text("6m")                        # a few active seconds are billed as one 6-minute unit
    pg.get_by_test_id("time-group").click(); pg.wait_for_timeout(500)
    expect(pg.get_by_test_id("time-entry")).to_have_count(1)
    expect(pg.get_by_test_id("time-entry")).to_contain_text("Created the tender")      # what was done is read back from the platform
    pg.get_by_label("Session note").fill("Checked earthworks quantities"); pg.get_by_label("Session note").blur(); pg.wait_for_timeout(800)
    # round up unit
    pg.get_by_label("Round up to").select_option("15"); pg.wait_for_timeout(800)
    expect(pg.get_by_test_id("time-group")).to_contain_text("15m")
    # manual entry
    pg.get_by_role("button", name="Add manual time").click()
    pg.get_by_label("Minutes").fill("20"); pg.get_by_label("What was it for?").fill("Phone call with client")
    pg.get_by_label("Tender (optional)").select_option(label=pg.locator("option", has_text="Hobsonville").first.inner_text())
    pg.get_by_role("button", name="Add time").click(); pg.wait_for_timeout(1000)
    expect(pg.get_by_test_id("time-group")).to_contain_text("30m")                       # 20 min manual + a few seconds -> 21 min -> two 15-min units
    pg.screenshot(path=SHOT + "timesheet.png")
    with pg.expect_download() as d: pg.get_by_role("button", name="CSV (per day)").click()
    csv = open(d.value.path()).read()
    assert "Billable minutes (rounded up to 15)" in csv and "Phone call with client" in csv and "Checked earthworks quantities" in csv, csv
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(500)
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    pg.screenshot(path=SHOT + "timesheet_phone.png")
    assert not errs, errs
print("OK")
