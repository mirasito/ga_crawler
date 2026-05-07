---
phase: 02
slug: project-skeleton-viled-crawl-storage
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-07
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> See `02-RESEARCH.md` `## Validation Architecture` for the full strategy; this file is the planner-consumed sign-off contract.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio + respx (curl_cffi mocks) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) — Wave 0 task installs if missing |
| **Quick run command** | `uv run pytest tests/ -x -q --ignore=tests/integration --ignore=tests/e2e` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~30s quick, ~90s full (incl. integration + e2e fixtures) |

---

## Sampling Rate

- **After every task commit:** Run quick suite (unit only)
- **After every plan wave:** Run full suite (unit + integration + e2e)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (quick), 90 seconds (full)

---

## Per-Task Verification Map

> Filled in by gsd-planner. Each PLAN.md task injects rows here via the planner contract.
> Skeleton below shows the expected shape — planner replaces with concrete tasks.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | DATA-01..06 | — | DB schema migrations idempotent | unit | `uv run pytest tests/db/test_schema.py -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | NORM-01..06 | — | Brand/volume/name normalize per corpus | unit | `uv run pytest tests/normalize/ -q` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 1 | PARSE-01..06 | — | viled `__NEXT_DATA__` fields extracted | unit | `uv run pytest tests/parse/test_viled.py -q` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 2 | CRAWL-01,03..06 | — | Retry/backoff + per-SKU isolation | integration | `uv run pytest tests/crawl/ -q` | ❌ W0 | ⬜ pending |
| 02-05-01 | 05 | 3 | DATA-04, success#5 | — | Sanity gate marks run failed when count < threshold | integration | `uv run pytest tests/gates/test_sanity.py -q` | ❌ W0 | ⬜ pending |
| 02-06-01 | 06 | 3 | end-to-end | — | `python -m ga_crawler` smoke against fixture HTML | e2e | `uv run pytest tests/e2e/test_weekly_run.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- [ ] `uv add --dev pytest pytest-asyncio respx` — install test dependencies
- [ ] `tests/conftest.py` — shared fixtures (in-memory SQLite session, sample viled `__NEXT_DATA__` JSON, `respx` mock factory for curl_cffi)
- [ ] `tests/fixtures/viled/` — captured real `__NEXT_DATA__` payload(s) from one beauty SKU detail page (probe outcome from RESEARCH §Wave 0 A1, A2)
- [ ] `tests/fixtures/viled/catalog/` — captured catalog/1310 page payload (probe outcome from RESEARCH §Wave 0 A3, A4)
- [ ] `tests/fixtures/normalize/volume-corpus.yaml` — documented test suite of real volume strings (`30 мл`, `30мл`, `30ml`, `1.0 oz`, `3 шт x 50мл`, kits/sets) per CONTEXT D-217
- [ ] `tests/fixtures/normalize/brand-corpus.yaml` — Cyrillic↔Latin alias resolution cases per CONTEXT D-216
- [ ] `tests/db/test_schema.py` — stubs for `runs`, `products`, `prices` tables + WAL pragma + `json_patch` merge
- [ ] `tests/normalize/test_brand.py`, `test_volume.py`, `test_name.py` — stubs driven by corpus YAML
- [ ] `tests/parse/test_viled.py` — stubs for `__NEXT_DATA__` field extraction
- [ ] `tests/crawl/test_runner.py` — stubs for retry/backoff, per-SKU isolation, batched commit
- [ ] `tests/gates/test_sanity.py` — stubs for `viled_count < N` and null-rate >5%
- [ ] `tests/e2e/test_weekly_run.py` — stub for end-to-end fixture-driven run

**Wave 0 also probes (per RESEARCH `## Wave 0 Probes`):**
- A1: viled `__NEXT_DATA__` field paths (`pageProps.product.attributes[0].realPrice` etc.) — verify against live page
- A2: viled discount semantics (`price` vs `realPrice` direction)
- A3: viled `/men/catalog/1310` returns 200 + `pageProps.products[]` for unauthenticated curl_cffi
- A4: catalog pagination metadata structure
- A10: stock_state field name in `__NEXT_DATA__` payload

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Backup directory contains ≥4 most-recent backups | DATA-05 | Cron-driven file rotation; deterministic filesystem state hard to assert in CI | After 4 weekly runs, `ls -1t backups/*.db \| head -4` returns 4 files; older files purged |
| First production weekly run succeeds against live viled.kz | success#1, #3 | Real network + bot-detection state cannot be reproduced offline | Operator runs `python -m ga_crawler weekly-run` after deploy; checks Telegram delivery + run status in DB |
| Sanity gate threshold tuned against real catalog size | success#5 | Threshold value depends on observed live `viled_count`; only set after first 1–2 successful runs | Operator records `viled_count` from first 2 runs, sets `VILED_MIN_COUNT` to ~80% of median |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (probes A1..A4, A10 + corpus YAML + conftest)
- [ ] No watch-mode flags (CI-friendly invocations only)
- [ ] Feedback latency < 30s (quick) / 90s (full)
- [ ] `nyquist_compliant: true` set in frontmatter (after planner fills the per-task map)

**Approval:** pending
