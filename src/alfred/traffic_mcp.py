"""Traffic MCP server: TomTom address search and car routes with live traffic."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastmcp import FastMCP

from alfred import traffic_routes
from alfred.paths import timezone as configured_timezone

mcp = FastMCP(
    name="traffic",
    instructions=(
        "Car routes with live traffic from TomTom. find_address turns an address into coordinates; "
        "get_route returns travel time, traffic delay and traffic sections, leaving now, at a time, "
        "or arriving by a time. Naive times use the configured timezone."
    ),
)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(configured_timezone()))
    return parsed


@mcp.tool
def find_address(query: str, count: int = 5, country: str | None = None) -> list[dict[str, Any]]:
    """Find coordinates for an address or place, e.g. "Via Roma 1, Bologna"; country is an ISO code
    such as "IT" to restrict the search."""
    return traffic_routes.find_address(query, count=count, country=country)


@mcp.tool
def get_route(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    depart_at: str | None = None,
    arrive_at: str | None = None,
) -> dict[str, Any]:
    """Fastest car route with traffic. Leave now by default; depart_at or arrive_at (ISO-8601, in the
    future) plan ahead using predicted traffic. Returns distance_km, travel_minutes,
    traffic_delay_minutes, departure, arrival and traffic_sections (queues, road works, closures)."""
    return traffic_routes.get_route(
        (origin_latitude, origin_longitude),
        (destination_latitude, destination_longitude),
        depart_at=_parse_time(depart_at),
        arrive_at=_parse_time(arrive_at),
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
