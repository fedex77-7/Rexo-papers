# Rexo Papers — Telegram Bot (Phase 1: Bot + Admin Panel)

Powered by Rexo International. Free-to-run stack: GitHub + Render (free web
service) + Firebase Firestore (free) + Groq API (free tier, no card).

---

## What's included in Phase 1

- Telegram bot: paste questions → AI formats → PDF (watermarked preview + clean download)
- License key system: create, revoke, expiry, entry limits, usage log — all via Firestore
- In-bot admin panel (password protected): create key, list keys, revoke key, broadcast message
- Settings menu: language selection (30+ languages), theme toggle
- Contact Admin / Developer menu with your email, Instagram, Telegram

**Not included yet (Phase 2, when you're ready):**
- Telegram Mini App (a real in-app web UI instead of button/text flow)
- Separate web-based admin dashboard (right now "admin panel" = admin-only menu inside the bot)
- Payment integration for buying keys automatically
- Email broadcast (current broadcast sends via Telegram only — email needs an SMTP/Gmail API add-on, tell me if you want it)

---

## Step 1 — Create the Telegram bot

1. Open Telegram, message **@BotFather**
2. Send `/newbot`, choose a name (`Rexo Papers`) and a username ending in `bot` (e.g. `RexoPapersBot`)
3. BotFather gives you a **token** like `123456:ABC-DEF...` — save it, you'll need it as `TELEGRAM_BOT_TOKEN`
4. Send BotFather `/setdescription` and `/setabouttext` to add "Powered by Rexo International" branding if you like

## Step 2 — Get your own Telegram numeric ID (for admin access)

1. Message **@userinfobot** on Telegram
2. It replies with your numeric ID — save it as `ADMIN_TELEGRAM_IDS`

## Step 3 — Set up Firebase (free database)

1. Go to https://console.firebase.google.com → **Add project** → name it `rexo-papers`
2. Inside the project: **Build → Firestore Database → Create database** → start in production mode → pick a region close to you
3. Go to **Project settings (gear icon) → Service accounts → Generate new private key** — this downloads a JSON file
4. Open that JSON file (on your phone: Files app → open with any text/notes app, or upload it to Google Drive and open with Drive's text viewer). You'll copy 4 values out of it one at a time into Render (Step 7) — this is more reliable on mobile than copying the whole file as one block:
   - `project_id` → copy the value (no quotes)
   - `private_key_id` → copy the value
   - `client_email` → copy the value
   - `private_key` → copy the **entire value between the quotes**, including all the `\n` characters exactly as shown (it will look like one long line starting with `-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n`) — don't retype it, just select and copy so nothing gets altered

No billing needs to be enabled for this — Firestore's free (Spark) tier is enough for this use case.

## Step 4 — Get a free Groq API key

1. Go to https://console.groq.com/keys
2. Sign in with email or Google — no credit card needed
3. Click **Create API Key**, copy it — save it as `GROQ_API_KEY`

Free tier: 30 requests/minute, 14,400 requests/day, no card, no expiry — plenty for a school bot. If you ever outgrow this (many schools using it heavily), Groq's paid tier is pay-per-token and cheap, still no forced upgrade.

## Step 5 — Choose your admin password, hash it

Don't use a weak password like `admin@123` in production. Pick a strong one, then convert it to a SHA-256 hash (the bot only stores the hash, never the plain password):

```bash
python3 -c "import hashlib; print(hashlib.sha256('YOUR_PASSWORD_HERE'.encode()).hexdigest())"
```

Copy the printed hash — that's your `ADMIN_PASSWORD_HASH` env var.

## Step 6 — Push this code to GitHub

**Files to add/replace this round:** `.python-version` (new — pins Python to a stable version so the bot's async code works correctly; Render was defaulting to a too-new Python 3.14)

**Option A — no terminal, just the GitHub website:**
1. Go to https://github.com/new → name it `rexo-papers-bot` → set to **Private** → Create repository
2. Click **uploading an existing file** → drag in every file from this folder (`bot.py`, `db.py`, `ai_format.py`, `pdf_maker.py`, `languages.py`, `keep_alive.py`, `requirements.txt`, `.gitignore`) → Commit changes

**Option B — using git on your computer:**
```bash
cd rexo-bot
git init
git add .
git commit -m "Rexo Papers bot — initial version"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/rexo-papers-bot.git
git push -u origin main
```
(Create the empty repo on GitHub first via github.com/new, then run the commands above from inside this folder.)

**Do not** commit any API keys or the Firebase JSON file directly — the `.gitignore` included here already excludes `.env` and `*firebase*.json` so you don't accidentally commit secrets. Keys go in as environment variables in Step 7 only.

## Step 7 — Deploy on Render (free, using Web Service — no card needed)

Render's "Background Worker" tier requires a credit card even on the free
plan. "Web Service" doesn't — so that's what we use here. Because Render's
free Web Service expects the app to answer on a port (for its health
check), `bot.py` now also starts a tiny Flask server (`keep_alive.py`)
alongside the Telegram polling loop, just so Render sees an open port.

1. Go to https://render.com, sign up (no card required for Web Service), click **New → Web Service**
2. Connect your GitHub account, select the `rexo-papers-bot` repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python bot.py`
5. Instance type: **Free**
6. Under **Environment**, add these variables:
   - `TELEGRAM_BOT_TOKEN`
   - `ADMIN_PASSWORD_HASH`
   - `ADMIN_TELEGRAM_IDS` (your numeric ID from Step 2)
   - `FIREBASE_PROJECT_ID` (from Step 3)
   - `FIREBASE_PRIVATE_KEY_ID` (from Step 3)
   - `FIREBASE_PRIVATE_KEY` (from Step 3 — the long value with `\n` in it, pasted exactly as copied)
   - `FIREBASE_CLIENT_EMAIL` (from Step 3)
   - `GROQ_API_KEY`
7. Click **Create Web Service** — Render installs dependencies and starts the bot
8. From now on, every push to GitHub auto-redeploys

### Keeping it awake (important — free Web Services sleep after ~15 min idle)

Render's free Web Service spins down when it gets no HTTP traffic for a
while. When it's asleep, the Telegram bot stops responding until
something wakes it up. Fix: use a free "uptime pinger" to hit your
Render URL every 5–10 minutes, 24x7.

1. Once deployed, Render gives you a URL like `https://rexo-papers-bot.onrender.com`
2. Go to https://uptimerobot.com → sign up free → **Add New Monitor**
3. Monitor type: HTTP(s), paste your Render URL, check interval: 5 minutes
4. Save — UptimeRobot will now ping your bot's server every 5 minutes, keeping it awake

This adds a small ongoing dependency (UptimeRobot), but it's free and
reliable, and needs no card.

## Step 8 — Try it

1. Open your bot on Telegram, send `/start`
2. Send `/admin`, enter your password
3. Tap **Create Key**, send e.g. `10 30 standard My First School` (10 papers, 30 days)
4. Copy that key, go back to `/start` → **New Question Paper**, paste the key when asked
5. Send exam details, then paste some questions — you'll get a watermarked preview, then a clean PDF

---

## Ongoing cost reality check

- Firebase Firestore: free at this scale
- Render free Web Service: free, but spins down after ~15 min idle — the UptimeRobot pinger in Step 7 keeps it awake. If it still feels slow to respond, Render's $7/mo starter tier removes the sleep entirely.
- Groq API: free tier, no card, 30 requests/min & 14,400/day — enough for a school or a handful of schools

If usage grows a lot (many schools, many papers/day), some of these will need small paid upgrades — but you can start and test the entire system at ₹0.

---

## Next steps — tell me if you want any of these added

- Key expiry reminders sent automatically before a key runs out
- CSV export of usage logs
- Email broadcast (needs an email-sending service — I can wire up Gmail API or a free service like Resend)
- Telegram Mini App front-end (a proper in-app web form instead of typing details message by message)
- Web-based admin dashboard (outside Telegram)
- A template you attach — send me the sample question paper image/PDF and I'll match its exact layout in `pdf_maker.py`
