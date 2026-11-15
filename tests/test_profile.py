"""Tests for Alfred's user profile store."""

import stat
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from alfred import paths
from alfred import profile as store

TODAY = date(2026, 11, 12)


@pytest.fixture
def profile_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "config" / "profile.yaml"
    monkeypatch.setenv(store.PROFILE_FILE_ENV, str(path))
    return path


def test_load_returns_empty_profile_when_file_is_missing(profile_path: Path) -> None:
    assert store.load_profile() == store.Profile()


def test_save_and_load_round_trip_with_owner_only_permissions(profile_path: Path) -> None:
    profile = store.update_me(
        store.Profile(), first_name="Mario", last_name="Rossi", birth_date=date(1980, 3, 5), today=TODAY
    )
    profile = store.save_vehicle(profile, "Peugeot 2008", fuel="benzina", today=TODAY)

    saved_path = store.save_profile(profile)

    assert saved_path == profile_path
    assert stat.S_IMODE(profile_path.stat().st_mode) == 0o600
    assert store.load_profile() == profile
    assert list(profile_path.parent.glob(".profile-*")) == []


def test_profile_file_defaults_to_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(store.PROFILE_FILE_ENV, raising=False)
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path))

    assert store.profile_file() == tmp_path / "profile.yaml"


@pytest.mark.parametrize(
    ("birth", "today", "expected"),
    [
        (date(1980, 3, 5), date(2026, 11, 12), 46),
        (date(1980, 3, 5), date(2027, 3, 4), 46),
        (date(1980, 3, 5), date(2027, 3, 5), 47),
    ],
)
def test_age_on(birth: date, today: date, expected: int) -> None:
    assert store.age_on(birth, today) == expected


def test_family_member_is_updated_by_name_keeping_other_fields() -> None:
    profile = store.save_family_member(store.Profile(), "Giulia", relation="moglie", today=TODAY)

    profile = store.save_family_member(profile, " giulia ", birth_date=date(1981, 7, 4), today=TODAY)

    assert len(profile.family) == 1
    assert profile.family[0].relation == "moglie"
    assert profile.family[0].birth_date == date(1981, 7, 4)


def test_birth_date_in_the_future_is_rejected() -> None:
    with pytest.raises(ValidationError, match="future"):
        store.save_family_member(store.Profile(), "Futuro", birth_date=date(2999, 1, 1))


def test_vehicles_are_matched_by_plate_then_name() -> None:
    profile = store.save_vehicle(store.Profile(), "Clio", fuel="benzina", today=TODAY)
    profile = store.save_vehicle(profile, "Clio", plate=" ab123cd ", today=TODAY)
    profile = store.save_vehicle(profile, "Clio", plate="ZZ999ZZ", fuel="gasolio", today=TODAY)

    assert [(v.name, v.plate, v.fuel) for v in profile.vehicles] == [
        ("Clio", "AB123CD", "benzina"),
        ("Clio", "ZZ999ZZ", "gasolio"),
    ]


def test_invalid_fuel_is_rejected() -> None:
    with pytest.raises(ValidationError):
        store.save_vehicle(store.Profile(), "Auto", fuel="carbone")  # type: ignore[arg-type]


def test_places_and_preferences_use_normalized_keys() -> None:
    profile = store.save_place(store.Profile(), "Work", "Via Roma 1", company="ACME", today=TODAY)
    profile = store.save_place(profile, "work", "Via Milano 2", today=TODAY)
    profile = store.set_preference(profile, "Preferred Fuel Brand", "Q8")

    assert profile.places["work"].address == "Via Milano 2"
    assert profile.places["work"].company == "ACME"
    assert profile.preferences == {"preferred_fuel_brand": "Q8"}


def test_notes_ignore_duplicates() -> None:
    profile = store.add_note(store.Profile(), "Preferisco il self service", today=TODAY)
    profile = store.add_note(profile, "preferisco il  self service", today=TODAY)

    assert len(profile.notes) == 1


def test_missing_essentials_follow_answers_and_skips() -> None:
    profile = store.Profile()
    assert [item["key"] for item in store.missing_essentials(profile)] == list(store.ESSENTIALS)

    profile = store.update_me(profile, first_name="Mario", birth_date=date(1980, 3, 5), today=TODAY)
    profile = store.save_place(profile, "home", "Via Roma 1", today=TODAY)
    profile = store.set_preference(profile, "commute", "mezzi pubblici")
    profile = store.skip_essential(profile, "family")

    # Commuting without a car makes the vehicle question unnecessary.
    assert [item["key"] for item in store.missing_essentials(profile)] == ["work"]


def test_vehicle_question_stays_when_commuting_by_car() -> None:
    profile = store.set_preference(store.Profile(), "commute", "in auto")

    assert "vehicles" in [item["key"] for item in store.missing_essentials(profile)]


def test_skip_essential_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="unknown onboarding question"):
        store.skip_essential(store.Profile(), "shoe_size")


