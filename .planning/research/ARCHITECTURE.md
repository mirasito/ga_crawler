# Architecture Research

**Domain:** Competitive e-commerce price intelligence pipeline (weekly batch ETL)
**Researched:** 2026-05-05
**Confidence:** HIGH (well-established patterns in scraping/ETL community; verified across multiple sources)

---

## Standard Architecture

### System Overview

```
+------------------------------------------------------------+
|                     SCHEDULER (cron)                        |
|             Sun 02:00 -> python -m ga_crawler.run           |
+------------------------+------------------------------------+
                         |
                         v
+------------------------------------------------------------+
|                       ORCHESTRATOR                          |
|   - opens new run_id, manages phase order                   |
|   - aggregates partial-failure status, surfaces errors      |
+----+--------------+--------------+--------------+----------+
     |              |              |              |
     v              v              v              v
+----------+  +-----------+  +-----------+  +----------+
| CRAWLERS |  |  PARSERS  |  | NORMALIZER|  | MATCHER  |
| viled.kz |->| extract   |->| brand+name|->| left-join|
| goldapple|  | fields    |  | +volume   |  | by key   |
+----+-----+  +-----+-----+  +-----+-----+  +-----+----+
     |              |              |              |
     v              v              v              v
+------------------------------------------------------------+
|                  STORAGE LAYER (SQLite)                     |
|  runs | products | snapshots | matches | report_artifacts   |
|  immutable history; current view = latest snapshot per SKU  |
+------------------------+------------------------------------+
                         |
                         v
              +----------+-----------+
              |     REPORTER         |  pandas + openpyxl
              |  diff vs prev run    |  -> .xlsx + summary text
              +----------+-----------+
                         |
                         v
              +----------+-----------+
              |     DELIVERY         |  python-telegram-bot
              |  Telegram + Excel    |  posts to channel/chat
              +----------+-----------+
                         |
                         v
+------------------------------------------------------------+
|     OBSERVABILITY: structured logs, run row update,         |
|     failure summary in delivery message                     |
+------------------------------------------------------------+
```

### Component Responsibilities

| Component | Responsibility (does) | Boundary (does NOT) | Typical Implementation |
|-----------|-----------------------|---------------------|------------------------|
| **Config** | Load brand list, URLs, secrets, limits, schedule | Make business decisions, persist runtime state | YAML for static + `.env` for secrets via `pydantic-settings` |
| **Scheduler** | Trigger weekly run, capture exit code | Know about scraping logic | OS-level `cron` (Linux) / Task Scheduler (Windows) calling `python -m ga_crawler` |
| **Orchestrator** | Open `run_id`, sequence phases, aggregate status, ensure DB row updated even on crash | Fetch HTML, parse fields | Top-level `run.py` with try/except per phase, structured logging |
| **Crawler** | Discover URLs, fetch raw HTML/JSON; respect rate limits, handle anti-bot, retry transient errors | Extract structured fields, decide what's a "match" | `httpx` for viled (likely simple), `playwright` (sync API) for goldapple |
| **Parser** | Take HTML/JSON -> structured `RawProduct` dicts (one per site) | Fetch network, normalize across sites | Per-site module with CSS/XPath selectors via `parsel`; prefer JSON-LD when available |
| **Normalizer** | Lowercase, strip punctuation, extract volume token, canonicalize brand spellings | Cross-site comparison logic | Pure functions, no I/O; `re` + small lookup dicts |
| **Matcher** | Cross-site join: build `(brand, name_norm, volume_norm)` key, produce `matches` rows | Calculate price delta semantics; format report | SQL `INNER JOIN` on normalized keys, written to `matches` table |
| **Storage** | Persist runs, snapshots, matches; provide queries for "current view" and "previous run" | Business logic | SQLite + thin DAO layer (`sqlite3` stdlib or `SQLAlchemy Core`) |
| **Reporter** | Diff current run vs previous; build summary stats + Excel workbook | Send messages, fetch data | `pandas` + `openpyxl` (multi-sheet xlsx) |
| **Delivery** | Post text summary + Excel attachment to Telegram | Decide what to report | `python-telegram-bot` or raw `requests` to Bot API |
| **Observability** | Structured logs to file + console; update `runs` row with success/failure counts | Be a metrics platform | `structlog` (or stdlib `logging` with JSON formatter) + `runs` table |

**Key boundary principle:** **Crawler-Parser-Normalizer-Matcher are pure pipelines** (input -> output). Side effects (DB writes, Telegram, files) live only in Storage / Reporter / Delivery. This is the "pipe and filter" pattern — testable in isolation, composable.

