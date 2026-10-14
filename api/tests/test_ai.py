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
    tid = client.post("/api/tenders", headers=auth, files={"file": ("a.xlsx", make_workbook())}).json()["id"]

    async def seed():
        d = dbmod.get_db()
        t = await d.tenders.find_one({"_id": tid})
        for fid, name, pages, status in (("F-civil", "Civil Drawings Rev C.pdf", [PAGE1, PAGE2], "ok"), ("F-arch", "Architectural Rev17.pdf", [PAGE3], "ok"), ("F-scan", "Scan.pdf", [""], "needs_ocr")):
            await d.doc_texts.insert_one({"_id": f"{tid}:{fid}", "org_id": t["org_id"], "tender_id": tid, "file_id": fid, "name": name, "revision": "C" if fid == "F-civil" else None,
                                          "status": status, "pages": [{"n": i + 1, "text": x} for i, x in enumerate(pages)], "page_count": len(pages), "chars": 1, "warnings": []})
    asyncio.run(seed())
    return tid


KEY = "sk-ant-test1234abcdefgh"


def on(client, auth, **extra):
    r = client.put("/api/ai/settings", headers=auth, json={"api_key": KEY, "enabled": True, "acknowledged": True, **extra})
    assert r.status_code == 200, r.text


def run(client, auth, tid, fake, files=("F-civil", "F-arch")):
    ai_client.CLIENT = fake
    try:
        return client.post(f"/api/ai/tenders/{tid}/draft", headers=auth, json={"file_ids": list(files)})
    finally:
        ai_client.CLIENT = None


def test_each_company_brings_its_own_key_and_the_owner_switches_it_on(client, auth, ai):
    st = client.get("/api/ai/status", headers=auth).json()
    assert st["configured"] is False and st["enabled"] is False and st["can_change"] and st["provider"] == "anthropic" and st["model"] == "claude-opus-5-5"
    assert {p["id"]: p["available"] for p in st["providers"]} == {"anthropic": True, "openai": False, "google": False}
    assert run(client, auth, ai, FakeClient([])).status_code == 503                                             # no key yet
    assert client.put("/api/ai/settings", headers=auth, json={"enabled": True, "acknowledged": True}).status_code == 409           # needs a key first
    assert client.put("/api/ai/settings", headers=auth, json={"api_key": KEY, "enabled": True}).status_code == 422                 # needs the acknowledgement
    r = client.put("/api/ai/settings", headers=auth, json={"api_key": KEY, "enabled": True, "acknowledged": True})
    assert r.status_code == 200 and r.json()["enabled"] and r.json()["key_source"] == "own" and r.json()["key_last4"] == "efgh"
    assert KEY not in json.dumps(client.get("/api/ai/status", headers=auth).json()) and KEY not in r.text                           # the key never comes back
    org = asyncio.run(dbmod.get_db().orgs.find_one({}))
    assert org["ai_key_enc"] != KEY and KEY not in str(org) and org["ai_ack_provider"] == "anthropic"                              # stored encrypted
    assert client.put("/api/ai/settings", headers=auth, json={"enabled": False}).json()["enabled"] is False
    assert run(client, auth, ai, FakeClient([])).status_code == 403                                             # switched off again
    assert client.put("/api/ai/settings", headers=auth, json={"enabled": True}).json()["enabled"] is True        # already acknowledged: no need to repeat


def test_key_and_provider_rules(client, auth, ai):
    on(client, auth)
    assert client.put("/api/ai/settings", headers=auth, json={"api_key": "not-a-key"}).status_code == 422
    assert client.put("/api/ai/settings", headers=auth, json={"provider": "openai"}).status_code == 422            # planned, not available yet
    assert client.put("/api/ai/settings", headers=auth, json={"provider": "nonsense"}).status_code == 422
    assert client.put("/api/ai/settings", headers=auth, json={"model": "has space"}).status_code == 422
    assert client.put("/api/ai/settings", headers=auth, json={"model": "claude-sonnet-5-5"}).json()["model"] == "claude-sonnet-5-5"
    fake = FakeClient([item()])
    assert run(client, auth, ai, fake).status_code == 200 and fake.calls[0]["model"] == "claude-sonnet-5-5"        # the company's model is the one used
    r = client.put("/api/ai/settings", headers=auth, json={"clear_key": True}).json()
    assert r["configured"] is False and r["enabled"] is False and r["key_last4"] == ""                              # removing the key switches AI off


