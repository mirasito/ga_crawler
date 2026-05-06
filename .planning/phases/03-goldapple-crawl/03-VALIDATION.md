---
phase: 3
slug: goldapple-crawl
status: verified
nyquist_compliant: true
wave_0_complete: true
test_files_total: 18
tests_passing: 192
tests_skipped_live: 0
created: 2026-05-06
verified: 2026-05-07
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Detailed invariants and fixtures live in `03-RESEARCH.md` § Validation Architecture.
> Re-audited 2026-05-07 after all 8 plans shipped (Waves 0..7).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 + pytest-asyncio 1.3.0 + pytest-mock 3.15.1 + respx 0.23.1 (per 03-01-SUMMARY) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (`asyncio_mode = "auto"`, markers `live`, `integration`) |
| **Quick run command** | `uv run pytest -q -m "not live"` |
| **Full suite command** | `uv run pytest --cov=ga_crawler --cov-report=term-missing` |
| **Measured runtime** | ~46 s quick (192 tests, no live network) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q -m "not live"` (skips Camoufox/network tests)
- **After every plan wave:** Run `uv run pytest --cov=ga_crawler` (full unit + integration with mocks)
- **Before `/gsd-verify-work`:** Full suite green + 1-hour live smoke (manual) per Success Criterion 4
- **Max feedback latency:** 46 seconds (quick run, measured 2026-05-07)

---

## Per-Task Verification Map

> Filled by gsd-planner during PLAN.md generation; verified post-execution (2026-05-07). Planner test-file names normalized to actual shipped paths.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Test File | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-----------|--------|
| 03-01-1..3 | 01 | 0 | infra | T-03-01-* | pytest + camoufox + tenacity + sqlmodel + pydantic installed; Phase 2 Protocols frozen; 11 conftest fixtures | infra | `uv run pytest --collect-only` | `pyproject.toml [tool.pytest.ini_options]` + `tests/conftest.py` | ✅ green |
| 03-02-1 | 02 | 1 | CRAWL-02 (slug-fy) | T-03-02-04 | Bilingual slug-fy idempotent; Cyrillic→Latin transliterate; KZ glyph alternation explicit | unit | `uv run pytest tests/unit/test_slug_fy.py -q` | `tests/unit/test_slug_fy.py` | ✅ green |
| 03-02-1 | 02 | 1 | NORM-06 (intersection) | T-03-02-04 | EXACT-match sitemap intersection via `dict.get`; zero false-positives on `tom-ford` ↔ `tom-ford-beauty` | unit | `uv run pytest tests/unit/test_intersect_brand_pool.py tests/unit/test_brand_token_index.py -q` | `tests/unit/test_intersect_brand_pool.py` (9 tests) + `tests/unit/test_brand_token_index.py` (7 tests, Wave 7 D-305 structural invariant) | ✅ green |
| 03-02-2 | 02 | 1 | CRAWL-02 (sitemap fetch) | T-03-02-04, T-03-02-05, T-03-02-09 | `PRODUCT_URL_RE` whitelist; tenacity retries on 5xx; path-traversal blocked by `int(run_id)` parse | unit | `uv run pytest tests/unit/test_sitemap_parser.py -q` | `tests/unit/test_sitemap_parser.py` | ✅ green |
| 03-02-2 | 02 | 1 | D-307 NORM-06 reverse | — | Week-over-week NEW goldapple-slug diff non-empty after second run only; pathlib safe | unit | `uv run pytest tests/unit/test_norm06_diff.py -q` | `tests/unit/test_norm06_diff.py` | ✅ green |
| 03-03-1..2 | 03 | 2 | PARSE-01..06 | T-03-03-09, T-03-03-02, T-03-03-02b | Microdata extractor returns current price; ignores StrikethroughPrice/ListPrice/GoldCard; 3-axis state classifier; sanity range 100..1_000_000 ₸ | unit | `uv run pytest tests/unit/test_goldapple_microdata_parser.py -q` | `tests/unit/test_goldapple_microdata_parser.py` (30 tests) | ✅ green |
| 03-03-1 | 03 | 2 | gate detection (3-axis) | T-03-03-02 | gate-shell vs stale-sku vs real-pdp; bounded by GATE_SHELL_MAX_BYTES=30000 + GATE_TITLE_MARKER='checking' | unit | `uv run pytest tests/unit/test_gate_detection.py tests/unit/test_stale_sku_detection.py -q` | `tests/unit/test_gate_detection.py` (11 tests) + `tests/unit/test_stale_sku_detection.py` (4 tests) | ✅ green |
| 03-04-1 | 04 | 3 | CRAWL-03 isolation | T-03-04-11 | One bad URL doesn't abort run; `fetch_one_isolated` swallows + counters | unit | `uv run pytest tests/unit/test_fetcher_isolation.py -q` | `tests/unit/test_fetcher_isolation.py` | ✅ green |
| 03-04-1 | 04 | 3 | CRAWL-04 retry | T-03-04-09b | tenacity `stop_after_attempt(3)` + `wait_exponential_jitter(2, 30)` + retry_if_exception_type | unit | `uv run pytest tests/unit/test_retry_policy.py -q` | `tests/unit/test_retry_policy.py` | ✅ green |
| 03-04-1 | 04 | 3 | CRAWL-02 fetcher loop | T-03-04-09b | `random.uniform(3, 5)` between fetches; concurrency=1; profile lifecycle cleanup | integration | `uv run pytest tests/integration/test_goldapple_fetch_loop_mocked.py -q` | `tests/integration/test_goldapple_fetch_loop_mocked.py` | ✅ green |
| 03-05-1 | 05 | 4 | D-312 smoke-probe | T-03-05-01 | All probe URLs must pass; first failure → run aborts before crawl; `smoke_urls=` override | unit | `uv run pytest tests/unit/test_smoke_probe.py -q` | `tests/unit/test_smoke_probe.py` | ✅ green |
| 03-05-1 | 05 | 4 | CRAWL-05 sanity-gate / D-308/309/310 | — | Final gate: `goldapple_count < M` → `runs.status='failed'`; auto-suggest after ≥4 weeks; formula `int(0.7 × median(last 4))` | unit | `uv run pytest tests/unit/test_final_gate.py -q` | `tests/unit/test_final_gate.py` | ✅ green |
| 03-05-1 | 05 | 4 | NORM-06 forward | — | Viled brands with zero matches go to review queue; counter incremented | unit | `uv run pytest tests/unit/test_norm06_forward.py -q` | `tests/unit/test_norm06_forward.py` | ✅ green |
| 03-05-1 | 05 | 4 | stats namespace | T-03-05-06 | Only `goldapple.*` keys allowed; `StatsNamespaceError` on unknown bare key; atomic merge via `patch_stats` | unit | `uv run pytest tests/unit/test_stats_namespace.py -q` | `tests/unit/test_stats_namespace.py` | ✅ green |
| 03-06-1..2 | 06 | 5 | DATA-03/04 + CRAWL-02 E2E | T-03-06-09, T-03-06-09b | Snapshots INSERT-only; `runs` row patched atomically (single `patch_stats`); full mock pipeline sitemap → intersect → fetch (mocked Camoufox) → parse → store → gate | integration | `uv run pytest tests/integration/test_storage_integration.py tests/integration/test_run_e2e_with_phase2_mocks.py tests/integration/test_norm06_diff_integration.py -q` | `tests/integration/test_storage_integration.py` + `tests/integration/test_run_e2e_with_phase2_mocks.py` (7 tests incl. realistic-sitemap + final-gate-fail-run-to-completion) + `tests/integration/test_norm06_diff_integration.py` (4 tests) | ✅ green |
| 03-07-1 | 07 | 6 | Success Criterion 4 | T-03-07-02 | 1-hour live run: <5% gate-shell, no sustained 429/503; per-page cookie reuse | manual+live | `uv run python -m ga_crawler goldapple-run --run-id N --viled-brands ... --sanity-gate-m 10` | `live-smoke-checklist.md` | ⚠️ manual — UAT-blocked (deferred to first production weekly run per VERIFICATION.md `deferred[]`) |
| 03-08-1 | 08 | 7 | NORM-06 brand-intersect bucket fix | — | longest-prefix-in-whitelist bucket; D-305 structural invariant; tom-ford ↔ tom-ford-beauty disambiguation | unit + integration | `uv run pytest tests/unit/test_brand_token_index.py tests/integration/test_run_e2e_with_phase2_mocks.py::test_e2e_brand_intersect_against_realistic_sitemap_shape -q` | `tests/unit/test_brand_token_index.py` (7 tests) + new full-pipeline regression in `test_intersect_brand_pool.py` (3 added) + new E2E in `test_run_e2e_with_phase2_mocks.py` (1 added) | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky / manual*

### Coverage Summary

| Metric | Count |
|--------|-------|
| **Plans** | 8 (Waves 0–7) |
| **Test files (unit)** | 14 |
| **Test files (integration)** | 4 |
| **Total tests** | 192 (no-live) |
| **Tests green** | 192 (100%) |
| **Tests deferred (manual/live)** | 1 (1-hour live run; SC#4 — UAT-blocked, Phase 7 first-cron item) |
| **Requirements MISSING auto coverage** | 0 |
| **Requirements PARTIAL coverage** | 0 |
| **Requirements COVERED auto** | 16/17 (94% — manual is the 17th) |

---

## Wave 0 Requirements

All Wave 0 deliverables shipped per `03-01-SUMMARY.md` (commits `36d8f56`, `c2716c5`, `6ac04c0`, 2026-05-06):

- [x] `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, markers `live`, `integration`
- [x] `tests/conftest.py` — 11 shared fixtures (HTML/JSON loaders + Phase 2 mocks + tmp Camoufox profile dir)
- [x] `tests/unit/test_slug_fy.py` — Cyrillic + ASCII transliterate + 11 enumerated cases
- [x] `tests/unit/test_intersect_brand_pool.py` — 9 tests (Wave 7 refactor: brand_bucket shape)
- [x] `tests/unit/test_brand_token_index.py` — 7 tests (Wave 7 D-305 structural invariant)
- [x] `tests/unit/test_sitemap_parser.py` — `PRODUCT_URL_RE` whitelist + path traversal
- [x] `tests/unit/test_norm06_diff.py` — D-307 NORM-06 reverse direction
- [x] `tests/unit/test_goldapple_microdata_parser.py` — 30 tests (priceType + sanity + JSON-LD anti-fixture)
- [x] `tests/unit/test_gate_detection.py` — 11 tests (3-axis classifier)
- [x] `tests/unit/test_stale_sku_detection.py` — 4 tests (anchored to spike row 0)
- [x] `tests/unit/test_fetcher_isolation.py` — CRAWL-03 swallow + counter
- [x] `tests/unit/test_retry_policy.py` — CRAWL-04 tenacity decorator
- [x] `tests/unit/test_smoke_probe.py` — D-312 5-fail-modes
- [x] `tests/unit/test_final_gate.py` — D-308/309/310 boundary + auto-suggest
- [x] `tests/unit/test_norm06_forward.py` — NORM-06 forward direction
- [x] `tests/unit/test_stats_namespace.py` — T-03-05-06 namespace enforcement
- [x] `tests/integration/test_goldapple_fetch_loop_mocked.py` — Camoufox-mocked fetch loop
- [x] `tests/integration/test_storage_integration.py` — DATA-03/04 storage
- [x] `tests/integration/test_run_e2e_with_phase2_mocks.py` — 7 E2E tests
- [x] `tests/integration/test_norm06_diff_integration.py` — 4 integration tests
- [x] `src/ga_crawler/interfaces.py` — 6 Phase 2 contract Protocols
- [x] `uv add` pins (locked): `camoufox[geoip]==0.4.11`, `tenacity 9.1.4`, `sqlmodel 0.0.38`, `pydantic 2.13.3`, `pytest 8.4.2`, `pytest-asyncio 1.3.0`, `pytest-mock 3.15.1`, `respx 0.23.1`, plus existing `selectolax`, `curl_cffi`, `structlog`
- [x] Camoufox Firefox 135.0.1-beta.24 cached on dev box (verified via `pkgman.installed_verstr()`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Status |
|----------|-------------|------------|-------------------|--------|
| 1-hour live goldapple run | Success Criterion 4 | Live network + Camoufox; cannot mock without invalidating signal | `uv run python -m ga_crawler goldapple-run --run-id N --viled-brands ... --sanity-gate-m 10`; assert `runs.status='success'`, `gate_shell_count/total < 5%`, no sustained 429/503 in structlog | ⚠️ deferred to first production weekly run (Phase 7 ops-playbook initial deploy) — see `03-VERIFICATION.md` `deferred[]` block |
| First-week NORM-06 review queue triage | Success Criterion 5 | Subjective brand-coverage decision by operator | After first run: open NORM-06 review queue, confirm format usable, classify ≥10 entries (alias-add vs not-on-goldapple) | ⚠️ pending first weekly run (run-43 produced `unmatched_viled_brands: 1` for `jo_malone_london` — already actionable; mechanism trustworthy after Wave 7) |
| Smoke-probe URL pool curation | D-312 (Phase 7 ops-playbook seed) | Operator judgement on URL freshness | Quarterly: hand-rotate 1 of 3 smoke URLs; rerun smoke probe; verify pass | 🗓️ quarterly cadence — first rotation after Phase 7 deploys cron |
| Camoufox upstream upgrade workflow | D-313 | Manual sign-off before `uv.lock` PR | On new Camoufox release: dev box → `uv add camoufox=={new}` → run live smoke → if pass, PR `uv.lock` change | 📘 documented; first exercise on next Camoufox release |

---

## Validation Audit 2026-05-07

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Manual-only items | 1 automated-blocked (SC#4 1-hour live), 3 procedural |
| Test infrastructure | pytest 8.4.2 + 4 dev libs; pyproject.toml asyncio_mode=auto |
| Total tests passing | 192/192 (no-live) |
| Coverage delta vs draft | All 14 planner-named test stubs shipped (renamed for clarity); 4 additional tests added beyond draft (`test_brand_token_index.py`, `test_sitemap_parser.py`, `test_stats_namespace.py`, `test_goldapple_fetch_loop_mocked.py`, `test_norm06_diff_integration.py`) |

**State A audit:** No new test generation required. All planner rows resolved to shipped files (with normalized naming). Manual-only items unchanged from draft. `nyquist_compliant: true` set in frontmatter.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (planner-enforced; verified post-exec)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none MISSING)
- [x] No watch-mode flags (pytest only, no `-f`/watcher)
- [x] Feedback latency < 60 s (quick run measured 46.59 s)
- [x] `nyquist_compliant: true` set in frontmatter
- [x] Test files under git, status `green` per `pytest -q -m "not live"` 2026-05-07

**Approval:** verified 2026-05-07
