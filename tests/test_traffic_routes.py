"""Tests for TomTom routes and address search."""

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
import requests

from alfred import paths, traffic_routes

ROME = ZoneInfo("Europe/Rome")
NOW = datetime(2026, 11, 16, 7, 0, tzinfo=ROME)
HOME = (41.90, 12.50)
WORK = (41.83, 12.34)


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(traffic_routes.API_KEY_NAME, "test-key")


def _response(payload: Any, status: int = 200) -> Mock:
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    return response


def _route_payload() -> dict[str, Any]:
    return {
        "routes": [
            {
                "summary": {
                    "lengthInMeters": 32140,
                    "travelTimeInSeconds": 2700,
                    "trafficDelayInSeconds": 900,
                    "noTrafficTravelTimeInSeconds": 1800,
                    "departureTime": "2026-11-16T08:00:00+01:00",
                    "arrivalTime": "2026-11-16T08:45:00+01:00",
                },
                "legs": [{"points": [{"latitude": 41.9, "longitude": 12.5}, {"latitude": 41.86, "longitude": 12.42}]}],
                "sections": [
                    {"sectionType": "TRAVEL_MODE", "startPointIndex": 0},
                    {
                        "sectionType": "TRAFFIC",
                        "startPointIndex": 1,
                        "simpleCategory": "JAM",
                        "magnitudeOfDelay": 3,
                        "delayInSeconds": 660,
                        "effectiveSpeedInKmh": 12,
                    },
                ],
            }
        ]
    }


def _tomtom_result(street: str, freeform: str, lat: float, lon: float) -> dict[str, Any]:
    return {
        "type": "Point Address",
        "address": {
            "freeformAddress": freeform,
            "streetName": street,
            "municipality": "Bologna",
            "countrySubdivision": "Emilia-Romagna",
            "countryCode": "IT",
        },
        "position": {"lat": lat, "lon": lon},
    }


def test_find_address_uses_tomtom_search_when_the_street_matches() -> None:
    session = Mock()
    session.get.return_value = _response(
        {"results": [_tomtom_result("Via Roma", "Via Roma 1, 40121 Bologna", 44.49, 11.34)]}
    )

    places = traffic_routes.find_address(" Via Roma 1, Bologna ", country="it", session=session)

    assert places == [
        {
            "address": "Via Roma 1, 40121 Bologna",
            "street": "Via Roma",
            "municipality": "Bologna",
            "region": "Emilia-Romagna",
            "country": "IT",
            "latitude": 44.49,
            "longitude": 11.34,
            "match": "Point Address",
            "source": "tomtom",
            "street_matches": True,
        }
    ]
    session.get.assert_called_once()
    url = session.get.call_args.args[0]
    params = session.get.call_args.kwargs["params"]
    assert url.endswith("/search/2/search/Via%20Roma%201%2C%20Bologna.json")
    assert params["countrySet"] == "IT"
    assert params["key"] == "test-key"


def test_find_address_falls_back_to_openstreetmap_for_unknown_streets() -> None:
    session = Mock()
    session.get.side_effect = [
        _response({"results": [_tomtom_result("Via Felice Rossi", "Via Felice Rossi, Bologna", 44.5, 11.3)]}),
        _response(
            [
                {
                    "display_name": "Via Mario Rossi, Bologna, Italia",
                    "lat": "44.49",
                    "lon": "11.33",
                    "addresstype": "road",
                    "address": {
                        "road": "Via Mario Rossi",
                        "city": "Bologna",
                        "state": "Emilia-Romagna",
                        "country_code": "it",
                    },
                }
            ]
        ),
    ]

    places = traffic_routes.find_address("Via Mario Rossi 19, Bologna", country="IT", session=session)

    assert [(p["source"], p["street"], p["street_matches"]) for p in places] == [
        ("openstreetmap", "Via Mario Rossi", True),
        ("tomtom", "Via Felice Rossi", False),
    ]
    osm_call = session.get.call_args_list[1]
    assert osm_call.args[0] == traffic_routes.OSM_SEARCH_URL
    assert osm_call.kwargs["params"]["countrycodes"] == "it"
    assert "key" not in osm_call.kwargs["params"]
    assert "Alfred" in osm_call.kwargs["headers"]["User-Agent"]


def test_find_address_keeps_tomtom_results_when_openstreetmap_fails() -> None:
    session = Mock()
    session.get.side_effect = [
        _response({"results": [_tomtom_result("Via Felice Rossi", "Via Felice Rossi, Bologna", 44.5, 11.3)]}),
        requests.ConnectionError("down"),
    ]

    places = traffic_routes.find_address("Via Mario Rossi 19, Bologna", session=session)

    assert [p["source"] for p in places] == ["tomtom"]
    assert places[0]["street_matches"] is False


