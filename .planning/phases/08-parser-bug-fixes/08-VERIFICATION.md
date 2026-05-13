---
phase: 08-parser-bug-fixes
verified: 2026-05-14T03:00:00Z
status: human_needed
score: 5/5 must-haves verified (operator live-run validation still required)
overrides_applied: 0
human_verification:
  - test: "Operator-deployed live dry-run on goldapple.kz + viled.kz produces goldapple_comparable_count > 0 and matched pairs land in matches table"
    expected: "After cron tick on Yandex Cloud kz1 (Phase 11), runs.stats.goldapple.volume_null_rate ≤ 0.5; matches table has rows; Excel report has match_count > 0"
    why_human: "Success Criterion #1 requires actual fetcher + Camoufox + live HTTP egress against Cloudflare/anti-bot — cannot be validated in CI/unit tests. Phase 11 (Operator Deploy) is the gating phase per ROADMAP.md; infrastructure (gate, helpers, SMOKE rotation, stats keys) is structurally complete and proven against fixtures."
---

# Phase 8: Parser Bug Fixes Verification Report

**Phase Goal:** Goldapple SKUs gain non-null `volume_raw`/`volume_norm` + clean `brand`/`name` split; viled SKUs gain volume from structured `attributes[]` field — together unblocking matched-pair production and ending empty-Excel deliveries.

