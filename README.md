# ACCESSPATH — Autonomous Accessibility Auditor

> "Don't just scan websites. Test whether everyone can use them."
> Team **Hear me out** · **HackIIITD**

ACCESSPATH gives a website + a task (for example *"add headphones to the cart and reach checkout"*).
Then it checks: **can a keyboard user, a screen reader user and a phone user really finish that task?**

---

## How it works (same 9 steps as our PPT)

| # | Step | What the code does | File |
|---|------|--------------------|------|
| 1 | Enter website URL | You type the URL + task in the dashboard | `frontend/app.js` |
| 2 | Inspect the site | Playwright opens the page, counts links / buttons / inputs, takes a screenshot | `services/browser_checks.py` → `inspect_site` |
| 3 | Select conditions | Keyboard / Screen reader / Mobile chips | `pipeline.py` |
| 4 | Attempt journey | **TinyFish agent** opens the real site in the cloud and tries the task like a normal mouse user. It sends back the exact buttons/links it clicked | `services/tinyfish.py` |
| 5 | Record interactions | Playwright **replays that same path using only the keyboard** (Tab, Enter, Escape) and records every focus move + screenshots | `browser_checks.py` → `keyboard_journey` |
| 6 | Analyse findings | axe-core rules + focus trap check + focus ring check + screen reader checks + mobile (touch size, sideways scroll) | `browser_checks.py` |
| 7 | Explain & recommend | LLM (Gemini / OpenAI / Claude) explains the cause in simple words and gives code fixes. No key? A built-in fix library is used | `services/llm.py` |
| 8 | Show audit report | Dashboard: Overview, Journey, Issues, Evidence, Fix ideas | `frontend/app.js` |
| 9 | Fix and rerun | "Fix & rerun" button runs the same journey again and shows **before vs after** | `main.py` → `/rerun` |

**The key idea:** TinyFish proves a *mouse user* can finish the task. Playwright checks if a *keyboard user* can finish the **same** path. If TinyFish passes but the keyboard fails → that is an accessibility barrier, and we show exactly where.

```
React dashboard ──► FastAPI ──► SQLite / PostgreSQL
                      │
     ┌────────────┬───┴────────┬──────────────┐
  TinyFish API  Playwright   axe-core     LLM analysis
  (journey)     (keyboard,   (WCAG rules) (causes + fixes)
                 mobile,
                 screenshots)
```

---

## Setup (venv, no Docker)

You need **Python 3.10+** (3.11 / 3.12 recommended). Node.js is **not** needed.

