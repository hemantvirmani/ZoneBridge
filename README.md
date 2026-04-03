# Fitbit Heart Rate Zone Analyzer

Fetches your Fitbit intraday heart rate data and classifies every minute into ACSM exercise intensity zones based on your personal HR-Max. Produces tabular summaries and stacked bar charts for daily, weekly, and monthly views — so you can track whether you're hitting the recommended 150 Fit-Mins per week.

---

## Purpose

Most fitness trackers show raw heart rate or generic zones that don't map to any scientific standard. This tool applies the **ACSM (American College of Sports Medicine)** intensity framework — the same evidence-based guidelines used by exercise physiologists — to your actual Fitbit intraday data (1-minute resolution).

The key metric is **Fit-Mins**: a weighted count of exercise minutes that mirrors the CDC/ACSM physical activity guidelines:

- 1 minute of Moderate intensity = **1 Fit-Min**
- 1 minute of Vigorous or Max Effort = **2 Fit-Mins**
- 1 minute of Light activity = **0 Fit-Mins**

**Weekly goal: 150 Fit-Mins** (equivalent to 150 min moderate *or* 75 min vigorous, or any combination).

Optional add-on: the app can also sync Fitbit activity logs to your Strava account, mapping Fitbit activity types and attributes into Strava's activity format.

---

## Intensity Zones (ACSM)

| Zone | % of HR-Max | Fit-Mins/min | Description |
|------|-------------|--------------|-------------|
| Light | < 65% | 0 | Below training threshold |
| Moderate | 65 – 75% | 1 | Aerobic / fat-burn |
| Vigorous | 76 – 96% | 2 | Cardio / tempo |
| Max Effort | > 96% | 2 | Anaerobic / peak |

Zone boundaries are calculated from your HR-Max (220 − age) and saved to `fitbit_config.json`.

**Fit-Mins formula:** `Moderate + 2 × (Vigorous + Max_Effort)`

---

## Prerequisites

