"""
icsa-scraper — a parser and analysis library for college sailing results.

Parses pages from scores.collegesailing.org (the ICSA Techscore system) into
plain dataclasses, and scrapes/assembles them into a queryable ``Dataset``.

Quick start::

    import scraper

    data = scraper.load("s26")
    data.fleet().results_frame()   # a pandas DataFrame, one row per (regatta, school)

Under the hood, ``load()`` fetches pages with ``scraper.Client`` and hands them
to the pure ``scraper.parsers`` — those parsers do no network I/O themselves,
so they're easy to test, cache, and call directly with HTML you already have.

Layers:
  - ``scraper.parsers`` — granular per-page HTML parsers (needs beautifulsoup4)
  - ``scraper.adapter``  — groups parser output into the ``scraper.models`` API
  - ``scraper.models``   — dataclasses describing the public data contract
  - ``scraper.cache``    — optional on-disk HTML cache
  - ``scraper.dataset``  — ``load``/``Dataset``: scrape a season into a queryable
    in-memory collection (the analysis layer)
  - ``scraper.head_to_head`` — compare two sailors without scraping a season

Heavier, optional pieces are NOT imported here so a core install stays light:
  - ``scraper.fetcher``  — async page fetching      (install extra: ``fetch``)
  - ``scraper.stores``   — DynamoDB ETag store       (install extra: ``aws``)
Import those modules explicitly when you need them. ``scraper.load()`` and
``scraper.Client`` also need the ``fetch`` extra, since they fetch pages themselves.
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
