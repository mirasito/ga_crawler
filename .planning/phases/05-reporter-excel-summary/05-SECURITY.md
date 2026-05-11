---
phase: 05
phase_name: reporter-excel-summary
audited: 2026-05-12
auditor: gsd-security-auditor
asvs_level: 1
block_on: high
threats_total: 24
threats_closed: 24
threats_open: 0
verdict: SECURED
---

# Phase 5 — Reporter (Excel + Summary) — Security Audit

## Verdict

**SECURED.** All 24 declared threat mitigations verified present in implementation
or accepted with documented disposition. Adversarial-stance grep verification
completed against each declared mitigation pattern at the file:line cited in the
threat register. 0 BLOCKERs, 0 WARNINGs.

No `## Threat Flags` section appeared in any of 05-01-SUMMARY.md..05-06-SUMMARY.md
(executor surfaced no new attack surface during implementation). Nothing to log
as `unregistered_flag`.

## Threat Verification — by Plan

### Plan 05-01 (foundation)

| Threat ID | Category | Disp. | Evidence |
|-----------|----------|-------|----------|
| T-05-config-tamper | Tampering | accept | `pyproject.toml` git-PR review control; no runtime check needed (operator-only edit surface). Disposition documented in 05-01-PLAN.md threat register. |
| T-05-namespace-pollution | Tampering | mitigate | `src/ga_crawler/reporter/stats.py:48-55` — `_resolve()` raises `StatsNamespaceError` for non-`report.*` keys. Tests: `tests/unit/test_report_stats.py:66` (`test_set_viled_key_rejected`), `:72` (`_goldapple_`), `:77` (`_match_`), `:82` (`test_four_way_namespaces_disjoint`). |
| T-05-fixture-data-leak | Info disclosure | accept | `synthetic_report_run` fixture uses tmp_path-scoped SQLite + synthetic SKU rows; no real PII or live-crawled data. Documented accept in 05-01-PLAN.md. |
| T-05-tz-missing | Availability | mitigate | `pyproject.toml:26` — `"tzdata; sys_platform == 'win32'"` conditional dependency ensures `ZoneInfo("Asia/Almaty")` resolves on Windows runtime. `archive.py:30` imports `from zoneinfo import ZoneInfo`. |

### Plan 05-02 (builders)

| Threat ID | Category | Disp. | Evidence |
|-----------|----------|-------|----------|
| T-05-injection (Excel formula) | Injection | mitigate | `src/ga_crawler/reporter/excel_builder.py:66` `_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r")`; `:69-81` `_sanitize_cell` prepends `'`; `:84-92` `_sanitize_dataframe` applies on object-dtype cols; called on each sheet at `:216, :226, :231`. Tests: `tests/unit/test_excel_builder.py:56-64` parametrize 6 trigger chars; `:292` `test_formula_injection_persists_through_workbook` openpyxl round-trip. |
| T-05-sql-injection | Injection | mitigate | `src/ga_crawler/reporter/queries.py` — all SQL is `text(":rid")` / `text(":n")` with `params={"rid": run_id}`. Grep for f-strings in `queries.py` returns 0 matches. `_cmd_report` argparse `type=int` (`cli.py:344`) provides defense-in-depth. |
| T-05-pandas-default-engine | Tampering | mitigate | `src/ga_crawler/reporter/excel_builder.py:200` — `pd.ExcelWriter(buffer, engine="xlsxwriter")` explicit. Pitfall 1 enforced. |
| T-05-formula-injection-bypass-via-numeric-coerce | Injection | accept | `excel_builder.py:90` — `_sanitize_dataframe` only iterates `dtype == object` columns; numeric cols pass through unchanged. Defense-in-depth: payload would have to enter via non-string column originally. Documented accept in 05-02-PLAN.md. |

### Plan 05-03 (archive)

