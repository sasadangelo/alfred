"""Daily historical events from Wikipedia."""

import random
from datetime import date

import requests

WIKIPEDIA_ON_THIS_DAY_URL = "https://api.wikimedia.org/feed/v1/wikipedia/it/onthisday/events/{month}/{day}"
CATEGORY_KEYWORDS = {
    "science": ("scoperta", "scienza", "spazio", "luna", "marte", "medicina", "fisica", "astronomia"),
    "technology": ("tecnologia", "computer", "internet", "software", "telefono", "satellite", "invenzione"),
    "culture": ("arte", "cinema", "libro", "musica", "teatro", "letteratura", "museo"),
    "italy": ("italia", "italiano", "italiana", "roma"),
    "history": ("guerra", "trattato", "indipendenza", "elezione", "rivoluzione", "impero"),
}


def _category(text: str) -> str:
    """Classify an event using a small set of general-interest categories."""
    normalized_text = text.casefold()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in normalized_text for keyword in keywords):
            return category
    return "general"


def _short_event(year: int, text: str) -> str:
    """Format an event as one short sentence."""
    sentence = text.split(". ", maxsplit=1)[0].strip().rstrip(".")
    for article in ("Il ", "Lo ", "La ", "L'", "I ", "Gli ", "Le ", "Un ", "Una "):
        if sentence.startswith(article):
            sentence = sentence[0].lower() + sentence[1:]
            break
    return f"Nel {year} {sentence}."


def _select_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    """Select one random event from a random available category."""
    if not events:
        return []

    events_by_category: dict[str, list[dict[str, object]]] = {}
    for event in events:
        category = _category(str(event.get("text", "")))
        events_by_category.setdefault(category, []).append(event)

    category = random.choice(list(events_by_category))
    return [random.choice(events_by_category[category])]


def get_almanac_data(today: date | None = None) -> str:
    """Return short, varied historical curiosities for the current date."""
    current_date = today or date.today()
    url = WIKIPEDIA_ON_THIS_DAY_URL.format(month=current_date.strftime("%m"), day=current_date.strftime("%d"))

    try:
        response = requests.get(url, headers={"User-Agent": "Alfred/0.1"}, timeout=10)
        response.raise_for_status()
        events = _select_events(response.json().get("events", []))
        if not events:
            return "💡 *Curiosità del giorno*\n\nNessuna curiosità disponibile."

        event_lines = [f"• {_short_event(int(str(event['year'])), str(event['text']))}" for event in events]
        return "💡 *Curiosità del giorno*\n\n" + "\n".join(event_lines)
    except (requests.RequestException, KeyError, TypeError, ValueError) as error:
        return f"💡 *Curiosità del giorno*\n\nImpossibile recuperare le curiosità: {error}"