def test_a_server_wide_key_is_ignored_unless_the_operator_allows_it(client, auth, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-platform0000000000")
    assert client.get("/api/ai/status", headers=auth).json()["configured"] is False
    monkeypatch.setattr(config, "AI_ALLOW_PLATFORM_KEY", True)
    st = client.get("/api/ai/status", headers=auth).json()
    assert st["configured"] is True and st["key_source"] == "platform"
    on(client, auth)                                                                                                # the company's own key then takes over
    assert client.get("/api/ai/status", headers=auth).json()["key_source"] == "own"


def test_only_the_owner_can_change_settings(client, auth, ai):
    asyncio.run(dbmod.get_db().users.update_many({}, {"$set": {"role": "member"}}))
    assert client.put("/api/ai/settings", headers=auth, json={"api_key": KEY, "enabled": True, "acknowledged": True}).status_code == 403
    assert client.post("/api/ai/test", headers=auth).status_code == 403
    assert client.get("/api/ai/status", headers=auth).json()["can_change"] is False


def test_connection_test_is_free_and_explains_failures(client, auth, ai):
    assert client.post("/api/ai/test", headers=auth).status_code == 409                                             # no key
    on(client, auth)
    class Ok:
        models = SimpleNamespace(retrieve=lambda m: SimpleNamespace(display_name="Claude Opus 5.5", id=m))
    ai_client.CLIENT = Ok()
    try:
        assert client.post("/api/ai/test", headers=auth).json() == {"ok": True, "model": "Claude Opus 5.5"}
        for name, text in (("AuthenticationError", "did not accept this key"), ("NotFoundError", "does not know that model"), ("RateLimitError", "out of credit")):
            exc = type(name, (Exception,), {})("x")
            ai_client.CLIENT = SimpleNamespace(models=SimpleNamespace(retrieve=lambda m, e=exc: (_ for _ in ()).throw(e)))
            r = client.post("/api/ai/test", headers=auth)
            assert r.status_code == 502 and text in r.json()["detail"]
    finally:
        ai_client.CLIENT = None


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
    st = client.get("/api/ai/status", headers=other).json()                                                          # the other company has no key of its own
    assert st["configured"] is False and st["key_last4"] == ""


def test_the_real_client_path_handles_sdk_errors_without_a_network(monkeypatch):
    class Boom:
        def __init__(self, exc): self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._c)); self.messages = self.beta.messages; self.exc = exc
        def _c(self, **kw): raise self.exc
    for name, text in (("AuthenticationError", "did not accept"), ("RateLimitError", "out of credit"), ("APITimeoutError", "could not be reached"), ("Weird", "returned an error")):
        ai_client.CLIENT = Boom(type(name, (Exception,), {})("x"))
        with pytest.raises(ai_client.AIError, match=text):
            ai_client.PROVIDERS["anthropic"].draft_json(KEY, "m", "s", "u", ai_draft.SCHEMA)
    # a beta-field rejection is retried once on the plain endpoint
    calls = []
    class Twice:
        def __init__(self):
            def beta(**kw): calls.append("beta"); raise type("BadRequestError", (Exception,), {})("no fallbacks here")
            def plain(**kw): calls.append("plain"); return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text='{"items": [], "coverage_notes": ""}')])
            self.beta = SimpleNamespace(messages=SimpleNamespace(create=beta)); self.messages = SimpleNamespace(create=plain)
    ai_client.CLIENT = Twice()
    assert ai_client.PROVIDERS["anthropic"].draft_json(KEY, "m", "s", "u", ai_draft.SCHEMA)["items"] == [] and calls == ["beta", "plain"]
    ai_client.CLIENT = None


