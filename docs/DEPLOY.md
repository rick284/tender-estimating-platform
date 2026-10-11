# Putting the platform online (step by step)

Three free services, same as Blackline: **MongoDB Atlas** (database), **Render** (the server), **Netlify** (the website).
Do them in this order. Keep a note of each address you are given.

## 1. Atlas: a private database for this platform
Use your existing Atlas project and cluster (no new cluster needed).
1. Atlas > **Database Access** > **Add New Database User**. Name `tender_app`, choose **Password** > **Autogenerate Secure Password** and copy it somewhere safe.
2. Under **Database User Privileges** choose **Specific Privileges** > role `readWrite` on database `tender_platform`. Save.
3. **Network Access** should already allow `0.0.0.0/0` from the Blackline setup (Render uses changing addresses). If not, add it.
4. **Database** > **Connect** > **Drivers** and copy the connection string. It looks like
   `mongodb+srv://tender_app:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`.
   Replace `<password>` with the password from step 1.

## 2. Render: the server
1. Render > **New** > **Blueprint** > connect GitHub repo `tender-estimating-platform`. It reads `render.yaml`.
2. When asked for values: `MONGO_URL` = the string from step 1.4. `BOOTSTRAP_EMAIL` = your email address. Leave `CORS_ORIGINS` blank for now.
3. Deploy. When it finishes, copy the service address, like `https://tender-platform-api.onrender.com` (no slash at the end).
   Open `<address>/api/health`. It should show `{"status":"ok"}`.

## 3. Netlify: the website
1. Netlify > **Add new site** > **Import an existing project** > GitHub > `tender-estimating-platform`. Netlify reads `web/netlify.toml`.
2. **Site configuration** > **Environment variables** > add `VITE_API_URL` = the Render address from step 2.3 (no slash at the end).
3. Deploy. Copy the site address, like `https://something.netlify.app`.

## 4. Join the two together
1. Back in Render > the service > **Environment** > set `CORS_ORIGINS` to the Netlify address (no slash at the end) and save. Render restarts.
2. Open the Netlify address. You will see **Create your workspace**. Use the email you set as `BOOTSTRAP_EMAIL`.
   Only that email can create the first account. After that nobody else can sign up unless you turn `REGISTRATION_OPEN` on.

## Good to know
- The free Render server sleeps after about 15 minutes. The first request after that takes up to a minute.
- Uploaded workbooks are calculated and the results saved in your database. The original `.xlsx` file itself is not stored.
- Passwords are stored hashed. Sessions last 12 hours.
- Before any other company uses it: paid hosting with backups, privacy terms, and a security review (see `docs/SPEC.md` section 14).
