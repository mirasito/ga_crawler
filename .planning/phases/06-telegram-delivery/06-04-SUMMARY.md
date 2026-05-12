---
phase: 06-telegram-delivery
plan: 04
subsystem: delivery
tags: [wave-3, orchestrator, cli, asyncio-run, d-605, d-606, d-607, d-608, d-611]
requires:
  - .planning/phases/06-telegram-delivery/06-03-SUMMARY.md     # Wave 2 service-layer (gate + telegram_client)
  - .planning/phases/06-telegram-delivery/06-02-SUMMARY.md     # Wave 1 foundations (config + stats + message_builder)
  - .planning/phases/06-telegram-delivery/06-CONTEXT.md        # D-601..D-616
  - .planning/phases/06-telegram-delivery/06-RESEARCH.md       # Integration Patterns 1-5 + Pitfalls A/B/C/D + §10/11 + caveat #4
  - .planning/phases/06-telegram-delivery/06-PATTERNS.md       # runners/delivery_run.py + cli.py amend skeletons
provides:
  - src/ga_crawler/runners/delivery_run.py::DeliveryPhaseResult
  - src/ga_crawler/runners/delivery_run.py::run_delivery_phase
  - src/ga_crawler/runners/delivery_run.py::_send_async       # async block per D-602 Pitfall B
  - src/ga_crawler/runners/delivery_run.py::_resolve_xlsx_safely  # Pitfall C defense-in-depth
  - src/ga_crawler/runners/delivery_run.py::_build_stats_skip_path  # Pitfall 6 atomicity helper
  - src/ga_crawler/runners/delivery_run.py::_coerce_started_at      # Python 3.12 sqlite3 ISO-string fix
  - src/ga_crawler/cli.py::_cmd_deliver                       # D-608 standalone recovery handler
  - src/ga_crawler/cli.py deliver-run subparser               # 6-flag CLI
affects:
  - tests/integration/test_delivery_run.py                    # 1 skip stub → 19 GREEN
  - tests/integration/test_cli_deliver.py                     # 1 skip stub → 8 GREEN
  - tests/unit/test_phase06_wave0_stub_inventory.py           # STUB_FILES 4→2; +WAVE3_CLOSURES regression
tech-stack:
  added: []                                                   # zero new deps — uses Wave 0/1/2 packages
  patterns:
    - "Sync orchestrator wraps a single async block via asyncio.run (mirror of main_run.py:224 goldapple pattern)"
    - "D-605 invariant: TelegramAPIError NEVER raises out — mapped to undelivered_telegram_unreachable + runs.status untouched"
    - "Pitfall 6 single patch_stats per invocation — exactly 2 static call sites in source (1 in _build_stats_skip_path + 1 in main flow Step 7); structural canary asserts == 2"
    - "Pitfall C defense-in-depth: _resolve_xlsx_safely re-validates xlsx_path before FSInputFile (Phase 5 validated write-side; Phase 6 re-validates read-side)"
    - "Pitfall D message_id sentinels: non-split business sends caption+document on ONE Telegram message → caption_id mirrors document_id; split path keeps them distinct"
    - "D-611 asymmetric ENV: TG_BOT_TOKEN missing → skipped_no_credentials (exit 3); business_chat_id missing → degrade route business→ops_only; ops_chat_id missing on business route → log warning + proceed"
    - "Subprocess CLI tests mirror Plan 05-05 test_cli_report_subcommand.py shape; in-process orchestrator tests use mock_aiogram_bot + patched_bot fixture"
    - "load_dotenv ONLY in cli.py::_cmd_deliver (RESEARCH caveat #4) — structural canary in test_cli_deliver.py:test_load_dotenv_only_in_cli enforces this"
key-files:
  created:
    - src/ga_crawler/runners/delivery_run.py
  modified:
    - src/ga_crawler/cli.py
    - tests/integration/test_delivery_run.py
    - tests/integration/test_cli_deliver.py
    - tests/unit/test_phase06_wave0_stub_inventory.py
