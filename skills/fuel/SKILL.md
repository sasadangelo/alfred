---
name: fuel
description: Use when the user asks about fuel prices, where to refuel, the cheapest petrol or diesel station near home, work, along the commute, or near a place, or wants to save or review favorite fuel stations.
---

# Fuel

Use the `fuel` MCP tools for prices of individual Italian stations, as communicated to the Ministry's price observatory (MIMIT), and `get_user_profile` from the `user-profile` server for places and vehicles.

## Fuel and places

1. The fuel comes from the user's vehicles in the profile: omit `fuel` and the tools use it. If the vehicles use different fuels, ask which one (or show both).
2. Search around saved places using their `latitude` and `longitude` (home, work). For other places, get coordinates with the `traffic` skill's `find_address`.
3. Default to self-service prices; show full-service ones only if asked.

## Finding the cheapest

1. Call `find_fuel_stations` (radius 5 km by default; widen up to 10 km if few results).
2. Answer in Italian with a short table: price per litre (3 decimals), distance, brand and address, and when the price was communicated ("oggi alle 7:10", "3 giorni fa").
3. Prices are what each station last communicated. Flag `stale: true` (over 72 hours) as possibly out of date. Registry addresses are sometimes wrong: use the `map` link for the position.
4. Put savings in perspective: the difference per full tank (about 45 litres) is often a few cents per litre. When a cheaper station is farther away, mention the detour; for the commute, compare with the `traffic` skill.

## Saved stations

1. To build the user's list, search near home and work, show the stations, and save the ones the user picks with `save_fuel_station`, passing the coordinates from the search and `near` with the place label.
2. `list_saved_fuel_stations` gives current prices at those stations, cheapest first; `near` filters by place.
3. Remove stations with `forget_fuel_station` only when the user asks.

## Limits

The observatory's API is free but not officially documented: avoid repeated searches in a short time (results are cached for 15 minutes). If it fails, say so and suggest trying later.
