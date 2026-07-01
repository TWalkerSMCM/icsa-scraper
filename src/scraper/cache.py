"""
Persistent disk cache for scraped HTML pages.

Files are stored as: <cache-dir>/<url-path-encoded>.html
The cache directory is created automatically on write.
A URL is never fetched more than once per run (or across runs).

The cache directory defaults to ``./.scraper_cache`` in the current working
directory. Override it with the ``SCRAPER_CACHE_DIR`` environment variable —
e.g. point it at a mounted Google Drive path in Colab to persist across runtime
resets. The library never writes into its own install directory.

Every function also accepts an optional ``cache_dir`` override so callers
(e.g. :class:`scraper.client.Client`) can hold a per-instance cache location
without mutating the module-level default.
"""

import os
import re
import time
from pathlib import Path

_cache_override = os.environ.get("SCRAPER_CACHE_DIR")
CACHE_DIR: Path = Path(_cache_override) if _cache_override else Path.cwd() / ".scraper_cache"


def _dir(cache_dir: Path | None) -> Path:
    """Resolve the effective cache directory: ``cache_dir`` if given, else the module default."""
    return cache_dir if cache_dir is not None else CACHE_DIR


def _url_to_filename(url: str) -> str:
    """Convert a URL to a safe filename. Strips scheme and host, encodes path."""
    # Remove scheme + host, keep path + query
    path = re.sub(r"^https?://[^/]+", "", url)
    # Replace unsafe filename characters; collapse slashes
    safe = re.sub(r"[^a-zA-Z0-9_\-.]", "_", path).strip("_")
    # Avoid empty or overly long names
    safe = safe[:200] or "root"
    return safe + ".html"


def get(url: str, cache_dir: Path | None = None) -> str | None:
    """Return cached HTML for url, or None if not cached."""
    path = _dir(cache_dir) / _url_to_filename(url)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def put(url: str, html: str, cache_dir: Path | None = None) -> None:
    """Store html for url in the cache."""
    resolved = _dir(cache_dir)
    resolved.mkdir(parents=True, exist_ok=True)
    path = resolved / _url_to_filename(url)
    path.write_text(html, encoding="utf-8")


def has(url: str, cache_dir: Path | None = None) -> bool:
    """Return True if url is already cached."""
    path = _dir(cache_dir) / _url_to_filename(url)
    return path.exists()


def path(url: str, cache_dir: Path | None = None) -> Path:
    """Return the on-disk cache path for url (whether or not it exists)."""
    return _dir(cache_dir) / _url_to_filename(url)


def age(url: str, cache_dir: Path | None = None) -> float | None:
    """Seconds since url was cached, or None if not cached."""
    p = _dir(cache_dir) / _url_to_filename(url)
    if not p.exists():
        return None
    return time.time() - p.stat().st_mtime
