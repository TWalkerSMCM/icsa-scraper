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
