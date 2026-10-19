"""Email threads kept in the job's Drive folder as text (Mason saves them; the app only reads them).

One file per thread, normally in `04.1 Emails In` (received) or `04.2 Emails Out - DRAFT ONLY` (drafts, never sent from here). A file may hold several messages
separated by a `=== ... ===` line. Headers are read tolerantly: `Source: <person>, <date>, subject: <subject>` (the layout Mason used in the first test),
or `From:` / `Date:` / `Subject:` lines. References (RFI-06, Q-03, SC-012, DOC-004) are picked out of the text so a thread can be linked to the register,
quotes and scope. Nothing here sends, edits or deletes anything.
"""
from __future__ import annotations
import re
from typing import Any

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
REF_RX = re.compile(r"\b(RFI-\d+[A-Z]?|Q-\d+|SC-\d+|DOC-\d+|RT\d+(?:-\d+)?|MR-\d+)\b")
NAME_RX = re.compile(r"^(\d{4}-\d{2}-\d{2})[_ -]+(In|Out|Draft)[_ -]+(.+)$", re.I)
SEP_RX = re.compile(r"^\s*={3,}.*={3,}\s*$")
SOURCE_RX = re.compile(r"^\s*(?:source|from)\s*:\s*(.+?)(?:,\s*(\d{1,2}-[A-Za-z]{3}-\d{4}|\d{4}-\d{2}-\d{2}))?(?:,\s*subject\s*:\s*(.+))?\s*$", re.I)
GMAIL_RX = re.compile(r"(?:original\s+)?gmail\s+(?:message\s+)?id\s*:\s*([A-Za-z0-9]+)", re.I)
URL_RX = re.compile(r"https?://\S+")


def iso(d: str) -> str:
    """'4-Sep-2026' or '2026-09-04' -> '2026-09-04' (blank when not a date)."""
    d = (d or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        return d
    m = re.fullmatch(r"(\d{1,2})-([A-Za-z]{3})[a-z]*-(\d{4})", d)
    if m and m.group(2).lower() in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return ""


def classify(path: str, name: str) -> str | None:
    """'in', 'out' (a draft: nothing here is sent) or None when the file is not an email thread."""
    p = f"{path}/{name}".lower()
    m = NAME_RX.match(name)
    if "emails out" in p or "04.2" in p or (m and m.group(2).lower() in ("out", "draft")):
        return "out"
    if "emails in" in p or "04.1" in p or (m and m.group(2).lower() == "in"):
        return "in"
    return None


def _clean_title(name: str) -> str:
    n = re.sub(r"\.(txt|md|eml|docx?)$", "", name, flags=re.I)
    n = re.sub(r"\s*[-_ ]\s*TEST\s*$", "", n)
    m = NAME_RX.match(n)
    return (m.group(3) if m else n).replace("_", " ").strip()


def parse_thread(name: str, text: str) -> dict[str, Any]:
    segs, cur = [], []
    for line in text.splitlines():
        if SEP_RX.match(line):
            segs.append(cur); cur = []
        else:
            cur.append(line)
    segs.append(cur)
    messages = []
    for seg in segs:
        body = [x for x in seg]
        frm = date = subj = gid = ""
        used = set()
        for i, line in enumerate(body[:14]):
            ln = line.strip().lstrip("#").strip()
            g = GMAIL_RX.search(ln)
            if g and not gid:
                gid = g.group(1); used.add(i); continue
            s = SOURCE_RX.match(ln)
            if s and not frm:
                frm = s.group(1).strip(" ,"); date = iso(s.group(2) or ""); subj = (s.group(3) or "").strip(); used.add(i); continue
            kv = re.match(r"^(date|subject|to|cc)\s*:\s*(.+)$", ln, re.I)
            if kv:
                k = kv.group(1).lower()
                if k == "date" and not date: date = iso(kv.group(2)) or date
                if k == "subject" and not subj: subj = kv.group(2).strip()
                used.add(i)
        text_body = "\n".join(l for i, l in enumerate(body) if i not in used).strip()
        if not (frm or subj or gid or text_body):
            continue
        messages.append({"from": frm, "date": date, "subject": subj, "gmail_id": gid, "body": text_body})
    messages = [m for m in messages if m["body"] or m["from"]]
    m0 = NAME_RX.match(re.sub(r"\.(txt|md|eml|docx?)$", "", name, flags=re.I))
    date = (m0.group(1) if m0 else "") or next((m["date"] for m in messages if m["date"]), "")
    subject = next((m["subject"] for m in messages if m["subject"]), "") or _clean_title(name)
    party = next((m["from"] for m in messages if m["from"]), "")
    atts = []
    for line in text.splitlines():
        a = re.match(r"^\s*attachments?\s*(?:\(s\))?\s*:\s*(.+)$", line, re.I)
        if a:
            atts += [x.strip() for x in re.split(r";|\s\|\s", a.group(1)) if x.strip()]
    refs = sorted(set(REF_RX.findall(text)), key=lambda r: (re.sub(r"[\d-]+.*", "", r), r))
    return {"date": date, "subject": subject[:300], "party": party[:120], "messages": messages, "count": max(len(messages), 1), "refs": refs,
            "attachments": atts[:30], "links": sorted(set(URL_RX.findall(text)))[:20], "gmail_ids": [m["gmail_id"] for m in messages if m["gmail_id"]]}


def snippet(text: str, q: str, width: int = 90) -> str:
    i = text.lower().find(q.lower())
    if i < 0:
        return ""
    a = max(0, i - width // 2)
    return ("…" if a else "") + re.sub(r"\s+", " ", text[a:i + len(q) + width // 2]).strip() + "…"
