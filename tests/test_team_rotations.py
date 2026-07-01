"""Tests for scraper.parsers.team_rotations — flight assignment extraction."""

from scraper.parsers.team_rotations import parse_flights

SINGLE_TABLE_HTML = """
<html><body>
<table class="tr-rotation-table">
  <thead><tr><th>#</th><th colspan="2">Team 1</th><th>Sails</th><th></th><th>Sails</th><th colspan="2">Team 2</th></tr></thead>
  <tbody>
    <tr class="tr-flight"><td colspan="8">Flight 1 (Round 1)</td></tr>
    <tr class="tr-sailed"><td>1</td><td class="team1"></td><td class="team1"><a href="/schools/navy/s26/">Navy</a></td><td>vs</td><td class="team2"><a href="/schools/mit/s26/">MIT</a></td></tr>
    <tr class="tr-sailed"><td>2</td><td class="team1"></td><td class="team1"><a href="/schools/yale/s26/">Yale</a></td><td>vs</td><td class="team2"><a href="/schools/harvard/s26/">Harvard</a></td></tr>
    <tr class="tr-flight"><td colspan="8">Flight 2</td></tr>
    <tr class="tr-sailed"><td>3</td><td class="team1"></td><td class="team1"><a href="/schools/navy/s26/">Navy</a></td><td>vs</td><td class="team2"><a href="/schools/yale/s26/">Yale</a></td></tr>
    <tr><td>4</td><td class="team1"></td><td class="team1"><a href="/schools/mit/s26/">MIT</a></td><td>vs</td><td class="team2"><a href="/schools/harvard/s26/">Harvard</a></td></tr>
    <tr class="tr-flight"><td colspan="8">Flight 3</td></tr>
    <tr><td>5</td><td class="team1"></td><td class="team1"><a href="/schools/navy/s26/">Navy</a></td><td>vs</td><td class="team2"><a href="/schools/harvard/s26/">Harvard</a></td></tr>
    <tr><td>6</td><td class="team1"></td><td class="team1"><a href="/schools/yale/s26/">Yale</a></td><td>vs</td><td class="team2"><a href="/schools/mit/s26/">MIT</a></td></tr>
  </tbody>
</table>
</body></html>
"""


def test_parse_flights_groups_consecutive_races_under_flight_header():
    flights = parse_flights(SINGLE_TABLE_HTML)
    assert flights == {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3}


def test_parse_flights_handles_unsailed_rows():
    """Unsailed race rows (no tr-sailed class) should still be assigned a flight."""
    flights = parse_flights(SINGLE_TABLE_HTML)
    assert flights[4] == 2
    assert flights[5] == 3


# ── Multi-table: one tr-rotation-table per round, flights reset per table ───

MULTI_TABLE_HTML = """
<html><body>
<table class="tr-rotation-table">
  <tbody>
    <tr class="tr-flight"><td colspan="8">Flight 1 (Round 1)</td></tr>
    <tr><td>1</td><td class="team1"></td></tr>
    <tr><td>2</td><td class="team1"></td></tr>
    <tr class="tr-flight"><td colspan="8">Flight 2</td></tr>
    <tr><td>3</td><td class="team1"></td></tr>
  </tbody>
</table>
<table class="tr-rotation-table">
  <tbody>
    <tr class="tr-flight"><td colspan="8">Flight 1 (Round 2)</td></tr>
    <tr><td>4</td><td class="team1"></td></tr>
    <tr class="tr-flight"><td colspan="8">Flight 2</td></tr>
    <tr><td>5</td><td class="team1"></td></tr>
    <tr><td>6</td><td class="team1"></td></tr>
  </tbody>
</table>
</body></html>
"""


def test_parse_flights_resets_per_table():
    """Each tr-rotation-table is one round; flight numbering restarts at 1."""
    flights = parse_flights(MULTI_TABLE_HTML)
    assert flights == {1: 1, 2: 1, 3: 2, 4: 1, 5: 2, 6: 2}


# ── Grouped rounds: PHP renders one table for the whole round_group with ────
# ── monotonic flight numbering across rounds (e.g. Flight 4 (Round 2)).      ──

