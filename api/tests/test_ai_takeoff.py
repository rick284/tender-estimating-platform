import ai_takeoff as t

PAGES = {3: "SITE PLAN. Actual earthworks area 2,105m2. Carpark 21 spaces including 1 accessible.", 4: "Door D1 2000 wide. Door D2 900 wide."}


def item(comps, op="single", q=None, **kw):
    return {"description": "x", "section": "earthworks", "unit": "m2", "operation": op, "components": comps, "quantity": q, "method": "READ", "confidence": "high", "notes": "", **kw}


def comp(value, quote, page=3, source="stated_area"):
    return {"label": "area", "value": value, "unit": "m2", "sheet": "A1", "page": page, "source": source, "quote": quote}


def test_a_number_that_is_written_on_the_cited_page_is_verified():
    r = t.verify([item([comp(2105, "Actual earthworks area 2,105m2")], q=2105)], PAGES)[0]
    assert r["status"] == "verified" and r["computed"] == 2105 and r["components"][0]["found"] is True


def test_a_quote_that_is_not_on_the_page_or_a_number_not_in_the_quote_is_unverified():
    a = t.verify([item([comp(2105, "Actual earthworks area 2,500m2")], q=2105)], PAGES)[0]
    b = t.verify([item([comp(2500, "Actual earthworks area 2,105m2")], q=2500)], PAGES)[0]
    c = t.verify([item([comp(2105, "Actual earthworks area 2,105m2", page=4)], q=2105)], PAGES)[0]
    assert a["status"] == b["status"] == c["status"] == "unverified"
    assert "not in the quote" in b["problems"][0] and "not on page 4" in c["problems"][0]


def test_the_platform_does_the_arithmetic_and_rejects_a_wrong_claim():
    small = t.verify([item([comp(3, "Door D1 2000", page=4, source="read_text")], q=3)], PAGES)[0]
    assert small["status"] == "unverified"                                   # 3 is neither a number in the quote nor its millimetre conversion
    mm = t.verify([item([comp(2.0, "Door D1 2000", page=4, source="read_text")], q=2.0)], PAGES)[0]
    assert mm["status"] == "verified"
    good = t.verify([item([comp(2000, "Door D1 2000", page=4, source="read_text"), comp(900, "Door D2 900", page=4, source="read_text")], op="sum", q=2900)], PAGES)[0]
    assert good["status"] == "verified" and good["computed"] == 2900
    bad = t.verify([item([comp(2000, "Door D1 2000", page=4, source="read_text"), comp(900, "Door D2 900", page=4, source="read_text")], op="sum", q=3000)], PAGES)[0]
    assert bad["status"] == "unverified" and "does not match" in bad["problems"][0]


def test_counted_and_scaled_components_need_the_estimators_check_and_a_missing_quote_fails():
    r = t.verify([item([{"label": "walls", "value": 12.5, "unit": "lm", "sheet": "A1", "page": 3, "source": "scaled", "quote": ""}], q=12.5, method="SCALED")], PAGES)[0]
    assert r["status"] == "check"
    r2 = t.verify([item([comp(2105, "")], q=2105)], PAGES)[0]
    assert r2["status"] == "unverified"
