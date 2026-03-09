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

    # Load zone config
    if not CONFIG_FILE.exists():
        print(f"Note: {CONFIG_FILE} not found — using defaults. Run --configure to set your zones.")
    cfg = load_config()

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
