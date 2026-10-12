# Switching on AI drafting (one-off, about 10 minutes)

AI drafting reads the documents you choose and proposes tender-register items (documents, RFIs, assumptions, exclusions, inclusions, risks).
It drafts only; every proposal must quote the document, the platform checks each quote, and nothing enters the estimate until you accept it and save a revision.
It is billed by use on a separate Anthropic account (not your Claude chat subscription).

## A. Account, credit and a spending limit
1. Open https://console.anthropic.com and sign in with the 3bears email (organisation name: Three Bears Projects).
2. Settings > Billing: add a payment method and buy a small credit amount (US$20 is plenty for testing). Turn auto-reload OFF.
3. Settings > Limits: set a monthly spend limit of about US$20.

## B. The key (keep it private: never paste it in a chat or email)
1. Settings > API keys > Create key. Name it `tender-platform`. Copy it once and store it in a password manager.
2. Render dashboard > tender-platform-api > Environment > add `ANTHROPIC_API_KEY` = the key. Save (Render restarts, a couple of minutes).
   (`AI_MODEL` is already set by the blueprint to claude-opus-5-5; leave it.)

## C. Switch it on in the platform
Tender > AI Drafting > tick the acknowledgement (the text of the documents you choose is sent to Anthropic's API) > Switch on. Only the company owner can.
Then: Drive Documents (read some files) > AI Drafting > tick documents > Draft register items > review each proposal > Edit > Accept into my draft > Review and save.

## What is sent, and what is not
Only the text of the documents you tick, plus the tender's name, location, client and the titles already in its register. No rates, no costs, no workbook, no mailbox.
