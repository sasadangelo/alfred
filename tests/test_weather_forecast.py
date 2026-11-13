"""Tests for Open-Meteo weather forecasts and place search."""

from datetime import date
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from alfred import weather_forecast as weather

TODAY = date(2026, 11, 13)


def _response(payload: dict[str, Any], status: int = 200) -> Mock:
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    return response


def _forecast_payload(**daily_overrides: list[Any]) -> dict[str, Any]:
    daily: dict[str, list[Any]] = {
        "time": ["2026-11-15"],
        "weather_code": [95],
        "temperature_2m_min": [15.9],
        "temperature_2m_max": [17.9],
        "apparent_temperature_min": [14.9],
        "apparent_temperature_max": [18.3],
        "precipitation_probability_max": [80],
        "precipitation_sum": [3.9],
        "wind_speed_10m_max": [16.9],
        "wind_gusts_10m_max": [37.4],
        "uv_index_max": [2.0],
        "sunrise": ["2026-11-15T07:00"],
        "sunset": ["2026-11-15T16:55"],
    }
    daily.update(daily_overrides)
    return {
        "latitude": 41.76,
        "longitude": 12.25,
        "timezone": "Europe/Rome",
        "daily": daily,
        "hourly": {
            "time": ["2026-11-15T06:00", "2026-11-15T07:00", "2026-11-15T08:00", "2026-11-15T10:00"],
            "temperature_2m": [16.0, 16.3, 16.5, 17.0],
            "apparent_temperature": [14.5, 14.9, 15.2, 16.0],
            "relative_humidity_2m": [90, 88, 85, 80],
            "precipitation_probability": [60, 70, 74, 50],
            "precipitation": [0.2, 0.5, 0.3, 0.1],
            "weather_code": [61, 80, 3, 3],
            "wind_speed_10m": [15.0, 16.6, 16.1, 14.0],
            "wind_gusts_10m": [30.0, 33.0, 31.0, 25.0],
        },
    }


def test_find_place_returns_candidates_with_region() -> None:
    session = Mock()
    session.get.return_value = _response(
        {
            "results": [
                {
                    "name": "Bologna",
                    "admin2": "Provincia di Roma",
                    "admin1": "Lazio",
                    "country": "Italia",
                    "latitude": 41.77,
                    "longitude": 12.24,
                    "timezone": "Europe/Rome",
                    "population": 80000,
                }
            ]
        }
    )

    places = weather.find_place(" Bologna ", session=session)

    assert places == [
        {
            "name": "Bologna",
            "province": "Provincia di Roma",
            "region": "Lazio",
            "country": "Italia",
            "latitude": 41.77,
            "longitude": 12.24,
            "timezone": "Europe/Rome",
            "population": 80000,
        }
    ]
    assert session.get.call_args.kwargs["params"]["name"] == "Bologna"
    assert session.get.call_args.kwargs["params"]["language"] == "it"


def test_find_place_without_results_returns_empty_list() -> None:
    session = Mock()
    session.get.return_value = _response({})

    assert weather.find_place("Xyzzy", session=session) == []


def test_get_forecast_builds_days_alerts_and_hour_window() -> None:
    session = Mock()
    session.get.return_value = _response(_forecast_payload())

    result = weather.get_forecast(
        41.76,
        12.25,
        start_date=date(2026, 11, 15),
        hour_from="07:00",
        hour_to="08:00",
        today=TODAY,
        session=session,
    )

    params = session.get.call_args.kwargs["params"]
    assert params["start_date"] == params["end_date"] == "2026-11-15"
    assert "hourly" in params and "current" not in params
    day = result["days"][0]
    assert day["condition"] == "temporale"
    assert day["sunrise"] == "07:00"
    assert day["alerts"] == ["pioggia: probabilità 80%, 3.9 mm previsti", "temporali"]
    assert [hour["time"] for hour in day["hours"]] == ["07:00", "08:00"]
    assert day["hours"][0]["condition"] == "rovesci deboli"
    assert day["hours"][0]["feels_like"] == 14.9


def test_get_forecast_without_hours_skips_hourly_data() -> None:
    session = Mock()
    session.get.return_value = _response(_forecast_payload())

    result = weather.get_forecast(41.76, 12.25, start_date=date(2026, 11, 15), today=TODAY, session=session)

    assert "hourly" not in session.get.call_args.kwargs["params"]
    assert "hours" not in result["days"][0]


def test_get_forecast_includes_current_conditions_for_today() -> None:
    payload = _forecast_payload(time=["2026-11-13"])
    payload["current"] = {"time": "2026-11-13T10:00", "temperature_2m": 20.7, "weather_code": 3}
    session = Mock()
    session.get.return_value = _response(payload)

    result = weather.get_forecast(41.76, 12.25, today=TODAY, session=session)

    assert "current" in session.get.call_args.kwargs["params"]
    assert result["current"]["time"] == "10:00"
    assert result["current"]["condition"] == "coperto"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"wind_gusts_10m_max": [67.7], "weather_code": [3], "precipitation_probability_max": [10]}, "vento"),
        ({"temperature_2m_min": [-1.0], "weather_code": [0], "precipitation_probability_max": [0]}, "gelo"),
        ({"temperature_2m_max": [35.0], "weather_code": [0], "precipitation_probability_max": [0]}, "caldo"),
        ({"weather_code": [45], "precipitation_probability_max": [0], "precipitation_sum": [0]}, "nebbia"),
    ],
)
def test_alerts_follow_thresholds(overrides: dict[str, list[Any]], expected: str) -> None:
    session = Mock()
    session.get.return_value = _response(_forecast_payload(**overrides))

    day = weather.get_forecast(41.76, 12.25, start_date=date(2026, 11, 15), today=TODAY, session=session)["days"][0]

    assert any(alert.startswith(expected) for alert in day["alerts"])


def test_calm_day_has_no_alerts() -> None:
    session = Mock()
    session.get.return_value = _response(
        _forecast_payload(weather_code=[1], precipitation_probability_max=[5], precipitation_sum=[0.0])
    )

    day = weather.get_forecast(41.76, 12.25, start_date=date(2026, 11, 15), today=TODAY, session=session)["days"][0]

    assert day["alerts"] == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start_date": date(2026, 11, 12)}, "next 15 days"),
        ({"start_date": date(2026, 11, 13), "end_date": date(2026, 11, 29)}, "next 15 days"),
        ({"start_date": date(2026, 11, 15), "end_date": date(2026, 11, 14)}, "end_date"),
        ({"hour_from": "07:00"}, "together"),
        ({"hour_from": "09:00", "hour_to": "07:00"}, "hour_to"),
    ],
)
def test_get_forecast_rejects_invalid_requests(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        weather.get_forecast(41.76, 12.25, today=TODAY, session=Mock(), **kwargs)


def test_service_errors_become_weather_errors() -> None:
    session = Mock()
    session.get.return_value = _response({"error": True, "reason": "Latitude must be in range"}, status=400)

    with pytest.raises(weather.WeatherError, match="Latitude must be in range"):
        weather.get_forecast(41.76, 12.25, today=TODAY, session=session)


def test_network_errors_become_weather_errors() -> None:
    session = Mock()
    session.get.side_effect = requests.ConnectionError("down")

    with pytest.raises(weather.WeatherError, match="unreachable"):
        weather.find_place("Roma", session=session)


def test_unknown_weather_code_has_generic_description() -> None:
    assert weather.describe_weather_code(1234) == "condizioni variabili"
    assert weather.describe_weather_code(None) == "non disponibile"
