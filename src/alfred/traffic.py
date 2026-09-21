"""Traffic information from the TomTom Routing API."""

from datetime import datetime

import requests

from alfred.core.config import AlfredSettings

GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
ROUTES_URL = "https://api.tomtom.com/routing/1/calculateRoute"
USER_AGENT = "Alfred/0.1"
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _format_duration(seconds: int) -> str:
    """Format a duration in hours and minutes."""
    hours, remaining_seconds = divmod(seconds, 3600)
    minutes = remaining_seconds // 60
    if hours:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"


def _geocode(address: str) -> tuple[float, float]:
    """Convert an address to latitude and longitude with OpenStreetMap."""
    response = requests.get(
        GEOCODE_URL,
        params={"q": address, "format": "jsonv2", "limit": "1", "countrycodes": "it"},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    position = response.json()[0]
    return float(position["lat"]), float(position["lon"])


def get_traffic_data(settings: AlfredSettings, api_key: str, now: datetime | None = None) -> str | None:
    """Return current commute traffic on configured workdays."""
    current_time = now or datetime.now().astimezone()
    if WEEKDAYS[current_time.weekday()] not in settings.work.days:
        return None

    try:
        origin = _geocode(settings.home.address)
        destination = _geocode(settings.work.address)
        locations = f"{origin[0]},{origin[1]}:{destination[0]},{destination[1]}"
        response = requests.get(
            f"{ROUTES_URL}/{locations}/json",
            params={
                "key": api_key,
                "traffic": "true",
                "travelMode": "car",
                "routeType": "fastest",
                "computeTravelTimeFor": "all",
            },
            timeout=10,
        )
        response.raise_for_status()
        summary = response.json()["routes"][0]["summary"]
        duration = int(summary["travelTimeInSeconds"])
        delay = int(summary["trafficDelayInSeconds"])
        distance = summary["lengthInMeters"] / 1000
        return (
            "🚗 *Traffico casa-lavoro*\n\n"
            f"• Destinazione: {settings.work.company}\n"
            f"• Distanza: {distance:.1f} km\n"
            f"• Tempo stimato: {_format_duration(duration)}\n"
            f"• Ritardo dovuto al traffico: {_format_duration(delay)}"
        )
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as error:
        return f"🚗 *Traffico casa-lavoro*\n\nImpossibile recuperare il traffico: {error}"
