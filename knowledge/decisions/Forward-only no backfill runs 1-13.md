---
tags: [decision, data, history, backfill, v1-1, matcher]
date: 2026-05-13
phase: v1.1-planning
status: locked
---

# Forward-only no backfill runs 1-13

## Утверждение

После fix парсеров в Phase 8, **НЕ перепарсить** runs 1-13 ретроактивно. Они остаются с broken `volume_norm` data и `match_count=0`. Только run #14+ получит правильные значения.

## Reasoning

### 1. HTML недоступен — backfill physically impossible

Snapshots-таблица хранит только **parsed fields** (`brand_norm`, `volume_norm`, `name_norm`, prices), не raw HTML. Repo не имеет HTML cache. Backfill матчера против run-13 data ничего не даст — `volume_raw` уже NULL в БД.

### 2. Matcher idempotent но input не изменится

`src/ga_crawler/matcher/strict_key.py` D-410: `build_matches_for_run` = idempotent `DELETE+INSERT` inside one `engine.begin()` transaction. Можно перезапустить matcher для старых runs — но он выдаст те же 0 matches потому что input snapshots не изменились.

### 3. Auto-suggest threshold rollover

`runner/gates.py:221 auto_suggest_threshold` берёт 4-week median и срабатывает после `n_auto_suggest_after_runs=4` (pyproject `[tool.ga_crawler.match].n_auto_suggest_after_runs`). По истории runs 1-13 = garbage, runs 14+ = clean. К run #17 история rolls — garbage уходит из window estimation natural.

### 4. История остаётся interpretable

Runs 1-13 — **legitimate historical record** того что "у нас был parser-bug тогда". Удаление этих записей замаскирует timeline когда баг был и когда починили.

## Implication

`.planning/MILESTONES.md` должен получить one-line annotation в Phase 10 (AUDIT-DEBT scope):

> Runs 1-13 (2026-05-05..2026-05-13) — pre-parser-fix; goldapple match-rate not meaningful. Fixed in Phase 8 (PARSE-FIX-01..05); first clean run = #14+.

## Alternative considered

- **Replay runs via `scripts/replay_runs.py`** — REJECTED. Скрипт fetch'ит ту же sitemap+URLs и snapshot'ит под новый `run_id`. Это fresh run, не true backfill. Стоит Camoufox crawl budget. Дает inflated stats baseline. Не рекомендуется. Defer.
- **DELETE FROM matches WHERE run_id<14** — REJECTED. Matches table не имеет fake данных — она пустая для goldapple просто потому что filter D-402 не пускает NULL volume. DELETE ничего не меняет.

## Sources

- `src/ga_crawler/matcher/strict_key.py:20-37` D-410 idempotency docstring
- `src/ga_crawler/runner/gates.py:221-239` auto_suggest_threshold + `gates.py:301` "NEVER auto-tunes"
- `pyproject.toml:90` `n_auto_suggest_after_runs = 4`
- `.planning/research/ARCHITECTURE.md` § C "Forward-only — no backfill"
