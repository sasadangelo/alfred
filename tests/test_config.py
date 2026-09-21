"""Tests for Alfred application settings."""

from alfred.core.config import AlfredSettings, PlaceConfig, WorkConfig


def test_settings_accept_personal_locations_and_work_days() -> None:
    """Validate personal, home, workplace, and commuting-day settings."""
    settings = AlfredSettings(
        first_name="Mario",
        last_name="Rossi",
        home=PlaceConfig(address="Via Roma 1, 00100 Roma"),
        work=WorkConfig(
            company="Example S.p.A.",
            address="Via Milano 10, 00100 Roma",
            days=["monday", "wednesday", "thursday"],
        ),
        school=None,
    )

    assert settings.first_name == "Mario"
    assert settings.work.company == "Example S.p.A."
    assert settings.work.days == ["monday", "wednesday", "thursday"]
