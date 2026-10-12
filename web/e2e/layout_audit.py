"""Layout audit: visits every tender page, in view and edit mode, at several widths, and reports text that breaks mid-word, text crushed into narrow columns,
inputs/buttons that overflow their cell, and pages that need sideways scrolling.  Usage: layout_audit.py OUT.json [width,width,...] [pages,...]"""
import json, sys, urllib.request, uuid
from playwright.sync_api import sync_playwright, expect

OUT = sys.argv[1]
WIDTHS = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "1440,1100,820,390").split(",")]
ONLY = sys.argv[3].split(",") if len(sys.argv) > 3 else None
PAGES = ["overview", "consolidated", "tender", "qs", "buildup", "programme", "weather", "risk", "reserve", "register", "quotes", "drive", "ai", "takeoff", "outputs", "library", "revisions"]
if ONLY: PAGES = [p for p in PAGES if p in ONLY]
SHOT = "/tmp/claude-0/-home-user/d48f647b-2b13-5568-9c30-5dd27b3706a0/scratchpad/audit/"

JS = r"""
() => {
  const issues = [];
  const vis = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const label = (e) => (e.getAttribute('aria-label') || e.id || (e.className && typeof e.className === 'string' ? e.className.split(' ').filter(c => !c.startsWith('hover') ).slice(0, 3).join('.') : '') || e.tagName).slice(0, 60);
  if (document.documentElement.scrollWidth > window.innerWidth + 1) issues.push({k: 'page-sideways-scroll', d: `content ${document.documentElement.scrollWidth}px wider than window ${window.innerWidth}px`});
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n = 0;
  while (walker.nextNode() && n < 6000) {
    const t = walker.currentNode; const text = t.textContent;
    if (!text.trim() || text.length > 600) continue;
    const el = t.parentElement; if (!el || !vis(el) || el.closest('script,style,option,select,textarea')) continue;
    n++;
    const re = /\S+/g; let m;
    while ((m = re.exec(text))) {
      if (m[0].length < 4 || /[-\/\u2013]/.test(m[0])) continue;      // breaking at a hyphen or slash is normal
      const r = document.createRange(); r.setStart(t, m.index); r.setEnd(t, m.index + m[0].length);
      const rects = Array.from(r.getClientRects()).filter(x => x.width > 0);
      if (rects.length > 1 && Math.abs(rects[0].top - rects[rects.length - 1].top) > 6) { issues.push({k: 'word-broken', d: `"${m[0]}" in ${label(el)}`}); break; }
    }
    const r = document.createRange(); r.selectNodeContents(t); const rects = Array.from(r.getClientRects()).filter(x => x.width > 0);
    const lines = new Set(rects.map(x => Math.round(x.top / 4))).size;
    const w = el.getBoundingClientRect().width;
    if (lines >= 4 && w < 110 && text.trim().length > 10) issues.push({k: 'crushed-text', d: `${lines} lines in ${Math.round(w)}px: "${text.trim().slice(0, 40)}" (${label(el)})`});
  }
  document.querySelectorAll('input:not([type=checkbox]):not([type=radio]):not([type=file]), select, textarea').forEach((e) => {
    if (!vis(e)) return;
    const c = e.closest('td, th, label, dialog > div, .panel, section, div'); if (!c) return;
    const a = e.getBoundingClientRect(), b = c.getBoundingClientRect();
    const sc = e.closest('.overflow-x-auto, .overflow-auto, .grid-scroll'); 
    if (a.right > b.right + 1.5 && !(c.matches('div') )) issues.push({k: 'input-overflows-cell', d: `${label(e)} right ${Math.round(a.right)} > cell ${Math.round(b.right)}`});
    if (a.width < 28 && e.tagName !== 'INPUT') issues.push({k: 'control-too-narrow', d: `${label(e)} ${Math.round(a.width)}px`});
    if (e.tagName === 'INPUT' && a.width < 36 && e.type !== 'hidden') issues.push({k: 'control-too-narrow', d: `${label(e)} ${Math.round(a.width)}px`});
  });
  document.querySelectorAll('button, .btn, a.btn').forEach((e) => {
    if (!vis(e)) return; const a = e.getBoundingClientRect();
    if (a.width > window.innerWidth + 1 || a.right > window.innerWidth + 2 && !e.closest('.overflow-x-auto, .overflow-auto, .grid-scroll')) issues.push({k: 'button-off-screen', d: `${(e.textContent || '').trim().slice(0, 30)} right ${Math.round(a.right)} / ${window.innerWidth}`});
    const lines = (() => { const r = document.createRange(); r.selectNodeContents(e); return new Set(Array.from(r.getClientRects()).filter(x => x.width > 0).map(x => Math.round(x.top / 4))).size; })();
    if (lines > 2 && (e.textContent || '').trim().length < 24) issues.push({k: 'button-text-wraps', d: `"${(e.textContent || '').trim()}" ${lines} lines in ${Math.round(a.width)}px`});
  });
  return issues;
}
"""

