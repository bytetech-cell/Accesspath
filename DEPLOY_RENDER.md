# Put ACCESSPATH online (Render)

After this you get a link like `https://accesspath.onrender.com` where anyone can audit **any URL**.
You do **not** need Docker on your laptop. Render builds everything on its own servers.

## 1. Push the project to GitHub
In VS Code, open the `accesspath` folder, open a terminal and run:
```
git init
git add .
git commit -m "ACCESSPATH"
```
Create an empty repo on GitHub (for example `accesspath`), then:
```
git remote add origin https://github.com/Anandtripathiii/accesspath.git
git branch -M main
git push -u origin main
```
Your `backend\.env` (with the TinyFish key) is **not** uploaded, because `.gitignore` skips it. Good.

## 2. Create the service on Render
1. Go to https://dashboard.render.com → **New +** → **Blueprint**.
2. Pick your `accesspath` repo. Render reads `render.yaml` and sets everything up.
3. It asks for the secret values:
   - `TINYFISH_API_KEY` → your key (`sk-tinyfish-...`)
   - `ACCESS_CODE` → a password you choose, for example `hearmeout2026`. Judges type this before running an audit, so strangers can't use your TinyFish credits.
   - `GEMINI_API_KEY` → optional (leave empty to use the built-in fix library)
4. Click **Apply**. The first build takes about 5–10 minutes (it downloads Chromium).

## 3. Open your link
When it says **Live**, open the `https://accesspath-xxxx.onrender.com` link at the top of the service page.
Check the top-right says **TinyFish: connected**. Type the access code, paste any URL and click **Run audit**.

The demo shop also works online, at `https://<your-link>/demo/`. Because it is now public, TinyFish can open it, so step 4 runs live on the demo too.

## Good to know
- **Free plan sleeps** after 15 minutes with no visitors. The first visit then takes about a minute to wake up. Open the link a few minutes before you present.
- **Free plan has 512 MB memory**, so audits run one at a time. If a big site fails with a memory error, upgrade the service to the Starter plan in Render settings.
- **History resets** when the service restarts (free plan has no permanent disk). For permanent history, create a Render PostgreSQL database and add its "Internal Database URL" as `DATABASE_URL`, changing `postgresql://` to `postgresql+psycopg2://` at the start.
- **Update the site:** change code, then `git add . && git commit -m "update" && git push`. Render redeploys by itself.
