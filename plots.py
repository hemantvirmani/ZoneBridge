"""
Matplotlib visualizations for heart-rate zone data.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from analysis import ZoneConfig, DEFAULT_ZONES

# Zone color palette (bottom → top in stacked bar)
ZONE_COLORS = {
    "resting": "#d5d8dc",  # light grey  – below Zone 1
    "zone1":   "#aab7b8",  # grey        – light activity
    "zone2":   "#27ae60",  # green       – aerobic / fat-burn
    "zone3":   "#e67e22",  # orange      – tempo
    "zone4":   "#e74c3c",  # red         – threshold
    "zone5":   "#8e44ad",  # purple      – max effort
}
FIT_COLOR = "#2980b9"     # blue – fit-mins bars

ZONE_STACK_KEYS = ("resting", "zone1", "zone2", "zone3", "zone4", "zone5")


def _stacked_bar(ax, x, data_by_key, keys, colors, labels, width=0.7):
    """Draw a stacked bar chart on *ax*."""
    bottom = np.zeros(len(x))
    for key in keys:
        values = np.array([data_by_key[k].get(key, 0) for k in data_by_key])
        ax.bar(x, values, width, bottom=bottom,
               color=colors[key], label=labels[key], alpha=0.88)
        bottom += values


def _fit_bar(ax, x, data_by_key, width=0.7):
    """Draw fit-mins bars + trend line."""
    values = np.array([data_by_key[k].get("fit_mins", 0) for k in data_by_key])
    ax.bar(x, values, width, color=FIT_COLOR, alpha=0.80, label="Fit-Mins")
    ax.plot(x, values, "o-", color="#1a5276", linewidth=2, markersize=5, zorder=5)
    return values


def _configure_axes(ax, x_pos, x_labels, ylabel, title, rotate=45):
    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels, rotation=rotate, ha="right", fontsize=9)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_xlim(-0.6, len(x_pos) - 0.4)


# ---------------------------------------------------------------------------
# Public plot functions
# ---------------------------------------------------------------------------

def plot_daily(
    daily: dict[str, dict],
    cfg: ZoneConfig = DEFAULT_ZONES,
    save_path: str = "fitbit_daily.png",
):
    """Stacked zone bars + fit-mins bars for each day."""
    dates = sorted(daily.keys())
    if not dates:
        print("No data to plot.")
        return

    x = np.arange(len(dates))
    x_labels = [d[5:] for d in dates]           # show MM-DD only
    labels = cfg.labels

    fig, (ax_zones, ax_fit) = plt.subplots(2, 1, figsize=(max(10, len(dates) * 0.6 + 2), 10))
    fig.suptitle("Daily Heart Rate Zone Analysis", fontsize=15, fontweight="bold", y=0.98)

    _stacked_bar(ax_zones, x, {d: daily[d] for d in dates},
                 ZONE_STACK_KEYS, ZONE_COLORS, labels)
    _configure_axes(ax_zones, x, x_labels, "Minutes", "Minutes in Each Zone")

    _fit_bar(ax_fit, x, {d: daily[d] for d in dates})
    _configure_axes(ax_fit, x, x_labels, "Fit-Mins",
                    "Daily Fit-Mins  (Zone2 + 2 × Zone3–5 minutes)")

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"Plot saved → {save_path}")


def plot_weekly(
    weekly: dict[str, dict],
    cfg: ZoneConfig = DEFAULT_ZONES,
    save_path: str = "fitbit_weekly.png",
):
    """Stacked zone bars + fit-mins bars per ISO week."""
    weeks = sorted(weekly.keys())
    if not weeks:
        print("No data to plot.")
        return

    x = np.arange(len(weeks))
    labels = cfg.labels

    fig, (ax_zones, ax_fit) = plt.subplots(2, 1, figsize=(max(10, len(weeks) * 1.2 + 2), 10))
    fig.suptitle("Weekly Heart Rate Zone Analysis", fontsize=15, fontweight="bold", y=0.98)

    _stacked_bar(ax_zones, x, {w: weekly[w] for w in weeks},
                 ZONE_STACK_KEYS, ZONE_COLORS, labels)
    _configure_axes(ax_zones, x, weeks, "Minutes", "Weekly Minutes in Each Zone", rotate=30)

    _fit_bar(ax_fit, x, {w: weekly[w] for w in weeks})
    _configure_axes(ax_fit, x, weeks, "Fit-Mins",
                    "Weekly Fit-Mins  (Zone2 + 2 × Zone3–5 minutes)", rotate=30)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"Plot saved → {save_path}")


def plot_monthly(
    monthly: dict[str, dict],
    cfg: ZoneConfig = DEFAULT_ZONES,
    save_path: str = "fitbit_monthly.png",
):
    """Stacked zone bars + fit-mins bars per month."""
    months = sorted(monthly.keys())
    if not months:
        print("No data to plot.")
        return

    x = np.arange(len(months))
    labels = cfg.labels

    fig, (ax_zones, ax_fit) = plt.subplots(2, 1, figsize=(max(10, len(months) * 1.5 + 2), 10))
    fig.suptitle("Monthly Heart Rate Zone Analysis", fontsize=15, fontweight="bold", y=0.98)

    _stacked_bar(ax_zones, x, {m: monthly[m] for m in months},
                 ZONE_STACK_KEYS, ZONE_COLORS, labels)
    _configure_axes(ax_zones, x, months, "Minutes", "Monthly Minutes in Each Zone", rotate=30)

    _fit_bar(ax_fit, x, {m: monthly[m] for m in months})
    _configure_axes(ax_fit, x, months, "Fit-Mins",
                    "Monthly Fit-Mins  (Zone2 + 2 × Zone3–5 minutes)", rotate=30)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"Plot saved → {save_path}")
