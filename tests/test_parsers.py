"""
Tests for scraper/parsers/ — the shared techscore HTML parsers.
"""

from scraper.parsers import full_scores, team_all_races, division as division_parser
from scraper.parsers.metadata import extract as extract_metadata
from bs4 import BeautifulSoup

from html_fixtures import (
    row_1div, row_a, row_b, row_c, totalrow,
    fs_header, fs_page, div_page,
)


# ---------------------------------------------------------------------------
# full_scores: 1-division (Format 1 — no Div. column)
# ---------------------------------------------------------------------------

def test_1div_basic():
    """Standard 1-div: TeamName<br/><a>School</a>, no Div. column."""
    header = fs_header([1, 2, 3], has_div=False)
    rows = [
        row_1div(1, "Navy", "/schools/navy/s26/", "Midshipmen", [1, 2, 3], 6),
        totalrow(6),
        row_1div(2, "MIT", "/schools/mit/s26/", "Engineers", [2, 1, 4], 7),
        totalrow(7),
    ]
    result = full_scores.parse(fs_page(header, rows))
    assert len(result) == 2
    assert result[0].school_name == "Navy"
    assert result[0].team_name == "Midshipmen"
    assert result[0].school_url == "/schools/navy/s26/"
    assert result[0].division == "A"
    assert result[0].div_total == 6
    assert len(result[0].race_scores) == 3
    assert result[1].school_name == "MIT"
    assert result[1].team_name == "Engineers"


def test_1div_multi_team_same_school():
    """J70-style: same school, different team names in the cell text before <a>.
    Parser should extract team_name from text before link, school from link."""
    header = fs_header([1, 2, 3], has_div=False)
    rows = [
        row_1div(1, "Coast Guard", "/schools/coast-guard/s26/", "Bears 1", [2, 1, 3], 6),
        totalrow(6),
        row_1div(2, "MIT", "/schools/mit/s26/", "Engineers", [1, 3, 4], 8),
        totalrow(8),
        row_1div(3, "Coast Guard", "/schools/coast-guard/s26/", "Bears 2", [3, 4, 5], 12),
        totalrow(12),
    ]
    result = full_scores.parse(fs_page(header, rows))
    assert len(result) == 3
    # Both CG entries should have school_name from the <a> link
    assert result[0].school_name == "Coast Guard"
    assert result[2].school_name == "Coast Guard"
    # Team names from text before the link
    assert result[0].team_name == "Bears 1"
    assert result[2].team_name == "Bears 2"
    # Same school_url
    assert result[0].school_url == result[2].school_url == "/schools/coast-guard/s26/"
    # MIT separate
    assert result[1].school_name == "MIT"
    assert result[1].team_name == "Engineers"


# ---------------------------------------------------------------------------
# full_scores: 2-division (Formats 2+3 — has Div. column)
# ---------------------------------------------------------------------------

def test_2div_basic():
    """Standard 2-div: divA has <a>School</a>, divB has TeamName."""
    header = fs_header([1, 2])
    rows = [
        row_a(1, "Navy", "/schools/navy/s26/", [1, 2], 3),
        row_b("Midshipmen", [2, 1], 3),
        totalrow(6),
    ]
    result = full_scores.parse(fs_page(header, rows))
    assert len(result) == 2
    assert result[0].school_name == "Navy"
    assert result[0].division == "A"
    assert result[0].div_total == 3
    assert result[1].division == "B"
    assert result[1].div_total == 3
    # Team name propagated from divB to divA
    assert result[0].team_name == "Midshipmen"
    assert result[1].team_name == "Midshipmen"


def test_2div_multi_team_same_school():
    """TAG State-style: two teams from same school in multi-div.
    Team names must not cross-contaminate between teams."""
    header = fs_header([1, 2])
    rows = [
        row_a(1, "Tennessee", "/schools/tennessee/s26/", [1, 2], 3),
        row_b("Volunteers", [1, 2], 3),
        totalrow(6),
        row_a(2, "Tennessee", "/schools/tennessee/s26/", [3, 1], 4),
        row_b("Smokies", [2, 4], 6),
        totalrow(10),
    ]
    result = full_scores.parse(fs_page(header, rows))
    assert len(result) == 4  # 2 teams x 2 divisions
    # Volunteers rows (team 1)
    assert result[0].team_name == "Volunteers"
    assert result[1].team_name == "Volunteers"
    assert result[0].school_name == "Tennessee"
    # Smokies rows (team 2) — must NOT get "Volunteers"
    assert result[2].team_name == "Smokies"
    assert result[3].team_name == "Smokies"
    assert result[2].school_name == "Tennessee"


