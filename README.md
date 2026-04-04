# zonebridge

zonebridge is a command-line tool to:
- analyze Fitbit intraday heart-rate data using American College of Sports Medicine (ACSM) intensity zones, aligned with CDC and AHA physical activity recommendations
- compute Fit-Mins* summaries (daily, weekly, monthly)
- help you easily track whether you are hitting the CDC-supported goal of 150-300 weekly exercise minutes
- let you customize zone thresholds to match your personal needs
- optionally sync Fitbit activities to Strava

## What Is A Fit-Min?

A Fit-Min is a weighted exercise minute used to reflect intensity:

- 1 minute in Moderate zone = 1 Fit-Min
- 1 minute in Vigorous & Max Effort zone = 2 Fit-Mins
- Light zone is for our regular activity and hence, do not add to Fit-Mins

Formula used by this app:

`Fit-Mins = Moderate + 2 x (Vigorous + Max Effort)`

Example:
- 20 min Moderate + 10 min Vigorous + 5 min Max Effort
- Fit-Mins = `20 + 2 x (10 + 5) = 50`

> **Weekly Goal: Target 150-300 Fit-Mins per week.**

## Guideline References

- Primary source used by this project for intensity zone definitions (Moderate/Vigorous/Max Effort):
  - Local copy: [ACSM Exercise Intensity Infographic (2025)](references/acsm-exercise-intensity-infographic-2025.pdf)
  - Original source URL: https://acsm.org/wp-content/uploads/2025/02/Exercise-intensity-infographic-PDF.pdf
  - CDC context: cited from CDC "How to Measure Physical Activity Intensity" page (Relative intensity section): https://www.cdc.gov/physical-activity-basics/measuring/index.html
- CDC (adult physical activity overview): https://www.cdc.gov/physical-activity-basics/guidelines/adults.html
- CDC (current intensity guidance): https://www.cdc.gov/physical-activity-basics/measuring/index.html
- American Heart Association recommendations: https://www.heart.org/en/healthy-living/fitness/fitness-basics/aha-recs-for-physical-activity-in-adults
- American Heart Association target heart rate chart: https://www.heart.org/en/healthy-living/fitness/fitness-basics/target-heart-rates

## Installation (Step-by-Step)

### Step 1: Clone and install dependencies

```bash
git clone https://github.com/hemantvirmani/ZoneBridge.git
cd ZoneBridge
python -m venv .venv
```

Activate the virtual environment:

Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Step 2: Configure credentials in `.env`

Create `.env` from template:

```bash
cp .env.example .env
```

Set your values:

```env
FITBIT_CLIENT_ID=your_fitbit_client_id
FITBIT_CLIENT_SECRET=your_fitbit_client_secret
FITBIT_REDIRECT_URI=http://localhost:8080

STRAVA_CLIENT_ID=your_strava_client_id
STRAVA_CLIENT_SECRET=your_strava_client_secret
STRAVA_REDIRECT_URI=http://localhost:8080
```

If you need help finding Fitbit/Strava credentials, see **Troubleshooting & FAQ** at the end.

### Step 3: Verify installation

```bash
python main.py --help
```

If help text prints, installation is complete.

### Step 4: Complete first-time authorization

Authenticate Fitbit:

```bash
python main.py --mode auth --provider fitbit
```

Authenticate Strava (needed only if you plan to sync):

```bash
python main.py --mode auth --provider strava
```

### Step 5: Run your first analysis

```bash
python main.py --mode analyze --days 7 --no-plot
```

### Step 6: Run your first sync as a dry run

```bash
python main.py --mode sync --provider strava --days 7 --dry-run --verbose
```

This validates conversion and filtering without uploading to Strava.

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

