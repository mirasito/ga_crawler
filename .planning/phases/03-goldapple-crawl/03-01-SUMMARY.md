---
phase: 03-goldapple-crawl
plan: 01
subsystem: scaffolding
tags: [bootstrap, deps, test-infra, contracts]
requires: []
provides:
  - "src/ga_crawler/ package importable as ga_crawler"
  - "Phase 2 contract Protocols frozen in interfaces.py"
  - "pytest infrastructure (asyncio_mode=auto, markers, fixtures)"
  - "Camoufox 0.4.11 / Firefox 135.0.1-beta.24 exact-pin per D-313"
  - "[tool.ga_crawler.crawl.goldapple] config namespace with 15 operational constants"
  - "6 test fixtures from spike sample-payloads + 1 synthesized (stale-SKU)"
affects:
  - "All Wave 1+ Phase 3 plans depend on this bootstrap"
  - "Phase 2 plan reviewer must cross-check interfaces.py contracts at Phase 2 implementation time"
tech-stack:
  added:
    - "tenacity 9.1.4 (CRAWL-04 retry decorator)"
    - "sqlmodel 0.0.38 (SQLAlchemy 2 + Pydantic 2; Phase 2 consumer)"
    - "pydantic 2.13.3"
    - "pytest 8.4.2 + pytest-asyncio 1.3.0 + pytest-mock 3.15.1 + respx 0.23.1 (dev)"
    - "hatchling build-backend (Rule 3 deviation: required to make src/-layout importable)"
  patterns:
    - "Phase 2 contract Protocols (freeze-at-Wave-0 mitigates Pitfall 9 contract drift)"
    - "Synthesize-vs-re-fetch fixture fallback (PATTERNS.md fixture-gap pattern)"
    - "Toml config namespace [tool.ga_crawler.crawl.goldapple] (CONTEXT 'Claude's Discretion')"
key-files:
  created:
    - "pyproject.toml — extended with [tool.pytest.ini_options], [tool.ga_crawler.crawl.goldapple], [build-system] hatchling"
    - "src/ga_crawler/__init__.py"
    - "src/ga_crawler/interfaces.py"
    - "tests/__init__.py"
    - "tests/conftest.py"
    - "tests/fixtures/goldapple/_debug-product-page.html (393 KB Givenchy PDP)"
    - "tests/fixtures/goldapple/gate-shell.html (19 KB GroupIB challenge sample)"
    - "tests/fixtures/goldapple/sitemap-1-excerpt.xml"
    - "tests/fixtures/goldapple/tier2-camoufox-kz-results.json"
    - "tests/fixtures/goldapple/_debug-jsonld-blocks.json"
    - "tests/fixtures/goldapple/stale-sku-9.5kb.html (synthesized 9189 B)"
    - "scripts/03-01-synthesize-stale-sku.py (re-runnable synthesizer)"
  modified:
    - "pyproject.toml (deps + config namespaces + build-system)"
    - "uv.lock (regenerated)"
decisions:
  - "Camoufox Python 0.4.11 == upstream Firefox 135.0.1-beta.24 — verified via camoufox.pkgman.installed_verstr() before pinning"
  - "Use camoufox[geoip]==0.4.11 (no PyPI local-version suffix) — semantic equivalent of plan's '0.4.11+camoufox.135.0.1-beta.24', PEP 440 valid"
  - "Add [build-system] hatchling — required for src/-layout package import (Rule 3 deviation, blocking)"
  - "Skip 'uv run camoufox fetch' — Firefox binary already cached from Phase 1 spike (installed_verstr() reports 135.0.1-beta.24)"
metrics:
  duration: "~9 minutes"
  completed: "2026-05-06T04:59:34Z"
  tasks: 3
  commits: 3
  files_created: 13
  files_modified: 2
---

# Phase 03 Plan 01: Wave 0 Bootstrap Summary

