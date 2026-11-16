"""Tests for fuel prices of individual stations."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from alfred import fuel_prices

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    fuel_prices._cache.clear()


def _response(payload: Any, status: int = 200) -> Mock:
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    return response


def _zone_station(station_id: int, self_price: float, distance: str) -> dict[str, Any]:
    return {
        "id": station_id,
        "brand": "Brand",
        "distance": distance,
        "location": {"lat": 41.7, "lng": 12.3},
        "fuels": [
            {"name": "Benzina", "price": self_price, "isSelf": True},
            {"name": "Benzina", "price": self_price + 0.2, "isSelf": False},
            {"name": "Gasolio", "price": 1.5, "isSelf": True},
        ],
    }


def _detail(station_id: int, self_price: float, updated: str = "2026-11-16T07:00:00Z") -> dict[str, Any]:
    return {
        "id": station_id,
        "name": f" Station {station_id} ",
        "brand": "Brand",
        "address": f"Via Roma {station_id}",
        "fuels": [
            {"name": "Benzina", "price": self_price + 0.2, "isSelf": False, "insertDate": "2026-11-12T07:00:00Z"},
            {"name": "Benzina", "price": self_price, "isSelf": True, "insertDate": updated},
            {"name": "Gasolio", "price": 1.5, "isSelf": True, "insertDate": updated},
        ],
    }


def test_station_prices_filters_fuel_and_reports_age() -> None:
    session = Mock()
    session.get.return_value = _response(_detail(7, 1.929))

    station = fuel_prices.station_prices(7, now=NOW, session=session)

    assert station["name"] == "Station 7"
    assert [(p["self_service"], p["price"], p["hours_since_update"], p["stale"]) for p in station["prices"]] == [
        (True, 1.929, 2.0, False),
        (False, 2.129, 98.0, True),
    ]
    assert session.get.call_args.args[0].endswith("/registry/servicearea/7")


def test_find_stations_returns_cheapest_with_map_links() -> None:
    session = Mock()
    session.post.return_value = _response(
        {"results": [_zone_station(1, 1.95, "1.4"), _zone_station(2, 1.929, "4.8"), _zone_station(3, 1.929, "3.1")]}
    )
    session.get.side_effect = lambda url, **_: _response(
        _detail(int(url.rsplit("/", 1)[1]), {1: 1.95, 2: 1.929, 3: 1.929}[int(url.rsplit("/", 1)[1])])
    )

    stations = fuel_prices.find_stations(41.76, 12.24, now=NOW, count=2, session=session)

    assert [(s["id"], s["price"], s["distance_km"]) for s in stations] == [(3, 1.929, 3.1), (2, 1.929, 4.8)]
    assert stations[0]["map"] == "https://www.google.com/maps?q=41.7,12.3"
    assert stations[0]["address"] == "Via Roma 3"
    assert session.post.call_args.kwargs["json"] == {"points": [{"lat": 41.76, "lng": 12.24}], "radius": 5}


def test_find_stations_can_look_for_full_service() -> None:
    session = Mock()
    session.post.return_value = _response({"results": [_zone_station(1, 1.95, "1.4")]})
    session.get.return_value = _response(_detail(1, 1.95))

    stations = fuel_prices.find_stations(41.76, 12.24, self_service=False, now=NOW, session=session)

    assert [(s["self_service"], s["price"]) for s in stations] == [(False, 2.15)]


def test_results_are_cached() -> None:
    session = Mock()
    session.get.return_value = _response(_detail(7, 1.929))

    fuel_prices.station_prices(7, now=NOW, session=session)
    fuel_prices.station_prices(7, now=NOW, session=session)

    session.get.assert_called_once()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"fuel": "kerosene"}, "unknown fuel"),
        ({"radius_km": 50}, "radius_km"),
        ({"count": 0}, "count"),
    ],
)
def test_find_stations_rejects_invalid_requests(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        fuel_prices.find_stations(41.76, 12.24, session=Mock(), **kwargs)


def test_service_errors_become_fuel_errors() -> None:
    session = Mock()
    session.get.return_value = _response({}, status=404)
    with pytest.raises(fuel_prices.FuelError, match="not found"):
        fuel_prices.station_prices(9, session=session)

    session.post.side_effect = requests.ConnectionError("down")
    with pytest.raises(fuel_prices.FuelError, match="unreachable"):
        fuel_prices.find_stations(41.76, 12.24, session=session)


def test_saved_stations_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "fuel-stations.yaml"
    session = Mock()
    session.get.side_effect = lambda url, **_: _response(
        _detail(int(url.rsplit("/", 1)[1]), 1.9 + int(url.rsplit("/", 1)[1]) / 100)
    )

    fuel_prices.save_station(5, latitude=41.7, longitude=12.3, near="home", path=path, session=session)
    fuel_prices.save_station(2, near="work", path=path, session=session)
    fuel_prices.save_station(5, note="sul tragitto", path=path, session=session)

    saved = fuel_prices.load_saved_stations(path)
    assert [(s["id"], s["near"], s["note"], s["latitude"]) for s in saved] == [
        (2, "work", "", None),
        (5, "home", "sul tragitto", 41.7),
    ]
    assert oct(path.stat().st_mode & 0o777) == "0o600"

    prices = fuel_prices.saved_station_prices(now=NOW, path=path, session=session)
    assert [s["id"] for s in prices] == [2, 5]
    assert [s["id"] for s in fuel_prices.saved_station_prices(near="HOME", now=NOW, path=path, session=session)] == [5]

    fuel_prices.forget_station(2, path=path)
    assert [s["id"] for s in fuel_prices.load_saved_stations(path)] == [5]
    with pytest.raises(KeyError):
        fuel_prices.forget_station(2, path=path)


def test_rate_limit_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fuel_prices.time, "sleep", lambda _seconds: None)
    session = Mock()
    session.get.side_effect = [_response({}, status=429), _response(_detail(7, 1.929))]

    assert fuel_prices.station_prices(7, now=NOW, session=session)["prices"][0]["price"] == 1.929
    assert session.get.call_count == 2


def test_find_stations_falls_back_to_zone_data_when_a_detail_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fuel_prices.time, "sleep", lambda _seconds: None)
    session = Mock()
    zone = _zone_station(1, 1.95, "1.4") | {"name": "Q8 Uno", "insertDate": "2026-11-16T08:00:00Z"}
    session.post.return_value = _response({"results": [zone]})
    session.get.return_value = _response({}, status=429)

    stations = fuel_prices.find_stations(41.76, 12.24, now=NOW, session=session)

    assert [(s["id"], s["name"], s["price"], s["hours_since_update"]) for s in stations] == [(1, "Q8 Uno", 1.95, 1.0)]
