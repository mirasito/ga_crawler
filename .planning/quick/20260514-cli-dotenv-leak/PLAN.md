---
quick_id: 20260514-cli-dotenv-leak
description: CLI .env data leakage hotfix — subprocess tests sent fake-xlsx to real Telegram
date: 2026-05-14
status: in-progress
---

# Quick Task: cli.py dotenv-leak hotfix

## Problem

`src/ga_crawler/cli.py:271` calls `load_dotenv(override=False)` with no explicit path. `python-dotenv`'s `find_dotenv()` walks **up from `cli.py`'s __file__ location**, not from `os.getcwd()`. This means subprocess CLI invocations from a tmp_path cwd still discover and load the project's `.env` at `C:\Users\gstorepc\projects\ga_crawler\.env` — which carries `TG_BOT_TOKEN` + `TG_BUSINESS_CHAT_ID=986299192` (operator's personal Telegram chat).

Two integration tests (`test_deliver_run_missing_token_exits_3`, `test_unicode_stdout_safe_on_windows`) strip `TG_*` from subprocess `env=` but do not (and cannot, without a CLI change) prevent the subprocess from re-reading those vars from `.env`. Both tests have been **actively delivering 35-byte fake-xlsx stubs to the operator's real Telegram chat every test run** — at least 11 confirmed deliveries (file IDs `2026-W19.xlsx` through `2026-W19 (10).xlsx` in Downloads/Telegram Desktop, all 35-byte `PK\x03\x04fake-xlsx-content-for-cli-tests` literals).

The Phase 8 `08-01-SUMMARY.md` line 36 labelled these failures "pre-existing test failures" — that was **wrong**. They are an active data-egress channel, not a benign test-runner quirk.

## Reproduction

```
uv run pytest tests/integration/test_cli_deliver.py::test_deliver_run_missing_token_exits_3 -v
```

Returns `exit_code=0` with `delivery_status=delivered_business` and `business_document_message_id=23` (real Telegram message just sent).

## Fix

Change `cli.py:271` from:
```python
load_dotenv(override=False)
```
to:
```python
dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path, override=False)
```

- `find_dotenv(usecwd=True)` walks up from `os.getcwd()` instead of `__file__`.
- In subprocess tests: cwd = `tmp_path` (outside project tree) → walk ends at `C:\` → returns `""` → no-op.
- In production: operator runs `cd /opt/ga_crawler && python -m ga_crawler deliver-run` → cwd = project root → walks to `/opt/ga_crawler/.env` → loaded normally.
- In CI: same as production — cwd is project root.

## Tasks

1. **Add canary regression test** that asserts: invoking the CLI from a directory outside the project tree (no `.env` reachable upward) with TG_* stripped from env → `exit_code == 3` AND `delivery_status == "skipped_no_credentials"`. This makes the regression intent explicit, separate from the 2 pre-existing tests.
2. **Apply fix** to `cli.py:271` (1-line change, swap to `find_dotenv(usecwd=True)`).
3. **Verify** the 2 pre-existing failures (`test_deliver_run_missing_token_exits_3`, `test_unicode_stdout_safe_on_windows`) now pass alongside the new canary, and full suite is **824 passed / 1 skipped / 0 failed**.
4. **Update STATE.md** correcting the 08-01 SUMMARY mislabeling (active leak, not pre-existing failure) — note also in 08-02-SUMMARY.md addendum.

## Acceptance

- `grep -q 'find_dotenv' src/ga_crawler/cli.py`
- New canary test passes
- Full suite: 824 passed, 0 failed (was 822/2-failed)
- No new fake-xlsx deliveries to chat 986299192 on subsequent test runs

## Out of scope

- Audit of past leaked data — only fake-xlsx fixtures (35-byte literals), no real customer data exposed.
- Telegram-side message cleanup — operator can delete the 11+ files manually if desired.
- `.env.example` / docs — addressed in W3 (Plan 08-05) doc cascade.