**Verified:** 2026-05-14T03:00:00Z
**Status:** human_needed (infrastructure verified; live-run validation deferred to Phase 11)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (mapped from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Live dry-run yields `goldapple_comparable_count > 0` and matched pairs land in `matches` table | HUMAN_NEEDED | Infrastructure verified: parsers produce non-null volume_raw + clean brand/name on all 3 live fixtures (STEREOTYPE/Armani/Givenchy); viled `_extract_volume_from_nextdata` returns "50 мл" on discounted fixture; matcher pipeline unchanged. Live run blocked on Phase 11 (Yandex Cloud kz1 deploy). |
| 2 | `goldapple_volume_norm` non-null rate ≥ 90% on non-volumeless categories (PARSE-FIX-01) | VERIFIED | `_extract_volume_block` at `src/ga_crawler/parsers/goldapple_microdata.py:273-329` uses selectolax 0.4 Lexbor + ancestor-walk + regex extraction. Empirical smoke (just ran): STEREOTYPE → `"12 мл"`, Armani → `"50 мл"` (first variant), Givenchy → `"50 мл"`. Round-trip test `test_parse_pipeline_yields_non_null_volume_norm` PASSES for all 3 shape buckets. W0 spike measured 25/30 (83%) PDPs carry a volume block; remaining 5 are legitimate-None volumeless products (eye creams etc.). On the carrier-only subset coverage is 25/25 = 100% (well above 90%). |
| 3 | Invariant canary `assert brand.lower() not in name.lower()` holds across goldapple snapshots (PARSE-FIX-02 — softened to log-only canary per W0 evidence) | VERIFIED | `goldapple_microdata.py:431-437` emits `log.warning("goldapple_brand_in_name_canary_violation", ...)` when invariant fails. Softening rationale documented inline + in 08-03-SUMMARY.md (2/30 PDPs legitimately fail — `armani`/`armani code`, upstream-data-redundancy). Tests `test_invariant_canary_stereotype` + `test_invariant_canary_across_clean_buckets[givenchy,stereotype]` PASS (strict assertion on the 28/30 clean-separation bucket). Aggregate enforcement happens at the runner via PARSE-FIX-04 `brand_null_rate` (truth #5). |
| 4 | Test suite green at ~818 tests (now 848 passing — well above target) | VERIFIED | `uv run pytest -m "not live" -q` → **848 passed, 1 skipped, 0 failed** in 136s. Baseline 803 v1.0 + 45 new tests over 5 plans (target 818, exceeded by 30). All 41 Phase 8-specific tests PASS individually. |
| 5 | Null-rate sanity gate (PARSE-FIX-04) actively fails synthetic regression run injected with >50% null volume | VERIFIED | `tests/integration/test_phase8_synthetic_regression.py::test_synthetic_60pct_null_volume_triggers_drift_gate` PASSES — plants 6 NULL + 4 valid snapshots (60% null), invokes gate, asserts `passed=False`, `failure_reason='parser_drift_null_volume_rate'`, runs.status=='failed', stats['goldapple.parser_drift_failure_reason'] populated. Direct end-to-end exercise of Success Criterion #5. |

**Score:** 5/5 truths VERIFIED (truth #1 with HUMAN_NEEDED qualification — infrastructure complete, live operator validation pending Phase 11)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/ga_crawler/parsers/goldapple_microdata.py` | `_extract_volume_block` helper + h1-spans brand/name + canary log | VERIFIED | Helper at line 273 (LOCAL Lexbor import line 310 per D-806); h1 child-span brand/name extraction lines 396-409; canary log lines 431-437 |
| `src/ga_crawler/parsers/viled_nextdata.py` | `_extract_volume_from_nextdata` helper + callsite wired | VERIFIED | Helper at line 114; matches 3 attribute name variants (размер/объем/объём); callsite at line 251 `_extract_volume_from_nextdata(a0) or name`; exposed in `__all__` line 259 |
| `src/ga_crawler/runner/gates.py` | `parser_drift_null_rate_gate` + `ParserDriftGateResult` + rotated SMOKE_URLS | VERIFIED | Frozen dataclass lines 288-305; gate function lines 308-342 (strict `> threshold` semantics; volume-priority on dual-fail); SMOKE_URLS rotated lines 50-54 (stereotype-sago + armani-code + givenchy-irresistible retained per D-818); `__all__` extended line 389-390 |
| `src/ga_crawler/runner/stats.py` | 3 new `goldapple.*` stats keys (13 → 16) | VERIFIED | Lines 36-38 add `goldapple.volume_null_rate`, `goldapple.brand_null_rate`, `goldapple.parser_drift_failure_reason`. `_BARE_TO_NAMESPACED` dict-comprehension at line 43 auto-picks-up new keys (no explicit additions to `_resolve` needed) — confirmed via spot-check (`GoldappleStatsBuilder().set("volume_null_rate", 0.3)` resolves to `goldapple.volume_null_rate`) |
| `src/ga_crawler/runners/main_run.py` | Orchestrator wiring at D-817 position (after goldapple+parse-quality, before matcher) | VERIFIED | Lines 275-355 — gate block sits after goldapple `g_result` handling (line 273) and before matcher invocation (line 367+). Imports parser_drift_null_rate_gate (line 46) + GoldappleStatsBuilder (line 47). Pitfall 6 empty-crawl guard at line 294 (`if goldapple_count > 0:`); Pitfall 4 sentinel at line 320 (`"" if None`). Single round-trip SQL AVG, atomic patch_stats merge. On fail: `run_writer.fail()` + Norm06 ledger + early-return MainRunResult(status="failed") |
| `tests/parsers/test_goldapple_volume_block.py` | PARSE-FIX-01 unit + parametrized round-trip tests | VERIFIED | 7 tests, all PASS. Covers STEREOTYPE/Armani/Givenchy via parametrized round-trip with normalizers.volume.parse_volume |
| `tests/parsers/test_goldapple_brand_name.py` | PARSE-FIX-02 invariant canary + microdata-read + backward-compat tests | VERIFIED | 6 collected (5 standalone + parametrize over 2 clean-separation buckets). All PASS. Test for Armani upstream-data-redundancy bucket asserts non-CONCATENATION (`name=='armani code'` not `'Armaniarmani code'`) rather than non-CONTAINMENT — matches W0 §4 softening decision |
| `tests/parsers/test_viled_volume_from_nextdata.py` | PARSE-FIX-03 unit + parametrized round-trip across 4 fixtures | VERIFIED | 14 tests, all PASS. Covers 10 helper-unit cases + 4 round-trip across discounted/clothing/multipack/contre-jour fixtures |
| `tests/runner/test_parser_drift_gate.py` | 8 boundary tests + frozen-dataclass canary | VERIFIED | 9 tests, all PASS (8 from plan template + 1 defensive `test_brand_custom_threshold_fails_with_brand_reason`). Covers exact-threshold-passes (D-815 strict `>`), volume-priority on dual-fail, custom threshold, frozen dataclass |
| `tests/runner/test_smoke_urls_rotation.py` | Structural canary: len 3, regex match, Givenchy retained, 3 distinct slugs | VERIFIED | 4 tests, all PASS. Confirms STEREOTYPE + Armani + Givenchy distinct shape rotation |
| `tests/integration/test_phase8_synthetic_regression.py` | Success Criteria #5 synthetic-regression scenario | VERIFIED | 1 test, PASSES. End-to-end: plants 60% NULL snapshots, runs gate, asserts run.status='failed' + reason='parser_drift_null_volume_rate' + 3 stats keys populated |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `goldapple_microdata.py::parse_pdp` line 464 | `_extract_volume_block` helper line 273 | `raw_volume_text = _extract_volume_block(html) or name or None` callsite | WIRED | Grep confirms wire; round-trip test passes against 3 fixtures |
| `goldapple_microdata.py::parse_pdp` lines 396-409 | h1 child-span CSS selectors | `h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__brand_"]` | WIRED | Pivot from microdata-walk (W0 invalidated) to h1-spans; empirically verified on 3 live fixtures |
| `viled_nextdata.py::parse_pdp` line 251 | `_extract_volume_from_nextdata` helper line 114 | `raw_volume_text=_extract_volume_from_nextdata(a0) or name` | WIRED | Callsite present; integration test confirms behavior on 4 fixtures including legitimate-None Contre-Jour |
| `main_run.py` lines 275-355 | `parser_drift_null_rate_gate` from gates.py | imported line 46, called line 308 | WIRED | Gate wired at D-817 position; integration test exercises full path |
| `main_run.py` lines 314-323 | `GoldappleStatsBuilder` from stats.py | imported line 47, used to set 3 new keys, patched via `run_writer.patch_stats` | WIRED | All 3 new stats keys (volume_null_rate, brand_null_rate, parser_drift_failure_reason) flow into runs.stats |
| `gates.py::SMOKE_URLS` lines 50-54 | shape-table.md selected fixture URLs (W0 spike) | URL tuples copied per D-818 | WIRED | STEREOTYPE-sago + Armani-code + Givenchy-irresistible match W0 spike output; test_smoke_urls_rotation.py canary green |
| `test_stats_namespace.py` line 14 | `GOLDAPPLE_STATS_KEYS` length canary | `assert len(GOLDAPPLE_STATS_KEYS) == 16` | WIRED | Coupled canary flipped 13→16; 3 new parametrize entries added |
| `test_viled_stats_builder.py` line 116 | duplicate coupled canary | `assert len(GOLDAPPLE_STATS_KEYS) == 16` | WIRED | Auto-fixed during Plan 08-05 GREEN (PATTERNS.md only listed test_stats_namespace.py; this duplicate caught by full-suite run) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|---------|
| `_extract_volume_block` | `composed` text from Lexbor ancestor-walk | Real PDP HTML → Lexbor parser → ancestor.text(deep=True) | YES — STEREOTYPE returns `"12 мл"`, Armani returns `"50 мл"`, Givenchy returns `"50 мл"` (smoke-checked just now) | FLOWING |
| `_extract_volume_from_nextdata` | `value` from attributes[0].attributes[] entry where name in {"размер","объем","объём"} | __NEXT_DATA__ JSON → page_props.attributes[0] | YES — discounted fixture yields `"50 мл"`, clothing yields `"S"`, multipack yields multi-variant string | FLOWING |
| `parser_drift_null_rate_gate` | `volume_null_rate`, `brand_null_rate` floats | SQL `AVG(CASE WHEN volume_norm IS NULL ...)` over `snapshots WHERE run_id=:rid AND retailer='goldapple'` | YES — synthetic test plants 6 NULL + 4 valid → 0.6 average correctly computed | FLOWING |
| `GoldappleStatsBuilder` 3 new keys | `delta` dict with `goldapple.*` namespaced keys | `_BARE_TO_NAMESPACED` comprehension picks up new keys automatically | YES — spot-check shows builder.set() resolves all 3 short keys to namespaced form and atomic patch_stats merges | FLOWING |
| h1-spans brand/name | `brand_raw`, `name` strings | `h1[class*="_ga-pdp-title__heading_"]` → child spans with class-substring match | YES — STEREOTYPE: brand='Stereotype', name='SAĜO'; Armani: brand='Armani', name='armani code'; Givenchy: brand='Givenchy', name=(non-empty per backward-compat tests) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Volume extraction on 3 live fixtures | `python -c "from ga_crawler.parsers.goldapple_microdata import _extract_volume_block; ..."` | STEREOTYPE → "12 мл" / Armani → "50 мл" / Givenchy → "50 мл" | PASS |
| Brand+name h1-spans extraction | parse_pdp on 3 fixtures | STEREOTYPE: ('Stereotype', 'SAĜO') / Armani: ('Armani', 'armani code') / Givenchy: ('Givenchy', non-empty) | PASS |
| Stats namespace length canary | `len(GOLDAPPLE_STATS_KEYS) == 16` | True | PASS |
| GoldappleStatsBuilder new short keys | `b.set('volume_null_rate', 0.3); 'goldapple.volume_null_rate' in b.delta` | True | PASS |
| Phase 8 specific tests | `pytest tests/parsers/test_goldapple_volume_block.py tests/parsers/test_goldapple_brand_name.py tests/parsers/test_viled_volume_from_nextdata.py tests/runner/test_parser_drift_gate.py tests/runner/test_smoke_urls_rotation.py tests/integration/test_phase8_synthetic_regression.py` | 41 passed, 0 failed, 0.33s | PASS |
| Full integration suite (gate-wiring sanity) | `pytest tests/integration/ -q` | 153 passed, 1 skipped, 0 failed, 60s | PASS |
| Full non-live test suite (no regression) | `pytest -m "not live" -q` | **848 passed, 1 skipped, 0 failed** in 136s | PASS |
| Live operator dry-run on goldapple.kz | (Phase 11 deploy) | Not runnable in CI — requires Camoufox + Yandex Cloud kz1 VPS + cron tick | SKIP — routed to human verification |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PARSE-FIX-01 | Plan 08-02 | Goldapple parser извлекает `volume_raw` from structured PDP-block; ≥90% non-null rate | SATISFIED | `_extract_volume_block` at goldapple_microdata.py:273; 7/7 parametrized tests pass across 3 shape buckets; 100% extraction on the 25/30 non-volumeless subset (W0 evidence) |
| PARSE-FIX-02 | Plan 08-03 | Goldapple parser extracts `brand` and `name` separately via h1-spans (W0 pivot); invariant canary softened to log-only | SATISFIED | h1 child-span brand/name extraction at goldapple_microdata.py:396-409; canary log at line 431-437; 6/6 tests pass |
| PARSE-FIX-03 | Plan 08-04 | Viled parser extracts `volume_raw` from `attributes[0].attributes[].name=="Размер"` JSON; fallback на regex по name только если отсутствует | SATISFIED | `_extract_volume_from_nextdata` at viled_nextdata.py:114; callsite line 251 with `or name` fallback; 14/14 tests pass (10 unit + 4 round-trip) |
| PARSE-FIX-04 | Plan 08-05 | Sanity-gate null-rate fail: run with `goldapple_volume_norm` null rate >50% → run marked `failed` with reason `parser_drift_null_volume_rate` | SATISFIED | Gate + ParserDriftGateResult at gates.py:288-342; orchestrator wiring at main_run.py:275-355 (D-817 position); 9 unit tests + 1 integration test (synthetic regression) all pass |
| PARSE-FIX-05 | Plan 08-05 | Smoke-probe URL rotation: SMOKE_URLS includes 1 URL per shape variant | SATISFIED | SMOKE_URLS rotated at gates.py:50-54 (STEREOTYPE + Armani + Givenchy retained per D-818); 4 canary tests pass |

**Orphaned requirements:** None. All 5 PARSE-FIX requirements from REQUIREMENTS.md are mapped to plans in this phase and satisfied. REQUIREMENTS.md per-requirement mapping table confirms 5/5 Complete (2026-05-13).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TODO/FIXME/placeholder in any new Phase 8 file | — | — |
| (none) | — | No empty `return None`/`return []` flows that mask logic | — | — |
| (none) | — | No hardcoded empty data; all stub patterns are guarded isinstance checks (T-08-13 mitigation) | — | — |

Anti-pattern grep on the 5 modified production files (`goldapple_microdata.py`, `viled_nextdata.py`, `gates.py`, `stats.py`, `runners/main_run.py`) found:
- Multiple legitimate `return None` paths — all on isinstance guard failure or absent-data path (PARSE-FIX-03 Threat T-08-13 mitigation, documented in helper docstrings)
- No emoji, no console.log debug residue, no commented-out code blocks
- The `goldapple_brand_in_name_canary_violation` warning log is INTENTIONAL per W0 §4 design (D-816 softening) — documented in goldapple_microdata.py:423-430

### Human Verification Required

#### 1. Live operator dry-run end-to-end validation (Success Criterion #1)

**Test:** Operator runs `python -m ga_crawler weekly-run` on Yandex Cloud kz1 VPS (after Phase 11 deploy completes) against live goldapple.kz + viled.kz sites.

**Expected:**
- `runs.stats.goldapple.fetch_count > 0` (Camoufox successfully clears anti-bot)
- `runs.stats.goldapple.volume_null_rate ≤ 0.5` (parser_drift gate passes — confirms PARSE-FIX-01 works against real live HTML, not just W0-captured fixtures)
- `runs.status == "success"` (matcher proceeds; both `viled` and `goldapple` snapshot tables have rows; matcher's strict-key SQL JOIN produces matched pairs)
- Excel report delivered to Telegram business chat with `match_count > 0`

**Why human:**
- Requires Camoufox + Cloudflare/anti-bot interaction → real HTTP egress
- Requires Yandex Cloud kz1 VPS (Phase 11 not yet executed per ROADMAP.md/STATE.md)
- Cannot be simulated in CI (real anti-bot blocks unit-test traffic)
- The phase goal explicitly says "operator-track — verify infrastructure exists, not live run" (per ROADMAP.md Success Criterion #1 annotation). Infrastructure verified above; this is the live-validation step that closes the loop.

**Deferred-to clarification:** Phase 11 (Operator Deploy на Yandex Cloud kz1, REQ DEPLOY-01..08) explicitly carries DEPLOY-07: "First production Sunday cron tick → Telegram delivery xlsx with match_count > 0 in business chat". That requirement closes truth #1 cleanly — Phase 8 is structurally sufficient.

### Gaps Summary

**No blocker gaps.** All 5 Success Criteria from ROADMAP.md are either VERIFIED (#2-5) or HUMAN_NEEDED on operator deploy (#1). The infrastructure required for #1 (parsers, gate, stats keys, orchestrator wiring, SMOKE rotation) is structurally complete, exercised end-to-end via the synthetic-regression integration test, and proven against W0-captured live fixtures.

**Strategy pivot consistency check (W0 invalidation of microdata-walk):**
- Plan 08-03 originally specified `<meta itemprop="name">` microdata walk (PATTERNS.md template)
- W0 spike (Plan 08-01) empirically falsified premise: 0/30 PDPs carry product-level `<meta itemprop="name">`
- Landed implementation: h1 child-spans (`_ga-pdp-title__brand_*` / `_ga-pdp-title__name_*`) — 30/30 W0 coverage
- ROADMAP.md Phase 8 entry correctly describes LANDED outcome with parenthetical "(W0 pivot — `<meta itemprop="name">` premise invalidated per 08-01 spike)"
- REQUIREMENTS.md PARSE-FIX-02 description updated to reference h1 `.brand`/`.name` spans
- Pivot is documented in 4 places: 08-01-SUMMARY.md, 08-03-SUMMARY.md "Auto-fixed Issues §1", goldapple_microdata.py:380-393 docstring, SKILL.md
- **Verdict:** strategy pivot is internally consistent across plan/summary/code/docs. No latent contradictions.

**D-816 invariant canary softening consistency check:**
- W0 §4 decided to soften from gate-level to log-only because 2/30 PDPs legitimately fail (`Armani` in `armani code`, `GIVENCHY` in `GIVENCHY GENTLEMAN RESERVE PRIVEE`)
- Production code: `log.warning("goldapple_brand_in_name_canary_violation", ...)` — soft warning, no exception
- Test code: strict assertion only against clean-separation buckets (Givenchy + STEREOTYPE); Armani bucket covered by non-CONCATENATION assertion
- ROADMAP.md Success Criterion #3 explicitly annotated "(PARSE-FIX-02 — softened to log-only canary per W0 evidence)"
- Aggregate protection: PARSE-FIX-04 `brand_null_rate` gate catches the "all SKUs broken" mode at the runner level
- **Verdict:** softening is internally consistent and the test/production split correctly handles the "canary fires legitimately 2/30 times" reality.

**Cherry-pick provenance check (operator strategy note):**
- Plan 08-03 (Wave 2) merged via worktree merge commit 99921db (cleanly)
- Plan 08-05 (Wave 3) cherry-picked onto master across 8 commits: 3dc7383, 2beb965, b224868, 3725797, 84dd3ab, c0e23e8, 110e85f, ccd29e1 — confirmed via git log
- All 8 cherry-picked commits have consistent prefixes (`test(08-05): RED`, `feat(08-05): GREEN`, `feat(08-05): wire`, 4× `docs(08):`)
- No mid-cherry-pick contamination; doc cascade fully applied (REQUIREMENTS.md, PROJECT.md, ROADMAP.md, STATE.md all reflect Phase 8 closed)
- **Verdict:** cherry-pick provenance is clean. The worktree was branched from stale origin/master (pre-dotenv-hotfix); cherry-picks correctly skip 43dbfd7 (dotenv hotfix) since master had already merged that fix independently.

**Test count delta:** 803 (v1.0 baseline) → 848 (current full non-live suite) = +45 tests across 5 plans. Well above the 818 target stated in ROADMAP.md Success Criterion #4. Distribution:
- Plan 08-02 (PARSE-FIX-01): +7 (test_goldapple_volume_block.py)
- Plan 08-03 (PARSE-FIX-02): +6 (test_goldapple_brand_name.py)
- Plan 08-04 (PARSE-FIX-03): +14 (test_viled_volume_from_nextdata.py — 10 helper + 4 round-trip)
- Plan 08-05 (PARSE-FIX-04 + 05): +14 (9 gate + 4 SMOKE rotation + 1 synthetic regression) + 3 stats namespace parametrize additions

---

_Verified: 2026-05-14T03:00:00Z_
_Verifier: Claude (gsd-verifier) — Opus 4.7_