GROUPED_ROUND_HTML = """
<html><body>
<table class="tr-rotation-table">
  <tbody>
    <tr class="tr-flight"><td colspan="8">Flight 1 (Round 1)</td></tr>
    <tr><td>1</td><td class="team1"></td></tr>
    <tr><td>2</td><td class="team1"></td></tr>
    <tr class="tr-flight"><td colspan="8">Flight 2</td></tr>
    <tr><td>3</td><td class="team1"></td></tr>
    <tr class="tr-flight"><td colspan="8">Flight 3 (Round 2)</td></tr>
    <tr><td>4</td><td class="team1"></td></tr>
    <tr class="tr-flight"><td colspan="8">Flight 4</td></tr>
    <tr><td>5</td><td class="team1"></td></tr>
  </tbody>
</table>
</body></html>
"""


def test_grouped_rounds_keep_monotonic_flight_numbers():
    """When rounds share a round_group, PHP renders one table with monotonic
    flight numbers (e.g. Round 2 starts at Flight 3, not Flight 1).  We
    preserve that numbering verbatim — the iOS view groups by round name from
    /all/ and shows whatever flight numbers techscore rendered."""
    flights = parse_flights(GROUPED_ROUND_HTML)
    assert flights == {1: 1, 2: 1, 3: 2, 4: 3, 5: 4}


# ── tr-incomplete rows (placeholder team before seeding) ────────────────────


def test_tr_incomplete_rows_still_get_flight():
    html = """
<table class="tr-rotation-table"><tbody>
  <tr class="tr-flight"><td colspan="8">Flight 1 (Round 1)</td></tr>
  <tr class="tr-incomplete">
    <td>1</td>
    <td class="team1"></td>
    <td class="team1"><em class="no-team">Team 1</em></td>
    <td class="vscell">vs</td>
    <td class="team2"><em class="no-team">Team 2</em></td>
    <td class="team2"></td>
  </tr>
</tbody></table>
"""
    assert parse_flights(html) == {1: 1}


# ── Round name with parens of its own (defensive) ───────────────────────────


def test_flight_header_with_complex_round_name():
    """Round names can contain words like 'Final Four' or '(Group A)'.
    We only capture the flight number; the round name in the header is
    informational (we join by race_num, not round name)."""
    html = """
<table class="tr-rotation-table"><tbody>
  <tr class="tr-flight"><td colspan="8">Flight 1 (Final Four)</td></tr>
  <tr><td>10</td><td class="team1"></td></tr>
</tbody></table>
"""
    assert parse_flights(html) == {10: 1}


def test_race_before_flight_header_is_skipped():
    """A race row appearing before the first flight header should be skipped."""
    html = """
<table class="tr-rotation-table"><tbody>
  <tr><td>99</td><td class="team1"></td></tr>
  <tr class="tr-flight"><td colspan="8">Flight 1 (Round 1)</td></tr>
  <tr><td>1</td><td class="team1"></td></tr>
</tbody></table>
"""
    flights = parse_flights(html)
    assert 99 not in flights
    assert flights[1] == 1


# ── Edge cases ──────────────────────────────────────────────────────────────


def test_empty_html_returns_empty():
    assert parse_flights("") == {}


def test_no_rotation_table_returns_empty():
    assert parse_flights("<html><body><p>nothing</p></body></html>") == {}


def test_flight_header_without_number_is_ignored():
    """A malformed flight row without a recognizable number should not crash."""
    html = """
<table class="tr-rotation-table"><tbody>
  <tr class="tr-flight"><td>(broken header)</td></tr>
  <tr><td>1</td><td class="team1"></td></tr>
  <tr class="tr-flight"><td>Flight 2</td></tr>
  <tr><td>2</td><td class="team1"></td></tr>
</tbody></table>
"""
    flights = parse_flights(html)
    assert 1 not in flights
    assert flights == {2: 2}


def test_boat_cell_does_not_confuse_race_number_extraction():
    """When a boat-cell column is present, the race number is still in the first td."""
    html = """
<table class="tr-rotation-table"><tbody>
  <tr class="tr-flight"><td colspan="9">Flight 1 (Round 1)</td></tr>
  <tr>
    <td>1</td>
    <td class="boat-cell"><span class="boat">FJ</span></td>
    <td class="team1"></td>
  </tr>
</tbody></table>
"""
    assert parse_flights(html) == {1: 1}
