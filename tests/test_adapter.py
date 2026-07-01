"""
Tests for scraper/adapter.py — verify that techscore parsers + adapter produce
correct RegattaScores / TeamRegattaScores output.
"""

from bs4 import BeautifulSoup

from html_fixtures import (
    date_block,
    full_scores_1div,
    full_scores_2div,
    team_all_scores,
    totalrow,
)
from scraper.adapter import build_fleet_scores, build_team_scores
from scraper.parsers import full_scores as ts_full_scores
from scraper.parsers import team_all_races as ts_team
from scraper.parsers.metadata import extract as extract_metadata
from scraper.parsers.regatta import TeamScore as TeamRankingScore

# ---------------------------------------------------------------------------
# Shared metadata tests
# ---------------------------------------------------------------------------


def _soup(html):
    return BeautifulSoup(html, "lxml")


def test_metadata_name():
    html = full_scores_1div(
        [
            {
                "place": 1,
                "school": "Navy",
                "school_url": "/schools/navy/s26/",
                "team_name": "Midshipmen",
                "race_scores": [1],
                "div_total": 1,
                "sum_total": 1,
            },
        ]
    )
    assert extract_metadata(_soup(html)).name == "Test 1-Div Regatta"


def test_metadata_host():
    html = full_scores_1div(
        [
            {
                "place": 1,
                "school": "Navy",
                "school_url": "/schools/navy/s26/",
                "team_name": "Midshipmen",
                "race_scores": [1],
                "div_total": 1,
                "sum_total": 1,
            },
        ]
    )
    assert extract_metadata(_soup(html)).host == "Navy"


def test_metadata_dates():
    html = full_scores_1div(
        [
            {
                "place": 1,
                "school": "Navy",
                "school_url": "/schools/navy/s26/",
                "team_name": "Midshipmen",
                "race_scores": [1],
                "div_total": 1,
                "sum_total": 1,
            },
        ]
    )
    meta = extract_metadata(_soup(html))
    assert meta.regatta_start == "2026-03-06"
    assert meta.regatta_end == "2026-03-08"


def test_metadata_no_date():
    meta = extract_metadata(_soup("<html><body></body></html>"))
    assert meta.regatta_start == ""
    assert meta.regatta_end == ""


def test_metadata_scoring_type_combined():
    """Combined scoring type should be extracted correctly from page-info metadata."""
    html = """<html><body>
    <h1>Combined Regatta</h1>
    <ul id="page-info">
      <li><span class="page-info-key">Scoring</span><span class="page-info-value">Combined</span></li>
    </ul>
    </body></html>"""
    meta = extract_metadata(_soup(html))
    assert meta.scoring_type == "combined"


def test_metadata_scoring_type_divisional():
    """2-division scoring should be extracted as divisional."""
    html = """<html><body>
    <h1>Fleet Regatta</h1>
    <ul id="page-info">
      <li><span class="page-info-key">Scoring</span><span class="page-info-value">2 Divisions</span></li>
    </ul>
    </body></html>"""
    meta = extract_metadata(_soup(html))
    assert meta.scoring_type == "divisional"


def test_metadata_scoring_type_team():
    """Team scoring should be extracted correctly."""
    html = """<html><body>
    <h1>Team Regatta</h1>
    <ul id="page-info">
      <li><span class="page-info-key">Scoring</span><span class="page-info-value">Team Racing</span></li>
    </ul>
    </body></html>"""
    meta = extract_metadata(_soup(html))
    assert meta.scoring_type == "team"


# ---------------------------------------------------------------------------
# Fleet racing — 1-division tests
# ---------------------------------------------------------------------------


def test_fleet_1div_basic():
    teams_data = [
        {
            "place": 1,
            "school": "Navy",
            "school_url": "/schools/navy/s26/",
            "team_name": "Midshipmen",
            "race_scores": [1, 2, 3],
            "div_total": 6,
            "sum_total": 6,
        },
        {
            "place": 2,
            "school": "MIT",
            "school_url": "/schools/mit/s26/",
            "team_name": "Engineers",
            "race_scores": [2, 1, 4],
            "div_total": 7,
            "sum_total": 7,
        },
        {
            "place": 3,
            "school": "Harvard",
            "school_url": "/schools/harvard/s26/",
            "team_name": "Crimson",
            "race_scores": [3, 4, 2],
            "div_total": 9,
            "sum_total": 9,
        },
    ]
    html = full_scores_1div(teams_data)
    result = build_fleet_scores(html, "s26", "test", ts_full_scores.parse(html))

    assert len(result.teams) == 3
    assert result.teams[0].place == 1
    assert result.teams[0].school == "Navy"
    assert result.teams[0].school_slug == "navy"
    assert result.teams[0].team_name == "Midshipmen"
    assert result.teams[0].total == 6
    assert "A" in result.teams[0].divisions
    assert result.teams[0].divisions["A"].total == 6
    assert len(result.teams[0].divisions["A"].races) == 3
    assert result.races_sailed == {"A": 3}
    assert result.name == "Test 1-Div Regatta"
    assert result.host == "Navy"
    assert result.regatta_start == "2026-03-06"


