"""
Parse a regatta main page, e.g. /s25/some-regatta/

Sub-pages that exist per regatta type (from Techscore source):
  Standard + multi-division:  /A/ /B/ ... /full-scores/ /sailors/
  Standard + singlehanded:    /full-scores/  (no /A/, no /sailors/)
  Combined:                   /divisions/ /full-scores/ /sailors/
  Team racing:                /all/ /full-scores/ /sailors/ /rotations/

Strategy: parse the nav links actually present on the page — ground truth,
no inference needed.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re

from bs4 import BeautifulSoup, Tag

from scraper.parsers import metadata
from scraper.parsers._soup import ensure_soup


@dataclass
class TeamScore:
    rank: int
    school_name: str
    school_url: str        # e.g. "/schools/mit/s25/"
    team_name: str
    division_scores: dict  # {"A": 12, "B": 8, ...}
    division_penalties: dict  # {"A": "MRP", ...}
    total: int
    wins: int = 0          # team racing only
    losses: int = 0        # team racing only
    tiebreaker: str = ""         # symbol, e.g. "*"
    tiebreaker_note: str = ""    # title text, e.g. "Head-to-head record (1-0)"


@dataclass
class RegattaMeta:
    name: str
    season: str            # e.g. "s25"
    nick: str              # URL slug
    scoring: str           # "standard" | "combined" | "team"
    participant: str       # "coed" | "women"
    status: str
    hosts: list[str]
    start_time: str = ""   # ISO 8601 e.g. "2025-10-25T10:00-04:00"
    end_date: str = ""     # ISO date e.g. "2025-10-26"
    boat: str = ""         # e.g. "FJ"
    type: str = ""         # e.g. "Conference Championship Regatta"
    team_scores: list[TeamScore] = field(default_factory=list)
    # Actual sub-pages linked in nav — derived from page links, not inferred
    division_pages: list[str] = field(default_factory=list)  # e.g. ["/f25/r/A/", "/f25/r/B/"]
    has_combined_page: bool = False   # /divisions/ — combined scoring
    has_full_scores_page: bool = False
    has_sailors_page: bool = False
    has_all_races_page: bool = False  # /all/ — team racing
    sailor_links: dict[str, str] = field(default_factory=dict)  # display_name → profile_url


def parse(html: str | BeautifulSoup, season: str, nick: str) -> RegattaMeta:
    """Parse a regatta main page into a RegattaMeta.

    season/nick identify the regatta (e.g. "s25", "some-regatta") and are
    used to recognise its own sub-page links (/{season}/{nick}/A/, etc.).
    """
    soup = ensure_soup(html)
    base = f"/{season}/{nick}/"

    name = _extract_name(soup)
    scoring, participant = _extract_scoring_and_participant(soup)
    status = _extract_status(soup)
    hosts = _extract_hosts(soup)
    team_scores, _ = _extract_scores(soup)
    sailor_links = _extract_sailor_links(soup)
    start_time = _extract_start_time(soup)
    # End-date and page-info parsing live in metadata.py — reuse, don't duplicate.
    end_date = metadata.extract_end_date(soup)
    boat = metadata.page_info_value(soup, metadata.PAGE_INFO_BOAT)
    regatta_type = metadata.page_info_value(soup, metadata.PAGE_INFO_TYPE)

    # Ground-truth sub-pages: only what's actually linked in the nav
    div_pattern = re.compile(rf"^{re.escape(base)}([A-D])/$")
    division_pages = []
    for a in soup.find_all("a", href=div_pattern):
        if a["href"] not in division_pages:
            division_pages.append(a["href"])

    def linked(path: str) -> bool:
        return bool(soup.find("a", href=base + path))

    return RegattaMeta(
        name=name,
        season=season,
        nick=nick,
        scoring=scoring,
        participant=participant,
        status=status,
        hosts=hosts,
        start_time=start_time,
        end_date=end_date,
        boat=boat,
        type=regatta_type,
        team_scores=team_scores,
        sailor_links=sailor_links,
        division_pages=division_pages,
        has_combined_page=linked("divisions/"),
        has_full_scores_page=linked("full-scores/"),
        has_sailors_page=linked("sailors/"),
        has_all_races_page=linked("all/"),
    )


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_name(soup: BeautifulSoup) -> str:
    title = soup.find("title")
    if title:
        return title.get_text().split("|")[0].strip()
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def _extract_scoring_and_participant(soup: BeautifulSoup) -> tuple[str, str]:
    """Infer (scoring, participant) from body classes, nav links and headings.

    scoring is "standard" | "combined" | "team"; participant is "coed" | "women".
    The presence of a /divisions/ link implies combined scoring, /all/ implies
    team racing — these win over the weaker body-class hints.
    """
    scoring = "standard"
    participant = "coed"

    # Body class carries scoring/participant hints in some themes
    body = soup.find("body")
    cls = " ".join(body.get("class", [])) if body else ""
    if "team" in cls:
        scoring = "team"
    elif "combined" in cls:
        scoring = "combined"
    if "women" in cls:
        participant = "women"

    # Presence of /divisions/ link → combined; /all/ link → team
    if soup.find("a", href=re.compile(r"/divisions/$")):
        scoring = "combined"
    if soup.find("a", href=re.compile(r"/all/$")):
        scoring = "team"

    # Participant from page headings
    for h in soup.find_all(["h1", "h2", "h3"]):
        if "women" in h.get_text(strip=True).lower():
            participant = "women"
            break

    return scoring, participant


def _extract_status(soup: BeautifulSoup) -> str:
    """Return "final" | "finished" | "ready" | "unknown" from result headings."""
    for h in soup.find_all(["h2", "h3", "h4", "p"]):
        text = h.get_text(strip=True).lower()
        if "final results" in text:
            return "final"
        if "preliminary" in text:
            return "finished"
        if "no scores" in text:
            return "ready"
    return "unknown"


def _extract_start_time(soup: BeautifulSoup) -> str:
    """Return the ISO 8601 start time from the og:event:start_time meta tag."""
    meta = soup.find("meta", property="og:event:start_time")
    if meta and meta.get("content"):
        return meta["content"]
    return ""


def _extract_hosts(soup: BeautifulSoup) -> list[str]:
    """Return host school names from /schools/{slug}/{season}/ links, de-duped."""
    hosts = []
    for a in soup.find_all("a", href=re.compile(r"^/schools/[^/]+/[sfmw]\d{2}/$")):
        name = a.get_text(strip=True)
        if name and name not in hosts:
            hosts.append(name)
    return hosts


def _extract_scores(soup: BeautifulSoup) -> tuple[list[TeamScore], list[str]]:
    """Return (team_scores, divisions) from whichever summary table is present.

    Prefers the fleet-racing "coordinate divisional" table; falls back to the
    team-racing "results" ranking table (which has no divisions).
    """
    # Fleet racing summary table
    table = soup.find("table", class_=re.compile(r"coordinate\s+divisional"))
    if table:
        return _parse_fleet_table(table)
    # Team racing ranking table
    table = soup.find("table", class_=re.compile(r"\bresults\b"))
    if table:
        return parse_team_ranking_table(table), []
    return [], []


def _parse_fleet_table(table: Tag) -> tuple[list[TeamScore], list[str]]:
    """Parse the fleet-racing summary table into (team_scores, divisions).

    Division columns are discovered from single-letter (A-D) headers; each
    division contributes a score column immediately followed by a penalty
    column. The final column is the grand total.
    """
    rows = table.find_all("tr")
    if not rows:
        return [], []

    headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
    divisions = []
    div_indices = {}
    for i, h in enumerate(headers):
        if re.match(r"^[A-D]$", h):
            divisions.append(h)
            div_indices[h] = i

    scores: list[TeamScore] = []
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue
        rank_text = cells[1].get_text(strip=True)
        if not rank_text.isdigit():
            continue

        school_cell = cells[3]
        school_a = school_cell.find("a")
        school_name = school_a.get_text(strip=True) if school_a else school_cell.get_text(strip=True)
        school_url = school_a.get("href", "") if school_a else ""

        team_name = cells[4].get_text(strip=True)

        div_scores, div_penalties = {}, {}
        for div, col in div_indices.items():
            if col < len(cells):
                try:
                    div_scores[div] = int(cells[col].get_text(strip=True))
                except ValueError:
                    pass
            if col + 1 < len(cells):
                pen = cells[col + 1].get_text(strip=True)
                if pen:
                    div_penalties[div] = pen

        try:
            total = int(cells[-1].get_text(strip=True))
        except ValueError:
            total = sum(div_scores.values())

        scores.append(TeamScore(
            rank=int(rank_text),
            school_name=school_name,
            school_url=school_url,
            team_name=team_name,
            division_scores=div_scores,
            division_penalties=div_penalties,
            total=total,
        ))
    return scores, divisions


def parse_team_ranking_table(table: Tag) -> list[TeamScore]:
    """Parse a teamranking table element.

    Column layout (from TeamSummaryRankingTableCreator.php):
      [0]=tiebreaker, [1]=rank, [2]=burgee, [3]=school, [4]=team, [5]=record, [6]=%
    """
    scores: list[TeamScore] = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue
        rank_text = cells[1].get_text(strip=True)
        if not rank_text.isdigit():
            continue
        school_cell = cells[3]
        school_a = school_cell.find("a")
        school_name = school_a.get_text(strip=True) if school_a else school_cell.get_text(strip=True)
        school_url = school_a.get("href", "") if school_a else ""
        team_name = cells[4].get_text(strip=True) if len(cells) > 4 else ""

        # Parse W/L record from "Rec." column (format "9/1" or "9/1/0")
        wins, losses = 0, 0
        if len(cells) > 5:
            rec = cells[5].get_text(strip=True)
            m = re.match(r"^(\d+)/(\d+)", rec)
            if m:
                wins, losses = int(m.group(1)), int(m.group(2))

        scores.append(TeamScore(
            rank=int(rank_text),
            school_name=school_name,
            school_url=school_url,
            team_name=team_name,
            division_scores={},
            division_penalties={},
            total=0,
            wins=wins,
            losses=losses,
            tiebreaker=cells[0].get_text(strip=True),
            tiebreaker_note=cells[0].get("title", "").strip(),
        ))
    return scores


def _extract_sailor_links(soup: BeautifulSoup) -> dict[str, str]:
    """Extract sailor display_name → profile_url from ranking table.

    Team racing ranking tables have 'Skippers' and 'Crews' columns with
    <a href="/sailors/slug/"> links.  This gives us the canonical sailor ID
    for every sailor at the regatta, which we can cross-reference against
    plain-text names on the /sailors/ teamregistrations page.
    """
    links: dict[str, str] = {}
    for a in soup.find_all("a", href=re.compile(r"^/sailors/[^/]+/$")):
        name = a.get_text(strip=True)
        url = a["href"]
        if name:
            links[name] = url
    return links