def test_plan_batches_splits_by_budget_and_cuts_big_files_at_page_boundaries():
    big = {"file_id": "B", "name": "Big", "revision": None, "pages": [{"n": i, "text": "x" * 40} for i in range(1, 6)]}
    small = {"file_id": "S", "name": "Small", "revision": None, "pages": [{"n": 1, "text": "y" * 30}]}
    empty = {"file_id": "E", "name": "Empty", "revision": None, "pages": [{"n": 1, "text": ""}]}
    bs = ai_draft.plan_batches([big, small, empty], budget=100, max_files=20)
    assert all(sum(len(p["text"]) for d in b for p in d["pages"]) <= 100 for b in bs)
    assert [(d["file_id"], d["pages"][0]["n"], d["pages"][-1]["n"]) for b in bs for d in b] == [("B", 1, 2), ("B", 3, 4), ("B", 5, 5), ("S", 1, 1)]
    assert len(ai_draft.plan_batches([small] * 5, budget=10_000, max_files=2)) == 3                      # file-count limit too


def test_intake_plan_skips_superseded_archive_and_scans_and_runs_in_parts_without_repeating(client, auth, ai):
    async def flag():
        d = dbmod.get_db()
        t = await d.tenders.find_one({"_id": ai})
        base = {"org_id": t["org_id"], "tender_id": ai, "revision": None, "pages": [{"n": 1, "text": "Old superseded drawing text, long enough to count."}], "page_count": 1, "chars": 1, "warnings": [], "status": "ok"}
        await d.doc_texts.insert_one({**base, "_id": f"{ai}:F-old", "file_id": "F-old", "name": "Civil Rev B.pdf", "superseded_by": "Civil Rev C.pdf"})
        await d.doc_texts.insert_one({**base, "_id": f"{ai}:F-arc", "file_id": "F-arc", "name": "Old.pdf", "in_archive": True})
    asyncio.run(flag())
    plan = client.get(f"/api/ai/tenders/{ai}/intake/plan", headers=auth).json()
    sent = {p["name"] for b in plan["batches"] for p in b["parts"]}
    assert sent == {"Civil Drawings Rev C.pdf", "Architectural Rev17.pdf"} and plan["files"] == 2
    why = {s["name"]: s["reason"] for s in plan["skipped"]}
    assert "Superseded" in why["Civil Rev B.pdf"] and "archive" in why["Old.pdf"] and "drawing reader" in why["Scan.pdf"]
    on(client, auth)
    # run the plan part by part: the second call must see the first call's proposal and mark a repeat as duplicate
    ai_client.CLIENT = FakeClient([item()])
    try:
        parts = plan["batches"][0]["parts"]
        r1 = client.post(f"/api/ai/tenders/{ai}/draft", headers=auth, json={"parts": parts, "run": "RUN1"})
        r2 = client.post(f"/api/ai/tenders/{ai}/draft", headers=auth, json={"parts": parts, "run": "RUN1"})
    finally:
        ai_client.CLIENT = None
    assert r1.status_code == 200 and r1.json()["batch"] == "RUN1" and r1.json()["proposals"][0]["status"] == "verified"
    assert r2.json()["proposals"][0]["status"] == "duplicate"


# ---------------------------------------------------------------- takeoff
def takeoff_item(**kw):
    base = {"description": "Earthworks area", "section": "earthworks", "unit": "m2", "operation": "single", "quantity": 2105, "method": "READ", "confidence": "high", "notes": "",
            "components": [{"label": "area", "value": 2105, "unit": "m2", "doc": "D1", "sheet": "A1", "page": 1, "source": "stated_area", "quote": "fill 1,310m3 and cut 113m3"}]}
    base.update(kw)
    return base


def run_takeoff(client, auth, tid, items, files=("F-civil",)):
    ai_client.CLIENT = FakeClient(items)
    try:
        return client.post(f"/api/takeoff/tenders/{tid}/run", headers=auth, json={"file_ids": list(files)})
    finally:
        ai_client.CLIENT = None


