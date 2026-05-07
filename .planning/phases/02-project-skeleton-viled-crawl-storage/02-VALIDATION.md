---
phase: 02
slug: project-skeleton-viled-crawl-storage
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-07
updated: 2026-05-07
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> See `02-RESEARCH.md` `## Validation Architecture` for the full strategy; this file is the planner-consumed sign-off contract.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (curl_cffi mocks via direct monkey-patch — NOT respx) |
| **Mock strategy** | Monkey-patch wrapper functions like `_fetch_html`, `_fetch_xml`, `fetch_catalog_urls` directly. Per RESEARCH §Pitfall 1 + Phase 3 D-302 lesson: respx is incompatible with curl_cffi for our patterns. respx may remain installed transitively from Phase 3, but Plan 04 includes `test_no_respx_used` to assert no test imports respx. |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) — Wave 0 task installs if missing |
| **Quick run command** | `uv run pytest tests/unit -x -q` |
| **Full suite command** | `uv run pytest -m "not live" -q` |
| **Estimated runtime** | ~30s quick (unit only), ~90s full (unit + integration) |

---

## Sampling Rate

- **After every task commit:** Run quick suite (unit only)
- **After every plan wave:** Run full suite (unit + integration)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (quick), 90 seconds (full)

---

## Per-Task Verification Map

> One row per task across all 6 plans (14 tasks total).
> `Automated Command` is the actual `<automated>` command from each task's `<verify>` block (truncated for table readability — see PLAN.md for full).

