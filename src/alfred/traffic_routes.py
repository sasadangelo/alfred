"""Car routes with live traffic and address search from TomTom.

Functions return structured data; how to phrase it (when to leave, which delays matter) is up to
the caller. The API key comes from the plugin option or ``alfred.env`` (``ALFRED_TOMTOM_API_KEY``).
"""

from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests

from alfred.paths import secret

API_KEY_NAME = "ALFRED_TOMTOM_API_KEY"  # pragma: allowlist secret
GEOCODE_URL = "https://api.tomtom.com/search/2/geocode"
ROUTE_URL = "https://api.tomtom.com/routing/1/calculateRoute"
REQUEST_TIMEOUT_SECONDS = 10

# TomTom "simpleCategory" values for traffic sections, in Italian.
TRAFFIC_CATEGORIES = {
    "JAM": "coda",
    "ROAD_WORK": "lavori in corso",
    "ROAD_CLOSURE": "strada chiusa",
    "OTHER": "rallentamento",
}
DELAY_MAGNITUDES = {0: "sconosciuto", 1: "lieve", 2: "moderato", 3: "forte", 4: "strada chiusa"}


class TrafficError(RuntimeError):
    """A traffic service failure explained in terms the user can act on."""


def _api_key() -> str:
    key = secret(API_KEY_NAME)
    if not key:
        raise TrafficError(
            'TomTom API key is not configured: set the plugin option "TomTom API key", '
            f"or add {API_KEY_NAME} to alfred.env in the plugin data directory."
        )
    return key


def _get(session: Any, url: str, params: dict[str, Any], what: str) -> dict[str, Any]:
    try:
        response = (session or requests).get(url, params={**params, "key": _api_key()}, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as error:
        raise TrafficError(f"Could not {what}: TomTom is unreachable ({error}).") from error
    if response.status_code == 403:
        raise TrafficError(
            f"Could not {what}: the TomTom key is not allowed to use this API. "
            "Enable the Search, Routing and Traffic APIs for the key in the TomTom developer dashboard."
        )
    if response.status_code == 429:
        raise TrafficError(f"Could not {what}: the TomTom daily quota is used up; try again later.")
    if response.status_code >= 400:
        try:
            detail = response.json().get("detailedError", {}).get("message") or response.json().get("error", "")
        except ValueError:
            detail = ""
        raise TrafficError(f"Could not {what} ({response.status_code}): {detail or 'request rejected'}.")
    data: dict[str, Any] = response.json()
    return data


def find_address(
    query: str, *, count: int = 5, country: str | None = None, session: Any | None = None
) -> list[dict[str, Any]]:
    """Turn an address or place name into coordinates, best matches first."""
    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= count <= 20:
        raise ValueError("count must be between 1 and 20")
    params: dict[str, Any] = {"limit": count, "language": "it-IT"}
    if country:
        params["countrySet"] = country.upper()
    data = _get(session, f"{GEOCODE_URL}/{quote(query.strip(), safe='')}.json", params, "find the address")
    return [
        {
            "address": str(item.get("address", {}).get("freeformAddress", "")),
            "municipality": str(item.get("address", {}).get("municipality", "")),
            "region": str(item.get("address", {}).get("countrySubdivision", "")),
            "country": str(item.get("address", {}).get("countryCode", "")),
            "latitude": float(item["position"]["lat"]),
            "longitude": float(item["position"]["lon"]),
            "match": str(item.get("type", "")),
        }
        for item in data.get("results", [])
    ]


def _minutes(seconds: Any) -> int:
    return round(int(seconds or 0) / 60)


def _check_point(latitude: float, longitude: float) -> str:
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("latitude/longitude out of range")
    return f"{latitude},{longitude}"


def get_route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    *,
    depart_at: datetime | None = None,
    arrive_at: datetime | None = None,
    now: datetime | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """Return the fastest car route with traffic, leaving now, at ``depart_at`` or arriving by ``arrive_at``.

    Times must be timezone-aware and in the future. The result has distance, travel time, the delay
    caused by traffic, departure and arrival times, and the traffic sections along the way.
    """
    if depart_at and arrive_at:
        raise ValueError("pass depart_at or arrive_at, not both")
    moment = depart_at or arrive_at
    if moment is not None:
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("depart_at/arrive_at must include a timezone")
        current = now or datetime.now(moment.tzinfo)
        if moment <= current:
            raise ValueError("depart_at/arrive_at must be in the future; omit them to leave now")

    locations = f"{_check_point(*origin)}:{_check_point(*destination)}"
    params: dict[str, Any] = {
        "traffic": "true",
        "travelMode": "car",
        "routeType": "fastest",
        "computeTravelTimeFor": "all",
        "sectionType": "traffic",
    }
    if depart_at:
        params["departAt"] = depart_at.isoformat(timespec="seconds")
    if arrive_at:
        params["arriveAt"] = arrive_at.isoformat(timespec="seconds")
    data = _get(session, f"{ROUTE_URL}/{locations}/json", params, "calculate the route")

    routes = data.get("routes") or []
    if not routes:
        raise TrafficError("TomTom found no car route between these points.")
    route = routes[0]
    summary = route.get("summary", {})
    points = [point for leg in route.get("legs", []) for point in leg.get("points", [])]
    sections = []
    for section in route.get("sections", []):
        if section.get("sectionType") != "TRAFFIC":
            continue
        start = points[section["startPointIndex"]] if section.get("startPointIndex", -1) < len(points) else {}
        sections.append(
            {
                "kind": TRAFFIC_CATEGORIES.get(str(section.get("simpleCategory", "")), "rallentamento"),
                "severity": DELAY_MAGNITUDES.get(int(section.get("magnitudeOfDelay", 0)), "sconosciuto"),
                "delay_minutes": _minutes(section.get("delayInSeconds")),
                "speed_kmh": section.get("effectiveSpeedInKmh"),
                "latitude": start.get("latitude"),
                "longitude": start.get("longitude"),
            }
        )

    travel = int(summary.get("travelTimeInSeconds", 0))
    no_traffic = summary.get("noTrafficTravelTimeInSeconds")
    return {
        "distance_km": round(int(summary.get("lengthInMeters", 0)) / 1000, 1),
        "travel_minutes": _minutes(travel),
        "traffic_delay_minutes": _minutes(summary.get("trafficDelayInSeconds")),
        "no_traffic_minutes": _minutes(no_traffic) if no_traffic is not None else None,
        "departure": str(summary.get("departureTime", "")),
        "arrival": str(summary.get("arrivalTime", "")),
        "traffic_sections": sections,
    }