def test_fleet_1div_multi_team_same_school():
    """J70-style: two entries from the same school should produce separate teams
    with correct per-team places (not per-school overwrite)."""
    teams_data = [
        {
            "place": 1,
            "school": "Coast Guard",
            "school_url": "/schools/coast-guard/s26/",
            "team_name": "Bears 1",
            "race_scores": [2, 1, 3],
            "div_total": 6,
            "sum_total": 6,
        },
        {
            "place": 2,
            "school": "MIT",
            "school_url": "/schools/mit/s26/",
            "team_name": "Engineers",
            "race_scores": [1, 3, 4],
            "div_total": 8,
            "sum_total": 8,
        },
        {
            "place": 3,
            "school": "Coast Guard",
            "school_url": "/schools/coast-guard/s26/",
            "team_name": "Bears 2",
            "race_scores": [3, 4, 5],
            "div_total": 12,
            "sum_total": 12,
        },
    ]
    html = full_scores_1div(teams_data)
    result = build_fleet_scores(html, "s26", "test", ts_full_scores.parse(html))

    assert len(result.teams) == 3
    cg_teams = [t for t in result.teams if t.school_slug == "coast-guard"]
    assert len(cg_teams) == 2
    assert {t.team_name for t in cg_teams} == {"Bears 1", "Bears 2"}
    # Places must be per-team, not per-school
    bears1 = next(t for t in cg_teams if t.team_name == "Bears 1")
    bears2 = next(t for t in cg_teams if t.team_name == "Bears 2")
    assert bears1.place == 1
    assert bears1.total == 6
    assert bears2.place == 3
    assert bears2.total == 12
    # MIT separate
    mit = next(t for t in result.teams if t.school_slug == "mit")
    assert mit.place == 2
    assert mit.total == 8


def test_fleet_1div_tiebreaker():
    """Tiebreaker symbols and notes should be extracted per-team from the results table."""
    teams_data = [
        {
            "place": 1,
            "school": "Navy",
            "school_url": "/schools/navy/s26/",
            "team_name": "Midshipmen",
            "race_scores": [1, 2],
            "div_total": 3,
            "sum_total": 3,
            "tb_sym": "*",
            "tb_title": "Head-to-head record (1-0)",
        },
        {
            "place": 2,
            "school": "MIT",
            "school_url": "/schools/mit/s26/",
            "team_name": "Engineers",
            "race_scores": [2, 1],
            "div_total": 3,
            "sum_total": 3,
            "tb_sym": "*",
            "tb_title": "Head-to-head record (0-1)",
        },
    ]
    html = full_scores_1div(teams_data)
    result = build_fleet_scores(html, "s26", "test", ts_full_scores.parse(html))

    assert result.teams[0].tiebreaker == "*"
    assert result.teams[0].tiebreaker_note == "Head-to-head record (1-0)"
    assert result.teams[1].tiebreaker == "*"
    assert result.teams[1].tiebreaker_note == "Head-to-head record (0-1)"


# ---------------------------------------------------------------------------
# Fleet racing — 2-division tests
# ---------------------------------------------------------------------------


def test_fleet_2div_basic():
    teams_data = [
        {
            "place": 1,
            "school": "Navy",
            "school_url": "/schools/navy/s26/",
            "mascot": "Midshipmen",
            "a_scores": [1, 2],
            "a_total": 3,
            "b_scores": [2, 1],
            "b_total": 3,
            "sum_total": 6,
        },
        {
            "place": 2,
            "school": "MIT",
            "school_url": "/schools/mit/s26/",
            "mascot": "Engineers",
            "a_scores": [2, 1],
            "a_total": 3,
            "b_scores": [1, 3],
            "b_total": 4,
            "sum_total": 7,
        },
    ]
    html = full_scores_2div(teams_data)
    result = build_fleet_scores(html, "s26", "test", ts_full_scores.parse(html))

    assert len(result.teams) == 2
    assert result.teams[0].place == 1
    assert result.teams[0].team_name == "Midshipmen"
    assert set(result.teams[0].divisions.keys()) == {"A", "B"}
    assert result.teams[0].total == 6
    assert result.teams[1].total == 7
    assert result.races_sailed == {"A": 2, "B": 2}


