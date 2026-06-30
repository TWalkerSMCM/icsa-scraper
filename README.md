# icsa-scraper

HTML parsers for college sailing results from
[scores.collegesailing.org](https://scores.collegesailing.org) — the ICSA
Techscore scoring system.

The parsers are pure functions over HTML: you hand them a page's HTML and they
return plain Python dataclasses. They do **no network I/O**, so they're easy to
test, cache, and run anywhere (including notebooks).

## Install

Install straight from GitHub — no PyPI needed:

```bash
pip install "git+https://github.com/TWalkerSMCM/icsa-scraper"
```

Pin to a tag or commit for reproducible notebooks:

```bash
pip install "icsa-scraper @ git+https://github.com/TWalkerSMCM/icsa-scraper@v0.1.0"
```

The base install pulls only `beautifulsoup4` + `lxml`. Optional extras:

| Extra   | Adds                  | For |
|---------|-----------------------|-----|
| `fetch` | `httpx`, `tenacity`   | an HTTP client (`httpx`) for fetching pages yourself, plus the async `scraper.fetcher` |
| `aws`   | `boto3`               | the DynamoDB ETag store in `scraper.stores` |

```bash
pip install "icsa-scraper[fetch] @ git+https://github.com/TWalkerSMCM/icsa-scraper"
```

## Quick start

The parsers don't fetch — the examples below use `httpx` for the GETs, so install
the `fetch` extra (`pip install "icsa-scraper[fetch] @ git+..."`). Or bring your
own client (`requests`, `urllib`) and skip the extra.

```python
import httpx
from scraper.parsers import division, regatta

base = "https://scores.collegesailing.org/s25/<regatta-slug>"

# Regatta overview (name, scoring type, which sub-pages exist, ...)
meta = regatta.parse(httpx.get(f"{base}/").text, season="s25", nick="<regatta-slug>")

# Per-division finishes
results = division.parse(httpx.get(f"{base}/A/").text, "A")
for team in results:
    print(team.rank, team.school_name, team.total_score)
```

Every parser exposes a `parse(html, ...)` entry point and accepts either a raw
HTML string or a pre-parsed `BeautifulSoup`.

## Examples

[`examples/quickstart.ipynb`](examples/quickstart.ipynb)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/TWalkerSMCM/icsa-scraper/blob/main/examples/quickstart.ipynb)
— a guided tour: assemble one regatta from its pages into a `RegattaScores`
model, then a pandas DataFrame and a chart. Click the badge to run it in Colab.

## Google Colab

```python
!pip install -q "icsa-scraper[fetch] @ git+https://github.com/TWalkerSMCM/icsa-scraper"

import httpx
from scraper.parsers import division

html = httpx.get("https://scores.collegesailing.org/s25/<regatta>/A/").text
for team in division.parse(html, "A"):
    print(team.rank, team.school_name, team.total_score)
```

Notes for Colab:

- **Use synchronous fetching** (`httpx.get(...)` / `requests.get(...)`) as
  above. `scraper.fetcher` is `async`, and Colab already runs an event loop, so
  `asyncio.run()` there raises "event loop already running." If you must use the
  async fetcher, `import nest_asyncio; nest_asyncio.apply()` first.
- **Persisting the disk cache:** `scraper.cache` defaults to `./.scraper_cache`,
  which Colab wipes on runtime reset. To keep it, mount Drive and point the
  cache at it:

  ```python
  import os
  from google.colab import drive
  drive.mount("/content/drive")
  os.environ["SCRAPER_CACHE_DIR"] = "/content/drive/MyDrive/icsa_cache"
  ```

  Set `SCRAPER_CACHE_DIR` **before** importing `scraper.cache`.

## Layout

| Module | Purpose |
|--------|---------|
| `scraper.parsers` | granular per-page HTML parsers (overview, divisions, full scores, sailors, rotations, …) |
| `scraper.adapter` | groups parser output into the `scraper.models` data contract |
| `scraper.models`  | dataclasses describing the public API shape |
| `scraper.cache`   | optional on-disk HTML cache |
| `scraper.fetcher` | async page fetcher (extra: `fetch`) |
| `scraper.stores`  | DynamoDB ETag store (extra: `aws`) |

## Development

```bash
pip install -e ".[dev,fetch,aws]"
pre-commit install   # strips notebook outputs on commit (nbstripout)
pytest
mypy src
```

## License

MIT — see [LICENSE](LICENSE). HTML structure is derived from the MIT-licensed
[Techscore](https://github.com/openwebsolns/techscore) source.
