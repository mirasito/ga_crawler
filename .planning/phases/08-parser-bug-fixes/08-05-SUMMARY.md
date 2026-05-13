---
phase: 08-parser-bug-fixes
plan: 05
subsystem: runner-gate + stats-namespace + orchestrator-wiring + doc-cascade
tags: [parse-fix, sanity-gate, smoke-rotation, doc-cascade, phase8-closure]
type: execute
wave: 3
autonomous: true
status: complete
completed: 2026-05-13
requirements: [PARSE-FIX-04, PARSE-FIX-05]
dependency_graph:
  requires:
    - .planning/phases/08-parser-bug-fixes/08-01-SUMMARY.md (W0 spike + SMOKE URL slots)
    - .planning/phases/08-parser-bug-fixes/08-02-SUMMARY.md (volume helper landed)
    - .planning/phases/08-parser-bug-fixes/08-03-SUMMARY.md (h1-spans brand+name landed)
    - .planning/phases/08-parser-bug-fixes/08-04-SUMMARY.md (viled volume helper landed)
  provides:
    - parser_drift_null_rate_gate + ParserDriftGateResult (D-815)
    - 3 new GOLDAPPLE_STATS_KEYS (volume_null_rate, brand_null_rate, parser_drift_failure_reason)
    - SMOKE_URLS rotated to 3 shape variants (D-818)
    - main_run.py D-817 wiring (after goldapple phase, before matcher)
    - Phase 8 closure paperwork (REQUIREMENTS/PROJECT/ROADMAP/STATE)
  affects:
    - Phase 9 (Live-HTML Harness — will lock these fixes retroactively via syrupy)
    - Phase 11 (Operator Deploy — first cron tick will exercise the new gate)
tech_stack:
  added: []
  patterns:
    - D-203 retailer-agnostic gate helper (frozen-dataclass return for multi-field result)
    - Pitfall 4 sentinel-on-pass for None-deleting RFC-7396 patch_stats
    - Pitfall 6 empty-crawl guard in orchestrator wiring
    - Doc cascade convention (single commit per file, message `docs(NN): mark Phase N reqs complete`)
key_files:
  created:
    - tests/runner/__init__.py
    - tests/runner/test_parser_drift_gate.py
    - tests/runner/test_smoke_urls_rotation.py
    - tests/integration/test_phase8_synthetic_regression.py
    - .planning/REQUIREMENTS.md (was deleted in worktree ancestor 0b713e3; re-created)
  modified:
    - src/ga_crawler/runner/gates.py (+94 LOC: dataclass + gate + SMOKE rotation + __all__)
    - src/ga_crawler/runner/stats.py (+13 LOC: 3 keys + docstring update)
    - src/ga_crawler/runners/main_run.py (+84 LOC: D-817 wiring + Pitfall 4+6 guards)
    - tests/unit/test_stats_namespace.py (13→16 + 3 parametrize entries)
    - tests/unit/test_viled_stats_builder.py (Rule 1 coupled-canary auto-fix: 13→16)
    - .planning/PROJECT.md (v1.1 Active section reflects Phase 8 complete)
    - .planning/ROADMAP.md (Phase 8 [x] + Progress 5/5 + Phase Details block + Plans list)
    - .planning/STATE.md (frontmatter v1.0→v1.1; Current Position advanced to Phase 9)
decisions:
  - D-810 doc cascade is part of Plan 08-05 — 4 atomic commits landed
  - D-813 50% absolute threshold — gate fails when null-rate > 0.5 (strict GT)
  - D-815 volume priority on dual-failure — `if v_fail: ... elif b_fail: ...` ordering
  - D-817 gate position — after goldapple phase + before matcher in main_run.py
  - D-818 SMOKE rotation — STEREOTYPE-sago + Armani-code + Givenchy-irresistible (Givenchy baseline retained)
metrics:
  duration_minutes: ~60
  test_count_delta: +15 (803 baseline → 818 passing in worktree)
  commits: 7
  loc_delta: "+659/-38"
---

# Phase 8 Plan 05: Phase 8 Defensive Close-Out Summary

## One-Liner

