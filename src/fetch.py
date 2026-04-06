"""
Fetch current river data from the USGS Water Data OGC API.
Replaces the legacy NWIS instantaneous-values service (waterservices.usgs.gov),
which is being phased out.

Docs / Swagger UI:
  https://api.waterdata.usgs.gov/ogcapi/v0/openapi?f=html

Gauge 09508500 — Salt River below Stewart Mountain Dam, AZ
"""

import requests
from datetime import datetime, timezone

USGS_LATEST_URL = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/latest-continuous/items"

# USGS parameter codes
PARAM_CFS       = "00060"   # Discharge, cubic feet per second
PARAM_HEIGHT    = "00065"   # Gauge height, feet
PARAM_ELEVATION = "00062"   # Reservoir/lake water surface elevation, feet above datum


def get_latest_reading(site_id: str) -> dict:
    """
    Fetch the most recent CFS and gauge height for the given USGS site.

    site_id should be the bare numeric ID (e.g. "09508500"); the required
    "USGS-" prefix is added here automatically.

    Returns a dict with keys: cfs, height_ft, timestamp, fetched_at
    Raises requests.HTTPError on API failure.
    """
    params = {
        "monitoring_location_id": f"USGS-{site_id}",
        "f": "json",
    }
    response = requests.get(USGS_LATEST_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    result = {
        "cfs":        None,
        "height_ft":  None,
        "timestamp":  None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        param_code = props.get("parameter_code")
        raw_val    = props.get("value")
        ts         = props.get("time")

        if raw_val is None:
            continue

        if param_code == PARAM_CFS:
            result["cfs"]       = float(raw_val)
            result["timestamp"] = ts
        elif param_code in (PARAM_HEIGHT, PARAM_ELEVATION):
            result["height_ft"] = float(raw_val)
            if result["timestamp"] is None:
                result["timestamp"] = ts

    return result
