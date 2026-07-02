from pathlib import Path

import httpx
import pytest

from scraper import cache
from scraper.client import Client


def test_per_instance_cache_dirs_no_cross_talk(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    original_cache_dir = cache.CACHE_DIR

    client_a = Client(cache_dir=dir_a)
    client_b = Client(cache_dir=dir_b)

    cache.put("https://example.com/page", "<html>a</html>", cache_dir=client_a.cache_dir)

    assert cache.get("https://example.com/page", cache_dir=client_a.cache_dir) == "<html>a</html>"
    assert cache.get("https://example.com/page", cache_dir=client_b.cache_dir) is None

    # Constructing Clients must never touch the module-level default.
    assert cache.CACHE_DIR == original_cache_dir


def test_cache_helpers_use_explicit_cache_dir(tmp_path: Path) -> None:
    url = "https://example.com/foo/bar"

    assert cache.get(url, cache_dir=tmp_path) is None
    assert cache.has(url, cache_dir=tmp_path) is False
    assert cache.age(url, cache_dir=tmp_path) is None

    cache.put(url, "<html>hi</html>", cache_dir=tmp_path)

    assert cache.has(url, cache_dir=tmp_path) is True
    assert cache.get(url, cache_dir=tmp_path) == "<html>hi</html>"
    assert cache.path(url, cache_dir=tmp_path).parent == tmp_path
    age = cache.age(url, cache_dir=tmp_path)
    assert age is not None and age >= 0


def test_fetch_retries_transport_errors_then_succeeds(tmp_path: Path, monkeypatch) -> None:
    calls = {"n": 0}

    def flaky_get(self, url, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom", request=httpx.Request("GET", url))
        return httpx.Response(200, text="<html>ok</html>", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", flaky_get)
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)

    client = Client(cache_dir=tmp_path)
    html = client.fetch("/some/path")

    assert html == "<html>ok</html>"
    assert calls["n"] == 3


def test_fetch_raises_after_exhausting_retries(tmp_path: Path, monkeypatch) -> None:
    calls = {"n": 0}

    def always_fails(self, url, *args, **kwargs):
        calls["n"] += 1
        raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", always_fails)
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)

    client = Client(cache_dir=tmp_path)
    with pytest.raises(httpx.ConnectError):
        client.fetch("/some/path")

    assert calls["n"] == 3


def _mock_client(tmp_path: Path, responses: dict[str, str]) -> tuple[Client, list[str]]:
    """A Client wired to an httpx.MockTransport serving ``responses`` by path,
    tracking every requested path in the returned list."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        requested.append(path)
        if path in responses:
            return httpx.Response(200, text=responses[path])
        return httpx.Response(404, text="not found")

    client = Client(cache_dir=tmp_path, transport=httpx.MockTransport(handler))
    return client, requested


def test_refresh_true_refetches_and_overwrites_cache(tmp_path: Path) -> None:
    client, requested = _mock_client(tmp_path, {"/p": "<html>v1</html>"})
    assert client.fetch("/p") == "<html>v1</html>"
    assert requested == ["/p"]

    # Same content still served without a request when not refreshing.
    assert client.fetch("/p") == "<html>v1</html>"
    assert requested == ["/p"]

    # New content on the transport; refresh=True re-fetches and overwrites.
    responses = {"/p": "<html>v2</html>"}
    client2, requested2 = _mock_client(tmp_path, responses)
    assert client2.fetch("/p") == "<html>v1</html>"  # served from cache, no request
    assert requested2 == []
    assert client2.fetch("/p", refresh=True) == "<html>v2</html>"
    assert requested2 == ["/p"]
    # The overwrite persists for subsequent (non-refresh) fetches.
    assert client2.fetch("/p") == "<html>v2</html>"
    assert requested2 == ["/p"]


def test_max_age_fresh_cache_skips_request(tmp_path: Path) -> None:
    client, requested = _mock_client(tmp_path, {"/p": "<html>ok</html>"})
    assert client.fetch("/p") == "<html>ok</html>"
    assert requested == ["/p"]

    assert client.fetch("/p", max_age=3600) == "<html>ok</html>"
    assert requested == ["/p"]  # still fresh, no new request


def test_max_age_stale_cache_triggers_refetch(tmp_path: Path) -> None:
    import os

    from scraper import cache

    client, requested = _mock_client(tmp_path, {"/p": "<html>old</html>"})
    assert client.fetch("/p") == "<html>old</html>"
    assert requested == ["/p"]

    # Back-date the cached file's mtime so it reads as stale.
    cached_path = cache.path(client._url("/p"), cache_dir=tmp_path)
    old_time = cached_path.stat().st_mtime - 3600
    os.utime(cached_path, (old_time, old_time))

    client2, requested2 = _mock_client(tmp_path, {"/p": "<html>new</html>"})
    assert client2.fetch("/p", max_age=60) == "<html>new</html>"
    assert requested2 == ["/p"]


def test_missing_ok_404_returns_none_and_does_not_cache(tmp_path: Path) -> None:
    client, requested = _mock_client(tmp_path, {})  # nothing exists -> 404
    assert client.fetch("/missing", missing_ok=True) is None
    assert requested == ["/missing"]

    from scraper import cache

    assert cache.has(client._url("/missing"), cache_dir=tmp_path) is False

    # A subsequent fetch retries rather than being permanently cached as a miss.
    assert client.fetch("/missing", missing_ok=True) is None
    assert requested == ["/missing", "/missing"]