def test_3div_propagation():
    """With 3 divisions, divC has blank name cell — propagation fills it."""
    header = fs_header([1])
    rows = [
        row_a(1, "Navy", "/schools/navy/s26/", [1], 1),
        row_b("Midshipmen", [2], 2),
        row_c([3], 3),
        totalrow(6),
    ]
    result = full_scores.parse(fs_page(header, rows))
    assert len(result) == 3
    assert all(r.team_name == "Midshipmen" for r in result)
    assert all(r.school_name == "Navy" for r in result)
    assert [r.division for r in result] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# full_scores: B fewer races than A
# ---------------------------------------------------------------------------

def test_b_fewer_races_than_a():
    """When division B has fewer races sailed, empty cells should produce
    score=None so the adapter can filter them out."""
    header = fs_header([1, 2, 3])
    a_cells = ('<td></td><td>1</td>'
               '<td><a href="/schools/navy/s26/">Navy</a></td>'
               '<td class="strong">A</td>'
               '<td class="right">1</td><td class="right">2</td><td class="right">3</td>'
               '<td></td><td class="right">6</td>')
    b_cells = ('<td></td><td></td><td>Midshipmen</td>'
               '<td class="strong">B</td>'
               '<td class="right">2</td><td class="right">1</td><td class="right"></td>'
               '<td></td><td class="right">3</td>')
    rows = [
        f'<tr class="divA">{a_cells}</tr>',
        f'<tr class="divB">{b_cells}</tr>',
        totalrow(9),
    ]
    result = full_scores.parse(fs_page(header, rows))
    a_scores = result[0].race_scores
    b_scores = result[1].race_scores
    assert len(a_scores) == 3
    assert all(r.score is not None for r in a_scores)
    # B race 3 is unsailed — score should be None
    assert len(b_scores) == 3
    b_race3 = next(r for r in b_scores if r.race_num == 3)
    assert b_race3.score is None


# ---------------------------------------------------------------------------
# full_scores: penalty / title parsing
# ---------------------------------------------------------------------------

def test_penalty_score_from_title_comma():
    """Penalty score must come from title='(15, Fleet + 1)', not cell text."""
    header = fs_header([1, 2])
    rows = [
        row_a(1, "Navy", "/schools/navy/s26/", [1, 2], 3).replace(
            '<td class="right">1</td>',
            '<td class="right" title="(15, Fleet + 1)"><abbr>DNF</abbr></td>'),
        row_b("Midshipmen", [1, 1], 2),
        totalrow(5),
    ]
    # Manually build since we modified a cell
    result = full_scores.parse(fs_page(fs_header([1, 2]), rows))
    dnf_race = result[0].race_scores[0]
    assert dnf_race.score == 15
    assert dnf_race.modifier == "DNF"


def test_penalty_score_from_title_colon():
    """Breakdown averages use colon: '(7: average in division)'."""
    header = fs_header([1])
    rows = [
        '<tr class="divA"><td></td><td>1</td>'
        '<td><a href="/schools/navy/s26/">Navy</a></td>'
        '<td>A</td>'
        '<td class="right" title="(7: average in division)"><abbr>BYE</abbr></td>'
        '<td></td><td class="right">7</td></tr>',
        totalrow(7),
    ]
    result = full_scores.parse(fs_page(header, rows))
    assert result[0].race_scores[0].score == 7
    assert result[0].race_scores[0].modifier == "BYE"


def test_clean_score_no_modifier():
    """Normal finish: integer score, no modifier."""
    header = fs_header([1])
    rows = [
        row_a(1, "Navy", "/schools/navy/s26/", [3], 3),
        row_b("Midshipmen", [2], 2),
        totalrow(5),
    ]
    result = full_scores.parse(fs_page(header, rows))
    assert result[0].race_scores[0].score == 3
    assert result[0].race_scores[0].modifier == ""


def test_title_field_captured():
    """The title attribute should flow through to RaceScore.title."""
    header = fs_header([1])
    rows = [
        '<tr class="divA"><td></td><td>1</td>'
        '<td><a href="/schools/navy/s26/">Navy</a></td>'
        '<td>A</td>'
        '<td class="right" title="(15, Fleet + 1)"><abbr>DNF</abbr></td>'
        '<td></td><td class="right">15</td></tr>',
        totalrow(15),
    ]
    result = full_scores.parse(fs_page(header, rows))
    assert result[0].race_scores[0].title == "(15, Fleet + 1)"


