"""Tests for daily historical events."""

from datetime import date
from unittest.mock import Mock, patch

import requests

from alfred.almanac import get_almanac_data


@patch("alfred.almanac.random.choice")
@patch("alfred.almanac.requests.get")
def test_get_almanac_data(mock_get: Mock, mock_choice: Mock) -> None:
    """Select one event from a randomly selected category."""
    moon_event = {"year": 1969, "text": "L'uomo sbarca sulla Luna. La missione è Apollo 11."}
    events = [
        moon_event,
        {"year": 2001, "text": "Un importante museo italiano apre a Roma."},
        {"year": 2002, "text": "Internet raggiunge un nuovo traguardo."},
    ]
    mock_get.return_value.json.return_value = {"events": events}
    mock_choice.side_effect = ["science", moon_event]

    result = get_almanac_data(date(2026, 7, 20))

    assert result == "💡 *Curiosità del giorno*\n\n• Nel 1969 l'uomo sbarca sulla Luna."
    mock_choice.assert_any_call(["science", "culture", "technology"])
    mock_choice.assert_any_call([moon_event])
    mock_get.assert_called_once_with(
        "https://api.wikimedia.org/feed/v1/wikipedia/it/onthisday/events/07/20",
        headers={"User-Agent": "Alfred/0.1"},
        timeout=10,
    )
    mock_get.return_value.raise_for_status.assert_called_once_with()


@patch("alfred.almanac.random.choice")
@patch("alfred.almanac.requests.get")
def test_get_almanac_data_does_not_truncate_event(mock_get: Mock, mock_choice: Mock) -> None:
    """Preserve the complete first sentence of the selected event."""
    text = (
        "Battaglia del Frigido: l'imperatore romano Teodosio I sconfigge e uccide l'usurpatore Flavio Eugenio, "
        "il suo generale franco Arbogaste e tutte le forze avversarie"
    )
    event = {"year": 394, "text": text}
    mock_get.return_value.json.return_value = {"events": [event]}
    mock_choice.side_effect = ["italy", event]

    result = get_almanac_data(date(2026, 9, 6))

    assert result == f"💡 *Curiosità del giorno*\n\n• Nel 394 {text}."
    assert "…" not in result


@patch("alfred.almanac.random.choice")
@patch("alfred.almanac.requests.get")
def test_get_almanac_data_uses_random_available_category(mock_get: Mock, mock_choice: Mock) -> None:
    """Choose only among categories represented by the day's events."""
    history_event = {"year": 1945, "text": "La guerra termina."}
    general_event = {"year": 2000, "text": "Accade un evento particolare."}
    events = [history_event, general_event]
    mock_get.return_value.json.return_value = {"events": events}
    mock_choice.side_effect = ["general", general_event]

    result = get_almanac_data(date(2026, 7, 20))

    assert result == "💡 *Curiosità del giorno*\n\n• Nel 2000 Accade un evento particolare."
    mock_choice.assert_any_call(["history", "general"])
    mock_choice.assert_any_call([general_event])


@patch("alfred.almanac.requests.get")
def test_get_almanac_data_handles_empty_events(mock_get: Mock) -> None:
    """Return a readable message when no events are available."""
    mock_get.return_value.json.return_value = {"events": []}

    result = get_almanac_data(date(2026, 7, 20))

    assert result == "💡 *Curiosità del giorno*\n\nNessuna curiosità disponibile."


@patch("alfred.almanac.requests.get", side_effect=requests.RequestException("offline"))
def test_get_almanac_data_handles_request_failure(_: Mock) -> None:
    """Return a readable message when Wikipedia is unavailable."""
    result = get_almanac_data(date(2026, 7, 20))
    assert result == "💡 *Curiosità del giorno*\n\nImpossibile recuperare le curiosità: offline"
