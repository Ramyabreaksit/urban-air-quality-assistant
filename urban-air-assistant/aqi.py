"""Air-quality data access (Open-Meteo, no API key needed) and AQI helpers."""
from __future__ import annotations

import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
TIMEOUT = 10

# (upper bound, label, level 0-5) based on the US AQI scale
AQI_BANDS = [
    (50, "Good", 0),
    (100, "Moderate", 1),
    (150, "Unhealthy for sensitive groups", 2),
    (200, "Unhealthy", 3),
    (300, "Very unhealthy", 4),
    (10_000, "Hazardous", 5),
]


class AirQualityError(Exception):
    """Raised when location or air-quality data cannot be fetched."""


def aqi_category(aqi: float) -> tuple[str, int]:
    """Return (label, level) for a US AQI value."""
    if aqi is None or aqi < 0:
        raise ValueError("AQI must be a non-negative number")
    for upper, label, level in AQI_BANDS:
        if aqi <= upper:
            return label, level
    return AQI_BANDS[-1][1], AQI_BANDS[-1][2]


def geocode(city: str) -> dict:
    """Resolve a city name to name/lat/lon."""
    try:
        r = requests.get(
            GEOCODE_URL,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        results = r.json().get("results")
    except (requests.RequestException, ValueError) as exc:
        raise AirQualityError("Could not look up that location right now.") from exc
    if not results:
        raise AirQualityError(f"No location found for '{city}'. Try a nearby city.")
    top = results[0]
    return {
        "name": ", ".join(p for p in (top.get("name"), top.get("admin1"), top.get("country")) if p),
        "lat": top["latitude"],
        "lon": top["longitude"],
    }


def fetch_air_quality(lat: float, lon: float) -> dict:
    """Current US AQI, PM2.5 and PM10 for a coordinate."""
    try:
        r = requests.get(
            AIR_URL,
            params={"latitude": lat, "longitude": lon, "current": "us_aqi,pm2_5,pm10"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        cur = r.json()["current"]
        aqi = cur["us_aqi"]
        if aqi is None:
            raise KeyError("us_aqi")
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise AirQualityError("Live air-quality data is unavailable for this location.") from exc
    label, level = aqi_category(aqi)
    return {
        "aqi": round(aqi),
        "pm2_5": cur.get("pm2_5"),
        "pm10": cur.get("pm10"),
        "category": label,
        "level": level,
    }