# ---------------------------------------------------------------------------
# full_scores: singlehanded layout
# ---------------------------------------------------------------------------

def test_singlehanded_extracts_school_not_sailor():
    """Singlehanded cells have sailor <a> then school <a>.
    Parser must extract school_url from the /schools/ link."""
    header = fs_header([1, 2], has_div=False)
    rows = [
        '<tr class="divA"><td></td><td>1</td>'
        '<td>'
        '<span class="singlehanded-sailor-span"><a href="/sailors/john-doe/">John Doe \'27</a></span>'
        '<br/><a href="/schools/navy/s26/">Navy</a>'
        '</td>'
        '<td class="right">1</td><td class="right">2</td>'
        '<td></td><td class="right">3</td></tr>',
        totalrow(3),
    ]
    result = full_scores.parse(fs_page(header, rows))
    assert result[0].school_url == "/schools/navy/s26/"
    assert result[0].school_name == "Navy"
    assert result[0].sailor_name == "John Doe '27"
    assert result[0].sailor_url == "/sailors/john-doe/"


def test_singlehanded_school_id():
    """School ID extracted from singlehanded school URL."""
    header = fs_header([1], has_div=False)
    rows = [
        '<tr class="divA"><td></td><td>1</td>'
        '<td>'
        '<span class="singlehanded-sailor-span"><a href="/sailors/jane/">Jane</a></span>'
        '<br/><a href="/schools/mit/s26/">MIT</a>'
        '</td>'
        '<td class="right">1</td>'
        '<td></td><td class="right">1</td></tr>',
        totalrow(1),
    ]
    result = full_scores.parse(fs_page(header, rows))
    assert result[0].school_id == "mit"


# ---------------------------------------------------------------------------
# full_scores: totalrow skipped
# ---------------------------------------------------------------------------

def test_totalrow_not_in_results():
    """The totalrow (cumulative sums) must be skipped entirely."""
    header = fs_header([1, 2])
    rows = [
        row_a(1, "Navy", "/schools/navy/s26/", [1, 2], 3),
        row_b("Mids", [3, 4], 7),
        '<tr class="totalrow"><td></td><td></td><td></td><td></td>'
        '<td class="right">5</td><td class="right">9</td>'
        '<td></td><td class="right">10</td></tr>',
    ]
    result = full_scores.parse(fs_page(header, rows))
    assert len(result) == 2  # divA + divB, not 3


# ---------------------------------------------------------------------------
# team_all_races: _parse_places (Bug 9)
# ---------------------------------------------------------------------------

def test_parse_places_clean():
    """Clean finish: '2-4-6' → places=[2,4,6], penalties=['','','']."""
    places, penalties = team_all_races._parse_places("2-4-6")
    assert places == [2, 4, 6]
    assert penalties == ["", "", ""]


def test_parse_places_single_penalty():
    """Single penalty: '1-3-6 RAF' → broadcast to all divisions."""
    places, penalties = team_all_races._parse_places("1-3-6 RAF")
    assert places == [1, 3, 6]
    assert penalties == ["RAF", "RAF", "RAF"]


def test_parse_places_compound_penalty():
    """Bug 9: Compound 'DNS,DNS,DNS' must use first code, not the whole string."""
    places, penalties = team_all_races._parse_places("4-5-6 DNS,DNS,DNS")
    assert places == [4, 5, 6]
    assert all(p == "DNS" for p in penalties)
    # Must NOT be "DNS,DNS,DNS"
    assert "," not in penalties[0]


def test_parse_places_mixed_penalty():
    """Mixed penalties 'DSQ,DNF' — use first code, broadcast."""
    places, penalties = team_all_races._parse_places("1-3-6 DSQ,DNF")
    assert places == [1, 3, 6]
    assert all(p == "DSQ" for p in penalties)


def test_parse_places_empty():
    """Empty string (unsailed race)."""
    places, penalties = team_all_races._parse_places("")
    assert places == []
    assert penalties == []


# ---------------------------------------------------------------------------
# team_all_races: round detection
# ---------------------------------------------------------------------------

