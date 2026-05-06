---
phase: 03-goldapple-crawl
plan: 04
subsystem: crawler-fetcher
tags: [camoufox, tenacity, async-context-manager, anti-bot-tier-2, fetcher, retry-policy, per-sku-isolation]

# Dependency graph
requires:
  - phase: 03-goldapple-crawl
    provides: Wave 0 (pyproject.toml constants, Protocol contracts, fixtures); Wave 1 (sitemap + slug-fy); Wave 2 (microdata parser + GATE_TITLE_MARKER + GATE_SHELL_MAX_BYTES + detect_state)
  - phase: 01-goldapple-reconnaissance-spike
    provides: spike notebook.py L41-49 operational constants, L128-191 fetch_one pattern, L207-214 Camoufox bootstrap, L217-257 run_loop pattern; SKILL.md locked Camoufox kwargs (geoip, locale, humanize, persistent_context); MEMO.md sign-off (99/100 D-13 PASS)
provides:
  - GoldappleFetcher async context manager (D-311 fresh tmp profile per run, always-cleanup on success AND exception per Pitfall 7)
  - TransientFetchError exception type for tenacity retry policy
  - _goto_with_retry tenacity decorator (CRAWL-04 — stop_after_attempt(3) + wait_exponential_jitter(2, 30) + retry_if_exception_type((TransientFetchError, PWTimeout)))
  - fetch_one_isolated module-level wrapper (CRAWL-03 — exception-swallow + stats counter, never bubbles)
  - run_loop sequential drive with random.uniform(3, 5) pacing + injectable sleep_fn for tests
  - fetch_one record-shape compatible with spike notebook.py for log replay forward compatibility
affects: [03-05 (Wave 4 smoke probe consumes GoldappleFetcher), 03-06 (Wave 5 orchestrator drives run_loop), 03-07 (Wave 6 manual live smoke), Phase 7 (cron deployment uses GoldappleFetcher as the production engine)]

# Tech tracking
tech-stack:
  added: []  # camoufox, tenacity, structlog, playwright (transitive) — all already pinned in Wave 0
  patterns:
    - "Async context manager with __aenter__-time tmp profile cleanup on boot failure"
    - "Two-layer error handling: tenacity retry inside fetch_one, broad try/except outside, fetch_one_isolated as outermost CRAWL-03 boundary"
    - "Operational constants duplicated in module + pyproject.toml (module = code-as-source-of-truth defaults; pyproject = ops-overridable namespace)"
    - "Lazy import of camoufox.async_api inside __aenter__ — keeps module importable on machines without Camoufox binary (test isolation; CI smoke)"
    - "Lazy build of tenacity retry decorator via _make_retry_decorator() factory — keeps PWTimeout import resilient when playwright is not installed"

key-files:
  created:
    - src/ga_crawler/fetchers/__init__.py
    - src/ga_crawler/fetchers/goldapple.py
    - tests/unit/test_retry_policy.py
    - tests/unit/test_fetcher_isolation.py
    - tests/integration/__init__.py
    - tests/integration/test_goldapple_fetch_loop_mocked.py
  modified: []

key-decisions:
  - "tenacity decorator built via factory function (_make_retry_decorator) so PWTimeout import is fault-tolerant on systems without playwright (Camoufox bundles its own Firefox; some test envs may not expose playwright.async_api)"
  - "Catch-all exception path in _goto_with_retry wraps non-TransientFetchError/non-Timeout exceptions as TransientFetchError → enables retry on transient network gunk (DNS hiccups, TCP RSTs) without hand-listing every connection-error class"
  - "fetch_one's broad outer try/except is intentional — turns any unexpected error into block=True+block_reason=exception so fetch_one_isolated does NOT need to re-classify; isolation is purely about counter+log"
  - "instance-method fetch_one_isolated delegates to module-level free function to keep both forms callable; orchestrator (Wave 5) chooses based on whether it has the fetcher instance or just a callable"

patterns-established:
  - "Pattern: async-context-manager fetcher with profile-lifecycle cleanup on exception path (try/finally in __aexit__ + cleanup-on-boot-failure in __aenter__)"
  - "Pattern: tenacity stop_after_attempt(3) + wait_exponential_jitter(2, 30) + retry_if_exception_type((TransientFetchError, PWTimeout)) reraise=True is the canonical retry policy for ALL Phase 3 network calls (sitemap, fetcher, smoke probe)"
  - "Pattern: spike-style fetch record dict {url, status, html_size, title, gate_cleared, gate_cleared_after_ms?, html?, block, block_reason?, error?, timing_ms} is the canonical handoff shape between fetcher and parser (back-compat with notebook.py log replay)"