def test_describe_profile_reports_ages_and_upcoming_birthdays() -> None:
    profile = store.update_me(store.Profile(), first_name="Mario", birth_date=date(1980, 3, 5), today=TODAY)
    profile = store.save_family_member(profile, "Luca", relation="figlio", birth_date=date(2013, 12, 1), today=TODAY)
    profile = store.save_family_member(profile, "Anna", relation="figlia", birth_date=date(2012, 4, 20), today=TODAY)

    description = store.describe_profile(profile, today=TODAY)

    assert [(item["name"], item["age"]) for item in description["ages"]] == [("Mario", 46), ("Luca", 12), ("Anna", 14)]
    assert [{k: v for k, v in item.items() if k != "id"} for item in description["upcoming_birthdays"]] == [
        {"name": "Luca", "birth_date": "2013-12-01", "date": "2026-12-01", "in_days": 19, "turns": 13}
    ]


def test_upcoming_birthday_handles_29_february() -> None:
    profile = store.save_family_member(store.Profile(), "Leap", birth_date=date(2000, 2, 29), today=TODAY)

    description = store.describe_profile(profile, today=date(2027, 2, 20))

    assert description["upcoming_birthdays"][0]["date"] == "2027-03-01"


@pytest.mark.parametrize(
    ("section", "key"),
    [
        ("family", "luca"),
        ("vehicles", "PEUGEOT 2008"),
        ("places", "Home"),
        ("preferences", "commute"),
        ("notes", "self"),
    ],
)
def test_forget_removes_one_item(section: store.Section, key: str) -> None:
    profile = store.save_family_member(store.Profile(), "Luca", today=TODAY)
    profile = store.save_vehicle(profile, "Peugeot 2008", today=TODAY)
    profile = store.save_place(profile, "home", "Via Roma 1", today=TODAY)
    profile = store.set_preference(profile, "commute", "auto")
    profile = store.add_note(profile, "Preferisco il self service", today=TODAY)

    updated = store.forget(profile, section, key)

    assert len(getattr(updated, section)) == len(getattr(profile, section)) - 1


def test_forget_unknown_item_raises() -> None:
    with pytest.raises(KeyError, match="nothing saved"):
        store.forget(store.Profile(), "family", "Nessuno")


def test_deceased_relatives_have_no_age_but_keep_anniversaries() -> None:
    profile = store.save_family_member(
        store.Profile(), "Nonno", relation="padre", birth_date=date(1931, 12, 1), deceased=True, today=TODAY
    )
    profile = store.save_family_member(profile, "Zia", relation="zia", birth_date=date(1950, 1, 1), today=TODAY)

    description = store.describe_profile(profile, today=TODAY)

    assert [(item["name"], item["age"]) for item in description["ages"]] == [("Zia", 76)]
    assert [{k: v for k, v in item.items() if k != "id"} for item in description["upcoming_birthdays"]] == [
        {"name": "Nonno", "birth_date": "1931-12-01", "date": "2026-12-01", "in_days": 19, "deceased": True}
    ]


def test_deceased_flag_is_kept_on_later_updates() -> None:
    profile = store.save_family_member(store.Profile(), "Nonna", deceased=True, today=TODAY)

    profile = store.save_family_member(profile, "Nonna", relation="suocera", today=TODAY)

    assert profile.family[0].deceased is True
    assert profile.family[0].relation == "suocera"


def test_namesakes_with_different_birth_dates_are_different_people() -> None:
    profile = store.save_family_member(
        store.Profile(), "Luca", "Bianchi", relation="suocero", birth_date=date(1950, 6, 1), today=TODAY
    )
    profile = store.save_family_member(
        profile, "Luca", "Bianchi", relation="nipote", birth_date=date(2010, 9, 15), today=TODAY
    )
    profile = store.save_family_member(profile, "luca", "bianchi", birth_date=date(1950, 6, 1), deceased=True)

    assert [(p.relation, p.birth_date, p.deceased) for p in profile.family] == [
        ("suocero", date(1950, 6, 1), True),
        ("nipote", date(2010, 9, 15), False),
    ]


def test_ambiguous_name_without_birth_date_is_rejected() -> None:
    profile = store.save_family_member(store.Profile(), "Luca", "Bianchi", birth_date=date(1950, 6, 1))
    profile = store.save_family_member(profile, "Luca", "Bianchi", birth_date=date(2010, 9, 15))

    with pytest.raises(store.AmbiguousPersonError, match="pass birth_date"):
        store.save_family_member(profile, "Luca", "Bianchi", relation="nipote")


def test_birth_date_fills_the_single_undated_namesake() -> None:
    profile = store.save_family_member(store.Profile(), "Paola", "Verdi", relation="suocera", today=TODAY)

    profile = store.save_family_member(profile, "Paola", "Verdi", birth_date=date(1945, 5, 1), today=TODAY)

    assert len(profile.family) == 1
    assert profile.family[0].birth_date == date(1945, 5, 1)
    assert profile.family[0].relation == "suocera"