def test_fleet_2div_multi_team_same_school():
    """TAG State-style: multiple teams from the same school in 2-div scoring.
    Each team should get its own correct place and team name."""
    teams_data = [
        {
            "place": 1,
            "school": "Tennessee",
            "school_url": "/schools/tennessee/s26/",
            "mascot": "Volunteers",
            "a_scores": [1, 2],
            "a_total": 3,
            "b_scores": [1, 2],
            "b_total": 3,
            "sum_total": 6,
        },
        {
            "place": 2,
            "school": "Vanderbilt",
            "school_url": "/schools/vanderbilt/s26/",
            "mascot": "Commodores",
            "a_scores": [2, 3],
            "a_total": 5,
            "b_scores": [3, 3],
            "b_total": 6,
            "sum_total": 11,
        },
        {
            "place": 3,
            "school": "Tennessee",
            "school_url": "/schools/tennessee/s26/",
            "mascot": "Smokies",
            "a_scores": [3, 1],
            "a_total": 4,
            "b_scores": [2, 4],
            "b_total": 6,
            "sum_total": 10,
        },
    ]
    html = full_scores_2div(teams_data)
    result = build_fleet_scores(html, "s26", "test", ts_full_scores.parse(html))

    assert len(result.teams) == 3
    tn_teams = [t for t in result.teams if t.school_slug == "tennessee"]
    assert len(tn_teams) == 2
    assert {t.team_name for t in tn_teams} == {"Volunteers", "Smokies"}
    # Places must be per-team
    vol = next(t for t in tn_teams if t.team_name == "Volunteers")
    smk = next(t for t in tn_teams if t.team_name == "Smokies")
    assert vol.place == 1
    assert vol.total == 6
    assert smk.place == 3
    assert smk.total == 10
    # Divisions should NOT be merged
    assert vol.divisions["A"].total == 3
    assert smk.divisions["A"].total == 4


def test_fleet_2div_tiebreaker():
    """Tiebreaker symbols from the results table should map per-team."""
    teams_data = [
        {
            "place": 1,
            "school": "Navy",
            "school_url": "/schools/navy/s26/",
            "mascot": "Midshipmen",
            "a_scores": [1, 2],
            "a_total": 3,
            "b_scores": [2, 1],
            "b_total": 3,
            "sum_total": 6,
            "tb_sym": "*",
            "tb_title": "Head-to-head record (1-0)",
        },
        {
            "place": 2,
            "school": "MIT",
            "school_url": "/schools/mit/s26/",
            "mascot": "Engineers",
            "a_scores": [2, 1],
            "a_total": 3,
            "b_scores": [1, 2],
            "b_total": 3,
            "sum_total": 6,
            "tb_sym": "*",
            "tb_title": "Head-to-head record (0-1)",
        },
    ]
    html = full_scores_2div(teams_data)
    result = build_fleet_scores(html, "s26", "test", ts_full_scores.parse(html))

    assert result.teams[0].tiebreaker == "*"
    assert result.teams[0].tiebreaker_note == "Head-to-head record (1-0)"
    assert result.teams[1].tiebreaker == "*"
    assert result.teams[1].tiebreaker_note == "Head-to-head record (0-1)"


def test_fleet_2div_multi_team_tiebreaker():
    """Tiebreakers should be per-team even when multiple teams share a school URL."""
    teams_data = [
        {
            "place": 1,
            "school": "Tennessee",
            "school_url": "/schools/tennessee/s26/",
            "mascot": "Volunteers",
            "a_scores": [1],
            "a_total": 1,
            "b_scores": [1],
            "b_total": 1,
            "sum_total": 2,
            "tb_sym": "*",
            "tb_title": "Head-to-head (1-0)",
        },
        {
            "place": 2,
            "school": "Tennessee",
            "school_url": "/schools/tennessee/s26/",
            "mascot": "Smokies",
            "a_scores": [2],
            "a_total": 2,
            "b_scores": [2],
            "b_total": 2,
            "sum_total": 4,
            "tb_sym": "",
            "tb_title": "",
        },
    ]
    html = full_scores_2div(teams_data)
    result = build_fleet_scores(html, "s26", "test", ts_full_scores.parse(html))

    vol = next(t for t in result.teams if t.team_name == "Volunteers")
    smk = next(t for t in result.teams if t.team_name == "Smokies")
    assert vol.tiebreaker == "*"
    assert smk.tiebreaker == ""


def test_fleet_division_ranks():
    teams_data = [
        {
            "place": 1,
            "school": "Navy",
            "school_url": "/schools/navy/s26/",
            "mascot": "Midshipmen",
            "a_scores": [1, 2],
            "a_total": 3,
            "b_scores": [2, 1],
            "b_total": 3,
            "sum_total": 6,
        },
        {
            "place": 2,
            "school": "MIT",
            "school_url": "/schools/mit/s26/",
            "mascot": "Engineers",
            "a_scores": [2, 1],
            "a_total": 3,
            "b_scores": [1, 3],
            "b_total": 4,
            "sum_total": 7,
        },
    ]
    html = full_scores_2div(teams_data)
    ranks = {"A": {"navy": 2, "mit": 1}, "B": {"navy": 1, "mit": 2}}
    result = build_fleet_scores(
        html, "s26", "test", ts_full_scores.parse(html), division_ranks=ranks
    )

    assert result.teams[0].divisions["A"].rank == 2
    assert result.teams[0].divisions["B"].rank == 1
    assert result.teams[1].divisions["A"].rank == 1


