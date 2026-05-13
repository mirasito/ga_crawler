---
quick_id: 20260514-cli-dotenv-leak
status: complete
date: 2026-05-14
commit: 43dbfd7
---

# Quick Task Summary — cli.py dotenv-leak hotfix

## What shipped

- `src/ga_crawler/cli.py:257-285` — `_cmd_deliver` now resolves dotenv path via `find_dotenv(usecwd=True)` and only calls `load_dotenv` when a path is found. Module-level `from dotenv import load_dotenv` upgraded to `from dotenv import find_dotenv, load_dotenv`.
- `tests/integration/test_cli_deliver.py:321-369` — new canary test `test_cli_does_not_load_project_dotenv_when_cwd_outside_tree` independent of the existing exit-code-3 contract test.
- `.planning/quick/20260514-cli-dotenv-leak/PLAN.md` + this SUMMARY.

## Stats

- **1 atomic commit:** `43dbfd7 fix(quick): cli.py dotenv discovery anchored at cwd, not __file__ (data egress hotfix)`.
- **Suite delta:** 822 passed / 2 failed → **825 passed / 0 failed** (+2 ex-failing tests now pass, +1 new canary).
- **No new dependencies** — `find_dotenv` ships in `python-dotenv>=1.0` (current pin).

## Root cause

`python-dotenv`'s `find_dotenv()` default behavior walks UP from `inspect.getfile(parent_frame)`, NOT from `os.getcwd()`. Since `cli.py` lives under `src/ga_crawler/`, the walk always lands on the project root's `.env` regardless of subprocess invocation context.

Tests that strip `TG_*` from `env=` cannot defeat this because the strip applies to the subprocess environment, while `load_dotenv` re-reads the values from disk AFTER the subprocess starts.

## Impact assessment

- **Data confidentiality:** ALL leaked deliveries carried the 35-byte fake-xlsx literal `PK\x03\x04fake-xlsx-content-for-cli-tests` from the test fixture at `tests/integration/test_cli_deliver.py:106`. **No customer data, no SKU prices, no DB snapshots leaked** — only the test stub's bytes.
- **Frequency:** ≥11 deliveries confirmed (file IDs in operator's Downloads/Telegram Desktop: `2026-W19.xlsx` through `2026-W19 (10).xlsx`). Each Phase 8 suite run added 2 messages (one per failing test).
- **Recipient:** `TG_BUSINESS_CHAT_ID=986299192` — operator's personal Telegram, NOT a shared business channel.
- **Operational impact:** non-zero only because the 2 "pre-existing failures" annotation in 08-01-SUMMARY hid the egress for ~1 day. No third-party exposure, no auth-credential leak (token in .env stayed in .env; only the file-upload API was exercised).

## Hazards added to project memory

1. **`load_dotenv()` without explicit path walks from `__file__`, not cwd.** Always use `find_dotenv(usecwd=True)` when test isolation matters.
2. **"Pre-existing failures" annotation in plan summaries is a code smell.** Treat them as live bugs until you have a written explanation of *why* they're pre-existing (commit ref, repro that confirms benign cause). 08-01-SUMMARY line 36 absorbed both failures into a "documented pre-existing failure" bucket without investigating; that was the failure of process that let the egress run for 11+ cycles.
3. **`.env` containing real Telegram credentials in a project that runs subprocess tests is a contamination hazard.** Future redesign: tests should never inherit credentials. Consider gating `load_dotenv` behind an env var like `GA_CRAWLER_ALLOW_DOTENV=1` that operator sets, never CI/tests.

## Cross-reference corrections

- `.planning/phases/08-parser-bug-fixes/08-01-SUMMARY.md:36` — annotation "Test suite: 801 passed / 1 skipped / 2 pre-existing failures (`test_cli_deliver.py` x2 — confirmed pre-existing via git stash test against HEAD baseline)" is **factually wrong**. The git-stash baseline check did not exercise Telegram I/O on HEAD (only locally); it confirmed the tests failed equally on HEAD, but did not detect WHY. Both failures were active data egress.
- `.planning/phases/08-parser-bug-fixes/08-02-SUMMARY.md` and `08-04-SUMMARY.md` references to "2 pre-existing test_cli_deliver failures" inherit the same mislabeling — context note added in `.planning/STATE.md`.

## Verification

- [x] `find_dotenv` imported and used: `grep -q "find_dotenv(usecwd=True)" src/ga_crawler/cli.py` → exits 0
- [x] Canary test exists and passes: `uv run pytest tests/integration/test_cli_deliver.py::test_cli_does_not_load_project_dotenv_when_cwd_outside_tree -v` → 1 passed
- [x] 2 ex-failing tests now pass: `uv run pytest tests/integration/test_cli_deliver.py::test_deliver_run_missing_token_exits_3 tests/integration/test_cli_deliver.py::test_unicode_stdout_safe_on_windows -v` → 2 passed
- [x] Full suite: 825 passed / 1 skipped / 0 failed (-m "not live")
- [x] No new Telegram deliveries from test runs (subsequent runs DO NOT add files to operator's chat)

## Next

- Resume Phase 8 W2 (Plan 08-03 goldapple brand+name h1-spans pivot) and W3 (Plan 08-05 null-rate gate + SMOKE rotation + doc cascade).
- W3 doc cascade should add the 3 hazards above to project hazards doc.
