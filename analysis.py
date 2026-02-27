"""
Heart-rate zone classification and metrics.

Zone boundaries are loaded from fitbit_config.json (created via --configure).
Five zones based on HR-Max percentages, plus a resting bucket for < Zone 1.

  Resting  –  hr < z1_min          (below 50 % HR-Max)
  Zone 1   –  z1_min <= hr < z2_min  (50–60 %)
  Zone 2   –  z2_min <= hr < z3_min  (60–70 %)
  Zone 3   –  z3_min <= hr < z4_min  (70–80 %)
  Zone 4   –  z4_min <= hr < z5_min  (80–90 %)
  Zone 5   –  hr >= z5_min           (90–100 %)

Fit-Mins = Zone2_mins + 2 × (Zone3_mins + Zone4_mins + Zone5_mins)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

CONFIG_FILE = Path("fitbit_config.json")

# Ordered bucket names used throughout the pipeline
ZONE_KEYS = ("resting", "zone1", "zone2", "zone3", "zone4", "zone5")


# ---------------------------------------------------------------------------
# Zone configuration
# ---------------------------------------------------------------------------

@dataclass
class ZoneConfig:
    z1_min: int = 90    # Zone 1 lower bound (≈50 % of HR-Max 180), inclusive
    z2_min: int = 108   # Zone 2 lower bound (≈60 %), inclusive
    z3_min: int = 126   # Zone 3 lower bound (≈70 %), inclusive
    z4_min: int = 144   # Zone 4 lower bound (≈80 %), inclusive
    z5_min: int = 162   # Zone 5 lower bound (≈90 %), inclusive

    @property
    def labels(self) -> dict[str, str]:
        return {
            "resting": f"Resting (<{self.z1_min} bpm)",
            "zone1":   f"Zone 1 ({self.z1_min}–{self.z2_min - 1} bpm, 50–60%)",
            "zone2":   f"Zone 2 ({self.z2_min}–{self.z3_min - 1} bpm, 60–70%)",
            "zone3":   f"Zone 3 ({self.z3_min}–{self.z4_min - 1} bpm, 70–80%)",
            "zone4":   f"Zone 4 ({self.z4_min}–{self.z5_min - 1} bpm, 80–90%)",
            "zone5":   f"Zone 5 ({self.z5_min}+ bpm, 90–100%)",
        }


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------

def load_config() -> ZoneConfig:
    """Load zone config from fitbit_config.json; fall back to defaults."""
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text())
        return ZoneConfig(
            z1_min=data.get("z1_min", 90),
            z2_min=data.get("z2_min", 108),
            z3_min=data.get("z3_min", 126),
            z4_min=data.get("z4_min", 144),
            z5_min=data.get("z5_min", 162),
        )
    return ZoneConfig()


def save_config(
    cfg: ZoneConfig,
    age: int | None = None,
    hr_max: int | None = None,
) -> None:
    """Persist zone config (and optional metadata) to fitbit_config.json."""
    data: dict = {
        "z1_min": cfg.z1_min,
        "z2_min": cfg.z2_min,
        "z3_min": cfg.z3_min,
        "z4_min": cfg.z4_min,
        "z5_min": cfg.z5_min,
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
    """Return 'resting' or 'zone1'…'zone5' for a heart-rate value."""
    if bpm < cfg.z1_min:
        return "resting"
    if bpm < cfg.z2_min:
        return "zone1"
    if bpm < cfg.z3_min:
        return "zone2"
    if bpm < cfg.z4_min:
        return "zone3"
    if bpm < cfg.z5_min:
        return "zone4"
    return "zone5"


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
    """Fit-Mins = Zone2 + 2 × (Zone3 + Zone4 + Zone5)."""
    return zm["zone2"] + 2 * (zm["zone3"] + zm["zone4"] + zm["zone5"])


# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------

def daily_summary(
    hr_by_date: dict[str, list[dict]],
    cfg: ZoneConfig = DEFAULT_ZONES,
) -> dict[str, dict]:
    """
    Build per-day stats from raw intraday data.
    Returns {date_str: {'resting': m, 'zone1': m, …, 'zone5': m, 'fit_mins': m}}
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