# ---------------------------------------------------------------------------
# Fleet racing — penalty / edge case tests
# ---------------------------------------------------------------------------


def test_fleet_penalty():
    header = "<th></th><th></th><th>Team</th><th>Div.</th><th>1</th><th>2</th><th>3</th><th></th><th>TOT</th>"
    cells = "<td></td><td>1</td>"
    cells += '<td>Midshipmen<br/><a href="/schools/navy/s26/">Navy</a></td>'
    cells += '<td class="strong">A</td>'
    cells += '<td class="right" title="(15, Fleet + 1)"><abbr>DNF</abbr></td>'
    cells += '<td class="right">2</td><td class="right">3</td>'
    cells += '<td></td><td class="right">20</td>'
    rows = f'<tr class="divA">{cells}</tr>' + totalrow(20)
    html = f"""<html><body>{date_block()}
<h1>Test Penalty</h1>
<table class="results coordinate">
  <thead><tr>{header}</tr></thead>
  <tbody>{rows}</tbody>
</table></body></html>"""

    result = build_fleet_scores(html, "s26", "test", ts_full_scores.parse(html))
    race1 = result.teams[0].divisions["A"].races[0]
    assert race1.penalty == "DNF"
    assert race1.penalty_formula == "Fleet + 1"
    assert race1.points == 15


def test_regression_b_fewer_races_than_a():
    """When division B has fewer races than A, the B total must not
    appear as a race score."""
    header = "<th></th><th></th><th>Team</th><th>Div.</th>"
    for rn in range(1, 6):
        header += f"<th>{rn}</th>"
    header += "<th></th><th>TOT</th>"

    a_cells = '<td></td><td>1</td><td><a href="/schools/navy/s26/">Navy</a></td>'
    a_cells += '<td class="strong">A</td>'
    for pts in [1, 2, 3, 4, 5]:
        a_cells += f'<td class="right">{pts}</td>'
    a_cells += '<td></td><td class="right">15</td>'

    b_cells = "<td></td><td></td><td>Midshipmen</td>"
    b_cells += '<td class="strong">B</td>'
    for pts in [2, 1, 4, 3]:
        b_cells += f'<td class="right">{pts}</td>'
    b_cells += '<td class="right"></td>'
    b_cells += '<td></td><td class="right">10</td>'

    rows = f'<tr class="divA">{a_cells}</tr>'
    rows += f'<tr class="divB">{b_cells}</tr>'
    rows += totalrow(25)

    html = f"""<html><body>{date_block()}
<h1>Test Fewer Races</h1>
<table class="results coordinate">
  <thead><tr>{header}</tr></thead>
  <tbody>{rows}</tbody>
</table></body></html>"""

    result = build_fleet_scores(html, "s26", "test", ts_full_scores.parse(html))
    a_races = result.teams[0].divisions["A"].races
    b_races = result.teams[0].divisions["B"].races

    assert len(a_races) == 5
    assert len(b_races) == 4
    assert all(r.points != 10 for r in b_races)
    assert result.teams[0].divisions["B"].total == 10


def test_regression_is_final_no_markers():
    html = """<html><body>
<h1>Test Team Regatta</h1>
<table class="teamscorelist"></table>
</body></html>"""
    assert extract_metadata(BeautifulSoup(html, "lxml")).is_final is False


def test_regression_is_final_preliminary():
    html = """<html><body>
<h1>Test Regatta</h1>
<p>Preliminary results. Last updated 5 min ago.</p>
</body></html>"""
    assert extract_metadata(BeautifulSoup(html, "lxml")).is_final is False


def test_regression_is_final_true():
    html = """<html><body>
<h1>Test Regatta</h1>
<h3>Final Results</h3>
</body></html>"""
    assert extract_metadata(BeautifulSoup(html, "lxml")).is_final is True


