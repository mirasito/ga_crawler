---
tags: [session, phase-8, wave-1, parser-bugs, hotfix, data-egress, dotenv, milestone-v1.1, quick-task]
date: 2026-05-14
phase: 8
wave: 1
verdict: W1-shipped-plus-hotfix
session_type: execute-phase-w1 + quick-task-hotfix
commits: 6
---

# 2026-05-14 — Phase 8 W1 GREEN shipped + cli.py dotenv-leak hotfix closes data egress

Resume после `/clear` поднял Phase 8 W1 в partial-GREEN состоянии (RED commits landed, GREEN unstaged). Закрыл оба плана W1 атомарными коммитами per TDD discipline. **Параллельно user сообщил баг: 11 файлов `2026-W19*.xlsx` в Telegram Desktop не открываются — OfficeImportErrorDomain Error 912**. Расследование вскрыло **активный канал data egress**: subprocess-тесты `test_cli_deliver.py` неявно подгружали реальный `.env` и доставляли fake-xlsx fixtures в operator's личный Telegram (chat_id=986299192). Бaг был замаскирован под "pre-existing test failures" в 08-01-SUMMARY с самого старта Phase 8. Hotfix через quick-task `/gsd-quick` workflow. Финал: **suite 822/2-failed → 825/0-failed**.

## Pipeline execution

| Шаг | Коммит | Что |
|---|---|---|
| 1. Resume diagnosis | — | `git status` + `git log` показали W1 partial-state: 08-02 RED (`9df9c55`) + 08-04 RED (`214e8ee`) landed, GREEN unstaged |
| 2. Plan 08-04 GREEN commit | `cc40621` | viled `_extract_volume_from_nextdata(a0)` helper + callsite + anchor-test flip; 38/38 viled tests pass |
| 3. selectolax bump commit | `f8fa492` | `>=0.3,<0.4` → `>=0.4.7,<0.5`; installed 0.4.8 |
| 4. Plan 08-02 GREEN implementation | — | Helper insertion в `goldapple_microdata.py:270`; **2 deviations from PATTERNS.md** (см. ниже) |
| 5. Plan 08-02 GREEN commit | `cf247b3` | goldapple `_extract_volume_block(html)`; 7/7 volume tests pass; full suite 822 passed / 2 failed |
| 6. W1 SUMMARY commit | `049999b` | `08-02-SUMMARY.md` + `08-04-SUMMARY.md` |
| 7. **User reports Excel bug** | — | `2026-W19 (9).xlsx` не открывается; **file size = 35 байт** (раскрытие: file content = `PKfake-xlsx-content-for-cli-tests` literal) |
| 8. Root-cause investigation | — | grep test fixtures: only `test_cli_deliver.py:106` + `test_weekly_run_with_delivery.py:336` + `conftest.py:652` write fake-xlsx literal. cli.py:271 `load_dotenv(override=False)` walks UP from `__file__`, не cwd → subprocess tests с stripped TG_* env-vars всё равно re-загружают `.env` |
| 9. Reproduce | — | `uv run pytest test_deliver_run_missing_token_exits_3 -v` показал `delivery_status=delivered_business, business_document_message_id=23` — тест прямо в момент репро отправил ещё один файл в чат |
| 10. /gsd-quick hotfix | `43dbfd7` | `find_dotenv(usecwd=True)` anchor + canary regression test |
| 11. Post-mortem doc | `a9c2292` | quick-task SUMMARY + STATE.md mislabel correction (08-01-SUMMARY line 36 wrong — superseded) |

## Critical findings

### Finding 1 (load-bearing): `load_dotenv()` без явного пути ищет от `__file__`, не от cwd

`python-dotenv`'s `find_dotenv()` default behavior walks UP from `inspect.getfile(parent_frame)` location. Для CLI module под `src/<pkg>/cli.py` это **всегда** находит project root's `.env` независимо от того, откуда запущен subprocess.

