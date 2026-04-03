"""Fitbit -> Strava conversion helpers."""

import re


def normalize_type_list(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {value.strip().lower() for value in raw.split(",") if value.strip()}


def fitbit_to_strava_type(name: str) -> str:
    text = name.lower()
    if "run" in text:
        return "Run"
    if "walk" in text:
        return "Walk"
    if "hike" in text:
        return "Hike"
    if "ride" in text or "bike" in text or "cycling" in text:
        return "Ride"
    if "swim" in text:
        return "Swim"
    if "elliptical" in text:
        return "Elliptical"
    if "row" in text:
        return "Rowing"
    if "yoga" in text:
        return "Yoga"
    if "weight" in text or "strength" in text:
        return "WeightTraining"
    if "stair" in text or "stepper" in text:
        return "StairStepper"
    return "Workout"


def distance_to_meters(distance: float | int | None, unit: str | None) -> float | None:
    if distance is None or unit is None:
        return None

    normalized = unit.strip().lower()
    if normalized in ("kilometer", "kilometers", "km"):
        return float(distance) * 1000.0
    if normalized in ("mile", "miles", "mi"):
        return float(distance) * 1609.344
    if normalized in ("meter", "meters", "m"):
        return float(distance)
    if normalized in ("yard", "yards", "yd"):
        return float(distance) * 0.9144
    return None


def extract_activity(detail: dict) -> dict:
    if "activityLog" in detail and isinstance(detail["activityLog"], dict):
        return detail["activityLog"]
    if "activity" in detail and isinstance(detail["activity"], dict):
        return detail["activity"]
    if "activities" in detail and isinstance(detail["activities"], list) and detail["activities"]:
        first = detail["activities"][0]
        if isinstance(first, dict):
            return first
    return detail


def _combine_start_datetime(start_date: str | None, start_time: str | None) -> str | None:
    if not start_date or not start_time:
        return None
    date_text = start_date.strip()
    time_text = start_time.strip()
    if not date_text or not time_text:
        return None

    if "T" in time_text:
        return time_text

    if re.fullmatch(r"\d{2}:\d{2}$", time_text):
        return f"{date_text}T{time_text}:00"
    if re.fullmatch(r"\d{2}:\d{2}:\d{2}$", time_text):
        return f"{date_text}T{time_text}"
    return None


def _resolve_start_time(activity: dict, fallback_activity: dict | None = None) -> str | None:
    primary = (
        activity.get("startTime")
        or activity.get("originalStartTime")
        or activity.get("startDate")
    )
    if isinstance(primary, str) and "T" in primary:
        return primary

    combined = _combine_start_datetime(
        activity.get("startDate"),
        activity.get("startTime"),
    )
    if combined:
        return combined

    if fallback_activity:
        fallback_primary = (
            fallback_activity.get("startTime")
            or fallback_activity.get("originalStartTime")
            or fallback_activity.get("startDate")
        )
        if isinstance(fallback_primary, str) and "T" in fallback_primary:
            return fallback_primary

        fallback_combined = _combine_start_datetime(
            fallback_activity.get("startDate"),
            fallback_activity.get("startTime"),
        )
        if fallback_combined:
            return fallback_combined

    return None


def activity_to_strava_payload(detail: dict, fallback_activity: dict | None = None) -> dict | None:
    activity = extract_activity(detail)
    name = activity.get("activityName") or activity.get("name") or "Fitbit Activity"

    start_time = _resolve_start_time(activity, fallback_activity=fallback_activity)
    if not start_time:
        print("  Warning: missing start time; skipping activity.")
        return None

    duration = activity.get("duration")
    if duration is None and fallback_activity is not None:
        duration = fallback_activity.get("duration")
    if duration is None:
        print("  Warning: missing duration; skipping activity.")
        return None

    duration_float = float(duration)
    duration_sec = int(round(duration_float / 1000.0)) if duration_float > 10000 else int(round(duration_float))
    if duration_sec <= 0:
        print("  Warning: invalid duration; skipping activity.")
        return None

    distance = activity.get("distance")
    distance_unit = activity.get("distanceUnit") or activity.get("distanceUnitLabel")
    if distance is None and fallback_activity is not None:
        distance = fallback_activity.get("distance")
    if distance_unit is None and fallback_activity is not None:
        distance_unit = fallback_activity.get("distanceUnit") or fallback_activity.get("distanceUnitLabel")
    distance_m = distance_to_meters(distance, distance_unit)

    payload = {
        "name": name,
        "type": fitbit_to_strava_type(name),
        "start_date_local": start_time,
        "elapsed_time": duration_sec,
        "external_id": str(
            activity.get("logId")
            or activity.get("activityLogId")
            or activity.get("id")
            or (fallback_activity or {}).get("logId")
            or (fallback_activity or {}).get("activityLogId")
            or (fallback_activity or {}).get("id")
            or ""
        ),
        "description": "Imported from Fitbit",
    }

    if distance_m is not None:
        payload["distance"] = distance_m

    calories = activity.get("calories")
    if calories is None and fallback_activity is not None:
        calories = fallback_activity.get("calories")
    if calories is not None:
        payload["calories"] = int(calories)

    return payload
