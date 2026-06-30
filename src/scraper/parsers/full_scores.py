"""
Parse a regatta full-scores page, e.g. /f25/some-regatta/full-scores/

Based on FullScoresTableCreator.php. Table class: "results coordinate".

Multi-division layout (one row per division per team + a totalrow):
  divA row:    tiebreaker | rank | school_nick | "A" | race1 … raceN | penalty | divA_total
  divB row:    ""         | ""   | team_name   | "B" | race1 … raceN | penalty | divB_total
  divC+ rows:  ""         | ""   | ""          | "C" | race1 … raceN | penalty | divC_total
  totalrow:    ""         | ""   | burgee      | ""  | cum1  … cumN  | penalty | grand_total  ← SKIP

Single-division layout (one row per team + a totalrow):
  row:      tiebreaker | rank | "team \\n school" | race1 … raceN | penalty | total
  totalrow: ""         | ""   | burgee            | cum1  … cumN  | ""      | grand_total  ← SKIP

Row class tells us the division: "divA" → "A", "divB" → "B", etc.
totalrow class → skip entirely.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re

from bs4 import BeautifulSoup, Tag

from scraper.parsers._soup import ensure_soup, extract_number


@dataclass
class RaceScore:
    race_num: int
    score: int | None   # penalized score (after penalties applied) — NOT the earned position.
                        # For clean finishes, score == earned. For penalized finishes, this is
                        # the penalty points (e.g. fleet+1 for DNF). None if not parseable.
    modifier: str       # e.g. "DNF", "DSQ", "" if clean
    title: str = ""     # raw title attr from <td>, e.g. "(15, Fleet + 1) comment"


@dataclass
class TeamDivScore:
    school_name: str    # nick_name from divA row (or combined cell for singlehanded)
    school_url: str     # href from school link e.g. "/schools/brown/f25/"
    school_id: str      # extracted slug e.g. "brown"
    team_name: str      # from divB row (or combined cell for singlehanded)
    division: str       # "A", "B", "C", "D" — or "A" for singlehanded
    penalty: str        # team penalty code e.g. "MRP", "PFD", or ""
    race_scores: list[RaceScore] = field(default_factory=list)
    div_total: int = 0
    sailor_name: str = ""   # singlehanded only: sailor name from the cell
    sailor_url: str = ""    # singlehanded only: link to /sailors/{slug}/


@dataclass
class PenaltyEntry:
    school_url: str        # from team cell link
    team_name: str         # text after school link
    race_or_division: str  # "A4", "A", "3", "All"
    penalty_type: str      # "DSQ", "MRP", "Discretionary", etc.
    amount: str            # "14 points (Orig: 4)", "+20", "-0.5 wins"
    comments: str


def parse_penalties(html: str | BeautifulSoup) -> list[PenaltyEntry]:
    """
    Parse the penalty-table from a full-scores page.

    Returns one PenaltyEntry per row in the <table class="penalty-table">.
    """
    soup = ensure_soup(html)
    table = soup.find("table", class_=re.compile(r"\bpenalty-table\b"))
    if table is None:
        return []

    rows = list(table.find_all("tr"))
    results: list[PenaltyEntry] = []

    for row in rows[1:]:  # skip header
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        # Team cell: <span><a href="/schools/.../">School</a> TeamName</span>
        team_cell = cells[0]
        a = team_cell.find("a")
        school_url = a.get("href", "") if a else ""
        # Team name: full text minus the school link text
        full_text = team_cell.get_text(strip=True)
        school_text = a.get_text(strip=True) if a else ""
        team_name = full_text[len(school_text):].strip() if school_text else full_text

        race_or_division = cells[1].get_text(strip=True)
        penalty_type = cells[2].get_text(strip=True)
        amount = cells[3].get_text(strip=True)
        comments = cells[4].get_text(strip=True)

        results.append(PenaltyEntry(
            school_url=school_url,
            team_name=team_name,
            race_or_division=race_or_division,
            penalty_type=penalty_type,
            amount=amount,
            comments=comments,
        ))

    return results


def parse(html: str | BeautifulSoup) -> list[TeamDivScore]:
    """
    Parse the full-scores page.

    Returns one TeamDivScore per team-division combination.
    """
    soup = ensure_soup(html)
    table = soup.find("table", class_=re.compile(r"\bcoordinate\b"))
    if table is None:
        return []

    rows = list(table.find_all("tr"))
    if not rows:
        return []

    # Parse header to find race-number column positions
    header = rows[0]
    header_cells = header.find_all(["th", "td"])
    headers = [c.get_text(strip=True) for c in header_cells]
    # e.g. ['', '', 'Team', 'Div.', '1', '2', '3', '', 'TOT']
    # or   ['', '', 'Team',         '1', '2', '3', '', 'TOT']  (singlehanded)

    has_div_col = "Div." in headers
    race_col_map: dict[int, int] = {}  # race_num → col_index
    for i, h in enumerate(headers):
        if h.isdigit():
            race_col_map[int(h)] = i

    # Track school/team across the multi-row group
    current_school_name = ""
    current_school_url = ""
    current_team_name = ""

    results: list[TeamDivScore] = []

    for row in rows[1:]:
        row_classes = set(row.get("class") or [])

        # Skip the totalrow (cumulative sums row)
        if "totalrow" in row_classes:
            current_school_name = ""
            current_school_url = ""
            current_team_name = ""
            continue

        # Determine division from row class: "divA" → "A"
        division = ""
        for cls in row_classes:
            m = re.match(r"^div([A-D])$", cls)
            if m:
                division = m.group(1)
                break

        cells = list(row.find_all("td"))
        if not cells:
            continue

        current_sailor_name = ""
        current_sailor_url = ""

        if has_div_col:
            # Multi-division layout
            # col0=tiebreaker, col1=rank, col2=school_or_team_or_blank,
            # col3=division_letter, col4..N=race_scores, col-2=penalty, col-1=div_total
            name_cell = cells[2] if len(cells) > 2 else None
            div_cell  = cells[3] if len(cells) > 3 else None

            if name_cell:
                a = name_cell.find("a")
                text = name_cell.get_text(strip=True)
                if division == "A" and text:
                    current_school_name = text
                    current_school_url = a.get("href", "") if a else ""
                elif division == "B" and text:
                    current_team_name = text
                # Div C+ rows have blank name cell

            # Re-read division from the div cell text if class wasn't set
            if not division and div_cell:
                d = div_cell.get_text(strip=True)
                if re.match(r"^[A-D]$", d):
                    division = d

        else:
            # Single-division layout (including singlehanded)
            # col0=tiebreaker, col1=rank, col2="sailor\nschool", col3..N=race_scores
            # Cell structure: <span class="singlehanded-sailor-span"><a href="/sailors/...">Name</a></span>
            #                 <br/><a href="/schools/...">School</a>
            division = "A"
            name_cell = cells[2] if len(cells) > 2 else None
            current_sailor_name = ""
            current_sailor_url = ""
            if name_cell:
                # Check for singlehanded span (sailor link + school link)
                sh_span = name_cell.find("span", class_="singlehanded-sailor-span")
                if sh_span:
                    sailor_a = sh_span.find("a")
                    if sailor_a:
                        current_sailor_name = sailor_a.get_text(strip=True)
                        current_sailor_url = sailor_a.get("href", "")
                    # School link is outside the span
                    school_links = [a for a in name_cell.find_all("a")
                                    if a.get("href", "").startswith("/schools/")]
                    if school_links:
                        current_school_name = school_links[0].get_text(strip=True)
                        current_school_url = school_links[0].get("href", "")
                    current_team_name = current_sailor_name
                else:
                    a = name_cell.find("a")
                    texts = [t.strip() for t in name_cell.stripped_strings]
                    current_team_name = texts[0] if len(texts) > 0 else ""
                    current_school_name = texts[1] if len(texts) > 1 else ""
                    current_school_url = a.get("href", "") if a else ""

        # Race scores — skip cells that are part of the totalrow sum columns
        race_scores: list[RaceScore] = []
        for race_num, col_idx in race_col_map.items():
            if col_idx >= len(cells):
                continue
            cell = cells[col_idx]
            # Skip if this is a sum cell (totalrow already handled above,
            # but guard against stray sum classes)
            if "sum" in " ".join(cell.get("class") or []):
                continue
            score, modifier = _parse_score_cell(cell)
            title = cell.get("title", "").strip()
            race_scores.append(RaceScore(race_num=race_num, score=score, modifier=modifier, title=title))

        # Penalty cell is second-to-last; total is last
        # (PHP: penalty column before TOT column)
        penalty = ""
        if len(cells) >= 2:
            pen_text = cells[-2].get_text(strip=True)
            if re.match(r"^[A-Z]{2,}$", pen_text):
                penalty = pen_text

        # Division total is the last cell
        try:
            div_total = int(cells[-1].get_text(strip=True))
        except (ValueError, IndexError):
            div_total = 0

        results.append(TeamDivScore(
            school_name=current_school_name,
            school_url=current_school_url,
            school_id=_school_id(current_school_url),
            team_name=current_team_name,
            division=division,
            penalty=penalty,
            race_scores=sorted(race_scores, key=lambda r: r.race_num),
            div_total=div_total,
            sailor_name=current_sailor_name,
            sailor_url=current_sailor_url,
        ))

    return _propagate_team_names(results)


def _propagate_team_names(rows: list[TeamDivScore]) -> list[TeamDivScore]:
    """
    The PHP puts school nick_name on divA and team qualified name on divB.
    Walk the rows in order: when a group of consecutive rows shares the same
    school_url, fill the team_name across all of them from whichever row has it.
    """
    if not rows:
        return rows

    # Group consecutive rows by school_url, breaking on team boundaries.
    # A new team starts when:
    #   - school_url changes (different school), OR
    #   - school_name changes and both are non-empty (1-div multi-team:
    #     "Bears 1" then "Bears 2" from Coast Guard), OR
    #   - division resets to "A" for the same school (multi-div multi-team:
    #     Tennessee Volunteers divA/B then Tennessee Smokies divA/B)
    groups: list[list[TeamDivScore]] = []
    current_group: list[TeamDivScore] = [rows[0]]
    for row in rows[1:]:
        prev = current_group[-1]
        first = current_group[0]
        same_school = row.school_url == first.school_url
        name_changed = (row.school_name and first.school_name
                        and row.school_name != first.school_name)
        div_reset = (same_school and row.division == "A"
                     and prev.division in ("B", "C", "D"))
        if same_school and not name_changed and not div_reset:
            current_group.append(row)
        else:
            groups.append(current_group)
            current_group = [row]
    groups.append(current_group)

    for group in groups:
        # Find the team name (non-empty) within the group
        team_name = next((r.team_name for r in group if r.team_name), "")
        for row in group:
            if not row.team_name:
                row.team_name = team_name

    return rows


def _school_id(url: str) -> str:
    """Return the school slug from a /schools/{slug}/{season}/ URL, or ""."""
    m = re.match(r"^/schools/([^/]+)/[sfmw]\d{2}/$", url)
    return m.group(1) if m else ""


def _parse_score_cell(cell: Tag) -> tuple[int | None, str]:
    """Return (numeric_score, modifier). modifier is empty string if clean finish."""
    abbr = cell.find("abbr")
    if abbr:
        modifier = abbr.get_text(strip=True)
        score = _score_from_title(cell.get("title", "")) or extract_number(cell.get_text())
        return score, modifier

    text = cell.get_text(strip=True)
    if not text:
        return None, ""

    # Plain integer
    try:
        return int(text), ""
    except ValueError:
        pass

    # Penalty code alone, e.g. "OCS", "DNF".
    # Score is encoded in the title: "(25, Fleet + 1)" or "(6: average in division)"
    if re.match(r"^[A-Z]+$", text):
        score = _score_from_title(cell.get("title", ""))
        return score, text

    # "DNF/14" or "DSQ 14"
    m = re.match(r"^([A-Z]+)[/\s]?(\d+)$", text)
    if m:
        return int(m.group(2)), m.group(1)

    return None, text


def _score_from_title(title: str) -> int | None:
    """Extract leading integer from title like '(25, Fleet + 1)' or '(6: average)'."""
    m = re.match(r"\((\d+)", title.strip())
    return int(m.group(1)) if m else None