def test_forget_namesake_requires_birth_date() -> None:
    profile = store.save_family_member(store.Profile(), "Luca", "Bianchi", birth_date=date(1950, 6, 1))
    profile = store.save_family_member(profile, "Luca", "Bianchi", birth_date=date(2010, 9, 15))

    with pytest.raises(store.AmbiguousPersonError):
        store.forget(profile, "family", "Luca Bianchi")
    updated = store.forget(profile, "family", "Luca Bianchi", birth_date=date(2010, 9, 15))

    assert [p.birth_date for p in updated.family] == [date(1950, 6, 1)]


def test_forget_by_nickname() -> None:
    profile = store.save_family_member(store.Profile(), "Elisabetta", nickname="Betty", today=TODAY)

    assert store.forget(profile, "family", "betty").family == []


def test_legacy_single_name_field_is_split_on_load(profile_path: Path) -> None:
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(
        "me:\n  name: Mario Rossi\nfamily:\n- name: Marco Rossi\n  relation: padre\n", encoding="utf-8"
    )

    profile = store.load_profile()

    assert profile.me is not None
    assert (profile.me.first_name, profile.me.last_name) == ("Mario", "Rossi")
    assert (profile.family[0].first_name, profile.family[0].last_name) == ("Marco", "Rossi")


def test_people_and_vehicles_get_stable_unique_ids(profile_path: Path) -> None:
    profile = store.save_family_member(store.Profile(), "Marco", "Rossi", birth_date=date(1945, 2, 3))
    profile = store.save_family_member(profile, "Marco", "Rossi", birth_date=date(2012, 4, 20))
    profile = store.save_vehicle(profile, "Peugeot 2008")
    ids = [p.id for p in profile.family] + [v.id for v in profile.vehicles]

    store.save_profile(profile)
    reloaded = store.load_profile()

    assert len(set(ids)) == 3
    assert all(item_id.startswith(("p-", "v-")) for item_id in ids)
    assert [p.id for p in reloaded.family] + [v.id for v in reloaded.vehicles] == ids


def test_duplicate_ids_are_replaced_on_load() -> None:
    profile = store.Profile.model_validate(
        {"family": [{"id": "p-1", "first_name": "A"}, {"id": "p-1", "first_name": "B"}]}
    )

    assert profile.family[0].id == "p-1"
    assert profile.family[1].id != "p-1"


def test_save_family_member_by_id_can_change_identity_fields() -> None:
    profile = store.save_family_member(store.Profile(), "Marco", relation="figlio", birth_date=date(2012, 4, 20))
    person_id = profile.family[0].id

    profile = store.save_family_member(
        profile, last_name="Rossi", person_id=person_id, birth_date=date(2012, 4, 21), today=TODAY
    )

    person = profile.family[0]
    assert len(profile.family) == 1
    assert (person.id, person.full_name, person.birth_date, person.relation) == (
        person_id,
        "Marco Rossi",
        date(2012, 4, 21),
        "figlio",
    )


def test_save_family_member_with_unknown_id_raises() -> None:
    with pytest.raises(KeyError, match="no family member with id"):
        store.save_family_member(store.Profile(), person_id="p-missing", relation="figlio")


def test_save_family_member_by_id_rejects_empty_first_name() -> None:
    profile = store.save_family_member(store.Profile(), "Anna")

    with pytest.raises(ValueError, match="first_name must not be empty"):
        store.save_family_member(profile, first_name="  ", person_id=profile.family[0].id)


def test_save_vehicle_by_id_can_rename() -> None:
    profile = store.save_vehicle(store.Profile(), "Peugot 2008", fuel="benzina", today=TODAY)
    vehicle_id = profile.vehicles[0].id

    profile = store.save_vehicle(profile, "Peugeot 2008", vehicle_id=vehicle_id, today=TODAY)

    assert [(v.id, v.name, v.fuel) for v in profile.vehicles] == [(vehicle_id, "Peugeot 2008", "benzina")]


def test_forget_by_id() -> None:
    profile = store.save_family_member(store.Profile(), "Luca", "Bianchi", birth_date=date(1950, 6, 1))
    profile = store.save_family_member(profile, "Luca", "Bianchi", birth_date=date(2010, 9, 15))

    updated = store.forget(profile, "family", profile.family[1].id)

    assert [p.birth_date for p in updated.family] == [date(1950, 6, 1)]


def test_describe_profile_exposes_ids() -> None:
    profile = store.save_family_member(store.Profile(), "Luca", birth_date=date(2013, 12, 1), today=TODAY)

    description = store.describe_profile(profile, today=TODAY)

    assert description["profile"]["family"][0]["id"] == profile.family[0].id
    assert description["ages"][0]["id"] == profile.family[0].id
    assert description["upcoming_birthdays"][0]["id"] == profile.family[0].id
