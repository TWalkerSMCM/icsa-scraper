"""Small shared helpers used across the HTML parsers."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def ensure_soup(html_or_soup: str | BeautifulSoup) -> BeautifulSoup:
    """Return a BeautifulSoup tree, parsing only if given a raw string."""
    if isinstance(html_or_soup, BeautifulSoup):
        return html_or_soup
    return BeautifulSoup(html_or_soup, "lxml")


def extract_number(text: str) -> int | None:
    """Return the first integer found in text, or None if there is none."""
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None