- Python 3.10+
- A Fitbit account with a **Personal** app registered at [dev.fitbit.com](https://dev.fitbit.com/apps/new)
  - App type: **Server** (enables client secret + intraday access without special approval)
  - Redirect URI: `http://localhost:8080` (or an HTTPS local IP — see [Authentication](#first-time-setup))
  - Scopes: `heartrate activity profile`
- (For Strava sync) A Strava API app registered at [strava.com/settings/api](https://www.strava.com/settings/api)
  - Authorization callback domain: `localhost`
  - Redirect URI: `http://localhost:8080`
  - Scopes used: `activity:write` and `activity:read_all`

---

## Installation

```bash
git clone <repo-url>
cd FitbitApp

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

Create your credentials file:

```bash
cp .env.example .env
```

Edit `.env` and fill in your app credentials:

```
FITBIT_CLIENT_ID=your_client_id
FITBIT_CLIENT_SECRET=your_client_secret
FITBIT_REDIRECT_URI=http://localhost:8080
STRAVA_CLIENT_ID=your_strava_client_id
STRAVA_CLIENT_SECRET=your_strava_client_secret
STRAVA_REDIRECT_URI=http://localhost:8080
```

---

## First-time setup

### 1. Configure your heart rate zones

```bash
python main.py --configure
```

Enter your age and the tool calculates HR-Max (220 − age) and sets ACSM zone boundaries automatically. You can accept the calculated values or override any boundary manually. Settings are saved to `fitbit_config.json`.

```
Fitbit HR Zone Configuration  (ACSM intensity framework)
========================================================
Enter your age: 47

HR-Max = 220 − 47 = 173 bpm

Calculated zone lower bounds (ACSM):
  Light      : < 112 bpm   (< 65% of HR-Max)
  Moderate   : 112 bpm      (65–75%)
  Vigorous   : 131 bpm      (76–96%)
  Max Effort : 166 bpm      (> 96%)

Override any boundary? [y/N]:
```

### 2. Authenticate with Fitbit

```bash
python main.py --auth
```

This opens your browser, walks through the Fitbit OAuth flow, and saves tokens to `~/.fitbit_tokens.json`. Tokens are refreshed automatically on subsequent runs.

> **HTTPS redirect URI:** If your app is registered with an `https://` redirect URI (e.g. `https://192.168.x.x:8080`), the tool automatically generates a temporary self-signed certificate. Your browser will warn about it — click **Advanced → Proceed** to continue.

### 3. Authenticate with Strava (for sync)

```bash
python main.py --strava-auth
```

---

## Usage

```bash
# Last 7 days — daily + weekly views (default)
python main.py

# Custom date range
python main.py --start 2025-11-28 --end 2026-03-07

# Last 30 days, all three views
python main.py --days 30 --view daily,weekly,monthly

# Print tables only, no charts
python main.py --no-plot

# Skip cache and re-fetch everything from the API
python main.py --no-cache

# Re-run on already-downloaded data (no API calls)
python main.py --start 2025-11-28 --end 2026-03-07 --view daily,weekly,monthly

# Authenticate with Strava (required once for sync)
python main.py --strava-auth

# Sync Fitbit activities to Strava
python main.py --sync-strava --days 7

# Sync a custom range, dry run first
python main.py --sync-strava --start 2026-02-01 --end 2026-02-07 --dry-run
```

### All options

| Flag | Description |
|------|-------------|
| `--configure` | Zone setup wizard (age → HR-Max → boundaries) |
| `--auth` | Re-authenticate with Fitbit |
| `--strava-auth` | Authenticate with Strava |
| `--sync-strava` | Sync Fitbit activities to Strava |
| `--days N` | Analyse the last N days (default: 7) |
| `--start YYYY-MM-DD` | Start of custom date range |
| `--end YYYY-MM-DD` | End of date range (default: yesterday) |
| `--view LIST` | Comma-separated: `daily`, `weekly`, `monthly` |
| `--no-plot` | Print tables only, skip PNG charts |
| `--no-cache` | Always fetch fresh data from the API |
| `--client-id ID` | Override `FITBIT_CLIENT_ID` env var |
| `--strava-client-id ID` | Override `STRAVA_CLIENT_ID` env var |
| `--strava-client-secret SECRET` | Override `STRAVA_CLIENT_SECRET` env var |
| `--types LIST` | Include only these Fitbit activity names |
| `--exclude-types LIST` | Exclude these Fitbit activity names |
| `--dry-run` | Convert only, do not upload |
| `--limit N` | Max number of activities to upload |
| `--force` | Upload even if already synced |
| `--verbose` | Extra logging |

---

## Output

Each run prints a summary table and (unless `--no-plot`) saves PNG charts to the working directory.

**Table example:**
```
========================================================================
  DAILY SUMMARY
========================================================================
  Date             Light  Moderate  Vigorous  Max Eff  Fit-Mins
  --------------------------------------------------------------------
  2025-03-10         892        98        67       29       323
  2025-03-11        1021        74        55        4       192
```

**Charts:** two-panel figures for each view — stacked zone bar on top, Fit-Mins bar (with per-bar value labels and weekly goal line) on the bottom — saved as:
- `fitbit_daily.png`
- `fitbit_weekly.png` — includes a 150 Fit-Mins goal line
- `fitbit_monthly.png`

---

## Caching

Raw heart rate data is cached per day in `.cache/hr_YYYY-MM-DD.json`. On re-runs, cached days are loaded instantly without hitting the Fitbit API. Today's data is never cached since it is still accumulating. Use `--no-cache` to force a full re-fetch.

Strava sync keeps a simple log in `.cache/strava_synced.json` to avoid duplicate uploads.

---

## Project structure

```
FitbitApp/
├── main.py             # CLI entry point
├── auth.py             # OAuth 2.0 PKCE + token refresh
├── api.py              # FitbitClient, intraday HR fetch, caching
├── strava.py           # Strava OAuth + activity upload
├── analysis.py         # Zone classification, Fit-Mins, aggregation
├── plots.py            # Matplotlib stacked bar + Fit-Mins charts
├── fitbit_config.json  # Zone boundaries (created by --configure)
├── .env                # Credentials (not committed)
├── .env.example        # Credential template
├── requirements.txt
└── .cache/             # Per-day HR JSON cache
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `requests` | Fitbit API calls |
| `matplotlib` | Charts |
| `numpy` | Bar chart stacking |
| `python-dotenv` | `.env` loading |
| `cryptography` | Self-signed cert for HTTPS redirect URI |
