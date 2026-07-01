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

from scraper import adapter, cache, ids, models, urls, views
from scraper.assemble import fleet_scores, team_scores
from scraper.dataset import Dataset, load, load_regattas
from scraper.head_to_head import head_to_head
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
from scraper.parsers.sailor_profile import SailorParticipation
from scraper.parsers.sailor_profile import parse as sailor_profile
from scraper.sailor_races import sailor_races, team_sailor_races
from scraper.views import (
    Finish,
    HeadToHead,
    RaceEncounter,
    Result,
    SailorRaceFinish,
    SharedRegatta,
)

__version__ = "0.1.0"

# Network-touching pieces (need the `fetch` extra: httpx) are imported lazily so
# a core install can `import scraper` without httpx present.
_LAZY = {"Client"}


def __getattr__(name: str):
    if name in _LAZY:
        from scraper import client as _client

        return getattr(_client, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # analysis / assembly
    "urls",
    "ids",
    "fleet_scores",
    "team_scores",
    "sailor_races",
    "team_sailor_races",
    "sailor_profile",
    "SailorParticipation",
    "load",
    "load_regattas",
    "head_to_head",
    "Dataset",
    "Result",
    "Finish",
    "SailorRaceFinish",
    "SharedRegatta",
    "RaceEncounter",
    "HeadToHead",
    "views",
    "Client",
    # data layers
    "adapter",
    "cache",
    "models",
    # parsers
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
