"""Fuel MCP server: prices of individual stations from the Italian price observatory (MIMIT)."""

from typing import Any

from fastmcp import FastMCP

from alfred import fuel_prices
from alfred import profile as profile_store

mcp = FastMCP(
    name="fuel",
    instructions=(
        "Fuel prices of individual Italian stations from the Ministry's observatory, with the time each "
        "price was last communicated. When fuel is omitted it comes from the user's vehicles in the profile."
    ),
)


def _fuel(fuel: str | None) -> str:
    if fuel:
        return fuel
    fuels = sorted({v.fuel for v in profile_store.load_profile().vehicles if v.fuel and v.fuel != "elettrica"})
    if len(fuels) == 1:
        return fuels[0]
    if not fuels:
        raise ValueError("no fuel type in the profile's vehicles: pass fuel (benzina, gasolio, gpl, metano)")
    raise ValueError(f"the vehicles use several fuels ({', '.join(fuels)}): pass fuel")


@mcp.tool
def find_fuel_stations(
    latitude: float,
    longitude: float,
    radius_km: float = 5,
    fuel: str | None = None,
    self_service: bool = True,
    count: int = 10,
) -> list[dict[str, Any]]:
    """Cheapest stations near a point (radius 0.5-10 km), with distance, map link, price and how many
    hours ago the station communicated it (stale=true after 72 hours)."""
    return fuel_prices.find_stations(
        latitude, longitude, radius_km=radius_km, fuel=_fuel(fuel), self_service=self_service, count=count
    )


@mcp.tool
def get_fuel_station_prices(station_id: int, fuel: str | None = None) -> dict[str, Any]:
    """Current self-service and full-service prices of one station."""
    return fuel_prices.station_prices(station_id, fuel=_fuel(fuel))


@mcp.tool
def collect_fuel_stations(near: str = "home", radius_km: float = 5, fuel: str | None = None) -> list[dict[str, Any]]:
    """Save every station selling the fuel within radius_km of a profile place ("home",
    "work"), with distance, closest first. Running it again refreshes the list and keeps the usual station."""
    return fuel_prices.collect_stations(near, radius_km=radius_km, fuel=_fuel(fuel))


@mcp.tool
def list_saved_fuel_stations(
    fuel: str | None = None, near: str | None = None, order: str = "distance", limit: int | None = None
) -> list[dict[str, Any]]:
    """Live prices at the saved stations; near filters by place ("home", "work");
    order is "distance" (closest first) or "price" (cheapest first); usual=true marks the user's station."""
    return fuel_prices.saved_station_prices(fuel=_fuel(fuel), near=near, order=order, limit=limit)


@mcp.tool
def save_fuel_station(
    station_id: int,
    near: str | None = None,
    distance_km: float | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    usual: bool | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Add or update one saved station, e.g. usual=true for the user's regular station (unmarks the old one).
    near and distance_km go together; omitted fields are kept."""
    return fuel_prices.save_station(
        station_id,
        near=near,
        distance_km=distance_km,
        latitude=latitude,
        longitude=longitude,
        usual=usual,
        note=note,
    )


@mcp.tool
def forget_fuel_station(station_id: int) -> dict[str, int]:
    """Remove a saved station."""
    fuel_prices.forget_station(station_id)
    return {"removed": station_id}


if __name__ == "__main__":
    mcp.run(transport="stdio")
