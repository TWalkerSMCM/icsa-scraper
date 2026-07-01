"""
Parse a season index page, e.g. https://scores.collegesailing.org/s25/

Extracts a list of regatta stubs: nick, name, date string, and URL path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from scraper.parsers._soup import ensure_soup


@dataclass
class RegattaStub:
    nick: str  # URL slug, e.g. "spring-championship"
    name: str  # Display name
    season: str  # Season URL key, e.g. "s25"
    path: str  # Full path, e.g. "/s25/spring-championship/"
    date_str: str  # Raw date text from page, e.g. "March 1–2"
    status: str  # e.g. "final", "scheduled", etc. (from class or text)


def parse(html: str | BeautifulSoup, season: str) -> list[RegattaStub]:
    """
    Parse the season index page HTML.

    The season page has a table or list of regattas. Each regatta is
    linked via an <a> whose href is /{season}/{nick}/.

    Args:
        html: raw HTML of the season index page.
        season: the season URL key (e.g. "s25").

    Returns:
        List of RegattaStub objects.
    """
    soup = ensure_soup(html)
    regattas: list[RegattaStub] = []

    # Links are relative slugs, e.g. href="some-regatta" (no leading slash).
    # Exclude anchors, external URLs, and navigation links.
    slug_pattern = re.compile(r"^[a-z0-9][a-z0-9\-]+$")

    seen = set()
    for a in soup.find_all("a", href=slug_pattern):
        nick = a["href"]
        if nick in seen:
            continue
        seen.add(nick)

        name = a.get_text(strip=True)
        if not name:
            continue

        path = f"/{season}/{nick}/"
        date_str = _find_nearby_date(a)

        regattas.append(
            RegattaStub(
                nick=nick,
                name=name,
                season=season,
                path=path,
                date_str=date_str,
                status="",
            )
        )

    return regattas


def _find_nearby_date(tag: Tag) -> str:
    """Walk up to a table row or list item and look for date text."""
    parent = tag.parent
    # Walk up at most a few levels — the date lives in the same tr/li/div as
    # the regatta link, never deeper than the surrounding row container.
    for _ in range(5):
        if parent is None:
            break
        if parent.name in ("tr", "li", "div"):
            # Look for a <td> or <time> with date-like content
            for child in parent.find_all(["td", "time", "span"]):
                text = child.get_text(strip=True)
                # Simple heuristic: contains a month name or date digits
                if re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", text):
                    return text
                if re.search(r"\d{4}-\d{2}-\d{2}", text):
                    return text
            break
        parent = parent.parent
    return ""
