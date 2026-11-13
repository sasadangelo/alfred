---
name: weather
description: Use when the user asks about the weather, rain, wind, temperature, whether to take an umbrella, what to wear, or whether conditions suit an outdoor activity such as running, for today, tomorrow, the weekend, or the next days, at home, at work, or in a named town.
---

# Weather

Use the `weather` MCP tools (Open-Meteo, free) for forecasts, and `get_user_profile` from the `user-profile` server for where the user lives, works, and runs. Never hard-code places or habits in answers: read them from the profile.

## Where

1. Default place: the user's home (`places.home`). On office days in `preferences.work_schedule`, also consider work (`places.work`) for the commute.
2. For home, work, or any address, search the town in the address with `find_place` (for example "Bologna" from "Via Roma 1, 00100 Roma"); it finds towns, not streets. When the user names a place, call `find_place` with it.
3. If several candidates match (same name in different regions), pick the one that fits the context (the user's region, an appointment's location); if still unclear, ask. Never send the user's name or full address to the weather service: only the town.

## When

1. Interpret relative dates in `Europe/Rome`. Forecasts cover today and the next 15 days; beyond that, say so.
2. Call `get_weather_forecast` with the coordinates and the date range. Ask for `hour_from`/`hour_to` whenever a time of day matters (a run, a commute, an appointment).

## Answering

1. Answer in Italian, short: condition, min/max temperature, feels-like when it differs by 2°C or more, rain probability and amount, wind when notable.
2. Always report the day's `alerts`. They are computed by the server with fixed thresholds: never invent other alerts or drop them.
3. Umbrella: suggest it when rain probability is 40% or more, or 0.5 mm or more is expected, during the hours the user is out.
4. Treat forecasts as forecasts: past 3 days, say they may change.

## Running

The user's running habits are in `preferences.running` (days, time window, starting place). For a question about a run, or when the next day is a running day:

1. Get the forecast for the running window with `hour_from`/`hour_to`, using the hourly data, not the daily totals.
2. Say whether conditions are favorable. Unfavorable means: rain probability 50% or more or rain in the window, thunderstorms, gusts 40 km/h or more, feels-like below 0°C or above 28°C, or fog with poor visibility. If unfavorable, look at the rest of the morning (for example 06:00–12:00) and suggest a better hour if there is one.
3. Note when the run starts before sunrise (compare with `sunrise`): suggest reflective or visible clothing and a light.
4. Suggest clothing from the feels-like temperature in the window. These are guidelines; adapt to wind and rain:
   - 18°C or more: canotta or maglia tecnica corta, pantaloncini; hydrate.
   - 12–18°C: maglia tecnica corta, pantaloncini.
   - 7–12°C: maglia tecnica a maniche lunghe leggera, pantaloncini o pantaloni 3/4.
   - 2–7°C: maglia termica, calzamaglia lunga, guanti leggeri.
   - below 2°C: due strati con antivento, calzamaglia lunga, guanti, cappellino o fascia.
   - Wind 20 km/h or more: add a windproof layer. Light rain: smanicato or giacca antipioggia leggera and a cap with a visor.

## Commute

On office days (`preferences.work_schedule`), check the commute hours with hourly data: the hour before `preferences.office_arrival` through the arrival window for the morning, and `preferences.office_return` for the evening. If those are missing, use early morning and late afternoon and say so. Mention umbrella, fog, strong wind, wet roads, and darkness that affect driving.
