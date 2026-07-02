"""
Synchronous, disk-cached HTTP client for scores.collegesailing.org.

The blessed way to fetch pages: one ``httpx`` session, the rate-limit clock,
and the cache directory all held as instance state (no module globals). Pair
paths from ``scraper.urls`` with :meth:`Client.fetch`. Requires the ``fetch``
extra (``httpx``, ``tenacity``).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from scraper import cache
from scraper.fetcher import BASE_URL

USER_AGENT = "icsa-scraper (+https://github.com/TWalkerSMCM/icsa-scraper)"


class Client:
    """A cached, rate-limited fetcher for one run.

    Args:
        base_url: site root; paths from ``scraper.urls`` are appended.
        cache_dir: on-disk cache location for this instance. ``None`` keeps
            the process default (``SCRAPER_CACHE_DIR`` env, else
            ``./.scraper_cache``). Each ``Client`` holds its own cache
            directory — constructing one never affects other instances or
            bare ``scraper.cache`` calls.
        user_agent: sent on every request.
        delay: minimum seconds between *live* (non-cached) requests. Default 0
            — the site is static S3; raise it only if you want to throttle.
            Enforced across threads when one ``Client`` is shared by a
            ``ThreadPoolExecutor`` (e.g. ``scraper.load(workers=...)``).
        timeout: per-request timeout in seconds.
        transport: an optional ``httpx.BaseTransport`` override. ``None`` keeps
            httpx's default transport (real network I/O). This is an escape
            hatch for tests — pass an ``httpx.MockTransport`` to exercise the
            full ``Client`` + cache + retry stack against synthetic responses
            with no real network access.
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        cache_dir: str | Path | None = None,
        user_agent: str = USER_AGENT,
        delay: float = 0.0,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.delay = delay
        self._last = 0.0
        self._throttle_lock = threading.Lock()
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    def _url(self, path: str) -> str:
        return self.base_url + path

    def _throttle(self) -> None:
        # Held for the whole wait so concurrent callers serialize onto one
        # rate-limit clock instead of all sleeping and firing at once.
        with self._throttle_lock:
            if self.delay:
                wait = self.delay - (time.monotonic() - self._last)
                if wait > 0:
                    time.sleep(wait)
            self._last = time.monotonic()

    @retry(
        retry=retry_if_exception_type(httpx.RequestError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=1),
        reraise=True,
    )
    def _get(self, url: str) -> httpx.Response:
        return self._client.get(url)

    def fetch(
        self,
        path: str,
        *,
        refresh: bool = False,
        max_age: float | None = None,
        missing_ok: bool = False,
    ) -> str | None:
        """Fetch one page and return its HTML.

        Args:
            path: site-relative path, e.g. from ``scraper.urls``.
            refresh: ignore any cached copy and re-fetch.
            max_age: treat a cached copy older than this many seconds as stale.
            missing_ok: return ``None`` on a 404 instead of raising.

        Returns:
            The HTML string, or ``None`` only when ``missing_ok`` and the page
            404s.

        Raises:
            httpx.HTTPStatusError: on 404 (unless ``missing_ok``) or other
                non-2xx responses.
            httpx.RequestError: on transport failure, after 3 attempts with
                short exponential backoff (0.5s, 1s) between retries.
        """
        url = self._url(path)
        if not refresh:
            cached = cache.get(url, cache_dir=self.cache_dir)
            if cached is not None and (
                max_age is None or (cache.age(url, cache_dir=self.cache_dir) or 0.0) <= max_age
            ):
                return cached

        self._throttle()
        resp = self._get(url)
        if resp.status_code == 404 and missing_ok:
            return None
        resp.raise_for_status()
        html = resp.text
        cache.put(url, html, cache_dir=self.cache_dir)
        return html

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