def test_find_address_for_a_town_skips_the_street_check() -> None:
    session = Mock()
    session.get.return_value = _response({"results": [_tomtom_result("", "Bologna", 44.49, 11.34)]})

    places = traffic_routes.find_address("Bologna", session=session)

    assert places[0]["street_matches"] is None
    session.get.assert_called_once()


def test_find_address_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        traffic_routes.find_address("  ", session=Mock())


def test_get_route_now_reports_delay_and_traffic_sections() -> None:
    session = Mock()
    session.get.return_value = _response(_route_payload())

    route = traffic_routes.get_route(HOME, WORK, session=session)

    assert route == {
        "distance_km": 32.1,
        "travel_minutes": 45,
        "traffic_delay_minutes": 15,
        "no_traffic_minutes": 30,
        "departure": "2026-11-16T08:00:00+01:00",
        "arrival": "2026-11-16T08:45:00+01:00",
        "traffic_sections": [
            {
                "kind": "coda",
                "severity": "forte",
                "delay_minutes": 11,
                "speed_kmh": 12,
                "latitude": 41.86,
                "longitude": 12.42,
            }
        ],
    }
    url = session.get.call_args.args[0]
    params = session.get.call_args.kwargs["params"]
    assert url.endswith("/calculateRoute/41.9,12.5:41.83,12.34/json")
    assert params["traffic"] == "true"
    assert params["sectionType"] == "traffic"
    assert "departAt" not in params and "arriveAt" not in params


def test_get_route_plans_by_arrival_time() -> None:
    session = Mock()
    session.get.return_value = _response(_route_payload())

    traffic_routes.get_route(HOME, WORK, arrive_at=datetime(2026, 11, 16, 9, 0, tzinfo=ROME), now=NOW, session=session)

    assert session.get.call_args.kwargs["params"]["arriveAt"] == "2026-11-16T09:00:00+01:00"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"depart_at": NOW, "arrive_at": NOW}, "not both"),
        ({"depart_at": datetime(2026, 11, 16, 6, 0, tzinfo=ROME)}, "in the future"),
        ({"arrive_at": datetime(2026, 11, 16, 9, 0)}, "timezone"),
    ],
)
def test_get_route_rejects_invalid_times(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        traffic_routes.get_route(HOME, WORK, now=NOW, session=Mock(), **kwargs)


def test_get_route_rejects_bad_coordinates() -> None:
    with pytest.raises(ValueError, match="out of range"):
        traffic_routes.get_route((95.0, 12.0), WORK, session=Mock())


def test_get_route_without_routes_raises() -> None:
    session = Mock()
    session.get.return_value = _response({"routes": []})

    with pytest.raises(traffic_routes.TrafficError, match="no car route"):
        traffic_routes.get_route(HOME, WORK, session=session)


@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (403, {"detailedError": {"message": "You are not allowed to access this endpoint"}}, "Enable the Search"),
        (429, {}, "quota"),
        (400, {"detailedError": {"message": "Invalid departAt"}}, "Invalid departAt"),
    ],
)
def test_tomtom_errors_become_clear_messages(status: int, payload: dict[str, Any], expected: str) -> None:
    session = Mock()
    session.get.return_value = _response(payload, status=status)

    with pytest.raises(traffic_routes.TrafficError, match=expected):
        traffic_routes.get_route(HOME, WORK, session=session)


def test_network_errors_become_traffic_errors() -> None:
    session = Mock()
    session.get.side_effect = requests.ConnectionError("down")

    with pytest.raises(traffic_routes.TrafficError, match="unreachable"):
        traffic_routes.find_address("Roma", session=session)


def test_missing_api_key_is_explained(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(traffic_routes.API_KEY_NAME)

    with pytest.raises(traffic_routes.TrafficError, match="not configured"):
        traffic_routes.find_address("Roma", session=Mock())


def test_api_key_is_read_from_alfred_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(traffic_routes.API_KEY_NAME)
    fake_key_line = 'ALFRED_TOMTOM_API_KEY="from-file"\n'  # pragma: allowlist secret
    env_file = "# comment\nALFRED_WHATSAPP_RECIPIENT=391234567890\n" + fake_key_line
    (tmp_path / "alfred.env").write_text(env_file, encoding="utf-8")
    session = Mock()
    session.get.return_value = _response({"results": []})

    traffic_routes.find_address("Roma", session=session)

    assert session.get.call_args.kwargs["params"]["key"] == "from-file"


def test_plugin_placeholder_falls_back_to_alfred_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(traffic_routes.API_KEY_NAME, "${user_config.tomtom_api_key}")
    (tmp_path / "alfred.env").write_text("export ALFRED_TOMTOM_API_KEY=from-file\n", encoding="utf-8")

    assert paths.secret(traffic_routes.API_KEY_NAME) == "from-file"