Established Phase 3 scaffolding: pinned dependencies (Camoufox 0.4.11 with bundled Firefox 135.0.1-beta.24, tenacity, sqlmodel, pydantic, pytest stack), froze Phase 2 contract Protocols in `src/ga_crawler/interfaces.py`, copied 5 spike fixtures + synthesized 1 stale-SKU fixture, and wrote `tests/conftest.py` with 11 shared fixtures (HTML loaders, Phase 2 mocks, tmp Camoufox profile dir factory).

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Pin deps + pytest config + ga_crawler config namespace | `36d8f56` | pyproject.toml, uv.lock |
| 2 | Phase 2 contract Protocols (interfaces.py) | `c2716c5` | src/ga_crawler/__init__.py, src/ga_crawler/interfaces.py, pyproject.toml (build-system), uv.lock |
| 3 | Test fixtures + conftest.py shared fixtures | `6ac04c0` | tests/__init__.py, tests/conftest.py, 6 fixtures, scripts/03-01-synthesize-stale-sku.py |

## Final Camoufox Version Pin

Verbatim from `pyproject.toml` line 12:

```toml
"camoufox[geoip]==0.4.11",
```

**Why this exact string** (and NOT `0.4.11+camoufox.135.0.1-beta.24` from the plan):

The plan suggested PyPI version string `0.4.11+camoufox.135.0.1-beta.24` which is a PEP 440 *local-version* identifier. PyPI does not publish wheels with local-version suffixes — `pip install camoufox==0.4.11+camoufox.135.0.1-beta.24` would fail.

Verified empirically before pinning:

```python
>>> from camoufox import pkgman
>>> pkgman.installed_verstr()
'135.0.1-beta.24'
```

Camoufox Python 0.4.11 (PyPI) bundles upstream Firefox 135.0.1-beta.24 — the exact fingerprint validated by spike 01-08 at 99/100 success. Pin `camoufox[geoip]==0.4.11` is **semantically equivalent** to the plan's intent and PEP 440-valid.

A header comment on the pin in pyproject.toml documents this for reviewers, the smoke-probe contract `camoufox_version_expected = "135.0.1.beta24"` (config), and the manual upgrade workflow per D-313.

## Phase 3 Config Keys Added to `[tool.ga_crawler.crawl.goldapple]`

15 operational constants + 3 smoke URLs:

| Key | Value | Source |
|-----|-------|--------|
| `sanity_gate_m` | `1000` | D-308 |
| `pause_range_min_seconds` | `3.0` | D-04, SKILL |
| `pause_range_max_seconds` | `5.0` | D-04, SKILL |
| `concurrency` | `1` | D-04, SKILL |
| `page_timeout_ms` | `60000` | spike notebook L43 |
| `gate_poll_deadline_ms` | `25000` | spike notebook L44 |
| `gate_poll_step_ms` | `500` | spike notebook L45 |
| `gate_shell_max_bytes` | `30000` | spike notebook L49 |
| `gate_title_marker` | `"checking"` | spike notebook L48 |
| `camoufox_locales` | `["ru-RU", "kk-KZ", "en-US"]` | SKILL |
| `camoufox_geoip` | `true` | SKILL |
| `camoufox_humanize` | `true` | SKILL |
| `camoufox_persistent_context` | `true` | SKILL, D-04 |
| `m_auto_suggest_factor` | `0.7` | D-310 |
| `m_auto_suggest_after_runs` | `4` | D-310 |
| `camoufox_version_expected` | `"135.0.1.beta24"` | D-313 |
| `smoke_urls.url_1..3` | 3 Givenchy URLs | D-312, RESEARCH L908-913 |

Plus `[tool.pytest.ini_options]` block (`asyncio_mode = "auto"`, `testpaths = ["tests"]`, `live` + `integration` markers).

## Test Fixtures

