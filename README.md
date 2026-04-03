# zonebridge

zonebridge is a command-line tool to:
- analyze Fitbit intraday heart-rate data using ACSM intensity zones
- compute Fit-Mins summaries (daily, weekly, monthly)
- optionally sync Fitbit activities to Strava

## Quick Start

```bash
git clone <repo-url>
cd zonebridge
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with your credentials:

```env
FITBIT_CLIENT_ID=your_fitbit_client_id
FITBIT_CLIENT_SECRET=your_fitbit_client_secret
FITBIT_REDIRECT_URI=http://localhost:8080

STRAVA_CLIENT_ID=your_strava_client_id
STRAVA_CLIENT_SECRET=your_strava_client_secret
STRAVA_REDIRECT_URI=http://localhost:8080
```

## How To Get Strava Client ID And Secret

1. Open `https://www.strava.com/settings/api`
2. Create an app (or open your existing app)
3. Copy the values shown as **Client ID** and **Client Secret**
4. Add them to your `.env` as:
   - `STRAVA_CLIENT_ID=...`
   - `STRAVA_CLIENT_SECRET=...`

If Strava asks for callback details, use:
- Authorization callback domain: `localhost`
- Redirect URI: `http://localhost:8080`

## Command Model

The CLI is mode-based:

```bash
zonebridge --mode <configure|auth|analyze|sync> [options]
```

If you do not have a `zonebridge` launcher yet, run the same command with `python main.py`.

Example:

```bash
python main.py --mode analyze --days 7
```

## Install `uv` (Needed For `uvx`)

`uvx` comes with `uv`. Install `uv` first:

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify installation:

```bash
uv --version
uvx --help
```

## Run From GitHub With `uvx` (No Install)

You can run zonebridge directly from this repo without installing it permanently:

```bash
uvx --from git+https://github.com/hemantvirmani/zonebridge zonebridge --help
```

For reproducible runs, pin to a tag:

```bash
uvx --from git+https://github.com/hemantvirmani/zonebridge@v0.1.0 zonebridge --mode analyze --days 7
```

## Modes

| Mode | Purpose | Required extra flags |
| --- | --- | --- |
| `configure` | Interactive HR zone setup | none |
| `auth` | Authenticate provider | `--provider fitbit|strava` |
| `analyze` | Download Fitbit HR data and generate summaries/charts | none |
| `sync` | Download Fitbit activities and upload to Strava | `--provider strava` |

## Options by Mode

### Configure

```bash
zonebridge --mode configure
```

Allowed options:
- `--verbose`

### Auth

Fitbit auth:

```bash
zonebridge --mode auth --provider fitbit [--client-id ID]
```

Strava auth:

```bash
zonebridge --mode auth --provider strava [--strava-client-id ID] [--strava-client-secret SECRET]
```

Allowed options:
- `--provider`
- `--client-id` (Fitbit only)
- `--strava-client-id` (Strava only)
- `--strava-client-secret` (Strava only)
- `--verbose`
- `--non-interactive`

### Analyze

```bash
zonebridge --mode analyze [date options] [output options]
```

Date options (choose one style):
- `--days N`
- `--start YYYY-MM-DD --end YYYY-MM-DD`

Output options:
- `--view daily,weekly,monthly`
- `--no-cache`
- `--no-plot`
- `--client-id`
- `--verbose`
- `--non-interactive`

### Sync

```bash
zonebridge --mode sync --provider strava [date options] [sync options]
```

Date options (choose one style):
- `--days N`
- `--start YYYY-MM-DD --end YYYY-MM-DD`

Sync options:
- `--types LIST`
- `--exclude-types LIST`
- `--dry-run`
- `--limit N`
- `--force`
- `--no-cache`
- `--client-id`
- `--strava-client-id`
- `--strava-client-secret`
- `--verbose`
- `--non-interactive`

## Validation Rules

- `--days` must be `>= 1`
- `--limit` must be `>= 0`
- `--start` requires `--end`
- `--end` requires `--start`
- do not mix `--days` with `--start/--end`
- analyze views must be from: `daily`, `weekly`, `monthly`
- in sync mode, `--types` and `--exclude-types` cannot overlap
- configure mode is interactive and cannot run with `--non-interactive`

