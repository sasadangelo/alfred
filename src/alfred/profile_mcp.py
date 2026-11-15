"""User-profile MCP server: read and update the locally stored profile of the user."""

from collections.abc import Callable
from datetime import date
from typing import Any

from fastmcp import FastMCP

from alfred import profile as store

mcp = FastMCP(
    name="user-profile",
    instructions=(
        "A local profile of the user: personal details, family, places, vehicles, preferences and notes. "
        "Dates are YYYY-MM-DD. Every change returns the updated profile."
    ),
)


def _load() -> store.Profile:
    return store.load_profile()


def _change(update: Callable[[store.Profile], store.Profile]) -> dict[str, Any]:
    profile = update(_load())
    store.save_profile(profile)
    return store.describe_profile(profile)


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@mcp.tool
def get_user_profile() -> dict[str, Any]:
    """Return the saved profile plus derived ages, upcoming birthdays and vehicle deadlines (next 30
    days) and the onboarding questions still unanswered (missing_essentials)."""
    return store.describe_profile(_load())


@mcp.tool
def save_my_details(
    first_name: str | None = None,
    last_name: str | None = None,
    nickname: str | None = None,
    birth_date: str | None = None,
    birth_place: str | None = None,
    source: str = "user",
) -> dict[str, Any]:
    """Save the user's own first/last name, nickname, birth date or birth place; omitted fields are kept.

    source records where the fact came from (e.g. "user", "google-contacts").
    """
    return _change(
        lambda p: store.update_me(
            p,
            first_name=first_name,
            last_name=last_name,
            nickname=nickname,
            birth_date=_parse_date(birth_date),
            birth_place=birth_place,
            source=source,
        )
    )


@mcp.tool
def save_family_member(
    first_name: str | None = None,
    last_name: str | None = None,
    birth_date: str | None = None,
    person_id: str | None = None,
    nickname: str | None = None,
    relation: str | None = None,
    birth_place: str | None = None,
    deceased: bool | None = None,
    source: str = "user",
) -> dict[str, Any]:
    """Add or update a family member; omitted fields are kept.

    To change an existing person, pass their person_id (the "id" in get_user_profile): then any
    field can be corrected, including first_name, last_name and birth_date. Without person_id a
    person is found by first_name + last_name + birth_date, so namesakes stay separate (pass
    birth_date whenever it is known), and a new person is added when none matches.
    relation e.g. "moglie", "figlio"; nickname e.g. "Betty".
    deceased=true marks a relative who has passed away: no age is computed for them.
    """
    return _change(
        lambda p: store.save_family_member(
            p,
            first_name,
            last_name,
            person_id=person_id,
            nickname=nickname,
            relation=relation,
            birth_date=_parse_date(birth_date),
            birth_place=birth_place,
            deceased=deceased,
            source=source,
        )
    )


@mcp.tool
def save_place(
    label: str,
    address: str | None = None,
    company: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    source: str = "user",
) -> dict[str, Any]:
    """Add or update a named place: label "home", "work", "school", or any other name (e.g. "palestra").

    Omitted fields are kept, so verified coordinates can be added to an existing place without its
    address. Changing the address without new coordinates drops the old coordinates.
    """
    return _change(
        lambda p: store.save_place(
            p, label, address, company=company, latitude=latitude, longitude=longitude, source=source
        )
    )


@mcp.tool
def save_vehicle(
    name: str | None = None,
    vehicle_id: str | None = None,
    fuel: store.FuelType | None = None,
    plate: str | None = None,
    owner: str | None = None,
    deadlines: dict[str, str | None] | None = None,
    source: str = "user",
) -> dict[str, Any]:
    """Add or update a vehicle (name e.g. "Peugeot 2008"); owner is the family member who uses it.

    Pass vehicle_id (the "id" in get_user_profile) to correct any field of an existing vehicle,
    including its name; without it the vehicle is matched by plate, then by name.
    deadlines merges yearly deadlines as MM-DD, e.g. {"bollo": "09-30", "assicurazione": "12-31"};
    an empty value removes one. Upcoming ones appear in get_user_profile as upcoming_deadlines.
    """
    return _change(
        lambda p: store.save_vehicle(
            p, name, vehicle_id=vehicle_id, fuel=fuel, plate=plate, owner=owner, deadlines=deadlines, source=source
        )
    )


@mcp.tool
def set_user_preference(key: str, value: str) -> dict[str, Any]:
    """Set a preference, e.g. key "commute" = "auto", or "preferred_fuel_brand" = "Q8"."""
    return _change(lambda p: store.set_preference(p, key, value))


@mcp.tool
def add_profile_note(text: str, source: str = "user") -> dict[str, Any]:
    """Remember a free-form fact that has no dedicated field."""
    return _change(lambda p: store.add_note(p, text, source=source))


@mcp.tool
def skip_onboarding_question(key: str) -> dict[str, Any]:
    """Record that the user does not want to answer an onboarding question (a missing_essentials key)."""
    return _change(lambda p: store.skip_essential(p, key))


@mcp.tool
def forget_profile_item(section: store.Section, key: str = "", birth_date: str | None = None) -> dict[str, Any]:
    """Delete one saved fact: a family member by id, full name or nickname (plus birth_date for
    namesakes), a vehicle by id, name or plate, a place or preference by key, a note containing key, or the user's own
    details with section "me"."""
    return _change(lambda p: store.forget(p, section, key, _parse_date(birth_date)))


if __name__ == "__main__":
    mcp.run(transport="stdio")
