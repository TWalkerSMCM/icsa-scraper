"""
Orchestration tests for scraper.head_to_head.head_to_head() — real sailor
profile pages, joined through the real Client + cache + parser stack (see
tests/conftest.py). No real network access.
"""

from __future__ import annotations

from conftest import fleet_full_scores_page, make_client, overview_page, sailors_page
from scraper.head_to_head import head_to_head


def _profile_page(rows):
    """rows: list of (href, name, host, datetime_attr, date_text, roles, placement_html)."""
    trs = ""
    for href, name, host, dt, date_text, roles, placement_html in rows:
        trs += (
            '<tr itemprop="event">'
            f'<td><a itemprop="url" href="{href}"><span itemprop="name">{name}</span></a></td>'
            f"<td>{host}</td>"
            f'<td><time itemprop="startDate" datetime="{dt}">{date_text}</time></td>'
            f"<td>{roles}</td>"
            f'<td><span class="sailor-placement-container">{placement_html}</span></td>'
            "</tr>"
        )
    return (
        '<html><body><table class="participation-table">'
        f"<tr><th>Name</th></tr>{trs}</table></body></html>"
    )


def test_head_to_head_shared_and_tallies(tmp_path):
    # Two regatta-divisions in common ("hood" A and "twin" A), plus one
    # unshared regatta each (alice has "match-cup", bob has "spring-invite").
    alice_html = _profile_page(
        [
            (
                "/s26/hood/",
                "Hood",
                "MIT",
                "2026-05-21",
                "May 21",
                "Skipper",
                '<a href="/s26/hood/A/">2/18 (A Div)</a>',
            ),
            (
                "/s25/twin/",
                "Twin State",
                "Dartmouth",
                "2025-04-12",
                "Apr 12",
                "Skipper",
                '<a href="/s25/twin/A/">7/18 (A Div)</a>',
            ),
            (
                "/f25/match-cup/",
                "Match Cup",
                "Navy",
                "2025-11-15",
                "Nov 15",
                "Skipper",
                '<a href="/f25/match-cup/full-scores/">1/10</a>',
            ),
        ]
    )
    bob_html = _profile_page(
        [
            (
                "/s26/hood/",
                "Hood",
                "MIT",
                "2026-05-21",
                "May 21",
                "Skipper",
                '<a href="/s26/hood/A/">5/18 (A Div)</a>',
            ),
            (
                "/s25/twin/",
                "Twin State",
                "Dartmouth",
                "2025-04-12",
                "Apr 12",
                "Skipper",
                '<a href="/s25/twin/A/">3/18 (A Div)</a>',
            ),
            (
                "/s26/spring-invite/",
                "Spring Invite",
                "Yale",
                "2026-04-01",
                "Apr 1",
                "Skipper",
                '<a href="/s26/spring-invite/A/">2/10 (A Div)</a>',
            ),
        ]
    )
    pages = {
        "/sailors/alice/": alice_html,
        "/sailors/bob/": bob_html,
    }
    client = make_client(pages, tmp_path)
    h = head_to_head("alice", "bob", client=client)

    assert {(s.season, s.slug, s.division) for s in h.shared} == {
        ("s26", "hood", "A"),
        ("s25", "twin", "A"),
    }
    # hood: alice 2nd, bob 5th -> alice ahead. twin: alice 7th, bob 3rd -> bob ahead.
    assert h.a_ahead == 1
    assert h.b_ahead == 1


