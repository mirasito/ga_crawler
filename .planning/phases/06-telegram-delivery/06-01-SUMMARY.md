---
phase: 06-telegram-delivery
plan: 01
subsystem: delivery
tags: [wave-0, setup, fixtures, stubs, aiogram, pyproject, env-template]
requires:
  - .planning/phases/05-reporter-excel-summary/05-06-SUMMARY.md     # Phase 5 frozen (D-514/D-515 cascade)
  - .planning/phases/06-telegram-delivery/06-CONTEXT.md             # D-601..D-616
  - .planning/phases/06-telegram-delivery/06-PATTERNS.md            # AMEND-patterns for pyproject + conftest
  - .planning/phases/06-telegram-delivery/06-VALIDATION.md          # Wave 0 stub inventory
provides:
  - pyproject.toml::[tool.ga_crawler.deliver]      # 6 keys per D-614
  - pyproject.toml::dependencies.aiogram           # >=3.27,<4.0 (resolved 3.28.2)
  - .env.example                                   # 3 TG_* placeholders (D-612)
  - tests/conftest.py::synthetic_delivered_run     # fixture for Waves 2-4
  - tests/conftest.py::mock_aiogram_bot            # fixture for Waves 2-4
  - tests/conftest.py::mock_tg_env                 # fixture for Waves 2-4
  - tests/fixtures/delivery/ops-alert-templates.txt  # 5 section-headers golden file (D-610 anchor)
  - 10 stub test files                             # red→green targets for Waves 1-4
affects:
  - pyproject.toml      # +1 dep + 1 new [tool.ga_crawler.deliver] table
  - tests/conftest.py   # +3 fixtures appended at end
  - uv.lock             # aiogram + aiofiles + magic-filter added
tech-stack:
  added:
    - "aiogram==3.28.2"      # resolved within >=3.27,<4.0 D-601 range
    - "aiofiles==25.1.0"     # transitive
    - "magic-filter==1.0.12" # transitive
  patterns:
    - "RED-then-GREEN per task (TDD plan-level cycle)"
    - "Three permanent canary tests (one per task) — drift detection through Phase 7"
    - "Five-way 4-task stat enforcement deferred — Plan 06-05 will close"
key-files:
  created:
    - .env.example
    - tests/conftest.py                                    # (extended)
    - tests/fixtures/delivery/ops-alert-templates.txt
    - tests/unit/test_phase06_wave0_pyproject_envexample.py
    - tests/unit/test_phase06_wave0_fixtures.py
    - tests/unit/test_phase06_wave0_stub_inventory.py
    - tests/test_delivery_config.py
    - tests/test_telegram_client.py
    - tests/test_gate.py
    - tests/test_message_builder.py
    - tests/test_delivery_stats.py
    - tests/test_delivery_source_lock.py
    - tests/integration/test_delivery_run.py
    - tests/integration/test_cli_deliver.py
    - tests/integration/test_weekly_run_with_delivery.py
    - tests/unit/test_stats_namespace_five_way.py
  modified:
    - pyproject.toml
    - tests/conftest.py
    - uv.lock
decisions:
  - D-601 aiogram>=3.27,<4.0 declared as alphabetically-first dep
  - D-614 [tool.ga_crawler.deliver] 6-key namespace verbatim (Pitfall drift-detection canary enforces "exactly 6 keys" invariant)
  - D-612 .env.example committed with 3 blank placeholders + 2 documentation comments
  - .gitignore audited — `.env` already present at line 25 (Phase 1 precedent); no edit needed
  - Three new conftest fixtures appended after synthetic_report_run; existing Phase 5 fixtures untouched
  - Golden file ships placeholder bodies (`<PLACEHOLDER ...>`) — real text deferred to Plan 06-02 build_ops_alert task
  - File 10 = `tests/unit/test_stats_namespace_five_way.py` (NEW file) — preserves Phase 5 `tests/unit/test_report_stats.py` untouched; plan task 3 alternative chosen
