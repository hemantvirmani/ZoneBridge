"""
Heart-rate zone classification and metrics (ACSM intensity framework).

Zone boundaries are loaded from fitbit_config.json (created via --configure).
Four zones based on HR-Max percentages:

  Light      –  hr < moderate_min       (< 65 % HR-Max)
  Moderate   –  moderate_min <= hr < vigorous_min  (65–75 %)
  Vigorous   –  vigorous_min <= hr < max_effort_min  (76–96 %)
  Max Effort –  hr >= max_effort_min    (> 96 % HR-Max)

Fit-Mins = Moderate_mins + 2 × (Vigorous_mins + Max_Effort_mins)
Weekly goal: 150 Fit-Mins
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

CONFIG_FILE = Path("fitbit_config.json")

# Ordered bucket names used throughout the pipeline
ZONE_KEYS = ("light", "moderate", "vigorous", "max_effort")


# ---------------------------------------------------------------------------
# Zone configuration
# ---------------------------------------------------------------------------

@dataclass
class ZoneConfig:
    moderate_min: int = 117   # 65% of HR-Max 180 (default age 40)
    vigorous_min: int = 137   # 76% of HR-Max 180
    max_effort_min: int = 173  # 96% of HR-Max 180

    @property
    def labels(self) -> dict[str, str]:
        return {
            "light":      f"Light (<{self.moderate_min} bpm, <65%)",
            "moderate":   f"Moderate ({self.moderate_min}–{self.vigorous_min - 1} bpm, 65–75%)",
            "vigorous":   f"Vigorous ({self.vigorous_min}–{self.max_effort_min - 1} bpm, 76–96%)",
            "max_effort": f"Max Effort ({self.max_effort_min}+ bpm, >96%)",
        }


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------

def load_config() -> ZoneConfig:
    """Load zone config from fitbit_config.json; fall back to defaults."""
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text())
        return ZoneConfig(
            moderate_min=data.get("moderate_min", 117),
            vigorous_min=data.get("vigorous_min", 137),
            max_effort_min=data.get("max_effort_min", 173),
        )
    return ZoneConfig()


def save_config(
    cfg: ZoneConfig,
    age: int | None = None,
    hr_max: int | None = None,
) -> None:
    """Persist zone config (and optional metadata) to fitbit_config.json."""
    data: dict = {
        "moderate_min": cfg.moderate_min,
        "vigorous_min": cfg.vigorous_min,
        "max_effort_min": cfg.max_effort_min,
    }
    if age is not None:
        data["age"] = age
    if hr_max is not None:
        data["hr_max"] = hr_max
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


DEFAULT_ZONES = ZoneConfig()


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_bpm(bpm: int, cfg: ZoneConfig = DEFAULT_ZONES) -> str:
    """Return 'light', 'moderate', 'vigorous', or 'max_effort' for a heart-rate value."""
    if bpm < cfg.moderate_min:
        return "light"
    if bpm < cfg.vigorous_min:
        return "moderate"
    if bpm < cfg.max_effort_min:
        return "vigorous"
    return "max_effort"


# ---------------------------------------------------------------------------
# Per-day calculation
# ---------------------------------------------------------------------------

def zone_minutes(dataset: Sequence[dict], cfg: ZoneConfig = DEFAULT_ZONES) -> dict[str, int]:
    """
    Count minutes in each zone from an intraday dataset.
    Each point is {'time': 'HH:MM:SS', 'value': bpm} = 1 minute.
    """
    counts: dict[str, int] = {k: 0 for k in ZONE_KEYS}
    for point in dataset:
        counts[classify_bpm(point["value"], cfg)] += 1
    return counts


def fit_mins(zm: dict[str, int]) -> int:
    """Fit-Mins = Moderate + 2 × (Vigorous + Max_Effort)."""
    return zm["moderate"] + 2 * (zm["vigorous"] + zm["max_effort"])


# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------

def daily_summary(
    hr_by_date: dict[str, list[dict]],
    cfg: ZoneConfig = DEFAULT_ZONES,
) -> dict[str, dict]:
    """
    Build per-day stats from raw intraday data.
    Returns {date_str: {'light': m, 'moderate': m, 'vigorous': m, 'max_effort': m, 'fit_mins': m}}
    """
    result: dict[str, dict] = {}
    for date_str, dataset in hr_by_date.items():
        zm = zone_minutes(dataset, cfg)
        result[date_str] = {**zm, "fit_mins": fit_mins(zm)}
    return result


def weekly_summary(daily: dict[str, dict]) -> dict[str, dict]:
    """Aggregate daily stats into ISO year-week keys ('2025-W03')."""
    weekly: dict[str, dict] = {}
    for date_str, stats in daily.items():
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        iso = dt.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        if key not in weekly:
            weekly[key] = {k: 0 for k in (*ZONE_KEYS, "fit_mins")}
        for k in (*ZONE_KEYS, "fit_mins"):
            weekly[key][k] += stats[k]
    return weekly


def monthly_summary(daily: dict[str, dict]) -> dict[str, dict]:
    """Aggregate daily stats into 'YYYY-MM' keys."""
    monthly: dict[str, dict] = {}
    for date_str, stats in daily.items():
        key = date_str[:7]
        if key not in monthly:
            monthly[key] = {k: 0 for k in (*ZONE_KEYS, "fit_mins")}
        for k in (*ZONE_KEYS, "fit_mins"):
            monthly[key][k] += stats[k]
    return monthly