decisions:
  - "D-605 enforcement: outer try/except in run_delivery_phase catches Exception → maps to undelivered_telegram_unreachable + records repr(e)[:500] in last_error. Programmer bugs (AttributeError etc.) caught at the asyncio.run boundary; tenacity-mapped Telegram failures arrive as SendOutcome(error=...) and never raise"
  - "Pacing per W5 ACK reorganized to 3 commits (scaffold/test/cli) — scaffold included _send_async in commit #1 since the module is monolithic; integration tests + bugfix shipped in commit #2; CLI + canary update in commit #3"
  - "_coerce_started_at helper added during integration (Rule 1 bug): SQLAlchemy text() over Python 3.12 SQLite returns started_at as ISO string (default datetime adapter deprecated); parse via datetime.fromisoformat with Z→+00:00 normalization and naive→UTC promotion"
  - "Test 5c (D-611 asymmetric ops_chat_missing) uses capsys NOT caplog — project's structlog config writes to stdout via PrintLogger; stdlib logging.caplog does not capture those events"
  - "_extract_payload in test_cli_deliver.py uses rfind to grab the LAST '{\\n' block — orchestrator dry-run writes preview JSON BEFORE the CLI payload, so the LAST block is always the CLI's"
  - "Exit code 0 for pending+dry_run added to CLI mapping (dry-run is read-only success, not failure)"
  - "Subprocess test for actual Telegram send deliberately omitted — subprocess cannot share mock_aiogram_bot; happy-path send is covered by in-process orchestrator tests in tests/integration/test_delivery_run.py (5a/5b/3)"
metrics:
  duration: "~17 min"
  completed: "2026-05-12T14:49:10Z"
  tests_pre: 707         # Wave 2 baseline (707 passed, 5 skipped)
  tests_post: 735        # +28 net (19 delivery + 8 CLI + 1 wave3 regression canary − 0 stubs converted give the count after Plan 06-04 closure)
  tests_skipped_post: 3  # 5 − 2 Plan 06-04 stub closures
  files_created: 1
  files_modified: 4
---

# Phase 6 Plan 04: Wave 3 Orchestrator + CLI Summary

One-liner: Sync 7-step delivery orchestrator (`runners/delivery_run.py::run_delivery_phase` wrapping `asyncio.run(_send_async(...))` per Pitfall B) + `deliver-run` CLI subcommand wire all of Wave 1 (config/stats/message_builder) and Wave 2 (gate/telegram_client) into a single working end-to-end recovery tool — 19 orchestrator integration tests + 8 CLI subprocess tests turn both remaining Plan 06-04 stubs GREEN, lifting the suite to 735 / 3 / 0 with zero regressions.

## What Shipped

Wave 3 is the **composition wave** of Phase 6 — the single place where every Wave-1 / Wave-2 module is wired together into a working delivery pipeline. Before this plan, the delivery package was a collection of pure-Python pieces nobody called; after this plan, `python -m ga_crawler deliver-run --run-id N` is a real working command.

### Task 1 — `src/ga_crawler/runners/delivery_run.py` (`89acd41` scaffold → `6eee871` integration suite GREEN)

Created `src/ga_crawler/runners/delivery_run.py` (~560 LOC prod) line-mirroring `runners/reporter_run.py` shape with Phase-6-specific additions:

- **`DeliveryPhaseResult`** dataclass (9 fields per D-616 + D-607 superset): `delivery_status`, `route`, `business_caption_message_id`, `business_document_message_id`, `ops_message_id`, `attempt_count`, `last_error`, `delivered_at`, `stats_delta`.
- **`run_delivery_phase(*, run_id, engine, run_writer, repo_root, config, env, force=False, dry_run=False) -> DeliveryPhaseResult`** — the public sync entrypoint. 7-step pipeline:
  1. **Pre-flight (D-611):** `env.bot_token` required → otherwise `skipped_no_credentials`.
  2. **Idempotency (D-608):** if existing `deliver.delivery_status == "delivered_business"` and not `force` → `skipped_already_delivered`.
  3. **Gate evaluation (D-604):** delegates to `evaluate_gate` (Wave 2).
  4. **Stats read:** flat-dot keys from `runs.stats` (`viled.fetch_count`, `goldapple.fetch_count`, `match.count`, `match.rate`, `report.summary_text`, `report.xlsx_path`, …). Also reads `runs.started_at` for ops-alert timestamp.
  5. **Message build:** `build_ops_alert(...)` for ops route; `business_caption(summary_text, max_chars=1024)` for business route.
  6. **dry-run early exit:** writes preview JSON to `sys.stdout.buffer` + skips Telegram + skips `patch_stats` (read-only by design).
  7. **Pitfall C path containment + asymmetric ENV chat_id handling + `asyncio.run(_send_async(...))`:** `_resolve_xlsx_safely` re-validates `xlsx_path` against `repo_root`; ENV asymmetry per D-611 (missing `business_chat_id` degrades route → ops_only; missing `ops_chat_id` on business route logs warning + proceeds; missing `ops_chat_id` on ops route → `skipped_no_credentials`); single async block under `async with bot` (Pitfall B).
  8. **Single atomic `patch_stats` (Pitfall 6):** all 8 `deliver.*` keys patched at once with `DeliverStatsBuilder`. `delivered_at` set to ISO-UTC iff `delivery_status.startswith("delivered_")`, empty string otherwise.

