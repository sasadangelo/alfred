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
def save_fuel_station(
    station_id: int,
    latitude: float | None = None,
    longitude: float | None = None,
    near: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Save a station the user cares about; near is a profile place label such as "home" or "work".
    Pass the coordinates from find_fuel_stations: the registry has no coordinates."""
    return fuel_prices.save_station(station_id, latitude=latitude, longitude=longitude, near=near, note=note)


@mcp.tool
def forget_fuel_station(station_id: int) -> dict[str, int]:
    """Remove a saved station."""
    fuel_prices.forget_station(station_id)
    return {"removed": station_id}


@mcp.tool
def list_saved_fuel_stations(fuel: str | None = None, near: str | None = None) -> list[dict[str, Any]]:
    """Current prices at the saved stations, cheapest first; near filters by place label."""
    return fuel_prices.saved_station_prices(fuel=_fuel(fuel), near=near)


if __name__ == "__main__":
    mcp.run(transport="stdio")
