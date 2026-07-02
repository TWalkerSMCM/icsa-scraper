"""
Shared fixture-page builders and a mock-transport Client helper for
orchestration tests (test_load.py, test_head_to_head.py, test_client.py
additions).

``make_client`` wires a REAL ``scraper.Client`` onto an ``httpx.MockTransport``
so tests exercise the full Client -> cache -> parser -> assemble pipeline with
no real network access. The page builders below produce real HTML — reusing
``tests/html_fixtures.py`` where possible — shaped exactly as the parsers in
``scraper.parsers`` expect, keyed by site-relative path (matching
``scraper.urls``).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import httpx

from html_fixtures import date_block, full_scores_2div, team_all_scores
from scraper.client import Client

# ---------------------------------------------------------------------------
# Mock-transport Client
# ---------------------------------------------------------------------------


def make_client(
    pages: dict[str, str],
    tmp_path: Path,
    *,
    requests: list[str] | None = None,
    delay_fn: Callable[[str], float] | None = None,
    **kw,
) -> Client:
    """Build a real ``Client`` wired to an ``httpx.MockTransport``.

    Args:
        pages: site-relative path -> HTML. Paths not present 404.
        tmp_path: on-disk cache dir for this Client instance.
        requests: if given, every requested path is appended here (in request
            order) so tests can assert which paths were actually fetched.
        delay_fn: optional path -> seconds; the handler sleeps that long
            before responding (used to test concurrency ordering).
        **kw: forwarded to ``Client(...)`` (e.g. ``delay=``, ``timeout=``).
    """

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if requests is not None:
            requests.append(path)
        if delay_fn is not None:
            wait = delay_fn(path)
            if wait:
                time.sleep(wait)
        if path in pages:
            return httpx.Response(200, text=pages[path])
        return httpx.Response(404, text="not found")

    transport = httpx.MockTransport(handler)
    return Client(cache_dir=tmp_path, transport=transport, **kw)


# ---------------------------------------------------------------------------
# Season index page (scraper.parsers.season)
# ---------------------------------------------------------------------------


def season_index_page(entries: list[tuple[str, str]]) -> str:
    """Build a season index page listing ``(slug, name)`` regattas.

    Links are bare relative slugs (``href="cactus-cup"``), matching the real
    site markup that ``scraper.parsers.season.parse`` expects.
    """
    rows = "".join(
        f'<tr><td><a href="{slug}">{name}</a></td><td>March 1-2</td></tr>' for slug, name in entries
    )
    return f"<html><body><table>{rows}</table></body></html>"


# ---------------------------------------------------------------------------
# Regatta overview page (scraper.parsers.regatta)
# ---------------------------------------------------------------------------


def overview_page(
    season: str,
    slug: str,
    name: str,
    *,
    has_sailors: bool = True,
    has_all: bool = False,
    host: str = "Navy",
) -> str:
    """Build a regatta overview page with just the nav links parsers/regatta.py
    reads (ground truth: only linked sub-pages are considered present).

    ``has_all=True`` links the ``/all/`` team-racing race list, which is what
    ``parsers/regatta.py`` uses to infer team-racing scoring (see
    ``_extract_scoring_and_participant``).
    """
    base = f"/{season}/{slug}/"
    links = f'<a href="{base}full-scores/">Full Scores</a>'
    if has_sailors:
        links += f'<a href="{base}sailors/">Sailors</a>'
    if has_all:
        links += f'<a href="{base}all/">All Races</a>'
    return f"""<html><body>
<title>{name} | Techscore</title>
<h1>{name}</h1>
{date_block(host=host)}
{links}
</body></html>"""


# ---------------------------------------------------------------------------
# Fleet full-scores page (scraper.parsers.full_scores)
# ---------------------------------------------------------------------------


def fleet_full_scores_page(n_races: int) -> str:
    """Two schools (navy, mit), divisions A/B, ``n_races`` races each.

    Navy places 1st every race in both divisions; MIT places 2nd. Deterministic
    so callers can assert exact places by (division, race_num).
    """
    teams = [
        {
            "place": 1,
            "school": "Navy",
            "school_url": "/schools/navy/s26/",
            "mascot": "Midshipmen",
            "a_scores": [1] * n_races,
            "a_total": n_races,
            "b_scores": [1] * n_races,
            "b_total": n_races,
            "sum_total": 2 * n_races,
        },
        {
            "place": 2,
            "school": "MIT",
            "school_url": "/schools/mit/s26/",
            "mascot": "Engineers",
            "a_scores": [2] * n_races,
            "a_total": 2 * n_races,
            "b_scores": [2] * n_races,
            "b_total": 2 * n_races,
            "sum_total": 4 * n_races,
        },
    ]
    return full_scores_2div(teams, race_nums=list(range(1, n_races + 1)))


def empty_full_scores_page() -> str:
    """A full-scores page whose table carries no team rows (scores not posted)."""
    from html_fixtures import fs_header, fs_page

    return fs_page(fs_header([1, 2, 3]), [])


# ---------------------------------------------------------------------------
# Sailors / RP page (scraper.parsers.sailors)
# ---------------------------------------------------------------------------


def _rp_team_rows(school: str, school_url: str, team_name: str, divisions: dict) -> str:
    """One team's rowspan-merged rows: divisions is {"A": (rank, name, url), ...}."""
    div_items = list(divisions.items())
    n = len(div_items)
    rows = []
    for i, (div, (rank, name, url)) in enumerate(div_items):
        cells = ""
        if i == 0:
            cells += (
                f'<td class="schoolname" rowspan="{n}"><a href="{school_url}">{school}</a></td>'
            )
            cells += f'<td class="teamname" rowspan="{n}">{team_name}</td>'
        cells += f'<td class="division-cell" rowspan="1">{div}</td>'
        cells += f'<td class="rank-cell">{rank}</td>'
        cells += f'<td><a href="{url}">{name}</a></td>'
        cells += '<td class="races"></td>'
        cells += "<td></td><td></td>"  # empty crew + crew-races
        rows.append(f"<tr>{cells}</tr>")
    return "".join(rows)


def sailors_page(teams: list[dict]) -> str:
    """Build a ``/sailors/`` RP page.

    Each team dict: school, school_url, team_name, divisions (dict of
    ``div -> (rank, skipper_name, skipper_url)``), one skipper per division,
    no crew (kept minimal — the parser's crew-cell path is exercised
    separately in tests/test_sailor_races.py).
    """
    header = "<tr><th>School</th><th>Team</th><th>Div.</th><th>Rank</th>"
    header += "<th>Skipper</th><th>Races</th><th>Crew</th><th>Races</th></tr>"
    rows = "".join(
        _rp_team_rows(t["school"], t["school_url"], t["team_name"], t["divisions"]) for t in teams
    )
    return f"""<html><body>
<table class="coordinate sailors">{header}{rows}</table>
</body></html>"""


# ---------------------------------------------------------------------------
# Team racing pages (scraper.parsers.team_all_races)
# ---------------------------------------------------------------------------


def team_all_races_page(host: str = "MIT") -> str:
    """A minimal 2-team, 1-round team-racing /all/ page."""
    rounds = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-3",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "2-4",
                    "winner": 1,
                },
            ],
        }
    ]
    return team_all_scores(rounds, host=host)