metrics:
  duration: "~12 min"
  completed: "2026-05-12T13:37:44Z"
  tests_pre: 610
  tests_post: 626        # 610 + 16 new canaries (5 + 7 + 4)
  tests_skipped_post: 11 # 1 pre-existing + 10 new stubs
  files_created: 16
  files_modified: 3
---

# Phase 6 Plan 01: Wave 0 Setup Summary

One-liner: Added aiogram 3.28.2 dependency, `[tool.ga_crawler.deliver]` 6-key pyproject namespace, `.env.example` template, 3 conftest fixtures (synthetic_delivered_run, mock_aiogram_bot, mock_tg_env), 5-section golden file, and 10 skip-marked test stubs so Waves 1-4 have a working red→green target.

## What Shipped

Wave 0 is mechanical setup — no production code, no behavior changes. The three tasks lay a deterministic foundation for the subsequent four implementation waves (Plans 06-02..06-05). Each task followed the plan-level TDD cycle: RED canary committed first, GREEN implementation committed second.

**Task 1 — Dependency + namespace + ENV template (RED 8699fe4 → GREEN 6a5ceda)**

- `pyproject.toml` gained one new dep (`aiogram>=3.27,<4.0`) inserted alphabetically before `camoufox`, and one new TOML table (`[tool.ga_crawler.deliver]`) appended after `[tool.ga_crawler.report]`. The 6 keys (`retry_max_attempts=3`, `retry_backoff_min_seconds=5`, `retry_backoff_max_seconds=45`, `ops_message_truncate_chars=3500`, `business_caption_max_chars=1024`, `parse_mode="HTML"`) match D-614 verbatim; the canary asserts `set(deliver.keys()) == { ... 6 names ... }` to refuse stealth additions outside operator PR.
- `.env.example` was created at repo root with 3 blank `TG_*` placeholders + 2 documentation lines pointing at @BotFather and @userinfobot. T-6-01 mitigation canary scans the file for non-blank token-shaped values and rejects any.
- `.gitignore` audit: the line `.env` already lives at line 25 from the Phase 1 D-08 IPRoyal credentials block; no edit was needed.
- `uv sync` resolved 4 new packages: aiogram 3.28.2, aiofiles 25.1.0, magic-filter 1.0.12 (a fourth was the editable `ga-crawler` rebuild). Sub-dep count came in around 4 net additions to the lockfile, well below RESEARCH §Environment Availability's "~70" upper-bound estimate — most aiogram transitives (aiohttp, pydantic, etc.) were already pinned by Phase 1-5 deps.

**Task 2 — Conftest fixtures + golden-file (RED 584cee5 → GREEN a8597ac)**

- `tests/conftest.py` extended with 3 fixtures appended at the end:
  - `synthetic_delivered_run` (Pitfall F superset of `synthetic_report_run`): plants the 7 `report.*` stats keys plus a fake xlsx file at `reports/2026-W19.xlsx` with the `PK\x03\x04` zip-shape header so FSInputFile would succeed in Wave 2.
  - `mock_aiogram_bot`: `MagicMock` with `__aenter__`/`__aexit__` as AsyncMock (so `async with Bot(...) as bot:` works) plus `send_message`/`send_document` as AsyncMock returning Message-like objects with `message_id=10001` / `10002`. Also includes `bot.session.close` as AsyncMock to prevent the "unclosed session" warning Pitfall B.
  - `mock_tg_env`: `monkeypatch.setenv` for the 3 `TG_*` env vars + yields a dict for assertion ergonomics. Per RESEARCH caveat #4 — tests **never** load real `.env`.
- `tests/fixtures/delivery/ops-alert-templates.txt`: 5 section headers (`upstream_status_failed`, `xlsx_oversize`, `empty_summary_text`, `no_xlsx_in_stats`, `delivery_exception`) with `<PLACEHOLDER>` bodies. Plan 06-02 will replace the placeholder lines with real `build_ops_alert(...)` output. The canary asserts `content.count("=== ") == 5` (drift-detection) and an additional T-6-08 regex check rejects any 13-digit negative chat_id pattern that would suggest a real Telegram id slipped in.