def test_takeoff_checks_every_line_does_the_arithmetic_and_hands_the_estimator_a_prefilled_qs_item(client, auth, ai):
    assert run_takeoff(client, auth, ai, []).status_code == 503                                       # no key yet
    on(client, auth)
    good = takeoff_item(components=[{"label": "fill", "value": 1310, "unit": "m3", "doc": "D1", "sheet": "A1", "page": 1, "source": "read_text", "quote": "fill 1,310m3 and cut 113m3"}], quantity=1310, unit="m3", description="Bulk fill")
    bad = takeoff_item(description="Invented", quantity=900, components=[{"label": "x", "value": 900, "unit": "m2", "doc": "D1", "sheet": "A1", "page": 1, "source": "read_text", "quote": "earthworks area is 900m2"}])
    scaled = takeoff_item(description="Wall length", unit="lm", method="SCALED", quantity=70, components=[{"label": "wall", "value": 70, "unit": "lm", "doc": "D1", "sheet": "A1", "page": 1, "source": "scaled", "quote": ""}])
    r = run_takeoff(client, auth, ai, [good, bad, scaled])
    assert r.status_code == 200, r.text
    by = {x["description"]: x for x in r.json()["lines"]}
    assert by["Bulk fill"]["status"] == "verified" and by["Bulk fill"]["quantity"] == 1310
    assert by["Invented"]["status"] == "unverified" and by["Wall length"]["status"] == "check"
    assert by["Bulk fill"]["components"][0]["file"] == "Civil Drawings Rev C.pdf"
    assert client.get(f"/api/takeoff/tenders/{ai}/lines", headers=auth).json()["lines"].__len__() == 3
    # an unverified line cannot be accepted; a verified one returns a pre-filled QS item built from the platform's number
    assert client.post(f"/api/takeoff/lines/{by['Invented']['id']}/decision", headers=auth, json={"decision": "accepted"}).status_code == 409
    peek = client.post(f"/api/takeoff/lines/{by['Bulk fill']['id']}/decision", headers=auth, json={"decision": "accepted", "commit": False}).json()
    assert peek["decision"] == "pending" and peek["qs"]["quantity"] == 1310                       # cancelling the Add dialog leaves the line open
    assert [x for x in client.get(f"/api/takeoff/tenders/{ai}/lines", headers=auth).json()["lines"] if x["description"] == "Bulk fill"][0]["decision"] is None
    a = client.post(f"/api/takeoff/lines/{by['Bulk fill']['id']}/decision", headers=auth, json={"decision": "accepted"}).json()
    assert a["qs"]["quantity"] == 1310 and a["qs"]["basis"] == "PROVIDED" and a["qs"]["unit"] == "m3" and "Civil Drawings Rev C.pdf" in a["qs"]["source"] and a["qs"]["section_hint"] == "earthworks"
    w = client.post(f"/api/takeoff/lines/{by['Wall length']['id']}/decision", headers=auth, json={"decision": "accepted"}).json()
    assert w["qs"]["basis"] == "MEASURED" and "check on the drawing" in w["qs"]["notes"]
    assert client.post(f"/api/takeoff/lines/{by['Invented']['id']}/decision", headers=auth, json={"decision": "rejected"}).status_code == 422       # a reason is needed
    assert client.post(f"/api/takeoff/lines/{by['Invented']['id']}/decision", headers=auth, json={"decision": "rejected", "reason": "not on the drawing"}).status_code == 200


def test_takeoff_does_not_repeat_lines_and_pictures_are_limited_to_chosen_documents(client, auth, ai):
    on(client, auth)
    ok = takeoff_item(description="Bulk fill", unit="m3", quantity=1310, components=[{"label": "fill", "value": 1310, "unit": "m3", "doc": "D1", "sheet": "A1", "page": 1, "source": "read_text", "quote": "fill 1,310m3 and cut 113m3"}])
    assert run_takeoff(client, auth, ai, [ok]).status_code == 200
    ai_client.CLIENT = FakeClient([])
    try:
        client.post(f"/api/takeoff/tenders/{ai}/run", headers=auth, json={"file_ids": ["F-civil"]})
        assert "Bulk fill: 1310" in json.dumps(ai_client.CLIENT.calls[0]["messages"])             # earlier lines are listed so they are not proposed again
        r = client.post(f"/api/takeoff/tenders/{ai}/run", headers=auth, json={"file_ids": ["F-civil"], "pictures": [{"file_id": "F-arch", "page": 1}]})
        assert r.status_code == 422
    finally:
        ai_client.CLIENT = None