def test_head_to_head_races_loads_only_shared_regattas(tmp_path):
    alice_html = _profile_page(
        [
            (
                "/s26/hood/",
                "Hood",
                "MIT",
                "2026-05-21",
                "May 21",
                "Skipper",
                '<a href="/s26/hood/A/">1/2 (A Div)</a>',
            )
        ]
    )
    bob_html = _profile_page(
        [
            (
                "/s26/hood/",
                "Hood",
                "MIT",
                "2026-05-21",
                "May 21",
                "Skipper",
                '<a href="/s26/hood/A/">2/2 (A Div)</a>',
            )
        ]
    )
    sp = sailors_page(
        [
            {
                "school": "Navy",
                "school_url": "/schools/navy/s26/",
                "team_name": "Navy",
                "divisions": {"A": (1, "Alice", "/sailors/alice/")},
            },
            {
                "school": "MIT",
                "school_url": "/schools/mit/s26/",
                "team_name": "MIT",
                "divisions": {"A": (2, "Bob", "/sailors/bob/")},
            },
        ]
    )
    pages = {
        "/sailors/alice/": alice_html,
        "/sailors/bob/": bob_html,
        "/s26/hood/": overview_page("s26", "hood", "Hood", has_sailors=True),
        "/s26/hood/full-scores/": fleet_full_scores_page(2),
        "/s26/hood/sailors/": sp,
    }
    client = make_client(pages, tmp_path)
    h = head_to_head("alice", "bob", client=client, races=True)

    assert [(r.division, r.race_num, r.place_a, r.place_b) for r in h.races] == [
        ("A", 1, 1, 2),
        ("A", 2, 1, 2),
    ]
    assert h.a_race_wins == 2
    assert h.b_race_wins == 0


def test_head_to_head_cross_season_same_slug_not_conflated(tmp_path):
    """Regression: both sailors sailed a regatta slugged "hood" in f24 AND in
    s25 — encounters must carry the correct season and never mix the two."""
    alice_html = _profile_page(
        [
            (
                "/f24/hood/",
                "Hood 2024",
                "MIT",
                "2024-11-01",
                "Nov 1",
                "Skipper",
                '<a href="/f24/hood/A/">1/2 (A Div)</a>',
            ),
            (
                "/s25/hood/",
                "Hood 2025",
                "MIT",
                "2025-05-01",
                "May 1",
                "Skipper",
                '<a href="/s25/hood/A/">2/2 (A Div)</a>',
            ),
        ]
    )
    bob_html = _profile_page(
        [
            (
                "/f24/hood/",
                "Hood 2024",
                "MIT",
                "2024-11-01",
                "Nov 1",
                "Skipper",
                '<a href="/f24/hood/A/">2/2 (A Div)</a>',
            ),
            (
                "/s25/hood/",
                "Hood 2025",
                "MIT",
                "2025-05-01",
                "May 1",
                "Skipper",
                '<a href="/s25/hood/A/">1/2 (A Div)</a>',
            ),
        ]
    )
    sp = sailors_page(
        [
            {
                "school": "Navy",
                "school_url": "/schools/navy/s26/",
                "team_name": "Navy",
                "divisions": {"A": (1, "Alice", "/sailors/alice/")},
            },
            {
                "school": "MIT",
                "school_url": "/schools/mit/s26/",
                "team_name": "MIT",
                "divisions": {"A": (2, "Bob", "/sailors/bob/")},
            },
        ]
    )
    pages = {
        "/sailors/alice/": alice_html,
        "/sailors/bob/": bob_html,
        "/f24/hood/": overview_page("f24", "hood", "Hood 2024", has_sailors=True),
        "/f24/hood/full-scores/": fleet_full_scores_page(2),
        "/f24/hood/sailors/": sp,
        "/s25/hood/": overview_page("s25", "hood", "Hood 2025", has_sailors=True),
        "/s25/hood/full-scores/": fleet_full_scores_page(2),
        "/s25/hood/sailors/": sp,
    }
    client = make_client(pages, tmp_path)
    h = head_to_head("alice", "bob", client=client, races=True)

    assert {(s.season, s.slug) for s in h.shared} == {("f24", "hood"), ("s25", "hood")}
    by_season = {r.season: r for r in h.races}
    assert set(by_season) == {"f24", "s25"}
    # Both seasons use the same underlying full-scores fixture (Navy=alice
    # 1st, MIT=bob 2nd every race) — the regression this pins is that the two
    # same-slug regattas aren't merged/dropped, not that placements differ.
    assert by_season["f24"].place_a == 1 and by_season["f24"].place_b == 2
    assert by_season["s25"].place_a == 1 and by_season["s25"].place_b == 2
    assert len(h.races) == 4  # 2 races each season, not conflated
    assert {r.race_num for r in h.races if r.season == "f24"} == {1, 2}
    assert {r.race_num for r in h.races if r.season == "s25"} == {1, 2}
