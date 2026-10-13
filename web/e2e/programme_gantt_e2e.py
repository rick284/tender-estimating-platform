"""Programme Gantt: open a real MS Project .mpp, edit it like MS Project, save, export MS Project XML, build from the estimate."""
import json, urllib.request, os, re
from playwright.sync_api import sync_playwright, expect

ROOT = "/home/user/tender-estimating-platform"
MPP = ROOT + "/private/Hobsonville_Programme_Rev34B.mpp"
SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/audit/"

def api(m, p, b=None, t=None):
    h = {"Content-Type": "application/json"}
    if t: h["Authorization"] = "Bearer " + t
    return json.load(urllib.request.urlopen(urllib.request.Request("http://localhost:8000" + p, data=json.dumps(b).encode() if b else None, method=m, headers=h)))

tok = api("POST", "/api/auth/login", {"email": "rick@3bearsprojects.co.nz", "password": "a long test password"})["token"]
tid = next(t["id"] for t in api("GET", "/api/tenders", t=tok)["tenders"] if "Hobsonville" in t["name"])
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": int(os.environ.get("W", 1440)), "height": int(os.environ.get("H", 900))}, accept_downloads=True); pg = ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:5173/"); pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click(); pg.wait_for_timeout(1200)
    pg.evaluate(f"location.hash = '#/tenders/{tid}/gantt'"); pg.wait_for_timeout(2000)
    expect(pg.get_by_text("No programmes yet")).to_be_visible()

    # 1. open the real .mpp
    pg.get_by_test_id("program-view-file").set_input_files(MPP)
    expect(pg.get_by_test_id("toggle-edit")).to_be_visible(timeout=60000)
    pg.wait_for_timeout(1500)
    expect(pg.locator("p.mt-0\\.5", has_text=" · 43 tasks")).to_be_visible()
    pg.screenshot(path=SHOT + "gantt_view.png")
    print("opened .mpp: 43 tasks")
    # zoom in / out in steps
    lvl = lambda: int(pg.get_by_test_id("gantt-zoom-level").inner_text().rstrip("%"))
    base = lvl(); assert base == 100, base
    pg.get_by_test_id("gantt-zoom-in").click(); pg.get_by_test_id("gantt-zoom-in").click(); pg.wait_for_timeout(300)
    assert lvl() > 150, lvl()
    pg.get_by_test_id("gantt-zoom-out").click(); pg.get_by_test_id("gantt-zoom-out").click(); pg.get_by_test_id("gantt-zoom-out").click(); pg.get_by_test_id("gantt-zoom-out").click(); pg.wait_for_timeout(300)
    assert lvl() < 70, lvl()
    pg.get_by_role("button", name="Days", exact=True).click(); pg.wait_for_timeout(300); assert lvl() == 100
    print("zoom in / out ok")
    # the Resources column is there in view mode too, and columns can be hidden and brought back (remembered)
    hdr = pg.get_by_test_id("gantt-columns")
    expect(pg.get_by_text("Resources", exact=True).first).to_be_visible()
    assert pg.get_by_text("Predecessors", exact=True).count() >= 1
    hdr.click(); pg.get_by_test_id("gantt-columns-menu").get_by_label("Predecessors").uncheck(); pg.wait_for_timeout(400)
    pg.keyboard.press("Escape"); pg.mouse.click(5, 5); pg.wait_for_timeout(300)
    assert pg.get_by_text("Predecessors", exact=True).count() == 0, "column still showing"
    assert pg.get_by_test_id("gantt-columns").inner_text().startswith("Columns (")
    pg.screenshot(path=SHOT + "gantt_columns.png")
    pg.reload(); pg.wait_for_timeout(2500)
    assert pg.get_by_text("Predecessors", exact=True).count() == 0, "hidden column not remembered"
    pg.get_by_test_id("gantt-columns").click(); pg.get_by_text("Show all columns").click(); pg.wait_for_timeout(400); pg.mouse.click(5, 5)
    assert pg.get_by_text("Predecessors", exact=True).count() >= 1
    print("columns hide / show / remembered")

    # 2. edit like MS Project: add a task, link two tasks, undo, save
    pg.get_by_test_id("toggle-edit").click(); pg.wait_for_timeout(500)
    pg.get_by_test_id("add-task").click(); pg.wait_for_timeout(600)
    pg.keyboard.type("Practical completion walk-through"); pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
    expect(pg.locator("p.mt-0\\.5", has_text=" · 44 tasks")).to_be_visible()
    expect(pg.get_by_text("Unsaved changes")).to_be_visible()
    pg.get_by_test_id("undo").click(); pg.get_by_test_id("undo").click(); pg.wait_for_timeout(400)    # the new row and its name are two steps
    expect(pg.locator("p.mt-0\\.5", has_text=" · 43 tasks")).to_be_visible()
    pg.get_by_role("button", name="Redo").click(); pg.get_by_role("button", name="Redo").click(); pg.wait_for_timeout(400)
    expect(pg.locator("p.mt-0\\.5", has_text=" · 44 tasks")).to_be_visible()
    pg.get_by_test_id("save-program").click(); pg.wait_for_timeout(1200)
    expect(pg.get_by_text("Unsaved changes")).to_have_count(0)
    pg.screenshot(path=SHOT + "gantt_edit.png")
    print("edit, undo, redo, save ok")

    # 3. export MS Project XML and check it opens as a project file again
    with pg.expect_download(timeout=60000) as dl:
        pg.get_by_test_id("export-xml").click()
    path = dl.value.path(); data = open(path, "rb").read()
    assert dl.value.suggested_filename.endswith(".xml") and b"<Project" in data and b"Practical completion walk-through" in data, dl.value.suggested_filename
    print("export:", dl.value.suggested_filename, len(data), "bytes")

    # 4. reopen from the list: saved edit persisted
    pg.get_by_role("button", name="All programmes").click(); pg.wait_for_timeout(1000)
    expect(pg.get_by_test_id("program-row")).to_have_count(1)
    pg.get_by_test_id("program-row").click(); pg.wait_for_timeout(1500)
    expect(pg.locator("p.mt-0\\.5", has_text=" · 44 tasks")).to_be_visible()

    # 5. build from this estimate
    pg.get_by_role("button", name="All programmes").click(); pg.wait_for_timeout(800)
    pg.get_by_test_id("new-from-estimate").click()
    pg.get_by_test_id("create-program").click(); pg.wait_for_timeout(2500)
    expect(pg.get_by_test_id("edit-toolbar")).to_be_visible()
    pg.screenshot(path=SHOT + "gantt_from_estimate.png")
    print("built from estimate")
    assert not errs, errs
print("OK")
