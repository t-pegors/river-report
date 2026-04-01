"""
Alert logic:
  - DRAMATIC CHANGE: CFS shifted >= alert_change_pct% since yesterday
  - BELOW THRESHOLD: current CFS is under the configured min_cfs float limit
"""


def check_alerts(current: dict, yesterday: dict | None, config: dict) -> list[dict]:
    """
    Returns a list of alert dicts, each with:
      level   — "alert" (urgent), "warning" (data problem), or "info" (FYI)
      message — human-readable string
    """
    alerts = []
    min_cfs = config.get("min_cfs", 600)
    alert_pct = config.get("alert_change_pct", 25)
    cfs = current.get("cfs")

    if cfs is None:
        alerts.append({
            "level": "warning",
            "message": "CFS data was unavailable from USGS for today's reading.",
        })
        return alerts

    # --- dramatic change check ---
    if yesterday and yesterday.get("cfs") and yesterday["cfs"] != 0:
        prev = yesterday["cfs"]
        change = cfs - prev
        change_pct = (change / prev) * 100
        if abs(change_pct) >= alert_pct:
            direction = "rose" if change > 0 else "dropped"
            alerts.append({
                "level": "alert",
                "message": (
                    f"Dramatic change: river {direction} {abs(change_pct):.1f}% since yesterday "
                    f"({prev:.0f} \u2192 {cfs:.0f} CFS)."
                ),
            })

    # --- float day threshold check ---
    if cfs < min_cfs:
        alerts.append({
            "level": "info",
            "message": (
                f"River is below the float threshold "
                f"({cfs:.0f} CFS \u2014 minimum is {min_cfs} CFS)."
            ),
        })

    return alerts
