"""
Backfill historical daily values from the USGS daily collection.
Called automatically by main.py when a chart year is missing data.

USGS daily endpoint returns one mean record per day.
Supports CFS (discharge), gauge height (00065), and lake/reservoir elevation (00062).
"""

import requests
from datetime import date

USGS_DAILY_URL  = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/daily/items"
PARAM_CFS       = "00060"   # Discharge, cubic feet per second
PARAM_HEIGHT    = "00065"   # Gauge height, feet
PARAM_ELEVATION = "00062"   # Reservoir/lake water surface elevation, feet above datum
STAT_MEAN       = "00003"   # daily mean


def _fetch_year_with_param(site_id: str, param_code: str, start: str, end: str) -> list[float | None]:
    """
    Raw fetch: returns a dict of {date_str: float} for the given parameter code.
    """
    params = {
        "monitoring_location_id": f"USGS-{site_id}",
        "parameter_code": param_code,
        "statistic_id":   STAT_MEAN,
        "time":           f"{start}/{end}",
        "limit":          400,
        "f":              "json",
    }
    resp = requests.get(USGS_DAILY_URL, params=params, timeout=30)
    resp.raise_for_status()

    results = {}
    for feature in resp.json().get("features", []):
        props   = feature.get("properties", {})
        raw_val = props.get("value")
        ts      = props.get("time", "")
        if raw_val is None or not ts:
            continue
        day = ts[:10]
        if day not in results:
            results[day] = float(raw_val)
    return results


def _fetch_year(site_id: str, year: int, gauge_unit: str = "cfs") -> list[dict]:
    """
    Fetch daily mean values for an entire year (or year-to-date for the current year).

    For height_ft gauges, tries reservoir elevation (00062) first, then stream gauge
    height (00065) as a fallback — handles both lake and stream gauges transparently.

    Returns a list of {"date": "YYYY-MM-DD", "cfs": float} or
                      {"date": "YYYY-MM-DD", "height_ft": float}.
    """
    start = f"{year}-01-01"
    end   = min(f"{year}-12-31", date.today().isoformat())

    if start > date.today().isoformat():
        return []

    if gauge_unit == "height_ft":
        # Lakes/reservoirs use 00062; fall back to 00065 for stream height gauges
        results = _fetch_year_with_param(site_id, PARAM_ELEVATION, start, end)
        if not results:
            results = _fetch_year_with_param(site_id, PARAM_HEIGHT, start, end)
        return [{"date": d, "height_ft": v} for d, v in sorted(results.items())]

    results = _fetch_year_with_param(site_id, PARAM_CFS, start, end)
    return [{"date": d, "cfs": v} for d, v in sorted(results.items())]


def ensure_historical_data(site_id: str, years: list[int], db, gauge_unit: str = "cfs") -> None:
    """
    For each year in `years`, fetch and store daily values if data is sparse or missing.
    `db` is the db module (passed in to avoid circular imports).
    gauge_unit: "cfs" or "height_ft" — controls which USGS parameter is fetched and stored.
    """
    today = date.today()

    for year in years:
        existing = db.count_daily_values_for_year(year)

        if year < today.year:
            expected = 366 if _is_leap(year) else 365
        else:
            expected = (today - date(year, 1, 1)).days + 1

        if existing < expected - 7:
            print(f"  Backfilling {year}: have {existing}, expect ~{expected} — fetching...")
            records = _fetch_year(site_id, year, gauge_unit)
            for r in records:
                if gauge_unit == "height_ft":
                    db.upsert_daily_value(r["date"], None, r["height_ft"])
                else:
                    db.upsert_daily_value(r["date"], r["cfs"], None)
            print(f"    Stored {len(records)} records for {year}.")
        else:
            print(f"  {year}: {existing} daily records (up to date).")


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
