---
phase: 3
slug: goldapple-crawl
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Detailed invariants and fixtures live in `03-RESEARCH.md` § Validation Architecture; this file is the executable summary the planner fills.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (project default per CLAUDE.md) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (Wave 0 installs `pytest`, `pytest-asyncio`, `respx`) |
| **Quick run command** | `uv run pytest -q -m "not live"` |
| **Full suite command** | `uv run pytest --cov=ga_crawler --cov-report=term-missing` |
| **Estimated runtime** | ~30 s quick / ~120 s full (no live network) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q -m "not live"` (skips Camoufox/network tests)
- **After every plan wave:** Run `uv run pytest --cov=ga_crawler` (full unit + integration with mocks)
- **Before `/gsd-verify-work`:** Full suite green + 1-hour live smoke (manual) per Success Criterion 4
- **Max feedback latency:** 30 seconds (quick run)

---

## Per-Task Verification Map

> Filled by gsd-planner during PLAN.md generation. Each row binds a task to a requirement, an automated command, and (where applicable) a threat-model reference. Skeleton rows below mark the invariants pulled from `03-RESEARCH.md` § Validation Architecture; the planner replaces `{plan_id}-{task_id}` placeholders with real IDs.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {plan}-{task} | 01 | 0 | infra | — | pytest + respx + camoufox installed | infra | `uv run pytest --collect-only` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 02 | 1 | CRAWL-02 | T-04 (sitemap-poison) | Sitemap parser rejects malformed XML; bilingual slug-fy idempotent | unit | `uv run pytest tests/unit/test_slugfy.py -q` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 02 | 1 | NORM-06 (reverse) | — | Slug-intersection produces zero false-positives on `Tom Ford` ↔ `tom-ford-beauty` fixture | unit | `uv run pytest tests/unit/test_brand_intersection.py -q` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 03 | 2 | PARSE-01..06 | T-09 (parser-malicious-html) | Microdata extractor returns current price, ignores StrikethroughPrice/ListPrice/GoldCard | unit | `uv run pytest tests/unit/test_goldapple_parser.py -q` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 03 | 2 | PARSE-04 | — | Sanity range 100..1_000_000 ₸; out-of-range → parse_error flag | unit | same as above (`-k sanity_range`) | ❌ W0 | ⬜ pending |
| {plan}-{task} | 04 | 3 | CRAWL-03 | T-11 (per-SKU isolation) | One bad URL doesn't abort run | unit | `uv run pytest tests/unit/test_fetcher_isolation.py -q` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 04 | 3 | CRAWL-04 | — | Retry uses exponential + jitter; honours max-attempts | unit | `uv run pytest tests/unit/test_retry.py -q` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 04 | 3 | CRAWL-02 | T-08 (gate-shell) | Title-check distinguishes shell (~9.5 KB) from de-listed (≥30 KB no microdata) | unit | `uv run pytest tests/unit/test_gate_detection.py -q` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 04 | 3 | D-303 stale-SKU | — | "200 + <30 KB + no microdata" → stale_count++; not parse_error | unit | same as above (`-k stale`) | ❌ W0 | ⬜ pending |
| {plan}-{task} | 05 | 4 | D-312 smoke-probe | T-01 (smoke-bypass) | All probe URLs must pass; first failure → run aborts before crawl | unit | `uv run pytest tests/unit/test_smoke_probe.py -q` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 05 | 4 | CRAWL-05 sanity-gate | — | Final gate: `goldapple_count < M` → `runs.status='failed'` | unit | `uv run pytest tests/unit/test_final_gate.py -q` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 05 | 4 | D-310 auto-suggest | — | Suggestion fires only with ≥4 weeks history; formula `0.7 × median` | unit | same as above (`-k auto_suggest`) | ❌ W0 | ⬜ pending |
| {plan}-{task} | 05 | 4 | NORM-06 forward | — | Viled brands with zero matches go to review queue; counter incremented | unit | `uv run pytest tests/unit/test_norm06.py -q` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 05 | 4 | D-307 NORM-06 reverse | — | Week-over-week NEW goldapple-slug diff non-empty after second run only | unit | same as above (`-k week_over_week`) | ❌ W0 | ⬜ pending |
| {plan}-{task} | 06 | 5 | DATA-03/04 | — | Snapshots INSERT-only; `runs` row updated atomically; WAL retained | integration | `uv run pytest tests/integration/test_storage_integration.py -q` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 06 | 5 | CRAWL-02 (E2E) | — | Full mock pipeline: sitemap → intersect → fetch (mocked Camoufox) → parse → store → gate | integration | `uv run pytest tests/integration/test_e2e_mocked.py -q` | ❌ W0 | ⬜ pending |
| {plan}-{task} | 07 | 6 | Success Criterion 4 | T-02 (anti-bot regression) | 1-hour live run: <5% gate-shell, no sustained 429/503 | manual+live | `uv run python -m ga_crawler.cli live-smoke --hour=1` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> **Note:** Threat refs (T-NN) point to `03-RESEARCH.md` § Threat model. Final IDs are bound when planner produces PLAN.md. The Wave-0 column holds `❌ W0` for every row above because no test file exists yet — Wave 0 task creates the scaffolding.

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — add `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, marker registry (`live`, `integration`)
- [ ] `tests/conftest.py` — shared fixtures: `sitemap_xml_fixture`, `goldapple_pdp_html_fixture` (loads `_debug-product-page.html`), `goldapple_shell_html_fixture` (loads gate-shell sample), `runs_row_factory`, `tmp_camoufox_profile_dir`
- [ ] `tests/unit/test_slugfy.py` — stub for slug-fy invariants (Cyrillic, ASCII transliterate, 11 enumerated cases per RESEARCH §"Slug-fy")
- [ ] `tests/unit/test_brand_intersection.py` — stub
- [ ] `tests/unit/test_goldapple_parser.py` — stub
- [ ] `tests/unit/test_fetcher_isolation.py` — stub
- [ ] `tests/unit/test_retry.py` — stub
- [ ] `tests/unit/test_gate_detection.py` — stub (uses gate-shell fixture)
- [ ] `tests/unit/test_smoke_probe.py` — stub
- [ ] `tests/unit/test_final_gate.py` — stub
- [ ] `tests/unit/test_norm06.py` — stub
- [ ] `tests/integration/test_storage_integration.py` — stub (in-memory SQLite + WAL pragma)
- [ ] `tests/integration/test_e2e_mocked.py` — stub (mocked Camoufox via fixture)
- [ ] `src/ga_crawler/interfaces.py` — Phase 2 contract Protocols (`BrandAlias`, `Normalize`, `SnapshotWriter`, `ParseDispatcher`) so Phase 3 can develop in parallel; Phase 2 imports satisfy these signatures
- [ ] `uv add` pins (locked): `camoufox==135.0.1.beta24`, `tenacity>=9`, `selectolax>=0.3`, `curl_cffi>=0.15`, `pytest`, `pytest-asyncio`, `respx`, `structlog`
- [ ] `uv run camoufox fetch` — downloads spoofed Firefox binary on dev box (post-deploy step on VPS too)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 1-hour live goldapple run | Success Criterion 4 | Live network + Camoufox; cannot mock without invalidating signal | `uv run python -m ga_crawler.cli live-smoke --hour=1`; assert `runs.status='success'`, `gate_shell_count/total < 5%`, no sustained 429/503 in structlog |
| First-week NORM-06 review queue triage | Success Criterion 5 | Subjective brand-coverage decision by operator | After first run: open NORM-06 review queue, confirm format usable, classify ≥10 entries (alias-add vs not-on-goldapple) |
| Smoke-probe URL pool curation | D-312 (Phase 7 ops-playbook seed) | Operator judgement on URL freshness | Quarterly: hand-rotate 1 of 3 smoke URLs; rerun smoke probe; verify pass |
| Camoufox upstream upgrade workflow | D-313 | Manual sign-off before `uv.lock` PR | On new Camoufox release: dev box → `uv add camoufox=={new}` → run live smoke → if pass, PR `uv.lock` change |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (planner enforces this)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (planner expands `❌ W0` rows)
- [ ] No watch-mode flags (pytest only, no `-f`/watcher)
- [ ] Feedback latency < 30 s (quick run)
- [ ] `nyquist_compliant: true` set in frontmatter (after planner-checker pass)

**Approval:** pending
