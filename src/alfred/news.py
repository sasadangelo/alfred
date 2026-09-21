"""News feed fetching and formatting using asyncio and aiohttp."""

import asyncio
import re

import aiohttp
import feedparser
from aiohttp.client import ClientTimeout
from feedparser.util import FeedParserDict

from alfred.core.config import get_settings

TIMEOUT: ClientTimeout = aiohttp.ClientTimeout(total=10)

DEFAULT_FEEDS: dict[str, str] = {
    # Internazionale
    "BBC News": "https://feeds.bbci.co.uk/news/world/rss.xml",
    # Nazionale
    "Repubblica": "https://www.repubblica.it/rss/homepage/rss2.0.xml",
    # Tecnologia
    "Wired": "https://www.wired.com/feed/rss",
    # Sport
    "Sky Sport": "https://sport.sky.it/rss/sport.xml",
    # Scienza
    "Science Daily": "https://www.sciencedaily.com/rss/top/science.xml",
}

HEADERS: dict[str, str] = {"User-Agent": "Mozilla/5.0 (compatible; AlfredBot/1.0)"}

MAX_SUMMARY = 150


def _strip_html(text: str) -> str:
    """Remove HTML tags, collapse whitespace, and truncate to MAX_SUMMARY chars."""
    clean = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()
    return clean[:MAX_SUMMARY] + "…" if len(clean) > MAX_SUMMARY else clean


async def fetch(session: aiohttp.ClientSession, url: str, limit: int = 3) -> list[dict[str, str]]:
    """Fetch a single RSS feed URL and extract up to limit items."""
    async with session.get(url) as resp:
        resp.raise_for_status()
        text: str = await resp.text()
    feed: FeedParserDict = feedparser.parse(url_file_stream_or_string=text)
    return [
        {
            "title": str(e.get(key="title", default="")).strip(),
            "link": str(e.get(key="link", default="")),
            "summary": _strip_html(str(e.get(key="summary", default=""))),
        }
        for e in feed.entries[:limit]
    ]


async def fetch_safe(
    session: aiohttp.ClientSession,
    source: str,
    url: str,
    semaphore: asyncio.Semaphore,
    timeout: float = 8.0,
    limit: int = 3,
) -> tuple[str, list[dict[str, str]], Exception | None]:
    """Fetch a single RSS feed safely with semaphore and timeout."""
    async with semaphore:
        try:
            async with asyncio.timeout(delay=timeout):
                items: list[dict[str, str]] = await fetch(session, url, limit=limit)
            return source, items, None
        except TimeoutError as exc:
            return source, [], exc
        except Exception as exc:
            return source, [], exc


async def _fetch_all(
    feeds: dict[str, str], limit: int = 3
) -> tuple[dict[str, list[dict[str, str]]], dict[str, Exception]]:
    """Fetch all RSS feeds concurrently using TaskGroup, Semaphore, and per-request timeouts."""
    semaphore = asyncio.Semaphore(value=3)
    results: dict[str, list[dict[str, str]]] = {}
    failed_sources: dict[str, Exception] = {}

    async with (
        aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as session,
        asyncio.TaskGroup() as tg,
    ):
        tasks = {
            source: tg.create_task(fetch_safe(session, source, url, semaphore, limit=limit))
            for source, url in feeds.items()
        }

    for source, task in tasks.items():
        _, items, error = task.result()
        if error is not None:
            failed_sources[source] = error
        else:
            results[source] = items

    return results, failed_sources


def format_news(results: dict[str, list[dict[str, str]]]) -> str:
    """Format news items as text blocks suitable for WhatsApp messaging."""
    blocks: list[str] = []
    for source, items in results.items():
        if not items:
            continue
        lines: list[str] = [f"*{source}*"]
        for item in items:
            lines.append(f"• {item['title']}")
            if item.get("summary"):
                lines.append(f"  {item['summary']}")
        blocks.append("\n".join(lines))
    if not blocks:
        return ""
    return "📰 *Ultime Notizie*\n\n" + "\n\n".join(blocks)


def get_news_data(feeds: dict[str, str] | None = None, max_items_per_feed: int | None = None) -> str:
    """Return a formatted news report string for all configured feeds."""
    settings = get_settings()
    if feeds is None:
        feeds = {feed.title: feed.url for feed in settings.news.feeds} if settings.news.feeds else DEFAULT_FEEDS
    limit = max_items_per_feed if max_items_per_feed is not None else settings.news.max_items_per_feed
    results, _ = asyncio.run(_fetch_all(feeds, limit=limit))
    return format_news(results)


async def main() -> None:
    """Entry point for testing news aggregator."""
    settings = get_settings()
    feeds: dict[str, str] = (
        {feed.title: feed.url for feed in settings.news.feeds} if settings.news.feeds else DEFAULT_FEEDS
    )

    results, failed_sources = await _fetch_all(feeds, limit=settings.news.max_items_per_feed)

    for source, items in results.items():
        print(f"*{source}*")
        for item in items:
            print(f"  Titolo : {item['title']}")
            print(f"  URL    : {item['link']}")
            print(f"  Summary: {item['summary']}")
            print()

    if failed_sources:
        print("--- Feed non riusciti ---")
        for source, error in failed_sources.items():
            print(f"{source}: error — {error}")


if __name__ == "__main__":
    asyncio.run(main=main())