def test_pictures_are_sent_as_image_blocks_before_the_text():
    fake = FakeClient([])
    ai_client.CLIENT = fake
    try:
        try:
            ai_client.PROVIDERS["anthropic"].draft_json(KEY, "m", "sys", "the text", {"type": "object"}, images=[("D1 page 3:", b"\x89PNG")])
        except ai_client.AIError:
            pass                                                       # the stand-in's answer has no usable items; only the request matters here
    finally:
        ai_client.CLIENT = None
    content = fake.calls[0]["messages"][0]["content"]
    assert [c["type"] for c in content] == ["text", "image", "text"] and content[1]["source"]["media_type"] == "image/png" and content[2]["text"] == "the text"


# ---------------------------------------------------------------- viewer and pictures (Drive stood in for)
def _drawing_pdf() -> bytes:
    import io
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A3))
    c.drawString(100, 700, "A1 Site Plan"); c.drawString(100, 600, "Actual earthworks area 2,105m2"); c.drawString(1020, 40, "A1 25237  Site Plan  1:200 @ A3")
    c.showPage(); c.drawString(100, 700, "Page two"); c.save()
    return buf.getvalue()


@pytest.fixture()
def drive(client, auth, ai, monkeypatch):
    import routes_takeoff as rt
    pdf = _drawing_pdf()
    calls = {"downloads": 0}

    async def token(user): return "tok"
    async def walk(tok, folder): return [{"id": "F-civil", "name": "Civil Drawings Rev C.pdf", "mime": "application/pdf", "is_folder": False, "path": ""}], False
    async def download(tok, f):
        calls["downloads"] += 1
        return f["name"], "application/pdf", pdf
    monkeypatch.setattr(rt, "_token", token); monkeypatch.setattr(rt.dc, "walk", walk); monkeypatch.setattr(rt.dc, "download", download)
    rt._CACHE.clear()

    async def seed():
        d = dbmod.get_db()
        await d.tenders.update_one({"_id": ai}, {"$set": {"drive_folder": {"id": "FOLDER", "name": "Job"}}})
        await d.doc_texts.update_one({"_id": f"{ai}:F-civil"}, {"$set": {"mime": "application/pdf", "modified": "2026-10-01T00:00:00Z"}})
    asyncio.run(seed())
    return calls


def test_pictures_are_rendered_and_sent_and_the_page_limit_is_explained(client, auth, ai, drive):
    on(client, auth)
    fake = FakeClient([])
    ai_client.CLIENT = fake
    try:
        r = client.post(f"/api/takeoff/tenders/{ai}/run", headers=auth, json={"file_ids": ["F-civil"], "pictures": [{"file_id": "F-civil", "page": 1}, {"file_id": "F-civil", "page": 2}]})
        assert r.status_code == 200 and r.json()["pictures"] == 2
        blocks = fake.calls[0]["messages"][0]["content"]
        assert [b["type"] for b in blocks] == ["text", "image", "text", "image", "text"] and blocks[0]["text"].startswith("D1 (Civil Drawings Rev C.pdf) page 1")
        assert client.post(f"/api/takeoff/tenders/{ai}/run", headers=auth, json={"file_ids": ["F-civil"], "pictures": [{"file_id": "F-civil", "page": 9}]}).status_code == 422     # no such page
        too_many = [{"file_id": "F-civil", "page": 1}] * (config.TAKEOFF_MAX_PICTURES + 1)
        r = client.post(f"/api/takeoff/tenders/{ai}/run", headers=auth, json={"file_ids": ["F-civil"], "pictures": too_many})
        assert r.status_code == 422 and "Run the takeoff again" in r.json()["detail"]
    finally:
        ai_client.CLIENT = None


