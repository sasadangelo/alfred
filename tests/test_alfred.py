"""Tests for the Alfred entry point."""

from unittest.mock import Mock, patch

import pytest

from alfred.alfred import TOMTOM_API_KEY_ENV, WHATSAPP_RECIPIENT_ENV, main


def test_main_requires_whatsapp_recipient(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject execution when the WhatsApp recipient is not configured."""
    monkeypatch.delenv(WHATSAPP_RECIPIENT_ENV, raising=False)

    with pytest.raises(RuntimeError, match=WHATSAPP_RECIPIENT_ENV):
        main()


@patch("alfred.alfred.get_news_data", return_value="📰 *Ultime Notizie*\n\n*BBC News*\n• News title")
@patch("alfred.alfred.get_almanac_data", return_value="Almanacco")
@patch("alfred.alfred.get_settings")
@patch("alfred.alfred.send_whatsapp_message")
@patch("alfred.alfred.get_weather_data", return_value="Meteo")
def test_main_sends_weather_report_with_news(
    mock_weather: Mock,
    mock_send: Mock,
    mock_settings: Mock,
    mock_almanac: Mock,
    mock_news: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Send the daily morning report including news to the recipient."""
    feed_mock = Mock(title="BBC News", url="https://feeds.bbci.co.uk/news/rss.xml")
    mock_settings.return_value.news.feeds = [feed_mock]
    mock_settings.return_value.news.max_items_per_feed = 3
    monkeypatch.setenv(WHATSAPP_RECIPIENT_ENV, "391234567890")
    monkeypatch.delenv(TOMTOM_API_KEY_ENV, raising=False)

    main()

    mock_weather.assert_called_once_with(latitude=41.9028, longitude=12.4964)
    mock_almanac.assert_called_once_with()
    mock_news.assert_called_once_with(
        feeds={"BBC News": "https://feeds.bbci.co.uk/news/rss.xml"},
        max_items_per_feed=3,
    )
    mock_send.assert_called_once_with(
        recipient="391234567890",
        message=(
            "Ciao sono Alfred, il tuo assistente virtuale.Ecco il bollettino di oggi:\n\n"
            "Meteo\n\n"
            "Almanacco\n\n"
            "📰 *Ultime Notizie*\n\n*BBC News*\n• News title"
        ),
    )


@patch("alfred.alfred.get_almanac_data", return_value="Almanacco")
@patch("alfred.alfred.get_settings")
@patch("alfred.alfred.send_whatsapp_message")
@patch("alfred.alfred.get_weather_data", return_value="Meteo")
def test_main_sends_weather_report(
    mock_weather: Mock, mock_send: Mock, mock_settings: Mock, mock_almanac: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Send the weather report to the recipient from the environment without news."""
    mock_settings.return_value.news.feeds = []
    monkeypatch.setenv(WHATSAPP_RECIPIENT_ENV, "391234567890")
    monkeypatch.delenv(TOMTOM_API_KEY_ENV, raising=False)

    main()

    mock_weather.assert_called_once_with(latitude=41.9028, longitude=12.4964)
    mock_almanac.assert_called_once_with()
    mock_send.assert_called_once_with(
        recipient="391234567890",
        message="Ciao sono Alfred, il tuo assistente virtuale.Ecco il bollettino di oggi:\n\nMeteo\n\nAlmanacco",
    )
