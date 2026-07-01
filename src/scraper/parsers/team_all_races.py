"""
Parse a team racing /all/ page, e.g. /s25/some-team-race/all/

Table class: "teamscorelist"
Rows alternate between round headers (class "roundrow") and race data rows.

Each data row:
  [0] race# | [1] burgee1 | [2] school+team1 (with school link) | [3] places "2-4-6"
  [4] "vs"  | [5] places "1-3-5" | [6] school+team2 (with school link) | [7] burgee2

CSS classes on cells [2]/[3] and [5]/[6]:
  tr-win/tr-lose indicate which team won the matchup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from scraper.parsers._soup import ensure_soup


@dataclass
class RoundInfo:
    title: str  # e.g. "Round 1", "Final Four"
    relative_order: int  # sequential within the regatta


@dataclass
class TeamRaceResult:
    race_number: int
    round_order: int  # maps to RoundInfo.relative_order
    team1_school_url: str
    team1_team_name: str  # team mascot e.g. "Bears"
    team1_earned: list[int]  # earned positions e.g. [2, 4, 6] — physical finish per division
    team1_won: bool
    team1_penalties: list[str]  # per-division penalties, e.g. ["DSQ", "", "DNF"]
    team2_school_url: str
    team2_team_name: str
    team2_earned: list[int]
    team2_won: bool
    team2_penalties: list[str]  # per-division penalties, e.g. ["", "", "DNS"]


def parse(html: str | BeautifulSoup) -> tuple[list[RoundInfo], list[TeamRaceResult]]:
    """Parse the team-racing /all/ page into (rounds, race_results).

    rounds carries the round headers in display order; race_results is one
    entry per individual match (both teams, their earned places, win flags).
    """
    soup = ensure_soup(html)
    table = soup.find("table", class_="teamscorelist")
    if table is None:
        return [], []

    rounds: list[RoundInfo] = []
    results: list[TeamRaceResult] = []
    current_round_order = 0
    seen_titles: dict[str, int] = {}  # title -> relative_order

    for row in table.find_all("tr"):
        row_classes = set(row.get("class") or [])

        if "roundrow" in row_classes:
            title = row.get_text(strip=True)
            if title in seen_titles:
                # Reuse order for repeated round headers (e.g. "Round 1"
                # appears once per matchup group in round-robin formats)
                current_round_order = seen_titles[title]
            else:
                current_round_order += 1
                seen_titles[title] = current_round_order
                rounds.append(RoundInfo(title=title, relative_order=current_round_order))
            continue

        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        # Cell [0] = race number
        race_num_text = cells[0].get_text(strip=True)
        if not race_num_text.isdigit():
            continue

        race_number = int(race_num_text)

        # Team 1: cells [2] (name) and [3] (places)
        team1_school_url, team1_team_name = _parse_team_cell(cells[2])
        team1_earned, team1_penalties = _parse_places(cells[3].get_text(strip=True))
        team1_won = "tr-win" in (cells[2].get("class") or [])

        # Team 2: cells [5] (places) and [6] (name)
        team2_school_url, team2_team_name = _parse_team_cell(cells[6])
        team2_earned, team2_penalties = _parse_places(cells[5].get_text(strip=True))
        team2_won = "tr-win" in (cells[6].get("class") or [])

        results.append(
            TeamRaceResult(
                race_number=race_number,
                round_order=current_round_order,
                team1_school_url=team1_school_url,
                team1_team_name=team1_team_name,
                team1_earned=team1_earned,
                team1_won=team1_won,
                team1_penalties=team1_penalties,
                team2_school_url=team2_school_url,
                team2_team_name=team2_team_name,
                team2_earned=team2_earned,
                team2_won=team2_won,
                team2_penalties=team2_penalties,
            )
        )

    return rounds, results


def _parse_team_cell(cell: Tag) -> tuple[str, str]:
    """Extract (school_url, team_name) from a team name cell.

    Cell structure: <a href="/schools/coast-guard/s25/">U. S. Coast Guard Academy</a> Bears
    """
    school_url = ""
    a = cell.find("a", href=re.compile(r"^/schools/"))
    if a:
        school_url = a.get("href", "")

    # Team name is the text after the school link
    strings = list(cell.stripped_strings)
    # Last string is typically the team name (e.g. "Bears")
    # First string is the school name from the link
    if len(strings) >= 2:
        return school_url, strings[-1]
    elif len(strings) == 1:
        return school_url, strings[0]
    return school_url, ""


def _parse_places(text: str) -> tuple[list[int], list[str]]:
    """Parse places and per-division penalties from the /all/ page.

    Techscore's Finish::displayPlaces() (Finish.php) iterates boats sorted by
    earned position and appends modifier types only for penalized boats.  The
    output order of penalty codes does NOT correspond to division order — we
    cannot tell from the string alone which division each penalty belongs to.

    Therefore we broadcast each penalty code to ALL divisions so that every
    division's finish gets a finish_modifier row.  The penalty table
    (_process_penalties) later enriches them with the correct amount/comments.

    Examples:
      '2-4-6'             → ([2, 4, 6], ['', '', ''])
      '1-3-6 RAF'         → ([1, 3, 6], ['RAF', 'RAF', 'RAF'])
      '4-5-6 DNS,DNS,DNS' → ([4, 5, 6], ['DNS', 'DNS', 'DNS'])
      '1-3-6 DSQ,DNF'     → ([1, 3, 6], ['DSQ', 'DSQ', 'DSQ'])  — use first code
    """
    parts = text.split()
    if not parts:
        return [], []
    nums = parts[0]
    places = []
    for p in nums.split("-"):
        try:
            places.append(int(p))
        except ValueError:
            pass

    # Extract the first penalty code and broadcast to all divisions.
    # We use the first code because mixed-type penalties (e.g. "DSQ,DNF") are
    # rare and the penalty table will provide per-finish detail when available.
    penalty = ""
    if len(parts) > 1:
        penalty = parts[1].split(",")[0]
    penalties = [penalty] * len(places) if penalty else [""] * len(places)

    return places, penalties