| Fixture | Size | Source | Content properties verified |
|---------|------|--------|-----------------------------|
| `_debug-product-page.html` | 392 967 B | spike verbatim | > 100 KB ✓ (real Givenchy PDP) |
| `gate-shell.html` | 19 058 B | spike verbatim (renamed from `goldapple-product-html-1.html`) | 8-25 KB ✓; contains "checking" ✓ |
| `sitemap-1-excerpt.xml` | 12 144 B | spike verbatim | — |
| `tier2-camoufox-kz-results.json` | 72 397 B | spike verbatim | — |
| `_debug-jsonld-blocks.json` | 667 B | spike verbatim | — |
| `stale-sku-9.5kb.html` | 9 189 B | **synthesized** | 5-13 KB ✓; contains "Loading" ✓; no `itemprop="price"` ✓ |

`stale-sku-9.5kb.html` synthesizer (`scripts/03-01-synthesize-stale-sku.py`) produces a deterministic HTML body that mimics spike result row 0 (200 OK + small HTML + no microdata). Re-runnable; new check sums on every regeneration would be deterministic.

## conftest.py Fixtures (11)

**HTML/JSON loaders (session-scope, 6):**
`goldapple_pdp_html`, `gate_shell_html`, `stale_sku_html`, `sitemap_xml`, `tier2_results_json`, `jsonld_blocks_anti_fixture`

**Phase 2 contract mocks (function-scope, 4):**
`mock_brand_alias`, `mock_normalizer`, `mock_snapshot_writer`, `mock_run_writer` — all with default side-effects that satisfy Protocol signatures and accumulate call records for test assertions.

**Camoufox tmp profile dir (function-scope, 1):**
`tmp_camoufox_profile_dir` — yields `tmp_path / "camoufox-profile"` (auto-cleanup by pytest); mirrors D-311 fresh-per-run pattern for fetcher tests in Wave 3.

## `uv sync` Outcome

```
Resolved 68 packages in 36ms
   Building ga-crawler @ file:///C:/Users/gstorepc/projects/ga_crawler
      Built ga-crawler @ file:///C:/Users/gstorepc/projects/ga_crawler
Prepared 1 package in 907ms
Installed 1 package in 1ms
 + ga-crawler==0.1.0 (from file:///C:/Users/gstorepc/projects/ga_crawler)
```

No version-resolution warnings. All transitive deps pinned in `uv.lock`. Build-backend `hatchling` packs `src/ga_crawler/` as the wheel target.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Added `[build-system]` block (hatchling) for src/-layout package import**

- **Found during:** Task 2 verification (`uv run python -c "from ga_crawler.interfaces import ..."` failed with `ModuleNotFoundError: No module named 'ga_crawler'`).
- **Issue:** Plan placed `interfaces.py` under `src/ga_crawler/` but pyproject.toml had no `[build-system]` declaration, so `uv sync` produced no installed wheel for the project package itself. Wave 1+ tasks would all fail at import time.
- **Fix:** Appended hatchling build-system to pyproject.toml:
  ```toml
  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [tool.hatch.build.targets.wheel]
  packages = ["src/ga_crawler"]
  ```
- **Files modified:** `pyproject.toml`
- **Commit:** `c2716c5` (folded into Task 2 commit)

**2. [Rule 1 — Bug-equivalent] Camoufox PEP 440 version string**

- **Found during:** Task 1.1 — plan suggested pin `camoufox[geoip]==0.4.11+camoufox.135.0.1-beta.24` which is a PEP 440 local-version identifier not published on PyPI.
- **Investigation:** Plan §1.5 explicitly anticipated this fallback: "If `135.0.1.beta24` not on PyPI, switch to coryking fork…". I verified BEFORE switching that the bundled Firefox version is already `135.0.1-beta.24` via `camoufox.pkgman.installed_verstr()`. Therefore the existing pin `camoufox[geoip]==0.4.11` is the semantic equivalent — the Firefox binary version is what matters for fingerprint stability, and the Python wrapper version pin uniquely determines that binary version.
- **Fix:** Kept `camoufox[geoip]==0.4.11` (already satisfied D-313 intent); added pre-pin comment in pyproject.toml documenting the relationship + manual upgrade workflow + coryking-fork backup.
- **Files modified:** `pyproject.toml`
- **Commit:** `36d8f56` (Task 1)

