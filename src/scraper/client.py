"""
Synchronous, disk-cached HTTP client for scores.collegesailing.org.

The blessed way to fetch pages: one ``httpx`` session and the rate-limit clock
held as instance state (no module globals). Pair paths from ``scraper.urls``
with :meth:`Client.fetch`. Requires the ``fetch`` extra (``httpx``).
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from scraper import cache
from scraper.fetcher import BASE_URL

USER_AGENT = "icsa-scraper (+https://github.com/TWalkerSMCM/icsa-scraper)"


class Client:
    """A cached, rate-limited fetcher for one run.

    Args:
        base_url: site root; paths from ``scraper.urls`` are appended.
        cache_dir: on-disk cache location. ``None`` keeps the process default
            (``SCRAPER_CACHE_DIR`` env, else ``./.scraper_cache``). Setting it
            here points the shared cache at that directory.
        user_agent: sent on every request.
        delay: minimum seconds between *live* (non-cached) requests. Default 0
            — the site is static S3; raise it only if you want to throttle.
        timeout: per-request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        cache_dir: str | Path | None = None,
        user_agent: str = USER_AGENT,
        delay: float = 0.0,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self._last = 0.0
        if cache_dir is not None:
            cache.CACHE_DIR = Path(cache_dir)
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        )

    def _url(self, path: str) -> str:
        return self.base_url + path

    def _throttle(self) -> None:
        if self.delay:
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        self._last = time.monotonic()

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
            httpx.RequestError: on transport failure.
        """
        url = self._url(path)
        if not refresh:
            cached = cache.get(url)
            if cached is not None and (max_age is None or (cache.age(url) or 0.0) <= max_age):
                return cached

        self._throttle()
        resp = self._client.get(url)
        if resp.status_code == 404 and missing_ok:
            return None
        resp.raise_for_status()
        html = resp.text
        cache.put(url, html)
        return html

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
