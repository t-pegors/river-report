"""
Entry point for the Salt River daily report.
Run from the project root: python src/main.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Allow sibling imports when run as a script
sys.path.insert(0, str(Path(__file__).parent))

from fetch import get_latest_reading
from db import init_db, insert_reading, get_recent_readings, get_yesterday_reading
from alerts import check_alerts
from report import build_html_email, send_email

CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def build_subject(cfs: float | None, alerts: list[dict], min_cfs: int) -> str:
    if cfs is not None:
        float_status = "FLOAT DAY ✓" if cfs >= min_cfs else "Not a float day"
        cfs_part = f"{cfs:.0f} CFS"
    else:
        float_status = "Data unavailable"
        cfs_part = "N/A"

    has_alert = any(a["level"] == "alert" for a in alerts)
    alert_tag = " — ⚠️ DRAMATIC CHANGE" if has_alert else ""

    return f"Salt River Report — {float_status} ({cfs_part}){alert_tag}"


def main():
    config  = load_config()
    site_id = config.get("gauge_site", "09508500")
    min_cfs = config.get("min_cfs", 600)

    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting Salt River report")
    print(f"  Gauge site : {site_id}")
    print(f"  Float min  : {min_cfs} CFS")

    init_db()

    # Grab yesterday's data BEFORE inserting today's reading
    yesterday = get_yesterday_reading()

    print(f"  Fetching USGS data...")
    reading = get_latest_reading(site_id)
    print(f"  CFS: {reading.get('cfs')}  |  Height: {reading.get('height_ft')} ft")

    insert_reading(
        timestamp  = reading.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        cfs        = reading.get("cfs"),
        height_ft  = reading.get("height_ft"),
        fetched_at = reading["fetched_at"],
    )

    history = get_recent_readings(days=7)
    alerts  = check_alerts(reading, yesterday, config)

    if alerts:
        print(f"  Alerts ({len(alerts)}):")
        for a in alerts:
            print(f"    [{a['level'].upper()}] {a['message']}")

    html    = build_html_email(reading, history, alerts, config)
    subject = build_subject(reading.get("cfs"), alerts, min_cfs)

    print(f"  Subject: {subject}")
    send_email(subject, html, config)
    print("Done.")


if __name__ == "__main__":
    main()
