"""User-profile MCP server: read and update the locally stored profile of the user."""

from collections.abc import Callable
from datetime import date
from typing import Any

from fastmcp import FastMCP

from alfred import profile as store
from alfred import subscriptions as subs

mcp = FastMCP(
    name="user-profile",
    instructions=(
        "A local profile of the user: personal details, family, places, vehicles, preferences and notes, "
        "plus utilities and subscriptions (luce, gas, internet, domini, abbonamenti) in a separate file. "
        "Dates are YYYY-MM-DD. Every profile change returns the updated profile."
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


def _dump(items: list[subs.Subscription]) -> list[dict[str, Any]]:
    return [{"id": item.id} | item.model_dump(exclude_defaults=True) for item in items]


@mcp.tool
def list_subscriptions(
    kind: str | None = None, place: str | None = None, include_inactive: bool = False, renewal_days: int = 60
) -> dict[str, Any]:
    """List the user's utilities and subscriptions (kept in subscriptions.yaml), optionally by kind
    (e.g. "luce", "gas", "dominio") or place (e.g. "home"), plus those renewing or expiring within
    renewal_days."""
    items = subs.load_subscriptions()
    matching = subs.find_subscriptions(items, kind=kind, place=place, active_only=not include_inactive)
    return {
        "subscriptions": _dump(matching),
        "upcoming_renewals": subs.upcoming_renewals(items, days=renewal_days),
    }


@mcp.tool
def save_subscription(
    kind: str | None = None,
    provider: str | None = None,
    subscription_id: str | None = None,
    place: str | None = None,
    identifiers: dict[str, str | None] | None = None,
    details: str | None = None,
    frequency: str | None = None,
    amount_eur: float | None = None,
    renewal: str | None = None,
    payment: str | None = None,
    email_match: str | None = None,
    documents_folder: str | None = None,
    filename_pattern: str | None = None,
    active: bool | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Add or update a utility or subscription; omitted fields are kept.

    kind e.g. "luce", "gas", "acqua", "internet", "telefono", "assicurazione", "dominio", "streaming";
    provider e.g. "Illumia"; place is a profile place label ("home") or a short name ("condominio").
    identifiers merges codes such as {"POD": "...", "cliente": "..."}; an empty value removes one.
    frequency: mensile, bimestrale, trimestrale, semestrale, annuale or "una tantum".
    renewal is MM-DD for a yearly renewal or YYYY-MM-DD for a one-off expiry.
    email_match is a Gmail query that finds its emails (e.g. "from:illumia.it"); documents_folder and
    filename_pattern say where and how to save its bills (e.g. "{provider}_{periodo}.pdf").
    Pass subscription_id to change an existing entry; without it, the same kind + provider + place
    is updated instead of duplicated. active=false keeps a cancelled one for the record.
    """
    fields = {
        "kind": kind,
        "provider": provider,
        "place": place,
        "details": details,
        "frequency": frequency,
        "amount_eur": amount_eur,
        "renewal": renewal,
        "payment": payment,
        "email_match": email_match,
        "documents_folder": documents_folder,
        "filename_pattern": filename_pattern,
        "active": active,
        "notes": notes,
    }
    items, entry = subs.save_subscription(
        subs.load_subscriptions(), subscription_id=subscription_id, identifiers=identifiers, **fields
    )
    subs.write_subscriptions(items)
    return {"saved": _dump([entry])[0], "count": len(items)}


@mcp.tool
def forget_subscription(subscription_id: str) -> dict[str, Any]:
    """Delete a utility or subscription by id (to keep it for the record, save it with active=false)."""
    items = subs.forget_subscription(subs.load_subscriptions(), subscription_id)
    subs.write_subscriptions(items)
    return {"removed": subscription_id, "count": len(items)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