---

## Recommended Project Structure

```
ga_crawler/
├── pyproject.toml             # uv/poetry deps, ruff, pytest config
├── README.md
├── .env.example               # TELEGRAM_BOT_TOKEN, PROXY_URL placeholders
├── config/
│   ├── brands.yaml            # canonical brand list from viled (source of truth)
│   ├── sites.yaml             # per-site config: base URLs, selectors, rate limits
│   └── settings.yaml          # global: schedule, timeouts, retry counts
├── src/ga_crawler/
│   ├── __init__.py
│   ├── __main__.py            # `python -m ga_crawler` entrypoint
│   ├── run.py                 # orchestrator: full pipeline for one run_id
│   ├── config.py              # pydantic Settings, loads YAML + .env
│   ├── models.py              # dataclasses: RawProduct, NormalizedProduct, Match
│   ├── crawlers/
│   │   ├── __init__.py
│   │   ├── base.py            # abstract Crawler protocol
│   │   ├── viled.py           # full-catalog crawl (httpx)
│   │   └── goldapple.py       # brand-filtered crawl (playwright + stealth)
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── viled.py
│   │   └── goldapple.py
│   ├── normalize.py           # pure functions: normalize_brand, extract_volume, ...
│   ├── matcher.py             # cross-site join logic
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── schema.sql         # CREATE TABLE statements + indexes
│   │   ├── migrations/        # versioned schema changes (v2+)
│   │   └── dao.py             # insert_run, insert_snapshot, get_previous_run, ...
│   ├── reporting/
│   │   ├── __init__.py
│   │   ├── diff.py            # compute deltas vs previous run
│   │   ├── excel.py           # build .xlsx workbook
│   │   └── summary.py         # build text summary for Telegram
│   ├── delivery/
│   │   ├── __init__.py
│   │   └── telegram.py        # send message + document
│   └── obs/
│       ├── __init__.py
│       └── logging.py         # configure structlog/JSON logs
├── tests/
│   ├── conftest.py            # shared fixtures
│   ├── fixtures/
│   │   ├── viled/             # saved HTML samples (one per page type)
│   │   └── goldapple/
│   ├── unit/
│   │   ├── test_normalize.py  # pure-function tests
│   │   ├── test_matcher.py    # given normalized inputs, assert matches
│   │   ├── test_parser_viled.py      # parser against fixture HTML
│   │   └── test_parser_goldapple.py
│   └── integration/
│       ├── test_storage.py    # against in-memory SQLite
│       └── test_run_e2e.py    # full pipeline with mocked crawlers
├── data/                      # gitignored
│   └── ga_crawler.db          # SQLite file
└── logs/                      # gitignored
    └── run-2026-05-04.log
```

### Structure Rationale

- **`src/` layout** (vs. flat module): standard modern Python, prevents accidental imports of project root, plays well with packaging tools (uv, poetry, hatch).
- **One folder per pipeline stage** (`crawlers/`, `parsers/`, `reporting/`): each stage is a swappable concern; aligns with the build-order phases below.
- **`crawlers/base.py` Protocol**: lets you start with one site, add the second without refactoring the orchestrator.
- **`normalize.py` flat module, not folder**: pure functions don't need a sub-package; resist the urge to over-structure.
- **`storage/schema.sql` over migrations folder on day 1**: SQLite + small project — one SQL file is enough until v2; introduce a migrations folder when you have a second migration.
- **`tests/fixtures/` with real HTML**: parser correctness is tested against captured HTML, not live network — fast and deterministic.
- **`config/` outside `src/`**: edited by ops, not packaged; YAML at the repo root makes weekly tweaks trivial.

---

## Architectural Patterns

### Pattern 1: Pipe-and-Filter (modular monolith)

**What:** Each stage is a callable that takes structured input, returns structured output. The orchestrator wires them together. No global state, no framework runtime.

**When to use:** Solo developer, batch job, fewer than ~10 modules. This project is the textbook fit.

**Trade-offs:**
- Pro: trivially testable; each stage replaceable; debuggable by running stages individually in a REPL
- Pro: zero infrastructure (no Airflow, no Celery, no message broker)
- Con: no built-in retries/parallelism — you build the bits you need yourself
- Con: a single Python process — crash kills the whole run (mitigated by per-stage try/except + checkpointing to DB)

