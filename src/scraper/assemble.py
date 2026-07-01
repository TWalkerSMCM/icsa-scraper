"""
One-call regatta assembly: HTML in, model out.

Folds parse + adapt into a single call so callers don't pass the same page
twice. These are the single home for assembly logic — the async
``scraper.fetcher.ICSAFetcher`` performs the equivalent steps for the live
poller; keep the two in sync.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from scraper.adapter import build_fleet_scores, build_team_scores
from scraper.models import RegattaScores, TeamRegattaScores
from scraper.parsers import division as _division
from scraper.parsers import full_scores as _full_scores
from scraper.parsers import team_all_races as _team_all_races
from scraper.parsers import team_rotations as _team_rotations
from scraper.parsers._soup import ensure_soup
from scraper.parsers.regatta import parse_team_ranking_table


def fleet_scores(
    html: str | BeautifulSoup,
    season: str,
    slug: str,
    *,
    division_html: dict[str, str] | None = None,
) -> RegattaScores:
    """Assemble a fleet-racing regatta from its ``/full-scores/`` HTML.

    Args:
        html: HTML (or soup) of the ``/full-scores/`` page.
        season, slug: regatta identity.
        division_html: optional ``{"A": html, ...}`` of per-division pages, used
            to fill each team's per-division tiebreak rank. Omit for the common
            case (overall places and totals don't need it).

    Returns:
        A ``RegattaScores``. ``teams == []`` means the page carried no fleet
        table (a team-racing regatta, or scores not yet posted).
    """
    soup = ensure_soup(html)
    div_scores = _full_scores.parse(soup)

    division_ranks: dict[str, dict[str, int]] | None = None
    if division_html:
        division_ranks = {}
        for div, dhtml in division_html.items():
            ranks: dict[str, int] = {}
            for r in _division.parse(dhtml, div):
                if r.school_slug and r.rank is not None:
                    ranks[r.school_slug] = r.rank
            division_ranks[div] = ranks

    return build_fleet_scores(soup, season, slug, div_scores, division_ranks)


def team_scores(
    all_html: str | BeautifulSoup,
    season: str,
    slug: str,
    *,
    full_scores_html: str | BeautifulSoup | None = None,
    rotations_html: str | BeautifulSoup | None = None,
) -> TeamRegattaScores:
    """Assemble a team-racing regatta from its ``/all/`` HTML.

    Args:
        all_html: HTML (or soup) of the ``/all/`` race list.
        season, slug: regatta identity.
        full_scores_html: optional ``/full-scores/`` HTML — adds the official
            team ranking (else win-pct order is used).
        rotations_html: optional ``/rotations/`` HTML — adds per-race flight
            numbers.

    Returns:
        A ``TeamRegattaScores``.
    """
    soup = ensure_soup(all_html)
    rounds, results = _team_all_races.parse(soup)

    rankings = None
    if full_scores_html is not None:
        fs_soup = ensure_soup(full_scores_html)
        table = fs_soup.find("table", class_="teamranking")
        if table is not None:
            rankings = parse_team_ranking_table(table)

    flights = None
    if rotations_html is not None:
        flights = _team_rotations.parse(rotations_html)

    return build_team_scores(
        soup, season, slug, rounds, results, rankings=rankings, flights=flights
    )
