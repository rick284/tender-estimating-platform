# Switching on AI drafting (about 10 minutes, once per company)

Each company brings its own AI provider account and key. Nothing is set on the server. The key is entered on the AI Drafting page, stored encrypted,
never shown again, and used only for that company. AI drafting reads the documents you choose and proposes tender-register items; it only drafts, every
proposal must quote the document (the platform checks each quote), and nothing enters the estimate until you accept it and save a revision.

## A. The provider account (Anthropic is the first provider supported)
1. Open https://console.anthropic.com and sign in (organisation name: your company).
2. Settings > Billing: add a payment method and buy a small credit amount (US$20 is plenty for testing). Turn auto-reload OFF.
3. Settings > Limits: set a monthly spend limit of about US$20.
4. Settings > API keys > Create key (name it `tender-platform`). Copy it once into a password manager. Never paste it into a chat or email.

## B. In the platform (company owner only)
1. Open any tender > AI Drafting > "AI provider for this company".
2. Provider: Anthropic (Claude). Model: leave the default. Paste the key > Save > Test connection (free; checks the key and the model exist).
3. Tick the acknowledgement (the text of the documents you choose is sent to the provider) > Switch on.

## C. Using it
Drive Documents: read some files. AI Drafting: tick documents > Draft register items > review each proposal > Edit > Accept into my draft > Review and save.

## What is sent, and what is not
Only the text of the documents you tick, plus the tender's name, location, client and the titles already in its register. No rates, no costs, no workbook, no mailbox.
