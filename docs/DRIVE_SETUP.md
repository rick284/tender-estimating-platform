# Connecting Google Drive (one-off setup, about 15 minutes)

The platform asks Google for **read-only** access (it can look at files, never change, move or delete them).
You create the "key" once in Google Cloud, then paste two values into Render.

## A. Create the Google connection
1. Go to https://console.cloud.google.com and sign in with the Google account that owns the Drive (the 3bears account).
2. Top bar > project picker > **New project** > name it `Tender Platform` > Create. Make sure it is selected.
3. Menu > **APIs & Services > Library** > search **Google Drive API** > **Enable**.
4. Menu > **APIs & Services > OAuth consent screen** (may be called "Google Auth Platform"):
   - User type **External**, app name `Tender Estimating Platform`, your email for support/contact. Save.
   - Under **Audience / Test users** add your own Gmail address (and any colleague who will connect Drive).
   - Leave it in **Testing** mode for now. (Testing mode makes Google ask you to re-approve about every 7 days; publishing the app removes that, and is needed before other customers use it. Google will want a privacy policy link at that point.)
5. **Data access / Scopes** > add `.../auth/drive.readonly`, `openid` and `email`.
6. **APIs & Services > Credentials > Create credentials > OAuth client ID**:
   - Application type **Web application**, name `Tender Platform web`.
   - **Authorised redirect URIs** > add exactly: `https://tender-platform-api.onrender.com/api/drive/callback`
   - Create. Copy the **Client ID** and **Client secret** (keep the secret private; do not email it or put it in chat).

## B. Give them to Render
Render dashboard > tender-platform-api > **Environment**: add
- `GOOGLE_CLIENT_ID` = the Client ID
- `GOOGLE_CLIENT_SECRET` = the Client secret
- (already set by the blueprint: `GOOGLE_REDIRECT_URI`, `WEB_URL`, `TOKEN_ENC_KEY`; check `GOOGLE_REDIRECT_URI` matches step A6 exactly)

Save; Render restarts the service.

## C. Connect inside the platform
Open a tender > **Drive Documents** > **Connect Google Drive** > approve on Google > **Choose folder**
(for example `329 Hobsonville Road`) > the file list appears with latest/superseded revisions and a check of the 01-07 folders.

## Notes
- Google shows "Google hasn't verified this app" while in Testing mode: Advanced > continue. Expected.
- Disconnect anytime in the platform, or at https://myaccount.google.com/permissions
- The saved Google token is encrypted in the database with `TOKEN_ENC_KEY`. Changing that key makes you reconnect.
