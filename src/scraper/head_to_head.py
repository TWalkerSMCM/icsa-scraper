"""
Head-to-head comparison of two sailors — efficiently.

Rather than scraping a season, this fetches each sailor's profile (one page
each), intersects the regattas they shared, and — only if you ask for race-level
detail — loads just those shared regattas. See :func:`head_to_head`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scraper import urls
from scraper.dataset import load_regattas
from scraper.parsers.sailor_profile import parse as _parse_profile
from scraper.views import HeadToHead, RaceEncounter, SharedRegatta

if TYPE_CHECKING:
    from scraper.client import Client


def head_to_head(
    a: str,
    b: str,
    *,
    races: bool = False,
    client: Client | None = None,
    refresh: bool = False,
) -> HeadToHead:
    """Compare two sailors by slug.

    Fetches both sailor profiles (2 requests) and intersects the regatta
    *divisions* they both sailed, with each sailor's finishing place — enough for
    a summary without loading any regatta. When ``races=True``, it additionally
    loads only the shared regattas and finds the individual races both sailed.

    Args:
        a, b: sailor slugs (e.g. ``"jane-doe"``), as in ``/sailors/{slug}/``.
        races: also compute per-race encounters (loads the shared regattas).
        client: a configured ``scraper.Client``; created/closed if omitted.
        refresh: bypass the disk cache and re-fetch.

    Returns:
        A ``HeadToHead`` with ``.shared`` (regatta-division overlaps) and, if
        requested, ``.races`` (per-race encounters), plus ``.a_ahead`` /
        ``.b_ahead`` / ``.a_race_wins`` / ``.b_race_wins`` tallies.
    """
    from scraper.client import Client  # lazy: needs httpx

    own_client = client is None
    client = client or Client()
    try:
        # fetch raises on a missing profile (404), so these are never None here.
        pa = _parse_profile(client.fetch(urls.sailor_profile(a), refresh=refresh) or "")
        pb = _parse_profile(client.fetch(urls.sailor_profile(b), refresh=refresh) or "")

        # Index each sailor's placements by (season, slug, division).
        a_by_key = {(r.season, r.slug, r.division): r for r in pa}
        b_by_key = {(r.season, r.slug, r.division): r for r in pb}

        shared: list[SharedRegatta] = []
        for key in sorted(a_by_key.keys() & b_by_key.keys()):
            ra, rb = a_by_key[key], b_by_key[key]
            shared.append(
                SharedRegatta(
                    season=ra.season,
                    slug=ra.slug,
                    regatta_name=ra.regatta_name,
                    division=ra.division,
                    place_a=ra.place,
                    place_b=rb.place,
                    fleet_size=ra.fleet_size,
                )
            )

        encounters: list[RaceEncounter] = []
        if races and shared:
            refs = sorted({(s.season, s.slug) for s in shared})
            data = load_regattas(refs, client=client, refresh=refresh)
            a_races = {
                (r.season, r.regatta_slug, r.division, r.race_num): r.place
                for r in data.sailor(a).sailor_races
            }
            b_races = {
                (r.season, r.regatta_slug, r.division, r.race_num): r.place
                for r in data.sailor(b).sailor_races
            }
            for season, slug, div, race_num in sorted(a_races.keys() & b_races.keys()):
                encounters.append(
                    RaceEncounter(
                        season=season,
                        regatta_slug=slug,
                        division=div,
                        race_num=race_num,
                        place_a=a_races[(season, slug, div, race_num)],
                        place_b=b_races[(season, slug, div, race_num)],
                    )
                )

        return HeadToHead(a=a, b=b, shared=shared, races=encounters)
    finally:
        if own_client:
            client.close()
