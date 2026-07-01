"""
The RP↔finish join: which sailor sailed which race, and the place their boat
earned. This is the reconstruction that makes sailor-level analysis (skipper
ELO, head-to-head) possible from parsed pages — it ports the attribution logic
that previously lived only in the analytics SQLite writer.

The public ``sailor_races`` / ``team_sailor_races`` parse HTML then delegate to
the pure ``_join_fleet`` / ``_join_team`` joins, which operate on parser output
(kept separate so the attribution logic is testable without HTML fixtures).
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from bs4 import BeautifulSoup

from scraper import ids
from scraper.parsers._soup import ensure_soup
from scraper.parsers import full_scores as _full_scores
from scraper.parsers import sailors as _sailors
from scraper.parsers import team_all_races as _team_all_races
from scraper.parsers import team_sailors as _team_sailors
from scraper.parsers.full_scores import TeamDivScore
from scraper.parsers.sailors import RpEntry
from scraper.parsers.team_all_races import RoundInfo, TeamRaceResult
from scraper.parsers.team_sailors import MatchupRP
from scraper.views import SailorRaceFinish


def _sailor_slug(name: str, sailor_links: Optional[dict[str, str]]) -> str:
    """Canonical sailor slug: prefer the profile link, else synthesize from name."""
    if sailor_links and name in sailor_links:
        s = ids.sailor_slug(sailor_links[name])
        if s:
            return s
    first, last, _, _ = ids.split_sailor_name(name)
    slug = f"{first}-{last}".lower().replace(" ", "-").replace("'", "")
    return re.sub(r"[^a-z0-9-]", "", slug)


# ── fleet ──────────────────────────────────────────────────────────────────────

def sailor_races(
    full_scores_html: str | BeautifulSoup,
    sailors_html: str | BeautifulSoup | None = None,
    *,
    season: str = "",
    slug: str = "",
) -> list[SailorRaceFinish]:
    """Join RP attribution to per-race finishes for one fleet regatta.

    Args:
        full_scores_html: the ``/full-scores/`` page (each team's per-race
            scores per division).
        sailors_html: the ``/sailors/`` (RP) page. Pass ``None`` for singlehanded
            regattas, which have no RP page — each skipper is then synthesized
            from the full-scores rows.
        season, slug: stamped onto each row for identity.

    Returns:
        One ``SailorRaceFinish`` per (sailor, race) sailed. An empty race-range
        on the RP page means the sailor sailed every race in their division.
    """
    div_scores = _full_scores.parse(ensure_soup(full_scores_html))
    rp = _sailors.parse(sailors_html)[0] if sailors_html is not None else []
    return _join_fleet(div_scores, rp, season, slug)


def _join_fleet(
    div_scores: list[TeamDivScore],
    rp: list[RpEntry],
    season: str,
    slug: str,
) -> list[SailorRaceFinish]:
    """Pure join of RP entries to per-race finishes (see ``sailor_races``)."""
    # Index team-division score rows by (school_slug, division). Most schools
    # field one team per division; disambiguate A/B entries on team_name.
    by_school_div: dict[tuple[str, str], list[TeamDivScore]] = defaultdict(list)
    for ds in div_scores:
        sslug = ds.school_id or ids.school_slug(ds.school_url)
        by_school_div[(sslug, ds.division)].append(ds)

    def resolve(sslug: str, team_name: str, division: str) -> TeamDivScore | None:
        cands = by_school_div.get((sslug, division), [])
        if len(cands) == 1:
            return cands[0]
        for ds in cands:
            if ds.team_name == team_name:
                return ds
        return cands[0] if cands else None

    out: list[SailorRaceFinish] = []
    if rp:
        for e in rp:
            sslug = ids.school_slug(e.school_url)
            td = resolve(sslug, e.team_name, e.division)
            if td is None:
                continue
            places = {rs.race_num: rs.score for rs in td.race_scores if rs.score is not None}
            for rn in ids.expand_races(e.races, sorted(places)):
                if rn in places:
                    out.append(SailorRaceFinish(
                        season=season, regatta_slug=slug,
                        sailor_slug=ids.sailor_slug(e.sailor_url), sailor_name=e.sailor_name,
                        school_slug=sslug, team_name=e.team_name, division=e.division,
                        race_num=rn, place=places[rn], boat_role=e.boat_role,
                    ))
    else:
        # Singlehanded: RP synthesized from full-scores rows (one skipper/team).
        for ds in div_scores:
            if not ds.sailor_name:
                continue
            sslug = ds.school_id or ids.school_slug(ds.school_url)
            for rs in ds.race_scores:
                if rs.score is None:
                    continue
                out.append(SailorRaceFinish(
                    season=season, regatta_slug=slug,
                    sailor_slug=ids.sailor_slug(ds.sailor_url), sailor_name=ds.sailor_name,
                    school_slug=sslug, team_name=ds.team_name or ds.school_name,
                    division=ds.division, race_num=rs.race_num, place=rs.score,
                    boat_role="skipper",
                ))
    return out


# ── team racing ────────────────────────────────────────────────────────────────

def team_sailor_races(
    all_html: str | BeautifulSoup,
    sailors_html: str | BeautifulSoup,
    *,
    season: str = "",
    slug: str = "",
    sailor_links: Optional[dict[str, str]] = None,
) -> list[SailorRaceFinish]:
    """Join team-racing RP to per-race earned positions.

    Team racing attributes sailors per (round, matchup, division). Each boat's
    ``place`` is the physical finish its team earned in that race/division.

    Args:
        all_html: the ``/all/`` race list (earned positions per race).
        sailors_html: the team ``/sailors/`` (RP) page.
        season, slug: stamped onto each row.
        sailor_links: optional ``display_name -> profile_url`` map (from the
            overview page) for canonical sailor slugs; names are otherwise
            synthesized.

    Returns:
        One ``SailorRaceFinish`` per (sailor, race) sailed. Team-label resolution
        is best-effort (mascot / school-name matching), mirroring the analytics
        pipeline; unresolvable matchups are skipped.
    """
    rounds, results = _team_all_races.parse(ensure_soup(all_html))
    matchups = _team_sailors.parse(sailors_html)
    return _join_team(rounds, results, matchups, season, slug, sailor_links)


def _join_team(
    rounds: list[RoundInfo],
    results: list[TeamRaceResult],
    matchups: list[MatchupRP],
    season: str,
    slug: str,
    sailor_links: Optional[dict[str, str]],
) -> list[SailorRaceFinish]:
    """Pure join of team RP to earned positions (see ``team_sailor_races``)."""
    if not matchups or not results:
        return []

    # Resolver: team display label -> school_slug, built from the race results.
    slug_by_mascot: dict[str, str] = {}
    all_slugs: set[str] = set()
    for r in results:
        for url, mascot in ((r.team1_school_url, r.team1_team_name),
                            (r.team2_school_url, r.team2_team_name)):
            s = ids.school_slug(url)
            if s:
                all_slugs.add(s)
                if mascot:
                    slug_by_mascot[mascot] = s

    def resolve(label: str) -> Optional[str]:
        if label in slug_by_mascot:
            return slug_by_mascot[label]
        parts = label.rsplit(" ", 1)          # "Bentley Falcons" -> "Falcons"
        if len(parts) == 2 and parts[1] in slug_by_mascot:
            return slug_by_mascot[parts[1]]
        for mascot, s in slug_by_mascot.items():
            if label.endswith(" " + mascot):
                return s
        cand = re.sub(r"[^a-z0-9-]", "", label.lower().replace(" ", "-"))
        if cand in all_slugs:
            return cand
        for s in all_slugs:
            if cand and (cand.startswith(s) or s.startswith(cand)):
                return s
        return None

    order_by_title = {ri.title: ri.relative_order for ri in rounds}

    out: list[SailorRaceFinish] = []
    for m in matchups:
        tslug = resolve(m.team_name)
        oslug = resolve(m.opponent_name)
        if not tslug or not oslug or tslug == oslug:
            continue
        target_order = order_by_title.get(m.round_title)

        for r in results:
            if target_order is not None and r.round_order != target_order:
                continue
            s1, s2 = ids.school_slug(r.team1_school_url), ids.school_slug(r.team2_school_url)
            if {s1, s2} != {tslug, oslug}:
                continue
            earned = r.team1_earned if s1 == tslug else r.team2_earned
            for boat in m.boats:
                di = ord(boat.division) - ord("A")
                if di < 0 or di >= len(earned):
                    continue
                place = earned[di]
                for role, name in (("skipper", boat.skipper_name), ("crew", boat.crew_name)):
                    if not name:
                        continue
                    out.append(SailorRaceFinish(
                        season=season, regatta_slug=slug,
                        sailor_slug=_sailor_slug(name, sailor_links), sailor_name=name,
                        school_slug=tslug, team_name=m.team_name, division=boat.division,
                        race_num=r.race_number, place=place, boat_role=role,
                    ))
    return out
