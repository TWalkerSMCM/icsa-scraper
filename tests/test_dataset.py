from scraper.dataset import Dataset
from scraper.models import (
    DivisionResult,
    RaceScore,
    RegattaScores,
    TeamRaceTeam,
    TeamRegattaScores,
    TeamResult,
)
from scraper.views import SailorRaceFinish


def _fleet_regatta(season="s26", slug="test-fleet", name="Test Fleet", start="2026-05-01"):
    def team(place, school):
        div = DivisionResult(
            total=10,
            races=[RaceScore(race_num=1, points=place), RaceScore(race_num=2, points=place)],
        )
        return TeamResult(
            place=place,
            school=school.title(),
            school_short=school,
            school_slug=school,
            school_url=f"/schools/{school}/{season}/",
            team_name=school.title(),
            total=place * 10,
            divisions={"A": div},
        )

    return RegattaScores(
        name=name,
        season=season,
        slug=slug,
        scoring_type="divisional",
        races_sailed={"A": 2},
        is_final=True,
        regatta_start=start,
        teams=[team(1, "navy"), team(2, "yale")],
    )


def _team_regatta():
    def team(place, school):
        return TeamRaceTeam(
            place=place,
            school=school.title(),
            school_short=school,
            school_slug=school,
            school_url=f"/schools/{school}/s26/",
            team_name=school.title(),
            total_wins=5,
            total_losses=1,
            total_ties=0,
            win_pct=0.83,
            rounds=[],
        )

    return TeamRegattaScores(
        name="Test Team",
        season="s26",
        slug="test-team",
        scoring_type="team",
        is_final=True,
        regatta_start="2026-05-02",
        teams=[team(1, "harvard"), team(2, "navy")],
    )


def _dataset():
    regs = [_fleet_regatta(), _team_regatta()]
    srs = [
        SailorRaceFinish(
            "s26", "test-fleet", "jane-doe", "Jane Doe", "navy", "Navy", "A", 1, 1, "skipper"
        ),
        SailorRaceFinish(
            "s26", "test-fleet", "jane-doe", "Jane Doe", "navy", "Navy", "A", 2, 1, "skipper"
        ),
        SailorRaceFinish(
            "s26", "test-fleet", "bob-roe", "Bob Roe", "yale", "Yale", "A", 1, 2, "skipper"
        ),
    ]
    return Dataset.from_regattas(regs, srs)


def test_projections():
    d = _dataset()
    assert len(d) == 2
    assert len(d.results) == 4  # 2 fleet + 2 team teams
    assert len(d.finishes) == 4  # 2 fleet teams x 2 races (team racing has none)
    assert len(d.sailor_races) == 3
    # team results carry place, total 0
    team_res = [r for r in d.results if r.scoring_type == "team"]
    assert {r.school_slug for r in team_res} == {"harvard", "navy"}
    assert all(r.total is None for r in team_res)


def test_context_enrichment():
    d = _dataset()
    jane = [s for s in d.sailor_races if s.sailor_slug == "jane-doe"][0]
    assert jane.regatta_name == "Test Fleet"
    assert jane.start_time == "2026-05-01"


def test_fleet_team_filters():
    d = _dataset()
    assert len(d.fleet()) == 1
    assert len(d.team()) == 1
    assert d.fleet().regattas[0].slug == "test-fleet"
    # filters narrow projections too
    assert all(f.regatta_slug == "test-fleet" for f in d.fleet().finishes)
    assert d.team().sailor_races == []  # no team sailor-races in fixture


def test_school_and_sailor_filters():
    d = _dataset()
    navy = d.school("navy")
    assert {r.regatta_slug for r in navy.results} == {"test-fleet", "test-team"}
    assert all(r.school_slug == "navy" for r in navy.results)
    jane = d.sailor("jane-doe")
    assert len(jane.sailor_races) == 2
    assert {s.regatta_slug for s in jane.sailor_races} == {"test-fleet"}


def _cross_season_same_slug_dataset():
    # Two fleet regattas sharing a slug ("hood") across seasons — annual
    # regattas like this are common, so the dataset must key by (season, slug)
    # rather than slug alone or same-slug regattas collide.
    f24 = _fleet_regatta(season="f24", slug="hood", name="Hood Trophy 2024", start="2024-10-01")
    s25 = _fleet_regatta(season="s25", slug="hood", name="Hood Trophy 2025", start="2025-04-01")
    srs = [
        SailorRaceFinish(
            "f24", "hood", "jane-doe", "Jane Doe", "navy", "Navy", "A", 1, 1, "skipper"
        ),
        SailorRaceFinish(
            "s25", "hood", "jane-doe", "Jane Doe", "navy", "Navy", "A", 1, 3, "skipper"
        ),
    ]
    return Dataset.from_regattas([f24, s25], srs)


