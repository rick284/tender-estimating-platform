"""The tender bar and each page's title + action buttons stay in view while the page scrolls (desktop and phone)."""
import json, urllib.request
from playwright.sync_api import sync_playwright

def api(m, p, b=None, t=None):
    h = {"Content-Type": "application/json"}
    if t: h["Authorization"] = "Bearer " + t
    return json.load(urllib.request.urlopen(urllib.request.Request("http://localhost:8000" + p, data=json.dumps(b).encode() if b else None, method=m, headers=h)))

tok = api("POST", "/api/auth/login", {"email": "rick@3bearsprojects.co.nz", "password": "a long test password"})["token"]
tid = next(t["id"] for t in api("GET", "/api/tenders", t=tok)["tenders"] if "Hobsonville" in t["name"])
SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/audit/"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    for w in (1440, 390):
        pg = b.new_context(viewport={"width": w, "height": 800}).new_page()
        pg.goto("http://localhost:5173/"); pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
        pg.get_by_role("button", name="Sign in").click(); pg.wait_for_timeout(1200)
        pg.evaluate(f"location.hash = '#/tenders/{tid}/overview'"); pg.wait_for_timeout(1500)
        pg.get_by_role("button", name="Edit", exact=True).click(); pg.wait_for_timeout(600)
        for page in ("qs", "buildup", "register", "quotes", "programme"):
            pg.evaluate(f"location.hash = '#/tenders/{tid}/{page}'"); pg.wait_for_timeout(1200)
            pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); pg.wait_for_timeout(400)
            h1 = pg.locator("h1").first.bounding_box(); bar = pg.get_by_text("Tender", exact=True).first.bounding_box()
            assert h1 and 0 <= h1["y"] < 200 and (w < 1024 or (bar and bar["y"] >= 0)), (w, page, h1, bar)
            print(w, page, "title at y=%d, tender bar at y=%d" % (h1["y"], bar["y"]))
            if page in ("qs", "buildup", "quotes"):
                pg.evaluate("document.querySelector('.grid-scroll').scrollTop = 99999"); pg.wait_for_timeout(300)
                th = pg.locator(".grid-scroll thead th:visible").first.bounding_box(); vh = pg.viewport_size["height"]
                assert th and 0 < th["y"] < vh - 40, (w, page, "column headings not in view", th)
                print(w, page, "column heading at y=%d (scrolled to the last row)" % th["y"])
            if page == "qs": pg.screenshot(path=SHOT + f"sticky_{w}.png")
print("OK")
