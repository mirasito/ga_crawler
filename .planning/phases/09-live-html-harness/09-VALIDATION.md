---
phase: 9
slug: live-html-harness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-14
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from `09-RESEARCH.md §8 Validation Architecture`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.24 + pytest-mock 3.14 + **syrupy 4.9.x** (NEW dev dep — Wave 0 installs) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` — markers `live`, `integration` already declared (Phase 7); syrupy auto-discovers via `pytest_plugins` |
| **Quick run command** | `uv run pytest -x -m "not live"` |
| **Full suite command** | `uv run pytest` + operator-track `uv run pytest -m live` |
| **Estimated runtime** | ~30s default suite; ~60s full suite; ~10s `-m live` (cassette-replay); 30+s `-m live --refresh-live` (operator-only, hits Camoufox) |

---

## Sampling Rate

- **After every task commit (TDD discipline D-811):** `uv run pytest <touched-test-file> -x` (~5s)
- **After every plan wave merge:** `uv run pytest -x -m "not live"` (~30s; excludes live tests)
- **Before `/gsd-verify-work`:** `uv run pytest` (full suite green) + `uv run pytest -m live` (cassette-replay green) + PII canary green
- **Operator-only post-deploy:** `uv run pytest -m live --refresh-live --snapshot-update` (D-906; the only path that hits Camoufox)
- **Max feedback latency:** ~30 seconds (full default suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-* | 09-01 | W0 | TEST-HARNESS-01 | — | syrupy 4.9.x installed; `HTMLSnapshotExtension(SingleFileSnapshotExtension)` importable; `file_extension="html"`, `WriteMode.TEXT` | unit | `pytest tests/test_snapshot_extension.py -x` | ❌ W0 | ⬜ pending |
| 09-01-* | 09-01 | W0 | TEST-HARNESS-02a | T-09-PII | PII canary rejects fixture containing `cf_clearance=`, `bot\d+:`, UUID hc-ping path | unit | `pytest tests/test_live_fixtures_pii_canary.py::test_dirty_fixture_fails -x` | ❌ W0 | ⬜ pending |
| 09-01-* | 09-01 | W0 | TEST-HARNESS-02b | T-09-SIZE | 50 MB per-fixture + 200 MB aggregate size budget triggers on oversized synthetic file | unit | `pytest tests/test_live_fixtures_pii_canary.py::test_oversize_rejected -x` | ❌ W0 | ⬜ pending |
| 09-01-* | 09-01 | W0 | TEST-HARNESS-02c | — | Sidecar JSON `{date, url, status, html_size, title, camoufox_version}` written + read round-trip | unit | `pytest tests/test_fixture_metadata.py -x` | ❌ W0 | ⬜ pending |
| 09-02-* | 09-02 | W1 | TEST-HARNESS-03a | — | `pytest -m live` cassette-replay parses 3 Phase 8 fixtures; brand+name+volume_raw non-empty (goldapple), brand not in name lowercase, current_price > 0 | live (cassette) | `pytest -m live tests/live/test_parser_drift.py -x` | ❌ W0 | ⬜ pending |
| 09-02-* | 09-02 | W1 | TEST-HARNESS-03b | T-09-DRIFT | `pytest -m live --refresh-live` re-fetches via Camoufox; asserts post-normalize HTML matches syrupy snapshot | live (refresh) | `pytest -m live --refresh-live tests/live/test_parser_drift.py -x` (operator-only) | ❌ W0 | ⬜ pending |
| 09-02-* | 09-02 | W1 | TEST-HARNESS-03c | T-09-SOUND | Missing-snapshot fails CI loudly (negative test: deleted fixture → suite RED, not skip) | unit | `pytest tests/test_snapshot_soundness.py -x` | ❌ W0 | ⬜ pending |
| 09-02-* | 09-02 | W1 | TEST-HARNESS-06a | — | `GoldappleRawProduct.model_validate({...volume_raw: ""...})` raises `ValidationError` (strict) | unit | `pytest tests/storage/test_schemas.py::test_goldapple_strict -x` | ❌ W0 | ⬜ pending |
| 09-02-* | 09-02 | W1 | TEST-HARNESS-06b | — | `ViledRawProduct.model_validate({...volume_raw: None...})` succeeds (relaxed; D-904 evidence: Contre-Jour) | unit | `pytest tests/storage/test_schemas.py::test_viled_relaxed -x` | ❌ W0 | ⬜ pending |
| 09-02-* | 09-02 | W1 | TEST-HARNESS-06c | T-09-SCHEMA | `SqliteSnapshotWriter.append` skips invalid rows + increments `schema.rejected_count` stats key | integration | `pytest tests/integration/test_writer_schema_gate.py -x` | ❌ W0 | ⬜ pending |
| 09-02-* | 09-02 | W1 | TEST-HARNESS-06d | T-09-GATE | `schema_rejected_rate_gate(rate=0.05)` passes; `0.0501` triggers run-fail with reason `schema_validation_rejected_rate` | unit | `pytest tests/runner/test_schema_rejected_gate.py -x` | ❌ W0 | ⬜ pending |
| 09-03-* | 09-03 | W2 (cond.) | TEST-HARNESS-04 | — | Brand-coverage canary asserts ≥1 fixture per active brand seen in last 4 weekly runs (P2 GO only) | integration | `pytest tests/test_brand_coverage_canary.py -x` | ❌ W0 | ⬜ conditional |
| 09-03-* | 09-03 | W2 (cond.) | TEST-HARNESS-05 | — | `python -m ga_crawler capture-fixtures --dry-run` writes correctly-shaped HTML + sidecar JSON (P2 GO only) | integration | `pytest tests/integration/test_capture_fixtures_cli.py -x` | ❌ W0 | ⬜ conditional |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> Task IDs (`09-01-XX`) finalized by `gsd-planner` in step 8; this row template is filled by planner with concrete task numbers.

---

## Wave 0 Requirements

> Wave 0 = the test-file stubs that MUST exist (and fail RED) before any production code is touched. TDD discipline per Phase 8 D-811.

- [ ] `uv add --dev "syrupy>=4.7,<5.0"` — framework install (Wave 0 prerequisite; resolves to 4.9.1 per RESEARCH §10)
- [ ] `tests/test_snapshot_extension.py` — stubs for TH-01 (subclass + file_extension + write_mode sanity)
- [ ] `tests/test_live_fixtures_pii_canary.py` — stubs for TH-02a, TH-02b (canary + size budget)
- [ ] `tests/test_fixture_metadata.py` — stub for TH-02c (sidecar round-trip)
- [ ] `tests/test_snapshot_soundness.py` — stub for TH-03c (missing-snapshot fails CI negative test)
- [ ] `tests/_html_normalize.py` — HTML normalization helper (`cf_clearance` cookie echoes, CSS-class build-hash drift, `__NEXT_DATA__` `buildId` strip) per RESEARCH §7.1 landmine
- [ ] `tests/_fixture_metadata.py` — sidecar JSON writer/reader helper
- [ ] `tests/_snapshot_extension.py` (or inline in `tests/conftest.py` if ≤15 LOC) — `HTMLSnapshotExtension` class location decision per CONTEXT.md "Claude's Discretion"
- [ ] `tests/conftest.py` extension — wrap `goldapple_pdp_html` + `viled_pdp_html` loaders through `_assert_fixture_clean(path)` (D-907 fixture-loader integration)
- [ ] `tests/storage/__init__.py` + `tests/storage/test_schemas.py` — stubs for TH-06a, TH-06b
- [ ] `tests/integration/test_writer_schema_gate.py` — stub for TH-06c (writer + Pydantic integration)
- [ ] `tests/runner/test_schema_rejected_gate.py` — stub for TH-06d (gate threshold semantics)
- [ ] `tests/live/__init__.py` + `tests/live/test_parser_drift.py` — stubs for TH-03a, TH-03b (headline test; replays 3 Phase 8 `_live-2026-05-13-*.html` fixtures)
- [ ] (P2 conditional) `tests/test_brand_coverage_canary.py` — stub for TH-04
- [ ] (P2 conditional) `tests/integration/test_capture_fixtures_cli.py` — stub for TH-05

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Operator runs `pytest -m live --refresh-live` post-suspected-drift; confirms drift output is actionable | TEST-HARNESS-03 (D-905 operator-only opt-in) | Hitting goldapple Camoufox costs ~30+s wallclock + KZ-IP proxy budget; not in CI per D-905 ("NO cron wiring"). Operator decides when to refresh. | (1) `cd /opt/ga_crawler && uv run pytest -m live --refresh-live -x` (2) If diff: read `.planning/research/parser-drift-YYYY-MM-DD.md` (3) If accepted drift: `uv run pytest -m live --refresh-live --snapshot-update` to overwrite fixture + regenerate sidecar JSON |
| Operator reads README §8 «Live HTML harness» and reproduces a refresh cycle | TEST-HARNESS-03, D-905 docs cascade | Documentation read-comprehension; not test-automatable | Follow new README §8 step-by-step (pre-deploy, post-suspected-drift, по запросу). Confirm: command runs, output understandable, drift-md location matches doc |
| Operator validates P2 GO/NO-GO decision boundary (8h elapsed W0+W1) | TEST-HARNESS-04, TEST-HARNESS-05 (D-902) | Time-budget measurement is wall-clock + git commit timestamps; planner records baseline in 09-01 first commit; verify reads `git log` | After 09-02 last GREEN commit, compute `(last_green_09_02 - first_red_09_01) > 8h`? → 09-03 writes defer-to-v1.2 doc cascade. Else → 09-03 implements TH-04+05. CONTEXT-PATCH allowed in either direction per D-902. |
| README §8 «Live HTML harness» RU-primary operator runbook readable + actionable | TEST-HARNESS-03 (D-905 docs) | Doc quality (clarity, completeness, RU/EN polish) is not automation-testable | Read README §8 fresh; confirm: when-to-run / how-to-run / how-to-read-output / how-to-write-back covered. Cross-reference with Phase 7 §3 and Phase 8 deferred README sections for RU-primary tone consistency. |

---

## Threat References (Phase 9 threat-model anchors)

> Used in the `Threat Ref` column above. Defined in PLAN.md `<threat_model>` block (security gate per workflow §5.55).

| Threat ID | Description | Mitigation |
|-----------|-------------|------------|
| T-09-PII | Live HTML fixture leaks anti-bot tokens (`cf_clearance`, `bot\d+:`, hc-ping UUIDs) into committed test data | PII canary at fixture-loader + standalone test (D-907 two-enforcement-point); CLI scrub-on-write if P2 GO |
| T-09-SIZE | Fixture commits bloat repo (single >50 MB file or aggregate >200 MB) | Size canary at fixture-loader (per-file <50 MB, aggregate <200 MB) |
| T-09-SOUND | Drift goes undetected because syrupy silently skips missing snapshot | Default syrupy behavior is to FAIL on missing snapshot (verified RESEARCH §7); explicit negative test `test_snapshot_soundness.py` |
| T-09-DRIFT | `--refresh-live` produces false-positive drift on every operator run (Camoufox HTML carries `cf_clearance` echoes, `__NEXT_DATA__` buildId rotation, CSS build-hash drift) | `tests/_html_normalize.py` strips rotating tokens BEFORE syrupy diff (RESEARCH §7.1 landmine) |
| T-09-SCHEMA | Schema drift (parser emits wrong shape) reaches DB silently | Pydantic `model_validate` at `SqliteSnapshotWriter.append` boundary; per-SKU `ValidationError` increments `schema.rejected_count` stats key |
| T-09-GATE | Schema-rejected-rate gate threshold (5%) is too tight (false-positive run-fail) or too loose (silent passthrough) | RESEARCH §4 — 5% chosen as cascade-position threshold; orthogonal to PARSE-FIX-04 50% absolute null-rate. Threshold revisitable in Phase 9.5 if production evidence demands. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (filled by planner in step 8)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (planner enforces via wave structure D-901)
- [ ] Wave 0 covers all MISSING test-file references (13 stubs above + framework install)
- [ ] No watch-mode flags (per Nyquist gate)
- [ ] Feedback latency < 30s default suite, < 60s full suite
- [ ] `nyquist_compliant: true` set in frontmatter (after planner closes Wave 0 — flipped at execute-phase end)

**Approval:** pending
