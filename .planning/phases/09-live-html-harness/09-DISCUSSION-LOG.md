# Phase 9: Live-HTML Harness — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 9-Live-HTML Harness
**Areas discussed:** Wave-структура + P2 bundling, Pydantic RawProduct write-boundary семантика, Live-drift тест интеграция с cron, PII canary + 50 MB size budget enforcement

---

## Wave-структура + P2 bundling

### Q1: Phase 9 wave structure (как разбиваем 6 TEST-HARNESS реквов на планы?)

| Option | Description | Selected |
|--------|-------------|----------|
| **3 plans, P2 GO/NO-GO после W1** | 09-01 = TH-01+02 (syrupy + fixture convention). 09-02 = TH-03+06 parallel. 09-03 = P2 bundle ИЛИ defer doc cascade. | ✓ |
| 4 plans, P2 split | 09-01 = TH-01 alone. 09-02 = TH-02 alone. 09-03 = TH-03+06 parallel. 09-04 = P2 conditional. Больше granularity / больше orchestration overhead. | |
| 2 plans, всё must-have в одном блоке | 09-01 = TH-01..03+06 одним блоком (крупный plan). 09-02 = P2. Минимум orchestration но blast-radius одного плана растёт. | |
| 5 plans, по одному на must-have req | 09-01..09-04 = TH-01/02/03/06 каждый отдельно. 09-05 = P2. Максимум granularity но over-engineering для 6-req phase. | |

**User's choice:** 3 plans, P2 GO/NO-GO после W1
**Notes:** Recommended option выбран — соответствует Phase 8 wave shape (W0 sequential / W1 parallel / W2 sequential).

### Q2: P2 bundle GO/NO-GO criterion на W1→W2 checkpoint?

