"""
Lightweight rotation page parser — extracts only the list of participating teams.

This is intentionally minimal: it pulls school slugs from the rotation page HTML
and nothing else (no sail numbers, race assignments, or rotation patterns).  Other
parsers in scraper/parsers/ aim for full coverage of their respective pages; a full
rotations.py parser can be added later if needed.

The rotation page is available once rotations are assigned, which typically happens
before racing starts — making it the best source for attributing teams to upcoming
regattas that don't yet have scores.

HTML structure (from Techscore PHP source):
  Fleet racing  — RotationTable.php:
    <table class="rotation"> → <td class="teamname"> → <a href="/schools/{slug}/{season}/">
  Team racing   — TeamRotationTable.php:
    <table class="tr-rotation-table"> → <td class="team1|team2"> → <a href="/schools/{slug}/{season}/">
    Placeholder rows use <em class="no-team"> (no <a>), flight separators have no links.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scraper.parsers._soup import ensure_soup

# Matches /schools/{slug}/...; capture group 1 is the school slug.
_SCHOOL_RE = re.compile(r"^/schools/([^/]+)/")


def parse(html: str | BeautifulSoup) -> list[str]:
    """Return a sorted, deduplicated list of school slugs from a rotation page."""
    soup = ensure_soup(html)
    slugs: set[str] = set()

    # Fleet rotation tables
    for a in soup.select("table.rotation td.teamname a[href]"):
        m = _SCHOOL_RE.match(a["href"])
        if m:
            slugs.add(m.group(1))

    # Team racing rotation tables
    for cls in ("team1", "team2"):
        for a in soup.select(f"table.tr-rotation-table td.{cls} a[href]"):
            m = _SCHOOL_RE.match(a["href"])
            if m:
                slugs.add(m.group(1))

    return sorted(slugs)


# Back-compat alias — descriptive name kept for existing call sites.
parse_team_slugs = parse
