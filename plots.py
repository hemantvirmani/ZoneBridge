"""Matplotlib visualizations for heart-rate zone data."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from analysis import DEFAULT_ZONES, ZoneConfig

# Zone color palette (bottom -> top in stacked bar)
ZONE_COLORS = {
    "moderate": "#27ae60",   # green
    "vigorous": "#e67e22",   # orange
    "max_effort": "#e74c3c",  # red
}
FIT_COLOR = "#2980b9"       # blue
EXERCISE_COLOR = "#16a085"  # teal
GOAL_COLOR = "#8e44ad"      # purple

ZONE_STACK_KEYS = ("moderate", "vigorous", "max_effort")
WEEKLY_GOAL = 150


def _stacked_bar(ax, x, data_by_key, keys, colors, labels, width=0.7):
    """Draw a stacked bar chart on *ax*."""
    bottom = np.zeros(len(x))
    inside_label_min_height = 18
    for key in keys:
        values = np.array([data_by_key[k].get(key, 0) for k in data_by_key])
        bars = ax.bar(x, values, width, bottom=bottom,
                      color=colors[key], label=labels[key], alpha=0.88)
        for bar, value, base in zip(bars, values, bottom):
            if value <= 0:
                continue
            cx = bar.get_x() + (bar.get_width() / 2)
            label = f"{int(value)}" if float(value).is_integer() else f"{value:.1f}"
            if value >= inside_label_min_height:
                cy = base + (value / 2)
                ax.text(
                    cx,
                    cy,
                    label,
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white",
                    fontweight="bold",
                )
            else:
                # Small stacked segments (common in vigorous/max effort) are hard to read.
                # Place labels just above the segment with a high-contrast box.
                cy = base + value + 1
                ax.text(
                    cx,
                    cy,
                    label,
                    ha="center",
                    va="bottom",
                    fontsize=7,
                    color="black",
                    fontweight="bold",
                    clip_on=False,
                    bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": "none", "alpha": 0.85},
                )
        bottom += values


def _fit_and_exercise_bar(ax, x, data_by_key, show_goal: bool = False, width=0.7):
    """Draw grouped Fit-Mins and Exercise-Mins bars; optionally include weekly goal line."""
    fit_values = np.array([data_by_key[k].get("fit_mins", 0) for k in data_by_key])
    exercise_values = np.array([data_by_key[k].get("exercise_mins", 0.0) for k in data_by_key])

    bar_w = width / 2.1
    fit_x = x - (bar_w / 2)
    exercise_x = x + (bar_w / 2)

    ax.bar(fit_x, fit_values, bar_w, color=FIT_COLOR, alpha=0.85, label="Fit-Mins")
    ax.bar(exercise_x, exercise_values, bar_w, color=EXERCISE_COLOR, alpha=0.85, label="Exercise Mins")

    for xi, v in zip(fit_x, fit_values):
        if v > 0:
            ax.text(xi, v + 1, str(int(v)), ha="center", va="bottom", fontsize=8, fontweight="bold")
    for xi, v in zip(exercise_x, exercise_values):
        if v > 0:
            ax.text(xi, v + 0.4, f"{v:.1f}", ha="center", va="bottom", fontsize=8)

    if show_goal:
        ax.axhline(WEEKLY_GOAL, color=GOAL_COLOR, linewidth=1.5, linestyle="--",
                   label=f"Goal ({WEEKLY_GOAL} Fit-Mins)")


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
    """Stacked exercise-zone bars + Fit-Mins/Exercise-Mins bars for each day."""
    dates = sorted(daily.keys())
    if not dates:
        print("No data to plot.")
        return

    x = np.arange(len(dates))
    x_labels = [d[5:] for d in dates]  # show MM-DD only
    labels = {k: cfg.labels[k] for k in ZONE_STACK_KEYS}

    fig, (ax_zones, ax_fit) = plt.subplots(2, 1, figsize=(max(10, len(dates) * 0.6 + 2), 10))
    fig.suptitle("Daily Heart Rate Zone Analysis", fontsize=15, fontweight="bold", y=0.98)

    _stacked_bar(ax_zones, x, {d: daily[d] for d in dates},
                 ZONE_STACK_KEYS, ZONE_COLORS, labels)
    _configure_axes(ax_zones, x, x_labels, "Minutes", "Exercise Zone Minutes (Moderate/Vigorous/Max Effort)")

    _fit_and_exercise_bar(ax_fit, x, {d: daily[d] for d in dates})
    _configure_axes(ax_fit, x, x_labels, "Minutes",
                    "Daily Fit-Mins and Total Exercise Minutes")

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"Plot saved -> {save_path}")


def plot_weekly(
    weekly: dict[str, dict],
    cfg: ZoneConfig = DEFAULT_ZONES,
    save_path: str = "fitbit_weekly.png",
):
    """Stacked exercise-zone bars + Fit-Mins/Exercise-Mins bars per ISO week."""
    weeks = sorted(weekly.keys())
    if not weeks:
        print("No data to plot.")
        return

    x = np.arange(len(weeks))
    labels = {k: cfg.labels[k] for k in ZONE_STACK_KEYS}

    fig, (ax_zones, ax_fit) = plt.subplots(2, 1, figsize=(max(10, len(weeks) * 1.2 + 2), 10))
    fig.suptitle("Weekly Heart Rate Zone Analysis", fontsize=15, fontweight="bold", y=0.98)

    _stacked_bar(ax_zones, x, {w: weekly[w] for w in weeks},
                 ZONE_STACK_KEYS, ZONE_COLORS, labels)
    _configure_axes(ax_zones, x, weeks, "Minutes", "Weekly Exercise Zone Minutes", rotate=30)

    _fit_and_exercise_bar(ax_fit, x, {w: weekly[w] for w in weeks}, show_goal=True)
    _configure_axes(ax_fit, x, weeks, "Minutes",
                    f"Weekly Fit-Mins and Total Exercise Minutes (goal: {WEEKLY_GOAL} Fit-Mins)",
                    rotate=30)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"Plot saved -> {save_path}")


def plot_monthly(
    monthly: dict[str, dict],
    cfg: ZoneConfig = DEFAULT_ZONES,
    save_path: str = "fitbit_monthly.png",
):
    """Stacked exercise-zone bars + Fit-Mins/Exercise-Mins bars per month."""
    months = sorted(monthly.keys())
    if not months:
        print("No data to plot.")
        return

    x = np.arange(len(months))
    labels = {k: cfg.labels[k] for k in ZONE_STACK_KEYS}

    fig, (ax_zones, ax_fit) = plt.subplots(2, 1, figsize=(max(10, len(months) * 1.5 + 2), 10))
    fig.suptitle("Monthly Heart Rate Zone Analysis", fontsize=15, fontweight="bold", y=0.98)

    _stacked_bar(ax_zones, x, {m: monthly[m] for m in months},
                 ZONE_STACK_KEYS, ZONE_COLORS, labels)
    _configure_axes(ax_zones, x, months, "Minutes", "Monthly Exercise Zone Minutes", rotate=30)

    _fit_and_exercise_bar(ax_fit, x, {m: monthly[m] for m in months})
    _configure_axes(ax_fit, x, months, "Minutes",
                    "Monthly Fit-Mins and Total Exercise Minutes", rotate=30)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"Plot saved -> {save_path}")
