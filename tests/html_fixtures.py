"""
Shared HTML fixture builders for techscore full-scores and team-race tables.

Mirrors the cell formats from techscore's FullScoresTableCreator:
  Format 1 (1-div):       TeamName<br/><a>School</a>   — row_1div()
  Format 2 (multi-div A): <a>School</a>                — row_a()
  Format 3 (multi-div B): TeamName (plain text)         — row_b()
  Format 4 (multi-div C+): (empty)                      — row_c()
"""


def date_block(date_text="March 6-8, 2026",
               datetime_attr="2026-03-06T10:00",
               host="Navy"):
    return (
        f'<span itemprop="location">{host}</span>'
        f'<time itemprop="startDate" datetime="{datetime_attr}">{date_text}</time>'
    )


# ---------------------------------------------------------------------------
# Full-scores row builders
# ---------------------------------------------------------------------------

def row_1div(place, school, school_url, team_name, race_scores, div_total,
             tb_sym="", tb_title=""):
    """Single-division row (PHP: num_divs==1). No Div. column."""
    cells = f'<td title="{tb_title}">{tb_sym}</td><td>{place}</td>'
    cells += f'<td class="strong">{team_name}<br/><a href="{school_url}">{school}</a></td>'
    for pts in race_scores:
        cells += f'<td class="right">{pts}</td>'
    cells += f'<td></td><td class="right">{div_total}</td>'
    return f'<tr class="divA">{cells}</tr>'


def row_a(place, school, school_url, race_scores, div_total,
          tb_sym="", tb_title=""):
    """Multi-division A row (PHP: num_divs>1, div=="A")."""
    cells = f'<td title="{tb_title}">{tb_sym}</td><td>{place}</td>'
    cells += f'<td><a href="{school_url}">{school}</a></td>'
    cells += '<td class="strong">A</td>'
    for pts in race_scores:
        cells += f'<td class="right">{pts}</td>'
    cells += f'<td></td><td class="right">{div_total}</td>'
    return f'<tr class="divA">{cells}</tr>'


def row_b(team_name, race_scores, div_total):
    """Multi-division B row (PHP: num_divs>1, div=="B")."""
    cells = '<td></td><td></td>'
    cells += f'<td>{team_name}</td>'
    cells += '<td class="strong">B</td>'
    for pts in race_scores:
        cells += f'<td class="right">{pts}</td>'
    cells += f'<td></td><td class="right">{div_total}</td>'
    return f'<tr class="divB">{cells}</tr>'


def row_c(race_scores, div_total):
    """Multi-division C+ row (PHP: num_divs>1, div not A or B)."""
    cells = '<td></td><td></td><td></td>'
    cells += '<td class="strong">C</td>'
    for pts in race_scores:
        cells += f'<td class="right">{pts}</td>'
    cells += f'<td></td><td class="right">{div_total}</td>'
    return f'<tr class="divC">{cells}</tr>'


def totalrow(total):
    return (f'<tr class="totalrow"><td></td><td></td><td></td><td></td>'
            f'<td class="right">{total}</td></tr>')


# ---------------------------------------------------------------------------
# Full-scores page builders
# ---------------------------------------------------------------------------

def fs_header(race_nums, has_div=True):
    cells = "<th></th><th></th><th>Team</th>"
    if has_div:
        cells += "<th>Div.</th>"
    for rn in race_nums:
        cells += f"<th>{rn}</th>"
    cells += "<th></th><th>TOT</th>"
    return f"<thead><tr>{cells}</tr></thead>"


def fs_page(header, rows):
    return f"""<html><body>
<table class="results coordinate">
  {header}
  <tbody>{"".join(rows)}</tbody>
</table>
</body></html>"""


def full_scores_1div(teams, race_nums=None):
    """Build full-scores HTML for a single-division regatta.

    Each team dict: place, school, school_url, team_name, race_scores,
    div_total, sum_total.  Optional: tb_sym, tb_title.
    """
    if race_nums is None:
        race_nums = list(range(1, len(teams[0]["race_scores"]) + 1))
    header = fs_header(race_nums, has_div=False)
    rows = ""
    for t in teams:
        rows += row_1div(str(t["place"]), t["school"], t["school_url"],
                         t["team_name"], t["race_scores"], t["div_total"],
                         t.get("tb_sym", ""), t.get("tb_title", ""))
        rows += totalrow(t["sum_total"])
    return f"""<html><body>
{date_block()}
<h1>Test 1-Div Regatta</h1>
<table class="results coordinate">
  {header}
  <tbody>{rows}</tbody>
</table>
</body></html>"""


