"""
Fitbit Heart Rate Zone Analyzer

Main CLI entrypoint for configuring zones, authenticating providers,
analyzing heart-rate zones, and syncing Fitbit activities to Strava.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from analysis import (
    CONFIG_FILE,
    ZoneConfig,
    daily_summary,
    load_config,
    monthly_summary,
    save_config,
    weekly_summary,
)
from fitbit_client import FitbitClient
from plots import plot_daily, plot_monthly, plot_weekly
from strava_client import StravaClient
from sync_adapter import activity_to_strava_payload, normalize_type_list

load_dotenv()

SYNC_LOG = Path(".cache") / "strava_synced.json"
ALLOWED_VIEWS = {"daily", "weekly", "monthly"}


def run_configure() -> ZoneConfig:
    """Interactive wizard: age -> HR-Max -> ACSM zone boundaries with optional override."""
    print("\nFitbit HR Zone Configuration (ACSM intensity framework)")
    print("=" * 56)

    age_str = input("Enter your age: ").strip()
    try:
        age = int(age_str)
    except ValueError:
        raise ValueError("age must be a whole number")

    hr_max = 220 - age
    print(f"\nHR-Max = 220 - {age} = {hr_max} bpm")

    moderate_min = round(hr_max * 0.65)
    vigorous_min = round(hr_max * 0.76)
    max_effort_min = round(hr_max * 0.96)

    print("\nCalculated zone lower bounds (ACSM):")
    print(f"  Light      : < {moderate_min} bpm   (< 65% of HR-Max)")
    print(f"  Moderate   : {moderate_min} bpm      (65-75%)")
    print(f"  Vigorous   : {vigorous_min} bpm      (76-96%)")
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
                print(f"  Invalid input, keeping {current}")
                return current

        moderate_min = _ask("Moderate lower bound (65%)", moderate_min)
        vigorous_min = _ask("Vigorous lower bound (76%)", vigorous_min)
        max_effort_min = _ask("Max Effort lower bound (96%)", max_effort_min)

    cfg = ZoneConfig(
        moderate_min=moderate_min,
        vigorous_min=vigorous_min,
        max_effort_min=max_effort_min,
    )
    save_config(cfg, age=age, hr_max=hr_max)

    print(f"\nConfiguration saved to {CONFIG_FILE}")
    print(f"  Light      : < {cfg.moderate_min} bpm              (< 65%)")
    print(f"  Moderate   : {cfg.moderate_min} - {cfg.vigorous_min - 1} bpm  (65-75%)")
    print(f"  Vigorous   : {cfg.vigorous_min} - {cfg.max_effort_min - 1} bpm  (76-96%)")
    print(f"  Max Effort : {cfg.max_effort_min}+ bpm              (> 96%)")
    return cfg


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fitbitapp",
        description="Fitbit HR analysis and Fitbit -> Strava sync",
    )

    parser.add_argument(
        "--mode",
        required=True,
        choices=["configure", "auth", "analyze", "sync"],
        help="Run mode: configure, auth, analyze, or sync.",
    )
    parser.add_argument(
        "--provider",
        choices=["fitbit", "strava"],
        help="Provider for auth/sync modes.",
    )

    parser.add_argument(
        "--client-id",
        metavar="ID",
        help="Fitbit OAuth Client ID (or FITBIT_CLIENT_ID env var).",
    )
    parser.add_argument(
        "--strava-client-id",
        metavar="ID",
        help="Strava Client ID (or STRAVA_CLIENT_ID env var).",
    )
    parser.add_argument(
        "--strava-client-secret",
        metavar="SECRET",
        help="Strava Client Secret (or STRAVA_CLIENT_SECRET env var).",
    )

    parser.add_argument(
        "--days",
        type=int,
        metavar="N",
        help="Analyze/sync the last N days.",
    )
    parser.add_argument(
        "--start",
        metavar="YYYY-MM-DD",
        help="Start date for analyze/sync.",
    )
    parser.add_argument(
        "--end",
        metavar="YYYY-MM-DD",
        help="End date for analyze/sync.",
    )

    parser.add_argument(
        "--view",
        default="daily,weekly",
        help="Comma-separated views for analyze mode: daily,weekly,monthly.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass cache and always fetch from APIs.",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Analyze mode only: print summaries and skip PNG charts.",
    )

    parser.add_argument(
        "--types",
        metavar="LIST",
        help="Sync mode only: include only these Fitbit activity names.",
    )
    parser.add_argument(
        "--exclude-types",
        metavar="LIST",
        help="Sync mode only: exclude these Fitbit activity names.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Sync mode only: convert only and do not upload to Strava.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Sync mode only: max number of activities to upload (0 = no limit).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sync mode only: upload even if already synced.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable extra logging.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail instead of prompting for missing credentials.",
    )

    return parser


def _collect_provided_flags(argv: list[str]) -> set[str]:
    flags = set()
    for token in argv:
        if token.startswith("--"):
            flags.add(token.split("=", 1)[0])
    return flags


def _validate_mode_contract(args: argparse.Namespace, parser: argparse.ArgumentParser, provided_flags: set[str]) -> None:
    allowed_by_mode = {
        "configure": {"--mode", "--verbose", "--non-interactive"},
        "auth": {
            "--mode",
            "--provider",
            "--client-id",
            "--strava-client-id",
            "--strava-client-secret",
            "--verbose",
            "--non-interactive",
        },
        "analyze": {
            "--mode",
            "--client-id",
            "--days",
            "--start",
            "--end",
            "--view",
            "--no-cache",
            "--no-plot",
            "--verbose",
            "--non-interactive",
        },
        "sync": {
            "--mode",
            "--provider",
            "--client-id",
            "--strava-client-id",
            "--strava-client-secret",
            "--days",
            "--start",
            "--end",
            "--types",
            "--exclude-types",
            "--dry-run",
            "--limit",
            "--force",
            "--no-cache",
            "--verbose",
            "--non-interactive",
        },
    }

    unsupported = sorted(flag for flag in provided_flags if flag not in allowed_by_mode[args.mode])
    if unsupported:
        parser.error(f"Unsupported option(s) for --mode {args.mode}: {', '.join(unsupported)}")

    if args.days is not None and args.days < 1:
        parser.error("--days must be >= 1")

    if args.limit < 0:
        parser.error("--limit must be >= 0")

    if args.mode == "configure":
        if args.non_interactive:
            parser.error("--mode configure is interactive and cannot be used with --non-interactive")
        if args.provider:
            parser.error("--provider is not valid for --mode configure")
        return

    if args.mode == "auth":
        if not args.provider:
            parser.error("--mode auth requires --provider (fitbit|strava)")
        if args.provider == "fitbit":
            if "--strava-client-id" in provided_flags or "--strava-client-secret" in provided_flags:
                parser.error("Strava credentials are not valid with --mode auth --provider fitbit")
        elif args.provider == "strava":
            if "--client-id" in provided_flags:
                parser.error("--client-id is Fitbit-only and not valid with --mode auth --provider strava")
        return

    if args.mode == "analyze":
        if args.provider:
            parser.error("--provider is not valid for --mode analyze")
        _validate_date_flags(args, parser)
        try:
            parse_views(args.view)
        except ValueError as exc:
            parser.error(str(exc))
        return

    if args.mode == "sync":
        if args.provider != "strava":
            parser.error("--mode sync requires --provider strava")
        _validate_date_flags(args, parser)
        include = normalize_type_list(args.types)
        exclude = normalize_type_list(args.exclude_types)
        overlap = sorted(include & exclude)
        if overlap:
            parser.error(f"--types and --exclude-types overlap: {', '.join(overlap)}")


def _validate_date_flags(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.start and not args.end:
        parser.error("--start requires --end")
    if args.end and not args.start:
        parser.error("--end requires --start")
    if args.start and args.days is not None:
        parser.error("Use either --days or --start/--end, not both")


def parse_views(raw_view: str) -> list[str]:
    views = [v.strip().lower() for v in raw_view.split(",") if v.strip()]
    if not views:
        raise ValueError("--view cannot be empty")
    invalid = sorted(set(views) - ALLOWED_VIEWS)
    if invalid:
        raise ValueError(f"Invalid --view value(s): {', '.join(invalid)}")
    return views


def _parse_iso_date(value: str, arg_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{arg_name} must be YYYY-MM-DD") from exc


def _resolve_date_range(args: argparse.Namespace) -> tuple[date, date]:
    yesterday = date.today() - timedelta(days=1)

    if args.start:
        start = _parse_iso_date(args.start, "--start")
        end = _parse_iso_date(args.end, "--end")
    else:
        days = args.days if args.days is not None else 7
        end = yesterday
        start = end - timedelta(days=days - 1)

    if start > end:
        raise ValueError("start date must be before or equal to end date")

    return start, end


def _ensure_cache_dir() -> None:
    Path(".cache").mkdir(exist_ok=True)


def _load_synced() -> dict[str, dict]:
    if SYNC_LOG.exists():
        return json.loads(SYNC_LOG.read_text())
    return {}


def _save_synced(data: dict[str, dict]) -> None:
    _ensure_cache_dir()
    SYNC_LOG.write_text(json.dumps(data, indent=2))


def _require_value(current: str, prompt: str, error_message: str, non_interactive: bool) -> str:
    value = current.strip() if current else ""
    if value:
        return value
    if non_interactive:
        raise ValueError(error_message)
    value = input(prompt).strip()
    if value:
        return value
    raise ValueError(error_message)


def _resolve_fitbit_credentials(args: argparse.Namespace) -> tuple[str, str, str]:
    client_id = _require_value(
        args.client_id or os.getenv("FITBIT_CLIENT_ID", ""),
        "Enter your Fitbit Client ID: ",
        "Fitbit Client ID is required.",
        args.non_interactive,
    )
    client_secret = os.getenv("FITBIT_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("FITBIT_REDIRECT_URI", "https://192.168.86.39:8080").strip()
    return client_id, client_secret, redirect_uri


def _resolve_strava_credentials(args: argparse.Namespace) -> tuple[str, str, str]:
    client_id = _require_value(
        args.strava_client_id or os.getenv("STRAVA_CLIENT_ID", ""),
        "Enter your Strava Client ID: ",
        "Strava Client ID is required.",
        args.non_interactive,
    )
    client_secret = _require_value(
        args.strava_client_secret or os.getenv("STRAVA_CLIENT_SECRET", ""),
        "Enter your Strava Client Secret: ",
        "Strava Client Secret is required.",
        args.non_interactive,
    )
    redirect_uri = os.getenv("STRAVA_REDIRECT_URI", "http://localhost:8080").strip()
    return client_id, client_secret, redirect_uri


def _print_table(title: str, data: dict[str, dict], key_header: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")
    print(f"  {key_header:<14}  {'Light':>6}  {'Moderate':>8}  {'Vigorous':>8}  {'Max Eff':>7}  {'Fit-Mins':>8}")
    print("  " + "-" * 68)
    for key in sorted(data.keys()):
        stats = data[key]
        print(
            f"  {key:<14}  "
            f"{stats['light']:>6}  "
            f"{stats['moderate']:>8}  "
            f"{stats['vigorous']:>8}  "
            f"{stats['max_effort']:>7}  "
            f"{stats['fit_mins']:>8}"
        )


def _run_auth_mode(args: argparse.Namespace) -> None:
    if args.provider == "fitbit":
        from auth import authorize

        client_id, client_secret, redirect_uri = _resolve_fitbit_credentials(args)
        authorize(client_id, client_secret, redirect_uri)
        return

    strava_client_id, strava_client_secret, strava_redirect_uri = _resolve_strava_credentials(args)
    StravaClient(strava_client_id, strava_client_secret, strava_redirect_uri)._token()


def _run_analyze_mode(args: argparse.Namespace, start: date, end: date) -> None:
    client_id, client_secret, redirect_uri = _resolve_fitbit_credentials(args)

    if not CONFIG_FILE.exists():
        print(f"Note: {CONFIG_FILE} not found - using defaults. Run with --mode configure to set your zones.")
    cfg = load_config()

    print("\nFitbit Heart Rate Zone Analyzer (ACSM intensity framework)")
    print(f"  Date range  : {start} -> {end}  ({(end - start).days + 1} days)")
    print(f"  Light       : < {cfg.moderate_min} bpm              (< 65%)")
    print(f"  Moderate    : {cfg.moderate_min} - {cfg.vigorous_min - 1} bpm  (65-75%)")
    print(f"  Vigorous    : {cfg.vigorous_min} - {cfg.max_effort_min - 1} bpm  (76-96%)")
    print(f"  Max Effort  : {cfg.max_effort_min}+ bpm              (> 96%)")
    print("  Fit-Mins    : Moderate + 2*(Vigorous + Max Effort)  [goal: 150/week]")
    print()

    client = FitbitClient(client_id, client_secret, redirect_uri)
    print("Fetching data...")
    hr_data = client.get_hr_range(start, end, use_cache=not args.no_cache)

    daily = daily_summary(hr_data, cfg)
    views = parse_views(args.view)

    if "daily" in views:
        _print_table("DAILY SUMMARY", daily, "Date")
        if not args.no_plot:
            plot_daily(daily, cfg)

    if "weekly" in views:
        weekly = weekly_summary(daily)
        _print_table("WEEKLY SUMMARY", weekly, "ISO Week")
        if not args.no_plot:
            plot_weekly(weekly, cfg)

    if "monthly" in views:
        monthly = monthly_summary(daily)
        _print_table("MONTHLY SUMMARY", monthly, "Month")
        if not args.no_plot:
            plot_monthly(monthly, cfg)


def _run_sync_mode(args: argparse.Namespace, start: date, end: date) -> None:
    fitbit_client_id, fitbit_client_secret, fitbit_redirect_uri = _resolve_fitbit_credentials(args)
    strava_client_id, strava_client_secret, strava_redirect_uri = _resolve_strava_credentials(args)

    print("\nFitbit -> Strava sync")
    print(f"  Date range  : {start} -> {end}  ({(end - start).days + 1} days)")
    print()

    fitbit_client = FitbitClient(fitbit_client_id, fitbit_client_secret, fitbit_redirect_uri)
    strava_client = StravaClient(strava_client_id, strava_client_secret, strava_redirect_uri)

    activities = fitbit_client.get_activities_range(start, end, use_cache=not args.no_cache)
    if args.verbose:
        print(f"Fetched {len(activities)} Fitbit activities.")

    include_types = normalize_type_list(args.types)
    exclude_types = normalize_type_list(args.exclude_types)

    synced = _load_synced()
    uploaded = 0

    for activity in activities:
        name = activity.get("activityName") or activity.get("name") or ""
        name_key = name.lower()

        if include_types and name_key not in include_types:
            continue
        if exclude_types and name_key in exclude_types:
            continue

        log_id = activity.get("logId") or activity.get("activityLogId") or activity.get("id")
        if not log_id:
            print("  Warning: missing logId; skipping activity.")
            continue

        if not args.force and str(log_id) in synced:
            if args.verbose:
                print(f"  Skipping already synced: {name} ({log_id})")
            continue

        detail = fitbit_client.get_activity_detail(int(log_id))
        payload = activity_to_strava_payload(detail, fallback_activity=activity)
        if payload is None:
            continue

        if args.dry_run:
            print(f"  Dry run: {payload['name']} ({payload['type']}) at {payload['start_date_local']}")
        else:
            response = strava_client.create_activity(payload)
            synced[str(log_id)] = {
                "strava_id": response.get("id"),
                "name": payload["name"],
                "start_date_local": payload["start_date_local"],
            }
            _save_synced(synced)
            print(f"  Uploaded: {payload['name']} -> Strava ID {response.get('id')}")
            uploaded += 1

        if args.limit and uploaded >= args.limit:
            break

    if args.dry_run:
        print("Dry run completed.")
    else:
        print(f"Sync completed. Uploaded {uploaded} activities.")


def main() -> None:
    parser = build_parser()
    provided_flags = _collect_provided_flags(sys.argv[1:])
    args = parser.parse_args()
    _validate_mode_contract(args, parser, provided_flags)

    try:
        if args.mode == "configure":
            run_configure()
            return

        if args.mode == "auth":
            _run_auth_mode(args)
            return

        start, end = _resolve_date_range(args)

        if args.mode == "analyze":
            _run_analyze_mode(args, start, end)
            return

        _run_sync_mode(args, start, end)

    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