def test_round_headers_detected():
    """Round headers with class='roundrow' create RoundInfo entries."""
    html = """<html><body>
<table class="teamscorelist">
<tr><th>#</th><th></th><th></th><th></th><th></th><th></th><th></th><th></th></tr>
<tr class="roundrow"><td colspan="8">Round 1</td></tr>
<tr>
  <td>1</td><td></td>
  <td class="tr-win"><a href="/schools/navy/s26/">Navy</a> Mids</td>
  <td>1-3-5</td><td>vs</td><td>2-4-6</td>
  <td class="tr-lose"><a href="/schools/mit/s26/">MIT</a> Eng</td>
  <td></td>
</tr>
<tr class="roundrow"><td colspan="8">Round 2</td></tr>
<tr>
  <td>2</td><td></td>
  <td class="tr-lose"><a href="/schools/navy/s26/">Navy</a> Mids</td>
  <td>2-4-6</td><td>vs</td><td>1-3-5</td>
  <td class="tr-win"><a href="/schools/mit/s26/">MIT</a> Eng</td>
  <td></td>
</tr>
</table></body></html>"""

    rounds, results = team_all_races.parse(html)
    assert len(rounds) == 2
    assert rounds[0].title == "Round 1"
    assert rounds[1].title == "Round 2"
    assert len(results) == 2
    assert results[0].round_order == 1
    assert results[1].round_order == 2


# ---------------------------------------------------------------------------
# team_all_races: winner detection
# ---------------------------------------------------------------------------

def test_winner_detection():
    """tr-win class on team cell indicates winner."""
    html = """<html><body>
<table class="teamscorelist">
<tr><th>#</th><th></th><th></th><th></th><th></th><th></th><th></th><th></th></tr>
<tr class="roundrow"><td colspan="8">Round 1</td></tr>
<tr>
  <td>1</td><td></td>
  <td class="tr-win"><a href="/schools/navy/s26/">Navy</a></td>
  <td>1-3-5</td><td>vs</td><td>2-4-6</td>
  <td class="tr-lose"><a href="/schools/mit/s26/">MIT</a></td>
  <td></td>
</tr>
</table></body></html>"""

    _, results = team_all_races.parse(html)
    assert results[0].team1_won is True
    assert results[0].team2_won is False


def test_unsailed_match_no_winner():
    """Unsailed match: no tr-win/tr-lose class, empty places."""
    html = """<html><body>
<table class="teamscorelist">
<tr><th>#</th><th></th><th></th><th></th><th></th><th></th><th></th><th></th></tr>
<tr class="roundrow"><td colspan="8">Round 1</td></tr>
<tr>
  <td>1</td><td></td>
  <td class="team1"><a href="/schools/navy/s26/">Navy</a></td>
  <td></td><td>vs</td><td></td>
  <td class="team2"><a href="/schools/mit/s26/">MIT</a></td>
  <td></td>
</tr>
</table></body></html>"""

    _, results = team_all_races.parse(html)
    assert results[0].team1_won is False
    assert results[0].team2_won is False
    assert results[0].team1_earned == []
    assert results[0].team2_earned == []


# ---------------------------------------------------------------------------
# metadata: scoring_type detection
# ---------------------------------------------------------------------------

def test_scoring_type_divisional():
    html = """<html><body>
<ul id="page-info"><li>
  <span class="page-info-key">Scoring</span>
  <span class="page-info-value">2 Divisions</span>
</li></ul></body></html>"""
    assert extract_metadata(BeautifulSoup(html, "lxml")).scoring_type == "divisional"


def test_scoring_type_team():
    html = """<html><body>
<ul id="page-info"><li>
  <span class="page-info-key">Scoring</span>
  <span class="page-info-value">Team</span>
</li></ul></body></html>"""
    assert extract_metadata(BeautifulSoup(html, "lxml")).scoring_type == "team"


def test_scoring_type_combined():
    html = """<html><body>
<ul id="page-info"><li>
  <span class="page-info-key">Scoring</span>
  <span class="page-info-value">Combined</span>
</li></ul></body></html>"""
    assert extract_metadata(BeautifulSoup(html, "lxml")).scoring_type == "combined"


def test_scoring_type_default():
    """No page-info → default to divisional."""
    assert extract_metadata(BeautifulSoup("<html></html>", "lxml")).scoring_type == "divisional"


# ---------------------------------------------------------------------------
# division parser
# ---------------------------------------------------------------------------