Locked in Phase 8 fixes structurally: added the PARSE-FIX-04 null-rate sanity gate (parser_drift_null_rate_gate with strict-> 0.5 threshold + volume-priority reason + frozen-dataclass result), rotated SMOKE_URLs to 3 shape variants per D-818, wired the gate into the orchestrator after goldapple phase / before matcher (D-817), and cascaded Phase 8 closure across REQUIREMENTS/PROJECT/ROADMAP/STATE — so future parser drift fails the run loudly instead of silently zeroing the Excel.

## What Shipped

### Production code

- **`src/ga_crawler/runner/gates.py`** (+94 LOC, net):
  - Imported `dataclass` from `dataclasses`.
  - Added `ParserDriftGateResult` (`@dataclass(frozen=True)`, 4 fields: `passed: bool`, `volume_null_rate: float`, `brand_null_rate: float`, `failure_reason: Optional[str]`).
  - Added `parser_drift_null_rate_gate(volume_null_rate, brand_null_rate, *, threshold=0.5) -> ParserDriftGateResult` with strict `>` threshold semantics (`> 0.5` fails; exactly `0.5` passes — per D-815). Priority ordering: `if v_fail: reason="parser_drift_null_volume_rate" elif b_fail: reason="parser_drift_null_brand_rate" else: reason=None`.
  - Rotated `SMOKE_URLS` to 3 shape-bucket coverage per D-818:
    - `19000440474-stereotype-sago` (STEREOTYPE-style)
    - `19000195723-armani-code` (Armani-style)
    - `19000488678-givenchy-irresistible` (Givenchy baseline, retained per D-818)
  - Extended `__all__` with `parser_drift_null_rate_gate`, `ParserDriftGateResult`.

- **`src/ga_crawler/runner/stats.py`** (+13 LOC):
  - Extended `GOLDAPPLE_STATS_KEYS` 13 → 16 with 3 new keys: `goldapple.volume_null_rate`, `goldapple.brand_null_rate`, `goldapple.parser_drift_failure_reason`. The `_BARE_TO_NAMESPACED` dict-comprehension and `_resolve` automatically pick up the new entries — **no explicit additions needed** to the builder (answer to plan's open question: "Whether `GoldappleStatsBuilder._resolve` already supported short keys generically OR required 3 explicit additions" — answer: **already supported generically via comprehension**).

- **`src/ga_crawler/runners/main_run.py`** (+84 LOC):
  - Added imports: `parser_drift_null_rate_gate` (from `runner.gates`), `GoldappleStatsBuilder` (from `runner.stats`). Reused existing `text` import from `sqlalchemy`.
  - Inserted gate wiring block between goldapple phase failure-handling (line 271) and matcher phase (line 273) — D-817 position.
  - Wiring includes:
    - Pitfall 6 empty-crawl guard: `if goldapple_count > 0:` else `log.warning("phase8_drift_gate_skipped_no_snapshots")`.
    - Single round-trip SQL `SELECT AVG(CASE ...) ... FROM snapshots WHERE run_id=:rid AND retailer='goldapple'` → 2 floats.
    - 3 stats keys written via single `patch_stats` call (Pitfall 6 single-call merge).
    - Pitfall 4 sentinel: `parser_drift_failure_reason` persisted as `""` (not None) when gate passes.
    - On fail: `log.error("phase8_parser_drift_gate_failed", ...)` + `run_writer.fail(run_id, reason)` + Norm06 ledger written + early-return `MainRunResult(status="failed", reason=...)` mirroring existing viled/goldapple failure paths.

### Tests

- **`tests/runner/test_parser_drift_gate.py`** (NEW, 89 LOC, 9 tests):
  - 8 boundary tests per 08-PATTERNS.md template (both-below, exact-threshold, volume-fail, brand-fail, both-exceed-volume-priority, custom-threshold, zero-rates, frozen-dataclass canary)
  - +1 defensive boundary test (`test_brand_custom_threshold_fails_with_brand_reason` — custom threshold path for brand-only failure)
- **`tests/runner/test_smoke_urls_rotation.py`** (NEW, 45 LOC, 4 tests):
  - Structural canary: length 3, PRODUCT_URL_RE match, Givenchy baseline retained, 3 distinct slugs
- **`tests/integration/test_phase8_synthetic_regression.py`** (NEW, 136 LOC, 1 test):
  - Success Criteria #5: 10 goldapple snapshots planted (6 NULL volume_norm + 4 valid) → SQL AVG = 0.6 → gate fails → fail() + patch_stats → runs.status=='failed' + fail_reason=='parser_drift_null_volume_rate' + stats keys all present
- **`tests/runner/__init__.py`** (NEW, empty package init)
- **`tests/unit/test_stats_namespace.py`** (MODIFIED): `test_namespace_has_13_keys` → `test_namespace_has_16_keys` + 3 new parametrize entries
- **`tests/unit/test_viled_stats_builder.py`** (MODIFIED — Rule 1 coupled-canary auto-fix): `test_goldapple_stats_keys_unchanged` flipped 13→16 (PATTERNS.md Pattern 2 only listed `test_stats_namespace.py`, but this duplicate length-canary in a different test file also needed flipping)

### Doc Cascade (4 atomic commits)

- **REQUIREMENTS.md** (commit `39e2094`): 5 PARSE-FIX checkboxes flipped `[ ]` → `[x]` with per-plan completion citations; traceability table row Status `Pending` → `Complete (2026-05-13)`; per-requirement mapping table PARSE-FIX-01..05 all `Complete`; footer counter `5/24 Complete; 19/24 Pending`. **Note:** REQUIREMENTS.md was absent in this worktree's filesystem (deleted in commit `0b713e3` in worktree's ancestor line, never re-created in this branch); re-created from authoritative content with all Phase 8 completion edits applied.
- **PROJECT.md** (commit `fba11f7`): Active section replaced `(None — v1 code-ship complete)` placeholder with v1.1 milestone state showing Phase 8 [x] Complete + Phases 9-11 [ ] Pending; Current State footer references v1.1 + Yandex Cloud kz1 deploy target; last-updated stamp refreshed.
- **ROADMAP.md** (commit `eae11e1`): Milestones section adds 🟢 v1.1 entry; `### 🟢 v1.1 (Active)` section with 4 phase rows; Phase Details block added for Phases 8-11 (Phase 8 full block with Goal/Success-Criteria/Plans list citing W0 pivot for Plan 08-03 per 08-03-SUMMARY.md; Phase 9/10/11 stubs); Progress table extended with 4 v1.1 rows; v1.1 totals line added.
- **STATE.md** (commit `0da1361`): Frontmatter rewrite (`milestone: v1.0` → `v1.1`; progress 7/7/50/50 → 1/4/5/5; `next_phase: 9`); Current Position section rewritten to show Phase 8 COMPLETE 2026-05-13 with 5-plan bullet list + Phases 9-11 PENDING; v1.0 history preserved as sub-paragraph (non-destructive).

