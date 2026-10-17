"""Create the job folder: always inside the company's jobs folder / client / job, never My Drive.
Drive API stubbed in the browser (real Google cannot be reached from a sandbox)."""
import json, os
from playwright.sync_api import sync_playwright, expect

SHOT = os.environ.get("SHOT", "/tmp/")
state = {"root": None, "anywhere": False, "linked": None, "posted": None}
ROOT = {"id": "BE", "name": "Blackline Estimating", "url": "https://drive.google.com/be"}

def plan(q):
    client = q.get("client") or "Siteworks (TPW)"; job = q.get("job") or "329 Hobsonville Road Childcare Centre"
    return {"root": state["root"], "client": client, "job": job, "clients": ["Dave Stewart", "Goodman"],
            "client_exists": client == "Dave Stewart", "job_exists": False, "can_write_anywhere": state["anywhere"],
            "folders": ["00 Project Admin", "01 Client Issue Pack", "02 Tender Source Documents", "03 Supplier and Subcontractor Quotes",
                        "04 RFIs Correspondence and Clarifications", "05 Takeoffs Markups and Programme", "06 Estimating Working Files", "07 Superseded and Archive"]}

def route(r):
    url = r.request.url; p = url.split("/api/drive")[1].split("?")[0]; m = r.request.method
    q = dict(x.split("=", 1) for x in url.split("?", 1)[1].split("&")) if "?" in url else {}
    from urllib.parse import unquote_plus
    q = {k: unquote_plus(v) for k, v in q.items()}
    j = lambda b, s=200: r.fulfill(status=s, content_type="application/json", body=json.dumps(b))
    if p == "/status": return j({"configured": True, "connected": True, "account": "rick@3bears.example", "connected_at": None,
                                 "read_only": not state["anywhere"], "can_write": state["anywhere"], "can_write_anywhere": state["anywhere"], "standard_folders": []})
    if p == "/connect": state["anywhere"] = True; return j({"url": "http://localhost:5173/#/tenders"})
    if p == "/folders": return j({"parent": "root", "folders": [ROOT]})
    if p == "/jobs-root" and m == "PUT": state["root"] = ROOT; return j({"folder": ROOT})
    if p == "/jobs-root": return j({"folder": state["root"]})
    if p.endswith("/new-job-plan"): return j(plan(q))
    if p.endswith("/folders") and m == "POST":
        body = json.loads(r.request.post_data); state["posted"] = body
        state["linked"] = {"id": "J1", "name": body["job"], "url": "https://drive.google.com/j1", "linked_at": "2026-10-17T01:00:00Z",
                           "path": f"Blackline Estimating / {body['client']} / {body['job']}"}
        return j({"created": plan(body)["folders"], "folder": state["linked"]})
    if p.endswith("/folder-plan"): return j({"folder": state["linked"], "plan": [], "can_write": True})
    if p.startswith("/tenders/") and p.endswith("/files"):
        return j({"folder": state["linked"], "truncated": False, "structure": [], "counts": {"files": 0, "latest_revisions": 0, "superseded": 0, "ambiguous_groups": 0, "loose_in_root": 0}, "files": []})
    if p.startswith("/tenders/"): return j({"folder": state["linked"]})
    return j({"detail": "unexpected " + p}, 500)

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    for width in (1440, 390):
        state.update(root=None, anywhere=False, linked=None, posted=None)
        pg = b.new_context(viewport={"width": width, "height": 900}).new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/api/drive/**", route)
        pg.goto("http://localhost:5173/")
        pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
        pg.get_by_role("button", name="Sign in").click()
        pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
        expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
        if width < 1024: pg.get_by_role("button", name="Open navigation").click()
        pg.get_by_role("button", name="Drive Documents").last.click()
        expect(pg.get_by_text("My Drive")).to_have_count(0)
        pg.get_by_role("button", name="Create the job folder…").click()
        dlg = pg.get_by_role("dialog")
        expect(dlg.get_by_text("It is never made in My Drive")).to_be_visible()
        # 1. no jobs folder yet and no permission: Create is disabled
        expect(dlg.get_by_role("button", name="Create job folder")).to_be_disabled()
        expect(dlg.get_by_role("button", name="Allow Drive to add folders…")).to_be_visible()
        dlg.get_by_role("button", name="Choose the jobs folder…").click()
        pg.get_by_role("button", name="Use this folder").click()
        dlg = pg.get_by_role("dialog")
        expect(dlg.get_by_text("Blackline Estimating", exact=True)).to_be_visible(timeout=10000)
        # 2. client name picked from the existing client folders
        dlg.get_by_label("Client folder name").fill("Dave Stewart")
        dlg.get_by_label("Job folder name").fill("329 Hobsonville Road")
        expect(dlg.get_by_text("Blackline Estimating / Dave Stewart / 329 Hobsonville Road")).to_be_visible()
        expect(dlg.get_by_text("Client folder exists: used as it is")).to_be_visible(timeout=5000)
        expect(dlg.get_by_text("00 Project Admin")).to_be_visible()
        pg.screenshot(path=f"{SHOT}new_job_{width}_a.png", full_page=True)
        # 3. permission granted (simulated), then create
        state["anywhere"] = True
        dlg.get_by_label("Job folder name").fill("329 Hobsonville Road ")
        expect(dlg.get_by_role("button", name="Create job folder")).to_be_enabled(timeout=5000)
        dlg.get_by_role("button", name="Create job folder").click()
        expect(pg.get_by_text("Blackline Estimating / Dave Stewart / 329 Hobsonville Road")).to_be_visible(timeout=10000)
        assert state["posted"] == {"where": "new", "client": "Dave Stewart", "job": "329 Hobsonville Road"}, state["posted"]
        pg.screenshot(path=f"{SHOT}new_job_{width}_b.png", full_page=True)
        sideways = pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
        assert not sideways and not errs, (sideways, errs)
        print("OK new job folder at", width)
    b.close()
