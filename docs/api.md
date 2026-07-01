# icsa-scraper API

A parser **and analysis** library for college-sailing results. Three layers, each
usable on its own:

1. **Parse** — pure functions over HTML (`scraper.parsers.*`). No network.
2. **Fetch & locate** — `scraper.Client` (cached HTTP) + `scraper.urls` (paths).
3. **Assemble & query** — `fleet_scores`/`team_scores`/`sailor_races` build models
   from pages; `scraper.load()` scrapes a season into a queryable `Dataset`; and
   `scraper.head_to_head()` compares two sailors without scraping a season.

Layers 2–3 that touch the network need the `fetch` extra: `pip install "icsa-scraper[fetch]"`.

---

## Locating pages — `scraper.urls`

Pure functions returning site-relative paths (core install, no deps).

| Function | Path |
|----------|------|
| `urls.season(season)` | `/{season}/` |
| `urls.regatta(season, slug)` | `/{season}/{slug}/` |
| `urls.full_scores(season, slug)` | `/{season}/{slug}/full-scores/` |
| `urls.division(season, slug, div)` | `/{season}/{slug}/{div}/` |
| `urls.divisions(season, slug)` | `/{season}/{slug}/divisions/` |
| `urls.all_races(season, slug)` | `/{season}/{slug}/all/` |
| `urls.rotations(season, slug)` | `/{season}/{slug}/rotations/` |
| `urls.sailors(season, slug)` | `/{season}/{slug}/sailors/` |
| `urls.school(school_id, season)` | `/schools/{school_id}/{season}/` |
| `urls.sailor_profile(sailor_slug)` | `/sailors/{sailor_slug}/` (cross-season) |

## Identity helpers — `scraper.ids`

`school_slug(url)`, `sailor_slug(url)`, `split_sailor_name(name) -> (first, last, grad_year, registered)`,
`expand_races("1-3,5", all_races) -> [1,2,3,5]` (empty range → all races). Pure.

## Fetching — `scraper.Client`

```python
Client(base_url=DEFAULT, cache_dir=None, user_agent=DEFAULT, delay=0.0, timeout=30.0)
```
Owns one `httpx` session + the rate-limit clock (no module globals).

**`client.fetch(path, *, refresh=False, max_age=None, missing_ok=False) -> str | None`**
- Cache hit → cached HTML, unless `refresh=True` or older than `max_age` seconds.
- Miss → rate-limited GET (`delay`), store, return.
- **2xx** → HTML. **404** → raises, or `None` if `missing_ok`. **Other/transport** → raises.

Context manager (`with Client() as c:`) or `client.close()`. `delay=0.0` by default
(the site is static S3); raise it if you want to throttle.

## Assembling one regatta — `fleet_scores` / `team_scores`

Pure, HTML-in / model-out. These fold parse+adapt into one call (no redundant args)
and are the single home for assembly logic.

```python
scraper.fleet_scores(full_scores_html, season, slug, *, division_html=None) -> RegattaScores
scraper.team_scores(all_html, season, slug, *, full_scores_html=None, rotations_html=None) -> TeamRegattaScores
```
- `fleet_scores`: pass the `/full-scores/` HTML; optional `division_html={"A": html, ...}`
  fills per-division tiebreak ranks.
- `team_scores`: pass the `/all/` HTML; optional `full_scores_html` adds official
  rankings, `rotations_html` adds flight numbers.

`RegattaScores.teams[]` → `place, school, school_slug, total, divisions{div: DivisionResult}`;
`DivisionResult.races[]` → `race_num, points, penalty`. (Team models mirror this with
`rounds`/`matches`.) `teams == []` means "no fleet scores" (team regatta or not yet posted).

## Per-sailor results — `scraper.sailor_races`

The RP↔finish join — who sailed which race, and the place their boat earned. This is
what makes sailor-level analysis (ELO, head-to-head) possible.

