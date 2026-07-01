from scraper.models import RegattaScores, TeamResult, DivisionResult, RaceScore
from scraper.models import TeamRegattaScores, TeamRaceTeam
from scraper.views import SailorRaceFinish
from scraper.dataset import Dataset


def _fleet_regatta():
    def team(place, school):
        div = DivisionResult(total=10, races=[RaceScore(race_num=1, points=place),
                                              RaceScore(race_num=2, points=place)])
        return TeamResult(place=place, school=school.title(), school_short=school,
                          school_slug=school, school_url=f"/schools/{school}/s26/",
                          team_name=school.title(), total=place * 10,
                          divisions={"A": div})
    return RegattaScores(
        name="Test Fleet", season="s26", slug="test-fleet", scoring_type="divisional",
        races_sailed={"A": 2}, is_final=True, regatta_start="2026-05-01",
        teams=[team(1, "navy"), team(2, "yale")],
    )


def _team_regatta():
    def team(place, school):
        return TeamRaceTeam(place=place, school=school.title(), school_short=school,
                            school_slug=school, school_url=f"/schools/{school}/s26/",
                            team_name=school.title(), total_wins=5, total_losses=1,
                            total_ties=0, win_pct=0.83, rounds=[])
    return TeamRegattaScores(
        name="Test Team", season="s26", slug="test-team", scoring_type="team",
        is_final=True, regatta_start="2026-05-02",
        teams=[team(1, "harvard"), team(2, "navy")],
    )


def _dataset():
    regs = [_fleet_regatta(), _team_regatta()]
    srs = [
        SailorRaceFinish("s26", "test-fleet", "jane-doe", "Jane Doe", "navy", "Navy",
                         "A", 1, 1, "skipper"),
        SailorRaceFinish("s26", "test-fleet", "jane-doe", "Jane Doe", "navy", "Navy",
                         "A", 2, 1, "skipper"),
        SailorRaceFinish("s26", "test-fleet", "bob-roe", "Bob Roe", "yale", "Yale",
                         "A", 1, 2, "skipper"),
    ]
    return Dataset.from_regattas(regs, srs)


def test_projections():
    d = _dataset()
    assert len(d) == 2
    assert len(d.results) == 4                 # 2 fleet + 2 team teams
    assert len(d.finishes) == 4                # 2 fleet teams x 2 races (team racing has none)
    assert len(d.sailor_races) == 3
    # team results carry place, total 0
    team_res = [r for r in d.results if r.scoring_type == "team"]
    assert {r.school_slug for r in team_res} == {"harvard", "navy"}
    assert all(r.total == 0 for r in team_res)


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
    assert d.team().sailor_races == []          # no team sailor-races in fixture


def test_school_and_sailor_filters():
    d = _dataset()
    navy = d.school("navy")
    assert {r.regatta_slug for r in navy.results} == {"test-fleet", "test-team"}
    assert all(r.school_slug == "navy" for r in navy.results)
    jane = d.sailor("jane-doe")
    assert len(jane.sailor_races) == 2
    assert {s.regatta_slug for s in jane.sailor_races} == {"test-fleet"}


def test_frames():
    d = _dataset()
    rf = d.results_frame()
    assert rf.shape[0] == 4 and "place" in rf.columns
    assert d.sailor_races_frame().shape[0] == 3
    assert d.finishes_frame().shape[0] == 4
