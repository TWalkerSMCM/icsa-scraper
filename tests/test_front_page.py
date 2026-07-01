"""
Tests for scraper/live/front_page.py — active and upcoming regatta parsing.
"""

from scraper.live.front_page import parse_active_regattas, parse_upcoming_regattas

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ACTIVE_HTML = """
<html><body>
<div id="in-progress">
  <table class="season-summary">
    <tbody>
      <tr><td><a href="/s26/cactus-cup/">Cactus Cup</a></td></tr>
      <tr><td><a href="/s26/spring-open/">Spring Open</a></td></tr>
    </tbody>
  </table>
</div>
</body></html>
"""

UPCOMING_HTML = """
<html><body>
<table class="coming-regattas">
  <tbody>
    <tr>
      <td><a href="/s26/future-regatta/">Future Regatta</a></td>
      <td>Navy</td>
      <td>Coed</td>
      <td>2 Divisions</td>
      <td>04/05/2026 @ 10:00</td>
    </tr>
    <tr>
      <td><a href="/s26/team-event/">Team Event</a></td>
      <td>MIT</td>
      <td>Coed</td>
      <td>Team</td>
      <td>04/12/2026 @ 09:00</td>
    </tr>
  </tbody>
</table>
</body></html>
"""

EMPTY_HTML = "<html><body><p>No regattas</p></body></html>"


# ---------------------------------------------------------------------------
# parse_active_regattas
# ---------------------------------------------------------------------------


def test_parse_active_regattas_basic():
    entries = parse_active_regattas(ACTIVE_HTML)
    assert len(entries) == 2
    assert entries[0].slug == "cactus-cup"
    assert entries[0].season == "s26"
    assert entries[0].status == "in_progress"
    assert entries[1].slug == "spring-open"


def test_parse_active_regattas_empty():
    entries = parse_active_regattas(EMPTY_HTML)
    assert entries == []


def test_parse_active_regattas_name():
    entries = parse_active_regattas(ACTIVE_HTML)
    assert entries[0].name == "Cactus Cup"


# ---------------------------------------------------------------------------
# parse_upcoming_regattas
# ---------------------------------------------------------------------------


def test_parse_upcoming_regattas_basic():
    entries = parse_upcoming_regattas(UPCOMING_HTML)
    assert len(entries) == 2
    assert entries[0].slug == "future-regatta"
    assert entries[0].status == "upcoming"
    assert entries[0].host == "Navy"
    assert entries[0].regatta_start == "2026-04-05"
    assert entries[0].scoring_type == "divisional"


def test_parse_upcoming_regattas_team_type():
    entries = parse_upcoming_regattas(UPCOMING_HTML)
    assert entries[1].slug == "team-event"
    assert entries[1].scoring_type == "team"
    assert entries[1].regatta_start == "2026-04-12"


def test_parse_upcoming_regattas_empty():
    entries = parse_upcoming_regattas(EMPTY_HTML)
    assert entries == []
