"""Tests for weather data retrieval."""

from unittest.mock import Mock, patch

import requests

from alfred.weather import get_weather_data


@patch("alfred.weather.requests.get")
def test_get_weather_data(mock_get: Mock) -> None:
    """Format current conditions, daily ranges, and weather alerts."""
    mock_get.return_value.json.return_value = {
        "current": {
            "temperature_2m": 21.5,
            "relative_humidity_2m": 64,
            "weather_code": 2,
            "wind_speed_10m": 12.3,
        },
        "daily": {
            "temperature_2m_min": [14.2],
            "temperature_2m_max": [24.8],
            "relative_humidity_2m_min": [45],
            "relative_humidity_2m_max": [82],
            "weather_code": [95],
            "precipitation_probability_max": [70],
            "precipitation_sum": [4.5],
            "wind_speed_10m_max": [35.0],
            "wind_gusts_10m_max": [52.0],
        },
    }

    result = get_weather_data(latitude=41.9028, longitude=12.4964)

    assert result == (
        "🌡️ *Meteo*\n\n"
        "*Adesso*\n"
        "• Temperatura: 21.5°C\n"
        "• Umidità: 64%\n"
        "• Condizioni: cielo parzialmente nuvoloso o coperto\n"
        "• Vento: 12.3 km/h\n\n"
        "*Oggi*\n"
        "• Temperatura minima/massima: 14.2°C / 24.8°C\n"
        "• Umidità minima/massima: 45% / 82%\n\n"
        "*Attenzioni*\n"
        "• Possibili precipitazioni: 70% (4.5 mm previsti)\n"
        "• Vento sostenuto: fino a 35.0 km/h, raffiche fino a 52.0 km/h\n"
        "• Attenzione per temporali durante la giornata"
    )


@patch("alfred.weather.requests.get", side_effect=requests.RequestException("offline"))
def test_get_weather_data_handles_request_failure(_: Mock) -> None:
    """Return a readable message when Open-Meteo is unavailable."""
    assert get_weather_data(latitude=41.9028, longitude=12.4964) == "Impossibile recuperare il meteo: offline"
