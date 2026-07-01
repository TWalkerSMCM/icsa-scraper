from scraper.parsers.sailor_profile import parse
from scraper.views import HeadToHead, RaceEncounter, SharedRegatta


def _row(href, name, host, dt, date_text, roles, placement_html):
    return (
        '<tr itemprop="event">'
        f'<td><a itemprop="url" href="{href}"><span itemprop="name">{name}</span></a></td>'
        f"<td>{host}</td>"
        f'<td><time itemprop="startDate" datetime="{dt}">{date_text}</time></td>'
        f"<td>{roles}</td>"
        f'<td><span class="sailor-placement-container">{placement_html}</span></td>'
        "</tr>"
    )


PAGE = (
    '<table class="participation-table">'
    "<tr><th>Name</th><th>Host</th><th>Date</th><th>Position</th><th>Place finish</th></tr>"
    + _row(
        "/s26/hood/",
        "Hood Trophy",
        "MIT",
        "2026-05-21",
        "May 21",
        "Skipper",
        '<a href="/s26/hood/A/">2/18 (A Div)</a>',
    )
    + _row(
        "/f25/match-cup/",
        "Match Cup",
        "Navy",
        "2025-11-15",
        "Nov 15",
        "Skipper",
        '<a href="/f25/match-cup/full-scores/#team-3">1/10</a>',
    )  # no division
    + _row(
        "/s25/twinstate/",
        "Twin State",
        "Dartmouth",
        "2025-04-12",
        "Apr 12",
        "Skipper, Crew",
        '<a href="/s25/twinstate/A/">3/18 (A Div)</a><a href="/s25/twinstate/B/">5/18 (B Div)</a>',
    )  # two divisions
    + _row("/s26/coming/", "Coming Up", "Yale", "2026-06-30", "Jun 30", "Skipper", "")  # unplaced
    + "</table>"
)


def test_parse_extracts_all_fields():
    rows = parse(PAGE)
    # Hood(A) + Match(overall) + TwinState(A) + TwinState(B) + Coming(none) = 5
    assert len(rows) == 5

    hood = rows[0]
    assert (hood.season, hood.slug, hood.regatta_name) == ("s26", "hood", "Hood Trophy")
    assert hood.host == "MIT" and hood.date == "2026-05-21" and hood.roles == "Skipper"
    assert (hood.division, hood.place, hood.fleet_size) == ("A", 2, 18)


def test_parse_overall_and_multidivision():
    rows = parse(PAGE)
    match = next(r for r in rows if r.slug == "match-cup")
    assert (match.division, match.place, match.fleet_size) == ("", 1, 10)  # no division

    twin = [r for r in rows if r.slug == "twinstate"]
    assert {(r.division, r.place) for r in twin} == {("A", 3), ("B", 5)}  # both divisions
    assert twin[0].roles == "Skipper, Crew"


def test_parse_unplaced_regatta():
    coming = next(r for r in parse(PAGE) if r.slug == "coming")
    assert coming.division == "" and coming.place is None and coming.fleet_size is None


def test_head_to_head_tallies():
    shared = [
        SharedRegatta("s26", "hood", "Hood", "A", place_a=2, place_b=5, fleet_size=18),  # a ahead
        SharedRegatta("s25", "twin", "Twin", "A", place_a=7, place_b=3, fleet_size=18),  # b ahead
        SharedRegatta("f25", "x", "X", "", place_a=1, place_b=None, fleet_size=10),  # b unplaced
    ]
    races = [
        RaceEncounter("s26", "hood", "A", 1, place_a=1, place_b=4),  # a wins
        RaceEncounter("s26", "hood", "A", 2, place_a=6, place_b=2),  # b wins
        RaceEncounter("s26", "hood", "A", 3, place_a=3, place_b=5),  # a wins
    ]
    h = HeadToHead(a="alice", b="bob", shared=shared, races=races)
    assert h.a_ahead == 1 and h.b_ahead == 1  # third has an unplaced sailor
    assert h.a_race_wins == 2 and h.b_race_wins == 1
