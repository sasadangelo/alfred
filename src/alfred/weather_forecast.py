"""Weather forecasts and place search from Open-Meteo (free, no API key).

Functions return structured data; how to phrase it (umbrella, running clothes) is up to the
caller. Weather alerts are computed here only, so every caller applies the same thresholds.
"""

from datetime import date, time, timedelta
from typing import Any

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
REQUEST_TIMEOUT_SECONDS = 10
MAX_FORECAST_DAYS = 16

DAILY_FIELDS = (
    "weather_code",
    "temperature_2m_min",
    "temperature_2m_max",
    "apparent_temperature_min",
    "apparent_temperature_max",
    "precipitation_probability_max",
    "precipitation_sum",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "uv_index_max",
    "sunrise",
    "sunset",
)
HOURLY_FIELDS = (
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation_probability",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
    "wind_gusts_10m",
)
CURRENT_FIELDS = (
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
    "wind_gusts_10m",
)

# Alert thresholds, kept in one place.
RAIN_PROBABILITY_ALERT = 40  # %
RAIN_AMOUNT_ALERT = 0.5  # mm per day
WIND_ALERT = 30  # km/h sustained
GUST_ALERT = 50  # km/h
HEAT_ALERT = 32  # °C max
FROST_ALERT = 0  # °C min
UV_ALERT = 6

WEATHER_CODES: dict[int, str] = {
    0: "sereno",
    1: "prevalentemente sereno",
    2: "parzialmente nuvoloso",
    3: "coperto",
    45: "nebbia",
    48: "nebbia con brina",
    51: "pioviggine leggera",
    53: "pioviggine",
    55: "pioviggine intensa",
    56: "pioviggine gelata",
    57: "pioviggine gelata intensa",
    61: "pioggia debole",
    63: "pioggia",
    65: "pioggia forte",
    66: "pioggia gelata",
    67: "pioggia gelata forte",
    71: "neve debole",
    73: "neve",
    75: "neve forte",
    77: "granelli di neve",
    80: "rovesci deboli",
    81: "rovesci",
    82: "rovesci violenti",
    85: "rovesci di neve",
    86: "rovesci di neve forti",
    95: "temporale",
    96: "temporale con grandine",
    99: "temporale con grandine forte",
}
FOG_CODES = {45, 48}
SNOW_CODES = {71, 73, 75, 77, 85, 86}
STORM_CODES = {95, 96, 99}
ICE_CODES = {56, 57, 66, 67}


class WeatherError(RuntimeError):
    """A weather service failure explained in terms the user can act on."""


def describe_weather_code(code: int | None) -> str:
    """Return the Italian description of a WMO weather code."""
    if code is None:
        return "non disponibile"
    return WEATHER_CODES.get(int(code), "condizioni variabili")


def _get(session: Any, url: str, params: dict[str, Any], what: str) -> dict[str, Any]:
    try:
        response = (session or requests).get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as error:
        raise WeatherError(f"Could not {what}: the weather service is unreachable ({error}).") from error
    if response.status_code >= 400:
        try:
            reason = str(response.json().get("reason", ""))
        except ValueError:
            reason = ""
        raise WeatherError(f"Could not {what} ({response.status_code}): {reason or 'request rejected'}.")
    data: dict[str, Any] = response.json()
    return data


def find_place(name: str, *, count: int = 5, session: Any | None = None) -> list[dict[str, Any]]:
    """Search places by name (town or city, not street addresses), best matches first."""
    if not name.strip():
        raise ValueError("name must not be empty")
    if not 1 <= count <= 20:
        raise ValueError("count must be between 1 and 20")
    data = _get(
        session,
        GEOCODING_URL,
        {"name": name.strip(), "count": count, "language": "it", "format": "json"},
        "search the place",
    )
    return [
        {
            "name": str(item.get("name", "")),
            "province": str(item.get("admin2", "")),
            "region": str(item.get("admin1", "")),
            "country": str(item.get("country", "")),
            "latitude": float(item["latitude"]),
            "longitude": float(item["longitude"]),
            "timezone": str(item.get("timezone", "")),
            "population": int(item.get("population") or 0),
        }
        for item in data.get("results", [])
    ]


def _day_alerts(day: dict[str, Any]) -> list[str]:
    alerts: list[str] = []
    probability = day["precipitation_probability"] or 0
    amount = day["precipitation_mm"] or 0
    if probability >= RAIN_PROBABILITY_ALERT or amount >= RAIN_AMOUNT_ALERT:
        alerts.append(f"pioggia: probabilità {probability}%, {amount} mm previsti")
    wind, gusts = day["wind_max_kmh"] or 0, day["gusts_max_kmh"] or 0
    if wind >= WIND_ALERT or gusts >= GUST_ALERT:
        alerts.append(f"vento: fino a {wind} km/h, raffiche fino a {gusts} km/h")
    code = day["weather_code"]
    if code in FOG_CODES:
        alerts.append("nebbia")
    if code in SNOW_CODES:
        alerts.append("neve")
    if code in STORM_CODES:
        alerts.append("temporali")
    if code in ICE_CODES:
        alerts.append("pioggia o pioviggine gelata: strade scivolose")
    if day["temp_max"] is not None and day["temp_max"] >= HEAT_ALERT:
        alerts.append(f"caldo: massima {day['temp_max']}°C")
    if day["temp_min"] is not None and day["temp_min"] <= FROST_ALERT:
        alerts.append(f"gelo: minima {day['temp_min']}°C")
    if day["uv_index_max"] is not None and day["uv_index_max"] >= UV_ALERT:
        alerts.append(f"UV alto: indice {day['uv_index_max']}")
    return alerts


