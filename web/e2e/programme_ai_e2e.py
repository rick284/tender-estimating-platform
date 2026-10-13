"""AI programme logic: propose (AI stubbed in the browser), choose, apply to the programme draft, nothing kept until Save; rejections need a reason."""
import json, re, urllib.request
from playwright.sync_api import sync_playwright, expect

SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/audit/"

def api(m, p, b=None, t=None):
    h = {"Content-Type": "application/json"}
    if t: h["Authorization"] = "Bearer " + t
    return json.load(urllib.request.urlopen(urllib.request.Request("http://localhost:8000" + p, data=json.dumps(b).encode() if b else None, method=m, headers=h)))

tok = api("POST", "/api/auth/login", {"email": "rick@3bearsprojects.co.nz", "password": "a long test password"})["token"]
tid = next(t["id"] for t in api("GET", "/api/tenders", t=tok)["tenders"] if "Hobsonville" in t["name"])
api("PUT", "/api/ai/settings", {"api_key": "sk-ant-test1234abcdefgh", "enabled": True, "acknowledged": True}, tok)
prog = api("POST", f"/api/tenders/{tid}/programmes/from-estimate", {"revision": 1}, tok)
tasks = prog["tasks"]
leaf = [t for i, t in enumerate(tasks) if not (i + 1 < len(tasks) and tasks[i + 1]["outline_level"] > t["outline_level"])]
a, b, c = leaf[0], leaf[3], leaf[5]
state = {"proposals": [], "decided": []}

def prop(i, kind, pu, su, typ, lag, reason, status="ok", problems=None, conf="high"):
    n = {t["uid"]: t["name"] for t in tasks}
    return {"id": f"P{i}", "kind": kind, "pred_uid": pu, "succ_uid": su, "pred_name": n[pu], "succ_name": n[su], "type": typ, "lag_days": lag, "reason": reason, "basis": "construction_logic",
            "confidence": conf, "register_ref": "", "status": status, "problems": problems or [], "decision": None, "created_at": "now"}
PROPOSALS = [prop(1, "link", a["uid"], b["uid"], "SS", 2, "Work can start two days after the first task starts."), prop(2, "link", b["uid"], c["uid"], "FS", 0, "Normal sequence."),
             prop(3, "link", c["uid"], a["uid"], "FS", 0, "Loops back.", "invalid", ["This would make the programme loop back on itself."])]

def handle(route):
    req = route.request; url = req.url
    if url.endswith("/ai/propose"):
        state["proposals"] = PROPOSALS
        return route.fulfill(json={"proposals": PROPOSALS, "questions": [{"question": "Is a cure time needed before pavements?", "why": "Affects the pavement start."}], "coverage_notes": "Looked at all rows."})
    if url.endswith("/ai/proposals"):
        return route.fulfill(json={"proposals": [], "questions": [], "coverage_notes": ""})
    if url.endswith("/ai/decision"):
        body = json.loads(req.post_data); state["decided"].append(body)
        acc = [p for p in PROPOSALS if p["id"] in body.get("accept", [])]
        return route.fulfill(json={"accepted": acc, "rejected": len(body.get("reject", []))})
    route.continue_()

with sync_playwright() as p:
    b_ = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b_.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r".*/programmes/[^/]+/ai/.*"), handle)
    pg.goto("http://localhost:5173/"); pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click(); pg.wait_for_timeout(1200)
    pg.evaluate(f"location.hash = '#/tenders/{tid}/gantt/{prog['id']}'"); pg.wait_for_timeout(2500)
    pg.get_by_test_id("open-ai-logic").click(); pg.wait_for_timeout(800)
    expect(pg.get_by_test_id("ai-logic-dialog")).to_be_visible()
    pg.get_by_test_id("ai-propose").click(); pg.wait_for_timeout(1500)
    expect(pg.get_by_test_id("ai-proposal")).to_have_count(3)
    expect(pg.get_by_text("Is a cure time needed before pavements?")).to_be_visible()
    expect(pg.get_by_text("Can't be used")).to_be_visible()
    assert pg.locator("[data-testid=ai-logic-dialog] input[type=checkbox]").nth(2).is_disabled()                                  # the failed one cannot be selected
    pg.screenshot(path=SHOT + "ai_logic.png")
    expect(pg.get_by_test_id("ai-apply")).to_contain_text("Apply 2 selected")
    # reject needs a reason: untick one, add reason
    pg.locator("[data-testid=ai-logic-dialog] input[type=checkbox]").nth(1).uncheck()
    expect(pg.get_by_test_id("ai-reject")).to_be_disabled()
    pg.get_by_label("Reason for rejecting").fill("Not needed here"); expect(pg.get_by_test_id("ai-reject")).to_be_enabled()
    pg.locator("[data-testid=ai-logic-dialog] input[type=checkbox]").nth(1).check(); pg.locator("[data-testid=ai-logic-dialog] input[type=checkbox]").nth(0).uncheck()
    pg.get_by_test_id("ai-reject").click(); pg.wait_for_timeout(800)
    assert state["decided"][-1]["reject"][0] == {"id": "P2", "reason": "Not needed here"}
    expect(pg.get_by_test_id("ai-proposal")).to_have_count(2)
    # apply the remaining valid one
    pg.locator("[data-testid=ai-logic-dialog] input[type=checkbox]").nth(0).check()
    pg.get_by_test_id("ai-apply").click(); pg.wait_for_timeout(1500)
    assert state["decided"][-1]["accept"] == ["P1"]
    expect(pg.get_by_text("Unsaved changes")).to_be_visible()
    # the successor now shows the predecessor in the table (SS+2)
    row = pg.locator(f'[data-name-uid="{b["uid"]}"]').first
    assert row.count() == 1
    pg.screenshot(path=SHOT + "ai_logic_applied.png")
    assert not errs, errs
print("OK")
