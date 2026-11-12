"""Alfred's user profile: personal facts learned from the user and stored locally.

The profile lives outside the repository (default ``~/.claude/config/profile.yaml``) with
owner-only permissions. Functions that change it are pure: they take a ``Profile`` and return
an updated copy, so callers decide when to ``save_profile``.
"""

import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

PROFILE_FILE_ENV = "ALFRED_PROFILE_FILE"
CONFIG_DIR_ENV = "ALFRED_CONFIG_DIR"
DEFAULT_CONFIG_DIR = Path.home() / ".claude" / "config"
PROFILE_FILENAME = "profile.yaml"
UPCOMING_BIRTHDAY_DAYS = 30

FuelType = Literal["benzina", "gasolio", "gpl", "metano", "elettrica", "ibrida"]
Section = Literal["me", "family", "places", "vehicles", "preferences", "notes"]

# Essential facts for onboarding, in the order Alfred should ask about them.
ESSENTIALS: dict[str, str] = {
    "me": "Come ti chiami e quando sei nato?",
    "home": "Dove abiti?",
    "work": "Dove lavori o studi?",
    "commute": "Come ti sposti di solito: auto, mezzi pubblici, bici, a piedi?",
    "family": "Chi c'è in famiglia? Nomi e, se vuoi, date di nascita.",
    "vehicles": "Che auto o moto usi, e a che carburante va?",
}


class ProfileItem(BaseModel):
    """Common metadata recording where a fact came from and when it was last confirmed."""

    model_config = ConfigDict(extra="forbid")

    source: str = "user"
    updated: date | None = None


def _not_in_future(value: date | None) -> date | None:
    if value is not None and value > date.today():
        raise ValueError("birth_date cannot be in the future")
    return value


class Person(ProfileItem):
    """The user or a family member."""

    name: str
    relation: str = ""
    birth_date: date | None = None
    birth_place: str = ""

    @field_validator("birth_date")
    @classmethod
    def _check_birth_date(cls, value: date | None) -> date | None:
        return _not_in_future(value)


class Place(ProfileItem):
    """A named place such as home, work or school."""

    address: str
    company: str = ""


class Vehicle(ProfileItem):
    """A vehicle the household uses."""

    name: str
    fuel: FuelType | None = None
    plate: str = ""
    owner: str = ""


class Note(ProfileItem):
    """A free-form fact or preference that has no dedicated field."""

    text: str


class Profile(BaseModel):
    """Everything Alfred knows about the user, as confirmed by them."""

    model_config = ConfigDict(extra="forbid")

    me: Person | None = None
    places: dict[str, Place] = Field(default_factory=dict)
    family: list[Person] = Field(default_factory=list)
    vehicles: list[Vehicle] = Field(default_factory=list)
    preferences: dict[str, str] = Field(default_factory=dict)
    notes: list[Note] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)


def profile_file() -> Path:
    """Return the profile path: ALFRED_PROFILE_FILE, else profile.yaml in ALFRED_CONFIG_DIR."""
    if explicit := os.environ.get(PROFILE_FILE_ENV):
        return Path(explicit).expanduser()
    return Path(os.environ.get(CONFIG_DIR_ENV, DEFAULT_CONFIG_DIR)).expanduser() / PROFILE_FILENAME


def load_profile(path: Path | None = None) -> Profile:
    """Load the profile, returning an empty one when the file does not exist yet."""
    path = path or profile_file()
    if not path.is_file():
        return Profile()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Profile.model_validate(data)


def save_profile(profile: Profile, path: Path | None = None) -> Path:
    """Write the profile atomically with owner-only permissions and return its path."""
    path = path or profile_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(
        profile.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
        allow_unicode=True,
        sort_keys=False,
    )
    file_descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".profile-", suffix=".yaml")
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(content)
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return path


def age_on(birth_date: date, today: date) -> int:
    """Return the age in whole years on ``today``."""
    had_birthday = (today.month, today.day) >= (birth_date.month, birth_date.day)
    return today.year - birth_date.year - (0 if had_birthday else 1)


def _next_birthday(birth_date: date, today: date) -> date:
    for year in (today.year, today.year + 1):
        try:
            candidate = birth_date.replace(year=year)
        except ValueError:  # 29 February in a non-leap year
            candidate = date(year, 3, 1)
        if candidate >= today:
            return candidate
    raise AssertionError("unreachable")


