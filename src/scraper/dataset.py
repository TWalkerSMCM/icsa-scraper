"""
Scrape a season (or several) into memory once, then loop and query.

``load()`` fetches and assembles every regatta into a ``Dataset``; the Dataset
exposes the nested models (``.regattas``) plus flat, pre-joined projections
(``.results``, ``.sailor_races``, ``.finishes``) and chainable filters. This is
the "analysis library" surface — CSR, ELO, and comparisons all sit on top of it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scraper.client import Client

from scraper import urls
from scraper.assemble import fleet_scores, team_scores
from scraper.models import RegattaScores, TeamRegattaScores
from scraper.parsers import regatta as _regatta_parser
from scraper.parsers import season as _season_parser
from scraper.parsers.regatta import RegattaMeta
from scraper.sailor_races import sailor_races as _sailor_races
from scraper.sailor_races import team_sailor_races as _team_sailor_races
from scraper.views import Finish, Result, SailorRaceFinish

Regatta = RegattaScores | TeamRegattaScores


class Dataset:
    """A queryable collection of assembled regattas.

    Construct via :func:`load`. Filters return a new, narrowed ``Dataset`` so
    they chain: ``data.fleet().school("navy").results``.
    """

    def __init__(
        self,
        regattas: list[Regatta],
        results: list[Result],
        finishes: list[Finish],
        sailor_races: list[SailorRaceFinish],
        metas: dict[tuple[str, str], RegattaMeta] | None = None,
    ) -> None:
        self.regattas = regattas
        self.results = results
        self.finishes = finishes
        self.sailor_races = sailor_races
        # Overview-only metadata, keyed (season, slug); carried through filters
        # so regattas_frame() stays enriched after chaining (e.g. data.fleet()).
        self._metas = metas or {}

    def __iter__(self) -> Iterator[Regatta]:
        return iter(self.regattas)

    def __len__(self) -> int:
        return len(self.regattas)

    def __repr__(self) -> str:
        return (
            f"Dataset({len(self.regattas)} regattas, {len(self.results)} results, "
            f"{len(self.sailor_races)} sailor-races)"
        )

    # ── construction ──────────────────────────────────────────────────────────
    @classmethod
    def from_regattas(
        cls,
        regattas: list[Regatta],
        sailor_races: list[SailorRaceFinish],
        metas: dict[tuple[str, str], RegattaMeta] | None = None,
    ) -> Dataset:
        """Derive the flat projections from assembled regattas.

        ``metas`` ((season, regatta_slug) → RegattaMeta) supplies overview-only
        context (boat, participant, type) used to enrich sailor-race rows for ELO.
        """
        metas = metas or {}
        results: list[Result] = []
        finishes: list[Finish] = []

        for reg in regattas:
            if isinstance(reg, TeamRegattaScores):
                for tt in reg.teams:
                    results.append(
                        Result(
                            season=reg.season,
                            regatta_slug=reg.slug,
                            regatta_name=reg.name,
                            scoring_type=reg.scoring_type,
                            school_slug=tt.school_slug,
                            school=tt.school,
                            team_name=tt.team_name,
                            place=tt.place,
                            total=None,
                            is_final=reg.is_final,
                            start_time=reg.regatta_start,
                        )
                    )
            else:
                for t in reg.teams:
                    results.append(
                        Result(
                            season=reg.season,
                            regatta_slug=reg.slug,
                            regatta_name=reg.name,
                            scoring_type=reg.scoring_type,
                            school_slug=t.school_slug,
                            school=t.school,
                            team_name=t.team_name,
                            place=t.place,
                            total=t.total,
                            is_final=reg.is_final,
                            start_time=reg.regatta_start,
                        )
                    )
                    for div, dr in t.divisions.items():
                        for rc in dr.races:
                            finishes.append(
                                Finish(
                                    season=reg.season,
                                    regatta_slug=reg.slug,
                                    school_slug=t.school_slug,
                                    team_name=t.team_name,
                                    division=div,
                                    race_num=rc.race_num,
                                    place=rc.points,
                                    penalty=rc.penalty,
                                )
                            )

        # Enrich sailor-race rows with regatta context.
        reg_by_key = {(r.season, r.slug): r for r in regattas}
        for sr in sailor_races:
            rr = reg_by_key.get((sr.season, sr.regatta_slug))
            if rr is not None:
                sr.regatta_name = rr.name
                sr.start_time = rr.regatta_start
            meta = metas.get((sr.season, sr.regatta_slug))
            if meta is not None:
                sr.boat = meta.boat
                sr.participant = meta.participant
                sr.regatta_type = meta.type
                if meta.start_time:
                    sr.start_time = meta.start_time  # ISO datetime beats date-only

        return cls(regattas, results, finishes, sailor_races, metas)

    # ── filters (chainable) ───────────────────────────────────────────────────
    def _narrow(self, keep: set[tuple[str, str]]) -> Dataset:
        return Dataset(
            [r for r in self.regattas if (r.season, r.slug) in keep],
            [r for r in self.results if (r.season, r.regatta_slug) in keep],
            [f for f in self.finishes if (f.season, f.regatta_slug) in keep],
            [s for s in self.sailor_races if (s.season, s.regatta_slug) in keep],
            self._metas,
        )

    def fleet(self) -> Dataset:
        """Only fleet-racing regattas (scoring_type != 'team')."""
        return self._narrow(
            {(r.season, r.slug) for r in self.regattas if getattr(r, "scoring_type", "") != "team"}
        )

    def team(self) -> Dataset:
        """Only team-racing regattas."""
        return self._narrow(
            {(r.season, r.slug) for r in self.regattas if getattr(r, "scoring_type", "") == "team"}
        )

    def school(self, slug: str) -> Dataset:
        """Narrow every projection to one school (regattas it appeared in)."""
        keep = {(r.season, r.regatta_slug) for r in self.results if r.school_slug == slug}
        return Dataset(
            [r for r in self.regattas if (r.season, r.slug) in keep],
            [r for r in self.results if r.school_slug == slug],
            [f for f in self.finishes if f.school_slug == slug],
            [s for s in self.sailor_races if s.school_slug == slug],
            self._metas,
        )

    def sailor(self, slug: str) -> Dataset:
        """Narrow to one sailor's races (and the regattas they sailed)."""
        rows = [s for s in self.sailor_races if s.sailor_slug == slug]
        keep = {(s.season, s.regatta_slug) for s in rows}
        return Dataset(
            [r for r in self.regattas if (r.season, r.slug) in keep],
            [r for r in self.results if (r.season, r.regatta_slug) in keep],
            [f for f in self.finishes if (f.season, f.regatta_slug) in keep],
            rows,
            self._metas,
        )

    # ── discovery ─────────────────────────────────────────────────────────────
    @property
    def schools(self) -> list[str]:
        """Sorted, deduped school slugs that appear in ``results``."""
        return sorted({r.school_slug for r in self.results})

    @property
    def sailors(self) -> list[str]:
        """Sorted, deduped sailor slugs that appear in ``sailor_races``."""
        return sorted({s.sailor_slug for s in self.sailor_races})

    # ── pandas escape hatch ───────────────────────────────────────────────────
    @staticmethod
    def _parse_start_time(df):
        """Coerce a ``start_time`` column (mixed date/datetime strings) to datetime64."""
        import pandas as pd

        if "start_time" in df.columns and not df.empty:
            df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce", format="mixed")
        return df

    def results_frame(self):
        """``results`` as a pandas DataFrame (requires pandas). ``start_time`` is datetime64."""
        import pandas as pd

        return self._parse_start_time(pd.DataFrame([vars(r) for r in self.results]))

    def sailor_races_frame(self):
        """``sailor_races`` as a pandas DataFrame (requires pandas). ``start_time`` is datetime64."""
        import pandas as pd

        return self._parse_start_time(pd.DataFrame([vars(s) for s in self.sailor_races]))

    def finishes_frame(self):
        """``finishes`` as a pandas DataFrame (requires pandas)."""
        import pandas as pd

        return pd.DataFrame([vars(f) for f in self.finishes])

    def regattas_frame(self):
        """One row per regatta: identity, scoring, dates, team_count, and — where a
        ``RegattaMeta`` was captured during load — boat/participant/type enrichment.

        Requires pandas. ``regatta_start`` is datetime64.
        """
        import pandas as pd

        rows = []
        for r in self.regattas:
            meta = self._metas.get((r.season, r.slug))
            rows.append(
                {
                    "season": r.season,
                    "slug": r.slug,
                    "name": r.name,
                    "scoring_type": r.scoring_type,
                    "host": r.host,
                    "regatta_start": r.regatta_start,
                    "regatta_end": r.regatta_end,
                    "is_final": r.is_final,
                    "team_count": len(r.teams),
                    "boat": meta.boat if meta is not None else "",
                    "participant": meta.participant if meta is not None else "",
                    "regatta_type": meta.type if meta is not None else "",
                }
            )
        df = pd.DataFrame(rows)
        if "regatta_start" in df.columns and not df.empty:
            df["regatta_start"] = pd.to_datetime(
                df["regatta_start"], errors="coerce", format="mixed"
            )
        return df


