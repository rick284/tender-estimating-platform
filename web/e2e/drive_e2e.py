"""Drive page with the Drive API stubbed in the browser (real Google cannot be reached from a sandbox)."""
import json
from playwright.sync_api import sync_playwright, expect

SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/tp/e2e/"
state = {"connected": False, "folder": None}
F = lambda i, n, p="", rev=None, latest=None, sup=None, arch=False: {"id": i, "name": n, "path": p, "mime": "application/pdf", "is_folder": False, "modified": "2026-10-02T01:00:00Z",
    "size": 1500000, "link": "https://drive.google.com/x", "revision": rev, "latest": latest, "superseded_by": sup, "in_archive": arch}
LISTING = {"folder": {"id": "T1", "name": "329 Hobsonville Road", "url": "https://drive.google.com/t1"}, "truncated": False,
    "structure": [{"number": n, "label": l, "found": i != 3, "actual": l if i != 3 else None, "exact": i not in (2, 3)} for i, (n, l) in enumerate([("01", "Client Issue Pack"), ("02", "Tender Source Documents"), ("03", "Supplier and Subcontractor Quotes"), ("04", "RFIs Correspondence and Clarifications"), ("05", "Takeoffs Markups and Programme"), ("06", "Estimating Working Files"), ("07", "Superseded and Archive")])],
    "counts": {"files": 4, "latest_revisions": 2, "superseded": 1, "ambiguous_groups": 0, "loose_in_root": 1},
    "files": [F("1", "Drawings RevC.pdf", "01 Client Issue Pack", "C", True), F("2", "Drawings RevB.pdf", "01 Client Issue Pack", "B", False, "Drawings RevC.pdf"),
              F("3", "Estimate_Rev34E.xlsx", "", "34E", True), F("4", "Spec.pdf", "01 Client Issue Pack")]}

def route(r):
    p = r.request.url.split("/api/drive")[1].split("?")[0]; m = r.request.method
    j = lambda b, s=200: r.fulfill(status=s, content_type="application/json", body=json.dumps(b))
    if p == "/status": return j({"configured": True, "connected": state["connected"], "account": "rick@gmail.example", "connected_at": None, "read_only": True, "standard_folders": []})
    if p == "/connect": state["connected"] = True; return j({"url": "http://localhost:5173/#/tenders"})
    if p == "/folders": return j({"parent": "root", "folders": [{"id": "T1", "name": "329 Hobsonville Road"}]})
    if p.startswith("/tenders/") and p.endswith("/files"): return j(LISTING)
    if p.startswith("/tenders/") and m == "PUT": state["folder"] = LISTING["folder"]; return j({"folder": LISTING["folder"]})
    if p.startswith("/tenders/"): return j({"folder": state["folder"]})
    return j({"detail": "unexpected"}, 500)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/api/drive/**", route)
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.locator("aside").get_by_role("button", name="Drive Documents").click()
    expect(pg.get_by_role("button", name="Connect Google Drive")).to_be_visible()
    state["connected"] = True; pg.reload()
    expect(pg.get_by_role("button", name="Choose folder")).to_be_visible(timeout=15000)
    pg.get_by_role("button", name="Choose folder").click()
    pg.get_by_role("button", name="Use this folder").click()
    expect(pg.get_by_text("Drawings RevB.pdf")).to_be_visible(timeout=10000)
    expect(pg.get_by_text("Superseded", exact=True).first).to_be_visible()
    expect(pg.get_by_text("Missing")).to_have_count(1)
    pg.screenshot(path=SHOT + "drive_1.png", full_page=True)
    pg.get_by_label("Hide superseded").check() if False else pg.get_by_text("Hide superseded").click()
    expect(pg.get_by_text("Drawings RevB.pdf")).to_have_count(0)
    print("OK drive page | page errors:", errs); b.close()
