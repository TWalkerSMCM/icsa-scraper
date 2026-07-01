"""
Shared metadata extraction from Techscore page templates.

Every Techscore page (main, full-scores, /all/, division) shares the same
page template with common elements: h1, time[itemprop=startDate],
span[itemprop=location], ul#page-info, etc.

This module extracts that shared metadata from a page (a raw HTML string or a
pre-parsed BeautifulSoup) so it can be reused by both regatta.py and the
adapter without re-parsing or reimplementing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta

from bs4 import BeautifulSoup

from scraper.parsers._soup import ensure_soup

_MONTH_NUMS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# Key labels in the shared ul#page-info metadata list (span.page-info-key text).
PAGE_INFO_SCORING = "Scoring"
PAGE_INFO_BOAT = "Boat"
PAGE_INFO_TYPE = "Type"
PAGE_INFO_CONFERENCE = "Conference"


@dataclass
class PageMeta:
    """Metadata extracted from a Techscore page template."""

    name: str = ""
    host: str = ""
    is_final: bool = False
    scoring_type: str = "divisional"  # "divisional", "combined", "team"
    regatta_start: str = ""  # "YYYY-MM-DD"
    regatta_end: str = ""  # "YYYY-MM-DD"


def parse(html_or_soup: str | BeautifulSoup) -> PageMeta:
    """Extract shared page-template metadata from a Techscore page."""
    soup = ensure_soup(html_or_soup)
    return PageMeta(
        name=_extract_name(soup),
        host=_extract_host(soup),
        is_final=_extract_is_final(soup),
        scoring_type=_extract_scoring_type(soup),
        regatta_start=_extract_start_date(soup),
        regatta_end=extract_end_date(soup),
    )


def page_info_value(soup: BeautifulSoup, key: str) -> str:
    """Return the value for an exact key in the shared ul#page-info list.

    Reads the first <li> whose span.page-info-key text equals key and returns
    its span.page-info-value text, or "" if the key is absent.
    """
    ul = soup.find("ul", id="page-info")
    if not ul:
        return ""
    for li in ul.find_all("li"):
        key_span = li.find("span", class_="page-info-key")
        val_span = li.find("span", class_="page-info-value")
        if key_span and val_span and key_span.get_text(strip=True) == key:
            return val_span.get_text(strip=True)
    return ""


# Back-compat alias — this module's entry point was historically named extract().
extract = parse


def _extract_name(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def _extract_host(soup: BeautifulSoup) -> str:
    loc = soup.find("span", itemprop="location")
    return loc.get_text(strip=True) if loc else ""


def _extract_is_final(soup: BeautifulSoup) -> bool:
    for el in soup.find_all(["h2", "h3", "h4", "p"]):
        text = el.get_text(strip=True).lower()
        if "final results" in text:
            return True
        if "preliminary" in text:
            return False
    return False


def _extract_scoring_type(soup: BeautifulSoup) -> str:
    """Read scoring type from the page-info metadata list.

    Returns 'divisional', 'combined', or 'team'.
    """
    for li in soup.select("ul#page-info li"):
        key = li.find("span", class_="page-info-key")
        val = li.find("span", class_="page-info-value")
        if key and PAGE_INFO_SCORING in key.get_text():
            raw = val.get_text(strip=True).lower() if val else ""
            if "team" in raw:
                return "team"
            if "combined" in raw:
                return "combined"
            return "divisional"
    return "divisional"


def _extract_start_date(soup: BeautifulSoup) -> str:
    """Extract start date as 'YYYY-MM-DD' from the datetime attribute."""
    time_el = soup.find("time", itemprop="startDate")
    if not time_el:
        return ""
    dt_attr = time_el.get("datetime", "")
    return dt_attr[:10] if dt_attr else ""


def extract_end_date(soup: BeautifulSoup) -> str:
    """Parse end date from startDate <time> element text.

    e.g. "March 6-8, 2026" → "2026-03-08"
         "February 28 - March 1, 2026" → "2026-03-01"
         "March 6, 2026" → "2026-03-06"
    Falls back to start date if parsing fails.
    """
    time_el = soup.find("time", itemprop="startDate")
    if not time_el:
        return ""

    text = time_el.get_text(strip=True)
    year_m = re.search(r"\b(\d{4})\b", text)
    if not year_m:
        # Fall back to start date
        return _extract_start_date(soup)

    year = int(year_m.group(1))
    date_part = text[: year_m.start()].strip().rstrip(",").strip()

    # "Month DD - Month DD" (cross-month)
    cross = re.match(r"(\w+)\s+\d+\s*-\s*(\w+)\s+(\d+)$", date_part, re.IGNORECASE)
    if cross:
        month_num = _MONTH_NUMS.get(cross.group(2).lower())
        if month_num:
            return f"{year:04d}-{month_num:02d}-{int(cross.group(3)):02d}"

    # "Month DD-DD" (same month)
    same = re.match(r"(\w+)\s+\d+\s*-\s*(\d+)$", date_part, re.IGNORECASE)
    if same:
        month_num = _MONTH_NUMS.get(same.group(1).lower())
        if month_num:
            return f"{year:04d}-{month_num:02d}-{int(same.group(2)):02d}"

    # Single day "Month DD"
    single = re.match(r"(\w+)\s+(\d+)$", date_part, re.IGNORECASE)
    if single:
        month_num = _MONTH_NUMS.get(single.group(1).lower())
        if month_num:
            return f"{year:04d}-{month_num:02d}-{int(single.group(2)):02d}"

    return _extract_start_date(soup)


def season_week(season: str, regatta_start: str) -> int:
    """Compute the week number within the season for a regatta.

    Mirrors techscore's Season::getFirstSaturday() + UpdateSeason.php:
    - Spring: first Saturday >= Feb 1 of the year in the season code
    - Fall:   first Saturday >= Sep 1 of the year in the season code
    - Week = regatta_ISO_week - first_saturday_ISO_week + 1

    Args:
        season: season code, e.g. "s26" or "f25"
        regatta_start: ISO date string "YYYY-MM-DD"

    Returns:
        Week number (1-based), or 0 if inputs are invalid.
    """
    if not regatta_start or len(regatta_start) < 10 or not season or len(season) < 3:
        return 0
    try:
        rd = date_type.fromisoformat(regatta_start[:10])
    except ValueError:
        return 0

    season_type = season[0]
    try:
        year = 2000 + int(season[1:3])
    except ValueError:
        return 0

    if season_type == "s":
        anchor = date_type(year, 2, 1)
    elif season_type == "f":
        anchor = date_type(year, 9, 1)
    else:
        return 0

    # First Saturday on or after the anchor (Saturday = weekday 5)
    days_until_sat = (5 - anchor.weekday()) % 7
    first_saturday = anchor + timedelta(days=days_until_sat)

    first_week = first_saturday.isocalendar()[1]
    regatta_week = rd.isocalendar()[1]
    week = regatta_week - first_week + 1
    # Handle year boundary wrap-around (fall seasons crossing into January)
    if week < 0 and rd > first_saturday:
        week += 52
    return max(week, 0)