```python
scraper.sailor_races(full_scores_html, sailors_html, season, slug) -> list[SailorRaceFinish]
scraper.team_sailor_races(all_html, sailors_html, season, slug, *, sailor_links=None) -> list[SailorRaceFinish]
```
`sailor_races` is for fleet racing (pass `sailors_html=None` for singlehanded);
`team_sailor_races` is the team-racing equivalent (joins RP to per-race earned
positions; team-label resolution is best-effort).
`SailorRaceFinish`: `sailor_slug, sailor_name, school_slug, team_name, division,
race_num, place, boat_role` ("skipper"/"crew"). Handles the singlehanded path
(RP synthesized from the full-scores page). Empty race-ranges are expanded to all
division races.

## Querying a whole season — `scraper.load`

Scrape a season (or several) into memory once, then loop/query.

```python
data = scraper.load("s26")                 # one season
data = scraper.load(["f24", "s25"])        # a full academic year
data = scraper.load("s26", client=my_client, refresh=False)
```

`Dataset`:

| Member | Type | |
|--------|------|-|
| `data.regattas` | `list[RegattaScores \| TeamRegattaScores]` | iterable; `for reg in data:` too |
| `data.results` | `list[Result]` | one per (regatta, school): `place, total, school_slug, regatta_slug, start_time, is_final` |
| `data.sailor_races` | `list[SailorRaceFinish]` | pre-joined with regatta `grade/boat/participant/start_time` |
| `data.finishes` | `list[Finish]` | per team·race place |
| `data.fleet()` / `data.team()` | `Dataset` | filter by scoring type (chainable) |
| `data.school(slug)` / `data.sailor(slug)` | `Dataset` | narrow to one school/sailor (chainable) |
| `data.results_frame()` / `data.sailor_races_frame()` | `DataFrame` | pandas escape hatch |

`load` is a **snapshot**: exact for a finished season, immutable; for a live season pass
`refresh=True` (or reload) so standings aren't frozen. Cached, so the first load is the
only slow part.

### The primary use cases, on top of `Dataset`

```python
# CSR — per-school season ranking (best N finishes)
best = (scraper.load(["f24","s25"]).fleet()
            .results_frame().sort_values("place").groupby("school_slug").head(N))

# Skipper ELO — chronological per-sailor rating
races = sorted(scraper.load(["f24","s25"]).sailor_races, key=lambda r: r.start_time)

# Comparison
navy, yale = (d := scraper.load("s26")).school("navy"), d.school("yale")
```

## Loading a specific set — `scraper.load_regattas`

Load an explicit, possibly cross-season set of regattas (unlike `load(only=…)`,
which scopes slugs to one season). This is what head-to-head uses to load *only*
the regattas two sailors shared.

```python
data = scraper.load_regattas([("s26", "hood"), ("f25", "danmark")])
```

## Comparing two sailors — `scraper.head_to_head`

A sailor's profile page (`urls.sailor_profile(slug)`) lists their *whole
cross-season history* in one fetch — each regatta with role, division, and
finishing place. `scraper.sailor_profile(html)` parses it into
`list[SailorParticipation]` (`season, slug, regatta_name, host, date, roles,
division, place, fleet_size`).

`head_to_head` uses that to compare two sailors **without scraping a season** —
it fetches the two profiles, intersects the regatta-divisions they shared, and
(optionally) loads *only* those to compare race by race.

```python
h = scraper.head_to_head("jane-doe", "john-roe")            # 2 fetches, no regatta loads
h.shared        # list[SharedRegatta]: (season, slug, division, place_a, place_b, fleet_size)
h.a_ahead, h.b_ahead                                        # regatta-divisions each finished ahead

h2 = scraper.head_to_head("jane-doe", "john-roe", races=True)   # loads only the shared regattas
h2.races        # list[RaceEncounter]: same regatta·division·race both sailed
h2.a_race_wins, h2.b_race_wins
```

| Call | Fetches | Grain |
|------|---------|-------|
| `head_to_head(a, b)` | 2 (both profiles) | regatta-division overlap + overall place |
| `head_to_head(a, b, races=True)` | 2 + shared regattas | individual races both sailed |
