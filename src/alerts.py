"""
Alert logic:
  - DRAMATIC CHANGE: value shifted >= alert_change_pct% since yesterday
  - BELOW THRESHOLD: current CFS is under the configured min_cfs float limit
    (only checked when min_cfs is present in config)
"""


def check_alerts(current: dict, yesterday: dict | None, config: dict) -> list[dict]:
    """
    Returns a list of alert dicts, each with:
      level   — "alert" (urgent), "warning" (data problem), or "info" (FYI)
      message — human-readable string
    """
    alerts = []
    min_cfs   = config.get("min_cfs")          # None when not configured
    alert_pct = config.get("alert_change_pct", 25)
    gauge_unit = config.get("gauge_unit", "cfs")

    cfs = current.get("cfs")
    height_ft = current.get("height_ft")

    # Use whichever metric is primary for this gauge
    current_val = cfs if gauge_unit == "cfs" else height_ft
    unit_label  = "CFS" if gauge_unit == "cfs" else "ft"

    if current_val is None:
        alerts.append({
            "level": "warning",
            "message": f"{unit_label} data was unavailable from USGS for today's reading.",
        })
        return alerts

    # --- dramatic change check ---
    if yesterday:
        prev_val = yesterday.get("cfs") if gauge_unit == "cfs" else yesterday.get("height_ft")
        if prev_val and prev_val != 0:
            change = current_val - prev_val
            change_pct = (change / prev_val) * 100
            if abs(change_pct) >= alert_pct:
                direction = "rose" if change > 0 else "dropped"
                alerts.append({
                    "level": "alert",
                    "message": (
                        f"Dramatic change: value {direction} {abs(change_pct):.1f}% since yesterday "
                        f"({prev_val:.1f} \u2192 {current_val:.1f} {unit_label})."
                    ),
                })

    # --- float day threshold check (only when min_cfs is configured) ---
    if min_cfs is not None and cfs is not None:
        if cfs < min_cfs:
            alerts.append({
                "level": "info",
                "message": (
                    f"River is below the float threshold "
                    f"({cfs:.0f} CFS \u2014 minimum is {min_cfs} CFS)."
                ),
            })

    return alerts