**3. [Rule 3 — Skip] `uv run camoufox fetch` skipped**

- **Found during:** Task 1.7 — plan said "Download Firefox binary (one-time, dev box)".
- **Investigation:** `camoufox.pkgman.installed_verstr()` returned `135.0.1-beta.24` BEFORE running fetch. Phase 1 spike already cached the binary in `~/.cache/camoufox/`.
- **Fix:** Skipped redundant download. Phase 7 ops-playbook will add `camoufox fetch` to deploy steps for fresh VPS.
- **Commit:** N/A (no file change)

### Out-of-scope / not auto-fixed

None — pre-existing untracked files (`.claude/scheduled_tasks.lock`, `.obsidian/`) and pre-existing modified files (`.planning/STATE.md`, `CLAUDE.md`) were left untouched per scope-boundary rule.

## Authentication Gates

None encountered.

## Verification Results

| Acceptance criterion | Status |
|---------------------|--------|
| `pyproject.toml` contains `camoufox[geoip]==0.4.11` | ✓ |
| `pyproject.toml` contains `tenacity`, `sqlmodel`, `pydantic` | ✓ |
| `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` | ✓ |
| `[tool.ga_crawler.crawl.goldapple]` with `sanity_gate_m = 1000` | ✓ |
| `pause_range_min_seconds` AND `pause_range_max_seconds` (count=2) | ✓ |
| `camoufox_locales = ["ru-RU", "kk-KZ", "en-US"]` | ✓ |
| 3 `smoke_urls` (url_1, url_2, url_3) | ✓ |
| `uv.lock` references camoufox 0.4.11 | ✓ |
| `uv run python -c "import camoufox, tenacity, sqlmodel, pydantic"` exits 0 | ✓ |
| `uv run pytest --collect-only` exits cleanly (no tests collected — expected at Wave 0) | ✓ |
| `src/ga_crawler/__init__.py` with `__version__ = "0.1.0"` | ✓ |
| 6 Protocol classes in `interfaces.py` | ✓ |
| 5 of 6 Protocols decorated `@runtime_checkable` (CrawlerProtocol intentionally excluded) | ✓ |
| All 6 Protocols importable | ✓ |
| 6 fixture files at correct sizes | ✓ |
| `stale-sku-9.5kb.html` contains "Loading"; no `itemprop="price"` | ✓ |
| `gate-shell.html` contains "checking" | ✓ |
| `tests/conftest.py` defines 11 fixtures | ✓ |

All Wave 0 success criteria satisfied.

## Self-Check: PASSED

**Files exist:**
- `pyproject.toml` ✓
- `src/ga_crawler/__init__.py` ✓
- `src/ga_crawler/interfaces.py` ✓
- `tests/__init__.py` ✓
- `tests/conftest.py` ✓
- `tests/fixtures/goldapple/_debug-product-page.html` ✓
- `tests/fixtures/goldapple/gate-shell.html` ✓
- `tests/fixtures/goldapple/sitemap-1-excerpt.xml` ✓
- `tests/fixtures/goldapple/tier2-camoufox-kz-results.json` ✓
- `tests/fixtures/goldapple/_debug-jsonld-blocks.json` ✓
- `tests/fixtures/goldapple/stale-sku-9.5kb.html` ✓
- `scripts/03-01-synthesize-stale-sku.py` ✓

**Commits exist:**
- `36d8f56` ✓ (Task 1)
- `c2716c5` ✓ (Task 2)
- `6ac04c0` ✓ (Task 3)