| Task ID | Plan | Wave | Requirement | Threat Ref | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 01 | 0 | enables: A1/A2/A3/A4/A10 probes | T-02-04, T-02-A10, T-02-W0 | live-probe + grep | `test -f tests/fixtures/viled/viled-pdp-407682.html && test -f tests/fixtures/viled/viled-catalog-men-1310-page1.html && grep -q "A1" 02-WAVE0-PROBE.md && from curl_cffi.requests.errors import RequestsError` | ❌ W0 | ⬜ pending |
| 02-01-T2 | 01 | 0 | enables: D-202, D-227 config | — | grep + tomllib | `grep -q "\[tool.ga_crawler.crawl.viled\]" pyproject.toml && grep -q "sanity_gate_n = 100" pyproject.toml && uv run python -c "import yaml" && tomllib.load asserts sanity_gate_n==100, len(catalog_urls)==2` | ❌ W0 | ⬜ pending |
| 02-01-T3 | 01 | 0 | enables: 24 RED test scaffolds | — | corpus + collect | `uv run python -c "yaml.safe_load(...volume-corpus.yaml)['cases'] >= 15" && brand-corpus >= 10 && pytest --co lists ≥24 new tests && pytest -m "not live" exits 0 (existing 192 pass + ≥24 skip)` | ❌ W0 | ⬜ pending |
| 02-02-T1 | 02 | 1 | DATA-01, DATA-02, DATA-03, DATA-04 | T-02-DATA01, T-02-DATA04 | unit + integration | `uv run pytest tests/unit/test_storage_models.py tests/unit/test_snapshot_writer.py tests/integration/test_storage_wal.py tests/integration/test_v_current_snapshots.py -x -q && grep -q "WAL" sqlite.py` | ❌ W0 | ⬜ pending |
| 02-02-T2 | 02 | 1 | DATA-05, NORM-06 | T-02-06 (Pitfall 6), T-02-NORM06 | unit + integration | `uv run pytest tests/unit/test_run_writer.py tests/unit/test_norm06_writer.py tests/integration/test_run_writer_lifecycle.py -x -q && grep -q "json_patch(stats" sqlite.py` | ❌ W0 | ⬜ pending |
| 02-03-T1 | 03 | 1 | NORM-01, NORM-02, NORM-05 | T-02-01 (alias poison) | unit | `uv run pytest tests/unit/test_yaml_brand_alias.py tests/unit/test_brand_normalizer.py tests/unit/test_name_normalizer.py -x -q && grep -q "_normalize_punct" alias/yaml_loader.py` | ❌ W0 | ⬜ pending |
| 02-03-T2 | 03 | 1 | NORM-03, NORM-04 | T-02-NORM03 (volume drift) | unit + corpus-driven | `uv run pytest tests/unit/test_volume_normalizer.py -x -q && grep -q "UNIT_TABLE" volume.py && grep -q "multipack" volume.py` | ❌ W0 | ⬜ pending |
| 02-04-T1 | 04 | 1 | PARSE-01, PARSE-02, PARSE-03, PARSE-04, PARSE-06 | T-02-04 (NEXT_DATA drift), T-02-Parse | unit | `uv run pytest tests/unit/test_viled_nextdata_parser.py tests/unit/test_parse_dispatcher.py -x -q && grep -q "__NEXT_DATA__" parsers/viled_nextdata.py && test_no_respx_used asserts no respx import` | ❌ W0 | ⬜ pending |
| 02-04-T2 | 04 | 1 | CRAWL-01, CRAWL-03, CRAWL-04, CRAWL-06 | T-02-Crawl, T-02-Rate | unit + integration | `uv run pytest tests/unit/test_viled_catalog_paginate.py tests/unit/test_viled_fetcher_isolation.py tests/unit/test_viled_retry_policy.py tests/unit/test_viled_rate_limit.py tests/integration/test_viled_fetcher_mocked.py -x -q` | ❌ W0 | ⬜ pending |
| 02-05-T1 | 05 | 2 | CRAWL-05, PARSE-05 | T-02-Phase3-Regression | unit | `uv run pytest tests/unit/test_auto_suggest_threshold.py tests/unit/test_sanity_n_gate.py tests/unit/test_parse_quality_gate.py tests/unit/test_viled_stats_builder.py -x -q && grep -q "auto_suggest_threshold" gates.py && grep -q "VILED_STATS_KEYS" stats.py` | ❌ W0 | ⬜ pending |
| 02-05-T2 | 05 | 2 | CRAWL-05, PARSE-05, NORM-06 (orchestration) | T-02-02, T-02-06, T-02-DATA05 | integration | `uv run pytest tests/integration/test_viled_run_e2e_with_real_storage.py tests/integration/test_main_run_e2e.py -x -q && grep -q "ViledPhaseResult" viled_run.py && grep -q "DISTINCT brand_norm" main_run.py` | ❌ W0 | ⬜ pending |
| 02-05-T3 | 05 | 2 | D-212 (stub cutover) | T-02-D212-Cascade | grep + smoke | `grep -v '^#' cli.py \| grep -c "class Stub" == 0 && grep -v '^#' cli.py \| grep -c "goldapple-run" == 0 && python -m ga_crawler --help shows weekly-run + goldapple-smoke && pytest -m "not live" exits 0` | ❌ W0 | ⬜ pending |
| 02-06-T1 | 06 | 3 | NORM-01 (seed) | T-02-01, T-02-Backup-1, T-02-Backup-2 | shell + smoke | `test -f config/brand-aliases.yaml && yaml.safe_load(...) >= 50 && test -x bin/backup.sh && grep "sqlite3.*backup" bin/backup.sh && grep "tail -n +5" bin/backup.sh && YamlBrandAlias loads ≥50 entries` | ❌ W0 | ⬜ pending |
| 02-06-T2 | 06 | 3 | DATA-06, doc-cascade | T-02-Backup-2, T-02-Doc-Cascade | integration + grep | `uv run pytest tests/integration/test_backup_script.py -x -q && grep -q "men/catalog/1310" REQUIREMENTS.md && grep -q "men/catalog/1310" PROJECT.md && grep -q "Phase 2 scope narrowed" STATE.md && grep -c "catalog/1310" ROADMAP.md ≥ 2 && pytest -m "not live" exits 0` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*File Exists: ✅ exists / ❌ W0 = test file scaffolded as skip-marked stub by Plan 02-01 Wave 0; Wave N production task removes the skip marker.*

