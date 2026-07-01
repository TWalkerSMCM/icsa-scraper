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
