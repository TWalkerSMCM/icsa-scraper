from scraper.views import HeadToHead, RaceEncounter, SharedRegatta


def _head_to_head():
    shared = [
        SharedRegatta(
            season="s26",
            slug="hood",
            regatta_name="Hood Trophy",
            division="A",
            place_a=1,
            place_b=2,
            fleet_size=10,
        ),
        SharedRegatta(
            season="s26",
            slug="oberg",
            regatta_name="Oberg Trophy",
            division="B",
            place_a=3,
            place_b=1,
            fleet_size=8,
        ),
    ]
    races = [
        RaceEncounter(
            season="s26", regatta_slug="hood", division="A", race_num=1, place_a=1, place_b=2
        ),
        RaceEncounter(
            season="s26", regatta_slug="hood", division="A", race_num=2, place_a=4, place_b=3
        ),
    ]
    return HeadToHead(a="jane-doe", b="bob-roe", shared=shared, races=races)


def test_shared_frame():
    import pytest

    pytest.importorskip("pandas")
    h2h = _head_to_head()
    df = h2h.shared_frame()
    assert df.shape[0] == 2
    assert set(df.columns) == {
        "season",
        "slug",
        "regatta_name",
        "division",
        "place_a",
        "place_b",
        "fleet_size",
    }


def test_races_frame():
    import pytest

    pytest.importorskip("pandas")
    h2h = _head_to_head()
    df = h2h.races_frame()
    assert df.shape[0] == 2
    assert set(df.columns) == {
        "season",
        "regatta_slug",
        "division",
        "race_num",
        "place_a",
        "place_b",
    }


def test_a_ahead_and_b_ahead_ignore_unplaced_sailor():
    """A shared regatta-division where either sailor is unplaced (place is
    None) must count toward neither a_ahead nor b_ahead."""
    shared = [
        SharedRegatta(
            season="s26",
            slug="a-unplaced",
            regatta_name="A",
            division="A",
            place_a=None,
            place_b=3,
            fleet_size=10,
        ),
        SharedRegatta(
            season="s26",
            slug="b-unplaced",
            regatta_name="B",
            division="A",
            place_a=2,
            place_b=None,
            fleet_size=10,
        ),
        SharedRegatta(
            season="s26",
            slug="both-unplaced",
            regatta_name="C",
            division="A",
            place_a=None,
            place_b=None,
            fleet_size=10,
        ),
    ]
    h2h = HeadToHead(a="jane-doe", b="bob-roe", shared=shared, races=[])
    assert h2h.a_ahead == 0
    assert h2h.b_ahead == 0


def test_a_ahead_and_b_ahead_ignore_ties():
    """Equal places (a tie) must count toward neither a_ahead nor b_ahead."""
    shared = [
        SharedRegatta(
            season="s26",
            slug="tied",
            regatta_name="Tied",
            division="A",
            place_a=4,
            place_b=4,
            fleet_size=10,
        ),
    ]
    h2h = HeadToHead(a="jane-doe", b="bob-roe", shared=shared, races=[])
    assert h2h.a_ahead == 0
    assert h2h.b_ahead == 0
