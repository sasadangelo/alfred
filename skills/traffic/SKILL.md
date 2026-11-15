---
name: traffic
description: Use when the user asks about traffic, travel time by car, delays, queues or road works, how long it takes to get somewhere, or when to leave to arrive on time — for the commute, an appointment, or any address.
---

# Traffic

Use the `traffic` MCP tools (TomTom) for car routes with live and predicted traffic, and `get_user_profile` from the `user-profile` server for the user's places, commute, and office hours. Never hard-code addresses or habits in answers: read them from the profile.

## Places

1. Home, work, and other saved places come from `places` in the profile. When a place has `latitude` and `longitude`, use them directly: do not search its address again.
2. Otherwise call `find_address` (use `country="IT"` for Italian addresses unless the user says otherwise). Prefer a candidate with `street_matches: true`; TomTom does not know every street, so such a match may come from OpenStreetMap (`source`). If none matches, or several do, show the options and ask.
3. For a saved place without coordinates, tell the user which address you found and, after they confirm, save its coordinates with `save_place` (label, `latitude`, `longitude`) from the `user-profile` server, so the next trips use them.
4. For a one-off destination (an appointment), use the best match without saving it.

## Routes

1. Call `get_route` with origin and destination coordinates.
   - "Now" or "how is the traffic": no times.
   - "If I leave at 8": `depart_at`.
   - "To be there at 12:30": `arrive_at`; the result's `departure` is when to leave.
   Times must be in the future; for past times, explain that only now or future trips can be computed.
2. Answer in Italian, short: travel time, distance, delay caused by traffic (say "nessun ritardo" when it is 0), and, when planning, the departure time rounded down to 5 minutes with a margin of 5–10 minutes.
3. Mention `traffic_sections` that matter: severity "moderato" or "forte", closures, or a delay of 5 minutes or more. Describe where by the nearest place name if you know it, otherwise just the kind and the delay.

## Commute

On office days (`preferences.work_schedule`):

- Morning: plan the trip from home to work with `arrive_at` at the start of `preferences.office_arrival`.
- Evening: plan from work to home with `depart_at` at the start of `preferences.office_return`.

If those preferences are missing, ask once and offer to save them with the `user-profile` skill.

## Appointments

For a calendar event with a location (from the `google-calendar` skill), plan the trip from where the user will be (home by default) with `arrive_at` at the event start, and suggest when to leave. Offer to add a reminder at that time; create it only if the user agrees.

## Weather

When the trip is soon and the weather may affect driving (rain, fog, strong wind), you may add a short note using the `weather` skill.

## Setup

If a tool reports that the TomTom key is missing or not allowed, explain that Alfred needs a free key from developer.tomtom.com with the Search, Routing, and Traffic APIs enabled, set as the plugin option "TomTom API key". Never ask the user to paste the key into the chat.