def test_regression_breakdown_colon_separator():
    """Breakdown averages use colon '(7: average in division)' not comma."""
    header = "<th></th><th></th><th>Team</th><th>Div.</th><th>1</th><th>2</th><th></th><th>TOT</th>"
    cells = "<td></td><td>1</td>"
    cells += '<td>Midshipmen<br/><a href="/schools/navy/s26/">Navy</a></td>'
    cells += '<td class="strong">A</td>'
    cells += '<td class="right" title="(7: average in division)"><abbr>BYE</abbr></td>'
    cells += '<td class="right">3</td>'
    cells += '<td></td><td class="right">10</td>'
    rows = f'<tr class="divA">{cells}</tr>' + totalrow(10)

    html = f"""<html><body>{date_block()}
<h1>Test Breakdown</h1>
<table class="results coordinate">
  <thead><tr>{header}</tr></thead>
  <tbody>{rows}</tbody>
</table></body></html>"""

    result = build_fleet_scores(html, "s26", "test", ts_full_scores.parse(html))
    race1 = result.teams[0].divisions["A"].races[0]
    assert race1.penalty == "BYE"
    assert race1.points == 7
    assert race1.penalty_formula == "average in division"


def test_regression_breakdown_comma_separator():
    """Standard penalty uses comma '(15, Fleet + 1)'."""
    header = "<th></th><th></th><th>Team</th><th>Div.</th><th>1</th><th></th><th>TOT</th>"
    cells = "<td></td><td>1</td>"
    cells += '<td>Midshipmen<br/><a href="/schools/navy/s26/">Navy</a></td>'
    cells += '<td class="strong">A</td>'
    cells += '<td class="right" title="(15, Fleet + 1)"><abbr>DNF</abbr></td>'
    cells += '<td></td><td class="right">15</td>'
    rows = f'<tr class="divA">{cells}</tr>' + totalrow(15)

    html = f"""<html><body>{date_block()}
<h1>Test Penalty</h1>
<table class="results coordinate">
  <thead><tr>{header}</tr></thead>
  <tbody>{rows}</tbody>
</table></body></html>"""

    result = build_fleet_scores(html, "s26", "test", ts_full_scores.parse(html))
    race1 = result.teams[0].divisions["A"].races[0]
    assert race1.penalty == "DNF"
    assert race1.points == 15
    assert race1.penalty_formula == "Fleet + 1"


# ---------------------------------------------------------------------------
# Team racing tests
# ---------------------------------------------------------------------------


def _std_team_rounds():
    return [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-3-5",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
                {
                    "race_num": 2,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "2-4-6",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "1-3-5",
                    "winner": 2,
                },
            ],
        }
    ]


def test_team_basic():
    html = team_all_scores(_std_team_rounds())
    ts_rounds, ts_results = ts_team.parse(html)
    result = build_team_scores(html, "s26", "test", ts_rounds, ts_results)

    assert len(result.teams) == 2
    assert result.name == "Test Team Regatta"
    assert result.host == "MIT"
    for team in result.teams:
        assert team.total_wins == 1
        assert team.total_losses == 1


def test_team_two_rounds():
    rounds_data = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-3-5",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
            ],
        },
        {
            "name": "Round 2",
            "races": [
                {
                    "race_num": 2,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "2-4-6",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "1-3-5",
                    "winner": 2,
                },
            ],
        },
    ]
    html = team_all_scores(rounds_data)
    ts_rounds, ts_results = ts_team.parse(html)
    result = build_team_scores(html, "s26", "test", ts_rounds, ts_results)

    for team in result.teams:
        assert len(team.rounds) == 2


def test_team_repeated_round_headers():
    """Round-robin formats repeat round headers for each matchup group.
    The parser must merge them so each team gets one round with all matches."""
    rounds_data = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-3-5",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
            ],
        },
        {
            "name": "Round 2",
            "races": [
                {
                    "race_num": 2,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "2-4-6",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "1-3-5",
                    "winner": 2,
                },
            ],
        },
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 3,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-2-5",
                    "school2": "Boston College",
                    "url2": "/schools/boston-college/s26/",
                    "mascot2": " Eagles",
                    "pos2": "3-4-6",
                    "winner": 1,
                },
            ],
        },
        {
            "name": "Round 2",
            "races": [
                {
                    "race_num": 4,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-3-4",
                    "school2": "Boston College",
                    "url2": "/schools/boston-college/s26/",
                    "mascot2": " Eagles",
                    "pos2": "2-5-6",
                    "winner": 1,
                },
            ],
        },
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 5,
                    "school1": "MIT",
                    "url1": "/schools/mit/s26/",
                    "mascot1": " Engineers",
                    "pos1": "2-3-6",
                    "school2": "Boston College",
                    "url2": "/schools/boston-college/s26/",
                    "mascot2": " Eagles",
                    "pos2": "1-4-5",
                    "winner": 2,
                },
            ],
        },
        {
            "name": "Round 2",
            "races": [
                {
                    "race_num": 6,
                    "school1": "MIT",
                    "url1": "/schools/mit/s26/",
                    "mascot1": " Engineers",
                    "pos1": "1-4-5",
                    "school2": "Boston College",
                    "url2": "/schools/boston-college/s26/",
                    "mascot2": " Eagles",
                    "pos2": "2-3-6",
                    "winner": 1,
                },
            ],
        },
    ]
    html = team_all_scores(rounds_data)
    ts_rounds, ts_results = ts_team.parse(html)

    assert len(ts_rounds) == 2
    result = build_team_scores(html, "s26", "test", ts_rounds, ts_results)
    navy = next(t for t in result.teams if t.school == "Navy")

    assert len(navy.rounds) == 2
    assert len(navy.rounds[0].matches) == 2
    assert len(navy.rounds[1].matches) == 2
    assert {m.opponent for m in navy.rounds[0].matches} == {"mit", "boston-college"}


