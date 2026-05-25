# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Setup

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Unix

pip install -r requirements.txt

# Copy and fill in credentials
cp .env.example .env
# Edit .env: set FITBIT_CLIENT_ID, FITBIT_CLIENT_SECRET, FITBIT_REDIRECT_URI
```

## Running the App

```bash
# First-time zone setup — asks age, computes HR-Max, sets zone boundaries
python main.py --configure

# First-time Fitbit authentication (opens browser, waits for callback)
python main.py --auth

# Default: last 7 days, daily + weekly views, with plots
python main.py

# Custom date range
python main.py --start 2025-01-01 --end 2025-01-31

# Last 30 days, all views, no plots
python main.py --days 30 --view daily,weekly,monthly --no-plot

# Force fresh API fetch (bypass .cache/)
python main.py --no-cache
```

## Architecture

The pipeline is: **auth → api → analysis → plots**, with `main.py` wiring them together via argparse.

**`auth.py`** — OAuth 2.0 Authorization Code + PKCE + Client Secret flow. Spawns a local HTTPS callback server using a temporary self-signed cert (via `cryptography`) when the redirect URI is `https://`. Tokens are persisted to `~/.fitbit_tokens.json` and auto-refreshed 5 minutes before expiry.

**`api.py`** — `FitbitClient` class. Fetches intraday HR data at 1-minute resolution one day at a time (Fitbit API limit). Caches responses to `.cache/hr_YYYY-MM-DD.json`; never caches today's data. Handles 429 rate-limit responses by sleeping until the reset time.

**`analysis.py`** — Pure data transformation, no I/O. `ZoneConfig` dataclass holds zone boundary BPM values. `daily_summary()` consumes raw API data and returns per-day zone minute counts + Fit-Mins. `weekly_summary()` and `monthly_summary()` aggregate daily stats by ISO week (`YYYY-Wnn`) and month (`YYYY-MM`).

**`plots.py`** — Matplotlib charts. Each public function (`plot_daily`, `plot_weekly`, `plot_monthly`) produces a 2-panel figure: stacked zone bar chart on top, Fit-Mins bars + trend line on bottom. Saves to a PNG in the working directory and calls `plt.show()`.

## Key Domain Details

- **Fit-Mins** = `Zone2_mins + 2 × (Zone3_mins + Zone4_mins + Zone5_mins)`
- **5 zones** based on HR-Max (= 220 − age): Z1 50–60%, Z2 60–70%, Z3 70–80%, Z4 80–90%, Z5 90–100%; plus a **Resting** bucket for < 50%
- Zone boundaries live in `fitbit_config.json` (created by `--configure`); absent file → `ZoneConfig` dataclass defaults
- All zone thresholds are stored as lower bounds (inclusive); each zone runs up to the next zone's lower bound
- The app is registered as a **Server** type on Fitbit (has client secret → uses Basic Auth header on token exchange)
- Fitbit intraday access requires **Personal** app type; rate limit is 150 req/hr
- Cache is stored in `.cache/` relative to the working directory (not the script location); past days are never re-fetched unless `--no-cache` is passed
- Tokens are stored at `~/.fitbit_tokens.json` (user home directory)