def full_scores_2div(teams, race_nums=None):
    """Build full-scores HTML for a two-division regatta.

    Each team dict: place, school, school_url, mascot, a_scores, a_total,
    b_scores, b_total, sum_total.  Optional: tb_sym, tb_title.
    """
    n_races = len(teams[0]["a_scores"])
    if race_nums is None:
        race_nums = list(range(1, n_races + 1))
    header = fs_header(race_nums)
    rows = ""
    for t in teams:
        rows += row_a(str(t["place"]), t["school"], t["school_url"],
                      t["a_scores"], t["a_total"],
                      t.get("tb_sym", ""), t.get("tb_title", ""))
        rows += row_b(t["mascot"], t["b_scores"], t["b_total"])
        rows += totalrow(t["sum_total"])
    return f"""<html><body>
{date_block()}
<h1>Test 2-Div Regatta</h1>
<table class="results coordinate">
  {header}
  <tbody>{rows}</tbody>
</table>
</body></html>"""


# ---------------------------------------------------------------------------
# Team racing page builder
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Division page builder (DivisionScoresTableCreator.php)
# ---------------------------------------------------------------------------

def div_team_row(rank, school, school_url, race_scores, total,
                 skipper="Skipper Name", crew="Crew Name",
                 team_name="", penalty="",
                 tb_sym="", tb_note=""):
    """One team group on a division page.  Simplified to skipper + crew rows."""
    sailor_count = 2
    cells_r1 = (
        f'<td class="tiebreaker" rowspan="{sailor_count}" title="{tb_note}">{tb_sym}</td>'
        f'<td rowspan="{sailor_count}">{rank}</td>'
        f'<td class="burgee-cell" rowspan="{sailor_count}"></td>'
        f'<td class="schoolname" rowspan="{sailor_count}">'
        f'<a href="{school_url}">{school}</a></td>'
        f'<td rowspan="{sailor_count}">{penalty}</td>'
        f'<td class="totalcell" rowspan="{sailor_count}">{total}</td>'
        f'<td class="sailor-name skipper">{skipper}</td>'
        f'<td class="races"></td><td class="superscript"></td>'
    )
    cells_r2 = (
        f'<td class="teamname" rowspan="1">{team_name}</td>'
        f'<td class="sailor-name crew">{crew}</td>'
        f'<td class="races"></td><td class="superscript"></td>'
    )
    return (
        f'<tr class="topborder left row0">{cells_r1}</tr>'
        f'<tr class="left row0">{cells_r2}</tr>'
    )


def div_page(division, teams, race_nums=None):
    """Build a division scores page.

    Each team dict: rank, school, school_url, race_scores, total.
    Optional: skipper, crew, team_name, penalty, tb_sym, tb_note.
    """
    if race_nums is None and teams:
        race_nums = list(range(1, len(teams[0].get("race_scores", [])) + 1))
    header_cells = '<th></th><th></th><th></th><th class="teamname">Team</th><th></th><th>Total</th><th>Sailors</th><th></th><th></th>'
    for rn in (race_nums or []):
        header_cells += f'<th>{rn}</th>'
    rows = ""
    for t in teams:
        rows += div_team_row(
            t["rank"], t["school"], t["school_url"],
            t.get("race_scores", []), t["total"],
            skipper=t.get("skipper", "Skipper"),
            crew=t.get("crew", "Crew"),
            team_name=t.get("team_name", ""),
            penalty=t.get("penalty", ""),
            tb_sym=t.get("tb_sym", ""),
            tb_note=t.get("tb_note", ""),
        )
    return f"""<html><body>
<table class="results coordinate division {division}">
<thead><tr>{header_cells}</tr></thead>
<tbody>{rows}</tbody>
</table>
</body></html>"""


# ---------------------------------------------------------------------------
# Team racing page builder
# ---------------------------------------------------------------------------

def team_race_row(race_num, school1, url1, mascot1, pos1,
                  school2, url2, mascot2, pos2, winner=1):
    t1_class = "tr-win" if winner == 1 else "tr-lose"
    t2_class = "tr-win" if winner == 2 else "tr-lose"
    return (
        f'<tr><td>{race_num}</td><td></td>'
        f'<td class="{t1_class}"><a href="{url1}">{school1}</a>{mascot1}</td>'
        f'<td>{pos1}</td><td>vs</td><td>{pos2}</td>'
        f'<td class="{t2_class}"><a href="{url2}">{school2}</a>{mascot2}</td>'
        f'<td></td></tr>'
    )


def team_all_scores(rounds, host="MIT"):
    rows = '<tr><th>#</th><th></th><th></th><th></th><th></th><th></th><th></th><th></th></tr>'
    for rnd in rounds:
        rows += f'<tr class="roundrow"><td colspan="8">{rnd["name"]}</td></tr>'
        for race in rnd["races"]:
            rows += team_race_row(**race)
    return f"""<html><body>
{date_block(host=host)}
<h1>Test Team Regatta</h1>
<table class="teamscorelist">{rows}</table>
</body></html>"""
