"""Fuel prices of individual Italian stations, from the Ministry's price observatory (MIMIT).

Prices are those each station communicated to the Osservatorio prezzi carburanti, with the time
of the last communication for every fuel. The service is free and needs no key, but it is not
documented officially: requests are kept few and short-lived results are cached in memory.

Stations near the user's places are kept in ``fuel-stations.yaml`` in the data directory,
closest first; prices are always read live.
"""

import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
import yaml
from pydantic import BaseModel, ConfigDict, Field

from alfred import profile as profile_store
from alfred.paths import data_dir

ZONE_URL = "https://carburanti.mise.gov.it/ospzApi/search/zone"
DETAIL_URL = "https://carburanti.mise.gov.it/ospzApi/registry/servicearea"
REQUEST_TIMEOUT_SECONDS = 20
RATE_LIMIT_RETRIES = 3
CACHE_SECONDS = 15 * 60
STATIONS_FILENAME = "fuel-stations.yaml"
STALE_AFTER_HOURS = 72

# Profile fuel types -> fuel names used by the observatory. Hybrids run on petrol.
FUEL_NAMES: dict[str, tuple[str, ...]] = {
    "benzina": ("Benzina",),
    "gasolio": ("Gasolio",),
    "gpl": ("GPL",),
    "metano": ("Metano",),
    "ibrida": ("Benzina",),
}

_cache: dict[str, tuple[float, Any]] = {}


class FuelError(RuntimeError):
    """A fuel price service failure explained in terms the user can act on."""


def _fuel_names(fuel: str) -> tuple[str, ...]:
    names = FUEL_NAMES.get(fuel.strip().casefold())
    if not names:
        raise ValueError(f"unknown fuel {fuel!r}; use one of {sorted(FUEL_NAMES)}")
    return names


def _cached(key: str, fetch: Any) -> Any:
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]
    value = fetch()
    _cache[key] = (now, value)
    return value


