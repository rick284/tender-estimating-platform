"""Pure analysis of a Drive folder listing: which file is the latest revision, and does the folder follow the
standard 01-07 issued-pack structure. No network, no database."""
from __future__ import annotations
import re
from typing import Any

STANDARD_FOLDERS = [
    ("01", "Client Issue Pack"), ("02", "Tender Source Documents"), ("03", "Supplier and Subcontractor Quotes"),
    ("04", "RFIs Correspondence and Clarifications"), ("05", "Takeoffs Markups and Programme"),
    ("06", "Estimating Working Files"), ("07", "Superseded and Archive"),
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
    for f in files:
        f = dict(f)
        f["revision"] = None; f["latest"] = None; f["superseded_by"] = None; f["in_archive"] = _in_archive(f.get("path", ""))
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


def _in_archive(path: str) -> bool:
    return any(p.lower().startswith("07") for p in path.split("/")[:1])


def check_structure(top_folder_names: list[str]) -> list[dict[str, Any]]:
    """For each standard folder: found (with the actual name) or missing."""
    res = []
    for num, label in STANDARD_FOLDERS:
        hit = next((n for n in top_folder_names if re.match(rf"^\s*{num}\b", n)), None)
        res.append({"number": num, "label": label, "found": hit is not None, "actual": hit,
                    "exact": bool(hit) and _base(hit) == _base(f"{num} {label}")})
    return res
