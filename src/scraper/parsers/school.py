"""
Parse a school season page, e.g. /schools/mit/f25/

HTML structure (from Techscore PHP source):
  - ul#page-info  → <li> rows of span.page-info-key / span.page-info-value;
                    the "Conference" row carries the conference affiliation.
  - h1            → the school's full display name.

Extracts the conference (e.g. "NEISA", "PCCSC") and the full school name.
"""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup

from scraper.parsers import metadata
from scraper.parsers._soup import ensure_soup


@dataclass
class SchoolInfo:
    conference: str  # e.g. "NEISA", "PCCSC"
    full_name: str  # e.g. "Massachusetts Institute of Technology"


def parse(html: str | BeautifulSoup) -> SchoolInfo:
    """Parse a school season page into a SchoolInfo (conference + full name)."""
    soup = ensure_soup(html)

    conference = metadata.page_info_value(soup, metadata.PAGE_INFO_CONFERENCE)

    # Full school name from h1
    full_name = ""
    h1 = soup.find("h1")
    if h1:
        full_name = h1.get_text(strip=True)

    return SchoolInfo(conference=conference, full_name=full_name)
