"""Weather MCP server: Open-Meteo forecasts and place search."""

from datetime import date
from typing import Any

from fastmcp import FastMCP

from alfred import weather_forecast

mcp = FastMCP(
    name="weather",
    instructions=(
        "Weather forecasts from Open-Meteo for today and the next 15 days. find_place turns a town "
        "name into coordinates; get_weather_forecast returns daily data, alerts and, with "
        "hour_from/hour_to, hourly data in the place's local time."
    ),
)


@mcp.tool
def find_place(name: str, count: int = 5) -> list[dict[str, Any]]:
    """Search a town or city by name (not a street address); returns candidates with coordinates,
    province and region so namesakes can be told apart."""
    return weather_forecast.find_place(name, count=count)


@mcp.tool
def get_weather_forecast(
    latitude: float,
    longitude: float,
    start_date: str | None = None,
    end_date: str | None = None,
    hour_from: str | None = None,
    hour_to: str | None = None,
) -> dict[str, Any]:
    """Forecast for a place from start_date to end_date (YYYY-MM-DD, default today).

    Each day has min/max and feels-like temperatures, rain probability and mm, wind and gusts,
    UV, sunrise/sunset and alerts. hour_from/hour_to (HH:MM, e.g. "07:00"/"09:00") add hourly
    data for that window. Current conditions are included when start_date is today.
    """
    return weather_forecast.get_forecast(
        latitude,
        longitude,
        start_date=date.fromisoformat(start_date) if start_date else None,
        end_date=date.fromisoformat(end_date) if end_date else None,
        hour_from=hour_from,
        hour_to=hour_to,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
