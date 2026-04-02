"""
Fetch hourly weather forecast and sunrise/sunset from Open-Meteo.
Free, no API key required.

Location: Salt River below Stewart Mountain Dam, AZ
Coordinates sourced directly from USGS site 09502000.
"""

import requests
from datetime import datetime

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather interpretation codes → emoji + short label
# https://open-meteo.com/en/docs#weathervariables
WMO_CODES = {
    0:  ("☀️",  "Clear"),
    1:  ("🌤️", "Mostly Clear"),
    2:  ("⛅",  "Partly Cloudy"),
    3:  ("☁️",  "Overcast"),
    45: ("🌫️", "Fog"),
    48: ("🌫️", "Icy Fog"),
    51: ("🌦️", "Light Drizzle"),
    53: ("🌦️", "Drizzle"),
    55: ("🌧️", "Heavy Drizzle"),
    61: ("🌧️", "Light Rain"),
    63: ("🌧️", "Rain"),
    65: ("🌧️", "Heavy Rain"),
    71: ("🌨️", "Light Snow"),
    73: ("🌨️", "Snow"),
    75: ("❄️",  "Heavy Snow"),
    77: ("🌨️", "Snow Grains"),
    80: ("🌦️", "Light Showers"),
    81: ("🌧️", "Showers"),
    82: ("⛈️",  "Heavy Showers"),
    85: ("🌨️", "Snow Showers"),
    86: ("❄️",  "Heavy Snow Showers"),
    95: ("⛈️",  "Thunderstorm"),
    96: ("⛈️",  "Thunderstorm w/ Hail"),
    99: ("⛈️",  "Thunderstorm w/ Hail"),
}


def _wmo(code: int) -> tuple[str, str]:
    """Return (emoji, label) for a WMO weather code."""
    return WMO_CODES.get(code, ("🌡️", "Unknown"))


def _parse_time(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str)


def get_weather(lat: float, lon: float) -> dict | None:
    """
    Fetch today's hourly forecast and sunrise/sunset for the given coordinates.

    Returns a dict with:
      sunrise      — "6:14 AM"
      sunset       — "7:33 PM"
      hourly       — list of dicts for each daylight hour:
                     {hour_label, emoji, condition, temp_f, precip_pct, wind_mph}
    Returns None on any API failure (weather is non-critical).
    """
    params = {
        "latitude":          lat,
        "longitude":         lon,
        "hourly":            "temperature_2m,weather_code,wind_speed_10m,precipitation_probability",
        "daily":             "sunrise,sunset",
        "temperature_unit":  "fahrenheit",
        "wind_speed_unit":   "mph",
        "timezone":          "America/Phoenix",
        "forecast_days":     1,
    }

    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  Weather fetch failed (non-fatal): {e}")
        return None

    try:
        daily   = data["daily"]
        hourly  = data["hourly"]

        sunrise_dt = _parse_time(daily["sunrise"][0])
        sunset_dt  = _parse_time(daily["sunset"][0])

        sunrise_label = sunrise_dt.strftime("%-I:%M %p")
        sunset_label  = sunset_dt.strftime("%-I:%M %p")

        times      = hourly["time"]
        temps      = hourly["temperature_2m"]
        codes      = hourly["weather_code"]
        winds      = hourly["wind_speed_10m"]
        precips    = hourly["precipitation_probability"]

        hours = []
        for i, ts in enumerate(times):
            dt = _parse_time(ts)
            # Include hours that fall within the daylight window
            if dt.hour < sunrise_dt.hour or dt.hour > sunset_dt.hour:
                continue
            emoji, condition = _wmo(codes[i])
            hours.append({
                "hour_label":  dt.strftime("%-I %p"),
                "emoji":       emoji,
                "condition":   condition,
                "temp_f":      round(temps[i]),
                "precip_pct":  round(precips[i]),
                "wind_mph":    round(winds[i]),
            })

        return {
            "sunrise": sunrise_label,
            "sunset":  sunset_label,
            "hourly":  hours,
        }

    except Exception as e:
        print(f"  Weather parse failed (non-fatal): {e}")
        return None
