"""Tests for TomTom traffic information."""

from datetime import datetime
from unittest.mock import Mock, patch

from alfred.core.config import AlfredSettings, PlaceConfig, WorkConfig
from alfred.traffic import get_traffic_data


def _settings() -> AlfredSettings:
    return AlfredSettings(
        first_name="Mario",
        last_name="Rossi",
        home=PlaceConfig(address="Via Roma 1, 00100 Roma"),
        work=WorkConfig(
            company="Example S.p.A.",
            address="Via Milano 10, 00100 Roma",
            days=["monday", "wednesday", "thursday"],
        ),
    )


@patch("alfred.traffic.requests.get")
def test_get_traffic_data_on_workday(mock_get: Mock) -> None:
    """Format traffic information on a configured commuting day."""
    origin_response = Mock()
    origin_response.json.return_value = [{"lat": "41.8", "lon": "12.2"}]
    destination_response = Mock()
    destination_response.json.return_value = [{"lat": "41.9", "lon": "12.4"}]
    route_response = Mock()
    route_response.json.return_value = {
        "routes": [
            {
                "summary": {
                    "travelTimeInSeconds": 2700,
                    "trafficDelayInSeconds": 900,
                    "lengthInMeters": 32100,
                }
            }
        ]
    }
    mock_get.side_effect = [origin_response, destination_response, route_response]

    result = get_traffic_data(_settings(), "api-key", datetime(2026, 9, 7, 7, 30))

    assert result == (
        "🚗 *Traffico casa-lavoro*\n\n"
        "• Destinazione: Example S.p.A.\n"
        "• Distanza: 32.1 km\n"
        "• Tempo stimato: 45 min\n"
        "• Ritardo dovuto al traffico: 15 min"
    )
    origin_response.raise_for_status.assert_called_once_with()
    destination_response.raise_for_status.assert_called_once_with()
    route_response.raise_for_status.assert_called_once_with()


@patch("alfred.traffic.requests.get")
def test_get_traffic_data_skips_non_workday(mock_get: Mock) -> None:
    """Do not query traffic outside configured commuting days."""
    assert get_traffic_data(_settings(), "api-key", datetime(2026, 9, 8, 7, 30)) is None
    mock_get.assert_not_called()