**Task 3 — 10 skip-marked stubs (RED 36bd7e1 → GREEN 09caf94)**

Created all 10 stub files per the plan. Each contains:
- Module docstring naming the target Plan (06-02 / 06-03 / 06-04 / 06-05) that will populate it (Behavior Test 4 requirement).
- A single `pytest.mark.skip(reason="Plan 06-01 stub — implemented in Plan 06-XX Wave Y")` placeholder test.
- For integration files: a module-level `pytestmark = pytest.mark.integration`.

The 6 top-level `tests/test_*.py` files (per the plan's explicit paths) sit alongside `tests/unit/` and `tests/integration/`. Pytest's `testpaths = ["tests"]` picks them up automatically.

## Tests Added

| Test file | Category | Tests |
|-----------|----------|-------|
| `tests/unit/test_phase06_wave0_pyproject_envexample.py` | Wave 0 canary (Task 1) | 5 green |
| `tests/unit/test_phase06_wave0_fixtures.py` | Wave 0 canary (Task 2) | 7 green |
| `tests/unit/test_phase06_wave0_stub_inventory.py` | Wave 0 canary (Task 3) | 4 green |
| 10 stubs listed above | skip-marked placeholders | 10 skipped |

**Suite totals:** 626 passed (up from 610), 11 skipped (up from 1) — exactly matches expectations (`+16 green canaries +10 new stubs`). One pre-existing skip carries over unchanged.

## aiogram resolution

`uv sync` resolved **aiogram 3.28.2** within the `>=3.27,<4.0` D-601 range (a one-minor-version drift from the spec's literal 3.27.0 mention, well within the `>=3.27` floor). Transitive additions: `aiofiles==25.1.0`, `magic-filter==1.0.12`. The "~70 sub-deps" estimate in RESEARCH was for a green-field install — most aiogram transitives (aiohttp, pydantic 2, certifi, etc.) were already present from Phase 1-5 deps, so the net lockfile delta was just **3 new packages**.

`import aiogram; print(aiogram.__version__)` from the project venv prints `3.28.2`.

## Deviations from Plan

### Auto-fixed Issues

None. Plan 06-01 was executed exactly as written across all three tasks. The plan was authored with surgical precision — every edit point (pyproject insertion alphabetical position, golden file section headers, conftest fixture docstrings) was specified down to the line, leaving zero room for interpretation drift.

### Deferred Items

None opened. Wave 0 ships everything it promised. The placeholder bodies in `ops-alert-templates.txt` are not deferrals — they are scheduled work for Plan 06-02 explicitly named on the file's first comment block.

## Auth Gates

None encountered. Telegram credentials are **not required** to ship Plan 06-01 — the plan's `user_setup` frontmatter even calls this out explicitly: "Plan 06-01 only documents — does NOT require credentials to ship." Wave 5+ (and Phase 7 cron) will need actual @BotFather token + chat_ids; those are operator actions out of scope for this plan.

## Decisions Made

- **Pyproject dep insertion position**: alphabetically first (before `camoufox`) — matches PATTERNS.md §"`pyproject.toml` (AMEND)" line 1021-1024 verbatim.
- **Pyproject namespace position**: appended after `[tool.ga_crawler.report]`, mirrors Phase 5 D-516 layout. Preserves the natural chronological order viled → goldapple → match → report → deliver.
- **Conftest fixture position**: appended at end-of-file (line 595+) after the last existing fixture `synthetic_report_run`. Phase 5 fixtures untouched (0-line diff against lines 1-594).
- **Golden file directory**: `tests/fixtures/delivery/` (new directory). Mirrors Phase 5 `tests/fixtures/reporter/` precedent.
- **File 10 choice**: created `tests/unit/test_stats_namespace_five_way.py` instead of amending `tests/unit/test_report_stats.py`. The plan explicitly offered this as the "alternative — keeps Phase 5 test untouched" choice; I took it because Phase 5 close-out (Plan 05-06 doc cascade) already declared `test_report_stats.py` frozen.

## Threat Model Surface

Plan 06-01's threat model (T-6-01, T-6-04, T-6-06, T-6-07, T-6-08) lists 5 threats with `mitigate` dispositions on T-6-01/06/07/08:

| Threat | Mitigation shipped in Wave 0 | Test canary |
|--------|------------------------------|-------------|
| T-6-01 (TG_BOT_TOKEN disclosure) | `.env` already in `.gitignore`; `.env.example` ships blank placeholders | `test_env_example_has_no_real_secret_values` |
| T-6-04 (pyproject tampering) | accept (operator-edits-via-PR convention) | N/A — accepted risk |
| T-6-06 (aiogram supply-chain spoofing) | Pin `aiogram>=3.27,<4.0` with major-version cap; `uv.lock` commits hashes | covered by lockfile integrity |
| T-6-07 (mock_tg_env leak between tests) | `monkeypatch.setenv` auto-teardown; per-test mock_aiogram_bot instance | per-test fixture isolation |
| T-6-08 (real chat_ids in golden file) | placeholder text only; regex canary rejects `-1001\d{9,}` pattern | `test_ops_alert_templates_contains_no_real_chat_ids` |

## Wave 0 → Wave 1 Handoff

Wave 1 (Plan 06-02) inherits:
- a resolved `aiogram` import path that works end-to-end (`uv run python -c "import aiogram"` → no error)
- a `DeliverConfig.from_pyproject` target class with 6 frozen pyproject keys waiting to be read
- a `tests/test_delivery_config.py` skip-marked stub naming Plan 06-02 in its docstring
- a `tests/test_delivery_stats.py` skip-marked stub waiting for `DELIVER_STATS_KEYS` 8-tuple
- a `tests/test_message_builder.py` skip-marked stub + `ops-alert-templates.txt` placeholder file ready to receive golden text
- `synthetic_delivered_run` fixture pre-loaded with the 7 `report.*` keys + a fake xlsx on disk; subsequent waves can `patch_stats` over the top to vary gate-pass / gate-fail scenarios

Five-way namespace disjoint canary (DELIVER ∩ {VILED, GOLDAPPLE, MATCH, REPORT} = ∅) deferred to Plan 06-05 per task 3 wording. The stub for it exists.

## Self-Check: PASSED

Files verified to exist on disk:
- pyproject.toml — `aiogram>=3.27,<4.0` line present; `[tool.ga_crawler.deliver]` table with 6 keys present
- .env.example — 3 TG_* placeholders present
- tests/conftest.py — 3 new fixture defs present (`synthetic_delivered_run`, `mock_aiogram_bot`, `mock_tg_env`)
- tests/fixtures/delivery/ops-alert-templates.txt — 5 section headers present
- 3 Wave 0 canary tests in tests/unit/
- 10 stub files (6 in tests/, 3 in tests/integration/, 1 in tests/unit/)

Commits verified in `git log --oneline`:
- 8699fe4 (RED Task 1) — `tests/unit/test_phase06_wave0_pyproject_envexample.py`
- 6a5ceda (GREEN Task 1) — pyproject.toml + uv.lock + .env.example
- 584cee5 (RED Task 2) — `tests/unit/test_phase06_wave0_fixtures.py`
- a8597ac (GREEN Task 2) — tests/conftest.py + tests/fixtures/delivery/ops-alert-templates.txt
- 36bd7e1 (RED Task 3) — `tests/unit/test_phase06_wave0_stub_inventory.py`
- 09caf94 (GREEN Task 3) — 10 stub files

626 passed, 11 skipped, 0 failed in 116.68s (full suite).