**Example:**
```python
# src/ga_crawler/run.py
from ga_crawler import crawlers, parsers, normalize, matcher, storage, reporting, delivery
from ga_crawler.obs.logging import get_logger

log = get_logger(__name__)

def main() -> int:
    run_id = storage.dao.start_run()
    try:
        # Phase 1: crawl + parse viled (full catalog)
        viled_raw = crawlers.viled.crawl_all()
        viled_products = [parsers.viled.parse(html) for html in viled_raw]
        viled_norm = [normalize.product(p) for p in viled_products]
        storage.dao.insert_snapshot(run_id, "viled", viled_norm)

        # Phase 2: crawl + parse goldapple (only brands present in viled)
        brands = sorted({p.brand for p in viled_norm})
        ga_raw = crawlers.goldapple.crawl_brands(brands)
        ga_products = [parsers.goldapple.parse(html) for html in ga_raw]
        ga_norm = [normalize.product(p) for p in ga_products]
        storage.dao.insert_snapshot(run_id, "goldapple", ga_norm)

        # Phase 3: match + diff + report + deliver
        matches = matcher.match(run_id)
        storage.dao.insert_matches(run_id, matches)
        report = reporting.build(run_id)
        delivery.telegram.send(report)

        storage.dao.finish_run(run_id, status="success")
        return 0
    except Exception as e:
        log.exception("run failed", run_id=run_id)
        storage.dao.finish_run(run_id, status="failed", error=str(e))
        delivery.telegram.send_failure(run_id, str(e))  # best-effort
        return 1
```

### Pattern 2: Immutable Snapshot per Run (no in-place updates)

**What:** Every weekly run inserts a complete `snapshots` row per product seen this week. Products are never updated; the "current view" is a query: `SELECT * FROM snapshots WHERE run_id = (latest)`.

