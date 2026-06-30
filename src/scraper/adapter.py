"""
Adapter: techscore parser output -> scraper.models dataclasses.

Converts the normalized, granular output of scraper.parsers into the
RegattaScores / TeamRegattaScores structures that the iOS app and DynamoDB
expect.

Metadata (name, host, dates, etc.) comes from scraper.parsers.metadata — the
shared page-template extractor. This module only handles the score-specific
grouping and conversion logic.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional, TypedDict

from bs4 import BeautifulSoup

from scraper.parsers._soup import ensure_soup

from scraper.models import (
    RaceScore,
    DivisionResult,
    TeamResult,
    RegattaScores,
    TeamRaceMatch,
    TeamRaceRound,
    TeamRaceTeam,
    TeamRegattaScores,
)
from scraper.school_names import short_name
from scraper.parsers.metadata import PageMeta, extract as extract_page_meta
from scraper.parsers.full_scores import TeamDivScore, RaceScore as TechRaceScore
from scraper.parsers.team_all_races import RoundInfo, TeamRaceResult
from scraper.parsers.regatta import TeamScore as TeamRankingScore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _school_slug(url: str) -> str:
    m = re.search(r'/schools/([^/]+)/', url)
    return m.group(1) if m else ""


def _parse_title(title: str) -> tuple[Optional[str], Optional[str]]:
    """Extract (formula, comment) from title like '(15, Fleet + 1) RC comment'."""
    if not title:
        return None, None
    m = re.match(r'\(\d+[,:]\s*(.*?)\)\s*(.*)', title)
    if m:
        return m.group(1).strip(), (m.group(2).strip() or None)
    return None, None


def _convert_race_score(rs: TechRaceScore) -> RaceScore:
    penalty = rs.modifier if rs.modifier else None
    formula, comment = _parse_title(rs.title) if rs.title else (None, None)
    return RaceScore(
        race_num=rs.race_num,
        points=rs.score if rs.score is not None else 0,
        penalty=penalty,
        penalty_formula=formula,
        penalty_comment=comment,
    )


def _extract_fleet_context(
    soup: BeautifulSoup,
) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], tuple[str, str]]]:
    """Extract places and tiebreakers from the results table (one soup pass).

    Keys are (school_url, team_name) to handle regattas where one school has
    multiple entries (e.g. Tennessee 1/2/3 in TAG State Championships).
    """
    place_map: dict[tuple[str, str], int] = {}
    tiebreakers: dict[tuple[str, str], tuple[str, str]] = {}
    table = soup.find("table", class_="results")
    if table:
        rows = table.find_all("tr")
        for i, row in enumerate(rows):
            tds = row.find_all("td")
            if len(tds) < 3:
                continue
            place_text = tds[1].get_text(strip=True)
            if not place_text.isdigit():
                continue
            link = tds[2].find("a", href=True)
            if not link:
                continue
            url = link["href"]
            # Extract team name — two possible locations:
            # 1. Same cell, text before the <a> link (single-div: "Bears 1<br/><a>...")
            # 2. Next row's div-B/C row (multi-div: separate row with team name)
            team_name = ""
            for node in tds[2].children:
                if node == link:
                    break
                text = node.get_text(strip=True) if hasattr(node, "get_text") else str(node).strip()
                if text:
                    team_name = text
                    break
            if not team_name and i + 1 < len(rows):
                next_row = rows[i + 1]
                next_cls = next_row.get("class", [])
                is_div_row = any(c.startswith("div") for c in next_cls) and "totalrow" not in next_cls
                if is_div_row:
                    next_tds = next_row.find_all("td")
                    if len(next_tds) >= 3:
                        team_name = next_tds[2].get_text(strip=True)
            key = (url, team_name)
            place_map[key] = int(place_text)
            tiebreakers[key] = (
                tds[0].get_text(strip=True),
                tds[0].get("title", "").strip(),
            )
    return place_map, tiebreakers


def _extract_team_context(soup: BeautifulSoup) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """Extract team tiebreakers and school name lookup from the page."""
    team_tiebreakers: dict[str, tuple[str, str]] = {}
    ranking = soup.find("table", class_="teamranking")
    if ranking:
        for tr in ranking.select("tbody tr"):
            tds = tr.find_all("td")
            if len(tds) >= 4:
                link = tr.find("a", href=True)
                if link:
                    team_tiebreakers[link.get_text(strip=True)] = (
                        tds[0].get_text(strip=True),
                        tds[0].get("title", "").strip(),
                    )

    school_names: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        if "/schools/" in a["href"] and a["href"] not in school_names:
            school_names[a["href"]] = a.get_text(strip=True)

    return team_tiebreakers, school_names


# ---------------------------------------------------------------------------
# Fleet racing adapter
# ---------------------------------------------------------------------------

def build_fleet_scores(
    html: str | BeautifulSoup,
    season: str,
    slug: str,
    div_scores: list[TeamDivScore],
    division_ranks: Optional[dict[str, dict[str, int]]] = None,
) -> RegattaScores:
    """Convert techscore full_scores output into a RegattaScores."""
    soup = ensure_soup(html)
    meta = extract_page_meta(soup)
    place_map, tiebreakers = _extract_fleet_context(soup)

    div_scores = [ds for ds in div_scores if ds.division]

    # Group by (school_url, team_identifier), preserving table order.
    # This handles regattas where one school has multiple entries (e.g. J70s).
    # Use team_name (from parser) as the primary differentiator; fall back to
    # school_name for single-division regattas where team_name may be empty.
    team_order: list[tuple[str, str]] = []
    team_groups: dict[tuple[str, str], list[TeamDivScore]] = defaultdict(list)
    for ds in div_scores:
        team_id = ds.team_name or ds.school_name
        key = (ds.school_url, team_id)
        if key not in team_groups:
            team_order.append(key)
        team_groups[key].append(ds)

    teams: list[TeamResult] = []
    races_sailed: dict[str, int] = {}

    for school_url, team_name_key in team_order:
        group = team_groups[(school_url, team_name_key)]
        school_name = group[0].school_name
        slug_id = _school_slug(school_url)

        # Team name: prefer the non-school-name value (typically from div B row).
        # For single-division regattas with multiple entries per school (e.g. J70s),
        # team_name may be empty — fall back to the grouping key which uses school_name.
        team_name = group[0].team_name
        for ds in group:
            if ds.team_name and ds.team_name != school_name:
                team_name = ds.team_name
                break
        if not team_name:
            team_name = team_name_key

        divisions: dict[str, DivisionResult] = {}
        total = 0
        for ds in group:
            # Filter out empty cells (unsailed races: score=None, no modifier)
            races = [_convert_race_score(rs) for rs in ds.race_scores
                     if rs.score is not None or rs.modifier]
            rank = None
            if division_ranks and ds.division in division_ranks:
                rank = division_ranks[ds.division].get(slug_id)
            divisions[ds.division] = DivisionResult(total=ds.div_total, races=races, rank=rank)
            total += ds.div_total
            if races:
                races_sailed[ds.division] = len(races)

        # The context maps are keyed by (school_url, team_name_from_html).
        # In multi-div regattas, the HTML B-row has the team name (e.g. "Volunteers").
        # In single-div regattas, there's no B-row so the key is (url, "").
        # Try the resolved team_name first, then fall back to empty string.
        context_key = (school_url, team_name)
        if context_key not in place_map:
            context_key = (school_url, "")
        tb_sym, tb_note = tiebreakers.get(context_key, ("", ""))
        teams.append(TeamResult(
            place=place_map.get(context_key, 0),
            school=school_name, school_short=short_name(slug_id),
            school_slug=slug_id, school_url=school_url,
            team_name=team_name, total=total, divisions=divisions,
            tiebreaker=tb_sym, tiebreaker_note=tb_note,
        ))

    return RegattaScores(
        name=meta.name, season=season, slug=slug,
        scoring_type=meta.scoring_type, races_sailed=races_sailed,
        host=meta.host, regatta_start=meta.regatta_start,
        regatta_end=meta.regatta_end, is_final=meta.is_final,
        teams=teams,
    )


class TeamRaw(TypedDict, total=False):
    """Intermediate team-racing accumulator built in build_team_scores().

    total=False because ``place`` is assigned in a later pass, after the
    win/loss tallies are first constructed.
    """
    school: str
    school_url: str
    school_slug: str
    team_name: str
    total_wins: int
    total_losses: int
    total_ties: int
    win_pct: float
    rounds: list[TeamRaceRound]
    place: int


def _team_tb(
    tb_map: dict[tuple[str, str], tuple[str, str]],
    tb_fallback: dict[str, tuple[str, str]],
    t: TeamRaw,
) -> tuple[str, str]:
    """Look up tiebreaker for a team racing entry.

    Tries composite (school_url, team_name) first (from rankings),
    falls back to (school_url, "") then school name (from HTML context).
    """
    key = (t["school_url"], t["team_name"])
    if key in tb_map:
        return tb_map[key]
    fallback_key = (t["school_url"], "")
    if fallback_key in tb_map:
        return tb_map[fallback_key]
    return tb_fallback.get(t["school"], ("", ""))


# ---------------------------------------------------------------------------
# Team racing adapter
# ---------------------------------------------------------------------------

def build_team_scores(
    html: str | BeautifulSoup,
    season: str,
    slug: str,
    rounds: list[RoundInfo],
    race_results: list[TeamRaceResult],
    rankings: Optional[list[TeamRankingScore]] = None,
    flights: Optional[dict[int, int]] = None,
) -> TeamRegattaScores:
    """Convert techscore team_all_races output into a TeamRegattaScores.

    rankings: optional parsed output from the teamranking table on
        /full-scores/.  When provided, positions and tiebreakers come from
        the table instead of being computed from win percentage.
    flights: optional {race_num: flight_number} map from the rotations page.
        Flight numbers are 1-based and reset per round.  Missing entries
        leave the match's flight at 0 (unknown).
    """
    soup = ensure_soup(html)
    meta = extract_page_meta(soup)
    team_tiebreakers, school_names = _extract_team_context(soup)
    flight_by_race = flights or {}

    # Build lookup dicts from parsed rankings when available.
    # Key by (school_url, team_name) to handle multiple teams per school.
    team_place_map: dict[tuple[str, str], int] = {}
    team_tb_map: dict[tuple[str, str], tuple[str, str]] = {}
    if rankings:
        for r in rankings:
            team_place_map[(r.school_url, r.team_name)] = r.rank
            if r.tiebreaker or r.tiebreaker_note:
                team_tb_map[(r.school_url, r.team_name)] = (r.tiebreaker, r.tiebreaker_note)

    round_titles = {ri.relative_order: ri.title for ri in rounds}
    round_order = [ri.relative_order for ri in rounds] or [0]

    # Key by (school_slug, team_name) to handle multiple teams per school.
    team_data: dict[tuple[str, str], dict] = {}

    for race in race_results:
        round_key = race.round_order or 0
        s1 = _school_slug(race.team1_school_url)
        s2 = _school_slug(race.team2_school_url)
        k1 = (s1, race.team1_team_name)
        k2 = (s2, race.team2_team_name)

        for url, tname, key in [
            (race.team1_school_url, race.team1_team_name, k1),
            (race.team2_school_url, race.team2_team_name, k2),
        ]:
            if key not in team_data:
                team_data[key] = {
                    "school": school_names.get(url, key[0]),
                    "school_url": url, "team_name": tname,
                    "school_slug": key[0], "rounds": {},
                }

        sailed = bool(race.team1_earned) or bool(race.team2_earned)
        tied = not race.team1_won and not race.team2_won and sailed
        flight = flight_by_race.get(race.race_number, 0)

        team_data[k1]["rounds"].setdefault(round_key, []).append(
            TeamRaceMatch(race_num=race.race_number, opponent=s2,
                          won=race.team1_won, our_positions=race.team1_earned,
                          their_positions=race.team2_earned, sailed=sailed,
                          tied=tied, flight=flight))
        team_data[k2]["rounds"].setdefault(round_key, []).append(
            TeamRaceMatch(race_num=race.race_number, opponent=s1,
                          won=race.team2_won, our_positions=race.team2_earned,
                          their_positions=race.team1_earned, sailed=sailed,
                          tied=tied, flight=flight))

    teams_raw: list[TeamRaw] = []
    for (sk, _tname), data in team_data.items():
        tw = tl = tt = 0
        team_rounds: list[TeamRaceRound] = []
        for rk in round_order:
            matches = data["rounds"].get(rk, [])
            w = sum(1 for m in matches if m.sailed and m.won)
            l = sum(1 for m in matches if m.sailed and not m.won and not m.tied)
            t = sum(1 for m in matches if m.sailed and m.tied)
            tw += w; tl += l; tt += t
            rn = round_titles.get(rk, "Round 1")
            if matches:
                team_rounds.append(TeamRaceRound(name=rn, wins=w, losses=l, ties=t,
                                                 matches=sorted(matches, key=lambda m: m.race_num)))
        d = tw + tl + tt
        teams_raw.append({"school": data["school"], "school_url": data["school_url"],
                          "school_slug": data["school_slug"], "team_name": data["team_name"],
                          "total_wins": tw, "total_losses": tl, "total_ties": tt,
                          "win_pct": tw / d if d else 0.0, "rounds": team_rounds})

    if team_place_map:
        # Use official positions scraped from the teamranking table.
        # Try (school_url, team_name) first; fall back to (school_url, "")
        # for rankings that don't include team names.
        for t in teams_raw:
            key = (t["school_url"], t["team_name"])
            if key not in team_place_map:
                key = (t["school_url"], "")
            t["place"] = team_place_map.get(key, 0)
        teams_raw.sort(key=lambda t: (t["place"] or 999, -t["win_pct"]))
    else:
        # Fallback: compute from win percentage (inaccurate across rounds)
        teams_raw.sort(key=lambda t: (-t["win_pct"], t["total_losses"]))
        for i, t in enumerate(teams_raw):
            t["place"] = i + 1

    teams = []
    for t in teams_raw:
        tiebreaker, tiebreaker_note = _team_tb(team_tb_map, team_tiebreakers, t)
        teams.append(TeamRaceTeam(
            place=t["place"], school=t["school"], school_short=short_name(t["school_slug"]),
            school_slug=t["school_slug"], school_url=t["school_url"],
            team_name=t["team_name"], total_wins=t["total_wins"],
            total_losses=t["total_losses"], total_ties=t["total_ties"],
            win_pct=t["win_pct"], rounds=t["rounds"],
            tiebreaker=tiebreaker, tiebreaker_note=tiebreaker_note,
        ))

    return TeamRegattaScores(
        name=meta.name, season=season, slug=slug,
        host=meta.host, regatta_start=meta.regatta_start,
        regatta_end=meta.regatta_end, is_final=meta.is_final,
        teams=teams,
    )
