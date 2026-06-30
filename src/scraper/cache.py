"""
Persistent disk cache for scraped HTML pages.

Files are stored as: <cache-dir>/<url-path-encoded>.html
The cache directory is created automatically.
A URL is never fetched more than once per run (or across runs).

The cache directory defaults to ``./.scraper_cache`` in the current working
directory. Override it with the ``SCRAPER_CACHE_DIR`` environment variable —
e.g. point it at a mounted Google Drive path in Colab to persist across runtime
resets. The library never writes into its own install directory.
"""

import os
import re
from pathlib import Path


_cache_override = os.environ.get("SCRAPER_CACHE_DIR")
CACHE_DIR: Path = Path(_cache_override) if _cache_override else Path.cwd() / ".scraper_cache"


def _url_to_filename(url: str) -> str:
    """Convert a URL to a safe filename. Strips scheme and host, encodes path."""
    # Remove scheme + host, keep path + query
    path = re.sub(r"^https?://[^/]+", "", url)
    # Replace unsafe filename characters; collapse slashes
    safe = re.sub(r"[^a-zA-Z0-9_\-.]", "_", path).strip("_")
    # Avoid empty or overly long names
    safe = safe[:200] or "root"
    return safe + ".html"


def get(url: str) -> str | None:
    """Return cached HTML for url, or None if not cached."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / _url_to_filename(url)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def put(url: str, html: str) -> None:
    """Store html for url in the cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / _url_to_filename(url)
    path.write_text(html, encoding="utf-8")


def has(url: str) -> bool:
    """Return True if url is already cached."""
    path = CACHE_DIR / _url_to_filename(url)
    return path.exists()
