"""Tests for fuel prices of individual stations."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from alfred import fuel_prices, paths
from alfred import profile as profile_store

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


@pytest.fixture
def profile_with_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    path = tmp_path / "profile.yaml"
    monkeypatch.setenv(profile_store.PROFILE_FILE_ENV, str(path))
    profile_store.save_profile(
        profile_store.save_place(profile_store.Profile(), "home", "Via Roma 1", latitude=41.76, longitude=12.24)
    )
    return path


def _detail_for(url: str, **_: Any) -> Mock:
    station_id = int(url.rsplit("/", 1)[1])
    return _response(_detail(station_id, 1.9 + station_id / 1000))


def test_collect_stations_saves_them_in_the_profile_closest_first(profile_with_home: Path) -> None:
    session = Mock()
    session.post.return_value = _response(
        {"results": [_zone_station(1, 1.95, "4.6"), _zone_station(2, 1.93, "0.4"), _zone_station(3, 1.94, "1.4")]}
    )
    session.get.side_effect = _detail_for

    collected = fuel_prices.collect_stations("home", now=NOW, session=session)

    assert [(s["id"], s["distances"]) for s in collected] == [
        (2, {"home": 0.4}),
        (3, {"home": 1.4}),
        (1, {"home": 4.6}),
    ]
    saved = fuel_prices.load_stations()
    assert [s.id for s in saved] == [2, 3, 1]
    assert fuel_prices.stations_file() == profile_with_home.parent / "fuel-stations.yaml"
    assert oct(fuel_prices.stations_file().stat().st_mode & 0o777) == "0o600"
    assert saved[0].address == "Via Roma 2"
    assert saved[0].source == "mimit"


def test_collect_again_keeps_the_usual_station_and_drops_the_rest(profile_with_home: Path) -> None:
    session = Mock()
    session.get.side_effect = _detail_for
    session.post.return_value = _response({"results": [_zone_station(1, 1.95, "4.6"), _zone_station(2, 1.93, "0.4")]})
    fuel_prices.collect_stations("home", now=NOW, session=session)
    fuel_prices.save_station(1, usual=True, note="abituale", session=session)

    fuel_prices._cache.clear()
    session.post.return_value = _response({"results": [_zone_station(3, 1.94, "1.4")]})
    fuel_prices.collect_stations("home", now=NOW, session=session)

    stations = fuel_prices.load_stations()
    assert [(s.id, s.distances, s.usual) for s in stations] == [(3, {"home": 1.4}, False), (1, {}, True)]


def test_collect_requires_place_coordinates(profile_with_home: Path) -> None:
    with pytest.raises(ValueError, match="no coordinates"):
        fuel_prices.collect_stations("work", session=Mock())


def test_saved_station_prices_by_distance_or_price(profile_with_home: Path) -> None:
    session = Mock()
    session.get.side_effect = _detail_for
    session.post.return_value = _response(
        {"results": [_zone_station(9, 1.95, "0.4"), _zone_station(2, 1.93, "3.0"), _zone_station(5, 1.94, "1.4")]}
    )
    fuel_prices.collect_stations("home", now=NOW, session=session)

    by_distance = fuel_prices.saved_station_prices(near="home", now=NOW, session=session)
    by_price = fuel_prices.saved_station_prices(near="home", order="price", now=NOW, session=session)

    assert [s["id"] for s in by_distance] == [9, 5, 2]
    assert [s["id"] for s in by_price] == [2, 5, 9]
    assert by_distance[0]["prices"][0]["price"] == pytest.approx(1.909)
    assert by_distance[0]["map"].startswith("https://www.google.com/maps?q=")
    fuel_prices.forget_station(9)
    assert [s.id for s in fuel_prices.load_stations()] == [5, 2]


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


def test_station_without_fuels_is_handled() -> None:
    session = Mock()
    session.get.return_value = _response({"id": 4, "name": "Chiuso", "brand": "X", "address": "", "fuels": None})

    assert fuel_prices.station_prices(4, now=NOW, session=session)["prices"] == []


def test_station_with_incomplete_registry_data_is_handled() -> None:
    session = Mock()
    session.get.return_value = _response({"id": None, "name": None, "brand": None, "address": None, "fuels": None})

    station = fuel_prices.station_prices(4, now=NOW, session=session)

    assert (station["id"], station["name"], station["brand"], station["address"]) == (4, "", "", "")


def test_upsert_records_distances_per_place_and_keeps_order() -> None:
    stations = fuel_prices.upsert_station([], 7, name="A", near="home", distance_km=3.14)
    stations = fuel_prices.upsert_station(stations, 8, name="B", near="work", distance_km=0.9)
    stations = fuel_prices.upsert_station(stations, 7, near="Work", distance_km=4.0, usual=True)

    assert [(s.id, s.distances, s.usual) for s in stations] == [
        (8, {"work": 0.9}, False),
        (7, {"home": 3.1, "work": 4.0}, True),
    ]
    assert [s.id for s in fuel_prices.stations_near(stations, "work")] == [8, 7]
    assert [s.id for s in fuel_prices.stations_near(stations, "home")] == [7]


def test_distance_needs_a_place() -> None:
    with pytest.raises(ValueError, match="together"):
        fuel_prices.upsert_station([], 7, distance_km=1.0)


def test_marking_a_new_usual_station_unmarks_the_old_one(profile_with_home: Path) -> None:
    session = Mock()
    session.get.side_effect = _detail_for

    fuel_prices.save_station(1, usual=True, session=session)
    fuel_prices.save_station(2, usual=True, session=session)

    assert [(s.id, s.usual) for s in fuel_prices.load_stations()] == [(1, False), (2, True)]
    with pytest.raises(KeyError):
        fuel_prices.forget_station(99)
