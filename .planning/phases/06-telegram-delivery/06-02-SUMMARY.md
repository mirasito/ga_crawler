---
phase: 06-telegram-delivery
plan: 02
subsystem: delivery
tags: [wave-1, foundations, pure-python, config, stats, message-builder, tdd, html-escape, almaty-tz]
requires:
  - .planning/phases/06-telegram-delivery/06-01-SUMMARY.md     # Wave 0 deliverable (aiogram dep, pyproject namespace, .env.example, conftest fixtures, 10 stubs)
  - .planning/phases/06-telegram-delivery/06-CONTEXT.md        # D-607 + D-609 + D-610 + D-611 + D-613 + D-614
  - .planning/phases/06-telegram-delivery/06-RESEARCH.md       # caveat #3 (stdlib html.escape) + caveat #4 (load_dotenv) + Pitfall A (escape) + Pitfall E (Almaty tz)
  - .planning/phases/06-telegram-delivery/06-PATTERNS.md       # line-mirror anchors for stats/config/message_builder
provides:
  - src/ga_crawler/delivery/__init__.py                        # package marker (mirror reporter/__init__.py)
  - src/ga_crawler/delivery/stats.py::DELIVER_STATS_KEYS       # D-607 8-tuple, source-locked
  - src/ga_crawler/delivery/stats.py::DeliverStatsBuilder      # mirror ReportStatsBuilder
  - src/ga_crawler/delivery/config.py::DeliverConfig           # D-614 6 keys, frozen
  - src/ga_crawler/delivery/config.py::DeliverEnvConfig        # D-611 asymmetric (TG_BOT_TOKEN + 2 chat_ids)
  - src/ga_crawler/delivery/message_builder.py::build_ops_alert # D-610 single template
  - src/ga_crawler/delivery/message_builder.py::business_caption # D-514 caption-fit helper
  - src/ga_crawler/delivery/message_builder.py::REASON_SHORT   # 8 reason-keys mapping
  - tests/fixtures/delivery/ops-alert-templates.txt            # 5 real golden expected outputs (no placeholders)
affects:
  - tests/test_delivery_stats.py                                # stub replaced (14 GREEN)
  - tests/test_delivery_config.py                               # stub replaced (12 GREEN)
  - tests/test_message_builder.py                               # stub replaced (22 GREEN)
  - tests/unit/test_stats_namespace_five_way.py                 # stub replaced (2 GREEN)
  - tests/unit/test_phase06_wave0_stub_inventory.py             # adjusted: 6 remaining stubs (was 10); +regression test
  - tests/fixtures/delivery/ops-alert-templates.txt             # placeholders → real outputs
tech-stack:
  added: []                                                     # zero new deps — pure-Python wave
  patterns:
    - "RED-then-GREEN per task (TDD plan-level cycle, 3 tasks × 2 commits = 6 commits)"
    - "Pure-function module set (no aiogram imports) — structural canary asserts this"
    - "Source-lock + golden-file canary for ops-alert template (5 scenarios)"
    - "Asia/Almaty via %z numeric offset (W1 fix — cross-platform-stable; %Z named zone rejected)"
    - "Empty-string env vars normalised to None via 'or None' idiom (D-611 asymmetric)"
key-files:
  created:
    - src/ga_crawler/delivery/__init__.py
    - src/ga_crawler/delivery/stats.py
    - src/ga_crawler/delivery/config.py
    - src/ga_crawler/delivery/message_builder.py
  modified:
    - tests/test_delivery_stats.py
    - tests/test_delivery_config.py
    - tests/test_message_builder.py
    - tests/unit/test_stats_namespace_five_way.py
    - tests/unit/test_phase06_wave0_stub_inventory.py
    - tests/fixtures/delivery/ops-alert-templates.txt
