---
phase: 8
slug: parser-bug-fixes
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-13
approved: 2026-05-13
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `08-RESEARCH.md` § Validation Architecture (lines 994-1058).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio ≥0.24 (existing, LOCKED) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (markers `live`, `integration` lines 51-53) |
| **Quick run command** | `uv run pytest tests/parsers tests/runner/test_parser_drift_gate.py -x` |
| **Full suite command** | `uv run pytest -m "not live" -q` |
| **Estimated runtime** | ~10-15s quick / ~60-90s full (818 tests projected) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/parsers tests/runner -x` (≤15s)
- **After every plan wave:** Run `uv run pytest -m "not live" -q` (full suite)
- **Before `/gsd-verify-work`:** Full suite must be green + manual visual inspection of `tests/fixtures/{goldapple,viled}/_live-2026-05-13-*.html` to confirm real HTML (not Camoufox error pages)
- **Max feedback latency:** 15 seconds per task; 90 seconds per wave

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-* | 01 | 0 | PARSE-FIX-01..05 (enables) | V12 | No PII / cf_clearance / UUIDs in committed fixtures | manual review | `git diff --staged tests/fixtures/` | ❌ W0 | ⬜ pending |
| 08-02-* | 02 | 1 | PARSE-FIX-01 | V5 | `_extract_volume_block` returns None on malformed HTML | unit | `uv run pytest tests/parsers/test_goldapple_volume_block.py -x` | ❌ W0 | ⬜ pending |
| 08-02-* | 02 | 1 | PARSE-FIX-01 | — | parametrized ≥3 fixtures yield non-None `volume_norm` | unit | same file | ❌ W0 | ⬜ pending |
| 08-03-* | 03 | 1 | PARSE-FIX-02 | V5 | invariant canary `brand.lower() not in name.lower()` holds | unit | `uv run pytest tests/parsers/test_goldapple_brand_name.py::test_invariant_canary -x` | ❌ W0 | ⬜ pending |
| 08-03-* | 03 | 1 | PARSE-FIX-02 | — | `name == "sago"` (microdata read, not h1 concat) | unit | same file | ❌ W0 | ⬜ pending |
| 08-03-* | 03 | 1 | PARSE-FIX-02 | — | backward-compat: Givenchy `name == "Pour Homme"` | unit | same file | ❌ W0 | ⬜ pending |
| 08-04-* | 04 | 1 | PARSE-FIX-03 | V5 | `_extract_volume_from_nextdata` returns "50 мл" for discounted-beauty | unit | `uv run pytest tests/parsers/test_viled_volume_from_nextdata.py -x` | ❌ W0 | ⬜ pending |
| 08-04-* | 04 | 1 | PARSE-FIX-03 | — | parametrized 4 fixtures (clothing "S" / multipack / discounted / contre-jour None) | unit (parametrize) | same file | ❌ W0 | ⬜ pending |
| 08-04-* | 04 | 1 | PARSE-FIX-03 | — | `raw_volume_text == "50 мл"` flips existing viled test assertion | unit (modify existing) | `uv run pytest tests/parsers/test_viled_nextdata.py -x` | ✅ exists (modify 1 line) | ⬜ pending |
| 08-05-* | 05 | 3 | PARSE-FIX-04 | V7 | `parser_drift_null_rate_gate(0.6, 0.0)` → `passed=False, reason="parser_drift_null_volume_rate"` | unit | `uv run pytest tests/runner/test_parser_drift_gate.py -x` | ❌ W0 | ⬜ pending |
| 08-05-* | 05 | 3 | PARSE-FIX-04 | — | parametrized 6 boundary cases (both-pass / volume-fail / brand-fail / both-fail / exactly-at-threshold / custom-threshold) | unit (parametrize) | same file | ❌ W0 | ⬜ pending |
| 08-05-* | 05 | 3 | PARSE-FIX-04 | V7 | Synthetic regression: 60% NULL → `run.status="failed"`, `stats.parser_drift_failure_reason="parser_drift_null_volume_rate"` (Success Criteria #5) | integration | `uv run pytest tests/integration/test_phase8_synthetic_regression.py -x` | ❌ W0 | ⬜ pending |
| 08-05-* | 05 | 3 | PARSE-FIX-05 | — | `SMOKE_URLS` len 3, contains STEREOTYPE-style + Armani-style + Givenchy baseline | unit (structural canary) | `uv run pytest tests/runner/test_smoke_urls_rotation.py -x` | ❌ W0 | ⬜ pending |
| (aggregate) | all | all | all | — | 803 existing tests stay green; ~818 total | regression | `uv run pytest -m "not live" -q` | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/parsers/test_goldapple_volume_block.py` — stubs for PARSE-FIX-01 (Plan 08-02 W1)
- [ ] `tests/parsers/test_goldapple_brand_name.py` — stubs for PARSE-FIX-02 (Plan 08-03 W1)
- [ ] `tests/parsers/test_viled_volume_from_nextdata.py` — stubs for PARSE-FIX-03 (Plan 08-04 W1)
- [ ] `tests/runner/test_parser_drift_gate.py` — stubs for PARSE-FIX-04 unit (Plan 08-05 W2)
- [ ] `tests/integration/test_phase8_synthetic_regression.py` — stub for PARSE-FIX-04 SC#5 integration (Plan 08-05 W2)
- [ ] `tests/runner/test_smoke_urls_rotation.py` — stub for PARSE-FIX-05 (Plan 08-05 W2)
- [ ] `tests/conftest.py` — append 3 new fixture loaders for `_live-2026-05-13-*` variants (Plan 08-01 W0)
- [ ] `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` — committed (Plan 08-01 W0)
- [ ] `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` — committed (Plan 08-01 W0)
- [ ] `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` — committed (Plan 08-01 W0)