### Windows
1. Double-click **`setup_windows.bat`** (makes `backend\venv`, installs packages, downloads Chromium).
2. Open `backend\.env` and paste your **TINYFISH_API_KEY** (get it from https://agent.tinyfish.ai/api-keys).
   Optional: add `GEMINI_API_KEY` (free) or `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` for AI explanations.
3. Double-click **`run_windows.bat`** → browser opens at http://127.0.0.1:8000

### Manual (any OS)
```bash
cd backend
python -m venv venv
# Windows:  venv\Scripts\activate        macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env      # macOS/Linux: cp .env.example .env
python run.py
```
Open **http://127.0.0.1:8000** (dashboard) or **http://127.0.0.1:8000/docs** (API).

macOS / Linux shortcut: `./setup.sh` then `./run.sh`.

---

## Put it online
See **[DEPLOY_RENDER.md](DEPLOY_RENDER.md)**: push to GitHub, create a Render Blueprint, paste your TinyFish key. You get a public link that audits any URL.

## Demo for the judges (2 minutes)

The project comes with **21 demo websites** (ShopEasy plus 20 fictional sites such as StreamNest, MailNest, TravelGo and RailYatra — pick one in the **Demo website** dropdown). Each has a broken and a fixed version. ShopEasy, the main one, has real accessibility bugs
(keyboard trap in the side menu, missing alt text, no focus ring, tiny cart icon, no `lang`…).

1. Click **Fill demo audit** → **Run audit**.
2. Watch the 9 steps light up. Result: **FAILED** — keyboard focus is trapped in the side menu, so "Add to Cart" is never reached (same as slide 5).
3. Open **Evidence** (screenshot with the trap marked in red) and **Fix ideas** (code fix).
4. Click **Apply developer fix** (switches the shop to the fixed version) → click **↻ Fix & rerun**.
5. Result: **PASSED**, score goes up, and the "Retest result" box lists every fixed issue.

> TinyFish runs in the cloud, so it **cannot open `localhost`**. For the local demo shop, step 4 is skipped and the journey steps you type are used.
> To show TinyFish live: audit any public website, **or** expose the demo with a tunnel, e.g. `ngrok http 8000`, and audit `https://<your-ngrok-id>.ngrok-free.app/demo/`.

---

## Tips for real websites

- **Task** in simple words: *"Search for a laptop, open the first result and add it to the cart."*
- **Journey steps** (optional) = the visible text of each button/link in order, separated by `>`:
  `Laptops > Add to Cart > Cart > Checkout`. If you leave it empty, TinyFish finds the path for you.
- Set `HEADLESS=false` in `.env` to **watch** Chromium do the keyboard journey on your screen.
- ACCESSPATH never enters real personal or payment details — the agent is told to stop before payment.

## Use PostgreSQL instead of SQLite
```bash
pip install -r requirements-postgres.txt
```
Then in `backend/.env`:
`DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/accesspath` (create the `accesspath` database first). Tables are created automatically.

## API (main endpoints)

| Method | Path | What |
|---|---|---|
| POST | `/api/audits` | Start audit `{url, task, steps?, conditions, use_tinyfish}` |
| GET | `/api/audits` | History |
| GET | `/api/audits/{id}` | Live progress (9 steps) + full report + before/after comparison |
| POST | `/api/audits/{id}/rerun` | Step 9 — rerun the same journey |
| GET | `/api/health` | Shows if TinyFish / LLM keys are set |
| GET/POST | `/api/demo` | Demo shop state (broken / fixed) |

## Project layout
```
accesspath/
├── setup_windows.bat / run_windows.bat / setup.sh / run.sh
├── backend/
│   ├── run.py                  start the server
│   ├── requirements.txt
│   ├── .env.example            copy to .env and add keys
│   └── app/
│       ├── main.py             FastAPI routes + demo shop + serves dashboard
│       ├── pipeline.py         the 9-step workflow
│       ├── database.py         SQLAlchemy model (SQLite or PostgreSQL)
│       ├── config.py
│       ├── vendor/axe.min.js   axe-core 4.14 (bundled, works offline)
│       └── services/
│           ├── tinyfish.py     TinyFish Agent API client
│           ├── browser_checks.py  Playwright + axe-core checks
│           └── llm.py          Gemini / OpenAI / Claude + fix library
├── frontend/                   React dashboard (no build step, React bundled)
└── demo_site/broken + fixed    test shop for the demo
```

## Troubleshooting
- **`playwright` error "Executable doesn't exist"** → run `python -m playwright install chromium` inside the venv.
- **TinyFish step says "skipped"** → key missing in `backend/.env`, or the URL is localhost.
- **Port 8000 busy** → change `PORT` in `.env`.
- **Windows: script blocked** → run the commands from the "Manual" section in Command Prompt.

## Demo websites
The 20 extra demo sites are generated by `demo_site/generate_sites.py` (brand, task, steps and which bugs each broken version has). Edit the list there and run `python demo_site/generate_sites.py` to rebuild them.

## 3D workflow figure ("Audit line")
The dashboard shows the 9-step workflow as an isometric machine: a website cartridge rides a carriage past 8 stations (URL terminal, magnifier, condition knobs, TinyFish probe, tape recorder, score dial, fix printer, report board), and station 9, a turntable with a return belt, is the retest loop. It follows the live audit: the carriage parks at the running step, each station's lamp shows that step's status, the knobs show the chosen conditions and the dial reads the real score.

- Drawn with the **anatomy** kit by Ryan (github.com/wheresryan22/anatomy, MIT licence, copy in `frontend/workflow3d/kit/LICENSE`).
- Source: `frontend/workflow3d/build.mjs`. Output: `frontend/workflow3d.js` (already built, no Node needed to run the app).
- To change it: edit `build.mjs`, then run `node frontend/workflow3d/build.mjs` (Node 20+).
- It only reads the audit data. If the script is missing, the dashboard works exactly as before.

## Design (older note)
Slate & indigo theme: soft slate page, white panels, one indigo accent; green and red only for pass and fail. The 3D audit line keeps its dark navy drawing palette. The About page (header button) explains the product. Fonts: IBM Plex Sans and IBM Plex Mono, bundled in `frontend/vendor/fonts` (SIL Open Font License) so the app works offline.

## Current version
- Frontend = the dark navy dashboard with the live 3D audit line (same look as the shared demo page), running on **real data**: type any URL and task, click **Run audit**.
- Every audit runs live: Playwright + axe-core on your machine, and TinyFish on public URLs (key in `backend/.env`).
- If a site can't be opened, the dashboard says why (wrong address, no internet, site refused, timeout).
- The demo-site panel is removed from the screen. The test sites in `demo_site/` are still served at `/demo/...` if you want to audit them by typing the URL.
