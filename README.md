# BenchPro — Competitive SERP Intelligence

**Track where benchdepot.com and competitors rank in Google for workbench keywords.**
**Runs entirely online. No computer needs to stay on. Free.**

Live at: **https://newtonmac.github.io/benchpro**

---

## How It Works

```
  ┌─────────────────────────────────┐
  │       GitHub (free)             │
  │                                 │
  │  GitHub Actions                 │
  │  ┌───────────────────────┐      │
  │  │ Runs 3x/day           │      │
  │  │ + on-demand via button │      │
  │  │ (headless Chromium)    │      │
  │  └──────────┬────────────┘      │
  │             ▼                   │
  │  docs/data/results.json         │
  │  docs/index.html ← GitHub Pages │
  └──────────┬──────────────────────┘
             │
    ┌────────┴────────┐
    │ You + colleague  │
    │ open dashboard   │
    │ on phone/laptop  │
    │ click "Run Now"  │
    └─────────────────┘
```

1. GitHub Actions runs a headless browser on GitHub's servers — 3× daily automatically
2. Results are saved to `docs/data/results.json` and committed
3. GitHub Pages serves the dashboard at your URL
4. You can also hit **"Run Now"** on the dashboard anytime for a fresh check
5. Password gate keeps it private

**Cost: $0.** GitHub Actions gives 2,000 free minutes/month. Each run takes ~2 min.
3 runs/day × 30 days = 90 runs = ~180 minutes. Well within the free tier.

---

## Setup (one time, ~5 minutes)

### 1. Push the code to your repo

Extract the zip into your `newtonmac/benchpro` repo and push:

```bash
git add -A
git commit -m "Initial BenchPro setup"
git push
```

### 2. Enable GitHub Pages

On github.com → your repo:
1. Go to **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: **main**, Folder: **/docs**
4. Click **Save**

Your dashboard is now live at **https://newtonmac.github.io/benchpro**

### 3. Create a GitHub token (so the "Run Now" button works)

1. Go to [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta)
2. Click **Generate new token**
3. Name: **BenchPro**, Expiration: **90 days**
4. Repository access → **Only select repositories** → choose **benchpro**
5. Permissions → Repository → **Actions: Read and write**
6. Click **Generate token** and copy it

### 4. Open the dashboard and connect

1. Visit **https://newtonmac.github.io/benchpro**
2. Enter password: **benchpro2026** (change it later — see below)
3. Click **⚙ GitHub token settings** at the bottom
4. Paste your token and save
5. Click **▶ Run now** — watch it search Google and populate the dashboard!

That's it. The 3× daily schedule is already active (GitHub Actions runs at 8am, noon, 5pm Pacific automatically).

### Optional: Change the password

```bash
python set_password.py yournewpassword
git add docs/data/auth.json
git commit -m "Update password"
git push
```

### Optional: Seed sample data first

If you want to see the dashboard populated before real data comes in:

```bash
pip install -r requirements.txt   # only needed for this step
python seed_data.py
git add docs/data/results.json
git commit -m "Add sample data"
git push
```

---

## Daily Use

1. Open **https://newtonmac.github.io/benchpro** on your phone or laptop
2. Enter the password
3. See instantly:
   - **Are we in the top 3 sponsored spots?** (green = yes, red = no)
   - **Who else is bidding on our keywords?**
   - **What positions are they getting?**
   - **When during the day do they bid heaviest?**
4. Want fresh data right now? Click **▶ Run now** — it triggers a search on GitHub's servers and updates the dashboard automatically (~2 min)

If you see benchdepot.com dropping out of the top 3 — time to bump the bid.

**Your colleague can do this too** — they just need the dashboard password and their own GitHub token.

---

## Configuration

Edit `config.py`:

```python
KEYWORDS = ["workbench", "work bench", "workbenches", "work benches"]
OUR_DOMAIN = "benchdepot.com"
SEARCH_TIMES = ["08:00", "12:00", "17:00"]
DELAY_BETWEEN_SEARCHES = 8     # seconds between keywords
DASHBOARD_PASSWORD = "benchpro2026"  # change this!
```

After changing the password, run `python set_password.py` and push.

---

## Project Structure

```
benchpro/
├── run.py                  # Main script: search → save → git push
├── scheduler.py            # Local 3x/day scheduler (alternative to Actions)
├── set_password.py         # Change dashboard password
├── seed_data.py            # Generate sample data for demo
├── config.py               # All settings
├── requirements.txt
├── .github/
│   └── workflows/
│       └── collect.yml     # GitHub Actions — runs 3x/day automatically
├── collector/
│   ├── search_runner.py    # Headless browser scraping
│   └── storage.py          # JSON data management
└── docs/                   # ← GitHub Pages serves this folder
    ├── index.html          # Dashboard UI
    ├── .nojekyll           # Tells GitHub not to use Jekyll
    ├── css/style.css
    ├── js/dashboard.js
    └── data/
        ├── results.json    # Search results (auto-updated)
        └── auth.json       # Password hash
```

---

## Notes

- **Everything runs online** — no computer needs to stay on, no local installs needed for daily use
- **Google Shopping results are excluded** — only text ads and organic
- GitHub Actions runs a real Chromium browser on their servers, so Google sees normal traffic
- 12 searches/day (4 keywords × 3 runs) is very low volume — shouldn't trigger blocks
- The GitHub token is stored in your browser's localStorage — each person saves their own
- The password is a simple client-side gate (not bank-level security, but keeps randos out)
- Data accumulates over time — the longer you run it, the better the competitor insights
- The **"Run Now"** button triggers the same GitHub Actions workflow, just on-demand
- Free GitHub tier limits: 2,000 min/month (public) or 500 min/month (private repos)
