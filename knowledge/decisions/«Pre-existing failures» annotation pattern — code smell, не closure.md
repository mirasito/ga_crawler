---
tags: [decision, process, planning, qa, retrospective, hotfix-43dbfd7]
date: 2026-05-14
status: locked
applies_to: .planning/phases/**/SUMMARY.md
---

# «Pre-existing failures» annotation pattern — code smell, не closure

## Решение

Никогда не помечать failing tests как "pre-existing" в `.planning/phases/*/SUMMARY.md` или других closure-документах **без written root-cause** в той же строке/абзаце.

Минимальный шаблон допустимого pre-existing label:

> N pre-existing failure(s): `<test_path>::<test_name>` — root cause: `<one-sentence WHY>` (commit ref: `<hash>`, repro: `<command>`)

Если не можешь заполнить root cause — test НЕ pre-existing, он **untriaged**. Открой `quick-task` через `/gsd-quick` для investigation, не маркируй failed test "documented" пока не понятна причина.

## Почему

В ga_crawler Phase 8 `08-01-SUMMARY.md:36` написано:

```
Test suite: 801 passed / 1 skipped / 2 pre-existing failures
(test_cli_deliver.py x2 — confirmed pre-existing via git stash test against HEAD baseline)
```

Git-stash baseline check confirmed что тесты падают и на HEAD — но **не объяснил WHY**. На самом деле:
- `test_deliver_run_missing_token_exits_3` падал потому что `cli.py:271 load_dotenv(override=False)` re-загружал `.env` в subprocess
- Каждый запуск subprocess отправлял 35-байт fake-xlsx fixture в operator's личный Telegram
- ≥11 leaks накопилось за ~1 день до discovery (commit `43dbfd7`)

Mislabel inherited verbatim в `08-02-SUMMARY` + `08-04-SUMMARY` — pattern propagated через subsequent phase closures.

См. [[fake-xlsx в личный Telegram — load_dotenv walks от file, не cwd]].

## Применение

### Когда test fails и хочется label "pre-existing"

1. **Stop**. Запиши root cause одной строкой.
   - "Test fails потому что X" — если не получается, test untriaged.
2. **Если test exercises side effects** (subprocess CLI / network I/O / file writes / external API) — treat as **live bug suspect**, не benign.
   - Эти тесты могут продолжать **emit реальные side effects** на каждом CI run.
   - 11 fake-xlsx файлов в operator's Telegram — это что было silently emit'нуто за ~1 день, пока test "documented broken".
3. **Если defer investigation** — file quick-task с:
   - One-line repro command
   - Acceptance criterion (что должно быть true после fix)
   - НЕ хорони в SUMMARY string.

### Phrases которые требуют scrutiny

- "pre-existing failure"
- "known flaky"
- "documented broken"
- "confirmed via baseline check" (без explicit WHY)
- "unrelated to this phase" (тоже без explanation)
- "fails on HEAD too" (НЕ root cause)

Каждое — red flag. Treat as work item, not closure.

### Acceptable patterns

✅ `test_x fails — root cause: deprecated API in Y library, fix in v2.0 (commit abc123, repro: pytest -k test_x)`
✅ `test_y skipped — requires live Telegram bot, exercised manually in operator UAT per HUMAN-UAT.md SC#5`
❌ `2 pre-existing test_cli_deliver failures — unrelated`
❌ `1 known flaky test`

## Ограничения

- Этот pattern строго про closure-документы (`.planning/phases/*/SUMMARY.md`, `.planning/quick/*/SUMMARY.md`, retrospectives). НЕ применяется к conversational chat / brainstorming notes / scratch debug logs.
- Cosmetic test failures (formatting, typos) могут быть legitимно pre-existing — but root cause всё равно нужен.

## Process change

`.planning/STATE.md` updated 2026-05-14 to flag `08-01-SUMMARY` + `08-02-SUMMARY` + `08-04-SUMMARY` "pre-existing failures" annotations как factually wrong — superseded by `.planning/quick/20260514-cli-dotenv-leak/SUMMARY.md`.

Phase 8 W3 (Plan 08-05 doc cascade) should add this pattern to project hazards doc.

## Связанные

- [[fake-xlsx в личный Telegram — load_dotenv walks от file, не cwd]] (debugging note для incident, который motivated этот pattern)
- [[find_dotenv usecwd=True — anchor dotenv discovery at cwd для test isolation]] (hotfix decision)
- `.planning/quick/20260514-cli-dotenv-leak/SUMMARY.md`
- `.planning/STATE.md` (mislabel correction note)