def test_division_basic():
    """Basic division page: ranks, school slugs, totals."""
    html = div_page("A", [
        {"rank": 1, "school": "Navy", "school_url": "/schools/navy/s26/",
         "race_scores": [], "total": 12},
        {"rank": 2, "school": "MIT", "school_url": "/schools/mit/s26/",
         "race_scores": [], "total": 18},
    ])
    results = division_parser.parse(html, "A")
    assert len(results) == 2
    assert results[0].rank == 1
    assert results[0].school_slug == "navy"
    assert results[0].total_score == 12
    assert results[1].rank == 2
    assert results[1].school_slug == "mit"
    assert results[1].total_score == 18


def test_division_tiebreaker():
    """Division page with tiebreaker symbols and explanations."""
    html = div_page("A", [
        {"rank": 1, "school": "Brown", "school_url": "/schools/brown/f22/",
         "race_scores": [], "total": 30},
        {"rank": 2, "school": "Coast Guard", "school_url": "/schools/coast-guard/f22/",
         "race_scores": [], "total": 30,
         "tb_sym": "*", "tb_note": "Head-to-head tiebreaker"},
        {"rank": 3, "school": "Harvard", "school_url": "/schools/harvard/f22/",
         "race_scores": [], "total": 30,
         "tb_sym": "*", "tb_note": "Head-to-head tiebreaker"},
    ])
    results = division_parser.parse(html, "A")
    assert len(results) == 3
    assert results[0].tiebreaker == ""
    assert results[0].tiebreaker_note == ""
    assert results[1].tiebreaker == "*"
    assert results[1].tiebreaker_note == "Head-to-head tiebreaker"
    assert results[2].tiebreaker == "*"
    assert results[2].tiebreaker_note == "Head-to-head tiebreaker"


def test_division_school_slug_extraction():
    """School slug extracted from <a href> in team cell."""
    html = div_page("B", [
        {"rank": 1, "school": "U. S. Coast Guard Academy",
         "school_url": "/schools/coast-guard/f22/",
         "race_scores": [], "total": 10},
    ])
    results = division_parser.parse(html, "B")
    assert results[0].school_slug == "coast-guard"


def test_division_multi_team_per_school():
    """Multiple teams from the same school get separate results."""
    html = div_page("A", [
        {"rank": 1, "school": "Tennessee", "school_url": "/schools/tennessee/s26/",
         "team_name": "Volunteers", "race_scores": [], "total": 10},
        {"rank": 2, "school": "Tennessee", "school_url": "/schools/tennessee/s26/",
         "team_name": "Smokies", "race_scores": [], "total": 20},
    ])
    results = division_parser.parse(html, "A")
    assert len(results) == 2
    assert results[0].school_slug == "tennessee"
    assert results[1].school_slug == "tennessee"


def test_division_penalty():
    """Penalty column is captured."""
    html = div_page("A", [
        {"rank": 1, "school": "Navy", "school_url": "/schools/navy/s26/",
         "race_scores": [], "total": 15, "penalty": "MRP"},
    ])
    results = division_parser.parse(html, "A")
    assert results[0].penalty == "MRP"


def test_division_multiple_tiebreaker_types():
    """Different tiebreaker explanations produce different symbols."""
    html = div_page("A", [
        {"rank": 1, "school": "Navy", "school_url": "/schools/navy/s26/",
         "race_scores": [], "total": 20},
        {"rank": 2, "school": "MIT", "school_url": "/schools/mit/s26/",
         "race_scores": [], "total": 20,
         "tb_sym": "*", "tb_note": "Head-to-head tiebreaker"},
        {"rank": 3, "school": "Brown", "school_url": "/schools/brown/s26/",
         "race_scores": [], "total": 20,
         "tb_sym": "*", "tb_note": "Head-to-head tiebreaker"},
        {"rank": 4, "school": "Yale", "school_url": "/schools/yale/s26/",
         "race_scores": [], "total": 25},
        {"rank": 5, "school": "Harvard", "school_url": "/schools/harvard/s26/",
         "race_scores": [], "total": 25,
         "tb_sym": "**", "tb_note": "Number of high-place (1) finishes"},
        {"rank": 6, "school": "Tufts", "school_url": "/schools/tufts/s26/",
         "race_scores": [], "total": 25,
         "tb_sym": "**", "tb_note": "Number of high-place (1) finishes"},
    ])
    results = division_parser.parse(html, "A")
    assert results[1].tiebreaker == "*"
    assert results[4].tiebreaker == "**"
    assert results[4].tiebreaker_note == "Number of high-place (1) finishes"
