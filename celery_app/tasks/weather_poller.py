"""
Weather poller — fetches marine weather from OpenWeatherMap for active vessel positions.

Runs every 30 minutes via Celery beat.
Uses the One Call API 3.0 (free tier: 1000 calls/day).
"""

import os
import time

import requests
import structlog

from celery_app.app import app
from celery_app.db import execute

log = structlog.get_logger()

OWM_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OWM_URL = "https://api.openweathermap.org/data/3.0/onecall"

# Grid resolution: fetch one point per N-degree cell to avoid hitting API rate limits
GRID_DEGREE = 5.0
# Only fetch weather within this many km of an active vessel
VESSEL_RADIUS_KM = 800


@app.task(name="celery_app.tasks.weather_poller.poll_all_regions")
def poll_all_regions():
    if not OWM_API_KEY:
        log.warning("openweather_api_key_missing")
        return

    # Get distinct grid cells containing active vessels
    rows = execute(
        """
        SELECT
            FLOOR(lat / :grid) * :grid AS grid_lat,
            FLOOR(lon / :grid) * :grid AS grid_lon
        FROM (
            SELECT DISTINCT ON (mmsi)
                lat, lon
            FROM vessel_positions
            WHERE time > NOW() - INTERVAL '2 hours'
            ORDER BY mmsi, time DESC
        ) recent
        GROUP BY grid_lat, grid_lon
        """,
        {"grid": GRID_DEGREE},
    ).fetchall()

    log.info("weather_poll_started", grid_cells=len(rows))
    for grid_lat, grid_lon in rows:
        fetch_weather.delay(float(grid_lat), float(grid_lon))


@app.task(
    name="celery_app.tasks.weather_poller.fetch_weather",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def fetch_weather(self, lat: float, lon: float):
    try:
        resp = requests.get(
            OWM_URL,
            params={
                "lat": lat,
                "lon": lon,
                "exclude": "minutely,hourly,daily,alerts",
                "appid": OWM_API_KEY,
                "units": "metric",
            },
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.exception("weather_fetch_failed", lat=lat, lon=lon)
        raise self.retry(exc=exc)

    data = resp.json()
    current = data.get("current", {})

    wind_speed = current.get("wind_speed")  # m/s
    wind_dir = current.get("wind_deg")
    pressure = current.get("pressure")
    description = (current.get("weather") or [{}])[0].get("description", "")

    # Wave data from "swell" if available (requires Marine endpoint — use wind proxy)
    # OpenWeatherMap doesn't provide wave height on free tier; we store wind-derived proxy
    wave_height_proxy = _wind_to_wave_proxy(wind_speed)

    storm_alert = wind_speed is not None and wind_speed > 20.0

    execute(
        """
        INSERT INTO weather_snapshots
            (time, lat, lon, position, wave_height_m, wind_speed_ms,
             wind_direction, pressure_hpa, storm_alert, description)
        VALUES
            (NOW(), :lat, :lon,
             ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
             :wave, :wind, :wind_dir, :pressure, :storm, :desc)
        """,
        {
            "lat": lat, "lon": lon,
            "wave": wave_height_proxy,
            "wind": wind_speed,
            "wind_dir": wind_dir,
            "pressure": pressure,
            "storm": storm_alert,
            "desc": description,
        },
    )

    log.info("weather_stored", lat=lat, lon=lon, wind=wind_speed, wave=wave_height_proxy)


def _wind_to_wave_proxy(wind_ms: float | None) -> float | None:
    """
    Rough empirical proxy: Beaufort-based significant wave height estimate.
    Only used when dedicated wave data is unavailable.
    """
    if wind_ms is None:
        return None
    # Simplified: Hs ≈ 0.0248 * U^2 (U in m/s, deep water approximation)
    return round(0.0248 * wind_ms ** 2, 2)
