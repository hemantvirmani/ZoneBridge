# zonebridge

zonebridge is a command-line tool to:
- analyze Fitbit intraday heart-rate data using American College of Sports Medicine (ACSM) intensity zones, aligned with CDC and AHA physical activity recommendations
- compute Fit-Mins and total exercise-minute summaries (daily, weekly, monthly)
- help you easily track whether you are hitting the CDC-supported goal of 150-300 weekly exercise minutes
- let you customize zone thresholds to match your personal needs
- optionally sync Fitbit activities to Strava

## What Is A Fit-Min?

A Fit-Min is a weighted exercise minute used to reflect intensity:

- 1 minute in Moderate zone = 1 Fit-Min
- 1 minute in Vigorous & Max Effort zone = 2 Fit-Mins
- Light zone is for our regular activity and hence, do not add to Fit-Mins

Assumption used by this app:
- the app assumes you are exercising when your heart rate is in Moderate, Vigorous, or Max Effort zones, and counts those minutes as exercise time

Formula used by this app:

`Fit-Mins = Moderate + 2 x (Vigorous + Max Effort)`

Example:
- 20 min Moderate + 10 min Vigorous + 5 min Max Effort
- Fit-Mins = `20 + 2 x (10 + 5) = 50`

> **Weekly Goal: Target 150-300 Fit-Mins per week.**

Report outputs:
- tables show `Moderate`, `Vigorous`, `Max Eff`, `Fit-Mins`, and `Exercise`
- `Light` minutes are intentionally excluded from report tables and plots
- `Exercise` is total Fitbit activity duration (minutes) for the period

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

## Examples

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
  analysis.py      # Zone/Fit-Mins + exercise-minute aggregations
  plots.py         # chart generation (exercise zones + Fit-Mins/Exercise Mins)
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

### How do I update heart-rate zone thresholds?

You have two options:

1. Recommended: run the interactive configurator

```bash
zonebridge --mode configure
```

This rewrites `fitbit_config.json` with your selected thresholds.

2. Manual edit: update `fitbit_config.json` directly

Example:

```json
{
  "moderate_min": 117,
  "vigorous_min": 137,
  "max_effort_min": 173
}
```

Rules:
- values are lower bounds in bpm
- keep ascending order: `moderate_min < vigorous_min < max_effort_min`
- changes apply to the next analyze/sync run automatically

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

### Give me quick list of commands that are run regularly?

* Weekly HR zone analysis (last 30 days)

```powershell
python .\main.py --mode analyze --days 30 --view weekly
```

* Sync Fitbit activities to Strava (last 30 days)

```powershell
python .\main.py --mode sync --days 30 --provider strava
```
