import asyncio
import json
from types import SimpleNamespace

import pytest

import ai_client
import ai_draft
import config
import db as dbmod
from conftest import register
from factory import make_workbook

PAGE1 = "DRAWING SCHEDULE. Civil drawing 301 Rev C dated 09/09/2026. Bulk earthworks: fill 1,310m3 and cut 113m3 per site calculations."
PAGE2 = "NOTES. Retaining walls maximum height 1.5m (Civil DWG301). Geotechnical report to be provided by others."
PAGE3 = "ARCHITECTURAL. Keystone retaining shown to a maximum height of 1.8m on the landscape plan."


class FakeClient:
    """Stands in for anthropic.Anthropic: records the request and answers with canned JSON."""
    def __init__(self, items, stop_reason="end_turn", text=None):
        self.calls, self._items, self._stop, self._text = [], items, stop_reason, text
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        text = self._text if self._text is not None else json.dumps({"items": self._items, "coverage_notes": "Read two documents."})
        return SimpleNamespace(stop_reason=self._stop, content=[SimpleNamespace(type="text", text=text)])


def item(kind="rfi", title="Retaining height conflict", basis="quoted", ev=None, rag="RED"):
    return {"kind": kind, "title": title, "detail": "Civil and architectural drawings disagree.", "impact": "Allowance or exclusion needed until resolved.", "rag": rag, "basis": basis,
            "evidence": ev if ev is not None else [{"file_id": "F-civil", "page": 2, "quote": "Retaining walls maximum height 1.5m (Civil DWG301)"},
                                                   {"file_id": "F-arch", "page": 1, "quote": "Keystone retaining shown to a maximum height of 1.8m on the landscape plan"}]}