def test_cross_season_same_slug_enrichment():
    d = _cross_season_same_slug_dataset()
    f24_row = [s for s in d.sailor_races if s.season == "f24"][0]
    s25_row = [s for s in d.sailor_races if s.season == "s25"][0]
    assert f24_row.regatta_name == "Hood Trophy 2024"
    assert f24_row.start_time == "2024-10-01"
    assert s25_row.regatta_name == "Hood Trophy 2025"
    assert s25_row.start_time == "2025-04-01"


def test_cross_season_same_slug_narrowing():
    d = _cross_season_same_slug_dataset()
    # both same-slug regattas survive fleet() narrowing, distinguished by season
    fleet = d.fleet()
    assert len(fleet.regattas) == 2
    assert {(r.season, r.slug) for r in fleet.regattas} == {("f24", "hood"), ("s25", "hood")}
    # school() keeps both seasons' rows for a school that raced in both
    navy = d.school("navy")
    assert {(r.season, r.regatta_slug) for r in navy.results} == {
        ("f24", "hood"),
        ("s25", "hood"),
    }
    # sailor() narrows to the regattas actually sailed, season-scoped
    jane = d.sailor("jane-doe")
    assert len(jane.sailor_races) == 2
    assert {(r.season, r.slug) for r in jane.regattas} == {("f24", "hood"), ("s25", "hood")}


def test_frames():
    import pytest

    pytest.importorskip("pandas")
    d = _dataset()
    rf = d.results_frame()
    assert rf.shape[0] == 4 and "place" in rf.columns
    assert d.sailor_races_frame().shape[0] == 3
    assert d.finishes_frame().shape[0] == 4


def test_results_frame_team_total_is_nan():
    import pandas as pd
    import pytest

    pytest.importorskip("pandas")
    d = _dataset()
    rf = d.results_frame()
    team_rows = rf[rf["scoring_type"] == "team"]
    assert len(team_rows) == 2
    assert team_rows["total"].isna().all()
    # fleet rows keep their real totals
    fleet_rows = rf[rf["scoring_type"] != "team"]
    assert not fleet_rows["total"].isna().any()
    assert pd.api.types.is_numeric_dtype(rf["total"])


def test_start_time_is_datetime_in_frames():
    import pytest

    pytest.importorskip("pandas")
    import pandas as pd

    d = _dataset()
    rf = d.results_frame()
    assert pd.api.types.is_datetime64_any_dtype(rf["start_time"])
    srf = d.sailor_races_frame()
    assert pd.api.types.is_datetime64_any_dtype(srf["start_time"])


def test_penalty_threading_fleet_finish():
    # A DNF scored fleet+1 should carry its penalty code into Finish, not just
    # the inflated points total.
    div = DivisionResult(
        total=10,
        races=[
            RaceScore(race_num=1, points=1),
            RaceScore(race_num=2, points=6, penalty="DNF", penalty_formula="Fleet + 1"),
        ],
    )
    team = TeamResult(
        place=1,
        school="Navy",
        school_short="navy",
        school_slug="navy",
        school_url="/schools/navy/s26/",
        team_name="Navy",
        total=7,
        divisions={"A": div},
    )
    reg = RegattaScores(
        name="Penalty Test",
        season="s26",
        slug="penalty-test",
        scoring_type="divisional",
        races_sailed={"A": 2},
        is_final=True,
        teams=[team],
    )
    d = Dataset.from_regattas([reg], [])
    by_race = {f.race_num: f for f in d.finishes}
    assert by_race[1].penalty is None
    assert by_race[2].penalty == "DNF"


def test_regattas_frame_shape_and_metas():
    import pytest

    pytest.importorskip("pandas")
    from scraper.parsers.regatta import RegattaMeta

    d = _dataset()
    meta = RegattaMeta(
        name="Test Fleet",
        season="s26",
        nick="test-fleet",
        scoring="standard",
        participant="coed",
        status="final",
        hosts=["Navy"],
        boat="FJ",
        type="Conference Championship Regatta",
    )
    d._metas = {("s26", "test-fleet"): meta}
    rf = d.regattas_frame()
    assert rf.shape[0] == 2
    assert set(rf.columns) == {
        "season",
        "slug",
        "name",
        "scoring_type",
        "host",
        "regatta_start",
        "regatta_end",
        "is_final",
        "team_count",
        "boat",
        "participant",
        "regatta_type",
    }
    fleet_row = rf[rf["slug"] == "test-fleet"].iloc[0]
    assert fleet_row["team_count"] == 2
    assert fleet_row["boat"] == "FJ"
    assert fleet_row["participant"] == "coed"
    assert fleet_row["regatta_type"] == "Conference Championship Regatta"
    team_row = rf[rf["slug"] == "test-team"].iloc[0]
    assert team_row["boat"] == ""  # no meta captured for this regatta
    import pandas as pd

    assert pd.api.types.is_datetime64_any_dtype(rf["regatta_start"])


def test_schools_and_sailors_properties():
    d = _dataset()
    assert d.schools == ["harvard", "navy", "yale"]
    assert d.sailors == ["bob-roe", "jane-doe"]