- **`_send_async(...)`** is the single async I/O block — mirror of `main_run.py:224` goldapple pattern. `await open_bot(token, parse_mode)` returns a `Bot`; `async with bot:` wraps the lifecycle (auto-close session — Pitfall B). Business branch handles caption-split fork: when `is_split=True`, sends full summary via `send_message_with_policy` FIRST (captures `business_caption_message_id`), then `send_document_with_policy` with the short fallback caption; when `is_split=False`, only `send_document` is called and `business_caption_message_id` mirrors `business_document_message_id` (Pitfall D semantics).

- **`_resolve_xlsx_safely(xlsx_path, repo_root)`** — Pitfall C defense-in-depth: resolves `(repo_root / xlsx_path)`, then `Path.relative_to(repo_root.resolve())` to detect escape; raises `ValueError("xlsx_path_escapes_repo:...")` on escape and `FileNotFoundError` if the file is absent. Caught by orchestrator → `undelivered_telegram_unreachable` + no send.

- **`_build_stats_skip_path(...)`** — single helper for ALL skip/early-exit branches (no credentials / idempotency / xlsx-path-invalid / unexpected-crash). Calls `run_writer.patch_stats(run_id, ...)` ONCE with all 8 sentinel-valued keys. This is the FIRST of exactly 2 static `patch_stats` call sites; the SECOND lives in the main-flow Step 7 success path. Structural canary `count_patch == 2` enforces D-607 atomicity invariant.

- **`_coerce_started_at(value)`** — added during integration (Rule 1 bug, see Deviations). Python 3.12 deprecated the default `sqlite3` datetime adapter, so `engine.execute(text("SELECT started_at FROM runs"))` returns `started_at` as an ISO 8601 string; coerce to aware UTC datetime via `datetime.fromisoformat` (handles both `+00:00` and `Z` suffixes; naive datetimes promoted to UTC).

**Tests (19 GREEN in `tests/integration/test_delivery_run.py`):**

