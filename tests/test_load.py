"""
Orchestration tests for scraper.dataset.load() / load_regattas() — the full
Client -> cache -> parser -> assemble -> Dataset pipeline, driven end-to-end
against an httpx.MockTransport (see tests/conftest.py). No real network access.
"""

from __future__ import annotations

from conftest import (
    empty_full_scores_page,
    fleet_full_scores_page,
    make_client,
    overview_page,
    sailors_page,
    season_index_page,
    team_all_races_page,
)
from scraper import cache
from scraper.dataset import load

# ---------------------------------------------------------------------------
# Golden end-to-end
# ---------------------------------------------------------------------------


def _cactus_cup_pages(n_races=3, has_sailors=True):
    pages = {
        "/s26/": season_index_page([("cactus-cup", "Cactus Cup")]),
        "/s26/cactus-cup/": overview_page(
            "s26", "cactus-cup", "Cactus Cup", has_sailors=has_sailors
        ),
        "/s26/cactus-cup/full-scores/": fleet_full_scores_page(n_races),
    }
    if has_sailors:
        pages["/s26/cactus-cup/sailors/"] = sailors_page(
            [
                {
                    "school": "Navy",
                    "school_url": "/schools/navy/s26/",
                    "team_name": "Navy",
                    "divisions": {
                        "A": (1, "Jane Doe", "/sailors/jane-doe/"),
                        "B": (1, "Bob Roe", "/sailors/bob-roe/"),
                    },
                },
                {
                    "school": "MIT",
                    "school_url": "/schools/mit/s26/",
                    "team_name": "MIT",
                    "divisions": {
                        "A": (2, "Sam Sail", "/sailors/sam-sail/"),
                        "B": (2, "Ann Ahoy", "/sailors/ann-ahoy/"),
                    },
                },
            ]
        )
    return pages


def test_golden_end_to_end(tmp_path):
    client = make_client(_cactus_cup_pages(n_races=3), tmp_path)
    data = load("s26", client=client, workers=1)

    assert len(data.regattas) == 1
    assert len(data.results) == 2  # Navy + MIT
    assert len(data.finishes) == 2 * 2 * 3  # 2 teams x 2 divisions x 3 races
    assert len(data.sailor_races) == 2 * 2 * 3  # 4 skippers x 3 races (whole division sailed)

    navy_result = next(r for r in data.results if r.school_slug == "navy")
    assert navy_result.place == 1
    assert navy_result.total == 6  # 2 divisions x 3 races x 1 pt

    jane = next(s for s in data.sailor_races if s.sailor_slug == "jane-doe")
    assert jane.division == "A" and jane.race_num in {1, 2, 3} and jane.place == 1
    # enrichment: regatta_name/start_time filled in from the assembled regatta
    assert jane.regatta_name == "Test 2-Div Regatta"
    assert jane.start_time == "2026-03-06"

    fleet_finish = next(f for f in data.finishes if f.school_slug == "navy" and f.division == "A")
    assert fleet_finish.place == 1


def test_golden_end_to_end_enriches_results_context(tmp_path):
    client = make_client(_cactus_cup_pages(n_races=3), tmp_path)
    data = load("s26", client=client, workers=1)
    assert all(r.regatta_name == "Test 2-Div Regatta" for r in data.results)
    assert all(r.start_time == "2026-03-06" for r in data.results)


# ---------------------------------------------------------------------------
# The e2e delta test — snapshot vs refresh semantics
# ---------------------------------------------------------------------------