def test_click_to_source_finds_the_quote_on_the_page_serves_the_page_and_caches_the_pdf(client, auth, ai, drive):
    on(client, auth)
    good = takeoff_item(components=[{"label": "area", "value": 2105, "unit": "m2", "doc": "D1", "sheet": "A1", "page": 1, "source": "stated_area", "quote": "Actual earthworks area 2,105m2"}])
    scaled = takeoff_item(description="Wall", unit="lm", method="SCALED", quantity=70, components=[{"label": "wall", "value": 70, "unit": "lm", "doc": "D1", "sheet": "A1", "page": 1, "source": "scaled", "quote": ""}])
    lines = {x["description"]: x for x in run_takeoff(client, auth, ai, [good, scaled]).json()["lines"]}
    s = client.get(f"/api/takeoff/lines/{lines['Earthworks area']['id']}/sources", headers=auth).json()["sources"][0]
    assert s["viewable"] and s["how"] == "quote" and s["file_id"] == "F-civil" and s["page"] == 1 and len(s["rects"]) == 1 and s["pages"] == 2
    w = client.get(f"/api/takeoff/lines/{lines['Wall']['id']}/sources", headers=auth).json()["sources"][0]
    assert w["viewable"] and w["how"] == "none" and w["rects"] == []                                 # a scaled line shows the page with no highlight: the estimator measures
    img = client.get(f"/api/takeoff/tenders/{ai}/files/F-civil/pages/1/image", headers=auth)
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG" and img.headers["content-type"] == "image/png"
    assert client.get(f"/api/takeoff/tenders/{ai}/files/F-civil/pages/9/image", headers=auth).status_code == 404
    sh = client.get(f"/api/takeoff/tenders/{ai}/files/F-civil/sheets", headers=auth).json()
    assert [p["page"] for p in sh["pages"]] == [1, 2] and sh["scale"]["1"] == "1:200@A3"
    assert drive["downloads"] == 1                                                                   # the same PDF is not downloaded again for every click
    assert client.get(f"/api/takeoff/tenders/{ai}/files/NOPE/pages/1/image", headers=auth).status_code == 404       # only documents read for this tender


def scope_item(title="Temporary retaining to the cut face", **kw):
    base = {"title": title, "detail": "Retaining walls are limited to 1.5m.", "group": "Temporary works", "owner": "OWN WORKS", "treatment": "UNRESOLVED",
            "impact": "Confirm method and who designs it.", "rag": "AMBER", "basis": "quoted",
            "evidence": [{"file_id": "F-civil", "page": 2, "quote": "Retaining walls maximum height 1.5m (Civil DWG301)"}]}
    base.update(kw)
    return base


def run_scope(client, auth, tid, fake):
    ai_client.CLIENT = fake
    try:
        return client.post(f"/api/ai/tenders/{tid}/draft", headers=auth, json={"file_ids": ["F-civil"], "mode": "scope"})
    finally:
        ai_client.CLIENT = None


def test_scope_drafting_checks_quotes_never_prices_and_hands_back_a_scope_edit(client, auth, ai):
    on(client, auth)
    fake = FakeClient([scope_item(), scope_item("Invented requirement", evidence=[{"file_id": "F-civil", "page": 2, "quote": "Retaining walls maximum height 9.9m (Civil DWG301)"}])])
    r = run_scope(client, auth, ai, fake)
    assert r.status_code == 200, r.text
    sent = fake.calls[0]
    assert "SCOPE REQUIREMENTS" in json.dumps(sent) and "PROJECT BRIEF" in json.dumps(sent)
    ps = {p["title"]: p for p in r.json()["proposals"]}
    good, bad = ps["Temporary retaining to the cut face"], ps["Invented requirement"]
    assert good["kind"] == "scope" and good["status"] == "verified" and good["group"] == "Temporary works" and good["owner"] == "OWN WORKS"
    assert bad["status"] == "unverified"
    assert client.post(f"/api/ai/proposals/{bad['id']}/decision", headers=auth, json={"decision": "accepted"}).status_code == 409
    a = client.post(f"/api/ai/proposals/{good['id']}/decision", headers=auth, json={"decision": "accepted"}).json()["edit"]
    assert a["target"] == "scope" and a["key"].startswith("C-") and a["value"]["treatment"] == "UNRESOLVED" and "Civil Drawings Rev C.pdf p.2" in a["value"]["source"]
    pv = client.post(f"/api/tenders/{ai}/revisions/1/preview", headers=auth, json={"edits": [a]})
    assert pv.status_code == 200 and any(x["title"] == good["title"] for x in pv.json()["estimate"]["scope"]["items"])
    # a second run does not repeat it; register drafting is not confused by scope proposals
    again = run_scope(client, auth, ai, FakeClient([scope_item()])).json()["proposals"]
    assert again[0]["status"] == "duplicate"
    assert run(client, auth, ai, FakeClient([item(title="Something else")])).json()["proposals"][0]["status"] == "verified"
