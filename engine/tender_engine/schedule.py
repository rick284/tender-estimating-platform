"""Client price schedule: the tender priced in the client's own format (e.g. a main contractor's trade-line schedule).

Every dollar of the known package is a SOURCE: a QS item (own works), a pre-margin allowance line CA01-CA16 (own works), or a
subcontract overlay. Each source is mapped to schedule lines, so nothing can be counted twice or left out.

  schedule = {"name", "client", "groups": [{"id", "name", "code", "lines": [{"ref", "trade", "kind"}]}], "map": {source_key: target}}
  line kinds   work    priced from mapped sources, included in the group sub-total
               pg      preliminaries / common costs, priced from mapped sources, shown after the sub-total
               margin  computed: the group's sell price minus its other lines (carries overhead, profit and any hidden allocations)
  source keys  "qs:<code>"  "ca:<ref>"  "overlay:<name>"
  target       "line:<ref>"            put it on that line
               "group:<id>"            hold it inside that group's Margin line (a cost the client's schedule has no line for)
               "spread"                share it across the groups in proportion to their own-works lines, inside the Margin lines
               or a list of parts [{"to": <target>, "amount": "123.45"}, ...]; at most one part may omit the amount (takes the rest)

Group sell price = group cost x (1 + overhead) / (1 - margin): the same true-margin pricing as the consolidated package, so the
groups add up to the all-in tender exactly; `difference` reports anything that does not.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any, Optional, Sequence

from .money import D, ZERO, ONE, cents

KINDS = ("work", "pg", "margin")


class ScheduleError(ValueError):
    pass


def validate_schedule(s: dict[str, Any]) -> None:
    if not isinstance(s, dict) or not isinstance(s.get("groups"), list) or not s["groups"]:
        raise ScheduleError("A price schedule needs at least one group of lines.")
    refs, ids = set(), set()
    for g in s["groups"]:
        gid = str(g.get("id", ""))
        if not gid or gid in ids:
            raise ScheduleError("Each schedule group needs its own identity.")
        ids.add(gid)
        margins = [ln for ln in g.get("lines", []) if ln.get("kind") == "margin"]
        if len(margins) != 1:
            raise ScheduleError(f"Group {g.get('name', gid)!r} needs exactly one Margin line (it carries overhead and profit).")
        for ln in g["lines"]:
            if ln.get("kind") not in KINDS:
                raise ScheduleError(f"Line {ln.get('ref')!r} has an unknown kind.")
            if not str(ln.get("ref", "")).strip() or ln["ref"] in refs:
                raise ScheduleError(f"Line reference {ln.get('ref')!r} is blank or used twice.")
            refs.add(ln["ref"])
    if not isinstance(s.get("map", {}), dict):
        raise ScheduleError("The schedule mapping must be a dictionary.")


def default_schedule(sections: Sequence[str], overlay_names: Sequence[str]) -> dict[str, Any]:
    """Used when a tender has no client format: one line per QS section, one per subcontract package, one for allowances."""
    lines = [{"ref": f"{i + 1:02d}", "trade": sec, "kind": "work"} for i, sec in enumerate(sections)]
    n = len(lines)
    lines += [{"ref": f"{n + i + 1:02d}", "trade": name, "kind": "work"} for i, name in enumerate(overlay_names)]
    n = len(lines)
    lines += [{"ref": f"{n + 1:02d}", "trade": "Allowances and provisions (weather, risk, reserve)", "kind": "pg"},
              {"ref": f"{n + 2:02d}", "trade": "Overhead and margin", "kind": "margin"}]
    mp: dict[str, Any] = {}
    return {"name": "Price schedule", "client": "", "auto": True, "groups": [{"id": "works", "name": "WORKS", "code": "", "lines": lines}],
            "map": mp}


def auto_map(schedule: dict[str, Any], qs: Sequence[dict], overlays: Sequence[dict], sources_ca: Sequence[str]) -> dict[str, Any]:
    """Mapping for default_schedule(): QS items by section, overlays one each, allowances on the allowance line."""
    lines = schedule["groups"][0]["lines"]
    work = [ln for ln in lines if ln["kind"] == "work"]
    sec_line = {ln["trade"]: ln["ref"] for ln in work}
    pg = next(ln["ref"] for ln in lines if ln["kind"] == "pg")
    mp: dict[str, Any] = {}
    for q in qs:
        mp[f"qs:{q['code']}"] = f"line:{sec_line[q['section']]}"
    for o in overlays:
        mp[f"overlay:{o['name']}"] = f"line:{sec_line[o['name']]}"
    for ref in sources_ca:
        mp[f"ca:{ref}"] = f"line:{pg}"
    return mp


def _parts(value: Any, amount: Decimal, key: str) -> list[tuple[str, Decimal]]:
    if isinstance(value, str):
        return [(value, amount)]
    if not isinstance(value, list) or not value:
        raise ScheduleError(f"{key}: the mapping isn't valid.")
    fixed = [(p["to"], D(p["amount"])) for p in value if p.get("amount") not in (None, "")]
    rest = [p["to"] for p in value if p.get("amount") in (None, "")]
    if len(rest) > 1:
        raise ScheduleError(f"{key}: only one part of a split can take the remainder.")
    used = sum((a for _, a in fixed), ZERO)
    if any(a < 0 for _, a in fixed):
        raise ScheduleError(f"{key}: a split amount can't be negative.")
    if used > amount + Decimal("0.005"):
        raise ScheduleError(f"{key}: the split amounts add up to more than the item's value.")
    out = list(fixed)
    if rest:
        out.append((rest[0], amount - used))
    elif amount - used > Decimal("0.005"):
        out.append(("", amount - used))                    # unallocated remainder
    return out


def compute_schedule(schedule: dict[str, Any], sources: Sequence[dict[str, Any]], overhead_rate: Decimal | None, margin: Decimal | None,
                     all_in: Decimal, line: tuple[Decimal, Decimal] | None = None) -> dict[str, Any]:
    """sources: [{"key", "label", "amount" (Decimal), "own": bool}]. Returns the priced schedule and its reconciliation."""
    validate_schedule(schedule)
    groups = {g["id"]: g for g in schedule["groups"]}
    line_group = {ln["ref"]: g["id"] for g in schedule["groups"] for ln in g["lines"]}
    line_kind = {ln["ref"]: ln["kind"] for g in schedule["groups"] for ln in g["lines"]}
    amt = {ln["ref"]: ZERO for g in schedule["groups"] for ln in g["lines"] if ln["kind"] != "margin"}
    src_on_line: dict[str, list[dict[str, Any]]] = {r: [] for r in amt}
    own_weight = {gid: ZERO for gid in groups}
    hidden = {gid: ZERO for gid in groups}
    spread_total = ZERO
    unmapped: list[dict[str, Any]] = []
    problems: list[str] = []
    mp = schedule.get("map", {})

    for s in sources:
        amount, key = D(s["amount"]), s["key"]
        if amount == 0:
            continue
        if key not in mp:
            unmapped.append({"key": key, "label": s["label"], "amount": amount})
            continue
        try:
            parts = _parts(mp[key], amount, key)
        except ScheduleError as e:
            problems.append(str(e)); unmapped.append({"key": key, "label": s["label"], "amount": amount}); continue
        for target, a in parts:
            if a == 0:
                continue
            if target.startswith("line:") and target[5:] in amt:
                ref = target[5:]
                amt[ref] += a
                src_on_line[ref].append({"key": key, "label": s["label"], "amount": a})
                if s["own"]:
                    own_weight[line_group[ref]] += a
            elif target.startswith("group:") and target[6:] in groups:
                hidden[target[6:]] += a
            elif target == "spread":
                spread_total += a
            else:
                problems.append(f"{key}: target {target!r} doesn't exist in this schedule.")
                unmapped.append({"key": key, "label": s["label"], "amount": a})

    weight_sum = sum(own_weight.values(), ZERO)
    if spread_total != 0:
        if weight_sum == 0:
            problems.append("There is a cost to spread across the groups but no own-works lines to spread it by.")
            unmapped.append({"key": "spread", "label": "Spread allocation", "amount": spread_total})
        else:
            for gid in groups:
                hidden[gid] += spread_total * own_weight[gid] / weight_sum

    # group sell = a x group cost + b x (group cost / package cost): `line` = (a, b) from commercial.package_sell_line, so fixed
    # overhead / profit / bond amounts are shared by cost and the groups add up to the package. Rates only: the older form.
    a, b = line if line is not None else ((ONE + D(overhead_rate)) / (ONE - D(margin)), ZERO)
    package_cost = sum((sum((amt[ln["ref"]] for ln in g["lines"] if ln["kind"] != "margin"), ZERO) + hidden[g["id"]] for g in schedule["groups"]), ZERO)
    out_groups = []
    total_sell = ZERO
    for g in schedule["groups"]:
        gid = g["id"]
        line_total = sum((amt[ln["ref"]] for ln in g["lines"] if ln["kind"] != "margin"), ZERO)
        cost = line_total + hidden[gid]
        sell = cost * a + (b * cost / package_cost if package_cost != 0 else ZERO)
        lines, shown = [], ZERO
        for ln in g["lines"]:
            if ln["kind"] == "margin":
                continue
            r = cents(amt[ln["ref"]])
            shown += r
            lines.append({"ref": ln["ref"], "trade": ln["trade"], "kind": ln["kind"], "amount": r, "sources": src_on_line[ln["ref"]]})
        total = cents(sell)
        margin_amt = total - shown
        # the Margin line keeps its place in the group's order
        full = []
        it = iter(lines)
        for ln in g["lines"]:
            full.append({"ref": ln["ref"], "trade": ln["trade"], "kind": "margin", "amount": margin_amt, "sources": [],
                         "hidden": cents(hidden[gid])} if ln["kind"] == "margin" else next(it))
        subtotal = sum((x["amount"] for x in full if x["kind"] == "work"), ZERO)
        out_groups.append({"id": gid, "name": g["name"], "code": g.get("code", ""), "lines": full, "subtotal": subtotal,
                           "cost": cents(cost), "hidden": cents(hidden[gid]), "total": total})
        total_sell += total
    # Each group is rounded to the cent on its own, so several groups can miss the package by a cent or two. When everything is mapped,
    # put that rounding on the largest group (its Margin line) so the printed groups always add up to the all-in exactly.
    gap = cents(all_in) - sum((g["total"] for g in out_groups), ZERO)
    if gap != 0 and not unmapped and not problems and abs(gap) <= Decimal("0.01") * len(out_groups) and out_groups:
        big = max(out_groups, key=lambda g: g["total"])
        big["total"] += gap
        for ln in big["lines"]:
            if ln["kind"] == "margin":
                ln["amount"] += gap
        total_sell += gap
    mapped_total = sum((D(s["amount"]) for s in sources), ZERO) - sum((u["amount"] for u in unmapped), ZERO)
    gross = sum((D(s["amount"]) for s in sources), ZERO)
    diff = cents(total_sell) - cents(all_in)
    ok = not unmapped and not problems and abs(diff) < Decimal("0.005")
    if abs(diff) >= Decimal("0.005") and not unmapped and not problems:
        problems.append(f"The schedule totals {cents(total_sell):,.2f} but the tender is {cents(all_in):,.2f}.")
    return {"name": schedule.get("name", ""), "client": schedule.get("client", ""), "groups": out_groups, "total": cents(total_sell),
            "all_in": cents(all_in), "difference": diff, "unmapped": unmapped, "problems": problems, "reconciles": ok,
            "gross_package": cents(gross), "mapped": cents(mapped_total)}


def parse_format(text: str, name: str = "", client: str = "") -> dict[str, Any]:
    """Build a schedule format from pasted text, e.g. copied from the client's Excel price schedule.

        # MAIN BUILDING | A          <- a group heading ('#' or '##'), optional short code after '|'
        MB/001   Excavation          <- ref, then trade (tab, two spaces or a single space between)
        MB/025   Preliminaries & General   [pg]
        MB/026   Margin              [margin]

    A group with no [margin] line gets one added at the end. Lines starting with '-' or blank lines are ignored.
    """
    import re
    groups: list[dict[str, Any]] = []
    cur: Optional[dict[str, Any]] = None
    refs: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip().strip("﻿")
        if not line or line.startswith("-"):
            continue
        if line.startswith("#"):
            head = line.lstrip("#").strip()
            title, _, code = head.partition("|")
            cur = {"id": f"g{len(groups) + 1}", "name": title.strip().upper(), "code": code.strip(), "lines": []}
            if not cur["name"]:
                raise ScheduleError("A group heading needs a name.")
            groups.append(cur)
            continue
        if cur is None:
            raise ScheduleError("Start with a group heading, for example '# CIVIL WORKS'.")
        kind = "work"
        m = re.search(r"\[(pg|margin|work)\]\s*$", line, re.I)
        if m:
            kind = m.group(1).lower()
            line = line[:m.start()].strip()
        parts = re.split(r"\t+|\s{2,}", line, maxsplit=1)
        if len(parts) < 2:
            parts = line.split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            raise ScheduleError(f"Line {line!r} needs a reference and a trade name.")
        ref, trade = parts[0].strip(), parts[1].strip()
        if ref in refs:
            raise ScheduleError(f"Reference {ref!r} appears twice.")
        refs.add(ref)
        cur["lines"].append({"ref": ref, "trade": trade, "kind": kind})
    if not groups:
        raise ScheduleError("Paste the client's schedule lines first.")
    for g in groups:
        if not g["lines"]:
            raise ScheduleError(f"Group {g['name']!r} has no lines.")
        margins = [ln for ln in g["lines"] if ln["kind"] == "margin"]
        if len(margins) > 1:
            raise ScheduleError(f"Group {g['name']!r} has more than one Margin line.")
        if not margins:
            ref = f"{g['code'] or g['id']}/M"
            while ref in refs:
                ref += "x"
            refs.add(ref)
            g["lines"].append({"ref": ref, "trade": "Margin", "kind": "margin"})
    s = {"name": name.strip(), "client": client.strip(), "groups": groups, "map": {}}
    validate_schedule(s)
    return s


def valid_target(s: dict[str, Any], target: str) -> bool:
    refs = {ln["ref"] for g in s["groups"] for ln in g["lines"] if ln["kind"] != "margin"}
    ids = {g["id"] for g in s["groups"]}
    return target == "spread" or (target.startswith("line:") and target[5:] in refs) or (target.startswith("group:") and target[6:] in ids)