def test_team_win_pct():
    rounds_data = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": i,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-3-5",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "2-4-6",
                    "winner": 1 if i <= 2 else 2,
                }
                for i in range(1, 4)
            ],
        }
    ]
    html = team_all_scores(rounds_data)
    ts_rounds, ts_results = ts_team.parse(html)
    result = build_team_scores(html, "s26", "test", ts_rounds, ts_results)

    navy = next(t for t in result.teams if t.school == "Navy")
    assert navy.total_wins == 2
    assert navy.total_losses == 1
    assert navy.place == 1
    assert abs(navy.win_pct - 2 / 3) < 0.001


def test_team_flights_attached_to_matches():
    """When a flights map is supplied, every match for that race carries its flight."""
    rounds_data = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-3-5",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
                {
                    "race_num": 2,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "2-4-6",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "1-3-5",
                    "winner": 2,
                },
            ],
        }
    ]
    html = team_all_scores(rounds_data)
    ts_rounds, ts_results = ts_team.parse(html)

    result = build_team_scores(
        html,
        "s26",
        "test",
        ts_rounds,
        ts_results,
        flights={1: 1, 2: 2},
    )

    for team in result.teams:
        flights = {m.race_num: m.flight for rnd in team.rounds for m in rnd.matches}
        assert flights == {1: 1, 2: 2}


def test_team_flights_omitted_defaults_to_zero():
    """Without a flights map, matches keep flight=0 (unknown)."""
    html = team_all_scores(_std_team_rounds())
    ts_rounds, ts_results = ts_team.parse(html)
    result = build_team_scores(html, "s26", "test", ts_rounds, ts_results)
    for team in result.teams:
        for rnd in team.rounds:
            for m in rnd.matches:
                assert m.flight == 0


def test_team_flights_partial_map_only_attaches_known_races():
    """Races missing from the flights map keep flight=0; others get their value."""
    rounds_data = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-3-5",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
                {
                    "race_num": 2,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "2-4-6",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "1-3-5",
                    "winner": 2,
                },
            ],
        }
    ]
    html = team_all_scores(rounds_data)
    ts_rounds, ts_results = ts_team.parse(html)
    result = build_team_scores(
        html,
        "s26",
        "test",
        ts_rounds,
        ts_results,
        flights={1: 3},
    )
    flights = {
        m.race_num: m.flight for team in result.teams for rnd in team.rounds for m in rnd.matches
    }
    assert flights[1] == 3
    assert flights[2] == 0


def test_team_multi_team_same_school():
    """Q1-style: multiple teams from the same school should produce separate entries
    with independent W/L records, not merge into one."""
    rounds_data = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Texas A&M",
                    "url1": "/schools/texas-am/s26/",
                    "mascot1": " Aggies 1",
                    "pos1": "1-3-5",
                    "school2": "Rice",
                    "url2": "/schools/rice/s26/",
                    "mascot2": " Owls",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
                {
                    "race_num": 2,
                    "school1": "Rice",
                    "url1": "/schools/rice/s26/",
                    "mascot1": " Owls",
                    "pos1": "1-3-5",
                    "school2": "Texas A&M",
                    "url2": "/schools/texas-am/s26/",
                    "mascot2": " Aggies 2",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
                {
                    "race_num": 3,
                    "school1": "Texas A&M",
                    "url1": "/schools/texas-am/s26/",
                    "mascot1": " Aggies 1",
                    "pos1": "1-2-5",
                    "school2": "Texas A&M",
                    "url2": "/schools/texas-am/s26/",
                    "mascot2": " Aggies 2",
                    "pos2": "3-4-6",
                    "winner": 1,
                },
            ],
        }
    ]
    html = team_all_scores(rounds_data, host="Texas A&M")
    ts_rounds, ts_results = ts_team.parse(html)
    result = build_team_scores(html, "s26", "test", ts_rounds, ts_results)

    assert len(result.teams) == 3
    am_teams = [t for t in result.teams if t.school_slug == "texas-am"]
    assert len(am_teams) == 2
    assert {t.team_name for t in am_teams} == {"Aggies 1", "Aggies 2"}
    a1 = next(t for t in am_teams if t.team_name == "Aggies 1")
    a2 = next(t for t in am_teams if t.team_name == "Aggies 2")
    assert a1.total_wins == 2 and a1.total_losses == 0
    assert a2.total_wins == 0 and a2.total_losses == 2


