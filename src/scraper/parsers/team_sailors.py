"""
Parse team racing /sailors/ page, e.g. /s25/some-team-race/sailors/

Produces per-round sailor assignment data for populating dt_rp.

Page structure:
  Per-round sections, each with <h3>Round Title</h3> followed by
  <table class="teamregistrations"> cross-table.

  Rows = teams, Columns = opponents.
  Each cell has a nested <table class="tr-boats"> with rows classed
  tr-boat-A, tr-boat-B, tr-boat-C — one per division.

  Each boat row: "Skipper Name 'YY<br/>Crew Name 'YY"
  Self-matchup cells have class "tr-ns" with text "X".
  Empty cells mean no sailors registered.
"""

from __future__ import annotations
from dataclasses import dataclass
import re

from bs4 import BeautifulSoup, Tag

from scraper.parsers._soup import ensure_soup


@dataclass
class BoatAssignment:
    """Sailor assignment for one boat (division) in one matchup."""
    division: str            # "A", "B", "C", "D"
    skipper_name: str        # e.g. "John O'Connell '28"
    crew_name: str           # e.g. "Isabel Walchli '28" or ""


@dataclass
class MatchupRP:
    """Sailor assignment for one team vs one opponent in one round."""
    round_title: str         # e.g. "Round 1", "Final Four"
    round_order: int         # sequential
    team_name: str           # row label, e.g. "Bentley Falcons"
    opponent_name: str       # column header, e.g. "Brown"
    boats: list[BoatAssignment]


def parse(html: str | BeautifulSoup) -> list[MatchupRP]:
    """Parse team racing sailors page → list of per-matchup sailor assignments."""
    soup = ensure_soup(html)

    results: list[MatchupRP] = []
    round_order = 0

    for table in soup.find_all("table", class_="teamregistrations"):
        round_order += 1

        # Round title from preceding <h3>
        h3 = table.find_previous("h3")
        round_title = h3.get_text(strip=True) if h3 else f"Round {round_order}"

        # Column headers = opponent names (skip pivot and any record columns)
        header_row = table.find("tr", class_="tr-cols")
        if not header_row:
            continue

        opponent_names: list[str] = []
        for th in header_row.find_all("th", class_="tr-vert-label"):
            opponent_names.append(th.get_text(strip=True))

        # Data rows
        for row in table.find_all("tr", class_="tr-row"):
            label_th = row.find("th", class_="tr-horiz-label")
            if not label_th:
                continue
            team_name = label_th.get_text(strip=True)

            cells = row.find_all("td")
            opp_idx = 0
            for cell in cells:
                cell_classes = set(cell.get("class") or [])

                if "tr-ns" in cell_classes:
                    # Self-matchup, skip
                    opp_idx += 1
                    continue

                if "tr-boattable" not in cell_classes:
                    # Record column or other non-matchup cell
                    continue

                if opp_idx >= len(opponent_names):
                    break

                opponent = opponent_names[opp_idx]
                boats = _parse_boat_table(cell)

                if boats:
                    results.append(MatchupRP(
                        round_title=round_title,
                        round_order=round_order,
                        team_name=team_name,
                        opponent_name=opponent,
                        boats=boats,
                    ))

                opp_idx += 1

    return results


def _parse_boat_table(cell: Tag) -> list[BoatAssignment]:
    """Extract boat assignments from a <table class="tr-boats"> nested in a cell."""
    boat_table = cell.find("table", class_="tr-boats")
    if not boat_table:
        return []

    boats: list[BoatAssignment] = []
    for tr in boat_table.find_all("tr"):
        tr_classes = set(tr.get("class") or [])

        # Determine division from class like "tr-boat-A"
        division = ""
        for cls in tr_classes:
            m = re.match(r"^tr-boat-([A-D])$", cls)
            if m:
                division = m.group(1)
                break

        if not division:
            continue

        td = tr.find("td")
        if not td:
            continue

        text = td.get_text(strip=True)
        if not text:
            continue

        # Names separated by <br/> — use stripped_strings to get them
        names = list(td.stripped_strings)
        skipper = names[0] if len(names) >= 1 else ""
        crew = names[1] if len(names) >= 2 else ""

        boats.append(BoatAssignment(
            division=division,
            skipper_name=skipper,
            crew_name=crew,
        ))

    return boats
