"""
Parse a regatta sailors/RP page, e.g. /s25/some-regatta/sailors/

Table class: "coordinate sailors"
Headers: School, Team, Div., Rank, Skipper, Races, Crew, Races

Each team has multiple rows (one per division, possibly multiple skippers/crews).
School and Team cells use rowspan across all their rows.

Extracts:
  - Sailor name + URL (links to /sailors/{slug}/)
  - Their role (skipper / crew)
  - Which races they sailed (from the "Races" cell; empty = all races)
  - Their school and team
"""

from __future__ import annotations
from dataclasses import dataclass
import re

from bs4 import BeautifulSoup, Tag

from scraper.parsers._soup import ensure_soup


@dataclass
class RpEntry:
    school_name: str
    school_url: str    # e.g. "/schools/boston-college/f25/"
    team_name: str
    division: str
    rank: int | None
    sailor_name: str
    sailor_url: str    # e.g. "/sailors/john-doe/"
    boat_role: str     # "skipper" or "crew"
    races: str         # race range string e.g. "1-3,5" or "" (all races)


@dataclass
class ReserveEntry:
    school_name: str
    school_url: str
    team_name: str
    sailor_name: str
    sailor_url: str


def parse(html: str | BeautifulSoup) -> tuple[list[RpEntry], list[ReserveEntry]]:
    """
    Parse the sailors/RP page for a regatta.

    Returns:
        Tuple of (rp_entries, reserve_entries).
    """
    soup = ensure_soup(html)

    table = soup.find("table", class_=re.compile(r"coordinate\s+sailors"))
    if table is None:
        return [], []

    return _parse_table(table)


def _parse_table(table: Tag) -> tuple[list[RpEntry], list[ReserveEntry]]:
    """Walk the RP table, resolving rowspan-merged School/Team/Division cells.

    School and Team span all of a team's rows, and Division spans its
    skipper/crew rows, so a given <tr> may omit those leading cells. We track
    the "current" school/team/division/rank and decrement per-section rowspan
    counters to know which cells the present row actually carries.

    Returns (rp_entries, reserve_entries).
    """
    rows = list(table.find_all("tr"))
    entries: list[RpEntry] = []
    reserves: list[ReserveEntry] = []

    # Track current school/team/division/rank across rowspan cells
    current_school = ""
    current_school_url = ""
    current_team = ""
    current_division = ""
    current_rank: int | None = None

    school_rowspan = 0
    team_rowspan = 0
    div_rowspan = 0

    for row in rows[1:]:  # skip header
        cells = list(row.find_all("td"))
        if not cells:
            continue

        row_class = " ".join(row.get("class", []))

        # Determine column positions dynamically since rowspan shifts things
        col = 0

        # School cell (present only when rowspan starts)
        if school_rowspan <= 0:
            if col < len(cells):
                school_cell = cells[col]
                cell_classes = set(school_cell.get("class") or [])
                # Only treat as school cell if it has the schoolname class
                if "schoolname" in cell_classes:
                    school_a = school_cell.find("a")
                    if school_a:
                        current_school = school_a.get_text(strip=True)
                        current_school_url = school_a.get("href", "")
                    else:
                        current_school = school_cell.get_text(strip=True)
                        current_school_url = ""
                    rs = school_cell.get("rowspan", "1")
                    school_rowspan = int(rs)
                    col += 1
                else:
                    school_rowspan = 1  # treat as 1-row span so we try again next row
        school_rowspan -= 1

        # Team cell
        if team_rowspan <= 0:
            if col < len(cells):
                team_cell = cells[col]
                cell_classes = set(team_cell.get("class") or [])
                if "teamname" in cell_classes:
                    current_team = team_cell.get_text(strip=True)
                    rs = team_cell.get("rowspan", "1")
                    team_rowspan = int(rs)
                    col += 1
                else:
                    team_rowspan = 1
        team_rowspan -= 1

        # Extract reserves AFTER decrementing rowspans
        # (reserves-rows still consume a rowspan slot in the HTML table)
        if "reserves-row" in row_class:
            div_rowspan = max(0, div_rowspan - 1)
            for cell in cells:
                if "reserves-cell" not in (cell.get("class") or []):
                    continue
                for span in cell.find_all("span", class_="reserve-entry"):
                    name, url = _extract_sailor(span)
                    if name:
                        reserves.append(ReserveEntry(
                            school_name=current_school,
                            school_url=current_school_url,
                            team_name=current_team,
                            sailor_name=name,
                            sailor_url=url,
                        ))
            continue

        # Division cell (with rowspan tracking)
        if div_rowspan <= 0:
            div_cell = _get_cell(cells, col)
            if div_cell:
                cell_classes = set(div_cell.get("class") or [])
                div_text = div_cell.get_text(strip=True)
                if "division-cell" in cell_classes or re.match(r"^[A-D]$", div_text):
                    current_division = div_text
                    div_rowspan = int(div_cell.get("rowspan", "1"))
                    col += 1
                    # Rank cell immediately follows
                    rank_cell = _get_cell(cells, col)
                    if rank_cell:
                        cell_classes2 = set(rank_cell.get("class") or [])
                        if "rank-cell" in cell_classes2 or rank_cell.get_text(strip=True).isdigit():
                            try:
                                current_rank = int(rank_cell.get_text(strip=True))
                            except ValueError:
                                current_rank = None
                            col += 1
        div_rowspan -= 1

        # Skipper cell
        skipper_cell = _get_cell(cells, col)
        col += 1
        skipper_races_cell = _get_cell(cells, col)
        col += 1

        # Crew cell
        crew_cell = _get_cell(cells, col)
        col += 1
        crew_races_cell = _get_cell(cells, col)

        if skipper_cell:
            name, url = _extract_sailor(skipper_cell)
            if name:
                races = skipper_races_cell.get_text(strip=True) if skipper_races_cell else ""
                entries.append(RpEntry(
                    school_name=current_school,
                    school_url=current_school_url,
                    team_name=current_team,
                    division=current_division,
                    rank=current_rank,
                    sailor_name=name,
                    sailor_url=url,
                    boat_role="skipper",
                    races=races,
                ))

        if crew_cell:
            name, url = _extract_sailor(crew_cell)
            if name:
                races = crew_races_cell.get_text(strip=True) if crew_races_cell else ""
                entries.append(RpEntry(
                    school_name=current_school,
                    school_url=current_school_url,
                    team_name=current_team,
                    division=current_division,
                    rank=current_rank,
                    sailor_name=name,
                    sailor_url=url,
                    boat_role="crew",
                    races=races,
                ))

    return entries, reserves


def _get_cell(cells: list[Tag], index: int) -> Tag | None:
    if index < len(cells):
        return cells[index]
    return None


def _extract_sailor(cell: Tag) -> tuple[str, str]:
    """Return (name, url) from a sailor cell."""
    a = cell.find("a")
    if a:
        return a.get_text(strip=True), a.get("href", "")
    text = cell.get_text(strip=True)
    return (text, "") if text else ("", "")
