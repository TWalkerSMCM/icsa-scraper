# icsa-scraper

A parser **and analysis** library for college sailing results from
[scores.collegesailing.org](https://scores.collegesailing.org) — the ICSA
Techscore scoring system.

Scrape a season into a queryable `Dataset`, compare two sailors head-to-head,
or drop down to the pure HTML parsers underneath — no network required at that
layer.

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
| `fetch` | `httpx`, `tenacity`   | `scraper.Client` (sync, cached) for fetching pages, plus the async `scraper.fetcher` |
| `aws`   | `boto3`               | the DynamoDB ETag store in `scraper.stores` |

```bash
pip install "icsa-scraper[fetch] @ git+https://github.com/TWalkerSMCM/icsa-scraper"
```

`scraper.load()` and `scraper.head_to_head()` need the `fetch` extra since they
fetch pages themselves.

## Quick start

```python
import scraper

data = scraper.load("s26")
data.fleet().results_frame()   # one row per (regatta, school): place, total, school_slug, ...

h = scraper.head_to_head("jane-doe", "john-roe")
h.a_ahead, h.b_ahead   # regatta-divisions each sailor finished ahead in
```

See [`docs/api.md`](docs/api.md) for the full surface, or the guided tour in
[`examples/quickstart.ipynb`](examples/quickstart.ipynb).

## Lower-level layers

The parsers are pure functions over HTML: hand them a page you already
fetched and they return plain Python dataclasses — no network I/O, easy to
test, cache, and run anywhere (including notebooks). `scraper.load()` and
`scraper.fleet_scores()`/`scraper.team_scores()` are built on top of them.

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

Every notebook opens in Colab from its badge; each is a self-contained,
executable analysis. Conventions live in
[`docs/notebook-style.md`](docs/notebook-style.md).

| Notebook | What it does |
|----------|--------------|
| [`quickstart.ipynb`](examples/quickstart.ipynb) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/TWalkerSMCM/icsa-scraper/blob/main/examples/quickstart.ipynb) | Guided tour: load a season into a `Dataset`, frames, chart, then under the hood |
| [`csr-ranking.ipynb`](examples/csr-ranking.ipynb) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/TWalkerSMCM/icsa-scraper/blob/main/examples/csr-ranking.ipynb) | Competitive Strength Rankings — grade-weighted best-N school scoring |
| [`skipper-elo.ipynb`](examples/skipper-elo.ipynb) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/TWalkerSMCM/icsa-scraper/blob/main/examples/skipper-elo.ipynb) | Fleet-race skipper Elo — per-race pairwise ratings, K by regatta grade |
| [`skipper-bradley-terry.ipynb`](examples/skipper-bradley-terry.ipynb) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/TWalkerSMCM/icsa-scraper/blob/main/examples/skipper-bradley-terry.ipynb) | Bradley-Terry skipper strengths — one scale spanning A and B divisions |
| [`team-elo.ipynb`](examples/team-elo.ipynb) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/TWalkerSMCM/icsa-scraper/blob/main/examples/team-elo.ipynb) | Team-race Elo — match-level ratings with margin-of-victory weighting |
| [`sailor-head-to-head.ipynb`](examples/sailor-head-to-head.ipynb) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/TWalkerSMCM/icsa-scraper/blob/main/examples/sailor-head-to-head.ipynb) | Two sailors compared — shared regattas and race-by-race encounters |
| [`fleet-head-to-head.ipynb`](examples/fleet-head-to-head.ipynb) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/TWalkerSMCM/icsa-scraper/blob/main/examples/fleet-head-to-head.ipynb) | Two schools across shared fleet regattas — record and place gaps |
| [`team-head-to-head.ipynb`](examples/team-head-to-head.ipynb) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/TWalkerSMCM/icsa-scraper/blob/main/examples/team-head-to-head.ipynb) | Two schools' direct team-racing matches — W-L-T and combos |

## Google Colab

```python
!pip install -q "icsa-scraper[fetch] @ git+https://github.com/TWalkerSMCM/icsa-scraper"

import scraper

data = scraper.load("s26")   # workers=16 by default: regattas fetched concurrently
data.fleet().results_frame().sort_values("place").head(10)
```

Notes for Colab:

- **`scraper.load` is synchronous** under the hood (`scraper.Client`), so it's
  Colab-safe with no event-loop juggling. `scraper.fetcher` is a separate
  `async` fetcher for the Lambda poller — you don't need it here.
- **Persisting the disk cache:** `scraper.cache` defaults to `./.scraper_cache`,
  which Colab wipes on runtime reset. To keep it, mount Drive and point the
  cache at it:

  ```python
  import os
  from google.colab import drive
  drive.mount("/content/drive")
  os.environ["SCRAPER_CACHE_DIR"] = "/content/drive/MyDrive/icsa_cache"
  ```

  Set `SCRAPER_CACHE_DIR` **before** importing `scraper` (or pass
  `scraper.Client(cache_dir=...)` explicitly).

## Layout

| Module | Purpose |
|--------|---------|
| `scraper.parsers` | granular per-page HTML parsers (overview, divisions, full scores, sailors, rotations, …) |
| `scraper.adapter` | groups parser output into the `scraper.models` data contract |
| `scraper.models`  | dataclasses describing the public API shape |
| `scraper.urls`    | pure functions for site-relative paths |
| `scraper.ids`     | slug/name helpers (school/sailor slugs, race-range expansion) |
| `scraper.client`  | `Client` — sync, cached, rate-limited HTTP fetcher (extra: `fetch`) |
| `scraper.assemble` | `fleet_scores`/`team_scores` — one HTML-in/model-out call per regatta |
| `scraper.sailor_races` | the RP↔finish join — per-sailor, per-race results |
| `scraper.dataset` | `load`/`Dataset` — scrape a season into a queryable in-memory collection |
| `scraper.head_to_head` | compare two sailors without scraping a whole season |
| `scraper.views`   | flat, analysis-friendly row types (`Result`, `Finish`, `SailorRaceFinish`, `HeadToHead`, …) |
| `scraper.cache`   | optional on-disk HTML cache |
| `scraper.fetcher` | async page fetcher, used by the Lambda poller (extra: `fetch`) |
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
