"""Alfred weather report entry point."""

import os

from alfred.almanac import get_almanac_data
from alfred.core.config import AlfredSettings, get_settings
from alfred.news import get_news_data
from alfred.traffic import get_traffic_data
from alfred.weather import get_weather_data
from alfred.whatsapp import send_whatsapp_message

WHATSAPP_RECIPIENT_ENV = "ALFRED_WHATSAPP_RECIPIENT"
TOMTOM_API_KEY_ENV = "ALFRED_TOMTOM_API_KEY"  # pragma: allowlist secret


def main() -> None:
    """Build and send the daily morning report through WhatsApp."""
    recipient: str | None = os.environ.get(WHATSAPP_RECIPIENT_ENV)
    if not recipient:
        raise RuntimeError(f"Environment variable {WHATSAPP_RECIPIENT_ENV} is required")

    settings: AlfredSettings = get_settings()
    weather: str = get_weather_data(latitude=41.9028, longitude=12.4964)
    sections: list[str] = [weather]
    api_key: str | None = os.environ.get(TOMTOM_API_KEY_ENV)
    if api_key:
        traffic: str | None = get_traffic_data(settings=settings, api_key=api_key)
        if traffic:
            sections.append(traffic)

    sections.append(get_almanac_data())

    if settings.news.feeds:
        news_feeds = {f.title: f.url for f in settings.news.feeds}
        news: str = get_news_data(feeds=news_feeds, max_items_per_feed=settings.news.max_items_per_feed)
        if news:
            sections.append(news)

    report: str = "\n\n".join(sections)
    message: str = f"Ciao sono Alfred, il tuo assistente virtuale.Ecco il bollettino di oggi:\n\n{report}"
    send_whatsapp_message(recipient=recipient, message=message)
    print("Meteo inviato con successo")


if __name__ == "__main__":
    main()
