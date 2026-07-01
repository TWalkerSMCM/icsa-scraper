"""
Parse a team racing rotations page, e.g. /s26/some-team-race/rotations/

Source: techscore TeamRotationTable.php

The rotations page renders one or more <table class="tr-rotation-table">
elements (typically one per round). Each table contains race rows broken up
by "flight" separator rows. A flight is a grouping of races within a round
(typically races that sail together on the water). Flight numbers reset at
each new round.

HTML structure (per table):
    <table class="tr-rotation-table">
      <thead> ... </thead>
      <tbody>
        <tr class="tr-flight"><td colspan="N">Flight 1 (Round 1)</td></tr>
        <tr class="tr-sailed">                                # or plain <tr>
          <td>1</td>                                          # race number
          <td class="team1">...</td><td class="team1">...</td>
          <td class="sail team1">...</td>...
          <td class="vscell">vs</td>
          <td class="sail team2">...</td>...
          <td class="team2">...</td><td class="team2">...</td>
        </tr>
        ...
        <tr class="tr-flight"><td colspan="N">Flight 2</td></tr>     # same round
        ...
      </tbody>
    </table>

Flight header text follows two patterns:
    "Flight {N}"               — continuation in the current round
    "Flight {N} ({round})"     — first flight in a new round

This parser extracts only the flight assignment for each race
(race_num -> flight_number), which is the secondary grouping the iOS view
uses inside each round.  Sail numbers, colors, and per-division assignments
are intentionally not extracted here.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scraper.parsers._soup import ensure_soup

# Matches flight headers like "Flight 3"; capture group 1 is the flight number.
_FLIGHT_RE = re.compile(r"Flight\s+(\d+)", re.IGNORECASE)


def parse(html: str | BeautifulSoup) -> dict[int, int]:
    """Parse a rotations page and return a {race_num: flight_number} map.

    Flight numbers are taken verbatim from the HTML, which (per techscore)
    resets to 1 at each new round.  Races without a preceding flight header
    in their table are skipped — each table should always start with one.
    The page may contain multiple tr-rotation-table elements (one per round
    in grouped formats); each table maintains its own flight numbering.
    """
    soup = ensure_soup(html)
    tables = soup.find_all("table", class_="tr-rotation-table")
    if not tables:
        return {}

    flights: dict[int, int] = {}

    for table in tables:
        current_flight: int | None = None
        for row in table.find_all("tr"):
            row_classes = set(row.get("class") or [])

            if "tr-flight" in row_classes:
                text = row.get_text(strip=True)
                m = _FLIGHT_RE.search(text)
                if m:
                    current_flight = int(m.group(1))
                continue

            if current_flight is None:
                continue

            first_td = row.find("td")
            if first_td is None:
                continue

            race_num_text = first_td.get_text(strip=True)
            if not race_num_text.isdigit():
                continue

            flights[int(race_num_text)] = current_flight

    return flights


# Back-compat alias — descriptive name kept for existing call sites.
parse_flights = parse