def _request(method: str, url: str, what: str, session: Any, **kwargs: Any) -> Any:
    wait = 1.0
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            response = getattr(session or requests, method)(url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
        except requests.RequestException as error:
            raise FuelError(f"Could not {what}: the fuel price service is unreachable ({error}).") from error
        if response.status_code != 429 or attempt == RATE_LIMIT_RETRIES:
            break
        time.sleep(wait)
        wait *= 2
    if response.status_code == 429:
        raise FuelError(f"Could not {what}: the fuel price service is limiting requests; try again in a minute.")
    if response.status_code == 404:
        raise FuelError(f"Could not {what}: the station was not found (closed or wrong id).")
    if response.status_code >= 400:
        raise FuelError(f"Could not {what}: the fuel price service answered {response.status_code}.")
    return response.json()


def _hours_since(stamp: str, now: datetime) -> float | None:
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return round((now - moment).total_seconds() / 3600, 1)


def _map_link(latitude: float | None, longitude: float | None) -> str:
    if latitude is None or longitude is None:
        return ""
    return f"https://www.google.com/maps?q={latitude},{longitude}"


def station_prices(
    station_id: int,
    *,
    fuel: str = "benzina",
    now: datetime | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """Return one station's current prices for ``fuel``, self-service and full-service separately."""
    names = _fuel_names(fuel)
    now = now or datetime.now(UTC)
    detail = _cached(
        f"detail:{station_id}",
        lambda: _request("get", f"{DETAIL_URL}/{int(station_id)}", "read the station", session),
    )
    prices = []
    for item in detail.get("fuels") or []:
        if item.get("name") not in names:
            continue
        updated = str(item.get("insertDate", ""))
        age = _hours_since(updated, now)
        prices.append(
            {
                "fuel": str(item["name"]),
                "self_service": bool(item.get("isSelf")),
                "price": float(item["price"]),
                "updated": updated,
                "hours_since_update": age,
                "stale": age is not None and age > STALE_AFTER_HOURS,
            }
        )
    prices.sort(key=lambda price: (not price["self_service"], price["price"]))
    return {
        "id": int(detail.get("id") or station_id),
        "brand": str(detail.get("brand") or ""),
        "name": str(detail.get("name") or "").strip(),
        "address": str(detail.get("address") or ""),
        "prices": prices,
    }


def _detail_from_zone(station: dict[str, Any], names: tuple[str, ...], now: datetime) -> dict[str, Any]:
    """Fallback when a station's detail cannot be read: prices and update time from the zone search."""
    updated = str(station.get("insertDate", ""))
    age = _hours_since(updated, now) if updated else None
    prices = [
        {
            "fuel": str(item["name"]),
            "self_service": bool(item.get("isSelf")),
            "price": float(item["price"]),
            "updated": updated,
            "hours_since_update": age,
            "stale": age is not None and age > STALE_AFTER_HOURS,
        }
        for item in station.get("fuels") or []
        if item.get("name") in names
    ]
    prices.sort(key=lambda price: (not price["self_service"], price["price"]))
    return {
        "id": int(station["id"]),
        "brand": str(station.get("brand", "")),
        "name": str(station.get("name", "")).strip(),
        "address": str(station.get("address") or ""),
        "prices": prices,
    }


def find_stations(
    latitude: float,
    longitude: float,
    *,
    radius_km: float = 5,
    fuel: str = "benzina",
    self_service: bool = True,
    count: int = 10,
    now: datetime | None = None,
    session: Any | None = None,
) -> list[dict[str, Any]]:
    """Return the cheapest stations selling ``fuel`` within ``radius_km``, cheapest first.

    Each station has its distance, coordinates and map link (registry addresses are sometimes
    wrong, coordinates are reliable), and the price with the time it was last communicated.
    """
    names = _fuel_names(fuel)
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("latitude/longitude out of range")
    if not 0.5 <= radius_km <= 10:
        raise ValueError("radius_km must be between 0.5 and 10")
    if not 1 <= count <= 25:
        raise ValueError("count must be between 1 and 25")

    body = {"points": [{"lat": latitude, "lng": longitude}], "radius": radius_km}
    found = _cached(
        f"zone:{latitude:.4f},{longitude:.4f},{radius_km}",
        lambda: _request("post", ZONE_URL, "search fuel stations", session, json=body),
    )
    candidates = []
    for station in found.get("results", []):
        offered = [
            float(item["price"])
            for item in station.get("fuels") or []
            if item.get("name") in names and bool(item.get("isSelf")) == self_service
        ]
        if offered:
            candidates.append((min(offered), station))
    candidates.sort(key=lambda pair: (pair[0], float(pair[1].get("distance") or 0)))

    results = []
    for _, station in candidates[:count]:
        location = station.get("location") or {}
        lat, lon = location.get("lat"), location.get("lng")
        try:
            detail = station_prices(int(station["id"]), fuel=fuel, now=now, session=session)
        except FuelError:
            detail = _detail_from_zone(station, names, now or datetime.now(UTC))
        price = next((p for p in detail["prices"] if p["self_service"] == self_service), None)
        if price is None:
            continue
        results.append(
            {
                "id": detail["id"],
                "brand": detail["brand"] or str(station.get("brand", "")),
                "name": detail["name"],
                "address": detail["address"],
                "distance_km": round(float(station.get("distance") or 0), 1),
                "latitude": lat,
                "longitude": lon,
                "map": _map_link(lat, lon),
                **{
                    key: price[key]
                    for key in ("fuel", "self_service", "price", "updated", "hours_since_update", "stale")
                },
            }
        )
    return sorted(results, key=lambda station: (station["price"], station["distance_km"]))


# ---------------------------------------------------------------------------------------------
# Stations saved in fuel-stations.yaml


class FuelStation(BaseModel):
    """A fuel station near the user's places, identified by its MIMIT registry id.

    ``distances`` maps profile place labels ("home", "work") to the distance in km. Prices are not
    stored because they change: they are read live from the observatory.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    brand: str = ""
    name: str = ""
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    distances: dict[str, float] = Field(default_factory=dict)
    usual: bool = False
    note: str = ""
    source: str = "user"

    def closest(self) -> float:
        return min(self.distances.values(), default=float("inf"))


def stations_file() -> Path:
    return data_dir() / STATIONS_FILENAME


def _label(near: str) -> str:
    return "_".join(near.casefold().split())


def _sorted(stations: list[FuelStation]) -> list[FuelStation]:
    return sorted(stations, key=lambda station: (station.closest(), station.id))


def load_stations(path: Path | None = None) -> list[FuelStation]:
    """Return the saved stations, closest first."""
    path = path or stations_file()
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _sorted([FuelStation.model_validate(item) for item in data.get("stations") or []])


def write_stations(stations: list[FuelStation], path: Path | None = None) -> Path:
    """Write the stations atomically with owner-only permissions, closest first."""
    path = path or stations_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    items = [station.model_dump(exclude_defaults=True) | {"id": station.id} for station in _sorted(stations)]
    content = yaml.safe_dump({"stations": items}, allow_unicode=True, sort_keys=False)
    file_descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".fuel-", suffix=".yaml")
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(content)
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return path


def upsert_station(
    stations: list[FuelStation],
    station_id: int,
    *,
    near: str | None = None,
    distance_km: float | None = None,
    **fields: Any,
) -> list[FuelStation]:
    """Add or update a station; ``None`` fields keep current values; ``near`` with ``distance_km``
    records the distance from a place."""
    if (near is None) != (distance_km is None):
        raise ValueError("near and distance_km must be given together")
    index = next((i for i, station in enumerate(stations) if station.id == int(station_id)), None)
    current: dict[str, Any] = stations[index].model_dump() if index is not None else {"id": int(station_id)}
    distances = dict(current.get("distances", {}))
    if near is not None and distance_km is not None:
        distances[_label(near)] = round(float(distance_km), 1)
    changes = {key: value for key, value in fields.items() if value is not None}
    station = FuelStation.model_validate({**current, **changes, "distances": distances})
    updated = list(stations)
    if index is None:
        updated.append(station)
    else:
        updated[index] = station
    return _sorted(updated)


def replace_near(stations: list[FuelStation], near: str, found: list[dict[str, Any]]) -> list[FuelStation]:
    """Make ``found`` the stations near a place: refresh them, drop that place from stations no
    longer found, and remove stations left with no place unless they are the usual one."""
    label = _label(near)
    found_ids = {int(item["id"]) for item in found}
    kept = []
    for station in stations:
        if station.id not in found_ids and label in station.distances:
            station = station.model_copy(
                update={"distances": {key: value for key, value in station.distances.items() if key != label}}
            )
        if station.distances or station.usual:
            kept.append(station)
    for item in found:
        kept = upsert_station(
            kept,
            int(item["id"]),
            near=label,
            distance_km=float(item["distance_km"]),
            brand=item.get("brand"),
            name=item.get("name"),
            address=item.get("address"),
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
            source="mimit",
        )
    return kept


def stations_near(stations: list[FuelStation], near: str | None = None) -> list[FuelStation]:
    """Stations near a place (all when ``near`` is None), closest first."""
    if near is None:
        return _sorted(stations)
    label = _label(near)
    return sorted((s for s in stations if label in s.distances), key=lambda station: station.distances[label])


def _station_dict(station: FuelStation) -> dict[str, Any]:
    data = station.model_dump(exclude={"source"})
    data["map"] = _map_link(station.latitude, station.longitude)
    return data


def collect_stations(
    near: str,
    *,
    radius_km: float = 5,
    fuel: str = "benzina",
    now: datetime | None = None,
    path: Path | None = None,
    session: Any | None = None,
) -> list[dict[str, Any]]:
    """Save every station selling ``fuel`` within ``radius_km`` of a profile place (e.g. "home"),
    with its distance; stations no longer found there are dropped, except the usual one.
    Returns the stations near that place, closest first."""
    names = _fuel_names(fuel)
    place = profile_store.load_profile().places.get(near)
    if place is None or place.latitude is None or place.longitude is None:
        raise ValueError(f"the profile place {near!r} has no coordinates; save them first")
    if not 0.5 <= radius_km <= 10:
        raise ValueError("radius_km must be between 0.5 and 10")
    body = {"points": [{"lat": place.latitude, "lng": place.longitude}], "radius": radius_km}
    zone = _cached(
        f"zone:{place.latitude:.4f},{place.longitude:.4f},{radius_km}",
        lambda: _request("post", ZONE_URL, "search fuel stations", session, json=body),
    )
    found = []
    for station in zone.get("results") or []:
        if not any(item.get("name") in names for item in station.get("fuels") or []):
            continue
        try:
            detail = station_prices(int(station["id"]), fuel=fuel, now=now, session=session)
        except FuelError:
            detail = _detail_from_zone(station, names, now or datetime.now(UTC))
        location = station.get("location") or {}
        found.append(
            {
                "id": int(station["id"]),
                "brand": detail["brand"] or str(station.get("brand") or ""),
                "name": detail["name"],
                "address": detail["address"],
                "latitude": location.get("lat"),
                "longitude": location.get("lng"),
                "distance_km": float(station.get("distance") or 0),
            }
        )
    stations = replace_near(load_stations(path), near, found)
    write_stations(stations, path)
    return [_station_dict(station) for station in stations_near(stations, near)]


def save_station(
    station_id: int,
    *,
    near: str | None = None,
    distance_km: float | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    usual: bool | None = None,
    note: str | None = None,
    path: Path | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """Add or update one station; brand, name and address come from the registry. Marking a station
    as usual unmarks the previous usual one."""
    detail = station_prices(station_id, fuel="benzina", session=session)
    stations = load_stations(path)
    if usual:
        stations = [s.model_copy(update={"usual": False}) if s.id != int(station_id) else s for s in stations]
    stations = upsert_station(
        stations,
        station_id,
        near=near,
        distance_km=distance_km,
        brand=detail["brand"],
        name=detail["name"],
        address=detail["address"],
        latitude=latitude,
        longitude=longitude,
        usual=usual,
        note=note,
    )
    write_stations(stations, path)
    return _station_dict(next(s for s in stations if s.id == int(station_id)))


def forget_station(station_id: int, *, path: Path | None = None) -> None:
    """Remove a saved station."""
    stations = load_stations(path)
    remaining = [station for station in stations if station.id != int(station_id)]
    if len(remaining) == len(stations):
        raise KeyError(f"no saved station with id {station_id}")
    write_stations(remaining, path)


def saved_station_prices(
    *,
    fuel: str = "benzina",
    near: str | None = None,
    order: str = "distance",
    limit: int | None = None,
    now: datetime | None = None,
    path: Path | None = None,
    session: Any | None = None,
) -> list[dict[str, Any]]:
    """Live prices at the saved stations, near a place or all, ordered by ``distance`` (closest
    first) or ``price`` (cheapest self-service first)."""
    if order not in ("distance", "price"):
        raise ValueError("order must be 'distance' or 'price'")
    stations = stations_near(load_stations(path), near)
    if limit is not None:
        stations = stations[:limit]
    results = []
    for station in stations:
        entry = _station_dict(station)
        try:
            entry["prices"] = station_prices(station.id, fuel=fuel, now=now, session=session)["prices"]
        except FuelError as error:
            entry["prices"], entry["error"] = [], str(error)
        results.append(entry)

    if order == "price":

        def best(entry: dict[str, Any]) -> float:
            own = [p["price"] for p in entry["prices"] if p["self_service"]] or [p["price"] for p in entry["prices"]]
            return min(own) if own else float("inf")

        results.sort(key=best)
    return results