| Threat ID | Category | Disp. | Evidence |
|-----------|----------|-------|----------|
| T-05-disk-full | Availability | mitigate | `src/ga_crawler/reporter/archive.py:136-140` — `tmp_path.write_bytes()` then `os.replace(tmp_path, target_path)`. `OSError` propagates uncaught to outer `main_run` try/except (no swallow in archive.py — grep `try:|except` returns 0 in module). |
| T-05-partial-write | Integrity | mitigate | `excel_builder.py:198-242` builds full xlsx zip into `io.BytesIO` before returning bytes; `archive.py:136-140` writes those complete bytes to `.tmp` sibling and atomic-renames. Test `tests/unit/test_archive_atomic_write.py:48` `test_write_atomic_no_orphan_tmp_on_success` asserts the tmp sibling is gone after a successful rename. `:114` `test_gitignore_excludes_xlsx_tmp` asserts `reports/*.xlsx.tmp` is in `.gitignore`. |
| T-05-path-traversal | Tampering | mitigate (escalated in 05-04) | Plan 05-03 declared accept-with-escalation; Plan 05-04 added the runtime guard. See Plan 05-04 row below. |
| T-05-overwrite-of-historical-report | Repudiation | accept | `archive.py:127` — `log.info("report_overwritten", path=..., previous_size_bytes=...)` audit event when target exists. DB matches/runs.stats rows are immutable source-of-truth; xlsx is regenerable artifact. Documented accept. |
| T-05-tz-spoofing | Tampering | accept | `tz_name` arg is operator-edited via `pyproject.toml` `[tool.ga_crawler.report].timezone`; no external input plane. Documented accept. |

### Plan 05-04 (orchestrator)

| Threat ID | Category | Disp. | Evidence |
|-----------|----------|-------|----------|
| T-05-status-bypass | AuthZ | mitigate | `src/ga_crawler/runners/reporter_run.py:37,147-151` — REUSES `matcher.strict_key.read_run_status` (no re-implementation). Tests: `tests/integration/test_reporter_run.py:49` (`test_d507_skip_on_failed_run`), `:86` (`_running_run`), `:108` (`_missing_run`). Skip-path patches all 7 D-514 keys with sentinel values (assertions at `:68-79`). |
| T-05-path-traversal | Tampering | mitigate | `reporter_run.py:189-199` — `target_path = (repo_root / output_dir / filename).resolve()`; `target_path.relative_to(repo_root_resolved)` raises `ValueError` if escaped. The only `try/except` in `run_reporter_phase` body is this ValueError re-raise wrapper at `:193-199`. |
| T-05-patch_stats-race | Race condition | mitigate | `reporter_run.py:101` (skip path) and `:227` (success path) — exactly ONE `run_writer.patch_stats(run_id, dict(builder.delta))` per code path; uses SQL `json_patch` (atomic per Pitfall 6). Tests: `tests/integration/test_reporter_run.py:265` `test_single_patch_stats_call` asserts `call_count == 1` on success; `:283` `test_single_patch_stats_call_on_skip_path` asserts same on skip. |
| T-05-skip-path-stats-missing-key | Tampering | mitigate | `reporter_run.py:92-98` — `_skip_path` sets ALL 7 D-514 keys (`xlsx_path`, `xlsx_size_bytes`, `summary_text`, `sheet_row_counts`, `skipped_reason`, `size_guard_passed`, `generated_at`) with sentinel values. Test `tests/integration/test_reporter_run.py:70-79` per-key iteration asserts every key is present after skip. |
| T-05-disk-full / T-05-partial-write | Availability/Integrity | mitigate | See Plan 05-03 evidence above. Orchestrator does not wrap archive calls in try/except — exceptions bubble to `main_run` DATA-05 owner. |

### Plan 05-05 (CLI)

| Threat ID | Category | Disp. | Evidence |
|-----------|----------|-------|----------|
| T-05-cli-injection-via-run-id | Injection | mitigate | `src/ga_crawler/cli.py:342-347` — `report.add_argument("--run-id", type=int, required=True, ...)`. Test `tests/integration/test_cli_report_subcommand.py:177` `test_report_run_non_int_run_id_rejected` asserts argparse exits 2 on non-int input. |
| T-05-cli-path-traversal-via-output-dir | Tampering | mitigate | `cli.py:187-190` builds `cfg = dataclasses.replace(cfg, output_dir=args.output_dir)`; cfg flows into `run_reporter_phase` which applies the `target_path.relative_to(repo_root)` containment guard at `reporter_run.py:192-199`. The CLI override therefore inherits the same defense-in-depth check. |
| T-05-data05-bypass-via-reporter-exception | Integrity | mitigate | `run_reporter_phase` body contains 0 try/except blocks outside the path-traversal `ValueError` wrapper (grep `try:\|except ` in `reporter_run.py` returns 2 lines, both within the path-containment guard). Outer `main_run.py:399-417` catches uncaught exceptions → `run_writer.fail`. Tests: `tests/integration/test_main_run_with_reporter.py:368` `test_data05_reporter_exception_finalizes` and `tests/integration/test_reporter_run.py:459` `test_uncaught_exception_propagates`. |
| T-05-state-leak-cli-runs | Info disclosure | accept | `_cmd_report` stdout JSON contains: status, run_id, xlsx_path, xlsx_size_bytes, summary_text, size_guard_passed, reason, stats_delta_keys. `summary_text` = same emoji caption sent to Telegram (aggregate KPIs + top-3 brand names; no per-customer or auth data). Documented accept. |
| T-05-mainrunresult-field-drift | Tampering | mitigate | `MainRunResult` at `src/ga_crawler/runners/main_run.py:72-77` — 4 scalar reporter fields (`xlsx_path`, `xlsx_size_bytes`, `summary_text`, `size_guard_passed`) with safe defaults. Test `tests/integration/test_main_run_with_reporter.py:429` `test_main_run_result_has_reporter_fields` asserts field presence and default types. |

