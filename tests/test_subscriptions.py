"""Tests for utilities and subscriptions."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from alfred import paths
from alfred import subscriptions as subs


def test_save_adds_then_updates_the_same_entry() -> None:
    items, first = subs.save_subscription(
        [], kind="luce", provider="Energia Esempio", place="home", identifiers={"POD": "IT000E0000001"}
    )
    items, second = subs.save_subscription(
        items, kind="Luce", provider="energia  esempio", place="Home", amount_eur=80.5, identifiers={"cliente": "42"}
    )

    assert len(items) == 1
    assert second.id == first.id
    assert second.amount_eur == 80.5
    assert second.identifiers == {"POD": "IT000E0000001", "cliente": "42"}


def test_same_provider_in_another_place_is_a_new_entry() -> None:
    items, _ = subs.save_subscription([], kind="luce", provider="Energia Esempio", place="home")
    items, _ = subs.save_subscription(items, kind="luce", provider="Energia Esempio", place="seconda casa")

    assert [s.place for s in items] == ["home", "seconda casa"]


def test_update_by_id_can_change_any_field_and_remove_identifiers() -> None:
    items, entry = subs.save_subscription([], kind="gas", provider="Gas Esempio", identifiers={"PDR": "123"})
    items, entry = subs.save_subscription(
        items, subscription_id=entry.id, provider="Altro Gas", active=False, identifiers={"PDR": ""}
    )

    assert (entry.provider, entry.active, entry.identifiers) == ("Altro Gas", False, {})
    with pytest.raises(KeyError):
        subs.save_subscription(items, subscription_id="s-missing", notes="x")


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": " ", "provider": "X"},
        {"kind": "luce", "provider": "X", "frequency": "ogni tanto"},
        {"kind": "luce", "provider": "X", "renewal": "31/12"},
        {"kind": "luce", "provider": "X", "renewal": "02-30"},
        {"kind": "luce", "provider": "X", "amount_eur": -1},
    ],
)
def test_invalid_fields_are_rejected(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        subs.Subscription.model_validate(fields)


def test_upcoming_renewals_handles_yearly_and_one_off_dates() -> None:
    items, _ = subs.save_subscription([], kind="dominio", provider="Registrar", renewal="01-01")
    items, _ = subs.save_subscription(items, kind="streaming", provider="Video", renewal="2026-11-30")
    items, _ = subs.save_subscription(items, kind="software", provider="Scaduto", renewal="2026-01-01")
    items, _ = subs.save_subscription(items, kind="rivista", provider="Lontano", renewal="06-01")
    items, _ = subs.save_subscription(items, kind="palestra", provider="Chiusa", renewal="12-01", active=False)

    upcoming = subs.upcoming_renewals(items, days=60, today=date(2026, 11, 16))

    assert [(u["provider"], u["date"], u["in_days"]) for u in upcoming] == [
        ("Video", "2026-11-30", 14),
        ("Registrar", "2027-01-01", 46),
    ]


def test_find_filters_by_kind_place_and_activity() -> None:
    items, _ = subs.save_subscription([], kind="luce", provider="A", place="home")
    items, _ = subs.save_subscription(items, kind="luce", provider="B", place="ufficio", active=False)
    items, _ = subs.save_subscription(items, kind="internet", provider="C", place="home")

    assert [s.provider for s in subs.find_subscriptions(items, kind="LUCE")] == ["A"]
    assert [s.provider for s in subs.find_subscriptions(items, kind="luce", active_only=False)] == ["A", "B"]
    assert [s.provider for s in subs.find_subscriptions(items, place="home")] == ["C", "A"]


def test_write_and_load_round_trip_with_private_permissions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))
    items, entry = subs.save_subscription(
        [], kind="luce", provider="Energia Esempio", frequency="Bimestrale", documents_folder="~/Bollette/Luce"
    )

    path = subs.write_subscriptions(items)

    assert path == tmp_path / "subscriptions.yaml"
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert subs.load_subscriptions() == [entry]
    assert "active" not in path.read_text(encoding="utf-8")
    items = subs.forget_subscription(items, entry.id)
    assert items == []
    with pytest.raises(KeyError):
        subs.forget_subscription(items, entry.id)


def test_load_without_file_is_empty(tmp_path: Path) -> None:
    assert subs.load_subscriptions(tmp_path / "none.yaml") == []
