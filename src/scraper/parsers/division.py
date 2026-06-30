"""
Parse a regatta division scores page, e.g. /s25/some-regatta/A/

Extracts per-race finish positions for each team in the division.

Table class: "results coordinate division {A|B|C|D}"
Header: (tie), (rank), (burgee), Team, (penalty), Total, Sailors, "", ""
Then race columns: 1, 2, 3, ...

Each row has: tiebreaker, rank, burgee, team name, penalty, total, sailors, then race scores.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re

from bs4 import BeautifulSoup, Tag

from scraper.parsers._soup import ensure_soup, extract_number


@dataclass
class RaceFinish:
    race_num: int
    score: int | None     # penalized score (after penalties applied) — NOT the earned position.
                          # For clean finishes, score == earned. None if not parseable.
    modifier: str         # penalty code: "DNF", "DSQ", "OCS", etc. — empty if clean


@dataclass
class TeamDivisionResult:
    rank: int
    school_name: str
    team_name: str
    division: str
    total_score: int
    penalty: str          # team-level penalty if shown (MRP/PFD etc.)
    sailors: list[str]    # sailor names shown inline
    race_finishes: list[RaceFinish] = field(default_factory=list)
    school_slug: str = ""       # from <a href="/schools/navy/"> in team cell
    tiebreaker: str = ""        # symbol from cells[0] text
    tiebreaker_note: str = ""   # explanation from cells[0] title attribute


def parse(html: str | BeautifulSoup, division: str) -> list[TeamDivisionResult]:
    """
    Parse a division scores page.

    Args:
        html: HTML of the division page (raw string or pre-parsed soup).
        division: the division letter, e.g. "A".

    Returns:
        List of TeamDivisionResult, one per team.
    """
    soup = ensure_soup(html)

    # Table class is "results coordinate division A" (for div A)
    table = soup.find("table", class_=re.compile(rf"coordinate\s+division\s+{re.escape(division)}"))
    if table is None:
        # Fallback: any division table
        table = soup.find("table", class_=re.compile(r"coordinate\s+division"))
    if table is None:
        return []

    return _parse_table(table, division)


def _parse_table(table: Tag, division: str) -> list[TeamDivisionResult]:
    """Parse the results table into one TeamDivisionResult per team row.

    Reads the header to locate the team/total columns and the race columns,
    then per row extracts the team, total, sailors, and each race finish.
    """
    rows = list(table.find_all("tr"))
    if not rows:
        return []

    # Parse header row to find race number columns
    header = rows[0]
    headers = [th.get_text(strip=True) for th in header.find_all("th")]
    # headers: ["", rank, "", Team, penalty, "Total", "Sailors", "", "", 1, 2, 3, ...]
    race_col_start = None
    for i, h in enumerate(headers):
        if h.isdigit():
            race_col_start = i
            break

    race_nums = []
    if race_col_start is not None:
        for h in headers[race_col_start:]:
            if h.isdigit():
                race_nums.append(int(h))

    results: list[TeamDivisionResult] = []

    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        rank_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        if not rank_text.isdigit():
            continue

        rank = int(rank_text)

        # School/team name (cell 3 = team, no separate school on this page)
        team_cell = cells[3] if len(cells) > 3 else None
        team_text = team_cell.get_text(strip=True) if team_cell else ""
        # Team cell may contain "School - Team" or just team name
        school_name, team_name = _split_school_team(team_text)

        # School slug from the <a href="/schools/navy/"> link
        school_slug = ""
        if team_cell:
            school_link = team_cell.find("a", href=True)
            if school_link:
                m = re.search(r'/schools/([^/]+)/', school_link["href"])
                if m:
                    school_slug = m.group(1)

        penalty = cells[4].get_text(strip=True) if len(cells) > 4 else ""
        total_text = cells[5].get_text(strip=True) if len(cells) > 5 else ""
        try:
            total = int(total_text)
        except ValueError:
            total = 0

        sailors_cell = cells[6] if len(cells) > 6 else None
        sailors = _extract_sailors(sailors_cell) if sailors_cell else []

        # Tiebreaker info from cells[0] (the tiebreaker symbol column)
        tiebreaker = cells[0].get_text(strip=True)
        tiebreaker_note = cells[0].get("title", "").strip()

        race_finishes: list[RaceFinish] = []
        if race_col_start is not None:
            for i, race_num in enumerate(race_nums):
                col = race_col_start + i
                if col < len(cells):
                    cell = cells[col]
                    score, modifier = _parse_finish_cell(cell)
                    race_finishes.append(RaceFinish(
                        race_num=race_num,
                        score=score,
                        modifier=modifier,
                    ))

        results.append(TeamDivisionResult(
            rank=rank,
            school_name=school_name,
            team_name=team_name,
            division=division,
            total_score=total,
            penalty=penalty,
            sailors=sailors,
            race_finishes=race_finishes,
            school_slug=school_slug,
            tiebreaker=tiebreaker,
            tiebreaker_note=tiebreaker_note,
        ))

    return results


def _split_school_team(text: str) -> tuple[str, str]:
    """Split "School / Team" or "School - Team" into parts."""
    for sep in (" / ", " - ", "/"):
        if sep in text:
            parts = text.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return "", text.strip()


def _extract_sailors(cell: Tag) -> list[str]:
    """Extract sailor names from a cell (may contain <a> tags)."""
    names = []
    for a in cell.find_all("a"):
        name = a.get_text(strip=True)
        if name:
            names.append(name)
    if not names:
        text = cell.get_text(strip=True)
        if text:
            names = [n.strip() for n in re.split(r"[,/\n]", text) if n.strip()]
    return names


def _parse_finish_cell(cell: Tag) -> tuple[int | None, str]:
    """
    Parse a finish score cell.

    May contain: "3", "DNF", "DSQ/4", "BKD", etc.
    Returns (numeric_score_or_None, modifier_string).
    """
    title = cell.get("title", "")
    text = cell.get_text(strip=True)

    # Check for abbr element with penalty code
    abbr = cell.find("abbr")
    if abbr:
        modifier = abbr.get_text(strip=True)
        # The numeric score may be in title or adjacent text
        score = extract_number(title) or extract_number(text)
        return score, modifier

    # Plain number
    try:
        return int(text), ""
    except ValueError:
        pass

    # Something like "DNF" or "DSQ"
    if re.match(r"^[A-Z]+$", text):
        return None, text

    # "DNF/14" style
    m = re.match(r"^([A-Z]+)[/\s](\d+)$", text)
    if m:
        return int(m.group(2)), m.group(1)

    return None, text
