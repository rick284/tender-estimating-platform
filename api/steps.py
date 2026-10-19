"""Mason build path: read a job's step files from its Drive folder (pure parsing, no network).

The ChatGPT 'senior estimator' leaves, in the job folder (instructions/senior-estimator/17 and 18):
  00 Project Admin / JOB_RECORD.md                         the index of the job, with a Steps table
  00 Project Admin / Steps / Step 05 Take-off - Drainage /  STEP_05_BRIEF.md and STEP_05_REPORT.md
The app only READS these here. Status comes from the Job Record's Steps table (DRAFT / APPROVED-LOCKED / REOPENED); with no row,
it is worked out from which files exist."""
from __future__ import annotations
import re
from typing import Any

STEP_FOLDER = re.compile(r"^\s*step\s+(\d{1,3})([a-z]?)\s*[-–—:.]?\s*(.*)$", re.I)
STEP_FILE = re.compile(r"^STEP_(\d{1,3})([a-z]?)_(BRIEF|REPORT)\.md$", re.I)
STATUSES = ("DRAFT", "APPROVED-LOCKED", "REOPENED")

# Stage groups for the sidebar, in order; a step goes to the first group whose words appear in its name.
GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Scope and plan", ("scope of work", "effort", "intake", "proposal", "scope confirmation", "production programme", "go-ahead", "induction")),
    ("Documents", ("document", "register", "addend", "revision control")),
    ("Scope coverage", ("scope",)),
    ("Takeoff", ("take-off", "takeoff", "take off", "quantit")),
    ("Quotes and correspondence", ("quote", "rfq", "correspondence", "email", "supplier", "subcontract")),
    ("Build-up and workbook", ("build-up", "build up", "buildup", "workbook", "pricing", "rates", "estimate build")),
    ("Programme and weather", ("programme", "program", "weather")),
    ("Review and release", ("review", "verification", "release", "check")),
    ("Client pack", ("client pack", "issue pack", "client issue", "submission")),
]
OTHER = "Other"


def group_for(name: str) -> str:
    n = name.lower()
    for g, words in GROUPS:
        if any(w in n for w in words):
            return g
    return OTHER


def group_order() -> list[str]:
    return [g for g, _ in GROUPS] + [OTHER]


def parse_step_folder(name: str) -> dict[str, Any] | None:
    m = STEP_FOLDER.match(name or "")
    if not m:
        return None
    num, suffix, rest = m.group(1), m.group(2).lower(), m.group(3).strip()
    return {"number": int(num), "suffix": suffix, "key": f"{int(num):02d}{suffix}", "name": rest or f"Step {int(num):02d}"}


def parse_step_file(name: str) -> tuple[str, str] | None:
    m = STEP_FILE.match(name or "")
    return (f"{int(m.group(1)):02d}{m.group(2).lower()}", m.group(3).lower()) if m else None


def _cells(line: str) -> list[str]:
    """Table cells; a pipe written as \\| (chat titles contain ' | ') stays inside its cell."""
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def parse_job_record(text: str) -> dict[str, Any]:
    """Lenient: pulls out what it can find; the page also shows the whole text, so a miss is never a loss."""
    out: dict[str, Any] = {"fields": {}, "steps": []}
    pats = {"revision": r"Revision:\s*(Rev\s?\S+)", "release_status": r"Release status:\s*(READY|HOLD)", "lifecycle": r"Lifecycle:\s*([A-Z][A-Z /\-]+?)(?:\s{2,}|\n|$)",
            "price": r"Price excl\.? GST:\s*([^\n]+?)(?:\s{2,}|\n|$)", "stage": r"Stage reached:\s*([0-9A-Za-z\-]+)", "step_completed": r"Step just completed:\s*([^\s].*?)(?:\s{2,}|\n|$)",
            "mode": r"Mode:\s*(STEP|RUN-THROUGH)", "tender_closes": r"Tender closes:\s*([^\n]+?)(?:\s{2,}|\n|$)", "updated": r"Updated:\s*([0-9]{1,2}-[A-Za-z]{3}-[0-9]{4})"}
    for k, p in pats.items():
        m = re.search(p, text or "")
        if m and not set(re.sub(r"\(.*?\)", "", m.group(1)).strip()) <= set("$_ -"):
            out["fields"][k] = m.group(1).strip()
    lines = (text or "").splitlines()
    at = next((i for i, l in enumerate(lines) if re.match(r"^#+\s*Steps\b", l.strip(), re.I)), None)
    if at is not None:
        head = None
        for l in lines[at + 1:]:
            s = l.strip()
            if s.startswith("#"):
                break
            if not s.startswith("|"):
                continue
            cells = _cells(s)
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            if head is None:
                head = [c.lower() for c in cells]
                continue
            row = dict(zip(head, cells))
            get = lambda *keys: next((row[h] for h in head for k in keys if k in h and row.get(h)), "")
            step_cell = get("step")
            m = re.match(r"\s*(?:step\s*)?(\d{1,3})([a-z]?)", step_cell, re.I)
            if not m:
                continue
            raw = get("status").upper()
            status = next((s2 for s2 in STATUSES if s2 in raw.replace(" ", "-").replace("_", "-")), raw)
            out["steps"].append({"key": f"{int(m.group(1)):02d}{m.group(2).lower()}", "chat_title": get("chat title", "title"), "status": status,
                                 "workbook_revision": get("workbook", "revision")})
    return out


def build_steps(folders: list[dict[str, Any]], record: dict[str, Any]) -> list[dict[str, Any]]:
    """folders: [{folder_id, name, files:[{id,name}]}] for each folder under Steps. Returns the ordered step list."""
    rec = {s["key"]: s for s in record.get("steps", [])}
    out: dict[str, dict[str, Any]] = {}
    for f in folders:
        p = parse_step_folder(f["name"])
        if not p:
            continue
        brief = report = None
        for fl in f.get("files", []):
            sf = parse_step_file(fl["name"])
            if sf and sf[0] == p["key"]:
                (brief := fl) if sf[1] == "brief" else (report := fl)
        r = rec.get(p["key"], {})
        status = r.get("status") or ("REPORTED" if report else "READY" if brief else "NOT STARTED")
        out[p["key"]] = {**p, "folder_id": f["folder_id"], "folder_name": f["name"], "group": group_for(p["name"]), "status": status, "brief": brief, "report": report,
                         "chat_title": r.get("chat_title", ""), "workbook_revision": r.get("workbook_revision", ""), "in_record": p["key"] in rec}
    for k, r in rec.items():                       # in the Job Record but with no folder yet
        if k not in out:
            part = next((x for x in (r["chat_title"] or "").split("|") if re.match(r"\s*step\s*\d", x, re.I)), "")
            n = (parse_step_folder(part) or {}).get("name") or f"Step {k}"
            out[k] = {"number": int(re.match(r"\d+", k).group()), "suffix": k[2:], "key": k, "name": n, "folder_id": None, "folder_name": "", "group": group_for(n),
                      "status": r["status"] or "NOT STARTED", "brief": None, "report": None, "chat_title": r["chat_title"], "workbook_revision": r["workbook_revision"], "in_record": True}
    return sorted(out.values(), key=lambda s: (s["number"], s["suffix"]))
