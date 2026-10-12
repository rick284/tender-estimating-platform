"""Score an AI takeoff against the quantities finally adopted in an estimate workbook (Hobsonville Rev34E).

Usage: python tools/score_takeoff.py WORKBOOK.xlsx PROPOSALS.json MATCHES.json [--out report.md]

PROPOSALS.json: {"items":[{id, description, unit, quantity (platform-computed if present as "computed"), status ...}]}
MATCHES.json:   {"matches":[{"qs":"PV01","proposals":["T03","T04"],"note":"..."}], "out_of_scope":{"EW02":"fill volume comes from the Yodha report, not from these drawings"}}
Matching is done by a person (or the estimator reviewing the AI) so that the table can be checked line by line; this script only does the arithmetic.
Bands: within 2% / within 10% / within 25% / outside. Only quantity lines (not lump sums / PC sums with an arbitrary quantity of 1) are scored.
"""
from __future__ import annotations
import json
import sys

sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from tender_engine.estimate import compute_estimate  # noqa: E402
from tender_engine.importers import load_master_workbook  # noqa: E402

BANDS = ((0.02, "within 2%"), (0.10, "within 10%"), (0.25, "within 25%"))


def band(err: float) -> str:
    for lim, name in BANDS:
        if abs(err) <= lim:
            return name
    return "outside 25%"


# "reference" matches score against a number the estimate states in its notes rather than on a quantity line: {"qs": "PV05", "truth": 21, "unit": "ea", "label": "...", "proposals": [...]}
def score(qs: list[dict], proposals: list[dict], matches: dict) -> dict:
    prop = {p["id"]: p for p in proposals}
    truth = {q["code"]: q for q in qs}
    scored, used = [], set()
    for m in matches.get("matches", []) + matches.get("reference", []):
        codes = m["qs"] if isinstance(m["qs"], list) else [m["qs"]]
        if "truth" in m:
            q = {"code": m["qs"], "description": m["label"], "unit": m["unit"], "quantity": m["truth"]}
        else:
          q = {"code": "+".join(codes), "description": " + ".join(truth[c]["description"][:30] for c in codes) if len(codes) > 1 else truth[codes[0]]["description"],
             "unit": truth[codes[0]]["unit"], "quantity": sum(float(truth[c]["quantity"]) for c in codes)}
        ps = [prop[i] for i in m["proposals"] if i in prop]
        used |= {p["id"] for p in ps}
        got = sum(float(p.get("computed") if p.get("computed") is not None else p.get("quantity") or 0) for p in ps) if m.get("combine", "sum") == "sum" else float(ps[0].get("computed") or ps[0].get("quantity") or 0)
        want = float(q["quantity"])
        err = (got - want) / want if want else None
        scored.append({"qs": q["code"], "description": q["description"], "unit": q["unit"], "truth": want, "got": got, "error": err, "band": band(err) if err is not None else "n/a",
                       "proposals": m["proposals"], "statuses": [p.get("status") for p in ps], "note": m.get("note", "")})
    out_scope = matches.get("out_of_scope", {})
    quantity_lines = [q for q in qs if q["unit"] != "LS" and float(q["quantity"] or 0) > 0]
    matched = {c for s in scored for c in s["qs"].split("+")}
    missed = [q for q in quantity_lines if q["code"] not in matched and q["code"] not in out_scope]
    extra = [p for p in proposals if p["id"] not in used]
    return {"scored": scored, "missed": missed, "extra": extra, "out_of_scope": {c: out_scope[c] for c in out_scope if c in truth}, "quantity_lines": len(quantity_lines)}


def render(r: dict) -> str:
    L = ["# Takeoff accuracy report", "", "| Estimate line | Unit | Rev34E quantity | AI quantity | Error | Band | Proposals (status) |", "|---|---|---:|---:|---:|---|---|"]
    for s in r["scored"]:
        e = "n/a" if s["error"] is None else f"{s['error'] * 100:+.1f}%"
        L.append(f"| {s['qs']} {s['description'][:48]} | {s['unit']} | {s['truth']:,.2f} | {s['got']:,.2f} | {e} | {s['band']} | {', '.join(f'{p} ({st})' for p, st in zip(s['proposals'], s['statuses']))} |")
    bands = {}
    for s in r["scored"]:
        bands[s["band"]] = bands.get(s["band"], 0) + 1
    L += ["", f"Scored lines: {len(r['scored'])} of {r['quantity_lines']} quantity lines in the estimate. " + ", ".join(f"{k}: {v}" for k, v in sorted(bands.items())), ""]
    if r["missed"]:
        L += ["## Quantity lines in the estimate the AI did not produce (and were not marked out of scope)", ""] + [f"- {q['code']} {q['description']} ({q['quantity']:,.2f} {q['unit']}) - {q['basis'][:90]}" for q in r["missed"]] + [""]
    if r["out_of_scope"]:
        L += ["## Out of scope for this drawing set", ""] + [f"- {c}: {why}" for c, why in r["out_of_scope"].items()] + [""]
    if r["extra"]:
        L += ["## AI lines with no matching estimate line (extra, to be reviewed)", ""] + [f"- {p['id']} {p['description']} - {p.get('computed', p.get('quantity'))} {p['unit']} ({p.get('status')})" for p in r["extra"]] + [""]
    return "\n".join(L)


if __name__ == "__main__":
    wb, pj, mj = sys.argv[1:4]
    est = compute_estimate(load_master_workbook(wb))
    props = json.load(open(pj))["items"]
    text = render(score(est["qs"], props, json.load(open(mj))))
    if "--out" in sys.argv:
        open(sys.argv[sys.argv.index("--out") + 1], "w").write(text)
    print(text)
