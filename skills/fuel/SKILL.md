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

The stations near the user's places are saved in `fuel-stations.yaml` in Alfred's data directory, each with its distance from "home" and/or "work" (places from the profile); the user's regular station has `usual: true`. Prices are never stored: they are read live.

1. To build or refresh the list for a place, call `collect_fuel_stations` with `near` ("home", "work"; 5 km by default). It keeps the usual station even when it falls outside the radius.
2. For "prezzi dei miei distributori" or "quanto costa al mio distributore", call `list_saved_fuel_stations`: `order="distance"` (closest first, the default) or `order="price"` (cheapest first); `near` filters by place; `limit` keeps it short.
3. Always compare with the usual station: say how much cheaper the best alternative is per litre and per full tank, and whether the detour is worth it.
4. Mark or change the usual station with `save_fuel_station` (`usual=true`; this unmarks the previous one); remove stations with `forget_fuel_station` only when the user asks.

## Limits

The observatory's API is free but not officially documented: avoid repeated searches in a short time (results are cached for 15 minutes). If it fails, say so and suggest trying later.