def test_team_multi_team_same_school_with_rankings():
    """Rankings should map correctly to multi-team-per-school entries."""
    rounds_data = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Texas A&M",
                    "url1": "/schools/texas-am/s26/",
                    "mascot1": " Aggies 1",
                    "pos1": "1-3-5",
                    "school2": "Rice",
                    "url2": "/schools/rice/s26/",
                    "mascot2": " Owls",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
                {
                    "race_num": 2,
                    "school1": "Rice",
                    "url1": "/schools/rice/s26/",
                    "mascot1": " Owls",
                    "pos1": "1-3-5",
                    "school2": "Texas A&M",
                    "url2": "/schools/texas-am/s26/",
                    "mascot2": " Aggies 2",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
            ],
        }
    ]
    html = team_all_scores(rounds_data, host="Texas A&M")
    ts_rounds, ts_results = ts_team.parse(html)
    rankings = [
        TeamRankingScore(
            rank=1,
            school_name="Texas A&M",
            school_url="/schools/texas-am/s26/",
            team_name="Aggies 1",
            division_scores={},
            division_penalties={},
            total=0,
        ),
        TeamRankingScore(
            rank=2,
            school_name="Rice",
            school_url="/schools/rice/s26/",
            team_name="Owls",
            division_scores={},
            division_penalties={},
            total=0,
        ),
        TeamRankingScore(
            rank=3,
            school_name="Texas A&M",
            school_url="/schools/texas-am/s26/",
            team_name="Aggies 2",
            division_scores={},
            division_penalties={},
            total=0,
        ),
    ]
    result = build_team_scores(html, "s26", "test", ts_rounds, ts_results, rankings=rankings)

    a1 = next(t for t in result.teams if t.team_name == "Aggies 1")
    rice = next(t for t in result.teams if t.team_name == "Owls")
    a2 = next(t for t in result.teams if t.team_name == "Aggies 2")
    assert a1.place == 1
    assert rice.place == 2
    assert a2.place == 3


# ---------------------------------------------------------------------------
# Team racing — ranking / tiebreaker tests
# ---------------------------------------------------------------------------


def _ranking(rank, school_name, school_url, tb="", tb_note=""):
    return TeamRankingScore(
        rank=rank,
        school_name=school_name,
        school_url=school_url,
        team_name="",
        division_scores={},
        division_penalties={},
        total=0,
        tiebreaker=tb,
        tiebreaker_note=tb_note,
    )


def test_team_ranking_from_full_scores():
    """Positions should come from the teamranking table, not win_pct sort."""
    rounds_data = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-3-5",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
                {
                    "race_num": 2,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-2-5",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "3-4-6",
                    "winner": 1,
                },
                {
                    "race_num": 3,
                    "school1": "Harvard",
                    "url1": "/schools/harvard/s26/",
                    "mascot1": " Crimson",
                    "pos1": "1-3-5",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
                {
                    "race_num": 4,
                    "school1": "Harvard",
                    "url1": "/schools/harvard/s26/",
                    "mascot1": " Crimson",
                    "pos1": "1-2-4",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "3-5-6",
                    "winner": 1,
                },
                {
                    "race_num": 5,
                    "school1": "Harvard",
                    "url1": "/schools/harvard/s26/",
                    "mascot1": " Crimson",
                    "pos1": "1-2-3",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "4-5-6",
                    "winner": 1,
                },
            ],
        }
    ]
    all_html = team_all_scores(rounds_data)
    rankings = [
        _ranking(1, "Harvard", "/schools/harvard/s26/"),
        _ranking(2, "Navy", "/schools/navy/s26/"),
        _ranking(3, "MIT", "/schools/mit/s26/"),
    ]

    ts_rounds, ts_results = ts_team.parse(all_html)
    result = build_team_scores(all_html, "s26", "test", ts_rounds, ts_results, rankings=rankings)

    assert result.teams[0].place == 1
    assert result.teams[0].school_slug == "harvard"
    assert result.teams[1].place == 2
    assert result.teams[1].school_slug == "navy"
    assert result.teams[2].place == 3
    assert result.teams[2].school_slug == "mit"


def test_team_ranking_tiebreaker_from_full_scores():
    """Tiebreakers should be populated from the ranking table."""
    rounds_data = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-3-5",
                    "school2": "MIT",
                    "url2": "/schools/mit/s26/",
                    "mascot2": " Engineers",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
            ],
        }
    ]
    all_html = team_all_scores(rounds_data)
    rankings = [
        _ranking(1, "Navy", "/schools/navy/s26/", tb="*", tb_note="Head-to-head record (1-0)"),
        _ranking(2, "MIT", "/schools/mit/s26/"),
    ]

    ts_rounds, ts_results = ts_team.parse(all_html)
    result = build_team_scores(all_html, "s26", "test", ts_rounds, ts_results, rankings=rankings)

    navy = next(t for t in result.teams if t.school_slug == "navy")
    assert navy.tiebreaker == "*"
    assert navy.tiebreaker_note == "Head-to-head record (1-0)"