## Data Download Behavior

Fitbit data is downloaded in these modes:

- `--mode analyze`: downloads intraday HR data via `FitbitClient.get_hr_range(...)`
- `--mode sync --provider strava`: downloads Fitbit activity logs/details via
  `FitbitClient.get_activities_range(...)` and `FitbitClient.get_activity_detail(...)`

Auth mode only performs OAuth token flows. It does not download analysis/activity data.

## Many Examples

### Setup and Authentication

```bash
# configure HR zones interactively
zonebridge --mode configure

# auth Fitbit using env vars
zonebridge --mode auth --provider fitbit

# auth Fitbit with explicit client id override
zonebridge --mode auth --provider fitbit --client-id 23ABCX

# auth Strava using env vars
zonebridge --mode auth --provider strava

# auth Strava with explicit credentials
zonebridge --mode auth --provider strava --strava-client-id 12345 --strava-client-secret secret123
```

### Analyze Examples

```bash
# default window (last 7 days), default views (daily,weekly)
zonebridge --mode analyze

# explicit 14-day analysis
zonebridge --mode analyze --days 14

# custom date range
zonebridge --mode analyze --start 2026-01-01 --end 2026-01-31

# monthly only
zonebridge --mode analyze --days 90 --view monthly

# daily + weekly + monthly
zonebridge --mode analyze --days 45 --view daily,weekly,monthly

# table output only (skip PNG plots)
zonebridge --mode analyze --days 30 --no-plot

# force fresh Fitbit API fetch
zonebridge --mode analyze --days 7 --no-cache

# fail instead of prompting for missing creds
zonebridge --mode analyze --days 7 --non-interactive
```

### Sync Examples

```bash
# sync last 7 days
zonebridge --mode sync --provider strava --days 7

# sync custom date range
zonebridge --mode sync --provider strava --start 2026-02-01 --end 2026-02-07

# dry run (no upload)
zonebridge --mode sync --provider strava --days 14 --dry-run

# only upload Run and Walk
zonebridge --mode sync --provider strava --days 30 --types Run,Walk

# exclude Yoga and Walk
zonebridge --mode sync --provider strava --days 30 --exclude-types Yoga,Walk

# upload at most 10 activities
zonebridge --mode sync --provider strava --days 30 --limit 10

# re-upload even if already in local synced log
zonebridge --mode sync --provider strava --days 30 --force

# force fresh activity fetch and verbose logging
zonebridge --mode sync --provider strava --days 7 --no-cache --verbose

# full explicit credentials in one command
zonebridge --mode sync --provider strava --days 7 --client-id FITBIT123 --strava-client-id STRAVA123 --strava-client-secret STRAVASECRET
```

### Same commands with python main.py

```bash
python main.py --mode analyze --days 7
python main.py --mode auth --provider fitbit
python main.py --mode sync --provider strava --days 7 --dry-run
```

## Activity Mapping (Fitbit -> Strava)

Type mapping and payload conversion live in `sync_adapter.py`.

Current mapping is heuristic and many-to-one, for example:
- names containing `run` -> `Run`
- `ride|bike|cycling` -> `Ride`
- unknown names -> `Workout`

Distance is converted to meters from km/mi/m/yd when possible.

## Cache and Files

- HR cache: `.cache/hr_YYYY-MM-DD.json`
- activity cache: `.cache/activities_<start>_<end>.json`
- sync log: `.cache/strava_synced.json`
- zone config: `fitbit_config.json`
- Fitbit tokens: `~/.fitbit_tokens.json`
- Strava tokens: `~/.strava_tokens.json`

## Project Structure

```text
zonebridge/
  main.py          # CLI and mode routing
  fitbit_client.py # Fitbit client
  auth.py          # Fitbit OAuth helpers
  strava_client.py # Strava OAuth + upload client
  sync_adapter.py  # Fitbit->Strava mapping and payload conversion
  analysis.py      # Zone/Fit-Mins calculations
  plots.py         # chart generation
  README.md
```

## Dependencies

- `requests`
- `matplotlib`
- `numpy`
- `python-dotenv`
- `cryptography`

