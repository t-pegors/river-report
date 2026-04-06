"""
Entry point for the river daily report.
Run from the project root: python src/main.py [--config config.json]
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Allow sibling imports when run as a script
sys.path.insert(0, str(Path(__file__).parent))

from fetch import get_latest_reading
from db import (init_db, insert_reading, get_recent_readings,
                get_yesterday_reading, upsert_daily_value,
                get_daily_values_for_year)
from alerts import check_alerts
from backfill import ensure_historical_data
from chart import generate_chart
from weather import get_weather
from report import build_html_email, send_email

PROJECT_ROOT = Path(__file__).parent.parent


def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return json.load(f)


def build_subject(current: dict, alerts: list[dict], config: dict) -> str:
    report_name = config.get("report_name", "River Report")
    gauge_unit  = config.get("gauge_unit", "cfs")
    min_cfs     = config.get("min_cfs")

    cfs       = current.get("cfs")
    height_ft = current.get("height_ft")

    has_alert = any(a["level"] == "alert" for a in alerts)
    alert_tag = " — ⚠️ DRAMATIC CHANGE" if has_alert else ""

    if gauge_unit == "height_ft":
        if height_ft is not None:
            reading_part = f"{height_ft:.2f} ft"
        else:
            reading_part = "N/A"
        return f"{report_name} — {reading_part}{alert_tag}"
    else:
        # CFS gauge — include float day status when min_cfs is configured
        if cfs is not None:
            cfs_part = f"{cfs:.0f} CFS"
            if min_cfs is not None:
                float_status = "FLOAT DAY ✓" if cfs >= min_cfs else "Not a float day"
                return f"{report_name} — {float_status} ({cfs_part}){alert_tag}"
            return f"{report_name} — {cfs_part}{alert_tag}"
        return f"{report_name} — Data unavailable{alert_tag}"


def main():
    parser = argparse.ArgumentParser(description="Send a daily river/lake report email.")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config.json",
        help="Path to the JSON config file (default: config.json)",
    )
    args = parser.parse_args()

    config_path = args.config if args.config.is_absolute() else PROJECT_ROOT / args.config
    config      = load_config(config_path)

    site_id     = config.get("gauge_site", "09502000")
    gauge_unit  = config.get("gauge_unit", "cfs")
    min_cfs     = config.get("min_cfs")
    chart_years = config.get("chart_years", [])
    db_path     = PROJECT_ROOT / config.get("db_path", "data/river.db")
    today_str   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting report: {config.get('report_name', site_id)}")
    print(f"  Gauge site  : {site_id}")
    print(f"  Gauge unit  : {gauge_unit}")
    print(f"  DB path     : {db_path}")
    print(f"  Chart years : {chart_years}")

    init_db(db_path)

    # Grab yesterday's data BEFORE inserting today's reading
    yesterday = get_yesterday_reading()

    print("  Fetching USGS data...")
    reading = get_latest_reading(site_id)
    print(f"  CFS: {reading.get('cfs')}  |  Height: {reading.get('height_ft')} ft")

    insert_reading(
        timestamp  = reading.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        cfs        = reading.get("cfs"),
        height_ft  = reading.get("height_ft"),
        fetched_at = reading["fetched_at"],
    )
    # Keep daily_values current for the chart
    if reading.get("cfs") is not None or reading.get("height_ft") is not None:
        upsert_daily_value(today_str, reading.get("cfs"), reading.get("height_ft"))

    history = get_recent_readings(days=7)
    alerts  = check_alerts(reading, yesterday, config)

    if alerts:
        print(f"  Alerts ({len(alerts)}):")
        for a in alerts:
            print(f"    [{a['level'].upper()}] {a['message']}")

    # ── chart ────────────────────────────────────────────────────────────────
    chart_png = None
    if chart_years:
        import db as db_module
        ensure_historical_data(site_id, chart_years, db_module, gauge_unit)
        year_data    = {yr: get_daily_values_for_year(yr) for yr in chart_years}
        current_year = max(chart_years)
        try:
            chart_png = generate_chart(
                year_data,
                min_cfs,
                current_year,
                gauge_unit  = gauge_unit,
                chart_title = config.get("chart_title", "Year over Year"),
            )
            print(f"  Chart generated ({len(chart_png) // 1024} KB).")
        except Exception as e:
            print(f"  Chart generation failed (non-fatal): {e}")

    lat = config.get("weather_lat")
    lon = config.get("weather_lon")
    weather = None
    if lat is not None and lon is not None:
        print("  Fetching weather forecast...")
        weather = get_weather(lat, lon)
        if weather:
            print(f"  Sunrise: {weather['sunrise']}  Sunset: {weather['sunset']}  "
                  f"({len(weather['hourly'])} daylight hours)")

    html    = build_html_email(reading, history, alerts, config,
                               chart_png=chart_png, weather=weather)
    subject = build_subject(reading, alerts, config)

    print(f"  Subject: {subject}")
    send_email(subject, html, config, chart_png=chart_png)
    print("Done.")


if __name__ == "__main__":
    main()
