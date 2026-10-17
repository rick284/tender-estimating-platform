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
(for example `329 Hobsonville Road`) > the file list appears with latest/superseded revisions and a check of the 00-07 job folders.

## D. Optional: let the platform add job folders (write permission)
By default Drive is read-only. To let the platform create job folders:
1. Google Cloud console > Google Auth Platform > **Data access** > **Add or remove scopes** > tick (or paste) `https://www.googleapis.com/auth/drive` > Update > **Save**.
2. In the platform, open a tender > **Drive Documents** > **Allow Drive to add folders** and approve on Google (Google will list "See, edit, create and delete all of your Google Drive files": that is Google's wording for this permission; the narrower `drive.file` permission cannot add a folder inside a folder you made yourself, such as Blackline Estimating).
3. **Create the job folder…** > **Choose the jobs folder…** once for the company (for example `Blackline Estimating`) > type or pick the client (existing client folders are offered) > check the job name > **Create job folder**.

Where it goes: always `<jobs folder> / <client> / <job>` with `00 Project Admin` ... `07 Superseded and Archive` inside. Never My Drive. An existing client or job folder is used as it is (never duplicated); only missing subfolders are added.
- The platform's code only ever **creates new, empty folders**. It never renames, moves, overwrites, shares or deletes, and it skips a number already used by a differently named folder.
- **Set up job folders** on a linked folder adds the missing 00-07 subfolders to it.
- Remove the permission any time at https://myaccount.google.com/permissions (then reconnect read-only).

## Notes
- Google shows "Google hasn't verified this app" while in Testing mode: Advanced > continue. Expected.
- Disconnect anytime in the platform, or at https://myaccount.google.com/permissions
- The saved Google token is encrypted in the database with `TOKEN_ENC_KEY`. Changing that key makes you reconnect.
