"""
Parse the scores.collegesailing.org front page for active and upcoming regattas.

These parsers are used only by the Lambda poller — the batch scraper (analytics/)
uses a different entry point. Extracted from the legacy parser.py.
"""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from scraper.models import RegattaListEntry
from scraper.parsers._soup import ensure_soup

BASE_URL = "https://scores.collegesailing.org"


def parse_active_regattas(html: str | BeautifulSoup) -> list[RegattaListEntry]:
    """
    Parse the front page (/) and return regattas currently in progress.

    The front page uses a div#in-progress section containing a table.season-summary.
    Each row has an anchor link like /s26/regatta-slug/ in the first column.

    Returns an empty list when no regattas are active.
    """
    soup = ensure_soup(html)
    results: list[RegattaListEntry] = []

    div = soup.find("div", id="in-progress")
    if not div:
        return results

    for a in div.select("table.season-summary tbody tr td:first-child a[href]"):
        href = a["href"]
        m = re.match(r'^/([a-z]\d{2})/([^/]+)/?$', href)
        if not m:
            continue
        season, slug = m.group(1), m.group(2)
        results.append(RegattaListEntry(
            name=a.get_text(strip=True),
            url=BASE_URL + href,
            slug=slug,
            season=season,
            status="in_progress",
        ))

    return results


def parse_upcoming_regattas(html: str | BeautifulSoup) -> list[RegattaListEntry]:
    """
    Parse the front page (/) and return regattas listed in the upcoming schedule.

    The front page uses a table.coming-regattas with columns:
      Name (linked to /<season>/<slug>/), Host, Type, Scoring, Start time

    Start time format: "03/06/2026 @ 10:00" -> regatta_start "2026-03-06"
    Scoring: "1 Division" / "2 Divisions" -> "divisional", "Team" -> "team"
    """
    soup = ensure_soup(html)
    results: list[RegattaListEntry] = []

    table = soup.find("table", class_="coming-regattas")
    if not table:
        return results

    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        a = tds[0].find("a", href=True)
        if not a:
            continue
        href = a["href"]
        m = re.match(r'^/([a-z]\d{2})/([^/]+)/?$', href)
        if not m:
            continue

        season, slug = m.group(1), m.group(2)
        host = tds[1].get_text(strip=True)
        # Heuristic: the front page only distinguishes team vs fleet here, so
        # anything not labelled "team" is treated as divisional. Combined-scoring
        # regattas are refined later once the regatta page itself is fetched.
        scoring_raw = tds[3].get_text(strip=True).lower()
        scoring_type = "team" if "team" in scoring_raw else "divisional"

        start_text = tds[4].get_text(strip=True)
        regatta_start = ""
        try:
            # Front-page dates render as US-style MM/DD/YYYY.
            regatta_start = datetime.strptime(start_text[:10], "%m/%d/%Y").date().isoformat()
        except ValueError:
            pass

        results.append(RegattaListEntry(
            name=a.get_text(strip=True),
            url=BASE_URL + href,
            slug=slug,
            season=season,
            status="upcoming",
            host=host,
            regatta_start=regatta_start,
            scoring_type=scoring_type,
        ))

    return results
