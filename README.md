# Fitbit Heart Rate Zone Analyzer

Fetches your Fitbit intraday heart rate data and breaks it down into five training zones based on your personal HR-Max. Produces both tabular summaries and stacked bar charts for daily, weekly, and monthly views.

---

## What it tracks

| Bucket   | % of HR-Max | Description            |
|----------|-------------|------------------------|
| Resting  | < 50%       | Below training zones   |
| Zone 1   | 50 – 60%    | Light / warm-up        |
| Zone 2   | 60 – 70%    | Aerobic / fat-burn     |
| Zone 3   | 70 – 80%    | Tempo / aerobic power  |
| Zone 4   | 80 – 90%    | Threshold              |
| Zone 5   | 90 – 100%   | Max effort / anaerobic |

**Fit-Mins** = Zone 2 mins + 2 × (Zone 3 + Zone 4 + Zone 5 mins)

---

## Prerequisites

- Python 3.10+
- A Fitbit account with a **Personal** app registered at [dev.fitbit.com](https://dev.fitbit.com/apps/new)
  - App type: **Server** (enables client secret + intraday access without special approval)
  - Redirect URI: `http://localhost:8080` (or an HTTPS local IP — see [Authentication](#authentication))
  - Scopes: `heartrate activity profile`

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
```

---

## First-time setup

### 1. Configure your heart rate zones

```bash
python main.py --configure
```

Enter your age and the tool calculates HR-Max (220 − age) and sets zone boundaries automatically. You can accept the calculated values or override any boundary manually. Settings are saved to `fitbit_config.json`.

```
Fitbit HR Zone Configuration
============================================
Enter your age: 38

HR-Max = 220 − 38 = 182 bpm

Calculated zone lower bounds:
  Zone 1 : 91 bpm  (50 % of HR-Max)
  Zone 2 : 109 bpm  (60 %)
  Zone 3 : 127 bpm  (70 %)
  Zone 4 : 146 bpm  (80 %)
  Zone 5 : 164 bpm  (90 %)

Override any boundary? [y/N]:
```

### 2. Authenticate with Fitbit

```bash
python main.py --auth
```

This opens your browser, walks through the Fitbit OAuth flow, and saves tokens to `~/.fitbit_tokens.json`. Tokens are refreshed automatically on subsequent runs.

> **HTTPS redirect URI:** If your app is registered with an `https://` redirect URI (e.g. `https://192.168.x.x:8080`), the tool automatically generates a temporary self-signed certificate. Your browser will warn about it — click **Advanced → Proceed** to continue.

---

## Usage

```bash
# Last 7 days — daily + weekly views (default)
python main.py

# Custom date range
python main.py --start 2025-01-01 --end 2025-03-31

# Last 30 days, all three views
python main.py --days 30 --view daily,weekly,monthly

# Print tables only, no charts
python main.py --no-plot

# Skip cache and re-fetch everything from the API
python main.py --no-cache
```

### All options

| Flag | Description |
|------|-------------|
| `--configure` | Zone setup wizard (age → HR-Max → boundaries) |
| `--auth` | Re-authenticate with Fitbit |
| `--days N` | Analyse the last N days (default: 7) |
| `--start YYYY-MM-DD` | Start of custom date range |
| `--end YYYY-MM-DD` | End of date range (default: yesterday) |
| `--view LIST` | Comma-separated: `daily`, `weekly`, `monthly` |
| `--no-plot` | Print tables only, skip PNG charts |
| `--no-cache` | Always fetch fresh data from the API |
| `--client-id ID` | Override `FITBIT_CLIENT_ID` env var |

---

## Output

Each run prints a summary table and (unless `--no-plot`) saves PNG charts to the working directory.

**Table example:**
```
============================================================================
  DAILY SUMMARY
============================================================================
  Date             Rest    Z1     Z2     Z3     Z4     Z5   Fit-Mins
  ------------------------------------------------------------------------
  2025-03-10        892   312     98     67     42     29        334
  2025-03-11       1021   198     74     55     18      4        206
```

**Charts:** two-panel figures with a stacked zone bar on top and a Fit-Mins trend bar on the bottom, saved as:
- `fitbit_daily.png`
- `fitbit_weekly.png`
- `fitbit_monthly.png`

---

## Caching

Raw heart rate data is cached per day in `.cache/hr_YYYY-MM-DD.json`. On re-runs, cached days are loaded instantly without hitting the Fitbit API. Today's data is never cached since it is still accumulating. Use `--no-cache` to force a full re-fetch.

---

## Project structure

```
FitbitApp/
├── main.py             # CLI entry point
├── auth.py             # OAuth 2.0 PKCE + token refresh
├── api.py              # FitbitClient, intraday HR fetch, caching
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
