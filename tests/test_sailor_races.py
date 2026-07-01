from scraper.parsers.full_scores import RaceScore as FSRace
from scraper.parsers.full_scores import TeamDivScore
from scraper.parsers.sailors import RpEntry
from scraper.parsers.team_all_races import RoundInfo, TeamRaceResult
from scraper.parsers.team_sailors import BoatAssignment, MatchupRP
from scraper.sailor_races import _join_fleet, _join_team


def _navy_div_a():
    return TeamDivScore(
        school_name="Navy",
        school_url="/schools/navy/s26/",
        school_id="navy",
        team_name="Navy",
        division="A",
        penalty="",
        race_scores=[FSRace(1, 3, ""), FSRace(2, 5, ""), FSRace(3, 1, "")],
        div_total=9,
    )


def test_join_fleet_rp_expands_ranges_and_looks_up_place():
    rp = [
        RpEntry(
            "Navy",
            "/schools/navy/s26/",
            "Navy",
            "A",
            1,
            "Jane Doe",
            "/sailors/jane-doe/",
            "skipper",
            "1-2",
        ),
        RpEntry(
            "Navy", "/schools/navy/s26/", "Navy", "A", 1, "Bob Roe", "/sailors/bob-roe/", "crew", ""
        ),  # empty range = all races
    ]
    rows = _join_fleet([_navy_div_a()], rp, "s26", "reg")

    skip = [r for r in rows if r.boat_role == "skipper"]
    crew = [r for r in rows if r.boat_role == "crew"]
    # skipper sailed races 1-2 → places 3, 5
    assert [(r.race_num, r.place) for r in skip] == [(1, 3), (2, 5)]
    # crew sailed all three → places 3, 5, 1
    assert [(r.race_num, r.place) for r in crew] == [(1, 3), (2, 5), (3, 1)]
    assert skip[0].sailor_slug == "jane-doe"
    assert skip[0].school_slug == "navy" and skip[0].division == "A"


def test_join_fleet_rp_carries_penalty_per_race():
    rp = [
        RpEntry(
            "Navy",
            "/schools/navy/s26/",
            "Navy",
            "A",
            1,
            "Jane Doe",
            "/sailors/jane-doe/",
            "skipper",
            "",
        ),
    ]
    div = TeamDivScore(
        school_name="Navy",
        school_url="/schools/navy/s26/",
        school_id="navy",
        team_name="Navy",
        division="A",
        penalty="",
        race_scores=[FSRace(1, 1, ""), FSRace(2, 6, "DNF")],
        div_total=7,
    )
    rows = _join_fleet([div], rp, "s26", "reg")
    by_race = {r.race_num: r for r in rows}
    assert by_race[1].penalty is None
    assert by_race[2].penalty == "DNF"


def test_join_fleet_singlehanded_carries_penalty():
    ds = TeamDivScore(
        "MIT",
        "/schools/mit/s26/",
        "mit",
        "",
        "A",
        "",
        [FSRace(1, 2, ""), FSRace(2, 7, "DSQ")],
        9,
        sailor_name="Sam Sail",
        sailor_url="/sailors/sam-sail/",
    )
    rows = _join_fleet([ds], [], "s26", "reg")
    by_race = {r.race_num: r for r in rows}
    assert by_race[1].penalty is None
    assert by_race[2].penalty == "DSQ"


def test_join_fleet_disambiguates_ab_teams_by_name():
    a1 = TeamDivScore(
        "Navy", "/schools/navy/s26/", "navy", "Navy 1", "A", "", [FSRace(1, 2, "")], 2
    )
    a2 = TeamDivScore(
        "Navy", "/schools/navy/s26/", "navy", "Navy 2", "A", "", [FSRace(1, 7, "")], 7
    )
    rp = [
        RpEntry(
            "Navy",
            "/schools/navy/s26/",
            "Navy 2",
            "A",
            1,
            "Deuce",
            "/sailors/deuce/",
            "skipper",
            "1",
        )
    ]
    rows = _join_fleet([a1, a2], rp, "s26", "reg")
    assert len(rows) == 1 and rows[0].place == 7  # matched Navy 2, not Navy 1


def test_join_fleet_singlehanded_from_full_scores():
    ds = TeamDivScore(
        "MIT",
        "/schools/mit/s26/",
        "mit",
        "",
        "A",
        "",
        [FSRace(1, 2, ""), FSRace(2, 4, "")],
        6,
        sailor_name="Sam Sail",
        sailor_url="/sailors/sam-sail/",
    )
    rows = _join_fleet([ds], [], "s26", "reg")  # no RP → singlehanded synthesis
    assert [(r.race_num, r.place, r.boat_role) for r in rows] == [
        (1, 2, "skipper"),
        (2, 4, "skipper"),
    ]
    assert rows[0].sailor_slug == "sam-sail"


def test_join_team_earned_positions_resolution_and_canonical_slug():
    rounds = [RoundInfo(title="Round 1", relative_order=1)]
    results = [
        TeamRaceResult(
            race_number=1,
            round_order=1,
            team1_school_url="/schools/harvard/s26/",
            team1_team_name="Crimson",
            team1_earned=[1, 3, 5],
            team1_won=True,
            team1_penalties=["", "", ""],
            team2_school_url="/schools/yale/s26/",
            team2_team_name="Bulldogs",
            team2_earned=[2, 4, 6],
            team2_won=False,
            team2_penalties=["", "", ""],
        )
    ]
    matchups = [
        MatchupRP(
            round_title="Round 1",
            round_order=1,
            team_name="Harvard Crimson",
            opponent_name="Yale",  # mascot vs school-short
            boats=[
                BoatAssignment("A", "Al Alpha '26", "Bea Beta '27"),
                BoatAssignment("B", "Cy Gamma '25", ""),
            ],
        )
    ]
    rows = _join_team(
        rounds, results, matchups, "s26", "reg", {"Al Alpha '26": "/sailors/al-alpha/"}
    )

    by = {(r.division, r.boat_role): r for r in rows}
    # Harvard is team1 → earned [1,3,5]; div A place 1, div B place 3
    assert by[("A", "skipper")].place == 1
    assert by[("A", "crew")].place == 1
    assert by[("B", "skipper")].place == 3
    assert ("B", "crew") not in by  # empty crew skipped
    assert all(r.school_slug == "harvard" for r in rows)  # "Harvard Crimson" → harvard
    assert by[("A", "skipper")].sailor_slug == "al-alpha"  # canonical via sailor_links
    assert by[("B", "skipper")].sailor_slug == "cy-gamma"  # synthesized from name


def test_join_team_skips_unresolvable_and_self_matchups():
    rounds = [RoundInfo(title="Round 1", relative_order=1)]
    results = [
        TeamRaceResult(
            1,
            1,
            "/schools/harvard/s26/",
            "Crimson",
            [1, 3, 5],
            True,
            ["", "", ""],
            "/schools/yale/s26/",
            "Bulldogs",
            [2, 4, 6],
            False,
            ["", "", ""],
        )
    ]
    # opponent label matches nothing → matchup dropped
    matchups = [
        MatchupRP(
            "Round 1",
            1,
            "Harvard Crimson",
            "Nonexistent College",
            [BoatAssignment("A", "Al Alpha '26", "")],
        )
    ]
    assert _join_team(rounds, results, matchups, "s26", "reg", None) == []