def _key(value: str) -> str:
    return " ".join(value.split()).casefold()


def missing_essentials(profile: Profile) -> list[dict[str, str]]:
    """Return the onboarding questions still unanswered and not skipped, in asking order."""
    commute = _key(profile.preferences.get("commute", ""))
    answered = {
        "me": profile.me is not None and profile.me.birth_date is not None,
        "home": "home" in profile.places,
        "work": "work" in profile.places,
        "commute": bool(commute),
        "family": bool(profile.family),
        "vehicles": bool(profile.vehicles) or (bool(commute) and not any(w in commute for w in ("auto", "moto"))),
    }
    return [
        {"key": key, "question": question}
        for key, question in ESSENTIALS.items()
        if not answered[key] and key not in profile.skipped
    ]


def describe_profile(profile: Profile, today: date | None = None) -> dict[str, Any]:
    """Return the profile plus derived facts: ages, upcoming birthdays and missing essentials."""
    today = today or date.today()
    people = ([profile.me] if profile.me else []) + profile.family
    ages = {person.name: age_on(person.birth_date, today) for person in people if person.birth_date}
    upcoming = []
    for person in people:
        if person.birth_date is None:
            continue
        next_birthday = _next_birthday(person.birth_date, today)
        days = (next_birthday - today).days
        if days <= UPCOMING_BIRTHDAY_DAYS:
            upcoming.append(
                {
                    "name": person.name,
                    "date": next_birthday.isoformat(),
                    "in_days": days,
                    "turns": age_on(person.birth_date, next_birthday),
                }
            )
    return {
        "profile": profile.model_dump(mode="json", exclude_none=True),
        "ages": ages,
        "upcoming_birthdays": sorted(upcoming, key=lambda item: item["in_days"]),
        "missing_essentials": missing_essentials(profile),
        "today": today.isoformat(),
    }


def _changes(**fields: Any) -> dict[str, Any]:
    return {name: value for name, value in fields.items() if value is not None}


def update_me(
    profile: Profile,
    *,
    name: str | None = None,
    birth_date: date | None = None,
    birth_place: str | None = None,
    source: str = "user",
    today: date | None = None,
) -> Profile:
    """Set facts about the user; ``None`` keeps the current value."""
    changes = _changes(birth_date=birth_date, birth_place=birth_place, source=source, updated=today or date.today())
    if profile.me is None:
        if not name:
            raise ValueError("name is required the first time the user's details are saved")
        me = Person(name=name.strip(), relation="io", **changes)
    else:
        me = Person.model_validate({**profile.me.model_dump(), **changes, **_changes(name=name and name.strip())})
    return profile.model_copy(update={"me": me})


def save_family_member(
    profile: Profile,
    name: str,
    *,
    relation: str | None = None,
    birth_date: date | None = None,
    birth_place: str | None = None,
    source: str = "user",
    today: date | None = None,
) -> Profile:
    """Add a family member or update the one with the same name; ``None`` keeps current values."""
    if not name.strip():
        raise ValueError("name must not be empty")
    changes = _changes(
        relation=relation, birth_date=birth_date, birth_place=birth_place, source=source, updated=today or date.today()
    )
    family = list(profile.family)
    for index, person in enumerate(family):
        if _key(person.name) == _key(name):
            family[index] = Person.model_validate({**person.model_dump(), **changes})
            break
    else:
        family.append(Person(name=name.strip(), **changes))
    return profile.model_copy(update={"family": family})


def save_place(
    profile: Profile,
    label: str,
    address: str,
    *,
    company: str | None = None,
    source: str = "user",
    today: date | None = None,
) -> Profile:
    """Add or replace a named place; ``label`` is normalized (e.g. "home", "work", "school")."""
    label = _key(label).replace(" ", "_")
    if not label or not address.strip():
        raise ValueError("label and address must not be empty")
    current = profile.places.get(label)
    place = Place(
        address=address.strip(),
        company=company if company is not None else (current.company if current else ""),
        source=source,
        updated=today or date.today(),
    )
    return profile.model_copy(update={"places": {**profile.places, label: place}})


