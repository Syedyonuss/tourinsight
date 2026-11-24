"""Open-Meteo connector: live forecast and long-run historical monthly normals."""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from typing import Any
import httpx
from backend.db import connect

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
APP_AGENT = "TourInsightLocal/1.0 (local tourism research application)"


def _cache_get(key: str, max_age_hours: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT fetched_at,payload_json FROM weather_cache WHERE cache_key=?", (key,)).fetchone()
    if not row:
        return None
    try:
        fetched = datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - fetched > timedelta(hours=max_age_hours):
            return None
        return json.loads(row["payload_json"])
    except Exception:
        return None


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO weather_cache(cache_key,fetched_at,payload_json) VALUES(?,?,?) ON CONFLICT(cache_key) DO UPDATE SET fetched_at=excluded.fetched_at,payload_json=excluded.payload_json",
                     (key, datetime.now(timezone.utc).isoformat(), json.dumps(payload)))
        conn.commit()


async def monthly_climate(destination: dict[str, Any], month: int) -> dict[str, Any]:
    """Compute 2016-2025 monthly climatology. Never labels this as a forecast."""
    key = f"climate:{destination['slug']}:{month}:2016-2025"
    cached = _cache_get(key, 24 * 30)
    if cached:
        return cached
    params = {
        "latitude": destination["latitude"], "longitude": destination["longitude"],
        "start_date": "2016-01-01", "end_date": "2025-12-31",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Asia/Kolkata",
    }
    try:
        async with httpx.AsyncClient(timeout=28.0, headers={"User-Agent": APP_AGENT}) as client:
            response = await client.get(ARCHIVE_URL, params=params)
            response.raise_for_status()
            raw = response.json()
        daily = raw.get("daily", {})
        dates = daily.get("time", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        rain = daily.get("precipitation_sum", [])
        high_values, low_values, rain_values = [], [], []
        for i, day in enumerate(dates):
            if int(day[5:7]) != month:
                continue
            if i < len(highs) and highs[i] is not None: high_values.append(float(highs[i]))
            if i < len(lows) and lows[i] is not None: low_values.append(float(lows[i]))
            if i < len(rain) and rain[i] is not None: rain_values.append(float(rain[i]))
        if not high_values or not low_values:
            raise ValueError("Historical climate response did not contain the requested month.")
        avg_high = sum(high_values) / len(high_values)
        avg_low = sum(low_values) / len(low_values)
        avg_rain = (sum(rain_values) / len(rain_values)) if rain_values else None
        wet_pct = (sum(1 for v in rain_values if v >= 1.0) / len(rain_values) * 100) if rain_values else None
        # Transparent general comfort heuristic; destination seasonality is scored separately.
        tmean = (avg_high + avg_low) / 2
        if 20 <= tmean <= 29: temp_score = 100
        elif 17 <= tmean < 20 or 29 < tmean <= 32: temp_score = 84
        elif 14 <= tmean < 17 or 32 < tmean <= 35: temp_score = 65
        else: temp_score = max(25, 65 - abs(tmean - 24) * 4)
        rain_score = 100 - min(75, (wet_pct or 0) * 0.85)
        # Waterfall destinations benefit from seasonal rainfall, rather than being penalized by it.
        if destination["slug"] == "jog-falls": rain_score = min(100, 35 + (wet_pct or 0) * 0.9)
        score = round(temp_score * 0.45 + rain_score * 0.55, 1)
        payload = {"available": True, "score": score, "avg_max_c": round(avg_high,1), "avg_min_c": round(avg_low,1),
                   "avg_daily_rain_mm": round(avg_rain,2) if avg_rain is not None else None,
                   "wet_days_pct": round(wet_pct,1) if wet_pct is not None else None,
                   "period": "2016–2025", "source": "Open-Meteo Historical Weather API (ERA5/ERA5-Land reanalysis)",
                   "basis": "Historical monthly climate normal; not a date-specific forecast."}
        _cache_set(key, payload)
        return payload
    except Exception as exc:
        return {"available": False, "score": None, "source": "Open-Meteo Historical Weather API",
                "error": str(exc)[:240], "basis": "Historical climate data unavailable; weather weight is excluded from the recommendation calculation."}


async def live_weather(destination: dict[str, Any]) -> dict[str, Any]:
    key = f"live:{destination['slug']}"
    cached = _cache_get(key, 1)
    if cached:
        return cached
    params = {"latitude": destination["latitude"], "longitude": destination["longitude"],
              "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m,weather_code",
              "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
              "forecast_days": 7, "timezone": "Asia/Kolkata"}
    try:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": APP_AGENT}) as client:
            response = await client.get(FORECAST_URL, params=params)
            response.raise_for_status()
            raw = response.json()
        payload = {"available": True, "current": raw.get("current", {}), "daily": raw.get("daily", {}),
                   "source": "Open-Meteo Forecast API", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                   "timezone": raw.get("timezone", "Asia/Kolkata")}
        _cache_set(key, payload)
        return payload
    except Exception as exc:
        return {"available": False, "source": "Open-Meteo Forecast API", "error": str(exc)[:240],
                "message": "Live weather could not be retrieved. No live conditions are being inferred."}
