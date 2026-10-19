"""Step 02 production plan: import (stubbed), edit, save, window comparison, issues, go-ahead banner."""
import json, re
from playwright.sync_api import sync_playwright, expect

exec(open("web/e2e/steps_e2e.py").read().split("with sync_playwright()")[0].split("\n", 1)[1])   # STEPS/OVERVIEW/route stubs
T = lambda i, n, st, lo, hi, **k: {"id": f"P-{i:03d}", "ref": f"T{i}", "stage": st, "name": n, "owner": "Estimator", "low": lo, "high": hi, "driver": "Drive", "predecessor": "", "deliverable": "Output", "acceptance": k.get("acc", "Rick agrees"), "scope_refs": "", "actual": None, "done": False}
PLAN = {"tasks": [T(1, "Read documents", "Intake", 2, 3), T(2, "Earthworks takeoff", "Takeoff", 28, 40, acc="")], "window": {"low_hours": 30, "high_hours": 40, "benchmark_hours": 38}, "source": "Drive: plan.xlsx", "updated_at": "2026-10-20T01:00:00Z", "go_ahead": None}
STATE = {"p": {"tasks": [], "window": None, "source": "", "updated_at": "", "go_ahead": None, "summary": None}}

def summ(p):
    lo = sum(t["low"] or 0 for t in p["tasks"]); hi = sum(t["high"] or 0 for t in p["tasks"]); w = p["window"]
    pos = None if not w or w["low_hours"] is None else "below" if hi < w["low_hours"] else "above" if lo > w["high_hours"] else "within"
    return {"low": lo, "high": hi, "mid": (lo + hi) / 2, "actual_task_hours": 0, "tracked_hours": 1.5, "done": sum(1 for t in p["tasks"] if t["done"]), "count": len(p["tasks"]),
            "issues": ["1 task(s) have no acceptance test."] if any(not t["acceptance"] for t in p["tasks"]) else [],
            "stages": [{"stage": s, "tasks": 1, "done": 0, "low": 0, "high": 0, "actual": 0} for s in dict.fromkeys(t["stage"] for t in p["tasks"])],
            "reconciliation": {"low_hours": w["low_hours"], "high_hours": w["high_hours"], "position": pos, "benchmark": 38, "note": "The plan's range overlaps the Step 01 window."} if pos else None}

def route3(r):
    u = r.request.url.split("?")[0]
    if u.endswith("/production") or u.endswith("/production/import"):
        if u.endswith("/import"): STATE["p"] = {**PLAN, "summary": None}
        elif r.request.method == "PUT":
            d = json.loads(r.request.post_data); STATE["p"] = {**STATE["p"], "tasks": d["tasks"], "window": d["window"]}
        STATE["p"]["summary"] = summ(STATE["p"]) if STATE["p"]["tasks"] else None
        return r.fulfill(status=200, content_type="application/json", body=json.dumps(STATE["p"]))
    return route(r)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/api/steps/**", route3)
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.get_by_test_id("build-path").get_by_role("button", name="02 Production Programme").click()
    m = pg.locator("main")
    expect(m).to_contain_text("No production plan yet", timeout=10000); expect(m).to_contain_text("No go-ahead recorded yet")
    m.get_by_role("button", name="Import from Drive").click()
    expect(m).to_contain_text("30 to 43"); expect(m).to_contain_text("Within the window"); expect(m).to_contain_text("no acceptance test")
    pg.screenshot(path=SHOTS + "step02_1.png", full_page=True)
    # edit: fix the missing acceptance test and hours; the total updates before saving
    pg.get_by_label("Acceptance test").nth(1).fill("Rick approves quantities")
    pg.get_by_label("High hours").nth(0).fill("5")
    expect(m).to_contain_text("30 to 45")
    m.get_by_role("button", name="Save plan").click()
    expect(m.get_by_role("button", name="Saved")).to_be_visible(timeout=10000)
    assert "no acceptance test" not in m.inner_text()
    pg.get_by_label("Done: Read documents").check()
    m.get_by_role("button", name="Save plan").click()
    expect(m).to_contain_text("1 of 2")
    # below-window warning
    pg.get_by_label("Window low_hours").fill("60"); pg.get_by_label("Window high_hours").fill("70")
    m.get_by_role("button", name="Save plan").click()
    expect(m).to_contain_text("Below the window", timeout=10000)
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(400)
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "sideways scroll"
    assert not errs, errs
    print("step02 e2e ok")
