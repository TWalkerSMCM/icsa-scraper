# Notebook style guide

Conventions for `examples/*.ipynb`. The reference implementation is
`examples/csr-ranking.ipynb` — when in doubt, match it.

## Structure

1. **Colab badge** — first cell, markdown only:
   ```markdown
   <a href="https://colab.research.google.com/github/TWalkerSMCM/icsa-scraper/blob/main/examples/<name>.ipynb" target="_blank"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>
   ```
2. **Title + intro** — `# icsa-scraper · <Feature Name>`, Title Case (keep
   acronyms like `CSR`/`CSV` uppercase), then what question the notebook
   answers in one or two sentences. If it reproduces a webapp feature, cite
   it in exactly this form: "the [analytics webapp](https://collegeanalytics.goforthom.as)"
   (link once per notebook, on first mention). If the feature's authoritative
   implementation lives in the `icsa-tools` monorepo, cite the path and line
   count too, e.g. "lives at `analytics/skipper_elo/engine.py` in the
   `icsa-tools` monorepo (339 lines)" — the notebook is a readable
   reproduction, not the source of truth.
3. **Install cell** — always the same shape, guarded so a local execution
   can't clobber an editable dev install with the GitHub version:
   ```python
   # Fresh runtimes (Colab) need the library. Guard on the distribution name so
   # re-running locally can't clobber an editable dev install; to force-update a
   # cached Colab runtime, restart it (or run the %pip line with --force-reinstall).
   from importlib.metadata import PackageNotFoundError, version

   try:
       version("icsa-scraper")
   except PackageNotFoundError:
       %pip install -q "icsa-scraper[fetch] @ git+https://github.com/TWalkerSMCM/icsa-scraper"
   ```
   Guard on the distribution (`icsa-scraper`), not the module (`scraper`) —
   the module name is generic enough to collide. This cell must be
   byte-for-byte identical across every notebook.
4. **Drive-cache tip** — immediately after the install cell, for any notebook
   that does a season-scale load (skip it for a notebook that only loads one
   regatta, e.g. `sailor-head-to-head.ipynb`). One markdown cell, exact
   heading and fenced snippet:
   ```markdown
   ## Optional: persist the cache on Colab

   `scraper.load()` caches every fetched page under `./.scraper_cache`, so re-running a cell (or the whole notebook) after the first pass is instant. Colab wipes that folder on runtime reset — mount Drive and point the cache there first if you want it to survive. Set `SCRAPER_CACHE_DIR` **before** importing `scraper`:

   \`\`\`python
   # from google.colab import drive
   # drive.mount('/content/drive')
   # import os
   # os.environ['SCRAPER_CACHE_DIR'] = '/content/drive/MyDrive/icsa_cache'
   \`\`\`
   ```
5. **Formula/constants before data** — explain the method in markdown, then a
   constants cell, then the function cells. A reader should understand the
   computation before any scraping happens. A multi-season constant gets a
   one-line comment on why the range matters in this notebook's context
   (e.g. `# The full academic year: ratings carry from fall into spring.`
   when a rating compounds over time; `# The full academic year: fall +
   spring.` when the year is just a wider data window) — parallel notebooks
   (the two skipper-rating notebooks, the two full-year head-to-head
   notebooks) should use matching comments unless the underlying reason
   actually differs.
6. **Load** — one `scraper.load(...)` cell. Pass `sailors=False` unless the
   notebook needs per-sailor rows, and say so once, identically phrased
   across notebooks: "`sailors=False` skips the per-sailor pages this
   notebook doesn't need, roughly halving the fetches." Do the same for any
   other load-affecting argument the notebook uses — `progress=True` ("shows
   a per-regatta progress bar while it runs"), `.fleet()`/`.team()`
   ("narrows the dataset to fleet-/team-scoring regattas only"). Print row
   counts so a reader can sanity-check their run.
7. **Compute → DataFrame → one chart** — pandas frames are the primary
   display; finish with a single clear matplotlib figure, not a gallery.
   An optional interactive companion (plotly, which ships with Colab) may
   follow the static chart when hover detail genuinely helps — the static
   matplotlib chart stays as the baseline because it renders in any
   environment with no JS frontend or extra install. (Outputs are stripped
   on commit, so neither chart shows on GitHub — charts only exist when a
   reader runs the notebook.)
8. **Closing markdown** — where to go next (chainable filters, multi-season
   loads, deeper model fields). Always `---` on its own line, then a bold
   label ending in a colon, e.g. `**Extending this:**` / `**Going
   deeper:**` / `**Recap:**` — pick whatever label fits the notebook, but
   keep the `---` + `**Label:**` shape identical.

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
  (`./.scraper_cache`) so re-runs are instant. See Structure item 4 for the
  canonical Drive-cache tip cell.
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
| — (companion: cross-division skipper strengths) | `skipper-bradley-terry.ipynb` |
| Team Race Elo Ratings | `team-elo.ipynb` |
| Sailor Head-to-Head | `sailor-head-to-head.ipynb` |
| Fleet Racing Head-to-Head | `fleet-head-to-head.ipynb` |
| Team Racing Head-to-Head | `team-head-to-head.ipynb` |
| — (utility: CSV export) | `export-skipper-finishes.ipynb` |