requirements-completed: [CRAWL-02]

# Metrics
duration: 5 min
completed: 2026-05-06
---

# Phase 3 Plan 04: Wave 3 Camoufox Fetcher Summary

**Production-quality `GoldappleFetcher` async context manager with D-311 fresh-profile lifecycle, tenacity retry/backoff (CRAWL-04), per-SKU isolation (CRAWL-03), and spike-style fetch-record dict — wraps spike `notebook.py` patterns into a CrawlerProtocol-conforming class.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-06T05:27:16Z
- **Completed:** 2026-05-06T05:32:40Z
- **Tasks:** 2
- **Files created:** 6 (2 source modules + 3 test modules + 1 integration package marker)
- **Files modified:** 0

## Accomplishments

- **GoldappleFetcher class** (CrawlerProtocol-conforming async context manager): `__aenter__` boots Camoufox with all six locked SKILL kwargs (`geoip=True`, `locale=["ru-RU","kk-KZ","en-US"]`, `humanize=True`, `persistent_context=True`, `user_data_dir=<tmp>`, configurable `headless`); `__aexit__` always cleans the tmp profile dir via `shutil.rmtree(..., ignore_errors=True)` even when caller raises (Pitfall 7).
- **`_goto_with_retry` tenacity decorator** wraps `page.goto`: `stop_after_attempt(3)` + `wait_exponential_jitter(initial=2, max=30)` + `retry_if_exception_type((TransientFetchError, PWTimeout))` + `reraise=True`. 5xx responses → wrapped as TransientFetchError; `None` response → wrapped; 403/404 → returned (NOT retried — caller's parse domain).
- **`fetch_one_isolated` module-level wrapper** (CRAWL-03): catches arbitrary exceptions from any fetch callable, logs structured `fetch_failed` event, increments `stats["fetch_failures"]`, returns `None` — never propagates.
- **`fetch_one(page, url)`**: returns spike-style dict (`url`, `status`, `html_size`, `title`, `gate_cleared`, `gate_cleared_after_ms?`, `html?`, `block`, `block_reason?`, `error?`, `timing_ms`); polls `page.title()` up to `GATE_POLL_DEADLINE_MS` for gate clearance; classifies state via `block_reason ∈ {gate_shell_not_cleared, http_*, exception}`.
- **`run_loop(urls, stats, sleep_fn=None)`**: sequential drive with `random.uniform(*PAUSE_RANGE)` pacing between URLs (NOT after last); accumulates `fetch_count`, `gate_shell_count`, `fetch_failures` into stats; structured `fetch_progress` log per URL.
- **21 new tests, all green** (Wave 0+1+2+3 = **105/105 passed in 45.65s** with `-m "not live"`).

## Test Counts

| Suite | Tests | Notes |
|-------|-------|-------|
| `tests/unit/test_retry_policy.py` | 7 | tenacity 3-attempt limit, 5xx wrapping, no-response wrapping, 403/404 NOT retried, unknown-exception wrapping, exhaust-then-reraise |
| `tests/unit/test_fetcher_isolation.py` | 4 | exception-swallow, success-passthrough, mixed-3-of-5, structlog event emission |
| `tests/integration/test_goldapple_fetch_loop_mocked.py` | 10 | lifecycle clean on success + on exception, locked Camoufox kwargs assertion, fetch_one happy/gate-shell/404/exception, run_loop pacing-between-not-after-last, run_loop isolation continues after one failure, run_loop accumulates `gate_shell_count` |
| **Total NEW (Wave 3)** | **21** | All green |
| **Wave 0+1+2+3 cumulative** | **105/105** | `uv run pytest tests/ -q -m "not live"` exits 0 (45.65s on Win11/Python 3.12.13) |

## Profile Dir Lifecycle Verified

`test_lifecycle_creates_and_cleans_profile_dir` confirms:
- `Path(tempfile.mkdtemp(prefix="camoufox-run-{run_id}-"))` is created at `__init__` time and remains during the `async with` body.
- After `__aexit__`, the directory is gone (success path).

`test_lifecycle_cleans_profile_dir_on_exception` confirms (Pitfall 7):
- When the body of `async with fetcher:` raises a `RuntimeError`, the profile dir is STILL gone after the context manager unwinds. The `try/finally` in `__aexit__` makes cleanup unconditional.

`test_locked_camoufox_kwargs` inspects the FakeCamoufoxCM kwargs dict and asserts:
- `geoip=True`, `locale=["ru-RU", "kk-KZ", "en-US"]`, `humanize=True`, `persistent_context=True`, `user_data_dir=str(fetcher.profile_dir)`.

## Task Commits

Each task was committed atomically:

1. **Task 1: tenacity retry policy + per-SKU isolation primitives** — `b178a97` (`feat`)
2. **Task 2: GoldappleFetcher async context manager + fetch_one + run_loop** — `e250e27` (`feat`)

**Plan metadata commit (this SUMMARY + STATE + ROADMAP):** added in the closing docs commit below.

## Files Created/Modified

- `src/ga_crawler/fetchers/__init__.py` — package marker (single line docstring)
- `src/ga_crawler/fetchers/goldapple.py` — `GoldappleFetcher`, `TransientFetchError`, `_goto_with_retry`, `fetch_one_isolated`, operational constants. ~210 LOC.
- `tests/unit/test_retry_policy.py` — 7 tenacity policy tests
- `tests/unit/test_fetcher_isolation.py` — 4 per-SKU isolation tests
- `tests/integration/__init__.py` — integration test package marker
- `tests/integration/test_goldapple_fetch_loop_mocked.py` — 10 mocked-Camoufox end-to-end tests via FakeCamoufoxCM context-manager replacement

## Decisions Made

- **Lazy import of `camoufox.async_api` inside `__aenter__`** (not module-top): keeps `from ga_crawler.fetchers.goldapple import ...` importable on machines without Camoufox binaries (CI test runners; partial dev environments). Moves the boot-failure surface to the runtime path that already has try/except + cleanup.
- **Lazy build of tenacity retry decorator via `_make_retry_decorator()` factory**: catches `ImportError` for `playwright.async_api.TimeoutError` and falls back to a private `class PWTimeout(Exception)` so retry-by-type still works. Camoufox bundles Firefox via Playwright internally, but the public Python `playwright` package is not strictly required. Keeps tests on environments where `playwright` is not separately installed.
- **Catch-all exception path in `_goto_with_retry` wraps as `TransientFetchError`**: cleaner than enumerating every transient network error class (`ConnectionError`, `OSError`, `aiohttp.ClientError`, etc.). Spike notebook.py also wraps broadly; mirrors that posture.
- **`fetch_one`'s outer try/except sets `block=True` + `block_reason="exception"` instead of re-raising**: pushes the "always-return-a-record" invariant down to fetch_one. `fetch_one_isolated` is then ONLY responsible for stats counter + log, not for re-classification. Simplifies orchestrator (Wave 5): every URL produces exactly one record OR exactly one fetch_failures increment, never both.
- **Instance-method `fetch_one_isolated` delegates to module-level free function**: preserves both call shapes — orchestrator with a fetcher instance uses `await fetcher.fetch_one_isolated(url, stats)`; tests with a mock callable use `await fetch_one_isolated(callable, page, url, stats)`.

## Deviations from Plan

**None — plan executed exactly as written.**

The plan's `<action>` blocks were copy-paste-ready (Task 1 and Task 2 each shipped exactly the code blocks in the plan). No Rule 1/2/3/4 deviations triggered. All acceptance criteria passed first-shot:

- Test counts match (≥7 retry, ≥3 isolation, ≥9 integration — actual 7/4/10).
- Constants pin verbatim (`PAUSE_RANGE = (3.0, 5.0)`, `RETRY_MAX_ATTEMPTS = 3`, `RETRY_WAIT_INITIAL = 2.0`, `RETRY_WAIT_MAX = 30.0`).
- All locked Camoufox kwargs present and asserted by `test_locked_camoufox_kwargs`.
- `gate_shell_not_cleared`, `5xx: {response.status}`, `no response (page.goto returned None)` literals all match plan's grep-anchors verbatim.
- `_goto_with_retry` retries on `(TransientFetchError, PWTimeout)` per `retry_if_exception_type((TransientFetchError, PWTimeout))` exact spelling.
- `run_loop` uses `random.uniform(*PAUSE_RANGE)`.
- `__aexit__` calls `shutil.rmtree(self.profile_dir, ignore_errors=True)`.

## Threat Surface Coverage

All STRIDE entries from `<threat_model>` map to test coverage:

| Threat ID | Mitigation Path | Verified By |
|-----------|-----------------|-------------|
| T-03-04-07 | Fresh tmp profile per run + always-cleanup | `test_lifecycle_creates_and_cleans_profile_dir` + `test_lifecycle_cleans_profile_dir_on_exception` |
| T-03-04-07b | tempfile.mkdtemp 0700 perms (OS-default) + Pitfall-7 always-cleanup | Same lifecycle tests; OS perms inherited from tempfile defaults |
| T-03-04-09 | try/finally in `__aexit__` always runs | `test_lifecycle_cleans_profile_dir_on_exception` |
| T-03-04-09b | `random.uniform(3, 5)` between fetches; tenacity exp+jitter | `test_run_loop_sequential_pacing` (assert `PAUSE_RANGE[0] ≤ t < PAUSE_RANGE[1]`); `test_retry_succeeds_on_third_attempt` (3 attempts) |
| T-03-04-11 | `fetch_one_isolated` swallow + counter | `test_isolation_swallows_exception`, `test_isolation_runs_continue_after_failure`, `test_run_loop_isolation_keeps_running` |
| T-03-04-13 | structlog logs only str(exception) + URL, not raw response/headers | Code review of `log.error("fetch_failed", url=..., error=str(e), error_type=type(e).__name__)` — no `response`, no `headers`, no `body` keys |
| T-03-04-08 | Wave 0 D-313 exact pin (`camoufox[geoip]==0.4.11`) in pyproject.toml | Out of scope here; verified in plan 03-01 |

No new threat surface introduced beyond the threat model.

## Issues Encountered

**None.** Both tasks committed first-shot. Zero retries, zero auto-fixes, zero blockers. The plan's verbatim-block-pasting strategy succeeded — RESEARCH §Pattern 3+5 + spike notebook.py are demonstrably production-ready code, not pseudocode.

## Self-Check: PASSED

All files verified present:
- `src/ga_crawler/fetchers/__init__.py` ✓
- `src/ga_crawler/fetchers/goldapple.py` ✓
- `tests/unit/test_retry_policy.py` ✓
- `tests/unit/test_fetcher_isolation.py` ✓
- `tests/integration/__init__.py` ✓
- `tests/integration/test_goldapple_fetch_loop_mocked.py` ✓
- `.planning/phases/03-goldapple-crawl/03-04-SUMMARY.md` ✓

All commits verified in git log:
- `b178a97` feat(03-04): tenacity retry policy + per-SKU isolation primitives (CRAWL-03/04) ✓
- `e250e27` feat(03-04): GoldappleFetcher async context manager + fetch_one + run_loop ✓

`uv run pytest tests/ -q -m "not live"` → **105 passed in 45.65s**.

## Next Phase Readiness

**Wave 3 ships GoldappleFetcher exactly as Wave 4 (smoke probe) and Wave 5 (orchestrator) need it.** Specifically:

- **Wave 4 (smoke probe — `runner/gates.py`)** can call `async with GoldappleFetcher(run_id=...) as fetcher: rec = await fetcher.fetch_one(fetcher._page, smoke_url)` and consume `rec["html"]` for `parse_pdp` round-trip.
- **Wave 5 (orchestrator)** can call `await fetcher.run_loop(matched_urls, stats)` and rely on `stats["fetch_count"]`, `stats["gate_shell_count"]`, `stats["fetch_failures"]` for `runs.stats` JSON merge per Pitfall 6.
- **Wave 6 (manual live smoke)** is a 1-URL `fetch_one` invocation against goldapple.kz from the dev machine; the lazy `camoufox.async_api` import is the only path that touches the binary.

**No blockers.** All Wave 0/1/2 contracts (constants, fixtures, parser, sitemap) are referenced and respected. Phase 2 contracts (`interfaces.py`) are NOT required by Wave 3 — fetcher does not write to storage or read alias-YAML.

---

*Phase: 03-goldapple-crawl*
*Completed: 2026-05-06*
