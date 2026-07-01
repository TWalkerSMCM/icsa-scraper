"""
Parse a public sailor profile page, e.g. /sailors/jane-doe/

Structure (from Techscore ``lib/data/SailorRegattaTable.php`` +
``SailorPlaceFinishDisplay.php``): one ``table.participation-table`` per season,
each row a schema.org SportsEvent with columns:

    Name | Host | Date | Position | Place finish

  - Name:  <a itemprop="url" href="/{season}/{slug}/"><span itemprop="name">…</span></a>
  - Date:  <time itemprop="startDate" datetime="…">
  - Position: boat role(s) — "Skipper" / "Crew" / "Skipper, Crew" / "Reserve"
  - Place finish: <span class="sailor-placement-container"> with one <a> per
    division, text "{rank}/{fleet} ({Div} Div)" (fleet) or "{rank}/{fleet}"
    (combined / team racing).

Yields one row per (regatta, placement); a sailor who scored in multiple
divisions produces multiple rows. This page is the whole cross-season history in
a single fetch — use it to find which regattas two sailors shared.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from scraper.parsers._soup import ensure_soup

_HREF_RE = re.compile(r"^/([sfmw]\d{2})/([^/]+)/$")
_PLACE_RE = re.compile(r"(\d+)\s*/\s*(\d+)(?:\s*\(([A-D])\s*Div\))?")


@dataclass
class SailorParticipation:
    season: str
    slug: str  # regatta slug
    regatta_name: str
    host: str
    date: str  # ISO "YYYY-MM-DD" (or raw text if no datetime attr)
    roles: str  # "Skipper" / "Crew" / "Skipper, Crew" / "Reserve"
    division: str  # "A".."D", or "" for combined/team/overall
    place: int | None  # finishing rank; None if not yet placed
    fleet_size: int | None


def parse(html: str | BeautifulSoup) -> list[SailorParticipation]:
    """Parse a sailor profile page into a list of SailorParticipation rows."""
    soup = ensure_soup(html)
    out: list[SailorParticipation] = []

    for table in soup.find_all("table", class_="participation-table"):
        for row in table.find_all("tr"):
            link = row.find("a", attrs={"itemprop": "url"}) or row.find("a", href=_HREF_RE)
            if link is None:
                continue  # header or non-regatta row
            m = _HREF_RE.match(link.get("href", ""))
            if not m:
                continue
            season, slug = m.group(1), m.group(2)

            name_span = link.find("span", attrs={"itemprop": "name"})
            regatta_name = (name_span or link).get_text(strip=True)

            cells = row.find_all("td")
            host = cells[1].get_text(strip=True) if len(cells) > 1 else ""

            time_el = row.find("time", attrs={"itemprop": "startDate"})
            date = ""
            if time_el is not None:
                dt = time_el.get("datetime", "")
                date = dt[:10] if dt else time_el.get_text(strip=True)

            roles = cells[3].get_text(strip=True) if len(cells) > 3 else ""

            container = row.find("span", class_="sailor-placement-container")
            placements = _parse_placements(container.get_text(" ", strip=True) if container else "")
            if not placements:
                placements = [("", None, None)]

            for division, place, fleet in placements:
                out.append(
                    SailorParticipation(
                        season=season,
                        slug=slug,
                        regatta_name=regatta_name,
                        host=host,
                        date=date,
                        roles=roles,
                        division=division,
                        place=place,
                        fleet_size=fleet,
                    )
                )
    return out


def _parse_placements(text: str) -> list[tuple[str, int | None, int | None]]:
    """Extract (division, place, fleet_size) tuples from a placement string."""
    results: list[tuple[str, int | None, int | None]] = []
    for m in _PLACE_RE.finditer(text):
        results.append((m.group(3) or "", int(m.group(1)), int(m.group(2))))
    return results
