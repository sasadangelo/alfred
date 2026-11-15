"""Tests for Alfred's data directory and runtime settings."""

from pathlib import Path

import pytest

from alfred import paths


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (paths.DATA_DIR_ENV, paths.PLUGIN_DATA_ENV, paths.TIMEZONE_ENV):
        monkeypatch.delenv(name, raising=False)


def test_data_dir_prefers_explicit_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.PLUGIN_DATA_ENV, str(tmp_path / "plugin"))
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "override"))

    assert paths.data_dir() == tmp_path / "override"


def test_data_dir_uses_plugin_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.PLUGIN_DATA_ENV, str(tmp_path / "plugin"))

    assert paths.data_dir() == tmp_path / "plugin"


def test_data_dir_defaults_outside_the_plugin() -> None:
    assert paths.data_dir() == paths.DEFAULT_DATA_DIR


def test_timezone_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    assert paths.timezone() == "Europe/Rome"
    monkeypatch.setenv(paths.TIMEZONE_ENV, "America/New_York")
    assert paths.timezone() == "America/New_York"


@pytest.mark.parametrize("value", ["${user_config.timezone}", "   "])
def test_timezone_ignores_placeholders_and_blanks(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.TIMEZONE_ENV, value)

    assert paths.timezone() == "Europe/Rome"


def test_unknown_timezone_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.TIMEZONE_ENV, "Mars/Olympus")

    with pytest.raises(ValueError, match="unknown timezone"):
        paths.timezone()