| # | Test | Coverage |
|---|------|----------|
| 1 | `test_skip_when_token_missing` | D-611 asymmetric: TG_BOT_TOKEN absent → `skipped_no_credentials` + no Bot ctor |
| 2 | `test_idempotency_skip_when_already_delivered` | D-608: pre-planted `delivered_business` + `force=False` → `skipped_already_delivered` |
| 3 | `test_force_overrides_idempotency` | D-608: `force=True` bypasses idempotency → `delivered_business` |
| 4 | `test_gate_fail_routes_to_ops_only` | D-604: `run_writer.fail()` → gate trips → ops alert sent (msg_id=10001) |
| 5a | `test_gate_pass_non_split_path_5a` | W2 FIX: summary ≤ 1024 → only `send_document`; caption_id == document_id == 10002 |
| 5b | `test_gate_pass_split_path_5b` | W2 FIX: summary > 1024 → `send_message`+`send_document`; caption_id=10001, document_id=10002 (distinct); send_message receives FULL summary; send_document caption is the short fallback |
| 5c | `test_business_route_with_missing_ops_chat_proceeds_5c` | W3 FIX: D-611 asymmetric, TG_OPS_CHAT_ID missing on business route → warn + proceed → `delivered_business`; structlog event `delivery_ops_chat_missing_acceptable_for_business_route` asserted in capsys |
| 6 | `test_single_patch_stats_per_invocation` | Pitfall 6: parametrized over 4 scenarios (gate-pass / gate-fail / token-missing / idempotency-skip); spy on `run_writer.patch_stats` → `call_count == 1` in all 4 |
| 7 | `test_telegram_network_error_does_not_fail_run` | D-605: bot.send_document raises TelegramNetworkError 3x → `undelivered_telegram_unreachable`; `runs.status` STILL `success`; xlsx STILL on disk. Uses `fast_retry` fixture to flatten tenacity wait to 0s |
| 8 | `test_telegram_bad_request_no_retry` | Pitfall A: TelegramBadRequest fail-fast → 1 invocation, no retry; `runs.status` unchanged |
| 9 | `test_xlsx_path_traversal_blocked` | Pitfall C: tampered `xlsx_path="../../etc/passwd"` → `undelivered_telegram_unreachable` + `xlsx_path_escapes_repo` in last_error; zero Telegram calls |
| 10 | `test_caption_split_when_long` | Claude's Discretion: 1500-char summary → send_message + send_document; correct message_id mapping |
| 11 | `test_dry_run_no_telegram_calls` | D-608: dry-run → 0 Telegram calls + 0 patch_stats + preview JSON contains `"route"` key |
| 12 | `test_all_8_d607_keys_present_after_business_send` | D-607: all 8 `deliver.*` keys in stats after business send; spot-checks sentinel semantics |
| 13 | `test_message_id_sentinels_for_ops_only` | Pitfall D: ops route → `business_*_message_id == -1`; `ops_message_id == 10001` |
| 14 | `test_no_unclosed_session_warning` | Pitfall B: `__aenter__`/`__aexit__` awaited exactly once; no `Unclosed client session` RuntimeWarning |