@pytest.fixture()
def ai(client, auth, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    tid = client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", make_workbook())}).json()["id"]

    async def seed():
        d = dbmod.get_db()
        t = await d.tenders.find_one({"_id": tid})
        for fid, name, pages, status in (("F-civil", "Civil Drawings Rev C.pdf", [PAGE1, PAGE2], "ok"), ("F-arch", "Architectural Rev17.pdf", [PAGE3], "ok"), ("F-scan", "Scan.pdf", [""], "needs_ocr")):
            await d.doc_texts.insert_one({"_id": f"{tid}:{fid}", "org_id": t["org_id"], "tender_id": tid, "file_id": fid, "name": name, "revision": "C" if fid == "F-civil" else None,
                                          "status": status, "pages": [{"n": i + 1, "text": x} for i, x in enumerate(pages)], "page_count": len(pages), "chars": 1, "warnings": []})
    asyncio.run(seed())
    return tid


def on(client, auth):
    assert client.put("/api/ai/settings", headers=auth, json={"enabled": True, "acknowledged": True}).status_code == 200


def run(client, auth, tid, fake, files=("F-civil", "F-arch")):
    ai_client.CLIENT = fake
    try:
        return client.post(f"/api/ai/tenders/{tid}/draft", headers=auth, json={"file_ids": list(files)})
    finally:
        ai_client.CLIENT = None


def test_switched_off_until_the_owner_acknowledges(client, auth, ai):
    st = client.get("/api/ai/status", headers=auth).json()
    assert st["configured"] and not st["enabled"] and st["can_change"] and st["model"] == "claude-opus-5-5"
    assert run(client, auth, ai, FakeClient([])).status_code == 403                                             # off by default
    assert client.put("/api/ai/settings", headers=auth, json={"enabled": True}).status_code == 422             # needs the acknowledgement
    assert client.put("/api/ai/settings", headers=auth, json={"enabled": True, "acknowledged": True}).status_code == 200
    assert client.get("/api/ai/status", headers=auth).json()["enabled"] is True
    assert client.put("/api/ai/settings", headers=auth, json={"enabled": False}).status_code == 200
    assert client.get("/api/ai/status", headers=auth).json()["enabled"] is False


def test_not_configured_without_a_key(client, auth, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    assert client.get("/api/ai/status", headers=auth).json()["configured"] is False
    assert client.put("/api/ai/settings", headers=auth, json={"enabled": True, "acknowledged": True}).status_code == 503


def test_only_the_owner_can_switch_it_on(client, auth, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")

    async def demote():
        await dbmod.get_db().users.update_many({}, {"$set": {"role": "member"}})
    asyncio.run(demote())
    assert client.put("/api/ai/settings", headers=auth, json={"enabled": True, "acknowledged": True}).status_code == 403
    assert client.get("/api/ai/status", headers=auth).json()["can_change"] is False


def test_draft_sends_only_the_chosen_text_with_the_rules_and_checks_every_quote(client, auth, ai):
    on(client, auth)
    fake = FakeClient([item(), item(kind="exclusion", title="Geotechnical report by others", ev=[{"file_id": "F-civil", "page": 2, "quote": "Geotechnical report to be provided by others"}], rag="AMBER"),
                       item(title="Invented quote", ev=[{"file_id": "F-civil", "page": 1, "quote": "All rock excavation is included in the lump sum price"}]),
                       item(title="Wrong page", ev=[{"file_id": "F-civil", "page": 2, "quote": "fill 1,310m3 and cut 113m3 per site calculations"}]),
                       item(title="Foreign file", ev=[{"file_id": "F-other", "page": 1, "quote": "Retaining walls maximum height 1.5m"}]),
                       item(title="No quote at all", basis="quoted", ev=[]),
                       item(title="Geotechnical report not supplied", basis="gap", ev=[], rag="AMBER")])
    r = run(client, auth, ai, fake)
    assert r.status_code == 200, r.text
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["output_config"]["format"]["type"] == "json_schema" and "Do not guess" in call["system"] and "Never GREEN" in call["system"]
    user = call["messages"][0]["content"]
    assert "Retaining walls maximum height 1.5m" in user and "file_id: F-civil" in user and "Scan.pdf" not in user and "TENDER CONTEXT" in user
    by = {p["title"]: p for p in r.json()["proposals"]}
    assert by["Retaining height conflict"]["status"] == "verified" and all(e["verified"] for e in by["Retaining height conflict"]["evidence"])
    assert by["Geotechnical report by others"]["status"] == "verified"
    for bad in ("Invented quote", "Wrong page", "Foreign file", "No quote at all"):
        assert by[bad]["status"] == "unverified" and by[bad]["problems"], bad
    assert by["Geotechnical report not supplied"]["status"] == "gap"
    assert r.json()["files_sent"] == ["Civil Drawings Rev C.pdf", "Architectural Rev17.pdf"] and r.json()["coverage_notes"]


def test_quote_check_tolerates_pdf_spacing_but_not_wrong_numbers(client, auth, ai):
    on(client, auth)
    ok = item(title="Spacing", ev=[{"file_id": "F-civil", "page": 1, "quote": "fill  1,310m3\nand cut 113m3 per site\ncalculations"}])
    bad = item(title="Wrong number", ev=[{"file_id": "F-civil", "page": 1, "quote": "fill 1,410m3 and cut 113m3 per site calculations"}])
    by = {p["title"]: p for p in run(client, auth, ai, FakeClient([ok, bad])).json()["proposals"]}
    assert by["Spacing"]["status"] == "verified" and by["Wrong number"]["status"] == "unverified"


def test_accept_returns_a_register_edit_that_applies_and_keeps_the_quotes(client, auth, ai):
    on(client, auth)
    r = run(client, auth, ai, FakeClient([item()]))
    pid = r.json()["proposals"][0]["id"]
    a = client.post(f"/api/ai/proposals/{pid}/decision", headers=auth, json={"decision": "accepted"})
    assert a.status_code == 200
    edit = a.json()["edit"]
    assert edit["target"] == "register" and edit["op"] == "add" and edit["value"]["kind"] == "rfi" and edit["value"]["rag"] == "RED" and edit["value"]["status"] == "OPEN"
    assert "Civil Drawings Rev C.pdf p.2" in edit["value"]["detail"] and "1.8m on the landscape plan" in edit["value"]["detail"] and edit["value"]["action"].startswith("Allowance")
    assert client.post(f"/api/ai/proposals/{pid}/decision", headers=auth, json={"decision": "accepted"}).json()["edit"]["key"] == edit["key"]      # idempotent
    # the edit goes through the normal estimating path: nothing is in the estimate until the estimator saves a revision
    pv = client.post(f"/api/tenders/{ai}/revisions/1/preview", headers=auth, json={"edits": [edit]})
    assert pv.status_code == 200 and any(x["title"] == "Retaining height conflict" for x in pv.json()["estimate"]["register"])
    before = client.get(f"/api/tenders/{ai}/revisions/1", headers=auth).json()["estimate"]["register"]
    assert not any(x["title"] == "Retaining height conflict" for x in before)
    assert client.post(f"/api/ai/proposals/{pid}/decision", headers=auth, json={"decision": "rejected", "reason": "changed my mind"}).status_code == 409


def test_unverified_and_duplicate_cannot_be_accepted_and_rejection_needs_a_reason(client, auth, ai):
    on(client, auth)
    existing = client.get(f"/api/tenders/{ai}/revisions/1", headers=auth).json()["estimate"]["register"]
    dup_title = next(x["title"] for x in existing if x["kind"] == "rfi") if any(x["kind"] == "rfi" for x in existing) else None
    items = [item(title="Invented", ev=[{"file_id": "F-civil", "page": 1, "quote": "A sentence that is not in the document at all"}])]
    if dup_title:
        items.append(item(title=dup_title, ev=[{"file_id": "F-civil", "page": 2, "quote": "Retaining walls maximum height 1.5m (Civil DWG301)"}]))
    props = run(client, auth, ai, FakeClient(items)).json()["proposals"]
    assert client.post(f"/api/ai/proposals/{props[0]['id']}/decision", headers=auth, json={"decision": "accepted"}).status_code == 409
    if dup_title:
        assert props[1]["status"] == "duplicate" and client.post(f"/api/ai/proposals/{props[1]['id']}/decision", headers=auth, json={"decision": "accepted"}).status_code == 409
    assert client.post(f"/api/ai/proposals/{props[0]['id']}/decision", headers=auth, json={"decision": "rejected", "reason": " "}).status_code == 422
    assert client.post(f"/api/ai/proposals/{props[0]['id']}/decision", headers=auth, json={"decision": "rejected", "reason": "Quote not in the document"}).json() == {"decision": "rejected"}
    listed = client.get(f"/api/ai/tenders/{ai}/proposals", headers=auth).json()["proposals"]
    assert next(p for p in listed if p["id"] == props[0]["id"])["decision"]["reason"] == "Quote not in the document"


def test_input_checks_and_failures_are_plain(client, auth, ai):
    on(client, auth)
    assert client.post(f"/api/ai/tenders/{ai}/draft", headers=auth, json={"file_ids": []}).status_code == 422
    assert run(client, auth, ai, FakeClient([]), files=("F-nope",)).status_code == 409                       # not read yet
    assert run(client, auth, ai, FakeClient([]), files=("F-scan",)).status_code == 409                       # no readable text
    r = run(client, auth, ai, FakeClient([], stop_reason="refusal")); assert r.status_code == 502 and "declined" in r.json()["detail"]
    r = run(client, auth, ai, FakeClient([], stop_reason="max_tokens")); assert r.status_code == 502 and "fewer documents" in r.json()["detail"]
    r = run(client, auth, ai, FakeClient([], text="not json")); assert r.status_code == 502 and "could not be read" in r.json()["detail"]
    r = run(client, auth, ai, FakeClient([], text="[]")); assert r.status_code == 502
    assert client.get(f"/api/ai/tenders/{ai}/proposals", headers=auth).json()["proposals"] == []              # nothing stored on failure


def test_size_limit_and_company_isolation(client, auth, ai, monkeypatch):
    on(client, auth)
    monkeypatch.setattr(config, "AI_MAX_INPUT_CHARS", 50)
    assert run(client, auth, ai, FakeClient([])).status_code == 413
    monkeypatch.setattr(config, "AI_MAX_INPUT_CHARS", 400000)
    pid = run(client, auth, ai, FakeClient([item()])).json()["proposals"][0]["id"]
    monkeypatch.setattr(config, "REGISTRATION_OPEN", True)
    other = {"Authorization": f"Bearer {register(client, 'b@example.com', 'Other Ltd').json()['token']}"}
    assert client.get(f"/api/ai/tenders/{ai}/proposals", headers=other).status_code == 404
    assert client.post(f"/api/ai/proposals/{pid}/decision", headers=other, json={"decision": "accepted"}).status_code == 404
    assert client.post(f"/api/ai/tenders/{ai}/draft", headers=other, json={"file_ids": ["F-civil"]}).status_code == 404


def test_the_real_client_path_handles_sdk_errors_without_a_network(monkeypatch):
    class Boom:
        def __init__(self, exc): self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._c)); self.messages = self.beta.messages; self.exc = exc
        def _c(self, **kw): raise self.exc
    for name, text in (("AuthenticationError", "did not accept"), ("RateLimitError", "out of credit"), ("APITimeoutError", "could not be reached"), ("Weird", "returned an error")):
        ai_client.CLIENT = Boom(type(name, (Exception,), {})("x"))
        with pytest.raises(ai_client.AIError, match=text):
            ai_client.draft_json("s", "u", ai_draft.SCHEMA)
    # a beta-field rejection is retried once on the plain endpoint
    calls = []
    class Twice:
        def __init__(self):
            def beta(**kw): calls.append("beta"); raise type("BadRequestError", (Exception,), {})("no fallbacks here")
            def plain(**kw): calls.append("plain"); return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text='{"items": [], "coverage_notes": ""}')])
            self.beta = SimpleNamespace(messages=SimpleNamespace(create=beta)); self.messages = SimpleNamespace(create=plain)
    ai_client.CLIENT = Twice()
    assert ai_client.draft_json("s", "u", ai_draft.SCHEMA)["items"] == [] and calls == ["beta", "plain"]
    ai_client.CLIENT = None