**Nyquist compliance:** ✅ Every task above has an `<automated>` command (no manual-only verifications among the 14 tasks). The 3 manual-only items below are not production tasks but external-environment checks documented for ops-playbook handoff (Phase 7 territory).

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- [ ] `uv add pyyaml` — only new dependency (per RESEARCH §Standard Stack)
- [ ] `tests/conftest.py` — extends with 6 new fixtures (viled_pdp_html, viled_catalog_html, brand_alias_yaml_fixture, in_memory_sqlite_session, volume_corpus_cases, brand_corpus_cases) preserving existing 11 Phase 3 fixtures
- [ ] `tests/fixtures/viled/` — captured live `__NEXT_DATA__` payload(s) from one beauty SKU (probe outcome from RESEARCH §Wave 0 A1, A2)
- [ ] `tests/fixtures/viled/` — captured catalog/1310 page-1 payload (probe outcome from RESEARCH §Wave 0 A3, A4)
- [ ] `tests/fixtures/normalize/volume-corpus.yaml` — ≥15 cases of real volume strings (`30 мл`, `30мл`, `30ml`, `1.0 oz`, `3 шт x 50мл`, kits/sets) per CONTEXT D-217 + ROADMAP success criterion 4
- [ ] `tests/fixtures/normalize/brand-corpus.yaml` — ≥10 cases for Cyrillic↔Latin alias resolution per CONTEXT D-206
- [ ] 24 skip-marked test stubs — one per file from RESEARCH §Validation Architecture map; each carries `pytestmark = pytest.mark.skip(reason="Wave N not implemented yet")` and Plan 02-NN flips the skip during the production wave

**Wave 0 also probes (per RESEARCH `## Wave 0 Probes`):**
- A1: viled `__NEXT_DATA__` field paths (`pageProps.product.attributes[0].realPrice` etc.) — verify against live page
- A2: viled discount semantics (`price` vs `realPrice` direction)
- A3: viled `/men/catalog/1310` returns 200 + `pageProps.products[]` for unauthenticated curl_cffi
- A4: catalog pagination metadata structure
- A10: `from curl_cffi.requests.errors import RequestsError, Timeout` import path verified

---

## Manual-Only Verifications

> These are NOT production tasks (none appear in the per-task map above). They are external-environment checks documented here for the Phase 7 ops-playbook handoff.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Backup directory contains ≥4 most-recent backups | DATA-06 | Cron-driven file rotation; deterministic filesystem state hard to assert in CI for the production VPS (the integration test in 02-06-T2 covers this in-process) | After 4 weekly runs on VPS, `ls -1t backups/*.db \| head -4` returns 4 files; older files purged |
| First production weekly run succeeds against live viled.kz | success#1, #3 | Real network + bot-detection state cannot be reproduced offline | Operator runs `python -m ga_crawler weekly-run` after deploy; checks Telegram delivery + run status in DB |
| Sanity gate threshold tuned against real catalog size | success#5 / D-201 auto-suggest | Threshold value depends on observed live `viled_count`; only set after first 4–5 successful runs | Operator records `viled_count` from first 4 runs, accepts auto-suggest_n PR if magnitude warrants |

---

## Validation Sign-Off

- [x] All 14 tasks have `<automated>` verify commands (Nyquist ✅)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task is automated)
- [x] Wave 0 covers all MISSING references (probes A1..A4, A10 + corpus YAML + conftest extensions)
- [x] No watch-mode flags (CI-friendly invocations only)
- [x] Feedback latency < 30s (quick) / 90s (full) — verified by RESEARCH §Validation Architecture
- [x] `nyquist_compliant: true` set in frontmatter (every task has `<automated>`; no manual-only production gates)
- [ ] `wave_0_complete: false` — flips to `true` after Plan 02-01 ships and live probes A1/A2/A3/A4/A10 are committed to 02-WAVE0-PROBE.md

**Approval:** pending operator review of per-task map; auto-approve gate is `nyquist_compliant=true && wave_0_complete=true`.
