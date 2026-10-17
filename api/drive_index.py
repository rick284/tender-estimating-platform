"""Pure analysis of a Drive folder listing: which file is the latest revision, and does the folder follow the
standard 01-07 issued-pack structure. No network, no database."""
from __future__ import annotations
import re
from typing import Any

# The standard job folder layout (Rick, 18 Oct 2026): the 01-07 layout of the Hobsonville job plus 00 Project Admin.
# Every job lives in Blackline Estimating / <Client> / <Job name> / these folders.
JOB_FOLDERS = [
    ("00", "Project Admin"),
    ("01", "Client Issue Pack"), ("02", "Tender Source Documents"), ("03", "Supplier and Subcontractor Quotes"),
    ("04", "RFIs Correspondence and Clarifications"), ("05", "Takeoffs Markups and Programme"),
    ("06", "Estimating Working Files"), ("07", "Superseded and Archive"),
]
STANDARD_FOLDERS = JOB_FOLDERS
# The 12-folder layout proposed on 15 Oct 2026 (replaced on 18 Oct 2026). Folders already set up that way are still recognised.
LEGACY_12_FOLDERS = [
    ("01", "Project_Admin"), ("02", "Source_Documents"), ("03", "Correspondence"), ("04", "Takeoffs_and_Scope"),
    ("05", "Supplier_and_Subcontract_Pricing"), ("06", "Estimate_Workbooks"), ("07", "Programme_and_Methodology"),
    ("08", "Risk_Allowances_and_RFIs"), ("09", "QA_and_Review"), ("10", "Issued_and_Baselines"), ("11", "Time_and_Billing"),
    ("12", "Delivery_and_Actuals"),
]
FOLDER_MIME = "application/vnd.google-apps.folder"

_REV = re.compile(r"(?<![A-Za-z0-9])(?:rev(?:ision)?|issue|ver(?:sion)?|v|r)[ _.\-]?(\d{1,3}[A-Za-z]?|[A-Za-z])(?![A-Za-z0-9])", re.I)


def split_revision(name: str) -> tuple[str, str | None]:
    """'Hobsonville_Rev34E.xlsx' -> ('hobsonville', '34E'). Uses the FIRST revision token (the document's own revision; later
    ones such as '..._Rev28_PAVEMENT_Rev5.xlsx' are the workbook's internal version). The base name is the text BEFORE that token, so
    'Estimate_Rev24_ESC' and 'Estimate_Rev28_PAVEMENT' compare as the same document series."""
    stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", name)
    found = list(_REV.finditer(stem))
    if not found:
        return _base(stem), None
    m = found[0]
    return _base(stem[:m.start()]), m.group(1).upper()


def _base(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _rank(token: str) -> tuple[int, str]:
    m = re.match(r"(\d+)([A-Z]?)$", token)
    return (int(m.group(1)), m.group(2)) if m else (-1, token)


def analyse(files: list[dict[str, Any]]) -> dict[str, Any]:
    """files: [{id, name, path, mime, modified, size, link, is_folder}] -> same files plus revision / latest / superseded.
    A file is 'superseded' only when another file in the SAME folder has the same base name and a higher revision."""
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    out = []
    layout = detect_layout([f["name"] for f in files if f.get("is_folder") and not f.get("path")])
    for f in files:
        f = dict(f)
        f["revision"] = None; f["latest"] = None; f["superseded_by"] = None; f["in_archive"] = _in_archive(f.get("path", ""), layout)
        if not f.get("is_folder"):
            base, rev = split_revision(f["name"])
            f["revision"] = rev
            ext = f["name"].rsplit(".", 1)[-1].lower() if "." in f["name"] else ""
            if rev:
                groups.setdefault((f.get("folder", ""), base, ext), []).append(f)
        out.append(f)
    ambiguous = 0
    for members in groups.values():
        if len(members) < 2:
            members[0]["latest"] = True
            continue
        kinds = {_rank(m["revision"])[0] >= 0 for m in members}
        best = max(_rank(m["revision"]) for m in members)
        if len(kinds) > 1:
            ambiguous += 1
        for m in members:
            m["latest"] = _rank(m["revision"]) == best
            m["superseded_by"] = None if m["latest"] else next(x["name"] for x in members if _rank(x["revision"]) == best)
            if len(kinds) > 1:
                m["ambiguous"] = True
    return {"files": out, "ambiguous_groups": ambiguous}


def _has_number(name: str, num: str) -> bool:
    return re.match(rf"^\s*{num}(?![0-9])", name) is not None


def detect_layout(top_folder_names: list[str]) -> str:
    """'12' when the folder uses the older 12-folder layout (a name matches one of its folders, or 08-12 style numbers), else '07'
    (the standard 00-07 layout, where 07 is the archive)."""
    for n in top_folder_names:
        for num, label in LEGACY_12_FOLDERS:
            if _base(n) == _base(f"{num} {label}"):
                return "12"
        if re.match(r"^\s*(08|09|1[0-2])[ _\-]", n):
            return "12"
    return "07"


def _in_archive(path: str, layout: str = "07") -> bool:
    top = path.split("/")[0].lower() if path else ""
    return (layout == "07" and top.startswith("07")) or "superseded" in top or "archive" in top


def check_structure(top_folder_names: list[str], layout: str | None = None) -> list[dict[str, Any]]:
    """For each standard folder: found (with the actual name) or missing."""
    layout = layout or detect_layout(top_folder_names)
    wanted = LEGACY_12_FOLDERS if layout == "12" else JOB_FOLDERS
    res = []
    for num, label in wanted:
        hit = next((n for n in top_folder_names if _has_number(n, num)), None)
        res.append({"number": num, "label": label.replace("_", " ") if layout == "12" else label, "found": hit is not None, "actual": hit,
                    "exact": bool(hit) and _base(hit) == _base(f"{num} {label}")})
    return res


def plan_folders(top_folder_names: list[str]) -> list[dict[str, Any]]:
    """What setting up the standard 00-07 layout would do inside a job folder. Never renames, moves or duplicates:
    a number already used by a differently-named folder (for example '01_Project_Admin' from the older 12-folder layout) is left alone
    and reported."""
    out = []
    for num, label in JOB_FOLDERS:
        name = f"{num} {label}"
        hit = next((n for n in top_folder_names if _has_number(n, num)), None)
        action = "create" if hit is None else "exists" if _base(hit) == _base(name) else "number_taken"
        out.append({"number": num, "name": name, "action": action, "actual": hit})
    return out