decisions:
  - W1 — Asia/Almaty formatted via strftime("%Y-%m-%d %H:%M %z") (numeric +0500 offset); %Z rejected as platform-dependent
  - delivery/config.py source text contains literally zero references to "load_dotenv" (structural canary, RESEARCH caveat #4)
  - DeliverStatsBuilder reuses StatsNamespaceError from runner.stats (NO new error class) — single-error-class invariant preserved across 5 namespaces
  - Wave-0 stub-inventory canary updated to track the 6 still-stubbed files (Plans 06-03/04/05); WAVE1_CLOSURES regression test pins the 4 Wave-1 closures
metrics:
  duration: "~20 min"
  completed: "2026-05-12T13:57:57Z"
  tests_pre: 626        # Wave 0 baseline (626 passed, 11 skipped)
  tests_post: 677       # 626 + 51 net (50 new GREEN + 1 added regression test) — 4 skips → green converted
  tests_skipped_post: 7 # 11 − 4 Wave-1 closures = 7
  files_created: 4
  files_modified: 6
---

# Phase 6 Plan 02: Wave 1 Foundations Summary

One-liner: Three pure-Python delivery modules (`stats.py` + `config.py` + `message_builder.py`) shipped via 3 TDD red→green cycles — D-607 8-key namespace, D-611 asymmetric ENV handling, and D-610 ops-alert template with `+0500` Almaty offset all turn 4 Wave-0 stubs GREEN (50 new tests; full suite 677 passed / 7 skipped, zero regressions in Phases 2-5).

## What Shipped

Wave 1 is the **pure-Python foundation** of the delivery package. No aiogram imports, no async, no network — three small modules that the rest of Phase 6 will compose. Every behavior is unit-testable without a mock Bot, by design (the Wave 2 telegram_client.py wave will own the aiogram surface).

Each task followed plan-level TDD: a `test(...)` commit added failing tests first, then a `feat(...)` commit added the minimal implementation to turn them GREEN.

### Task 1 — `delivery/stats.py` + 5-way namespace canary (RED `73621be` → GREEN `f86959a`)

- Created `src/ga_crawler/delivery/__init__.py` (single-line package docstring, mirror of `reporter/__init__.py`).
- Created `src/ga_crawler/delivery/stats.py` exporting `DELIVER_STATS_KEYS` (the 8-tuple per D-607, source-locked in canonical order) and `DeliverStatsBuilder` (line-mirror of `ReportStatsBuilder` — same `_resolve` / `set` / `inc` / `get` / `keys` / `__len__` API).
- `DeliverStatsBuilder` reuses `StatsNamespaceError` from `runner.stats` (no new error class — Pitfall 6 invariant: one error class across all 5 namespaces).
- Replaced `tests/test_delivery_stats.py` stub with 14 GREEN tests covering keys count / prefix / immutable tuple / canonical order / bare-and-namespaced set / idempotent overwrite / unknown key rejection / cross-namespace rejection (viled.* + report.*) / inc accumulation / len-matches-delta-keys / unknown-key default / sentinel values (-1 for int, "" for str).
- Replaced `tests/unit/test_stats_namespace_five_way.py` stub with 2 GREEN tests: 5-way disjoint pairwise check (10 pairs across {viled, goldapple, match, report, deliver}) + `deliver.` prefix all-keys check. This is the Phase 5 4-way canary extended to 5 — the architectural invariant Phase 6 freezes for the rest of the project.

### Task 2 — `delivery/config.py` (RED `99d3a5c` → GREEN `1389d21`)

- Created `src/ga_crawler/delivery/config.py` with two frozen dataclasses:
  - `DeliverConfig` — 6 keys per D-614 (`retry_max_attempts=3`, `retry_backoff_min_seconds=5`, `retry_backoff_max_seconds=45`, `ops_message_truncate_chars=3500`, `business_caption_max_chars=1024`, `parse_mode="HTML"`). `from_pyproject(path)` mirrors `ReportConfig.from_pyproject`: opens the toml, walks `tool.ga_crawler.deliver`, casts each value through its target type, and falls back to dataclass defaults on missing file or missing nested namespace.
  - `DeliverEnvConfig` — 3 `Optional[str]` fields (`bot_token`, `business_chat_id`, `ops_chat_id`). `from_env()` is a pure `os.getenv` read; empty strings are normalised to `None` via the `or None` idiom so D-611's asymmetric handling can rely on a clean `is None` check.
- **RESEARCH caveat #4 enforcement:** the source text of `delivery/config.py` contains literally zero references to `load_dotenv` (no import, no call, not even in docstrings). The structural canary `test_from_env_does_not_call_load_dotenv` reads the file and asserts the substring is absent — this guarantees that test runs never accidentally pick up a real on-disk `.env`. Only the future `cli.py::_cmd_deliver` entrypoint will own the dotenv-loading side effect (Plan 06-04).
- Replaced `tests/test_delivery_config.py` stub with 12 GREEN tests: 6 covering `DeliverConfig` (defaults / against repo pyproject / missing file / one-key override / missing namespace / `parse_mode == "HTML"` regression) and 6 covering `DeliverEnvConfig` (unset → None / set → value / all-three / structural canary / empty-string-is-None / both dataclasses frozen).

### Task 3 — `delivery/message_builder.py` + 5-scenario golden file (RED `b8962c6` → GREEN `e36383e`)

- Created `src/ga_crawler/delivery/message_builder.py` exporting:
  - `REASON_SHORT` — 8-key dict mapping D-610 gate-failure reasons (e.g. `xlsx_oversize`) to human-readable phrases (`"xlsx too large for Telegram"`). Unknown keys fall back to the raw key string so the alert never breaks on a new gate reason.
  - `_format_almaty(dt)` — pure formatter for `Asia/Almaty` (Pitfall E). Naive datetimes are treated as UTC. **W1 fix:** uses `strftime("%Y-%m-%d %H:%M %z")` with **lowercase `%z`** (numeric offset → `+0500`) instead of uppercase `%Z` (named-zone abbreviation), which would be platform-dependent on Windows and would drift the golden file between OSes.
  - `_esc(value)` — `html.escape(value, quote=False)` from stdlib (RESEARCH caveat #3 — stdlib over `aiogram.html`).
  - `build_ops_alert(...)` — the D-610 single ops-alert template. All dynamic str fields pass through `_esc` (Pitfall A); the `xlsx size:` line is conditional on `size_guard_failed`; the `<i>Error:</i> <pre>...</pre>` block is conditional on a truthy `error_short` and truncates to ≤ 3500 chars (D-614 `ops_message_truncate_chars`); the output ends with the manual-recovery hint.
  - `business_caption(summary_text, max_chars=1024)` — pure D-514-cascade helper for the future `delivery_run`. Returns `(summary_text, False)` when it fits, or `("См. сводку выше", True)` when the caller must split.
- Populated `tests/fixtures/delivery/ops-alert-templates.txt` by **running the module** against 5 scenarios (`upstream_status_failed`, `xlsx_oversize`, `empty_summary_text`, `no_xlsx_in_stats`, `delivery_exception`) with fixed inputs (`run_id=42`, `started_at_utc=2026-05-11 17:00 UTC` → `2026-05-11 22:00 +0500` Almaty, `viled=120`, `goldapple=540`, `size_limit_mb=45`) and pasting each verbatim output between `=== {scenario} ===` markers. The golden file now contains zero `PLACEHOLDER` strings and zero stub-style angle-bracketed markers; every section is byte-identical to what the live module produces.
- Replaced `tests/test_message_builder.py` stub with 22 GREEN tests: 18 behavior tests (first-line shape / html-escape on error + gate_failed_check / Almaty `+0500` substring / naive-datetime UTC fallback / 3500-char truncation / size_guard line on/off / error block on/off / manual-recovery footer / 8-key `REASON_SHORT` superset / unknown-key fallback / business_caption pass-through / split / exact-max boundary / no-placeholder canary) + 5 parametrized golden-file scenarios + 1 file-shape canary.

### Wave-0 canary adjustment

The Plan 06-01 canary `test_all_ten_stub_files_contain_skip_marker` asserted every Wave-0 stub still carried a `pytest.mark.skip`. Plan 06-02 explicitly turned 4 of those 10 GREEN, so the canary started firing as soon as Task 1's GREEN commit landed. Per Rule 3 (auto-fix blocking issues), the canary was updated:

- `STUB_FILES` narrowed to the 6 stubs still owned by Plans 06-03 / 06-04 / 06-05.
- `test_remaining_stub_count_after_wave1` renamed and asserts `len(STUB_FILES) == 6`.
- A new regression test `test_wave1_closures_no_longer_have_skip_marker` walks the 4 Wave-1-closed files and asserts none of them still contain `pytest.mark.skip`. The canary now both protects future plans (un-replaced stubs stay flagged) **and** locks in the Wave-1 closure (re-adding a skip marker would fail).

## Tests Added

| Test file | Before | After Wave 1 | Delta |
|-----------|--------|--------------|-------|
| `tests/test_delivery_stats.py` | 1 skip stub | 14 GREEN | +14, −1 skip |
| `tests/test_delivery_config.py` | 1 skip stub | 12 GREEN | +12, −1 skip |
| `tests/test_message_builder.py` | 1 skip stub | 22 GREEN | +22, −1 skip |
| `tests/unit/test_stats_namespace_five_way.py` | 1 skip stub | 2 GREEN | +2, −1 skip |
| `tests/unit/test_phase06_wave0_stub_inventory.py` | 4 GREEN | 5 GREEN | +1 GREEN regression test |

**Suite totals:** 677 passed (up from 626), 7 skipped (down from 11). Delta = +51 passed, −4 skipped — exactly the Wave-1 expectation. Zero failing tests, zero regressions in Phase 2-5 unit + integration suites.

## Verification Canaries

| Canary | Command | Result |
|--------|---------|--------|
| Wave-1 module suite green | `uv run pytest -x tests/test_delivery_stats.py tests/test_delivery_config.py tests/test_message_builder.py tests/unit/test_stats_namespace_five_way.py` | 50 passed |
| Full suite green | `uv run pytest --no-header` | 677 passed / 7 skipped / 0 failed |
| `DELIVER_STATS_KEYS` has 8 prefixed entries | `python -c "from ga_crawler.delivery.stats import DELIVER_STATS_KEYS; ..."` | OK |
| `StatsNamespaceError` raised on unknown key | `python -c "import pytest; ...pytest.raises(StatsNamespaceError, b.set, 'xxx', 'y')"` | OK |
| `DeliverConfig.from_pyproject` matches defaults | `python -c "from ga_crawler.delivery.config import DeliverConfig; ..."` | OK |
| No `load_dotenv` in `delivery/config.py` | `python -c "'load_dotenv' not in src"` | OK |
| `REASON_SHORT` has ≥ 8 entries | `python -c "from ... import REASON_SHORT; assert len(REASON_SHORT) >= 8"` | 8 |
| Golden file: ≥ 5 sections, no placeholders, contains `+0500` | `python -c "t = read('ops-alert-templates.txt'); ..."` | OK |
| **No-aiogram-import canary** (pure-Python invariant) | `python -c "'import aiogram' not in (config.py + stats.py + message_builder.py); 'from aiogram' not in ..."` | OK — pure-Python preserved |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Wave-0 `test_all_ten_stub_files_contain_skip_marker` canary tripped after Task 1**
- **Found during:** Task 1 full-suite check (after the GREEN commit `f86959a`).
- **Issue:** Plan 06-01 shipped a strict canary asserting all 10 Wave-0 stub files still carry a `pytest.mark.skip` marker. Plan 06-02's explicit goal is to remove skip-markers from 4 of those 10 (the Wave-1 stubs), so the canary fires as soon as the first stub turns GREEN.
- **Fix:** Updated `tests/unit/test_phase06_wave0_stub_inventory.py`: narrowed `STUB_FILES` to the 6 stubs still owned by Plans 06-03 / 06-04 / 06-05; renamed the assertions accordingly; added `WAVE1_CLOSURES` regression test asserting the 4 Wave-1-closed files do NOT contain `pytest.mark.skip` any more. The canary still protects future plans (un-replaced stubs continue to trigger it) AND now pins the Wave-1 closure (re-introducing a skip marker would fail this test).
- **Files modified:** `tests/unit/test_phase06_wave0_stub_inventory.py`
- **Commit:** rolled into `e36383e` (GREEN Task 3) since the inventory canary is structurally coupled to the Wave-1 stub closures.

**2. [Rule 1 — Pre-empted] Docstring referencing `load_dotenv` literal tripped my own structural canary**
- **Found during:** Task 2 GREEN gate (first run).
- **Issue:** I wrote the first draft of `delivery/config.py` with a docstring that *described* RESEARCH caveat #4 by literally naming `load_dotenv` (the very token the canary forbids). Test `test_from_env_does_not_call_load_dotenv` correctly failed: "load_dotenv must NOT appear in delivery/config.py".
- **Fix:** Reworded both class-level docstrings to describe the caveat as "dotenv-loading is the CLI entrypoint's job" without naming the symbol; the `from_env` method docstring also updated. No functional change — the canary now passes because the source text is clean. This is arguably the canary working as designed (it catches even *mentions* of the forbidden API, since a future contributor might grep for it).
- **Files modified:** `src/ga_crawler/delivery/config.py` (3 docstring edits)
- **Commit:** fixed in-place before the GREEN commit `1389d21` was created (no separate commit).

### Deferred Items

None. Wave 1 ships every artifact promised in the plan's `<output>` block. Two structural details of note that are **not** deferrals, just scope notes:

- The Plan 06-02 `<read_first>` section for Task 1 mentions `tests/unit/test_phase06_smoke.py` "created in Task 1 as part of test suite". That file was not actually planned as a task output — the wording is a forward-looking sketch from the plan's verify-block comment, not a deliverable. None of the three tasks reference it; the 50 GREEN tests sit in their plan-named files. No action needed.
- `business_caption` was implemented even though it is not strictly required until Plan 06-04. The plan explicitly directed it ("pure helper for Plan 06-04 delivery_run"), so it ships now as part of the message_builder module and gets 3 GREEN tests. No premature complexity — it is 4 lines and three tests, and Plan 06-04 will need it.

## Auth Gates

None encountered. Plan 06-02 is pure-Python with zero network or credential touch — the `.env.example` from Wave 0 stays unused. Wave 2 (telegram_client.py async network) will be the first wave that *could* hit an auth gate, but only at integration-test time; unit tests will keep using `mock_aiogram_bot`.

## Decisions Made

- **`%z` numeric offset over `%Z` named-zone abbreviation** (W1 fix in `_format_almaty`): Windows / macOS / Linux render `%Z` differently (e.g. "Asia/Almaty" vs "+05" vs ""), which would drift the golden file across platforms. `%z` is uniformly numeric (`+0500`) on every platform. The 5 golden-file scenarios use `+0500` and the verify canary `assert '+0500' in t` pins this format.
- **Structural canary over runtime check for `load_dotenv`-absence**: the cleaner alternative would have been to wrap `os.getenv` in a guard that fails if `dotenv` has been imported. That would require runtime introspection and add brittle test coupling. A source-text grep is bulletproof, fast, and self-documenting — and it doubles as a code-review hint for anyone editing `delivery/config.py`.
- **Reuse `StatsNamespaceError` from `runner.stats`** (rather than defining a new `DeliveryStatsNamespaceError`): all 5 builders (viled/goldapple/match/report/deliver) share the single error class, so a generic `except StatsNamespaceError:` clause in any future code remains correct as new namespaces are added.
- **One `_esc(value: str)` helper instead of inline `html.escape(...)` calls**: the local helper makes Pitfall A textually obvious (every templated field reads `_esc(value)` rather than the longer stdlib invocation) and centralises the `quote=False` choice for HTML mode in a single place.
- **`business_caption` helper colocated with `build_ops_alert`** (not a separate module): both are pure transforms on Telegram-bound strings, both consume the D-514 source-of-truth `summary_text`, and both are < 10 LOC. Keeping them together preserves the "one delivery module per concern" invariant (`stats`/`config`/`message_builder` × `gate`/`telegram_client` × `runners/delivery_run`).

## Threat Model Surface

Plan 06-02's threat register lists T-6-01 / T-6-03 / T-6-09 / T-6-10 with `mitigate` dispositions:

| Threat | Mitigation shipped | Test canary |
|--------|--------------------|-------------|
| **T-6-01** (TG_BOT_TOKEN disclosure) | `DeliverEnvConfig` is `frozen=True`; no `__repr__` override (uses dataclass default which echoes field values — accepted risk for now per the register; Plan 06-04 routes structlog WITHOUT logging the token directly). | `test_dataclasses_are_frozen` |
| **T-6-03** (`error_short` HTML injection) | `_esc = html.escape(..., quote=False)` applied to every dynamic str field in `build_ops_alert`. | `test_html_escape_applied_to_error` (`<script>alert(1)</script>` → `&lt;script&gt;alert(1)&lt;/script&gt;`) + `test_html_escape_applied_to_run_status` (`x<y&z` → `x&lt;y&amp;z`) |
| **T-6-09** (naive-datetime tz drift) | `_format_almaty` attaches `timezone.utc` to naive datetimes BEFORE `astimezone(ZoneInfo("Asia/Almaty"))`. | `test_almaty_naive_datetime_treated_as_utc` (asserts naive `datetime(2026,5,11,17,0)` produces same string as tz-aware equivalent) |
| **T-6-10** (pathological 1 MB error_short DoS) | `truncate_chars=3500` default + slice operation `error_short[:truncate_chars]`. Telegram hard limit is 4096 chars; the remaining ~500 chars cover template HTML overhead. | `test_error_truncated_to_3500_chars` (4000-char input → exactly 3500 in `<pre>` payload) |

## Wave 1 → Wave 2 Handoff

Wave 2 (Plan 06-03 `gate.py` + `telegram_client.py`) inherits:

- A `DeliverConfig` / `DeliverEnvConfig` pair ready to be loaded once at start of `delivery_run`. The config object's `retry_max_attempts` / `retry_backoff_min_seconds` / `retry_backoff_max_seconds` fields are the inputs Wave 2's tenacity wrapper consumes.
- A `DELIVER_STATS_KEYS` 8-tuple to write through. Wave 2's `telegram_client.send_*` methods will populate `deliver.business_caption_message_id` / `deliver.business_document_message_id` / `deliver.ops_message_id` from the `aiogram` Message objects.
- A `build_ops_alert(...)` callable for the gate-fail branch and a `business_caption(...)` callable for the gate-pass branch — both pure and tested. Wave 2's `gate.py::evaluate_gate` produces the inputs that flow into `build_ops_alert`.
- A `REASON_SHORT` dict that already contains `missing_env_TG_BUSINESS_CHAT_ID` and `delivery_exception` — both reasons that originate in Wave 3 orchestrator (`delivery_run.py`) rather than the gate. The mapping is forward-compatible.
- A golden file `tests/fixtures/delivery/ops-alert-templates.txt` that pins the template shape for the rest of Phase 6. Wave 2 / 3 changes that alter the alert wording will trigger the 5 parametrized scenarios — drift detection by construction.
- Wave-0 canary `test_all_remaining_stub_files_contain_skip_marker` now lists 6 stubs (Plans 06-03/04/05). Wave 2 will turn `test_telegram_client.py` and `test_gate.py` GREEN, dropping the count to 4 and adding two more entries to `WAVE1_CLOSURES` (or whatever it's renamed to at that point).

## Self-Check: PASSED

Files verified to exist on disk:

- `src/ga_crawler/delivery/__init__.py` — FOUND
- `src/ga_crawler/delivery/stats.py` — FOUND (DELIVER_STATS_KEYS 8-tuple, DeliverStatsBuilder)
- `src/ga_crawler/delivery/config.py` — FOUND (DeliverConfig, DeliverEnvConfig)
- `src/ga_crawler/delivery/message_builder.py` — FOUND (build_ops_alert, business_caption, REASON_SHORT, _format_almaty)
- `tests/test_delivery_stats.py` — FOUND (14 GREEN tests, no skip markers)
- `tests/test_delivery_config.py` — FOUND (12 GREEN tests, no skip markers)
- `tests/test_message_builder.py` — FOUND (22 GREEN tests, no skip markers)
- `tests/unit/test_stats_namespace_five_way.py` — FOUND (2 GREEN tests, no skip markers)
- `tests/fixtures/delivery/ops-alert-templates.txt` — FOUND (5 sections with real outputs, no placeholders, `+0500` offset)

Commits verified in `git log --oneline`:

- `73621be` (RED Task 1) — failing tests for `delivery/stats.py` + 5-way namespace canary
- `f86959a` (GREEN Task 1) — `delivery/__init__.py` + `delivery/stats.py`
- `99d3a5c` (RED Task 2) — failing tests for `delivery/config.py`
- `1389d21` (GREEN Task 2) — `delivery/config.py`
- `b8962c6` (RED Task 3) — failing tests for `delivery/message_builder.py`
- `e36383e` (GREEN Task 3) — `delivery/message_builder.py` + golden file + Wave-0 canary adjustment

Suite at HEAD: **677 passed, 7 skipped, 0 failed in 116.48s**.

## TDD Gate Compliance

This plan has `tdd="true"` on each of its 3 tasks. Gate sequence in `git log`:

| Task | RED commit | GREEN commit | RED→GREEN order respected? |
|------|------------|--------------|------|
| 1 | `73621be` `test(06-02): add failing tests for delivery/stats.py + 5-way namespace canary` | `f86959a` `feat(06-02): implement delivery package skeleton + delivery/stats.py` | YES |
| 2 | `99d3a5c` `test(06-02): add failing tests for delivery/config.py (D-611 + D-614)` | `1389d21` `feat(06-02): implement delivery/config.py (DeliverConfig + DeliverEnvConfig)` | YES |
| 3 | `b8962c6` `test(06-02): add failing tests for delivery/message_builder.py (D-610)` | `e36383e` `feat(06-02): implement delivery/message_builder.py + populate ops-alert golden file` | YES |

For each task, the RED commit was confirmed failing at the expected error (`ModuleNotFoundError: No module named 'ga_crawler.delivery[.config|.message_builder]'`) before the GREEN commit was created. No REFACTOR commits were needed — the implementations were small enough that the GREEN code shipped clean. No mid-task fail-fast events (no tests passed unexpectedly during RED).