def test_team_multi_team_tiebreaker():
    """Tiebreakers should be per-team even when multiple teams share a school."""
    rounds_data = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Texas A&M",
                    "url1": "/schools/texas-am/s26/",
                    "mascot1": " Aggies 1",
                    "pos1": "1-3-5",
                    "school2": "Rice",
                    "url2": "/schools/rice/s26/",
                    "mascot2": " Owls",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
                {
                    "race_num": 2,
                    "school1": "Rice",
                    "url1": "/schools/rice/s26/",
                    "mascot1": " Owls",
                    "pos1": "1-3-5",
                    "school2": "Texas A&M",
                    "url2": "/schools/texas-am/s26/",
                    "mascot2": " Aggies 2",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
            ],
        }
    ]
    html = team_all_scores(rounds_data, host="Texas A&M")
    ts_rounds, ts_results = ts_team.parse(html)
    rankings = [
        TeamRankingScore(
            rank=1,
            school_name="Texas A&M",
            school_url="/schools/texas-am/s26/",
            team_name="Aggies 1",
            division_scores={},
            division_penalties={},
            total=0,
            tiebreaker="*",
            tiebreaker_note="Head-to-head (1-0)",
        ),
        TeamRankingScore(
            rank=2,
            school_name="Rice",
            school_url="/schools/rice/s26/",
            team_name="Owls",
            division_scores={},
            division_penalties={},
            total=0,
        ),
        TeamRankingScore(
            rank=3,
            school_name="Texas A&M",
            school_url="/schools/texas-am/s26/",
            team_name="Aggies 2",
            division_scores={},
            division_penalties={},
            total=0,
            tiebreaker="**",
            tiebreaker_note="Head-to-head (0-1)",
        ),
    ]
    result = build_team_scores(html, "s26", "test", ts_rounds, ts_results, rankings=rankings)

    a1 = next(t for t in result.teams if t.team_name == "Aggies 1")
    a2 = next(t for t in result.teams if t.team_name == "Aggies 2")
    rice = next(t for t in result.teams if t.team_name == "Owls")
    # Tiebreakers must be per-team, not per-school
    assert a1.tiebreaker == "*"
    assert a1.tiebreaker_note == "Head-to-head (1-0)"
    assert a2.tiebreaker == "**"
    assert a2.tiebreaker_note == "Head-to-head (0-1)"
    assert rice.tiebreaker == ""


def test_regression_team_opponent_is_slug():
    """Team racing opponents must be school slugs so short_name() works."""
    rounds_data = [
        {
            "name": "Round 1",
            "races": [
                {
                    "race_num": 1,
                    "school1": "Navy",
                    "url1": "/schools/navy/s26/",
                    "mascot1": " Midshipmen",
                    "pos1": "1-3-5",
                    "school2": "Georgetown University",
                    "url2": "/schools/georgetown/s26/",
                    "mascot2": " Hoyas",
                    "pos2": "2-4-6",
                    "winner": 1,
                },
            ],
        }
    ]
    html = team_all_scores(rounds_data)
    ts_rounds, ts_results = ts_team.parse(html)
    result = build_team_scores(html, "s26", "test", ts_rounds, ts_results)

    navy = next(t for t in result.teams if t.school_slug == "navy")
    match = navy.rounds[0].matches[0]
    assert match.opponent == "georgetown"


def test_regression_team_tied_match():
    """Tied team racing matches must be counted as sailed and marked tied=True."""
    html = f"""<html><body>{date_block(host="MIT")}
<h1>Test Tied Match</h1>
<table class="teamscorelist">
<tr><th>#</th><th></th><th></th><th></th><th></th><th></th><th></th><th></th></tr>
<tr class="roundrow"><td colspan="8">Round 1</td></tr>
<tr>
  <td>1</td><td></td>
  <td class="tr-tie"><a href="/schools/navy/s26/">Navy</a> Midshipmen</td>
  <td>1-4-5</td><td>vs</td><td>2-3-6</td>
  <td class="tr-tie"><a href="/schools/mit/s26/">MIT</a> Engineers</td>
  <td></td>
</tr>
</table></body></html>"""

    ts_rounds, ts_results = ts_team.parse(html)
    result = build_team_scores(html, "s26", "test", ts_rounds, ts_results)

    for team in result.teams:
        assert team.total_ties == 1
        assert team.total_wins == 0
        assert team.total_losses == 0
        match = team.rounds[0].matches[0]
        assert match.sailed is True
        assert match.tied is True