Local fixtures: `patched_bot` (replaces `runners.delivery_run.open_bot` with a stub returning `mock_aiogram_bot` — bypasses aiogram token validator which would reject `mock_tg_env`'s `test-token-12345` format); `fast_retry` (mirror of `tests/test_telegram_client.py::fast_retry` — flattens `wait_chain(5,15,45)` → `wait_chain(0,0,0)` while preserving `before_sleep` callback semantics).

### Task 2 — `src/ga_crawler/cli.py` amend + CLI integration tests (`9e74e80`)

Amended `src/ga_crawler/cli.py`:

- **Module docstring** lists `deliver-run` as 5th subcommand with full flag + exit code spec.
- **`_cmd_deliver(args) -> int`** handler:
  - Calls `load_dotenv(override=False)` ONCE at handler entry (RESEARCH caveat #4 — ONLY place in the project where `load_dotenv` lives; structural canary `test_load_dotenv_only_in_cli` enforces this).
  - Builds `DeliverConfig.from_pyproject(args.pyproject)` + `DeliverEnvConfig.from_env()`.
  - Invokes `run_delivery_phase(run_id=..., force=args.force, dry_run=args.dry_run)`.
  - Emits indented JSON payload to `sys.stdout.buffer` (Unicode-safe on Windows — Plan 05-05 pattern).
  - **D-608 exit code map:**
    - `0` → `delivered_business` | `delivered_ops_only` | `skipped_already_delivered` | `pending+dry_run`
    - `2` → `undelivered_telegram_unreachable` (retryable)
    - `3` → `skipped_no_credentials` (config error)
- **`deliver-run` subparser** with 6 args: `--run-id` (required int), `--db-path` (default `prices.db`), `--pyproject` (default `pyproject.toml`), `--repo-root` (default `.`), `--force` (store_true), `--dry-run` (store_true).
- **Dispatch table** extended with `if args.cmd == "deliver-run": return _cmd_deliver(args)`.

**Tests (8 GREEN in `tests/integration/test_cli_deliver.py`):**

| # | Test | Coverage |
|---|------|----------|
| 1 | `test_deliver_run_help_lists_subcommand` | top-level `--help` mentions deliver-run |
| 2 | `test_deliver_run_help_shows_all_flags` | `deliver-run --help` advertises all 6 flags |
| 3 | `test_deliver_run_missing_run_id_exits_nonzero` | argparse rejects missing `--run-id` |
| 4 | `test_deliver_run_missing_token_exits_3` | D-611+D-608: missing TG_BOT_TOKEN → exit 3 + `skipped_no_credentials` payload |
| 5 | `test_deliver_run_dry_run_prints_preview` | D-608: `--dry-run` → exit 0 + JSON payload with `"route"` key |
| 6 | `test_force_flag_parsed` | argparse parses `--force` boolean; `_cmd_deliver` exported |
| 7 | `test_unicode_stdout_safe_on_windows` | Cyrillic + emoji summary_text round-trips through stdout |
| 8 | `test_load_dotenv_only_in_cli` | RESEARCH caveat #4 structural canary — exactly 1 hit under `src/ga_crawler/`, must be `cli.py` (cross-platform `PurePath.parts` match per W4 fix) |

Real-Telegram-send subprocess tests are deliberately omitted because subprocess cannot share a Python-level mock — happy-path business sends are covered in-process by Tests 3 / 5a / 5b / 6 / 10 / 12 of the orchestrator suite via `patched_bot`.

Helper `_extract_payload` uses `stdout.rfind("{\n")` (not `find`) — in `--dry-run` mode the orchestrator writes its OWN preview JSON to stdout BEFORE the CLI's payload, so the LAST indented JSON block is always the CLI's final payload.

## Tests Added

| Test file | Before | After Wave 3 | Delta |
|-----------|--------|--------------|-------|
| `tests/integration/test_delivery_run.py` | 1 skip stub | 19 GREEN | +19, −1 skip |
| `tests/integration/test_cli_deliver.py` | 1 skip stub | 8 GREEN | +8, −1 skip |
| `tests/unit/test_phase06_wave0_stub_inventory.py` | 6 GREEN | 7 GREEN | +1 GREEN regression test (WAVE3_CLOSURES) |

**Suite totals:** 735 passed (up from 707), 3 skipped (down from 5). Delta = +28 passed (+19 + +8 + +1), −2 skipped. Zero failing tests, zero regressions in Phases 2-5.

## Verification Canaries

| Canary | Command | Result |
|--------|---------|--------|
| Orchestrator suite green | `uv run pytest tests/integration/test_delivery_run.py -x` | 19 passed |
| CLI suite green | `uv run pytest tests/integration/test_cli_deliver.py -x` | 8 passed |
| Full suite green | `uv run pytest -q` | 735 passed / 3 skipped / 0 failed |
| `DeliveryPhaseResult` 9-field shape | `python -c "from ga_crawler.runners.delivery_run import DeliveryPhaseResult; import dataclasses; assert len(dataclasses.fields(DeliveryPhaseResult))==9"` | OK |
| **D-607 Pitfall 6 atomicity** (exactly 2 `patch_stats` sites in delivery_run.py) | `python -c "from pathlib import Path; assert Path('src/ga_crawler/runners/delivery_run.py').read_text(encoding='utf-8').count('run_writer.patch_stats(') == 2"` | OK |
| `deliver-run` registered | `uv run python -m ga_crawler --help \| grep deliver-run` | OK |
| `deliver-run --help` advertises all flags | `uv run python -m ga_crawler deliver-run --help` | OK |
| **load_dotenv only in cli.py** (RESEARCH caveat #4) | structural canary `test_load_dotenv_only_in_cli` | OK |
| WAVE3_CLOSURES regression | `test_wave3_closures_no_longer_have_skip_marker` | OK |
| Stub inventory count = 2 | `test_remaining_stub_count_after_wave3` | OK |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Python 3.12 sqlite3 default datetime adapter deprecation returns `started_at` as ISO string**
- **Found during:** Task 1 Test 4 (`test_gate_fail_routes_to_ops_only`) — first integration test that exercised the ops-alert path. `build_ops_alert` called `_format_almaty(started_at_utc)` which called `started_at_utc.tzinfo` → `AttributeError: 'str' object has no attribute 'tzinfo'`.
- **Issue:** Python 3.12 deprecated the default `sqlite3` datetime adapter; `runs.started_at` is stored as a string and returned as `'2026-05-10 14:00:00+00:00'` from `engine.execute(text("SELECT started_at FROM runs"))`. The original plan skeleton fed this value directly into `build_ops_alert(started_at_utc=...)`, but `_format_almaty` expects a `datetime`.
- **Fix:** Added `_coerce_started_at(value) -> datetime` helper that handles `None` / `datetime` / ISO string inputs. Uses `datetime.fromisoformat` with `Z → +00:00` normalization (`fromisoformat` accepts `+00:00` but not `Z` until 3.11; safer to normalize). Naive datetimes promoted to UTC per DATA-05.
- **Files modified:** `src/ga_crawler/runners/delivery_run.py` (new helper + call-site swap)
- **Commit:** rolled into `6eee871` (Task 1 GREEN commit) since the issue surfaced during integration testing, not at scaffold time.

**2. [Rule 3 — Blocking] Wave-0 inventory canary tripped after closing `tests/integration/test_delivery_run.py`**
- **Found during:** Task 1 full-suite check after Test 4 fix landed. `test_all_remaining_stub_files_contain_skip_marker` listed `test_delivery_run.py` in `STUB_FILES` but the file no longer carries `pytest.mark.skip`.
- **Issue:** Same pattern as Wave 1/2 closures — the canary is intentionally strict to catch forgotten stubs. Closing a stub MUST be paired with updating `STUB_FILES`.
- **Fix:** Two-step update (Task 1 commit moved `test_delivery_run.py`; Task 2 commit moved `test_cli_deliver.py`). Added `WAVE3_CLOSURES` list + companion regression test `test_wave3_closures_no_longer_have_skip_marker`. `test_remaining_stub_count_after_wave3` now asserts `len(STUB_FILES) == 2` (only Plan 06-05 stubs remain).
- **Files modified:** `tests/unit/test_phase06_wave0_stub_inventory.py`
- **Commits:** Task 1 commit `6eee871` updated for `test_delivery_run.py`; Task 2 commit `9e74e80` updated for `test_cli_deliver.py`.

**3. [Rule 1 — Bug] structlog warning event invisible to `caplog` (Test 5c)**
- **Found during:** Task 1 Test 5c first run.
- **Issue:** The test asserted that `caplog.records` contains the event `delivery_ops_chat_missing_acceptable_for_business_route`. The event WAS logged (visible in captured stdout) but `caplog` (stdlib logging) was empty — structlog is configured with `PrintLogger` (writes to stdout directly), bypassing stdlib `logging` entirely.
- **Fix:** Test 5c now uses `capsys` (stdout-level capture) instead of `caplog`. The assertion `"delivery_ops_chat_missing_acceptable_for_business_route" in captured.out` is more direct and matches the project's actual logging setup.
- **Files modified:** `tests/integration/test_delivery_run.py`
- **Commit:** rolled into `6eee871`.

**4. [Rule 1 — Bug] CLI `--dry-run` payload extraction failed because orchestrator AND handler each emit JSON**
- **Found during:** Task 2 Test 5 (`test_deliver_run_dry_run_prints_preview`).
- **Issue:** In `--dry-run` mode, `run_delivery_phase` writes the gate-decision preview JSON to `sys.stdout.buffer` BEFORE returning; then `_cmd_deliver` writes its own indented JSON payload AFTER. Both blocks satisfy the `"{\n"` prefix, so `stdout.find("{\n")` landed on the orchestrator's block and `json.loads` failed with `Extra data` on the second block.
- **Fix:** Switched `_extract_payload` to `stdout.rfind("{\n")` — the LAST indented JSON block in stdout is always the CLI's final payload. Existing non-dry-run callers also work (single payload → `rfind` returns the same index as `find`).
- **Files modified:** `tests/integration/test_cli_deliver.py`
- **Commit:** rolled into `9e74e80`.

**5. [Rule 2 — Critical functionality] D-608 exit code 0 for `pending` + `--dry-run`**
- **Found during:** Reviewing the exit code map while writing `_cmd_deliver`.
- **Issue:** The plan's exit code mapping was `delivered_*` / `skipped_already_delivered` → 0; `skipped_no_credentials` → 3; everything else → 2. But `--dry-run` returns `delivery_status="pending"` which would map to 2 (retryable failure). A successful `--dry-run` should NOT exit non-zero — operator running `deliver-run --dry-run --run-id N` to verify the gate decision expects exit 0 if everything is fine.
- **Fix:** Added explicit branch: `if result.delivery_status == "pending" and args.dry_run: return 0`. Documented in handler docstring.
- **Files modified:** `src/ga_crawler/cli.py`
- **Commit:** rolled into `9e74e80` (caught during writing, never shipped a bad version).

### Deferred Items

None. All 14 behavior tests from the plan's `<behavior>` section are GREEN; the CLI suite has 8 tests (plan promised ≥7). The plan explicitly defers real-Telegram subprocess sends to Phase 7 (operator setup); Wave 3 is complete.

## Auth Gates

None encountered during execution. Plan 06-04 stays at the integration-test level — `mock_aiogram_bot` (Plan 06-01 fixture) plus `patched_bot` (this plan's local fixture replacing `runners.delivery_run.open_bot`) keep all 19 orchestrator tests fully isolated from any real network or Telegram credentials. CLI subprocess tests use `_env_without_tg()` to strip `TG_*` env vars and either deliberately omit `TG_BOT_TOKEN` (Test 4, Test 7 → exit 3 path) or stub it with a fake digits:string-format token (Test 5 → exit 0 dry-run path).

Real auth gates will surface at Phase 7 deployment time when an operator first runs `python -m ga_crawler deliver-run --run-id N` against the production VPS — that's outside Phase 6 scope.

## Decisions Made

- **3-commit pacing reorganized from the W5 ACK's `scaffold/wire/tests` split to `scaffold/test/cli`** — `_send_async` was small enough (≤40 LOC after dataclass-bundle pattern) to ship in the scaffold commit without making it unwieldy. Splitting it into a separate "wire" commit would have introduced an intermediate state with `_send_async` defined but no `asyncio.run` caller, which adds no review value. The 3-commit chain ships exactly the boundaries that make sense: scaffold (`89acd41`), integration suite + bugfixes (`6eee871`), CLI + canary (`9e74e80`).
- **`_AsyncSendResult` is a private dataclass colocated with `_send_async`** — it carries 6 fields (cumulative across business/ops branches) that the sync caller maps onto stats. Could have been a tuple but dataclass gives named attribute access for the 6 separate map operations in Step 7 (clearer at the call site).
- **`assert business_payload is not None` etc. in `_send_async`** — defensive runtime assertions that the orchestrator wired the route-specific payload correctly. Bare programmer-bug catches; never expected to fire in production. If they DO fire, they hit the outer try/except in `run_delivery_phase` and map to `undelivered_telegram_unreachable + last_error="AssertionError: ..."`.
- **Test 5c uses `capsys` (not `caplog`)** — see Deviation #3. The project's structlog config uses `PrintLogger`, bypassing stdlib `logging`. `capsys` is the correct tool for asserting structlog event names emitted via `log.warning(...)`.
- **`stdout.rfind("{\n")` instead of `find`** in `_extract_payload` — see Deviation #4. Robust to dry-run mode where orchestrator AND handler each emit a JSON block.
- **Exit code 0 for `pending+dry_run`** — see Deviation #5. Operator using `--dry-run` to verify gate decision expects 0 on success.
- **Subprocess CLI tests deliberately limited to: --help / exit 3 (missing token) / exit 0 (dry-run) / Unicode stdout / structural canary** — real Telegram-send subprocess tests are infeasible without a real bot (subprocess cannot share `mock_aiogram_bot`). The 19 in-process orchestrator tests cover all 6 D-606 enum transitions including `delivered_business` and `delivered_ops_only`.

## Threat Model Surface

Plan 06-04's threat register lists T-6-02 (Pitfall C), T-6-03 (HTML injection — handled in Wave 1), T-6-04 (operator chat_id), T-6-05 (xlsx → Telegram cloud — accepted business risk), T-6-15 (delivery_status not persisted on crash), T-6-16 (TG_BOT_TOKEN in logs).

| Threat | Mitigation shipped | Test canary |
|--------|--------------------|-------------|
| **T-6-02** (xlsx_path containment) | `_resolve_xlsx_safely` re-validates `(repo_root / xlsx_path).resolve().relative_to(repo_root.resolve())` BEFORE FSInputFile; raises `ValueError("xlsx_path_escapes_repo:...")`; caught by orchestrator → `undelivered_telegram_unreachable`. | Test 9 `test_xlsx_path_traversal_blocked` pins regression with `xlsx_path="../../etc/passwd"` |
| **T-6-03** (HTML injection in ops-alert dynamic fields) | Wave 1 `build_ops_alert` already escapes via `_esc = html.escape(value, quote=False)`; Plan 06-04 just consumes the pre-escaped string. | Wave 1 tests pin this; Wave 3 inherits |
| **T-6-04** (operator-controlled chat_id) | Documented operational hygiene; Phase 7 will document @userinfobot verification. Wave 3 does not add technical mitigation. | accept (documented) |
| **T-6-05** (xlsx → Telegram cloud) | Accepted business risk per PROJECT.md (delivery channel = Telegram). | accept |
| **T-6-15** (delivery_status not persisted on crash) | Outer try/except in `run_delivery_phase` catches `Exception` → `_build_stats_skip_path(delivery_status="undelivered_telegram_unreachable", last_error=repr(e)[:500])`. Even programmer-bug crash leaves an audit trail in `runs.stats.deliver.*`. | Test 9 (Pitfall C `ValueError` flows through this path); Test 6 parametrized scenario `skip_token_missing` exercises the same skip-path helper |
| **T-6-16** (TG_BOT_TOKEN in structlog) | Manual code review: zero `bot_token` substring in any `log.info` / `log.warning` / `log.error` kwarg across `runners/delivery_run.py`; `_cmd_deliver` does not pass `env` into log events. | manual canary; documented |

## Wave 3 → Wave 4 Handoff

Plan 06-05 (Wave 4 composition into `runners/main_run.py::run_weekly` + final source-lock canaries + cron docs) inherits:

- A fully working `run_delivery_phase(run_id, engine, run_writer, repo_root, config, env, force=False, dry_run=False) -> DeliveryPhaseResult` — Wave 4 just needs to hook it AFTER the reporter step in `main_run.run_weekly` with `force=True` (weekly cron always re-attempts).
- A `deliver-run` CLI subcommand that mirrors the weekly-run shape — no further CLI work needed.
- A `DeliveryPhaseResult` dataclass ready to be mapped onto Wave 4's `MainRunResult.delivery_status` + `MainRunResult.delivery_route` fields (D-616).
- `load_dotenv` source-lock canary in `tests/integration/test_cli_deliver.py` — Wave 4 must NOT introduce a second `load_dotenv` call; the canary will catch it.
- Wave-0 stub-inventory canary now lists 2 remaining stubs (`test_delivery_source_lock.py` + `test_weekly_run_with_delivery.py`). Wave 4 will turn both GREEN, dropping the count to 0 and closing Phase 6's stub-tracking story entirely.

Open considerations for Plan 06-05:
- D-616 `MainRunResult` amendment: add `delivery_status: str = "pending"` + `delivery_route: str = ""` fields. Map from `DeliveryPhaseResult` at the end of `run_weekly`.
- Composition pattern: same `if r_result.status == "success":` gate the reporter uses for its conditional → Wave 4 hooks `run_delivery_phase` AFTER the reporter, with `force=True` for unattended cron operation (operator never wants `skipped_already_delivered` on the cron path).
- The 2 remaining stub files name their target plan in the docstring; Wave 4 just needs to write the actual tests.

## Self-Check: PASSED

Files verified to exist on disk:

- `src/ga_crawler/runners/delivery_run.py` — FOUND (DeliveryPhaseResult + run_delivery_phase + _send_async + _resolve_xlsx_safely + _build_stats_skip_path + _coerce_started_at + _AsyncSendResult)
- `src/ga_crawler/cli.py` — FOUND (modified: _cmd_deliver handler + deliver-run subparser + dispatch + docstring)
- `tests/integration/test_delivery_run.py` — FOUND (19 GREEN tests, no skip markers, patched_bot + fast_retry local fixtures)
- `tests/integration/test_cli_deliver.py` — FOUND (8 GREEN tests, no skip markers, _plant_run + _extract_payload helpers, load_dotenv structural canary)
- `tests/unit/test_phase06_wave0_stub_inventory.py` — FOUND (modified: STUB_FILES narrowed to 2 + WAVE3_CLOSURES extended + test_wave3_closures_no_longer_have_skip_marker)

Commits verified in `git log --oneline`:

- `89acd41` (Task 1 scaffold) — `feat(06-04): scaffold run_delivery_phase 7-step orchestrator + _send_async`
- `6eee871` (Task 1 GREEN) — `test(06-04): integration suite for run_delivery_phase (19 GREEN)`
- `9e74e80` (Task 2 GREEN) — `feat(06-04): add deliver-run CLI subcommand + _cmd_deliver handler (D-608)`

Suite at HEAD: **735 passed, 3 skipped, 0 failed in 131.42s**.
