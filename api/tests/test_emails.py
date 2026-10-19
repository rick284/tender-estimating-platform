import emails

FIRST = """# INCOMING EMAIL — HISTORICAL TEST TRANSCRIPTION

Source: Dave Stewart (Siteworks), 04-Sep-2026, subject: FW: Childcare Centre - 329 Hobsonville Road, Hobsonville

Original Gmail message ID: 1a0693e378eab3f6. Verbatim substantive scope excerpt.

Hi Rick.
Earth works including sediment and silt control. Drainage - Jason is pricing. See RFI-06 and SC-012.
The tender is due Monday the 14th.

=== SUPPLEMENTARY INCOMING EMAIL ===

Source: Dave Stewart, 04-Sep-2026, subject: hobsonville childcare.

Original Gmail message ID: 1a0694434e9c42ab.

Sorry Rick can you also allow for the channel drains anywhere around the building.
Attachment: Channel drain detail.pdf; Rate sheet.xlsx
"""


def test_classify():
    assert emails.classify("04 RFIs/04.1 Emails In", "x") == "in"
    assert emails.classify("04 RFIs/04.2 Emails Out - DRAFT ONLY", "x") == "out"
    assert emails.classify("", "2026-09-04_In_Dave_Stewart_Enquiry") == "in"
    assert emails.classify("02 Source", "plan.pdf") is None


def test_parse_the_real_test_transcription_layout():
    t = emails.parse_thread("2026-09-04_In_Dave_Stewart_Initial_Tender_Enquiry_TEST", FIRST)
    assert t["date"] == "2026-09-04" and t["count"] == 2
    assert t["subject"].startswith("FW: Childcare Centre") and t["party"].startswith("Dave Stewart")
    assert t["gmail_ids"] == ["1a0693e378eab3f6", "1a0694434e9c42ab"]
    assert t["messages"][1]["subject"] == "hobsonville childcare." and "channel drains" in t["messages"][1]["body"]
    assert t["refs"] == ["RFI-06", "SC-012"] and t["attachments"] == ["Channel drain detail.pdf", "Rate sheet.xlsx"]


def test_generic_headers_and_a_plain_note():
    t = emails.parse_thread("2026-10-01_Out_Quote_request_Concrete", "From: Rick\nDate: 1-Oct-2026\nSubject: Quote request\nTo: a@b.co\n\nPlease quote Q-03.")
    assert (t["date"], t["subject"], t["party"], t["refs"]) == ("2026-10-01", "Quote request", "Rick", ["Q-03"])
    t2 = emails.parse_thread("2026-10-02_In_Note", "Just some text with no headers")
    assert t2["count"] == 1 and t2["subject"] == "Note" and t2["messages"][0]["body"].startswith("Just")
    assert emails.snippet("abc the channel drains here", "channel") .startswith("abc the channel")
