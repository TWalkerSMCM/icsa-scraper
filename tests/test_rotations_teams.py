"""Tests for scraper.parsers.rotations_teams — lightweight team slug extraction."""

from scraper.parsers.rotations_teams import parse_team_slugs


# ── Fleet racing rotation table (from RotationTable.php) ─────────────────────

FLEET_HTML = """
<html><body>
<h3>Division A</h3>
<table class="rotation">
  <thead><tr><th></th><th>Team</th><th>1A</th><th>2A</th></tr></thead>
  <tbody>
    <tr class="row0">
      <td class="burgee-cell"><img src="/burgees/navy.png" /></td>
      <td class="teamname"><a href="/schools/navy/s26/">Navy</a> Midshipmen</td>
      <td>1</td><td>2</td>
    </tr>
    <tr class="row1">
      <td class="burgee-cell"><img src="/burgees/mit/s26/" /></td>
      <td class="teamname"><a href="/schools/mit/s26/">MIT</a> Engineers</td>
      <td>2</td><td>1</td>
    </tr>
  </tbody>
</table>
<h3>Division B</h3>
<table class="rotation">
  <thead><tr><th></th><th>Team</th><th>1B</th><th>2B</th></tr></thead>
  <tbody>
    <tr class="row0">
      <td class="burgee-cell"></td>
      <td class="teamname"><a href="/schools/navy/s26/">Navy</a> Midshipmen</td>
      <td>1</td><td>2</td>
    </tr>
    <tr class="row1">
      <td class="burgee-cell"></td>
      <td class="teamname"><a href="/schools/mit/s26/">MIT</a> Engineers</td>
      <td>2</td><td>1</td>
    </tr>
  </tbody>
</table>
</body></html>
"""


def test_fleet_rotation_extracts_slugs():
    slugs = parse_team_slugs(FLEET_HTML)
    assert slugs == ["mit", "navy"]


def test_fleet_rotation_deduplicates_across_divisions():
    """Teams appear in every division table — should still be deduplicated."""
    slugs = parse_team_slugs(FLEET_HTML)
    assert len(slugs) == 2


# ── Team racing rotation table (from TeamRotationTable.php) ──────────────────

TEAM_HTML = """
<html><body>
<table class="tr-rotation-table">
  <thead><tr><th>#</th><th colspan="2">Team 1</th><th>Sails</th><th></th><th>Sails</th><th colspan="2">Team 2</th></tr></thead>
  <tbody>
    <tr class="tr-flight"><td colspan="8">Flight 1 (Round 1)</td></tr>
    <tr>
      <td>1</td>
      <td class="team1"><img src="/burgees/brown.png" /></td>
      <td class="team1"><a href="/schools/brown/s26/">Brown University</a> Bears</td>
      <td class="team1">1</td>
      <td class="vscell">vs</td>
      <td class="team2">2</td>
      <td class="team2"><a href="/schools/coast-guard/s26/">Coast Guard</a> Bears</td>
      <td class="team2"><img src="/burgees/coast-guard.png" /></td>
    </tr>
    <tr>
      <td>2</td>
      <td class="team1"><img src="/burgees/harvard.png" /></td>
      <td class="team1"><a href="/schools/harvard/s26/">Harvard</a> Crimson</td>
      <td class="team1">3</td>
      <td class="vscell">vs</td>
      <td class="team2">4</td>
      <td class="team2"><a href="/schools/tufts/s26/">Tufts</a> Jumbos</td>
      <td class="team2"><img src="/burgees/tufts.png" /></td>
    </tr>
  </tbody>
</table>
</body></html>
"""


def test_team_rotation_extracts_slugs():
    slugs = parse_team_slugs(TEAM_HTML)
    assert slugs == ["brown", "coast-guard", "harvard", "tufts"]


# ── Team racing with placeholders (no teams assigned yet) ────────────────────

TEAM_PLACEHOLDER_HTML = """
<html><body>
<table class="tr-rotation-table">
  <thead><tr><th>#</th><th colspan="2">Team 1</th><th></th><th colspan="2">Team 2</th></tr></thead>
  <tbody>
    <tr class="tr-flight"><td colspan="6">Flight 1</td></tr>
    <tr class="tr-incomplete">
      <td>1</td>
      <td class="team1"></td>
      <td class="team1"><em class="no-team">Team 1</em></td>
      <td class="vscell">vs</td>
      <td class="team2"><em class="no-team">Team 2</em></td>
      <td class="team2"></td>
    </tr>
  </tbody>
</table>
</body></html>
"""


def test_team_placeholder_returns_empty():
    slugs = parse_team_slugs(TEAM_PLACEHOLDER_HTML)
    assert slugs == []


# ── Empty / no rotation page ─────────────────────────────────────────────────

def test_empty_html_returns_empty():
    assert parse_team_slugs("") == []


def test_no_rotation_tables_returns_empty():
    assert parse_team_slugs("<html><body><p>No rotations</p></body></html>") == []


# ── Mixed: page with both fleet and team tables ─────────────────────────────

MIXED_HTML = """
<html><body>
<table class="rotation">
  <thead><tr><th></th><th>Team</th><th>1A</th></tr></thead>
  <tbody>
    <tr><td></td><td class="teamname"><a href="/schools/yale/s26/">Yale</a></td><td>1</td></tr>
  </tbody>
</table>
<table class="tr-rotation-table">
  <thead><tr><th>#</th><th colspan="2">Team 1</th><th></th><th colspan="2">Team 2</th></tr></thead>
  <tbody>
    <tr>
      <td>1</td>
      <td class="team1"></td>
      <td class="team1"><a href="/schools/yale/s26/">Yale</a></td>
      <td class="vscell">vs</td>
      <td class="team2"><a href="/schools/cornell/s26/">Cornell</a></td>
      <td class="team2"></td>
    </tr>
  </tbody>
</table>
</body></html>
"""


def test_mixed_tables_deduplicates():
    slugs = parse_team_slugs(MIXED_HTML)
    assert slugs == ["cornell", "yale"]