def _value(series: dict[str, list[Any]], field: str, index: int) -> Any:
    values = series.get(field) or []
    return values[index] if index < len(values) else None


def _parse_hour(value: str | None) -> time | None:
    return time.fromisoformat(value) if value else None


def get_forecast(
    latitude: float,
    longitude: float,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    hour_from: str | None = None,
    hour_to: str | None = None,
    today: date | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """Return daily forecasts for [start_date, end_date] in the place's local time.

    With ``hour_from``/``hour_to`` (``HH:MM``, inclusive) each day also lists its hourly forecast
    in that window, e.g. 07:00-09:00 for a morning run. Current conditions are included when the
    range starts today.
    """
    today = today or date.today()
    start_date = start_date or today
    end_date = end_date or start_date
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("latitude/longitude out of range")
    if end_date < start_date:
        raise ValueError("end_date must not be before start_date")
    if start_date < today or end_date > today + timedelta(days=MAX_FORECAST_DAYS - 1):
        raise ValueError(f"forecasts cover today and the next {MAX_FORECAST_DAYS - 1} days only")
    first_hour, last_hour = _parse_hour(hour_from), _parse_hour(hour_to)
    if (first_hour is None) != (last_hour is None):
        raise ValueError("hour_from and hour_to must be given together")
    if first_hour and last_hour and last_hour < first_hour:
        raise ValueError("hour_to must not be before hour_from")

    params: dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "auto",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": ",".join(DAILY_FIELDS),
    }
    if first_hour:
        params["hourly"] = ",".join(HOURLY_FIELDS)
    if start_date == today:
        params["current"] = ",".join(CURRENT_FIELDS)
    data = _get(session, FORECAST_URL, params, "get the forecast")

    daily: dict[str, list[Any]] = data.get("daily", {})
    hourly: dict[str, list[Any]] = data.get("hourly", {})
    hours_by_day: dict[str, list[dict[str, Any]]] = {}
    for index, stamp in enumerate(hourly.get("time", [])):
        day_text, _, clock = str(stamp).partition("T")
        if first_hour and last_hour and first_hour <= time.fromisoformat(clock) <= last_hour:
            code = _value(hourly, "weather_code", index)
            hours_by_day.setdefault(day_text, []).append(
                {
                    "time": clock,
                    "condition": describe_weather_code(code),
                    "temperature": _value(hourly, "temperature_2m", index),
                    "feels_like": _value(hourly, "apparent_temperature", index),
                    "humidity": _value(hourly, "relative_humidity_2m", index),
                    "precipitation_probability": _value(hourly, "precipitation_probability", index),
                    "precipitation_mm": _value(hourly, "precipitation", index),
                    "wind_kmh": _value(hourly, "wind_speed_10m", index),
                    "gusts_kmh": _value(hourly, "wind_gusts_10m", index),
                }
            )

    days = []
    for index, day_text in enumerate(daily.get("time", [])):
        code = _value(daily, "weather_code", index)
        day: dict[str, Any] = {
            "date": day_text,
            "condition": describe_weather_code(code),
            "weather_code": code,
            "temp_min": _value(daily, "temperature_2m_min", index),
            "temp_max": _value(daily, "temperature_2m_max", index),
            "feels_min": _value(daily, "apparent_temperature_min", index),
            "feels_max": _value(daily, "apparent_temperature_max", index),
            "precipitation_probability": _value(daily, "precipitation_probability_max", index),
            "precipitation_mm": _value(daily, "precipitation_sum", index),
            "wind_max_kmh": _value(daily, "wind_speed_10m_max", index),
            "gusts_max_kmh": _value(daily, "wind_gusts_10m_max", index),
            "uv_index_max": _value(daily, "uv_index_max", index),
            "sunrise": str(_value(daily, "sunrise", index) or "").partition("T")[2],
            "sunset": str(_value(daily, "sunset", index) or "").partition("T")[2],
        }
        day["alerts"] = _day_alerts(day)
        if first_hour:
            day["hours"] = hours_by_day.get(day_text, [])
        days.append(day)

    result: dict[str, Any] = {
        "location": {
            "latitude": data.get("latitude", latitude),
            "longitude": data.get("longitude", longitude),
            "timezone": data.get("timezone", ""),
        },
        "days": days,
    }
    if current := data.get("current"):
        result["current"] = {
            "time": str(current.get("time", "")).partition("T")[2],
            "condition": describe_weather_code(current.get("weather_code")),
            "temperature": current.get("temperature_2m"),
            "feels_like": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation_mm": current.get("precipitation"),
            "wind_kmh": current.get("wind_speed_10m"),
            "gusts_kmh": current.get("wind_gusts_10m"),
        }
    return result
