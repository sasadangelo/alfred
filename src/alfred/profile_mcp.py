"""User-profile MCP server: read and update the locally stored profile of the user."""

from collections.abc import Callable
from datetime import date
from typing import Any

from fastmcp import FastMCP

from alfred import profile as store
from alfred.core.config import get_settings

mcp = FastMCP(
    name="user-profile",
    instructions=(
        "A local profile of the user: personal details, family, places, vehicles, preferences and notes. "
        "Dates are YYYY-MM-DD. Every change returns the updated profile."
    ),
)


def _load() -> store.Profile:
    """Load the profile, seeding name and places from config.yaml the first time."""
    profile = store.load_profile()
    try:
        settings = get_settings()
    except Exception:  # config.yaml is optional for the profile  # noqa: BLE001
        return profile
    seeded = store.seed_from_settings(profile, settings)
    if seeded != profile:
        store.save_profile(seeded)
    return seeded


def _change(update: Callable[[store.Profile], store.Profile]) -> dict[str, Any]:
    profile = update(_load())
    store.save_profile(profile)
    return store.describe_profile(profile)


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@mcp.tool
def get_user_profile() -> dict[str, Any]:
    """Return the saved profile plus derived ages, upcoming birthdays (next 30 days) and the
    onboarding questions still unanswered (missing_essentials)."""
    return store.describe_profile(_load())


@mcp.tool
def save_my_details(
    name: str | None = None,
    birth_date: str | None = None,
    birth_place: str | None = None,
    source: str = "user",
) -> dict[str, Any]:
    """Save the user's own name, birth date or birth place; omitted fields are kept.

    source records where the fact came from (e.g. "user", "google-contacts").
    """
    return _change(
        lambda p: store.update_me(
            p, name=name, birth_date=_parse_date(birth_date), birth_place=birth_place, source=source
        )
    )


@mcp.tool
def save_family_member(
    name: str,
    relation: str | None = None,
    birth_date: str | None = None,
    birth_place: str | None = None,
    source: str = "user",
) -> dict[str, Any]:
    """Add or update a family member by name (relation e.g. "moglie", "figlio"); omitted fields are kept."""
    return _change(
        lambda p: store.save_family_member(
            p, name, relation=relation, birth_date=_parse_date(birth_date), birth_place=birth_place, source=source
        )
    )


@mcp.tool
def save_place(label: str, address: str, company: str | None = None, source: str = "user") -> dict[str, Any]:
    """Add or replace a named place: label "home", "work", "school", or any other name (e.g. "palestra")."""
    return _change(lambda p: store.save_place(p, label, address, company=company, source=source))


@mcp.tool
def save_vehicle(
    name: str,
    fuel: store.FuelType | None = None,
    plate: str | None = None,
    owner: str | None = None,
    source: str = "user",
) -> dict[str, Any]:
    """Add or update a vehicle (name e.g. "Peugeot 2008"); owner is the family member who uses it."""
    return _change(lambda p: store.save_vehicle(p, name, fuel=fuel, plate=plate, owner=owner, source=source))


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
def forget_profile_item(section: store.Section, key: str = "") -> dict[str, Any]:
    """Delete one saved fact: a family member or vehicle by name, a place or preference by key, a note
    containing key, or the user's own details with section "me"."""
    return _change(lambda p: store.forget(p, section, key))


if __name__ == "__main__":
    mcp.run(transport="stdio")
