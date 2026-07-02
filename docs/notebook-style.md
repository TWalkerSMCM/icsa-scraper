# Notebook style guide

Conventions for `examples/*.ipynb`. The reference implementation is
`examples/csr-ranking.ipynb` — when in doubt, match it.

## Structure

1. **Colab badge** — first cell, markdown only:
   ```markdown
   <a href="https://colab.research.google.com/github/TWalkerSMCM/icsa-scraper/blob/main/examples/<name>.ipynb" target="_blank"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>
   ```
2. **Title + intro** — what question the notebook answers, in one or two
   sentences. If it reproduces a webapp feature or an algorithm from the
   monorepo, say so and cite the authoritative source (e.g.
   `analytics/skipper_elo/engine.py`) — the notebook is a readable
   reproduction, not the source of truth.
3. **Install cell** — always the same shape, guarded so a local execution
   can't clobber an editable dev install with the GitHub version:
   ```python
   # Fresh runtimes (Colab) need the library; skip when it's already importable
   # (a local venv) so this can't clobber an editable dev install.
   import importlib.util

   if importlib.util.find_spec("scraper") is None:
       %pip install -q "icsa-scraper[fetch] @ git+https://github.com/TWalkerSMCM/icsa-scraper"
       # pandas + matplotlib ship with Colab; add them here if missing elsewhere.
   ```
4. **Formula/constants before data** — explain the method in markdown, then a
   constants cell, then the function cells. A reader should understand the
   computation before any scraping happens.
5. **Load** — one `scraper.load(...)` cell. Pass `sailors=False` unless the
   notebook needs per-sailor rows (it halves the requests). Print row counts
   so a reader can sanity-check their run.
6. **Compute → DataFrame → one chart** — pandas frames are the primary
   display; finish with a single clear matplotlib figure, not a gallery.
   An optional interactive companion (plotly, which ships with Colab) may
   follow the static chart when hover detail genuinely helps — the static
   chart stays, since GitHub renders it and plotly it won't.
7. **Closing markdown** — where to go next (chainable filters, multi-season
   loads, deeper model fields).

## Rules

- **No hardcoded slugs.** Pick schools/sailors/regattas programmatically from
  the loaded data (most shared regattas, most races sailed, top of the season
  index). Seasons roll over; notebooks that hardcode subjects rot.
- **Season constant at the top** of the analysis (e.g. `SEASON = "s25"`), so
  updating a notebook for a new season is a one-line change.
- **Outputs stripped.** Code cells committed with `outputs: []` and
  `execution_count: null`. The pre-commit `nbstripout` hook enforces this —
  never commit executed copies.
- **Execute before committing.** Prove the notebook runs end-to-end:
  ```bash
  .venv/bin/python -m jupyter nbconvert --to notebook --execute examples/<name>.ipynb --output /tmp/<name>-check.ipynb
  ```
  The live site is static S3 — network in a local check is fine. Never write
  the executed copy back into `examples/`.
- **Keep a cold run to a minute or two.** Prefer `sailors=False`, `only=`, or
  a single season over exhaustive sweeps; mention the disk cache
  (`./.scraper_cache`) so re-runs are instant. Include the commented Drive
  mount tip for Colab persistence:
  ```python
  # import os; from google.colab import drive
  # drive.mount('/content/drive')
  # os.environ['SCRAPER_CACHE_DIR'] = '/content/drive/MyDrive/icsa_cache'
  ```
- **No emojis.** Anywhere.
- **Markdown voice**: short, declarative, explains *why* before *how*. Code
  comments only where the code can't speak (scoring quirks, dedupe wrinkles
  like multi-team schools or both-perspectives match rows).

## Coverage map

One notebook per primary webapp feature (`analytics/web/src/pages/` in the
monorepo), plus the library tour:

| Webapp feature | Notebook |
|---|---|
| (library tour) | `quickstart.ipynb` |
| Competitive Strength Rankings | `csr-ranking.ipynb` |
| Fleet Race Skipper Elo | `skipper-elo.ipynb` |
| Team Race Elo Ratings | `team-elo.ipynb` |
| Sailor Head-to-Head | `sailor-head-to-head.ipynb` |
| Fleet Racing Head-to-Head | `fleet-head-to-head.ipynb` |
| Team Racing Head-to-Head | `team-head-to-head.ipynb` |
