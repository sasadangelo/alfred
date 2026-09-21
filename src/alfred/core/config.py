"""Application configuration loaded from YAML with Pydantic Settings."""

import os
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource

DEFAULT_CONFIG_FILE = Path("config.yaml")
CONFIG_FILE = Path(os.environ.get("ALFRED_CONFIG_FILE", DEFAULT_CONFIG_FILE))


class NewsFeedConfig(BaseModel):
    """A single RSS feed source with a display title."""

    title: str
    url: str


class NewsConfig(BaseModel):
    """News section configuration listing one or more RSS feeds."""

    max_items_per_feed: int = 3
    feeds: list[NewsFeedConfig] = []


class PlaceConfig(BaseModel):
    """A named place and its postal address."""

    address: str


class WorkConfig(PlaceConfig):
    """Workplace details and commuting days."""

    company: str
    days: list[str]


class AlfredSettings(BaseSettings):
    """Validated Alfred personal and location settings."""

    model_config = SettingsConfigDict(yaml_file=CONFIG_FILE, env_prefix="ALFRED_", extra="forbid")

    first_name: str
    last_name: str
    home: PlaceConfig
    work: WorkConfig
    school: PlaceConfig | None = None
    news: NewsConfig = NewsConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Load settings from constructor values, environment variables, and YAML."""
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
        )


def get_settings() -> AlfredSettings:
    """Load and validate Alfred's configuration."""
    return AlfredSettings()  # type: ignore[call-arg]