## Optional: Install `uv` (For `uvx`)

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
uvx --from git+https://github.com/hemantvirmani/ZoneBridge zonebridge --help
```

For reproducible runs, pin to a tag:

```bash
uvx --from git+https://github.com/hemantvirmani/ZoneBridge@v0.1.0 zonebridge --mode analyze --days 7
```

## Modes

| Mode | Purpose | Required extra flags |
| --- | --- | --- |
| `configure` | Interactive HR zone setup | none |
| `auth` | Authenticate provider | `--provider fitbit|strava` |
| `analyze` | Download Fitbit HR data and generate summaries/charts | none |
| `sync` | Download Fitbit activities and upload to Strava | `--provider strava` |

## CLI Contract (Allowed And Forbidden By Mode)

All CLI flags:
- `--mode` (required): `configure|auth|analyze|sync`
- `--provider`: `fitbit|strava`
- `--client-id`
- `--strava-client-id`
- `--strava-client-secret`
- `--days`
- `--start`
- `--end`
- `--view` (default: `daily,weekly`)
- `--no-cache`
- `--no-plot`
- `--types`
- `--exclude-types`
- `--dry-run`
- `--limit` (default: `0`)
- `--force`
- `--verbose`
- `--non-interactive`

### `--mode configure`

Allowed:
- `--mode`
- `--verbose`
- `--non-interactive`

Forbidden:
- all other flags, including `--provider`

Special rule:
- `--non-interactive` is rejected for configure because configure is interactive.

### `--mode auth`

Allowed:
- `--mode`
- `--provider` (required)
- `--client-id` (Fitbit only)
- `--strava-client-id` (Strava only)
- `--strava-client-secret` (Strava only)
- `--verbose`
- `--non-interactive`

Forbidden combos:
- `--provider fitbit` with `--strava-client-id` or `--strava-client-secret`
- `--provider strava` with `--client-id`

### `--mode analyze`

Allowed:
- `--mode`
- `--client-id`
- `--days`
- `--start`
- `--end`
- `--view`
- `--no-cache`
- `--no-plot`
- `--verbose`
- `--non-interactive`

Forbidden:
- `--provider`
- sync-only flags (`--types`, `--exclude-types`, `--dry-run`, `--limit`, `--force`, Strava credentials)

### `--mode sync`

Allowed:
- `--mode`
- `--provider` (must be `strava`)
- `--client-id`
- `--strava-client-id`
- `--strava-client-secret`
- `--days`
- `--start`
- `--end`
- `--types`
- `--exclude-types`
- `--dry-run`
- `--limit`
- `--force`
- `--no-cache`
- `--verbose`
- `--non-interactive`

Forbidden:
- `--view`
- `--no-plot`
- any flag not listed above

### Validation Rules

- unsupported flags for a selected mode are rejected
- `--days` must be `>= 1`
- `--limit` must be `>= 0`
- `--start` requires `--end`
- `--end` requires `--start`
- do not mix `--days` with `--start/--end`
- `--view` values must be a subset of: `daily`, `weekly`, `monthly`
- `--types` and `--exclude-types` cannot overlap
- if no date options are provided for analyze/sync, default window is the last 7 days

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

## Troubleshooting & FAQ

### How do I get `uvx`?

`uvx` is included with `uv`. Install `uv`, then verify:

```bash
uv --version
uvx --help
```

Install `uv`:

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### How do I get Fitbit Client ID and Secret?

1. Open `https://dev.fitbit.com/apps`
2. Create a Fitbit app (or open your existing app)
3. Copy **Client ID** and **Client Secret** into `.env`:
   - `FITBIT_CLIENT_ID=...`
   - `FITBIT_CLIENT_SECRET=...`
4. Set redirect URI in `.env`:
   - `FITBIT_REDIRECT_URI=http://localhost:8080`

### How do I get Strava Client ID and Secret?

1. Open `https://www.strava.com/settings/api`
2. Create a Strava app (or open your existing app)
3. Copy **Client ID** and **Client Secret** into `.env`:
   - `STRAVA_CLIENT_ID=...`
   - `STRAVA_CLIENT_SECRET=...`
4. Use these callback settings:
   - Authorization callback domain: `localhost`
   - Redirect URI: `http://localhost:8080`

### I get `zonebridge: command not found`

Use one of these:
- run from source: `python main.py ...`
- run via uvx: `uvx --from git+https://github.com/hemantvirmani/ZoneBridge zonebridge --help`

### Why was `.cache/strava_synced.json` not created?

`--dry-run` does not upload anything and does not write sync ledger entries.  
Run without `--dry-run` to perform actual uploads and create/update `.cache/strava_synced.json`.

### Why does rename fail with “file is being used by another process”?

A running Python process, terminal, or editor still has files open in the project folder.  
Wait for sync jobs to finish or close those processes, then retry rename.

### Why does `--start` fail without `--end`?

Current CLI contract requires date ranges to be either:
- `--days N`, or
- `--start YYYY-MM-DD --end YYYY-MM-DD`

Using only one of `--start`/`--end` is rejected.