def save_vehicle(
    profile: Profile,
    name: str,
    *,
    fuel: FuelType | None = None,
    plate: str | None = None,
    owner: str | None = None,
    source: str = "user",
    today: date | None = None,
) -> Profile:
    """Add a vehicle or update the one with the same plate (or, without plates, the same name)."""
    if not name.strip():
        raise ValueError("name must not be empty")
    changes = _changes(fuel=fuel, plate=plate and plate.strip().upper(), owner=owner, source=source)
    changes["updated"] = today or date.today()
    vehicles = list(profile.vehicles)
    for index, vehicle in enumerate(vehicles):
        same_plate = bool(changes.get("plate")) and vehicle.plate == changes["plate"]
        same_name = _key(vehicle.name) == _key(name) and (not changes.get("plate") or not vehicle.plate)
        if same_plate or same_name:
            vehicles[index] = Vehicle.model_validate({**vehicle.model_dump(), **changes, "name": name.strip()})
            break
    else:
        vehicles.append(Vehicle(name=name.strip(), **changes))
    return profile.model_copy(update={"vehicles": vehicles})


def set_preference(profile: Profile, key: str, value: str) -> Profile:
    """Set a preference such as ``commute`` or ``preferred_fuel_brand``."""
    key = _key(key).replace(" ", "_")
    if not key or not value.strip():
        raise ValueError("key and value must not be empty")
    skipped = [item for item in profile.skipped if item != key]
    return profile.model_copy(update={"preferences": {**profile.preferences, key: value.strip()}, "skipped": skipped})


def add_note(profile: Profile, text: str, *, source: str = "user", today: date | None = None) -> Profile:
    """Append a free-form note, ignoring exact duplicates."""
    if not text.strip():
        raise ValueError("text must not be empty")
    if any(_key(note.text) == _key(text) for note in profile.notes):
        return profile
    note = Note(text=text.strip(), source=source, updated=today or date.today())
    return profile.model_copy(update={"notes": [*profile.notes, note]})


def skip_essential(profile: Profile, key: str) -> Profile:
    """Remember that the user chose not to answer an onboarding question."""
    if key not in ESSENTIALS:
        raise ValueError(f"unknown onboarding question: {key!r}; expected one of {sorted(ESSENTIALS)}")
    if key in profile.skipped:
        return profile
    return profile.model_copy(update={"skipped": [*profile.skipped, key]})


def forget(profile: Profile, section: Section, key: str = "") -> Profile:
    """Remove one item: a family member or vehicle by name (or plate), a place or preference by
    key, a note containing ``key``, or the user's own details (``section="me"``)."""
    wanted = _key(key)
    if section == "me":
        if profile.me is None:
            raise KeyError("no personal details are saved")
        return profile.model_copy(update={"me": None})
    if section in ("places", "preferences"):
        items: dict[str, Any] = getattr(profile, section)
        label = wanted.replace(" ", "_")
        if label not in items:
            raise KeyError(f"nothing saved as {key!r} in {section}")
        return profile.model_copy(update={section: {k: v for k, v in items.items() if k != label}})
    if section == "family":
        remaining: list[Any] = [person for person in profile.family if _key(person.name) != wanted]
    elif section == "vehicles":
        remaining = [v for v in profile.vehicles if _key(v.name) != wanted and _key(v.plate) != wanted]
    else:
        remaining = [note for note in profile.notes if wanted not in _key(note.text)]
    if len(remaining) == len(getattr(profile, section)):
        raise KeyError(f"nothing saved as {key!r} in {section}")
    return profile.model_copy(update={section: remaining})


def seed_from_settings(profile: Profile, settings: Any, today: date | None = None) -> Profile:
    """Fill the user's name and home/work/school from config.yaml when the profile lacks them."""
    today = today or date.today()
    if profile.me is None and getattr(settings, "first_name", None):
        profile = update_me(
            profile, name=f"{settings.first_name} {settings.last_name}".strip(), source="config.yaml", today=today
        )
    for label in ("home", "work", "school"):
        place = getattr(settings, label, None)
        if place is not None and label not in profile.places:
            profile = save_place(
                profile,
                label,
                place.address,
                company=getattr(place, "company", None),
                source="config.yaml",
                today=today,
            )
    return profile