def test_snapshot_then_refresh_delta(tmp_path):
    pages_v1 = {
        "/s26/": season_index_page([("cactus-cup", "Cactus Cup")]),
        "/s26/cactus-cup/": overview_page("s26", "cactus-cup", "Cactus Cup", has_sailors=False),
        "/s26/cactus-cup/full-scores/": fleet_full_scores_page(3),
    }

    # Poll 1: 3 races, populate the cache.
    reqs1: list[str] = []
    client1 = make_client(pages_v1, tmp_path, requests=reqs1)
    d1 = load("s26", client=client1, sailors=False, workers=1)
    client1.close()

    assert {f.race_num for f in d1.finishes} == {1, 2, 3}
    assert len(d1.finishes) == 2 * 2 * 3  # 2 teams x 2 divisions x 3 races
    for path in (
        "/s26/",
        "/s26/cactus-cup/",
        "/s26/cactus-cup/full-scores/",
    ):
        url = f"https://scores.collegesailing.org{path}"
        assert cache.has(url, cache_dir=tmp_path)

    # The site now has 5 races (2 new).
    pages_v2 = dict(pages_v1)
    pages_v2["/s26/cactus-cup/full-scores/"] = fleet_full_scores_page(5)

    # Poll 2 with a FRESH Client pointed at the same cache dir: plain load()
    # is a snapshot — still 3 races, served entirely from cache. No new
    # requests should hit the transport for the cached pages.
    reqs2: list[str] = []
    client2 = make_client(pages_v2, tmp_path, requests=reqs2)
    d2 = load("s26", client=client2, sailors=False, workers=1)
    client2.close()

    assert {f.race_num for f in d2.finishes} == {1, 2, 3}
    assert len(d2.finishes) == 2 * 2 * 3
    assert reqs2 == []  # everything served from disk cache

    # Poll 3 with refresh=True: now sees 5 races.
    reqs3: list[str] = []
    client3 = make_client(pages_v2, tmp_path, requests=reqs3)
    d3 = load("s26", client=client3, sailors=False, workers=1, refresh=True)
    client3.close()

    assert {f.race_num for f in d3.finishes} == {1, 2, 3, 4, 5}
    assert len(d3.finishes) == 2 * 2 * 5
    assert set(reqs3) == {
        "/s26/",
        "/s26/cactus-cup/",
        "/s26/cactus-cup/full-scores/",
    }

    # The original 3 races are unchanged; the 2 new ones have correct places.
    navy_a = sorted(
        (f.race_num, f.place) for f in d3.finishes if f.school_slug == "navy" and f.division == "A"
    )
    assert navy_a == [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1)]
    mit_a = sorted(
        (f.race_num, f.place) for f in d3.finishes if f.school_slug == "mit" and f.division == "A"
    )
    assert mit_a == [(1, 2), (2, 2), (3, 2), (4, 2), (5, 2)]


# ---------------------------------------------------------------------------
# Routing / fallbacks
# ---------------------------------------------------------------------------


def test_missing_overview_skips_regatta_but_keeps_others(tmp_path):
    pages = {
        "/s26/": season_index_page([("ghost-regatta", "Ghost"), ("cactus-cup", "Cactus Cup")]),
        # no /s26/ghost-regatta/ overview page -> 404
        "/s26/cactus-cup/": overview_page("s26", "cactus-cup", "Cactus Cup", has_sailors=False),
        "/s26/cactus-cup/full-scores/": fleet_full_scores_page(2),
    }
    client = make_client(pages, tmp_path)
    data = load("s26", client=client, sailors=False, workers=1)
    assert [r.slug for r in data.regattas] == ["cactus-cup"]


def test_missing_full_scores_skips_regatta(tmp_path):
    pages = {
        "/s26/": season_index_page([("cactus-cup", "Cactus Cup")]),
        "/s26/cactus-cup/": overview_page("s26", "cactus-cup", "Cactus Cup", has_sailors=False),
        # no full-scores page -> 404
    }
    client = make_client(pages, tmp_path)
    data = load("s26", client=client, sailors=False, workers=1)
    assert data.regattas == []


def test_empty_full_scores_table_skips_regatta(tmp_path):
    pages = {
        "/s26/": season_index_page([("cactus-cup", "Cactus Cup")]),
        "/s26/cactus-cup/": overview_page("s26", "cactus-cup", "Cactus Cup", has_sailors=False),
        "/s26/cactus-cup/full-scores/": empty_full_scores_page(),
    }
    client = make_client(pages, tmp_path)
    data = load("s26", client=client, sailors=False, workers=1)
    assert data.regattas == []


def test_team_racing_regatta_routes_to_all_page(tmp_path):
    pages = {
        "/s26/": season_index_page([("team-cup", "Team Cup")]),
        "/s26/team-cup/": overview_page(
            "s26", "team-cup", "Team Cup", has_all=True, has_sailors=False
        ),
        "/s26/team-cup/all/": team_all_races_page(),
    }
    client = make_client(pages, tmp_path)
    data = load("s26", client=client, sailors=False, workers=1)
    assert len(data.regattas) == 1
    assert data.regattas[0].scoring_type == "team"


