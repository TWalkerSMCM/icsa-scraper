"""
icsa-scraper — HTML parsers for college sailing results.

Parses pages from scores.collegesailing.org (the ICSA Techscore system) into
plain dataclasses. Pass in HTML you already have; the parsers do no network I/O.

Quick start::

    import httpx
    from scraper.parsers import division

    html = httpx.get("https://scores.collegesailing.org/s25/<regatta>/A/").text
    results = division.parse(html, "A")   # -> list[TeamDivisionResult]

Layers:
  - ``scraper.parsers`` — granular per-page HTML parsers (needs beautifulsoup4)
  - ``scraper.adapter``  — groups parser output into the ``scraper.models`` API
  - ``scraper.models``   — dataclasses describing the public data contract
  - ``scraper.cache``    — optional on-disk HTML cache

Heavier, optional pieces are NOT imported here so a core install stays light:
  - ``scraper.fetcher``  — async page fetching      (install extra: ``fetch``)
  - ``scraper.stores``   — DynamoDB ETag store       (install extra: ``aws``)
Import those modules explicitly when you need them.
"""

from __future__ import annotations

from scraper import adapter, cache, models
from scraper.parsers import (
    division,
    full_scores,
    metadata,
    regatta,
    rotations_teams,
    sailors,
    school,
    season,
    team_all_races,
    team_rotations,
    team_sailors,
)

__version__ = "0.1.0"

__all__ = [
    "adapter",
    "cache",
    "models",
    "division",
    "full_scores",
    "metadata",
    "regatta",
    "rotations_teams",
    "sailors",
    "school",
    "season",
    "team_all_races",
    "team_rotations",
    "team_sailors",
]
