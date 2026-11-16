"""The user's utilities and subscriptions, kept in ``subscriptions.yaml`` in the data directory.

Each entry records who provides it, where or for whom it applies, its codes (POD, PDR, customer
or contract numbers), how often it is billed, when it renews, how to recognize its emails and where
its documents go. Functions return updated copies; ``write_subscriptions`` saves them.
"""

import os
import secrets
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from alfred.paths import data_dir

SUBSCRIPTIONS_FILENAME = "subscriptions.yaml"
FREQUENCIES = ("mensile", "bimestrale", "trimestrale", "semestrale", "annuale", "una tantum")


class Subscription(BaseModel):
    """A utility (luce, gas, acqua, internet...) or a subscription (streaming, dominio, software...)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: f"s-{secrets.token_hex(3)}")
    kind: str
    provider: str
    place: str = ""
    identifiers: dict[str, str] = Field(default_factory=dict)
    details: str = ""
    frequency: str = ""
    amount_eur: float | None = None
    renewal: str = ""
    payment: str = ""
    email_match: str = ""
    documents_folder: str = ""
    filename_pattern: str = ""
    active: bool = True
    notes: str = ""

    @field_validator("kind", "provider")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("kind and provider must not be empty")
        return " ".join(value.split())

    @field_validator("frequency")
    @classmethod
    def _check_frequency(cls, value: str) -> str:
        value = value.strip().casefold()
        if value and value not in FREQUENCIES:
            raise ValueError(f"frequency must be one of {', '.join(FREQUENCIES)}")
        return value

    @field_validator("renewal")
    @classmethod
    def _check_renewal(cls, value: str) -> str:
        """Accept a yearly day (MM-DD) or a single date (YYYY-MM-DD)."""
        value = value.strip()
        if not value:
            return ""
        try:
            date.fromisoformat(f"2000-{value}" if len(value) == 5 else value)
        except ValueError as error:
            raise ValueError("renewal must be MM-DD (every year) or YYYY-MM-DD (once)") from error
        return value

    @field_validator("amount_eur")
    @classmethod
    def _not_negative(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("amount_eur must not be negative")
        return value


def subscriptions_file() -> Path:
    return data_dir() / SUBSCRIPTIONS_FILENAME


def _sorted(items: list[Subscription]) -> list[Subscription]:
    return sorted(items, key=lambda s: (not s.active, s.kind.casefold(), s.place.casefold(), s.provider.casefold()))


def load_subscriptions(path: Path | None = None) -> list[Subscription]:
    """Return the saved entries, active first, by kind, place and provider."""
    path = path or subscriptions_file()
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _sorted([Subscription.model_validate(item) for item in data.get("subscriptions") or []])


def write_subscriptions(items: list[Subscription], path: Path | None = None) -> Path:
    """Write the entries atomically with owner-only permissions."""
    path = path or subscriptions_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [{"id": item.id} | item.model_dump(exclude_defaults=True) for item in _sorted(items)]
    content = yaml.safe_dump({"subscriptions": records}, allow_unicode=True, sort_keys=False)
    file_descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".subscriptions-", suffix=".yaml")
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(content)
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return path


def _key(kind: str, provider: str, place: str) -> tuple[str, str, str]:
    return (" ".join(kind.split()).casefold(), " ".join(provider.split()).casefold(), place.strip().casefold())


def save_subscription(
    items: list[Subscription],
    *,
    subscription_id: str | None = None,
    identifiers: dict[str, str | None] | None = None,
    **fields: Any,
) -> tuple[list[Subscription], Subscription]:
    """Add an entry, or update the one with ``subscription_id``; ``None`` fields keep current values.

    ``identifiers`` are merged (an empty value removes one). Without ``subscription_id``, an entry
    with the same kind, provider and place is updated instead of being duplicated.
    """
    changes = {key: value for key, value in fields.items() if value is not None}
    updated = list(items)
    index = None
    if subscription_id:
        index = next((i for i, s in enumerate(updated) if s.id == subscription_id.strip()), None)
        if index is None:
            raise KeyError(f"no subscription with id {subscription_id!r}")
    elif "kind" in changes and "provider" in changes:
        wanted = _key(changes["kind"], changes["provider"], str(changes.get("place", "")))
        index = next((i for i, s in enumerate(updated) if _key(s.kind, s.provider, s.place) == wanted), None)
    current: dict[str, Any] = updated[index].model_dump() if index is not None else {}
    merged = dict(current.get("identifiers", {}))
    for key, value in (identifiers or {}).items():
        if value is None or not str(value).strip():
            merged.pop(key.strip(), None)
        else:
            merged[key.strip()] = str(value).strip()
    entry = Subscription.model_validate({**current, **changes, "identifiers": merged})
    if index is None:
        updated.append(entry)
    else:
        updated[index] = entry
    return _sorted(updated), entry


def forget_subscription(items: list[Subscription], subscription_id: str) -> list[Subscription]:
    """Remove an entry by id."""
    remaining = [item for item in items if item.id != subscription_id.strip()]
    if len(remaining) == len(items):
        raise KeyError(f"no subscription with id {subscription_id!r}")
    return remaining


def find_subscriptions(
    items: list[Subscription], *, kind: str | None = None, place: str | None = None, active_only: bool = True
) -> list[Subscription]:
    """Filter entries by kind and place (case-insensitive)."""
    return [
        item
        for item in items
        if (not active_only or item.active)
        and (kind is None or item.kind.casefold() == kind.strip().casefold())
        and (place is None or item.place.casefold() == place.strip().casefold())
    ]


def _next_renewal(renewal: str, today: date) -> date | None:
    if not renewal:
        return None
    if len(renewal) == 10:
        due = date.fromisoformat(renewal)
        return due if due >= today else None
    for year in (today.year, today.year + 1):
        try:
            due = date.fromisoformat(f"{year}-{renewal}")
        except ValueError:  # 02-29 in a non-leap year
            due = date(year, 3, 1)
        if due >= today:
            return due
    return None


def upcoming_renewals(items: list[Subscription], *, days: int = 60, today: date | None = None) -> list[dict[str, Any]]:
    """Active entries renewing or expiring within ``days``, soonest first."""
    today = today or date.today()
    upcoming = []
    for item in items:
        due = _next_renewal(item.renewal, today) if item.active else None
        if due is not None and (due - today).days <= days:
            upcoming.append(
                {
                    "id": item.id,
                    "kind": item.kind,
                    "provider": item.provider,
                    "place": item.place,
                    "date": due.isoformat(),
                    "in_days": (due - today).days,
                }
            )
    return sorted(upcoming, key=lambda entry: entry["in_days"])