def _load_regatta(
    client: Client,
    season: str,
    slug: str,
    refresh: bool,
    build_sailors: bool,
) -> tuple[Regatta | None, list[SailorRaceFinish], RegattaMeta | None]:
    """Fetch + assemble one regatta and (if ``build_sailors``) its sailor rows.

    Returns ``(regatta_or_None, sailor_rows, meta_or_None)``. The regatta is
    ``None`` when the overview/scores pages are absent or empty.
    """
    overview = client.fetch(urls.regatta(season, slug), refresh=refresh, missing_ok=True)
    if overview is None:
        return None, [], None
    meta = _regatta_parser.parse(overview, season, slug)
    rows: list[SailorRaceFinish] = []

    if meta.scoring == "team":
        all_html = client.fetch(urls.all_races(season, slug), refresh=refresh, missing_ok=True)
        if not all_html:
            return None, [], meta
        fs = client.fetch(urls.full_scores(season, slug), refresh=refresh, missing_ok=True)
        rot = client.fetch(urls.rotations(season, slug), refresh=refresh, missing_ok=True)
        reg: Regatta = team_scores(
            all_html, season=season, slug=slug, full_scores_html=fs, rotations_html=rot
        )
        if build_sailors and meta.has_sailors_page:
            srh = client.fetch(urls.sailors(season, slug), refresh=refresh, missing_ok=True)
            if srh:
                rows = _team_sailor_races(
                    all_html, srh, season=season, slug=slug, sailor_links=meta.sailor_links
                )
        return reg, rows, meta

    fs = client.fetch(urls.full_scores(season, slug), refresh=refresh, missing_ok=True)
    if not fs:
        return None, [], meta
    fleet = fleet_scores(fs, season=season, slug=slug)
    if not fleet.teams:
        return None, [], meta
    if build_sailors:
        srh = None
        if meta.has_sailors_page:
            srh = client.fetch(urls.sailors(season, slug), refresh=refresh, missing_ok=True)
        rows = _sailor_races(fs, srh, season=season, slug=slug)
    return fleet, rows, meta