### Plan 05-06 (doc cascade — no code changes)

| Threat ID | Category | Disp. | Evidence |
|-----------|----------|-------|----------|
| T-05-doc-drift | Tampering | accept | Doc cascade IS the mitigation; reviewer (operator git-PR) is the control. Documented accept. |
| T-05-stale-traceability | Repudiation | mitigate | `.planning/REQUIREMENTS.md:168-173` — REPORT-01..06 Traceability rows all flipped `Pending → Done` with plan citations (Plan 05-02, 05-03, 05-04, 05-05). |
| T-05-missed-cascade-to-phase6 | Tampering | mitigate | `.planning/STATE.md` Accumulated Key Decisions: row L180 (D-514 4-way namespace disjoint), L183 (D-514 reporter source-of-truth for Telegram caption), L184 (D-515 size-guard delivery cascade to ops-chat — NON-NEGOTIABLE invariant), L185 (D-405 reporter cites match.rate verbatim). Each row carries explicit Phase 6 cascade text that Phase 6 planner must cite. |

## Unregistered Flags

None. `## Threat Flags` section was not present in any of the 6 SUMMARY.md files
for Phase 5; executor surfaced no new attack surface during implementation.

## Accepted Risks Log

The following dispositions are accepted (not mitigated in code) and acknowledged
as residual phase-5 risk:

1. **T-05-config-tamper** — `pyproject.toml` `[tool.ga_crawler.report]` is editable only via git PR; reviewer is the sole control. No runtime defense.
2. **T-05-fixture-data-leak** — `synthetic_report_run` fixture data is fabricated and tmp_path-scoped; not a production data leak vector.
3. **T-05-formula-injection-bypass-via-numeric-coerce** — `_sanitize_dataframe` only touches object-dtype columns. A future schema change that stored a hostile string in a numeric column would bypass the sanitizer. Re-evaluate when new sheet columns are added.
4. **T-05-overwrite-of-historical-report** — Same-ISO-week second run overwrites xlsx without backup. DB row history is preserved (immutable source-of-truth); xlsx is regenerable via `report-run --run-id N`. `report_overwritten` structlog event provides audit trail.
5. **T-05-tz-spoofing** — `config.timezone` is operator-edited via pyproject.toml; not a runtime input.
6. **T-05-state-leak-cli-runs** — `_cmd_report` stdout summary_text contains aggregate KPIs and top-3 product names (same content as Telegram caption); no PII or auth tokens.
7. **T-05-doc-drift** — Plan 05-06 doc cascade IS the mitigation; reviewer is the control.

## Observations (informational, non-blocking)

- WR-01 from `05-REVIEW.md`: `MainRunResult.size_guard_passed=True` default for no-reporter paths is semantically "no xlsx → no violation possible." Phase 6 DELIVER-03 MUST gate-check `xlsx_path is not None and len(xlsx_path) > 0` BEFORE trusting the default — this is already persisted in STATE.md L184 cascade row as a NON-NEGOTIABLE invariant. Not a Phase 5 BLOCKER.
- WR-02 from `05-REVIEW.md`: `check_size_guard`'s docstring claims "never raises" but `Path.stat()` could raise `OSError` on edge filesystems. The orchestrator does not wrap this call — an `OSError` would propagate to `main_run`'s DATA-05 handler, which IS the documented behavior (uncaught reporter exception → `run_writer.fail`). Semantically consistent with T-05-data05-bypass-via-reporter-exception mitigation. Not a Phase 5 BLOCKER.

## Audit Trail

- Implementation files read-only — no edits performed.
- All threat-mitigation grep matches recorded with file:line above.
- No `## Threat Flags` blocks emitted by executor → no unregistered surface to log.
- 0 BLOCKER, 0 WARNING.

Phase 5 ships SECURED.
