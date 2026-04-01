"""
Backfill historical daily CFS values from the USGS daily collection.
Called automatically by main.py when a chart year is missing data.

USGS daily endpoint returns one mean-discharge record per day.
"""

import requests
from datetime import date

USGS_DAILY_URL = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/daily/items"
PARAM_CFS  = "00060"
STAT_MEAN  = "00003"   # daily mean discharge


def _fetch_year(site_id: str, year: int) -> list[dict]:
    """
    Fetch daily mean CFS for an entire year (or year-to-date for the current year).
    Returns a list of {"date": "YYYY-MM-DD", "cfs": float}.
    """
    start = f"{year}-01-01"
    end   = min(f"{year}-12-31", date.today().isoformat())

    if start > date.today().isoformat():
        return []

    params = {
        "monitoring_location_id": f"USGS-{site_id}",
        "parameter_code": PARAM_CFS,
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
        day = ts[:10]                    # keep only YYYY-MM-DD
        cfs = float(raw_val)
        # Keep one value per day (mean preferred; take first if duplicates)
        if day not in results:
            results[day] = cfs

    return [{"date": d, "cfs": c} for d, c in sorted(results.items())]


def ensure_historical_data(site_id: str, years: list[int], db) -> None:
    """
    For each year in `years`, fetch and store daily CFS if data is sparse or missing.
    `db` is the db module (passed in to avoid circular imports).
    """
    today = date.today()

    for year in years:
        existing = db.count_daily_values_for_year(year)

        # How many days should exist for this year?
        if year < today.year:
            expected = 366 if _is_leap(year) else 365
        else:
            expected = (today - date(year, 1, 1)).days + 1

        # Fetch if we're missing more than 7 days worth of data
        if existing < expected - 7:
            print(f"  Backfilling {year}: have {existing}, expect ~{expected} — fetching...")
            records = _fetch_year(site_id, year)
            for r in records:
                db.upsert_daily_value(r["date"], r["cfs"], None)
            print(f"    Stored {len(records)} records for {year}.")
        else:
            print(f"  {year}: {existing} daily records (up to date).")


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