def test_only_slugs_skips_season_index_fetch(tmp_path):
    pages = {
        # deliberately no "/s26/" season index page
        "/s26/cactus-cup/": overview_page("s26", "cactus-cup", "Cactus Cup", has_sailors=False),
        "/s26/cactus-cup/full-scores/": fleet_full_scores_page(2),
    }
    reqs: list[str] = []
    client = make_client(pages, tmp_path, requests=reqs)
    data = load("s26", only=["cactus-cup"], client=client, sailors=False, workers=1)
    assert len(data.regattas) == 1
    assert "/s26/" not in reqs


def test_sailors_false_skips_sailors_page_fetch(tmp_path):
    pages = _cactus_cup_pages(n_races=2, has_sailors=True)
    reqs: list[str] = []
    client = make_client(pages, tmp_path, requests=reqs)
    data = load("s26", client=client, sailors=False, workers=1)
    assert len(data.regattas) == 1
    assert data.sailor_races == []
    assert not any(p.endswith("/sailors/") for p in reqs)


def test_multi_season_walks_both_indexes(tmp_path):
    pages = {
        "/f24/": season_index_page([("fall-opener", "Fall Opener")]),
        "/f24/fall-opener/": overview_page("f24", "fall-opener", "Fall Opener", has_sailors=False),
        "/f24/fall-opener/full-scores/": fleet_full_scores_page(2),
        "/s25/": season_index_page([("spring-opener", "Spring Opener")]),
        "/s25/spring-opener/": overview_page(
            "s25", "spring-opener", "Spring Opener", has_sailors=False
        ),
        "/s25/spring-opener/full-scores/": fleet_full_scores_page(2),
    }
    client = make_client(pages, tmp_path)
    data = load(["f24", "s25"], client=client, sailors=False, workers=1)
    assert {(r.season, r.slug) for r in data.regattas} == {
        ("f24", "fall-opener"),
        ("s25", "spring-opener"),
    }


# ---------------------------------------------------------------------------
# Concurrency ordering
# ---------------------------------------------------------------------------


def test_load_order_is_stable_regardless_of_fetch_completion_order(tmp_path):
    slugs = ["reg0", "reg1", "reg2", "reg3"]
    pages = {"/s26/": season_index_page([(s, s) for s in slugs])}
    for i, slug in enumerate(slugs):
        pages[f"/s26/{slug}/"] = overview_page("s26", slug, slug, has_sailors=False)
        pages[f"/s26/{slug}/full-scores/"] = fleet_full_scores_page(1)

    def delay_fn(path: str) -> float:
        # Later-listed regattas' pages return faster than earlier ones, so
        # completion order is the reverse of the season-index listing order.
        for i, slug in enumerate(slugs):
            if f"/{slug}/" in path:
                return 0.03 * (len(slugs) - 1 - i)
        return 0.0

    client = make_client(pages, tmp_path, delay_fn=delay_fn)
    data = load("s26", client=client, sailors=False, workers=4)

    assert [r.slug for r in data.regattas] == slugs


# ---------------------------------------------------------------------------
# progress=True
# ---------------------------------------------------------------------------


def test_progress_bar_updates_per_regatta(tmp_path, monkeypatch):
    """progress=True drives the bar once per regatta and closes it."""
    from scraper import dataset

    events = []

    class Bar:
        def __init__(self, total):
            events.append(("total", total))

        def update(self, n=1):
            events.append(("update", n))

        def close(self):
            events.append(("close",))

    monkeypatch.setattr(dataset, "_make_bar", Bar)

    pages = {
        "/s26/": season_index_page([("cactus-cup", "Cactus Cup"), ("hood", "Hood Trophy")]),
        "/s26/cactus-cup/": overview_page("s26", "cactus-cup", "Cactus Cup", has_sailors=False),
        "/s26/cactus-cup/full-scores/": fleet_full_scores_page(2),
        "/s26/hood/": overview_page("s26", "hood", "Hood Trophy", has_sailors=False),
        "/s26/hood/full-scores/": fleet_full_scores_page(2),
    }
    with make_client(pages, tmp_path) as client:
        load("s26", client=client, sailors=False, workers=1, progress=True)

    assert events[0] == ("total", 2)
    assert events.count(("update", 1)) == 2
    assert events[-1] == ("close",)


def test_plain_bar_fallback_writes_stderr(capsys):
    """_PlainBar (the no-tqdm fallback) counts on stderr and is closeable."""
    from scraper.dataset import _PlainBar

    bar = _PlainBar(3)
    bar.update()
    bar.update()
    bar.close()
    err = capsys.readouterr().err
    assert "2/3 regattas" in err
