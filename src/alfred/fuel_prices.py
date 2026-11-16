"""Fuel prices of individual Italian stations, from the Ministry's price observatory (MIMIT).

Prices are those each station communicated to the Osservatorio prezzi carburanti, with the time
of the last communication for every fuel. The service is free and needs no key, but it is not
documented officially: requests are kept few and short-lived results are cached in memory.

Stations the user cares about are saved in ``fuel-stations.yaml`` in the data directory.
"""

import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
import yaml

from alfred.paths import data_dir

ZONE_URL = "https://carburanti.mise.gov.it/ospzApi/search/zone"
DETAIL_URL = "https://carburanti.mise.gov.it/ospzApi/registry/servicearea"
REQUEST_TIMEOUT_SECONDS = 20
RATE_LIMIT_RETRIES = 3
CACHE_SECONDS = 15 * 60
STALE_AFTER_HOURS = 72
STATIONS_FILENAME = "fuel-stations.yaml"

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
    for item in detail.get("fuels", []):
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
        "id": int(detail.get("id", station_id)),
        "brand": str(detail.get("brand", "")),
        "name": str(detail.get("name", "")).strip(),
        "address": str(detail.get("address", "") or ""),
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
        for item in station.get("fuels", [])
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
            for item in station.get("fuels", [])
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
# Saved stations


def stations_file() -> Path:
    return data_dir() / STATIONS_FILENAME


def load_saved_stations(path: Path | None = None) -> list[dict[str, Any]]:
    """Return the stations the user saved."""
    path = path or stations_file()
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    stations: list[dict[str, Any]] = list(data.get("stations", []))
    return stations


def _write_saved_stations(stations: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump({"stations": stations}, allow_unicode=True, sort_keys=False)
    file_descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".fuel-", suffix=".yaml")
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(content)
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def save_station(
    station_id: int,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    near: str = "",
    note: str = "",
    path: Path | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """Save (or update) a station; brand, name and address come from the registry."""
    path = path or stations_file()
    detail = station_prices(station_id, session=session, fuel="benzina")
    entry = {
        "id": detail["id"],
        "brand": detail["brand"],
        "name": detail["name"],
        "address": detail["address"],
        "latitude": latitude,
        "longitude": longitude,
        "near": near.strip(),
        "note": note.strip(),
    }
    saved = load_saved_stations(path)
    previous = next((station for station in saved if int(station["id"]) == entry["id"]), {})
    stations = [station for station in saved if int(station["id"]) != entry["id"]]
    for key in ("latitude", "longitude", "near", "note"):
        if entry[key] in (None, "") and previous.get(key) not in (None, ""):
            entry[key] = previous[key]
    stations.append(entry)
    _write_saved_stations(stations, path)
    return entry


def forget_station(station_id: int, *, path: Path | None = None) -> None:
    """Remove a saved station."""
    path = path or stations_file()
    stations = load_saved_stations(path)
    remaining = [station for station in stations if int(station["id"]) != int(station_id)]
    if len(remaining) == len(stations):
        raise KeyError(f"no saved station with id {station_id}")
    _write_saved_stations(remaining, path)


def saved_station_prices(
    *,
    fuel: str = "benzina",
    near: str | None = None,
    now: datetime | None = None,
    path: Path | None = None,
    session: Any | None = None,
) -> list[dict[str, Any]]:
    """Current prices at the saved stations (optionally only those near "home", "work", ...),
    cheapest self-service first."""
    results = []
    for station in load_saved_stations(path):
        if near and station.get("near", "").casefold() != near.casefold():
            continue
        try:
            detail = station_prices(int(station["id"]), fuel=fuel, now=now, session=session)
        except FuelError as error:
            results.append({**station, "error": str(error), "prices": []})
            continue
        results.append(
            {
                **station,
                "map": _map_link(station.get("latitude"), station.get("longitude")),
                "prices": detail["prices"],
            }
        )

    def best(station: dict[str, Any]) -> float:
        own = [p["price"] for p in station["prices"] if p["self_service"]] or [p["price"] for p in station["prices"]]
        return min(own) if own else float("inf")

    return sorted(results, key=best)
