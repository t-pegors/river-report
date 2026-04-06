"""
Generate a year-over-year comparison chart as a PNG.
Supports CFS (river flow) or height_ft (lake level) as the primary metric.
Uses matplotlib with a warm, outdoorsy color palette to match the email theme.
"""

import io

import matplotlib
matplotlib.use("Agg")          # non-interactive backend — safe for servers / Actions
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from datetime import datetime

# Palette: oldest → most recent. Current year is always assigned the last slot (river blue).
# Designed to be distinct at a glance — avoids clustering similar hues together.
_YEAR_COLORS = [
    "#b07d3a",   # amber
    "#c0533a",   # terracotta
    "#8d6e63",   # warm brown
    "#6a994e",   # olive green
    "#9b59b6",   # purple
    "#1a6b9a",   # river blue  ← current year
]

# Month boundary day-of-year values (non-leap)
_MONTH_STARTS  = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
_MONTH_LABELS  = ["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"]


def _day_of_year(date_str: str) -> int:
    return datetime.strptime(date_str, "%Y-%m-%d").timetuple().tm_yday


def generate_chart(
    year_data: dict,
    min_cfs: int | None,
    current_year: int,
    gauge_unit: str = "cfs",
    chart_title: str = "Salt River CFS — Year over Year",
) -> bytes | None:
    """
    Build a line chart comparing multiple years.

    Args:
        year_data:    {year: [{"date": "YYYY-MM-DD", "cfs": float, "height_ft": float}, ...]}
        min_cfs:      float threshold line value; pass None to omit the line
        current_year: the year whose line is drawn bold
        gauge_unit:   "cfs" or "height_ft" — which column to plot
        chart_title:  title string displayed above the chart

    Returns:
        Raw PNG bytes, or None if there is no plottable data.
    """
    years = sorted(year_data.keys())
    if not any(year_data[y] for y in years):
        return None

    fig, ax = plt.subplots(figsize=(10, 3.8))
    fig.patch.set_facecolor("#fffcf5")
    ax.set_facecolor("#f5f0e6")

    for idx, year in enumerate(years):
        records = year_data.get(year, [])
        if not records:
            continue

        days = [_day_of_year(r["date"]) for r in records]
        vals = [r.get(gauge_unit) for r in records]
        # Drop rows where the metric is None
        pairs = [(d, v) for d, v in zip(days, vals) if v is not None]
        if not pairs:
            continue
        days, vals = zip(*pairs)

        is_current = (year == current_year)
        if is_current:
            color = _YEAR_COLORS[-1]
        else:
            color = _YEAR_COLORS[min(idx, len(_YEAR_COLORS) - 2)]

        ax.plot(
            days, vals,
            color     = color,
            linewidth = 2.2 if is_current else 1.4,
            alpha     = 1.0 if is_current else 0.70,
            label     = str(year),
            zorder    = 10 if is_current else 5,
        )

    # Optional float/threshold line
    if min_cfs is not None:
        ax.axhline(
            y         = min_cfs,
            color     = "#8b3a1a",
            linewidth = 1.3,
            linestyle = "--",
            alpha     = 0.85,
            label     = f"Float min ({min_cfs} CFS)",
            zorder    = 3,
        )

    # Axes
    y_label = "Height (ft)" if gauge_unit == "height_ft" else "CFS"
    ax.set_xlim(1, 366)
    ax.set_xticks(_MONTH_STARTS)
    ax.set_xticklabels(_MONTH_LABELS, fontsize=9, color="#3a2e1e")
    ax.set_ylabel(y_label, fontsize=10, color="#3a2e1e")
    ax.tick_params(axis="y", colors="#3a2e1e", labelsize=9)
    ax.tick_params(axis="x", length=0)

    # Grid
    ax.yaxis.grid(True,  color="#d4c9b0", linewidth=0.7, linestyle="-")
    ax.xaxis.grid(True,  color="#d4c9b0", linewidth=0.4, linestyle="-")
    ax.set_axisbelow(True)

    # Spines
    for spine in ax.spines.values():
        spine.set_edgecolor("#c8bfae")

    # Title + legend
    ax.set_title(
        chart_title,
        fontsize   = 12,
        fontweight = "bold",
        color      = "#2d5a1b",
        pad        = 10,
    )
    leg = ax.legend(
        fontsize    = 9,
        loc         = "upper right",
        framealpha  = 0.92,
        facecolor   = "#fffcf5",
        edgecolor   = "#d4c9b0",
    )
    for txt in leg.get_texts():
        txt.set_color("#3a2e1e")

    plt.tight_layout(pad=0.8)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()
