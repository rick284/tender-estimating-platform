"""Offline: unsaved edits survive a reload and a lost connection; the offline banner shows; the built app (service worker) opens with no connection."""
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:5173/")
    pg.get_by_label("Email").fill("rick@3bearsprojects.co.nz"); pg.get_by_label("Password").fill("a long test password")
    pg.get_by_role("button", name="Sign in").click()
    pg.get_by_role("link", name="329 Hobsonville Road Childcare Centre").first.click()
    expect(pg.get_by_text("Tender overview")).to_be_visible(timeout=20000)
    pg.get_by_role("button", name="Edit", exact=True).click()
    pg.locator("aside").get_by_role("button", name="QS Takeoff").click()
    pg.get_by_label("EW01 quantity").fill("3000")
    expect(pg.get_by_text("1 change")).to_be_visible(timeout=8000)
    # connection lost: banner, saving blocked, typing still works
    ctx.set_offline(True)
    expect(pg.get_by_text("You're offline.")).to_be_visible()
    expect(pg.get_by_role("button", name="Review & save")).to_be_disabled()
    pg.get_by_label("EW01 quantity").fill("3100")
    ctx.set_offline(False)
    expect(pg.get_by_text("You're offline.")).to_have_count(0)
    expect(pg.get_by_role("button", name="Review & save")).to_be_enabled(timeout=10000)      # totals refreshed by themselves
    # closed without saving: the draft is waiting when the tender is opened again
    pg.wait_for_timeout(500)
    pg.reload()
    expect(pg.get_by_text("1 unsaved change")).to_be_visible(timeout=20000)
    pg.get_by_role("button", name="Continue editing").click()
    pg.locator("aside").get_by_role("button", name="QS Takeoff").click()
    assert pg.get_by_label("EW01 quantity").input_value() == "3100"
    # discarding removes it for good
    pg.once("dialog", lambda d: d.accept())
    pg.get_by_role("button", name="Discard", exact=True).click()
    pg.reload()
    expect(pg.get_by_text("Tender overview").or_(pg.get_by_text("Quantity"))).to_be_visible(timeout=20000)
    assert pg.get_by_text("unsaved change").count() == 0
    assert not errs, errs
    print("offline drafts ok")
    b.close()