В ga_crawler это вызвало **silent data egress**:
- Тесты `test_deliver_run_missing_token_exits_3` + `test_unicode_stdout_safe_on_windows` стрипали `TG_*` из subprocess `env=`, ожидая exit code 3
- Subprocess CLI после старта вызывал `load_dotenv(override=False)` → находил project root `.env` → re-загружал реальный `TG_BOT_TOKEN` + `TG_BUSINESS_CHAT_ID=986299192`
- CLI продолжал в delivery happy path → отправлял 35-байтную fake-xlsx в operator's личный Telegram чат
- **≥11 file deliveries confirmed** (file IDs `2026-W19.xlsx` через `2026-W19 (10).xlsx` в Downloads/Telegram Desktop, все `PK\x03\x04fake-xlsx-content-for-cli-tests` literals)
- 18.4-second test runtime соответствует Telegram retry+send latency

Fix: `find_dotenv(usecwd=True)` anchors поиск на `os.getcwd()`. Tests с `cwd=tmp_path` (вне проекта) → walk заканчивается на `C:\` → returns `""` → load_dotenv no-op. Production operator `cd /opt/ga_crawler && python -m ...` → cwd=project root → `.env` нормально загружается.

### Finding 2: 08-01-SUMMARY line 36 факт-неверен — "pre-existing failures" mislabeling маскировал бaг

```
Test suite: 801 passed / 1 skipped / 2 pre-existing failures
(test_cli_deliver.py x2 — confirmed pre-existing via git stash test against HEAD baseline)
```

Git-stash baseline confirmed что тесты падают и на HEAD, но **не объяснил WHY**. На самом деле оба теста были активным data-egress каналом. Mislabel inherited verbatim в 08-02-SUMMARY + 08-04-SUMMARY.

Lesson saved в memory (`feedback_pre_existing_failures_smell.md`): "pre-existing failures" annotation без written root-cause = code smell. Особенно для тестов с subprocess/network/file-write side effects.

### Finding 3: 2 deviations from PATTERNS.md в Plan 08-02 GREEN — empirical fixture probe required

PATTERNS.md прескрипировал:
1. Selector `'div:lexbor-contains("ОБЪЁМ" i)'` (uppercase + `i` flag for case-insensitive)
2. Strategy A sibling-walk for digit-bearing sibling

**Empirical probe vs live fixtures show оба incorrect:**
1. **Lexbor's `i` flag byte-level для non-ASCII** — uppercase "ОБЪЁМ" с `i` flag НЕ матчит lowercase "объём" в live HTML (UTF-8: Ё=`D0 81` vs `D1 91`). Live HTML emits lowercase 25/25 в W0 shape-table. Fix: lowercase literal `"объём"` без `i` flag.
2. **Sibling-walk fails on Armani DOM shape** — Armani-style radio-group has label-then-radio-children где digits live deeper в DOM, не как direct siblings. Fix: ancestor-walk (max depth 3) до digit-bearing ancestor, extract first numeric token + unit из label, compose `f"{value} {unit}"` shape that `parse_volume` accepts.

`parse_volume` требует `<digit>{whitespace?}мл` adjacent. Probed manually — `"objём / мл50100"` (unit before digits) and `"12объём / мл"` (digit before label-with-unit-at-end) ОБА fail. Только `"50 мл"` / `"50мл"` shapes pass.

## Что зашиплено

### Phase 8 W1

- `src/ga_crawler/parsers/viled_nextdata.py` — `_extract_volume_from_nextdata(a0)` helper (line 114) + callsite (line 251) + `__all__` export
- `src/ga_crawler/parsers/goldapple_microdata.py` — `_extract_volume_block(html)` helper (line 270) с LOCAL Lexbor import + callsite (line 418)
- `pyproject.toml` + `uv.lock` — selectolax 0.4.8
- `tests/parsers/test_viled_volume_from_nextdata.py` (RED+GREEN landed in earlier commits)
- `tests/parsers/test_goldapple_volume_block.py` (RED+GREEN landed in earlier commits)
- `tests/unit/test_viled_nextdata_parser.py` — anchor-test rename + D-812 flip
- `.planning/phases/08-parser-bug-fixes/08-02-SUMMARY.md` + `08-04-SUMMARY.md`

### Quick-task 20260514-cli-dotenv-leak

- `src/ga_crawler/cli.py:257-285` — `find_dotenv(usecwd=True)` + guarded `load_dotenv`
- `tests/integration/test_cli_deliver.py:321-369` — `test_cli_does_not_load_project_dotenv_when_cwd_outside_tree` canary
- `.planning/quick/20260514-cli-dotenv-leak/PLAN.md` + `SUMMARY.md`
- `.planning/STATE.md` — Quick Tasks Completed table + mislabel correction note

## Stats

- **6 atomic commits** (4 на Phase 8 W1 + 2 на quick-task hotfix)
- **Suite delta:** 822 passed / 2 failed → **825 passed / 0 failed** (-m "not live"). Net +3: +2 ex-failing tests now pass + 1 new canary.
- **Test count:** 803 baseline → 825 (+22 over Phase 8 to date; +5 goldapple volume + +11 viled volume + +1 hotfix canary + tooling overhead).
- **Wall-clock:** ~90 min total (~25 min Phase 8 W1 + ~25 min Excel bug investigation + ~15 min hotfix + ~25 min docs/memory)

## Memory updates

Saved 2 new entries:
- `hazard_dotenv_walks_from_file.md` — load_dotenv default walks `__file__`, не cwd
- `feedback_pre_existing_failures_smell.md` — "pre-existing failures" annotations нужны written root-cause

## Deviations from plan

1. **PATTERNS.md Plan 08-02 — selector form** — empirical probe vs live HTML forced lowercase literal + ancestor-walk strategy (PATTERNS.md said uppercase + sibling-walk).
2. **08-01-SUMMARY annotation correction** — "pre-existing failures" label removed; superseded by hotfix SUMMARY.
3. **gsd-sdk not installed** — full `/gsd-quick` workflow требует `gsd-sdk` в PATH. Executed spirit вручную (created `.planning/quick/...` dir + PLAN.md + SUMMARY.md + STATE.md row, ran atomic commits с TDD discipline).

## Next

- **Phase 8 W2 (Plan 08-03 goldapple brand+name h1-spans pivot)** — ~10 min execute via `/gsd-execute-phase 8 --wave 2` или вручную (helper insertion + callsite rewrite — Plan 08-01 SKILL.md документирует точные CSS selectors). Plan 08-03 PLAN.md still mentions microdata premise — executor MUST read SKILL.md для pivot.
- **Phase 8 W3 (Plan 08-05 null-rate gate + SMOKE rotation + doc cascade)** — sequenced after W2. Doc cascade should add 3 hazards из hotfix:
  1. `load_dotenv()` без явного пути walks от `__file__`
  2. "Pre-existing failures" annotation pattern needs explicit root-cause
  3. `.env` с реальными credentials + subprocess tests = contamination hazard

## Related

- [[Текущие приоритеты — Phase 8 W1 done, W2 next]] (new, replaces W0-done priorities)
- ~~[[Текущие приоритеты — Phase 8 W0 done, Wave 1-3 next]]~~ (superseded — W1 done)
- [[2026-05-14 — Phase 8 W0 spike done, microdata премиса invalidated — pivot к h1-spans extraction]] (immediate predecessor session)
- [[fake-xlsx в личный Telegram — load_dotenv walks от file, не cwd]] (new debugging note)
- [[find_dotenv usecwd=True — anchor dotenv discovery at cwd для test isolation]] (new decision note)
- [[Goldapple PDP renders volume в structured flexbox blok, не в microdata]] (Plan 08-02 strategy — refined этой сессией)
- [[viled Размер JSON path — nested attributes 0 attributes, не item attributes]] (Plan 08-04 strategy — refined этой сессией)
- `.planning/quick/20260514-cli-dotenv-leak/SUMMARY.md` — quick-task post-mortem
- `.planning/phases/08-parser-bug-fixes/08-02-SUMMARY.md` — Plan 08-02 W1 closure
- `.planning/phases/08-parser-bug-fixes/08-04-SUMMARY.md` — Plan 08-04 W1 closure

---

**Bottom line:** W1 закрыт (oба parser fixes shipped) + **активный data-egress канал найден и пофикшен**. Mislabeling "pre-existing failures" в 08-01-SUMMARY был root cause того, что bug маскировался 1+ день. 11 fake-xlsx файлов в personal Telegram — только тест-fixture bytes, **никаких customer data не утекло**. Suite зелёный 825/0. Готов W2 (Plan 08-03) — h1-spans pivot per W0 SKILL.md.