| Option | Description | Selected |
|--------|-------------|----------|
| **Time-budget: «elapsed W0+W1 < 8h → GO»** | Просто, объяснимо. Измеряется по git commit timestamps. >8h → 09-03 пишет defer-to-v1.2 doc cascade. User может override. | ✓ |
| Test-count delta: «W0+W1 дали ≤+12 тестов → GO» | Прокси для «implementation проще ожидаемого». Плохо коррелирует со сложностью. | |
| Always GO (P2 всегда bundle'ится) | Отменяет «P2 cheap-bundle» опцию из D-810; противоречит STATE.md locked decision. | |
| Always DEFER (TH-04/05 в v1.2 upfront) | Сокращает Phase 9 до 4 reqs но теряем brand-coverage canary критичный для STEREOTYPE/Armani shape-drift detection. | |

**User's choice:** Time-budget < 8h elapsed W0+W1 → GO

---

## Pydantic RawProduct write-boundary семантика (TEST-HARNESS-06)

### Q3: Где валидируется Pydantic `RawProduct` и что происходит при violation?

| Option | Description | Selected |
|--------|-------------|----------|
| **SqliteSnapshotWriter.persist boundary, hard-raise per-SKU + run-fail на >5% reject rate** | REQUIREMENTS verbatim. Pydantic raise per-SKU, increment `rejected_count`. `rejected_rate > 5%` → run failed reason `schema_validation_rejected_rate`. Ортогонально PARSE-FIX-04. | ✓ |
| Dispatcher boundary (parsers/dispatcher.py:51), soft-fail log + skip | Раньше в pipeline. Нарушает REQUIREMENTS verbatim и теряет fail-loud discipline. | |
| SqliteSnapshotWriter, hard-raise НА ПЕРВОМ violating SKU (run-abort) | Максимально fail-loud, но один legitimate None (Contre-Jour) положит весь run. | |
| Validation на SqliteSnapshotWriter, no run-fail — только stats key + log | Мягкий вариант. Теряется «defense-in-depth» — PARSE-FIX-04 уже жёсткий gate; здесь нужен ортогональный cascade. | |

**User's choice:** SqliteSnapshotWriter.persist boundary, hard-raise per-SKU + run-fail на >5% reject rate

### Q4: RawProduct поля — required vs optional для обоих retailer'ов?

| Option | Description | Selected |
|--------|-------------|----------|
| **Per-retailer schema: goldapple strict, viled relaxed** | GoldappleRawProduct: brand+volume_raw+name+price все REQUIRED NonEmptyStr/Decimal>0. ViledRawProduct: brand+name+price REQUIRED, volume_raw: NonEmptyStr \| None. Базовый RawProductBase + 2 subclass'а. | ✓ |
| Unified schema, всё Optional, ловим только типы | Один `RawProduct` на обоих, всё Optional. Теряет 90% ценности boundary'я. | |
| Strict unified: всё NonEmptyStr для обоих retailer'ов | Один schema, всё obligatory. Выбьет viled SKU без volume в reject bucket → false-positive run-fail на legitimate data. | |
| Per-retailer + custom validator для viled None-allow-list | Per-retailer + brand whitelist «этим можно None volume». Over-engineering для v1.1. | |

**User's choice:** Per-retailer schema (goldapple strict, viled relaxed)

---

## Live-drift тест интеграция с cron (TEST-HARNESS-03)

### Q5: Как `pytest -m live` запускается в проде?

| Option | Description | Selected |
|--------|-------------|----------|
| **Operator-only opt-in, README §8** | Manual run pre-deploy / post-suspected-drift. ARCH Open Q2 рекомендует. cron weekly-run.sh не меняется. Drift пишет `parser-drift-YYYY-MM-DD.md`. | ✓ |
| Auto-attached к weekly cron как 7-й шаг с diff-to-ops | weekly-run.sh запускает pytest -m live + git-diff + ops-chat alert. PITFALLS #2 это предлагает но расширяет cron blast radius + Camoufox 30s+ в cron path = flakes положат weekly-run. | |
| Separate cron entry (суббота 20:00) + Telegram ops alert | Отдельный cron субботы вечером. Operator-level concern, Phase 11 ещё не лёг. Phase 9 преждевременно. | |
| GitHub Action weekly, игнорирует VPS | Schedule в .github/workflows/. Camoufox + KZ-IP делает либо self-hosted (= VPS) либо EU-IP geo-fake ломает Phase 7 setup. | |

**User's choice:** Operator-only opt-in, README §8

### Q6: Что assertит `tests/live/test_parser_drift.py`?

| Option | Description | Selected |
|--------|-------------|----------|
| **Двух-режимный: cassette-replay default + явный --refresh флаг** | Default читает frozen `_live-*.html` + asserts invariants. `--refresh-live` re-fetch'ит Camoufox + syrupy assert + sidecar update. Stale fixture >30 дней = warning. | ✓ |
| Всегда live-fetch, replay = отдельный marker | Каждый -m live → live HTTP. Replay = синтетические. Нарушает snapshot pattern. | |
| Cassette-replay only, refresh ручно через capture-fixtures CLI | Pytest -m live чисто против frozen. Live-fetch в TH-05 CLI. Без P2 = no drift detection. | |
| Live-fetch + diff vs cassette всегда (no flag) | Каждый запуск 30+s Camoufox + bans risk. PITFALLS #2 рекомендует в weekly batch не per-pytest. | |

**User's choice:** Двух-режимный (cassette-replay default + --refresh-live flag)

---

## PII canary + 50 MB size budget enforcement

### Q7: Где срабатывают PII canary и 50 MB size guard?

| Option | Description | Selected |
|--------|-------------|----------|
| **Pytest fixture-validator при load + conftest test «all fixtures clean»** | (1) conftest `_assert_fixture_clean(path)` на любой `_live-*.html` load → pytest.fail. (2) `tests/test_live_fixtures_pii_canary.py` iterates all fixtures, regex-scan + size-check. Срабатывает в default pytest. capture-fixtures CLI scrub'ит ДО записи (если P2 GO). | ✓ |
| Pre-commit hook только | .pre-commit-config.yaml. Operator может --no-verify; не ловит при syrupy --snapshot-update в dev cycle; project ещё нет pre-commit infra. | |
| capture-fixtures CLI скрабит + trust-the-CLI | Если P2 NO-GO — нет CLI и нет canary. Operator может dropp'ать HTML вручную (Phase 8 так и делал). | |
| CI-only check (GitHub Action) | v1.1 GHA infra не настроена. Ловит только после push. Operator работает прямо на VPS — GHA не в его workflow'е. | |

**User's choice:** Pytest fixture-validator + standalone conftest canary test

---

## Claude's Discretion

- Точное имя файла для `HTMLSnapshotExtension` class location — `tests/conftest.py` если < 30 LOC иначе dedicated module
- Точное имя файла для Pydantic schemas — `storage/schemas.py` (новый) ИЛИ extend `storage/types.py` (planner inspects)
- Sidecar JSON helper модуль ИЛИ inline в conftest — planner решает по LOC
- Точная регулярка для UUID hc-ping detection — стандартная UUID v4
- `parser-drift-YYYY-MM-DD.md` template shape — следует Phase 1 spike memo convention

## Deferred Ideas

- Auto-scheduled live-drift cron (weekly refresh + ops-chat diff alert) → v1.2 if Phase 11 production evidence warrants
- GitHub Action CI live-tests workflow → v1.2 (self-hosted runner + Camoufox/KZ-IP required)
- `@pytest.mark.flaky` ban grep canary → v1.2 (premature; no flake-decorated tests exist yet)
- `parser-drift-YYYY-MM-DD.md` auto-classifier (LLM-driven) → v2
- Match-rate floor alert (SUMMARY.md "A5") → v2 backlog
- viled volume null-rate gate companion to PARSE-FIX-04 → v1.2 if post-deploy evidence warrants
- Separate cron entry для cassette refresh (Saturday 20:00 Almaty) → v1.2 reconsider if operator monthly-refresh slips