## Statistics

| Metric | Value |
|--------|-------|
| Tests in scope (passing GREEN) | **818** (vs 803 v1.0 baseline; +15) |
| 9 new gate unit tests | passing |
| 4 new SMOKE rotation canary tests | passing |
| 1 new synthetic-regression integration test | passing |
| 4 namespace tests modified (16-key flip + 3 new params) | passing |
| 1 coupled-canary auto-fixed (Rule 1) | passing |
| Commits in this plan | **7** (1 RED + 1 GREEN + 1 wiring + 4 doc cascade) |
| LOC delta | +659 / -38 |
| Files touched | 13 (5 created + 8 modified) |
| Phase 8 closure complete | YES (5/5 PARSE-FIX reqs Complete) |
| Synthetic regression (Success Criteria #5) | satisfied — 60% NULL volume → run.status='failed' + reason='parser_drift_null_volume_rate' |

## Commit Hashes

| Task | Commit | Message |
|------|--------|---------|
| Task 1 (RED) | `82db354` | test(08-05): RED — failing tests for parser_drift_null_rate_gate + 3 stats keys + synthetic regression |
| Task 2 (GREEN) | `03ea32a` | feat(08-05): GREEN — parser_drift_null_rate_gate + 3 stats keys + SMOKE rotation |
| Task 3 (wiring) | `83ba7c5` | feat(08-05): wire parser_drift_null_rate_gate into orchestrator pipeline (D-817) |
| Task 4 (cascade #1) | `39e2094` | docs(08): mark PARSE-FIX-01..05 complete in REQUIREMENTS.md |
| Task 4 (cascade #2) | `fba11f7` | docs(08): mark Phase 8 complete in PROJECT.md |
| Task 4 (cascade #3) | `eae11e1` | docs(08): mark Phase 8 complete in ROADMAP.md with 5-plan list |
| Task 4 (cascade #4) | `0da1361` | docs(08): advance STATE pointer to Phase 9 |

## Decisions Made

- **D-815 priority semantics**: implemented exactly as spec — `if v_fail: reason="parser_drift_null_volume_rate" elif b_fail: reason="parser_drift_null_brand_rate" else: reason=None`. Volume wins over brand on dual-failure (most-impactful for match-rate); D-815 priority ordering preserved.
- **Pitfall 4 sentinel**: `parser_drift_failure_reason` written as `""` (empty string) when gate passes, NOT None. `SqliteRunWriter.patch_stats` rejects None values upfront (`raise ValueError`) due to RFC-7396 MergePatch DELETE semantics. Used `""` because schema-discipline requires the key to always exist after gate executes.
- **`finalize` vs `fail`**: PATTERNS.md template called `rw.finalize(run_id, "failed", reason=...)` but `SqliteRunWriter.finalize` has no `reason` kwarg — it only accepts `status`. The proper call is `rw.fail(run_id, reason)` which sets both `status='failed'` AND `fail_reason=reason`. Used `fail` in both the integration test and the orchestrator wiring.
- **W0 pivot for Plan 08-03 ROADMAP entry**: Per 08-03-SUMMARY.md "Deviations": Plan 08-03 pivoted from microdata-walk (PATTERNS.md original strategy) to h1 child-spans (W0-spike-evidence strategy). ROADMAP entry for 08-03 describes the LANDED outcome ("PARSE-FIX-02 goldapple brand+name via h1 child-spans (W0 pivot — landed h1-spans strategy, NOT microdata-walk per shape-table evidence; D-816 invariant softened to log-only canary)").
- **REQUIREMENTS.md re-creation in worktree**: REQUIREMENTS.md was absent from this worktree's filesystem (deleted in commit `0b713e3` in the worktree's ancestor line). Re-created with all Phase 8 completion edits as a single new file (commit `39e2094` — `create mode 100644 .planning/REQUIREMENTS.md`). Content matches the authoritative v1.1 24-req roster from main repo `0477cda` plus the Phase 8 closure edits.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Coupled-canary length assertion in test_viled_stats_builder.py was not anticipated by PATTERNS.md**
- **Found during:** Task 2 GREEN full-suite verification (after I assumed `tests/unit/test_stats_namespace.py` was the only length-canary touching `GOLDAPPLE_STATS_KEYS`)
- **Issue:** `tests/unit/test_viled_stats_builder.py::test_goldapple_stats_keys_unchanged` also asserted `len(GOLDAPPLE_STATS_KEYS) == 13`. PATTERNS.md Pattern 2 only listed `test_stats_namespace.py:14-38` as the coupled canary; this duplicate canary in `test_viled_stats_builder.py:114-118` was overlooked during plan authoring.
- **Fix:** Flipped the assertion to `== 16` in the same Task 2 GREEN commit (`03ea32a`). Comment updated: `"Phase 3 baseline 13 keys preserved + Phase 8 PARSE-FIX-04 +3 (D-815)"`.
- **Files modified:** `tests/unit/test_viled_stats_builder.py`
- **Commit:** `03ea32a`

### Pre-existing Issues (Out of Scope — NOT introduced by Plan 08-05)

**1. `test_cli_deliver.py` subprocess env-leak in worktree env (2 failing tests)**
- **Tests:** `test_deliver_run_missing_token_exits_3`, `test_unicode_stdout_safe_on_windows`
- **Symptom:** subprocess `python -m ga_crawler deliver-run` ran in the worktree directory **picks up a real .env file** (with live `TG_BOT_TOKEN` + `TG_BUSINESS_CHAT_ID`) and **successfully delivered a real Telegram message** to the operator's business chat (`delivery_status: "delivered_business"`, `business_caption_message_id: 26`). The test expected `returncode=3` (missing-token failure) but got `returncode=0` (successful delivery).
- **Baseline confirmation:** Same 2 tests **pass** on main repo HEAD `393be5c` (cwd = `C:\Users\gstorepc\projects\ga_crawler`); they **fail** in this worktree (cwd = `C:\Users\gstorepc\projects\ga_crawler\.claude\worktrees\agent-...`). Difference is the `find_dotenv` discovery resolution under the worktree-style nested-directory layout. The `find_dotenv(usecwd=True)` fix from commit `43dbfd7` (quick-20260514-cli-dotenv-leak) addresses cwd-anchored discovery but does NOT prevent the parent `.env` from being discovered when the subprocess runs in the worktree subdirectory (parent of worktree is the main repo, which contains `.env`).
- **Disposition:** This is a **worktree-specific data egress hazard** uncovered during execution; it is **NOT** caused by Plan 08-05's changes. Per MEMORY.md ("Pre-existing failures annotations are a code smell"): documenting with **written root-cause** here rather than absorbing into a "documented" bucket. Recommend new quick-task for v1.1 hotfix backlog: extend `find_dotenv` logic to **STOP at worktree boundary** (or detect `.claude/worktrees/` in path and force-disable parent-`.env` discovery). Until then, the only safe mitigation is to delete the parent `.env` while running subprocess tests in worktree contexts — operator should be aware before next test session.
- **Action item:** Add v1.1 backlog item — "dotenv-worktree-egress hotfix" — for follow-up quick-task.

## Known Stubs

None — Plan 08-05 introduces no UI / no rendered values / no placeholder text. Gate output flows to `runs.stats` JSON and structlog events only; no surface for stubs to leak through.

## TDD Gate Compliance

Plan 08-05 uses **per-task TDD** (per task `tdd="true"` flag), not plan-level TDD. Atomic commit pair landed for each new component:
- ✅ RED: `82db354` `test(08-05): RED ...` — ImportErrors + AssertionErrors confirm tests fail before implementation
- ✅ GREEN: `03ea32a` `feat(08-05): GREEN ...` — implementation lands; all 78 in-scope tests pass
- ✅ Wiring: `83ba7c5` `feat(08-05): wire ...` — orchestrator integration (no new tests but verified against existing integration suite)

## Open Items for Phase 9

- TEST-HARNESS-01..06 will lock these fixes retroactively via syrupy HTML snapshot harness — Phase 9 will exercise the new gate against captured live PDPs, not just synthetic snapshots.
- Phase 9 will also formalize `python -m ga_crawler capture-fixtures` CLI subcommand (TEST-HARNESS-05) — the ad-hoc `scripts/capture_spike_pdps.py` from W0 Plan 08-01 graduates into the supported CLI surface.
- Worktree dotenv-egress hazard (see Deviations §"Pre-existing Issues") — recommend quick-task before Phase 11 (operator deploy) to avoid recurrence in production cron tick subprocess invocations.

## Self-Check: PASSED

**1. Created files exist:**
- ✓ `tests/runner/__init__.py`
- ✓ `tests/runner/test_parser_drift_gate.py`
- ✓ `tests/runner/test_smoke_urls_rotation.py`
- ✓ `tests/integration/test_phase8_synthetic_regression.py`
- ✓ `.planning/REQUIREMENTS.md`
- ✓ `.planning/phases/08-parser-bug-fixes/08-05-SUMMARY.md` (this file)

**2. Commits exist on worktree branch `worktree-agent-a6a9fef4ec786b5e4`:**
- ✓ `82db354` (RED) — `git log --oneline | grep 82db354` returns hit
- ✓ `03ea32a` (GREEN) — confirmed
- ✓ `83ba7c5` (wiring) — confirmed
- ✓ `39e2094` (REQUIREMENTS.md cascade) — confirmed
- ✓ `fba11f7` (PROJECT.md cascade) — confirmed
- ✓ `eae11e1` (ROADMAP.md cascade) — confirmed
- ✓ `0da1361` (STATE.md cascade) — confirmed

**3. Test count target met:** **818 passing** (target ≥818 per plan acceptance criteria; baseline 803 + 15 net new) — matches plan expectation **exactly**.

**4. Doc cascade complete:**
- ✓ REQUIREMENTS.md PARSE-FIX-01..05 checkboxes flipped (5/5)
- ✓ PROJECT.md v1.1 status reflects Phase 8 complete
- ✓ ROADMAP.md Phase 8 marked complete with 5-plan list, Progress row shows 5/5 Complete
- ✓ STATE.md `next_phase: 9` + Current Position points to Phase 9 as next
