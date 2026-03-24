from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import requests


@dataclass
class WeatherSnapshot:
    location_name: str
    temperature_c: float
    humidity_pct: int
    rain_probability_pct: int
    wind_speed_kmh: float
    weather_code: int
    condition: str


class OpenMeteoWeatherService:
    GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    _code_to_condition: Dict[int, str] = {
        0: "clear",
        1: "clear",
        2: "cloudy",
        3: "cloudy",
        45: "overcast",
        48: "overcast",
        51: "humid",
        53: "humid",
        55: "humid",
        61: "rain_threat",
        63: "rain_threat",
        65: "rain_threat",
        80: "rain_threat",
        81: "rain_threat",
        82: "rain_threat",
        95: "rain_threat",
    }

    def __init__(self, timeout_seconds: int = 12) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_current(self, location_query: str) -> Optional[WeatherSnapshot]:
        if not location_query.strip():
            return None

        geo = requests.get(
            self.GEOCODE_URL,
            params={
                "name": location_query,
                "count": 1,
                "language": "en",
                "format": "json",
            },
            timeout=self.timeout_seconds,
        ).json()
        results = geo.get("results") or []
        if not results:
            return None

        top = results[0]
        latitude = top.get("latitude")
        longitude = top.get("longitude")
        if latitude is None or longitude is None:
            return None

        current = requests.get(
            self.FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,relative_humidity_2m,"
                    "precipitation_probability,weather_code,wind_speed_10m"
                ),
            },
            timeout=self.timeout_seconds,
        ).json().get("current", {})

        weather_code = int(current.get("weather_code", 1))
        condition = self._code_to_condition.get(weather_code, "cloudy")
        return WeatherSnapshot(
            location_name=str(top.get("name", location_query)),
            temperature_c=float(current.get("temperature_2m", 28.0)),
            humidity_pct=int(current.get("relative_humidity_2m", 60)),
            rain_probability_pct=int(current.get("precipitation_probability", 10)),
            wind_speed_kmh=float(current.get("wind_speed_10m", 10.0)),
            weather_code=weather_code,
            condition=condition,
        )

