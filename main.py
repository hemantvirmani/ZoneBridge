"""
Fitbit Heart Rate Zone Analyzer
================================
Fetches intraday heart rate data from the Fitbit Web API and produces:
  • Zone minutes (Resting + Zone1–5) per day / week / month
  • Fit-Mins metric  =  Zone2 mins + 2 × (Zone3 + Zone4 + Zone5 mins)
  • Stacked bar charts saved as PNG

Zone boundaries are stored in fitbit_config.json (run --configure to set up).

Usage examples
--------------
  # First-time zone setup — asks age, calculates HR-Max, sets zone boundaries
  python main.py --configure

  # First-time Fitbit authentication
  python main.py --auth

  # Last 7 days (default), daily + weekly plots
  python main.py

  # Custom date range
  python main.py --start 2025-01-01 --end 2025-01-31

  # 30 days, weekly + monthly views
  python main.py --days 30 --view weekly,monthly
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from api import FitbitClient
from analysis import (
    ZoneConfig, load_config, save_config, CONFIG_FILE,
    daily_summary, weekly_summary, monthly_summary,
)
from plots import plot_daily, plot_weekly, plot_monthly
from strava import StravaClient

load_dotenv()


# ---------------------------------------------------------------------------
# Zone configuration wizard
# ---------------------------------------------------------------------------

def run_configure() -> ZoneConfig:
    """Interactive wizard: age → HR-Max → ACSM zone boundaries with optional override."""
    print("\nFitbit HR Zone Configuration  (ACSM intensity framework)")
    print("=" * 56)

    age_str = input("Enter your age: ").strip()
    try:
        age = int(age_str)
    except ValueError:
        print("Error: age must be a whole number.")
        sys.exit(1)

    hr_max = 220 - age
    print(f"\nHR-Max = 220 − {age} = {hr_max} bpm")

    moderate_min   = round(hr_max * 0.65)
    vigorous_min   = round(hr_max * 0.76)
    max_effort_min = round(hr_max * 0.96)

    print("\nCalculated zone lower bounds (ACSM):")
    print(f"  Light      : < {moderate_min} bpm   (< 65% of HR-Max)")
    print(f"  Moderate   : {moderate_min} bpm      (65–75%)")
    print(f"  Vigorous   : {vigorous_min} bpm      (76–96%)")
    print(f"  Max Effort : {max_effort_min} bpm     (> 96%)")

    override = input("\nOverride any boundary? [y/N]: ").strip().lower()
    if override == "y":
        def _ask(label: str, current: int) -> int:
            raw = input(f"  {label} [{current}]: ").strip()
            if not raw:
                return current
            try:
                return int(raw)
            except ValueError:
                print(f"  Invalid — keeping {current}")
                return current

        moderate_min   = _ask("Moderate lower bound (65%)", moderate_min)
        vigorous_min   = _ask("Vigorous lower bound (76%)", vigorous_min)
        max_effort_min = _ask("Max Effort lower bound (96%)", max_effort_min)

    cfg = ZoneConfig(
        moderate_min=moderate_min,
        vigorous_min=vigorous_min,
        max_effort_min=max_effort_min,
    )
    save_config(cfg, age=age, hr_max=hr_max)

    print(f"\nConfiguration saved to {CONFIG_FILE}")
    print(f"  Light      : < {cfg.moderate_min} bpm              (< 65%)")
    print(f"  Moderate   : {cfg.moderate_min} – {cfg.vigorous_min - 1} bpm  (65–75%)")
    print(f"  Vigorous   : {cfg.vigorous_min} – {cfg.max_effort_min - 1} bpm  (76–96%)")
    print(f"  Max Effort : {cfg.max_effort_min}+ bpm              (> 96%)")
    return cfg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fitbit_zones",
        description="Fitbit Heart Rate Zone Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Setup modes
    p.add_argument("--configure", action="store_true",
                   help="Set up HR zone boundaries from age/HR-Max and exit")
    p.add_argument("--auth", action="store_true",
                   help="(Re-)authenticate with Fitbit and exit")
    p.add_argument("--client-id", metavar="ID",
                   help="Fitbit OAuth Client ID (or set FITBIT_CLIENT_ID env var)")

    # Strava sync modes
    p.add_argument("--strava-auth", action="store_true",
                   help="Authenticate with Strava and exit")
    p.add_argument("--sync-strava", action="store_true",
                   help="Sync Fitbit activities to Strava")
    p.add_argument("--strava-client-id", metavar="ID",
                   help="Strava Client ID (or set STRAVA_CLIENT_ID env var)")
    p.add_argument("--strava-client-secret", metavar="SECRET",
                   help="Strava Client Secret (or set STRAVA_CLIENT_SECRET env var)")

    # Date range
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--days", type=int, default=7, metavar="N",
                     help="Analyse the last N days (default: 7)")
    grp.add_argument("--start", metavar="YYYY-MM-DD",
                     help="Start date (requires --end)")
    p.add_argument("--end", metavar="YYYY-MM-DD",
                   help="End date (default: yesterday)")

    # Output
    p.add_argument("--view", default="daily,weekly",
                   help="Comma-separated list of views: daily, weekly, monthly (default: daily,weekly)")
    p.add_argument("--no-cache", action="store_true",
                   help="Bypass local cache and always fetch fresh data")
    p.add_argument("--no-plot", action="store_true",
                   help="Print tables only, skip plotting")
    p.add_argument("--types", metavar="LIST",
                   help="Comma-separated Fitbit activity names to include (e.g. Run,Ride,Walk)")
    p.add_argument("--exclude-types", metavar="LIST",
                   help="Comma-separated Fitbit activity names to exclude")
    p.add_argument("--dry-run", action="store_true",
                   help="Fetch and convert only, do not upload to Strava")
    p.add_argument("--limit", type=int, default=0, metavar="N",
                   help="Max number of activities to upload (0 = no limit)")
    p.add_argument("--force", action="store_true",
                   help="Upload even if activity appears already synced")
    p.add_argument("--verbose", action="store_true",
                   help="Verbose logging")

    return p


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

def _print_table(title: str, data: dict[str, dict], key_header: str):
    print(f"\n{'='*72}")
    print(f"  {title}")
    print(f"{'='*72}")
    print(f"  {key_header:<14}  {'Light':>6}  {'Moderate':>8}  {'Vigorous':>8}  {'Max Eff':>7}  {'Fit-Mins':>8}")
    print("  " + "-" * 68)
    for key in sorted(data.keys()):
        s = data[key]
        print(
            f"  {key:<14}  "
            f"{s['light']:>6}  "
            f"{s['moderate']:>8}  "
            f"{s['vigorous']:>8}  "
            f"{s['max_effort']:>7}  "
            f"{s['fit_mins']:>8}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SYNC_LOG = Path(".cache") / "strava_synced.json"


def _ensure_cache_dir():
    Path(".cache").mkdir(exist_ok=True)


def _load_synced() -> dict[str, dict]:
    if SYNC_LOG.exists():
        return json.loads(SYNC_LOG.read_text())
    return {}


def _save_synced(data: dict[str, dict]) -> None:
    _ensure_cache_dir()
    SYNC_LOG.write_text(json.dumps(data, indent=2))


def _normalize_type_list(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {t.strip().lower() for t in raw.split(",") if t.strip()}


def _fitbit_to_strava_type(name: str) -> str:
    n = name.lower()
    if "run" in n:
        return "Run"
    if "walk" in n:
        return "Walk"
    if "hike" in n:
        return "Hike"
    if "ride" in n or "bike" in n or "cycling" in n:
        return "Ride"
    if "swim" in n:
        return "Swim"
    if "elliptical" in n:
        return "Elliptical"
    if "row" in n:
        return "Rowing"
    if "yoga" in n:
        return "Yoga"
    if "weight" in n or "strength" in n:
        return "WeightTraining"
    if "stair" in n or "stepper" in n:
        return "StairStepper"
    return "Workout"


def _distance_to_meters(distance: float | int | None, unit: str | None) -> float | None:
    if distance is None:
        return None
    if unit is None:
        return None
    u = unit.strip().lower()
    if u in ("kilometer", "kilometers", "km"):
        return float(distance) * 1000.0
    if u in ("mile", "miles", "mi"):
        return float(distance) * 1609.344
    if u in ("meter", "meters", "m"):
        return float(distance)
    if u in ("yard", "yards", "yd"):
        return float(distance) * 0.9144
    return None


def _extract_activity(detail: dict) -> dict:
    if "activity" in detail and isinstance(detail["activity"], dict):
        return detail["activity"]
    if "activities" in detail and isinstance(detail["activities"], list) and detail["activities"]:
        if isinstance(detail["activities"][0], dict):
            return detail["activities"][0]
    return detail


def _activity_to_strava_payload(detail: dict) -> dict | None:
    activity = _extract_activity(detail)
    name = (
        activity.get("activityName")
        or activity.get("name")
        or "Fitbit Activity"
    )
    start_time = activity.get("startTime") or activity.get("startDate")
    if not start_time:
        print("  Warning: missing start time; skipping activity.")
        return None

    duration = activity.get("duration")
    if duration is None:
        print("  Warning: missing duration; skipping activity.")
        return None
    duration_sec = int(round(float(duration) / 1000.0)) if float(duration) > 10000 else int(round(float(duration)))
    if duration_sec <= 0:
        print("  Warning: invalid duration; skipping activity.")
        return None

    distance = activity.get("distance")
    distance_unit = activity.get("distanceUnit") or activity.get("distanceUnitLabel")
    distance_m = _distance_to_meters(distance, distance_unit)

    payload = {
        "name": name,
        "type": _fitbit_to_strava_type(name),
        "start_date_local": start_time,
        "elapsed_time": duration_sec,
        "external_id": str(activity.get("logId") or activity.get("activityLogId") or activity.get("id") or ""),
        "description": "Imported from Fitbit",
    }
    if distance_m is not None:
        payload["distance"] = distance_m
    calories = activity.get("calories")
    if calories is not None:
        payload["calories"] = int(calories)
    return payload

def main():
    parser = build_parser()
    args = parser.parse_args()

    # --configure mode: wizard only
    if args.configure:
        run_configure()
        return

    # Resolve credentials
    client_id     = args.client_id or os.getenv("FITBIT_CLIENT_ID", "").strip()
    client_secret = os.getenv("FITBIT_CLIENT_SECRET", "").strip()
    redirect_uri  = os.getenv("FITBIT_REDIRECT_URI", "https://192.168.86.39:8080").strip()

    if not client_id:
        client_id = input("Enter your Fitbit Client ID: ").strip()
    if not client_id:
        print("Error: Fitbit Client ID is required.")
        sys.exit(1)

    # --auth mode: authenticate and exit
    if args.auth:
        from auth import authorize
        authorize(client_id, client_secret, redirect_uri)
        return

    # --strava-auth mode: authenticate and exit
    if args.strava_auth:
        strava_client_id = args.strava_client_id or os.getenv("STRAVA_CLIENT_ID", "").strip()
        strava_client_secret = args.strava_client_secret or os.getenv("STRAVA_CLIENT_SECRET", "").strip()
        strava_redirect_uri = os.getenv("STRAVA_REDIRECT_URI", "http://localhost:8080").strip()
        if not strava_client_id:
            strava_client_id = input("Enter your Strava Client ID: ").strip()
        if not strava_client_secret:
            strava_client_secret = input("Enter your Strava Client Secret: ").strip()
        if not strava_client_id or not strava_client_secret:
            print("Error: Strava Client ID and Secret are required.")
            sys.exit(1)
        StravaClient(strava_client_id, strava_client_secret, strava_redirect_uri)._token()
        return

    # Load zone config
    # Date range
    yesterday = date.today() - timedelta(days=1)
    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
        end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else yesterday
    else:
        end = yesterday
        start = end - timedelta(days=args.days - 1)

    if start > end:
        print("Error: start date must be before end date.")
        sys.exit(1)

    if args.sync_strava:
        strava_client_id = args.strava_client_id or os.getenv("STRAVA_CLIENT_ID", "").strip()
        strava_client_secret = args.strava_client_secret or os.getenv("STRAVA_CLIENT_SECRET", "").strip()
        strava_redirect_uri = os.getenv("STRAVA_REDIRECT_URI", "http://localhost:8080").strip()

        if not strava_client_id:
            strava_client_id = input("Enter your Strava Client ID: ").strip()
        if not strava_client_secret:
            strava_client_secret = input("Enter your Strava Client Secret: ").strip()
        if not strava_client_id or not strava_client_secret:
            print("Error: Strava Client ID and Secret are required.")
            sys.exit(1)

        print("\nFitbit -> Strava sync")
        print(f"  Date range  : {start}  ->  {end}  ({(end - start).days + 1} days)")
        print()

        client = FitbitClient(client_id, client_secret, redirect_uri)
        strava = StravaClient(strava_client_id, strava_client_secret, strava_redirect_uri)

        activities = client.get_activities_range(start, end, use_cache=not args.no_cache)
        if args.verbose:
            print(f"Fetched {len(activities)} Fitbit activities.")

        include_types = _normalize_type_list(args.types)
        exclude_types = _normalize_type_list(args.exclude_types)

        synced = _load_synced()
        uploaded = 0

        for act in activities:
            name = act.get("activityName") or act.get("name") or ""
            name_key = name.lower()
            if include_types and name_key not in include_types:
                continue
            if exclude_types and name_key in exclude_types:
                continue

            log_id = act.get("logId") or act.get("activityLogId") or act.get("id")
            if not log_id:
                print("  Warning: missing logId; skipping activity.")
                continue

            if not args.force and str(log_id) in synced:
                if args.verbose:
                    print(f"  Skipping already synced: {name} ({log_id})")
                continue

            detail = client.get_activity_detail(int(log_id))
            payload = _activity_to_strava_payload(detail)
            if payload is None:
                continue

            if args.dry_run:
                print(f"  Dry run: {payload['name']} ({payload['type']}) at {payload['start_date_local']}")
            else:
                resp = strava.create_activity(payload)
                synced[str(log_id)] = {
                    "strava_id": resp.get("id"),
                    "name": payload["name"],
                    "start_date_local": payload["start_date_local"],
                }
                _save_synced(synced)
                print(f"  Uploaded: {payload['name']} -> Strava ID {resp.get('id')}")
                uploaded += 1

            if args.limit and uploaded >= args.limit:
                break

        if args.dry_run:
            print("Dry run completed.")
        else:
            print(f"Sync completed. Uploaded {uploaded} activities.")
        return

    # Load zone config (only for HR analysis flow)
    if not CONFIG_FILE.exists():
        print(f"Note: {CONFIG_FILE} not found -- using defaults. Run --configure to set your zones.")
    cfg = load_config()

    print(f"\nFitbit Heart Rate Zone Analyzer  (ACSM intensity framework)")
    print(f"  Date range  : {start}  →  {end}  ({(end - start).days + 1} days)")
    print(f"  Light       : < {cfg.moderate_min} bpm              (< 65%)")
    print(f"  Moderate    : {cfg.moderate_min} – {cfg.vigorous_min - 1} bpm  (65–75%)")
    print(f"  Vigorous    : {cfg.vigorous_min} – {cfg.max_effort_min - 1} bpm  (76–96%)")
    print(f"  Max Effort  : {cfg.max_effort_min}+ bpm              (> 96%)")
    print(f"  Fit-Mins    : Moderate + 2×(Vigorous + Max Effort)  [goal: 150/week]")
    print()

    # Fetch (uses .cache/ by default — already-downloaded days are not re-fetched)
    client = FitbitClient(client_id, client_secret, redirect_uri)
    print("Fetching data…")
    hr_data = client.get_hr_range(start, end, use_cache=not args.no_cache)

    # Analyse
    daily = daily_summary(hr_data, cfg)

    views = [v.strip().lower() for v in args.view.split(",")]

    # ── Daily ──────────────────────────────────────────────────────────
    if "daily" in views:
        _print_table("DAILY SUMMARY", daily, "Date")
        if not args.no_plot:
            plot_daily(daily, cfg)

    # ── Weekly ─────────────────────────────────────────────────────────
    if "weekly" in views:
        weekly = weekly_summary(daily)
        _print_table("WEEKLY SUMMARY", weekly, "ISO Week")
        if not args.no_plot:
            plot_weekly(weekly, cfg)

    # ── Monthly ────────────────────────────────────────────────────────
    if "monthly" in views:
        monthly = monthly_summary(daily)
        _print_table("MONTHLY SUMMARY", monthly, "Month")
        if not args.no_plot:
            plot_monthly(monthly, cfg)


if __name__ == "__main__":
    main()