**When to use:** Whenever historical comparison matters (this project's whole point). Aligns with SCD Type 2 / event-sourcing thinking but simpler.

**Trade-offs:**
- Pro: full audit trail, trivial backfills, idempotent (re-running a `run_id` is safe — delete-then-reinsert)
- Pro: dead-simple delta queries (`run_id = N` vs `run_id = N-1`)
- Pro: easy to recover from bad parses (mark run failed, run again)
- Con: storage grows linearly (~10K SKUs × 52 weeks × ~200 bytes ≈ 100MB/year — trivial for SQLite)
- Con: "what is the current price?" requires a JOIN/subquery (solve with a `v_current_products` view)

### Pattern 3: Per-Site Crawler Adapter (Protocol-based)

**What:** Each site has a `Crawler` class implementing a common interface. Adding a third competitor = one new file. Anti-bot strategy lives inside the adapter, not leaked into the orchestrator.

**When to use:** Multi-source scraping where sites differ in tech (one needs Playwright, the other doesn't).

**Trade-offs:**
- Pro: orchestrator doesn't care if it's httpx or Playwright under the hood
- Pro: sync/async choice can differ per crawler (see Sync vs Async below)
- Con: small abstraction cost — easy to over-design if you stop at 2 sites

**Example:**
```python
# src/ga_crawler/crawlers/base.py
from typing import Protocol, Iterable
from ga_crawler.models import RawProduct

class Crawler(Protocol):
    site: str
    def crawl(self, brands: list[str] | None = None) -> Iterable[RawProduct]: ...
```

### Pattern 4: Hierarchical Parser Fallbacks

**What:** Parsers attempt the most stable data source first (JSON-LD `<script type="application/ld+json">`), fall back to inline `__NEXT_DATA__` / dataLayer JSON, fall back to CSS selectors only as last resort. Captured selector breakage in logs.

**When to use:** Any production scraper; visual markup is the most fragile thing on the page.

**Trade-offs:**
- Pro: resilient to redesigns
- Pro: cleaner data (structured > extracted)
- Con: more code paths to test

---

## Data Flow

### End-to-end Flow (one weekly run)

```
[cron Sun 02:00]
    |
    v
[run_id = INSERT INTO runs(started_at)]
    |
    v
[CRAWL viled (full catalog)] --httpx--> raw HTML pages -> [PARSE viled] -> RawProduct[]
    |                                                                          |
    |                                                                          v
    |                                                    [NORMALIZE] -> NormalizedProduct[]
    |                                                                          |
    |                                                                          v
    |                                                    [INSERT snapshots WHERE site='viled', run_id=N]
    |
    v
[derive brand_list FROM snapshots WHERE site='viled', run_id=N]
    |
    v
[CRAWL goldapple FILTERED by brand_list] --playwright--> raw HTML
    |                                                       |
    |                                                       v
    |                                       [PARSE goldapple] -> RawProduct[] -> [NORMALIZE]
    |                                                                              |
    |                                                                              v
    |                                                    [INSERT snapshots WHERE site='goldapple', run_id=N]
    v
[MATCH: SQL JOIN snapshots(viled, run=N) x snapshots(goldapple, run=N) ON (brand, name_norm, volume_norm)]
    |
    v
[INSERT INTO matches(run_id, viled_snapshot_id, ga_snapshot_id, price_delta, ...)]
    |
    v
[DIFF vs runs.id = N-1: changed prices, new SKUs, dropped SKUs, new promos]
    |
    v
[BUILD Excel: 4 sheets - Summary | Matched SKUs | Viled-only | GA-only]
[BUILD text summary: "X SKUs scanned, Y matched, Z avg delta, W new promos"]
    |
    v
[SEND to Telegram chat (text + .xlsx attachment)]
    |
    v
[UPDATE runs SET finished_at, status='success', counts=...]
```

### Storage Schema Sketch

```sql
-- Immutable run log: one row per weekly job
CREATE TABLE runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,                    -- ISO8601
    finished_at     TEXT,
    status          TEXT NOT NULL,                    -- 'running'|'success'|'partial'|'failed'
    viled_count     INTEGER,
    goldapple_count INTEGER,
    matched_count   INTEGER,
    error           TEXT
);

-- Snapshot of each product seen on each site, per run.
-- This IS the historical record. No UPDATEs to existing rows.
CREATE TABLE snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES runs(id),
    site            TEXT NOT NULL,                    -- 'viled' | 'goldapple'
    site_sku_id     TEXT,                             -- whatever the site uses internally
    url             TEXT NOT NULL,
    brand_raw       TEXT NOT NULL,
    name_raw        TEXT NOT NULL,
    volume_raw      TEXT,                             -- e.g. "50 ml"
    brand_norm      TEXT NOT NULL,                    -- lowercase, canonical
    name_norm       TEXT NOT NULL,
    volume_norm     TEXT,                             -- e.g. "50ml"
    price           REAL,                             -- effective price
    price_old       REAL,                             -- pre-discount, NULL if no promo
    in_stock        INTEGER,                          -- 0/1
    scraped_at      TEXT NOT NULL,
    UNIQUE (run_id, site, site_sku_id)
);
CREATE INDEX idx_snap_run_site ON snapshots(run_id, site);
CREATE INDEX idx_snap_match_key ON snapshots(brand_norm, name_norm, volume_norm);

-- Pre-computed cross-site joins, one row per matched pair per run
CREATE TABLE matches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES runs(id),
    viled_snapshot_id   INTEGER NOT NULL REFERENCES snapshots(id),
    ga_snapshot_id      INTEGER NOT NULL REFERENCES snapshots(id),
    match_key           TEXT NOT NULL,                -- "brand|name|volume" for debugging
    price_delta_abs     REAL,                         -- ga_price - viled_price
    price_delta_pct     REAL,
    UNIQUE (run_id, viled_snapshot_id, ga_snapshot_id)
);
CREATE INDEX idx_match_run ON matches(run_id);

-- Convenience view: "what's the current state?"
CREATE VIEW v_current_snapshots AS
  SELECT * FROM snapshots
  WHERE run_id = (SELECT MAX(id) FROM runs WHERE status IN ('success','partial'));
```

**Why this schema:**
- `runs` is the anchor for everything; failures are first-class (status field)
- `snapshots` is append-only — true immutable history, easy backfill, easy delete-and-retry per run
- `matches` is denormalized convenience — could be a view, but precomputing speeds up reporting and lets you store the matching strategy version
- No separate `products` master table on v1 — the natural key `(brand_norm, name_norm, volume_norm)` is sufficient. Add a master table in v2 if/when fuzzy matching arrives.

### Key Data Flows

1. **URL discovery -> extraction:** crawler yields HTML; parser produces `RawProduct`. Pure data, no DB touch.
2. **Extraction -> normalization:** `RawProduct -> NormalizedProduct` via pure functions.
3. **Site results -> storage:** the only DB write is at end of each site's pass — atomic per-site checkpoint.
4. **Snapshot -> match:** matcher reads from DB (not from in-memory lists), so a partial run can be re-matched without re-crawling.
5. **Match -> report -> deliver:** all reads from DB by `run_id`; report is also a pure transform until the final Telegram call.

---

## Build Order (Phase Decomposition)

This is the dependency-correct order; each phase produces something runnable end-to-end (vertical slice over horizontal layering).

| Phase | Component(s) | Vertical Slice Goal | Depends On |
|-------|--------------|---------------------|------------|
| **0. Project skeleton** | repo, config, logging, models, schema | `python -m ga_crawler` runs and exits 0; DB initialized | — |
| **1. viled crawler + parser + storage** | crawlers/viled, parsers/viled, normalize, storage | One command: scrape viled, write snapshots row, query results | Phase 0 |
| **2. goldapple crawler + parser** | crawlers/goldapple (Playwright), parsers/goldapple, anti-bot strategy | Brand-filtered scrape working against real site; writes snapshots | Phase 1 (needs viled brand list) |
| **3. matcher** | matcher.py, matches table | Cross-site join produces matches rows for run_id | Phase 1 + 2 |
| **4. reporter** | reporting/diff, reporting/excel, reporting/summary | `.xlsx` file generated locally with all 4 sheets | Phase 3 (and ideally 2 historical runs) |
| **5. delivery** | delivery/telegram | Excel + summary posted to Telegram chat | Phase 4 |
| **6. scheduler + observability hardening** | cron entry, runs row updated on every exit, structured logs, failure alerts | Cron-driven weekly runs visible in Telegram even when they fail | Phase 5 |

**Why this order:**
- viled before goldapple: viled defines the brand filter for goldapple; without viled, there's no input for the goldapple crawl.
- crawler before reporter: you can't report on data you haven't collected.
- delivery last: reporter produces a file on disk first, which is testable; only after that wrap it in Telegram. Don't entangle "we built a report" with "we got Telegram credentials right."
- scheduler is intentionally last: the manual `python -m ga_crawler` command must be rock-solid before automation hides any issues.

**Phase 2 is the highest-risk phase** (anti-bot on goldapple). Worth a research spike before committing the design.

---

## Architectural Decisions (Specific)

### Decision: Modular Monolith (not single script, not microservices)

**Recommended:** Modular monolith — one Python package, one process, multiple modules with clear boundaries.

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| Single script (one .py file) | Trivial to start | Untestable, one parser bug taints everything, painful to extend | NO |
| **Modular monolith** | Testable in isolation, one process to run, no infra | Need self-discipline to keep boundaries | **YES** |
| Service-oriented (Celery/queues) | Independent scaling, resilient | Massive overkill for a weekly batch with 1 user | NO |

A weekly batch with a single operator and ~30K total SKUs has zero need for a queue or worker pool. Resist the urge.

### Decision: Sync API for v1, Targeted Async Where it Pays

**Recommended:** Start with **synchronous code** everywhere, including Playwright's sync API. Add `asyncio` only inside the goldapple crawler if/when measurement shows the run is too slow.

**Reasoning:**
- viled is small — sync `httpx` with a small `time.sleep` between requests is fine
- goldapple is the slow link; if it takes 2 hours sync vs 30 min async, swap the crawler internally — orchestrator unchanged
- async Playwright is genuinely harder to debug; for a solo dev's first version, sync wins on iteration speed
- Scrapy's reactor model conflicts with sync code elsewhere — picking Scrapy commits the whole pipeline to async-style. Don't unless you need it.

**Concrete recommendation:** Plain Playwright Sync API + `httpx` sync, both behind the `Crawler` Protocol. Promote the Playwright crawler to async only after Phase 6 if benchmarks demand it.

### Decision: Crawler and Matcher in the Same Run (with checkpoints)

**Recommended:** **One scheduled job runs all phases** for a `run_id`, but each phase commits to DB before the next starts.

**Reasoning:**
- Matching against partial data is meaningless — must crawl both sites first
- But: viled finishes -> commit; goldapple crashes mid-way -> the orchestrator can resume just goldapple by detecting `run_id` has viled snapshots but no goldapple snapshots
- Splitting into separate cron jobs adds coordination problems (race conditions, did viled finish?) for no benefit at this scale

**Practical rule:** the orchestrator in `run.py` must be re-runnable for a given `run_id` and skip already-completed phases. Cheap to build with a few `SELECT COUNT(*)` checks.

### Decision: "Current" View as a Query, Not a Table

**Recommended:** Don't maintain a separate "current products" table. Define a SQL view `v_current_snapshots = SELECT * FROM snapshots WHERE run_id = (latest successful run)`.

**Reasoning:**
- Avoids dual-write consistency bugs (snapshot saved but current table forgot to update)
- Reflects the truth: there is no "current" — there are weekly snapshots, latest is current
- Cheap on SQLite at our scale (~30K rows / week × 52 weeks = 1.5M rows; indexed lookup is sub-millisecond)

### Decision: YAML for Static Config, .env for Secrets, DB-Driven for Dynamic Data

**Recommended split:**
- **YAML (`config/*.yaml`)**: brand list, base URLs, CSS selectors, rate limits, retry counts — version-controlled, code-reviewable
- **`.env` via `pydantic-settings`**: `TELEGRAM_BOT_TOKEN`, `PROXY_URL`, `TELEGRAM_CHAT_ID` — secrets, never in git
- **DB**: nothing config-like. `runs`, `snapshots`, `matches` are data, not config
- **NOT recommended**: DB-driven config (a `config` table) — overkill, adds a moving part for no win in a single-operator system

### Decision: Logging via `structlog` + JSON to file

**Recommended:** Structured logs with `run_id` as a bound context variable; JSON-formatted file logs (so `jq` works); human-readable console for live debugging. Always update the `runs` row with success/fail counts so you don't need to grep logs to know what happened.

```python
log = structlog.get_logger().bind(run_id=run_id, site="goldapple")
log.info("crawl_started", brand_count=len(brands))
```

**Failure surfacing strategy:**
1. Per-stage `try/except` -> log with full traceback, mark phase status in `runs` table
2. Orchestrator-level `try/except` catches anything per-stage missed
3. Best-effort Telegram alert on failure (separate from success report) — "Run 42 failed at goldapple_crawl: TimeoutError"
4. Operator (you) gets a Telegram message every Monday — either the report or the failure notice. Silent failure is impossible by design.

### Decision: Testing Strategy

**Three layers, weighted toward unit:**

| Layer | What | Tools | When run |
|-------|------|-------|----------|
| **Unit (most tests)** | normalize, matcher logic, parser against fixture HTML, diff/report builders | `pytest`, `unittest.mock`, `responses` for `httpx` | Every commit |
| **Integration** | storage DAO against in-memory SQLite, end-to-end with mocked crawlers | `pytest` + `:memory:` SQLite | Every commit |
| **Smoke (manual)** | One real fetch of one viled page, one goldapple page; pinned to fixtures occasionally refreshed | A `make refresh-fixtures` target | Weekly / before phase transition |

**Key tactic:** capture real HTML samples to `tests/fixtures/{site}/{page_type}.html` once, commit them. Parsers test against these. When the site redesigns and a parser breaks in production, refresh the fixture, write a failing test, fix the parser. **No live network in the unit suite.**

For Scrapy users specifically, [`scrapy-mock`](https://pypi.org/project/scrapy-mock/) records real responses as fixtures. We're not using Scrapy, but the pattern transfers directly.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **Current (1 site pair, ~30K SKU/week, 1 operator)** | SQLite file, sync Python, cron, single VPS. No changes needed. |
| **3-5 sites, ~100K SKU/week** | Move goldapple-style crawlers to async Playwright (5x throughput). Add a `sites` table and `site_id` FK to snapshots. Still SQLite. |
| **10+ sites, daily runs, ~1M SKU/run** | Migrate SQLite -> Postgres (concurrent writes, better indexing, JSONB for raw blobs). Split crawl/match/report into separate processes triggered sequentially. Consider Prefect/Dagster for orchestration. |
| **Multiple operators, dashboards** | Add a small FastAPI app for browsing runs/diffs. At this point, fully justified to add Postgres + a small scheduler service. |

### Scaling Priorities (what breaks first, in order)

1. **goldapple anti-bot blocks**: this kills runs long before any DB or memory issue. Mitigation = paid residential proxies + headless stealth + behavioral pacing. Already on the roadmap.
2. **Parser drift after site redesign**: fix-time = hours, blast radius = one weekly run. Mitigation = JSON-LD-first parsing, fixture refresh discipline, Telegram failure alerts.
3. **Run duration > 4-6 hours**: if goldapple takes too long, we miss the Monday-morning deadline. Mitigation (in order): brand-list pruning, async crawler, distributed crawl across two VPS.
4. **SQLite write contention**: not a real issue with one writer. Becomes one only if a future dashboard reads while a run writes. Migrate to Postgres at that point.
5. **DB size**: 100MB/year. Non-issue for years.

---

## Anti-Patterns

### Anti-Pattern 1: "Update the products table in place"

**What people do:** Maintain a single `products` table; on each run, UPDATE existing rows with new prices. Lose the old price.
**Why it's wrong:** Destroys the historical record this entire project exists to provide. No trends, no delta reports, no audit trail. Re-running a failed job is destructive.
**Do this instead:** Append-only `snapshots`, never UPDATE. The "current" view is a query.

### Anti-Pattern 2: "One mega-spider that does everything"

**What people do:** A single `scraper.py` that fetches, parses, matches, builds Excel, sends to Telegram, all in 600 lines.
**Why it's wrong:** Untestable; a parser bug means re-running the entire 2-hour crawl; can't replay a failed report from existing data; can't add a second site without surgery.
**Do this instead:** Modular monolith with the boundaries above. Each stage reads/writes through the DB; each is independently re-runnable for a given `run_id`.

### Anti-Pattern 3: "Skip the run_id, timestamp every row"

**What people do:** Every `snapshots` row has `created_at`. To find "last week", `WHERE created_at > NOW() - INTERVAL '7 days'`.
**Why it's wrong:** A run that takes 3 hours straddles a date boundary; partial failures leave half-runs in the data; "the previous run" is genuinely ambiguous; reasoning about idempotency becomes painful.
**Do this instead:** A `runs` table with explicit `run_id`. Everything joins through `run_id`. "Previous run" = `MAX(run_id) WHERE id < current AND status='success'`.

### Anti-Pattern 4: "Catch and swallow exceptions everywhere"

**What people do:** Wrap every fetch in try/except, log a warning, continue silently.
**Why it's wrong:** A 95%-failed run looks identical to a 100%-successful one. You ship empty reports for weeks before noticing.
**Do this instead:** Catch exceptions per *unit of work* (one product, one page), record the failure in a counter, log with context. At end of phase, evaluate: if `failure_rate > threshold`, fail the run loudly. The `runs` row records `viled_count` / `goldapple_count` / `error_count` so a Telegram message says "scanned 27,431 / 28,000 products, 569 errors — investigate."

### Anti-Pattern 5: "Use Scrapy because everyone uses Scrapy"

**What people do:** Default to Scrapy because it's the most-Googled scraping framework.
**Why it's wrong:** Scrapy commits you to an async-callback world (Twisted reactor) that interacts awkwardly with sync code in matcher/reporter/Telegram. For two sites where one needs Playwright anyway, Scrapy adds complexity without payoff. Its declared sweet spot is large-scale crawls with thousands of spiders, not "two sites once a week."
**Do this instead:** Plain `httpx` + `parsel` for viled, `playwright` (sync) for goldapple, both behind a small `Crawler` Protocol. You get 90% of Scrapy's value (item pipelines = our normalize+storage, contracts = our pytest fixtures) at 10% of the lock-in.

### Anti-Pattern 6: "Couple report generation to delivery"

**What people do:** The function that builds the Excel also sends it to Telegram in one call.
**Why it's wrong:** Can't preview reports without spamming Telegram; a Telegram outage loses the report; testing requires mocking out HTTP.
**Do this instead:** Reporter writes a file to disk, returns its path. Delivery reads the file, sends it. Two stages, two responsibilities. Bonus: every report is also archived on disk.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **viled.kz** | Direct HTTP (`httpx`), pagination, sleep between requests | Likely simple HTML; check for sitemap.xml first to discover URLs |
| **goldapple.kz** | Playwright Sync API + stealth + residential proxy | Cloudflare/DataDome very likely; expect to iterate on the bypass strategy |
| **Telegram Bot API** | `python-telegram-bot` library, single bot, 1 chat | `sendDocument` for the Excel attachment; max 50MB (we'll be far under) |
| **Proxy provider** | HTTP/SOCKS proxy URL via env var, passed to crawler | Decide residential vs datacenter after the goldapple research spike |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Orchestrator -> Crawler | Function call, returns iterable of `RawProduct` | No globals; orchestrator passes config explicitly |
| Crawler -> Parser | Function call: `parse(html: str) -> list[RawProduct]` | Parsers stateless, pure |
| Parser -> Normalize | Function call, dataclass in -> dataclass out | Pure, no I/O |
| Normalize -> Storage | DAO call: `dao.insert_snapshot(run_id, site, products)` | Single transaction per site per run |
| Storage -> Matcher | DAO query: `dao.snapshots_for_run(run_id, site)` returns rows | Matcher reads from DB, writes back to DB — DB is the integration bus |
| Matcher -> Reporter | DAO query: `dao.matches_for_run(run_id)` + `dao.previous_run()` | Reporter reads only; never writes |
| Reporter -> Delivery | File path + summary string returned from reporter | Delivery is a thin wrapper around Telegram Bot API |

**Single integration backbone:** the SQLite database. Every cross-stage communication goes through it. This is what makes individual stages re-runnable for a `run_id`.

---

## Sources

- [Building a Modular Web Scraper with Scrapy-Like Architecture (Medium)](https://medium.com/@zakimaliki/building-a-modular-web-scraper-with-scrapy-like-architecture-16eb7f2a643c) — modular vs script trade-offs (MEDIUM confidence)
- [Scrapy Item Pipeline docs](https://docs.scrapy.org/en/latest/topics/item-pipeline.html) — official pipeline pattern, why we apply it without using Scrapy itself (HIGH confidence)
- [Scrapy Spider Contracts](https://docs.scrapy.org/en/latest/topics/contracts.html) — testing pattern for spider callbacks (HIGH confidence)
- [scrapy-mock on PyPI](https://pypi.org/project/scrapy-mock/) — fixture-recording approach for parser tests (MEDIUM confidence)
- [How to Build an Automated Competitor Price Monitoring System with Python (Firecrawl)](https://www.firecrawl.dev/blog/automated-competitor-price-scraping) — end-to-end reference architecture (MEDIUM confidence)
- [How to Track Competitor Prices Using Web Scraping (Scrapfly)](https://scrapfly.io/blog/posts/how-to-track-competitor-pricing-using-web-scraping) — JSON-LD-first parsing, normalization tactics (MEDIUM confidence)
- [Web Scraping with Playwright and Python (Scrapfly)](https://scrapfly.io/blog/posts/web-scraping-with-playwright-and-python) — sync vs async trade-offs (MEDIUM confidence)
- [scrapy-playwright integration (GitHub)](https://github.com/scrapy-plugins/scrapy-playwright) — reference for hybrid stack we explicitly chose NOT to use (HIGH confidence)
- [How to Bypass Cloudflare with Playwright in 2026 (BrowserStack)](https://www.browserstack.com/guide/playwright-cloudflare) — anti-bot strategy options (MEDIUM confidence)
- [Playwright Stealth: Bypass Bot Detection (Scrapfly)](https://scrapfly.io/blog/posts/playwright-stealth-bypass-bot-detection) — stealth limitations, why proxies are still needed (MEDIUM confidence)
- [Stop Losing Data History: dbt Snapshots SCD Type 2 (Pmunhoz Blog)](https://blog.pmunhoz.com/dbt/dbt-snapshots-guide-scd-type-2) — historical data modeling, basis for our run/snapshot schema (MEDIUM confidence)
- [Slowly Changing Dimensions Type 2 (Wikipedia)](https://en.wikipedia.org/wiki/Slowly_changing_dimension) — canonical reference (HIGH confidence)
- [ETL: Idempotency in Data Pipelines (Medium)](https://fahadthedatascientist.medium.com/etl-idempotency-in-data-pipelines-1f323f3f573d) — re-runnable pipelines, basis for our run_id design (MEDIUM confidence)
- [Building an Idempotent Data Pipeline (Fivetran Blog)](https://www.fivetran.com/blog/building-an-idempotent-data-pipeline) — partition + replace pattern (MEDIUM confidence)
- [Modular Monolith in Python (breadcrumbscollector.tech)](https://breadcrumbscollector.tech/modular-monolith-in-python/) — sweet-spot architecture for solo developers (MEDIUM confidence)
- [Structuring Your Project (Hitchhiker's Guide to Python)](https://docs.python-guide.org/writing/structure/) — `src/` layout rationale (HIGH confidence)
- [Scrapy Error Handling & Retry Logic (DEV.to)](https://dev.to/ikram_khan/scrapy-error-handling-retry-logic-when-things-go-wrong-4f5d) — retry/backoff patterns we apply manually (LOW-MEDIUM confidence)
- [Building a Robust Web Scraper with Error Handling and Retry Logic (Medium)](https://medium.com/techtrends-digest/building-a-robust-web-scraper-with-error-handling-and-retry-logic-3e7b6541bbbc) — partial-failure tolerance (LOW-MEDIUM confidence)

---
*Architecture research for: competitive e-commerce price intelligence pipeline (weekly batch, Python)*
*Researched: 2026-05-05*