**Framework install:** None — pytest 8.x + pytest-asyncio ≥0.24 already in `pyproject.toml [dependency-groups].dev`.

**selectolax upgrade:** `uv lock --upgrade-package selectolax && uv sync` after bumping `pyproject.toml [project].dependencies` to `selectolax>=0.4.7,<0.5`. First step in Plan 08-02 (RED → bump → GREEN).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `_live-2026-05-13-*.html` are real HTML (not Camoufox error pages or 403/Cloudflare-challenge stubs) | PARSE-FIX-01..03 (enables) | Visual confirmation that fetched HTML carries real product microdata, not a bot-detect interstitial | Open each fixture in browser; confirm `<meta itemprop="name">` and product structure present; check filesize >50 KB |
| No PII / `cf_clearance=` / UUID-shaped session tokens in committed fixtures | V12 (security) | Phase 8 lacks automated gitleaks scan (Phase 9 TEST-HARNESS-02 formalizes) | `git diff --staged tests/fixtures/` + grep for `cf_clearance`, `[a-f0-9]{8}-[a-f0-9]{4}`, `Bearer `, `eyJ` |
| `shape-table.md` filled with concrete brand_raw / name_raw / volume_block_present / shape_bucket for all 30 PDPs | D-808 spike output gate | Operator must categorize observed shapes; LLM cannot do this from raw HTML reliably without W0 evidence | Spot-check 5 random rows in `shape-table.md` against the corresponding `.planning/spikes/v1.1-brand-name-shapes/pdp-NN-*.html` file |

---

## Sampling Sufficiency (Nyquist coverage rationale)

For each parser fix, the test set must oversample the shape diversity revealed by W0:

- **PARSE-FIX-01 volume:** ≥3 fixtures (Givenchy-baseline volume-in-title, STEREOTYPE-style separate-block uppercase, Armani-style separate-block mixed-case). If W0 reveals 4th shape bucket, add 4th fixture.
- **PARSE-FIX-02 brand+name:** ≥3 fixtures, same buckets. Invariant canary `brand.lower() not in name.lower()` holds across all + existing 60+ Givenchy tests.
- **PARSE-FIX-03 viled volume:** ≥4 fixtures — clothing "S" / multipack "200мл+..." / discounted "50 мл" / live Contre-Jour (no `Размер`). Disambiguation rule (clothing "S" → `volume_norm=None`) verified via real `parse_volume`, not mock.
- **PARSE-FIX-04 null-rate gate:** ≥6 unit boundary cases + 1 integration test injecting 60% null volumes against in-memory SQLite. Proves the gate handles all branches AND wires correctly to `runs.stats` + `runs.status`.
- **PARSE-FIX-05 smoke rotation:** 1 structural canary asserting `SMOKE_URLS` shape. Real-world validation is the next live run (Phase 11 cron tick).

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (confirmed via plan-checker Dim 8a)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (confirmed via plan-checker)
- [x] Wave 0 covers all MISSING references (Plan 08-01 creates 3 fixtures + conftest extension + skill)
- [x] No watch-mode flags (all commands are one-shot pytest invocations)
- [x] Feedback latency < 90s (quick run ≤15s, full suite ≤90s baseline)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-13 by plan-phase orchestrator (gsd-plan-checker Dim 8 PASS, post-paperwork fix)