def _collect(refs, client: Client, refresh: bool, build_sailors: bool, workers: int) -> Dataset:
    refs = list(refs)

    def load_one(ref):
        return _load_regatta(client, ref[0], ref[1], refresh, build_sailors)

    # Fetch regattas concurrently — the work is latency-bound, httpx.Client is
    # thread-safe, and the disk cache writes one file per URL. Results keep input
    # order (executor.map is ordered).
    if workers > 1 and len(refs) > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=workers) as pool:
            triples = list(pool.map(load_one, refs))
    else:
        triples = [load_one(ref) for ref in refs]

    regattas: list[Regatta] = []
    sailor_rows: list[SailorRaceFinish] = []
    metas: dict[tuple[str, str], RegattaMeta] = {}
    for (reg, rows, meta), (_season, slug) in zip(triples, refs):
        if meta is not None:
            metas[(_season, slug)] = meta
        if reg is not None:
            regattas.append(reg)
            sailor_rows.extend(rows)
    return Dataset.from_regattas(regattas, sailor_rows, metas)


def load(
    seasons: str | list[str],
    *,
    only: list[str] | None = None,
    client: Client | None = None,
    refresh: bool = False,
    sailors: bool = True,
    workers: int = 16,
) -> Dataset:
    """Scrape one or more seasons into a queryable :class:`Dataset`.

    Args:
        seasons: a season code (``"s26"``) or list (``["f24", "s25"]``).
        only: restrict to these regatta slugs instead of the whole season index
            (handy for exploring a few regattas without the full sweep).
        client: a configured ``scraper.Client``; one is created (and closed) if
            omitted.
        refresh: bypass the disk cache and re-fetch (use for live regattas).
        sailors: build per-sailor rows. Set ``False`` to skip the ``/sailors/``
            fetches when you only need results/finishes (e.g. school rankings).
        workers: how many regattas to fetch concurrently. The work is
            latency-bound (many small requests to a static host), so the default
            of 16 cuts a season scrape from minutes to seconds. Beyond ~16 the
            GIL-bound HTML parsing becomes the floor (measured: 8→22s,
            16→13s, 32→15s for a full season). Set ``1`` for a strictly
            sequential fetch.

    Returns:
        A ``Dataset``. This is a point-in-time snapshot; re-load (or pass
        ``refresh=True``) for regattas still in progress.
    """
    from scraper.client import Client  # lazy: only this path needs httpx

    if isinstance(seasons, str):
        seasons = [seasons]

    own_client = client is None
    client = client or Client()
    try:
        refs: list[tuple[str, str]] = []
        for season in seasons:
            if only is not None:
                refs.extend((season, slug) for slug in only)
            else:
                index = client.fetch(urls.season(season), refresh=refresh)
                if index is None:
                    continue
                refs.extend((season, stub.nick) for stub in _season_parser.parse(index, season))
        return _collect(refs, client, refresh, sailors, workers)
    finally:
        if own_client:
            client.close()


def load_regattas(
    refs: list[tuple[str, str]],
    *,
    client: Client | None = None,
    refresh: bool = False,
    sailors: bool = True,
    workers: int = 16,
) -> Dataset:
    """Load an explicit, possibly cross-season set of regattas into a Dataset.

    Args:
        refs: ``(season, slug)`` pairs, e.g. ``[("s26", "hood"), ("f25", "danmark")]``.
            Unlike ``load(only=…)``, seasons are per-ref, so this suits
            head-to-head queries that span seasons.
        client: a configured ``scraper.Client``; created/closed if omitted.
        refresh: bypass the disk cache and re-fetch.
        sailors: build per-sailor rows (set ``False`` to skip ``/sailors/`` fetches).
        workers: regattas to fetch concurrently (default 16; 1 = sequential).
    """
    from scraper.client import Client  # lazy

    own_client = client is None
    client = client or Client()
    try:
        return _collect(list(refs), client, refresh, sailors, workers)
    finally:
        if own_client:
            client.close()
