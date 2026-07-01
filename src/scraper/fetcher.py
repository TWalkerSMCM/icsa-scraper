"""
Async HTTP fetch layer for scores.collegesailing.org.

Responsibilities:
  - Conditional GETs via If-None-Match / ETags (304 = no change, skip parse)
  - Concurrent fetching of multiple regattas with a shared connection pool
  - Exponential backoff on transient errors via tenacity
  - ETag persistence through a swappable store (in-memory now, DynamoDB later)
  - Auto-detection of divisional vs team racing format
  - Full poll cycle: front page → active regattas → scores diff

Usage:
    async with ICSAFetcher() as fetcher:
        changed = await fetcher.poll_active_scores()
        for result in changed:
            print(result.name, result.scoring_type)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol, runtime_checkable

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .adapter import build_fleet_scores, build_team_scores
from .live.front_page import parse_active_regattas
from .models import RegattaListEntry, RegattaScores, TeamRegattaScores, make_pk
from .parsers.division import parse as _parse_division
from .parsers.full_scores import parse as _parse_full_scores_raw
from .parsers.regatta import parse_team_ranking_table
from .parsers.team_all_races import parse as _parse_team_all_raw
from .parsers.team_rotations import parse_flights as _parse_team_flights

log = logging.getLogger(__name__)

BASE_URL = "https://scores.collegesailing.org"
USER_AGENT = "ICSA-LiveScores/1.0 (contact: icsa-app)"

ScoreResult = RegattaScores | TeamRegattaScores


# ---------------------------------------------------------------------------
# ETag store — swappable interface
# ---------------------------------------------------------------------------


@runtime_checkable
class ETagStore(Protocol):
    async def get(self, url: str) -> str | None: ...
    async def set(self, url: str, etag: str) -> None: ...


class InMemoryETagStore:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, url: str) -> str | None:
        return self._store.get(url)

    async def set(self, url: str, etag: str) -> None:
        self._store[url] = etag


# ---------------------------------------------------------------------------
# Retry predicate
# ---------------------------------------------------------------------------


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code not in (404, 410, 403, 401)
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------


class ICSAFetcher:
    """
    Async HTTP client for scores.collegesailing.org.

    Use as an async context manager to share a single connection pool
    across the entire poll cycle:

        async with ICSAFetcher() as fetcher:
            entries, html = await fetcher.fetch_active_regattas()
            changed = await fetcher.poll_active_scores(entries=entries)
    """

    def __init__(
        self,
        etag_store: ETagStore | None = None,
        max_concurrent: int = 50,
        timeout: float = 15.0,
        ignore_etags: bool = False,
    ) -> None:
        self._etag_store = etag_store or InMemoryETagStore()
        self._ignore_etags = ignore_etags
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout

    async def __aenter__(self) -> ICSAFetcher:
        self._client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=self._timeout,
            follow_redirects=True,
            http2=True,
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Core fetch — conditional GET with ETag + retry
    # ------------------------------------------------------------------

    async def _fetch(
        self,
        url: str,
        *,
        bypass_etag: bool = False,
    ) -> tuple[str | None, str | None]:
        """
        Fetch a URL with conditional GET.

        Returns:
            (html, etag)  — content changed or first fetch
            (None, etag)  — HTTP 304, content unchanged

        bypass_etag: skip both reading and writing the ETag store. Use for
            supplementary URLs whose body must populate every poll regardless
            of whether the page changed (e.g. /rotations/, /full-scores/
            rankings) — these are joined into the primary /all/ result, so a
            304 returning None would overwrite live data with empty defaults.
        """
        etag = None
        if not (self._ignore_etags or bypass_etag):
            etag = await self._etag_store.get(url)
        headers = {"If-None-Match": etag} if etag else {}

        @retry(
            retry=retry_if_exception(_is_transient),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=16),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        )
        async def _do_request() -> httpx.Response:
            async with self._semaphore:
                assert self._client is not None, "Use ICSAFetcher as an async context manager"
                return await self._client.get(url, headers=headers)

        resp = await _do_request()

        if resp.status_code == 304:
            log.debug("304 unchanged: %s", url)
            return None, etag

        resp.raise_for_status()

        new_etag = resp.headers.get("etag")
        if new_etag and not bypass_etag:
            await self._etag_store.set(url, new_etag)

        return resp.text, new_etag

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_active_regattas(self) -> tuple[list[RegattaListEntry], str]:
        """Fetch the front page and return (in-progress regattas, raw HTML).

        The raw HTML is returned so the caller can pass it to _seed_upcoming()
        without a redundant second fetch of the front page.
        """
        assert self._client is not None, "Use ICSAFetcher as an async context manager"
        resp = await self._client.get(f"{BASE_URL}/")
        resp.raise_for_status()
        log.info('HTTP Request: GET %s/ "%s"', BASE_URL, resp.status_code)
        return parse_active_regattas(resp.text), resp.text

    async def _fill_division_ranks_if_tied(
        self, result: RegattaScores, season: str, slug: str
    ) -> None:
        """Fetch per-division ranks only when ties exist."""
        div_totals: dict[str, list[int]] = {}
        for team in result.teams:
            for div_key, div in team.divisions.items():
                div_totals.setdefault(div_key, []).append(div.total)

        tied_divs = [dk for dk, totals in div_totals.items() if len(totals) != len(set(totals))]
        if not tied_divs:
            return

        async def _fetch_div(div_key: str) -> tuple[str, list]:
            url = f"{BASE_URL}/{season}/{slug}/{div_key}/"
            try:
                html, _ = await self._fetch(url)
                if html:
                    return div_key, _parse_division(html, div_key)
            except Exception:
                log.warning("Failed to fetch division %s ranks for %s/%s", div_key, season, slug)
            return div_key, []

        results = await asyncio.gather(*[_fetch_div(dk) for dk in tied_divs])

        for div_key, parsed in results:
            if not parsed:
                continue
            # Match by (slug, occurrence) — when a school has multiple teams,
            # the Nth occurrence of that slug in the division page corresponds
            # to the Nth team with that slug in our results.
            slug_counts: dict[str, int] = {}
            rank_by_occurrence: dict[tuple[str, int], tuple] = {}
            for dr in parsed:
                s = dr.school_slug
                occ = slug_counts.get(s, 0)
                rank_by_occurrence[(s, occ)] = (dr.rank, dr.tiebreaker, dr.tiebreaker_note)
                slug_counts[s] = occ + 1

            slug_counts.clear()
            for team in result.teams:
                if div_key not in team.divisions:
                    continue
                occ = slug_counts.get(team.school_slug, 0)
                entry = rank_by_occurrence.get((team.school_slug, occ))
                if entry is not None:
                    rank, tb_sym, tb_note = entry
                    team.divisions[div_key].rank = rank
                    team.divisions[div_key].tiebreaker = tb_sym
                    team.divisions[div_key].tiebreaker_note = tb_note
                slug_counts[team.school_slug] = occ + 1

    async def _fetch_team_rankings(self, season: str, slug: str) -> list | None:
        """Fetch and parse /full-scores/ page for official team racing rankings.

        ETag is bypassed: the rankings join into the /all/ result and a 304
        here (page unchanged) would otherwise return None, dropping the
        official ranking and forcing the win-pct fallback in build_team_scores.
        """
        url = f"{BASE_URL}/{season}/{slug}/full-scores/"
        try:
            html, _ = await self._fetch(url, bypass_etag=True)
            if html is None:
                return None
            soup = BeautifulSoup(html, "lxml")
            table = soup.find("table", class_="teamranking")
            return parse_team_ranking_table(table) if table else None
        except Exception:
            log.warning("Failed to fetch ranking page for %s/%s", season, slug)
            return None

    async def _fetch_team_flights(self, season: str, slug: str) -> dict[int, int] | None:
        """Fetch /rotations/ and parse the flight assignment for each race.

        ETag is bypassed: rotations are typically published once and rarely
        change, so a conditional GET would return 304 on most polls.  None
        here would propagate to build_team_scores as an empty flights map,
        zeroing out flight data on every match whenever /all/ updates.  Pages
        are small (~60 KB) so refetching is cheap.
        """
        url = f"{BASE_URL}/{season}/{slug}/rotations/"
        try:
            html, _ = await self._fetch(url, bypass_etag=True)
            if html is None:
                return None
            return _parse_team_flights(html)
        except Exception:
            log.warning("Failed to fetch rotations page for %s/%s", season, slug)
            return None

    def _parse_fleet(self, html: str, season: str, slug: str) -> RegattaScores:
        soup = BeautifulSoup(html, "lxml")
        div_scores = _parse_full_scores_raw(soup)
        return build_fleet_scores(soup, season, slug, div_scores)

    def _parse_team(
        self,
        html: str,
        season: str,
        slug: str,
        rankings=None,
        flights=None,
    ) -> TeamRegattaScores:
        soup = BeautifulSoup(html, "lxml")
        rounds, results = _parse_team_all_raw(soup)
        return build_team_scores(
            soup, season, slug, rounds, results, rankings=rankings, flights=flights
        )

    async def _fetch_and_parse_team(
        self,
        season: str,
        slug: str,
    ) -> tuple[ScoreResult | None, str | None]:
        """Fetch /all/, /full-scores/, /rotations/ concurrently, parse as team race."""
        url = f"{BASE_URL}/{season}/{slug}/all/"
        (html, _), rankings, flights = await asyncio.gather(
            self._fetch(url),
            self._fetch_team_rankings(season, slug),
            self._fetch_team_flights(season, slug),
        )
        if html is None:
            return None, None
        return self._parse_team(html, season, slug, rankings, flights), html

    async def fetch_scores(
        self, season: str, slug: str, scoring_type: str | None = None
    ) -> tuple[ScoreResult | None, str | None]:
        """
        Fetch and parse full scores for one regatta.

        scoring_type: "team", "divisional", or "combined".
        Combined uses the same full-scores page as divisional.
        """
        if scoring_type == "team":
            return await self._fetch_and_parse_team(season, slug)

        if scoring_type in ("divisional", "combined"):
            url = f"{BASE_URL}/{season}/{slug}/full-scores/"
            html, _ = await self._fetch(url)
            if html is None:
                return None, None
            result = self._parse_fleet(html, season, slug)
            await self._fill_division_ranks_if_tied(result, season, slug)
            return result, html

        # scoring_type unknown — try team first, fall back to divisional on 404.
        # Sequential here: if /all/ 404s we fall back to fleet, and concurrent
        # would waste a /full-scores/ fetch that gets re-fetched in the fallback.
        all_url = f"{BASE_URL}/{season}/{slug}/all/"
        try:
            html, _ = await self._fetch(all_url)
            if html is None:
                return None, None
            rankings, flights = await asyncio.gather(
                self._fetch_team_rankings(season, slug),
                self._fetch_team_flights(season, slug),
            )
            return self._parse_team(html, season, slug, rankings, flights), html
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise

        url = f"{BASE_URL}/{season}/{slug}/full-scores/"
        html, _ = await self._fetch(url)
        if html is None:
            return None, None
        result = self._parse_fleet(html, season, slug)
        await self._fill_division_ranks_if_tied(result, season, slug)
        return result, html

    async def poll_active_scores(
        self,
        entries: list[RegattaListEntry] | None = None,
        known_scoring_types: dict[str, str] | None = None,
    ) -> list[tuple[ScoreResult, str]]:
        """
        One full poll cycle: fetch scores for all active regattas concurrently.
        Returns only regattas whose content changed (non-304).
        """
        if entries is None:
            entries, _ = await self.fetch_active_regattas()
        if not entries:
            log.info("poll_active_scores: no active regattas found")
            return []

        known = known_scoring_types or {}
        log.info("poll_active_scores: checking %d regattas", len(entries))

        tasks = [
            self.fetch_scores(e.season, e.slug, known.get(make_pk(e.season, e.slug)))
            for e in entries
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        changed: list[tuple[ScoreResult, str]] = []
        for entry, outcome in zip(entries, raw_results):
            if isinstance(outcome, BaseException):
                log.warning("Failed to fetch %s/%s: %s", entry.season, entry.slug, outcome)
            else:
                result, html = outcome
                if result is not None and html is not None:
                    log.info("Scores changed: %s (%s)", entry.slug, result.scoring_type)
                    changed.append((result, html))
                else:
                    log.debug("No change: %s/%s", entry.season, entry.slug)

        return changed