def api(method, path, body=None, tok=None, files=None):
    url = "http://localhost:8000" + path; h = {}
    if tok: h["Authorization"] = f"Bearer {tok}"
    if files:
        bd = uuid.uuid4().hex; parts = []
        for k, (fn, data) in files.items(): parts.append(f'--{bd}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n")
        parts.append(f"--{bd}--\r\n".encode()); data = b"".join(parts); h["Content-Type"] = f"multipart/form-data; boundary={bd}"
    else: data = json.dumps(body).encode() if body is not None else None; h["Content-Type"] = "application/json"
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=h)))

tok = api("POST", "/api/auth/login", {"email": "rick@3bearsprojects.co.nz", "password": "a long test password"})["token"]
tenders = {t["name"]: t["id"] for t in api("GET", "/api/tenders", tok=tok)["tenders"]}
if not any("Bridle" in n.upper() or "BRIDLE" in n.upper() for n in tenders):
    api("POST", "/api/tenders", tok=tok, files={"file": ("Bridle.xlsx", open("/home/user/tender-estimating-platform/private/Bridle_Trail.xlsx", "rb").read())})
    tenders = {t["name"]: t["id"] for t in api("GET", "/api/tenders", tok=tok)["tenders"]}
jobs = [("Hobsonville", next(i for n, i in tenders.items() if "Hobsonville" in n))] + [("Bridle", next(i for n, i in tenders.items() if "ridle" in n))]

report = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    for width in WIDTHS:
        for jobname, tid in jobs:
            if jobname == "Bridle" and width not in (1440, 390): continue
            ctx = b.new_context(viewport={"width": width, "height": 900}); pg = ctx.new_page()
            errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto("http://localhost:5173/"); pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
            pg.get_by_role("button", name="Sign in").click()
            pg.wait_for_timeout(1200)
            for mode in ("view", "edit"):
                pg.evaluate(f"location.hash = '#/tenders/{tid}/overview'"); pg.wait_for_timeout(1500)
                if mode == "edit":
                    btn = pg.get_by_role("button", name="Edit", exact=True)
                    if not btn.is_enabled(): continue
                    btn.click(); pg.wait_for_timeout(800)
                for page in PAGES:
                    pg.evaluate(f"location.hash = '#/tenders/{tid}/{page}'"); pg.wait_for_timeout(1300)
                    issues = pg.evaluate(JS)
                    seen, uniq = set(), []
                    for i in issues:
                        key = (i["k"], i["d"])
                        if key not in seen: seen.add(key); uniq.append(i)
                    report.append({"width": width, "job": jobname, "mode": mode, "page": page, "issues": uniq[:25], "n": len(uniq), "errors": errs[:2]})
                    if width == 1440 or uniq:
                        pg.screenshot(path=SHOT + f"{jobname}_{width}_{mode}_{page}.png")
            ctx.close()
    b.close()
json.dump(report, open(OUT, "w"), indent=1)
bad = [r for r in report if r["n"]]
print(f"pages checked: {len(report)}; with issues: {len(bad)}")
