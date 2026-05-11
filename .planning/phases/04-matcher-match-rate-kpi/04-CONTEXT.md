# Phase 4: Matcher + Match-Rate KPI - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 строит **strict-key matcher** между viled и goldapple snapshots в пределах одного `run_id`. На вход — `v_current_snapshots` (Phase 2 schema, frozen Wave 0 Phase 3), на выход — новая таблица `matches` + ключевые stats-метрики (`match.count`, `match.rate`, `match.denominator`, `match.numerator`) в `runs.stats` через atomic `json_patch` (Pitfall 6 pattern). Денормализованная строка matches несёт всё, что нужно Phase 5 reporter'у без JOIN-back: brand_norm / name_norm / volume_norm + цены обоих ритейлеров + price_delta + price_delta_pct. Match-rate KPI считается по формуле REQUIREMENTS MATCH-03: `matches / viled_skus_with_brand_in_goldapple_brands × 100%` с фильтром comparable-only (`multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state ≠ 'DELISTED'`) — формула фиксируется С WEEK 1 как исторический baseline, изменение требует v2-migration. Sanity-gate `match_count > P` с seed P=20 + auto-suggest `0.7×4-week-median` после 4 runs (mirror D-201/D-308). Idempotency через `DELETE WHERE run_id=:N` + INSERT внутри одной транзакции — `matcher-run --run-id N` идемпотентен. Phase 4 НЕ строит Excel-отчёт (Phase 5), НЕ доставляет в Telegram (Phase 6), НЕ деплоит cron (Phase 7), НЕ меняет схему `runs` / `snapshots` (frozen Phase 2).

</domain>

<decisions>
## Implementation Decisions

### Matches table — schema + filtering (MATCH-01, MATCH-02)

- **D-401:** **Денормализованный schema + N→1 keep-all.** Таблица `matches` шире, чем минимальный REQ MATCH-02:
  ```
  matches(
    run_id           INTEGER NOT NULL,        -- PK part, FK runs.run_id
    viled_sku        TEXT NOT NULL,           -- PK part, FK snapshots(run_id,'viled',sku_id)
    goldapple_sku    TEXT NOT NULL,           -- PK part, FK snapshots(run_id,'goldapple',sku_id)
    brand_norm       TEXT NOT NULL,           -- денормализовано из snapshots для reporter
    name_norm        TEXT NOT NULL,           -- денормализовано
    volume_norm      TEXT NOT NULL,           -- денормализовано (NULL отфильтрован WHERE)
    viled_price      INTEGER NOT NULL,        -- viled current_price (KZT)
    goldapple_price  INTEGER NOT NULL,        -- goldapple current_price (KZT)
    viled_was_price  INTEGER,                 -- nullable
    goldapple_was_price INTEGER,              -- nullable
    price_delta      INTEGER NOT NULL,        -- goldapple_price − viled_price (signed)
    price_delta_pct  REAL NOT NULL,           -- price_delta / viled_price × 100, 2 знака
    matched_at       TIMESTAMP NOT NULL,      -- DEFAULT CURRENT_TIMESTAMP
    PRIMARY KEY (run_id, viled_sku, goldapple_sku)
  )
  ```
  Phase 5 reporter не делает join-back — все колонки уже в matches. PK composite — `(run_id, viled_sku, goldapple_sku)` — гарантирует уникальность пары и поддерживает N→1.

- **D-402:** **Фильтры на матчинг (numerator)** — symmetric для обоих ритейлеров:
  ```sql
  WHERE v.retailer='viled'    AND v.run_id=:run_id AND v.multipack_flag=0 AND v.volume_norm IS NOT NULL AND v.stock_state != 'DELISTED'
    AND g.retailer='goldapple' AND g.run_id=:run_id AND g.multipack_flag=0 AND g.volume_norm IS NOT NULL AND g.stock_state != 'DELISTED'
    AND v.brand_norm = g.brand_norm
    AND v.name_norm  = g.name_norm
    AND v.volume_norm = g.volume_norm
  ```
  - `multipack_flag=0`: D-215 multipack flagged-excluded из price-per-unit-comparison (PROJECT.md NORM-04 inherits)
  - `volume_norm IS NOT NULL`: PARSE-04 unparseable volume → строка остаётся в snapshots для аудита, но не матчится (strict-key требует volume)
  - `stock_state != 'DELISTED'`: цена DELISTED-строки stale-by-definition; OUT_OF_STOCK / UNAVAILABLE / IN_STOCK / UNKNOWN — оставляем (цена сохранена в snapshot, comparison валиден)

- **D-403:** **N→1 keep-all.** При нескольких goldapple SKU с одинаковым `(brand_norm, name_norm, volume_norm)`, который совпадает с одним viled SKU — пишем все пары. Excel-reporter (Phase 5) видит дубликаты viled_sku в `Per-SKU deltas` листе и может (а) показать все варианты, (б) дедуплицировать по min-price на уровне рендера. Не теряем сигнал «у goldapple несколько вариантов» на уровне БД.

### Match-rate denominator (MATCH-03, KPI fixed week 1)

- **D-404:** **Denominator = comparable viled SKUs в брендах с goldapple-присутствием.**
  ```sql
  denominator = (
    SELECT COUNT(*) FROM snapshots v
    WHERE v.retailer='viled' AND v.run_id=:run_id
      AND v.multipack_flag=0
      AND v.volume_norm IS NOT NULL
      AND v.stock_state != 'DELISTED'
      AND v.brand_norm IN (
        SELECT DISTINCT g.brand_norm FROM snapshots g
        WHERE g.retailer='goldapple' AND g.run_id=:run_id
      )
  )
  ```
  Symmetric с numerator-фильтром (D-402). Знаменатель = "сколько viled-SKU **могли** быть сматчены". Match-rate = «эффективность нормализации в матчабельном подмножестве».

- **D-405:** **`match.rate` хранится как REAL в `runs.stats` с 2 знаками после запятой** (например `42.31`, percent points). Numerator + denominator также пишутся в stats для прозрачности расчёта при ручном аудите: `match.numerator`, `match.denominator`, `match.rate`. KPI с week 1 — формула фиксируется в коде через regression-test на synthetic fixture (matcher не должен поменять формулу без обновления fixture).

### Sanity-gate P (MATCH-04)

- **D-406:** **Seed P=20 static, auto-suggest `0.7×4-week-median` после 4 успешных runs** — mirror D-201 (viled N=100) и D-308 (goldapple M=1000) pattern. Обоснование P=20: catastrophic-failure detector. Spike не дал empirical baseline matches (Phase 1 был про anti-bot, не про match-rate). Грубо: ~60-300 viled comparable SKU × низкий strict-key match-rate v1 (10-30% типично без fuzzy) = ожидаем 10-100 matches/week. P=20 = ~30% от консервативного ожидаемого минимума 60 — поймает «normalizer сломан» или «один ритейлер пустой», но не false-positive на здоровом low-coverage старте.

- **D-407:** **Auto-suggest mechanic 100% переиспользует `runner/gates.py::auto_suggest_threshold(history, factor=0.7, min_runs=4)`** — уже retailer-agnostic после Phase 2 D-203 рефактора. Phase 4 вызывает с `history = SELECT match.count FROM runs WHERE status='success' ORDER BY run_id DESC LIMIT 4`. Аналогично D-310: оператор получает ops-Telegram `new P-rec for matcher: 0.7 × 4-week-median match_count = X` после каждого успешного run с 5-й недели; **никогда auto-tune** — оператор подтверждает PR в `pyproject.toml`. Зашита: silent drift вниз = silent KPI degradation = ложно-успешный отчёт. P-PR обязателен.

- **D-408:** **Storage: `pyproject.toml [tool.ga_crawler.match]` ключ `sanity_gate_p=20`** — namespace consistent с `[tool.ga_crawler.crawl.viled]` и `[tool.ga_crawler.crawl.goldapple]`. CLI override `--sanity-gate-p N` для recovery / эксперимента.

- **D-409:** **Gate-failure semantics**: `match_count <= P` → `run_writer.fail(run_id, reason='match_count_below_threshold:{count}<{threshold}')`. matches rows **всё равно остаются** в БД (audit-trail invariant — mirror DATA-03 immutable + D-218 gate-fail-but-snapshot-persists). Downstream (Phase 6 delivery) увидит `runs.status='failed'` и пропустит business-чат.

### Idempotency + failed-crawl + CLI shape (MATCH-01..04 ortho)

- **D-410:** **Idempotency = DELETE-and-reinsert внутри одной SQLite transaction**:
  ```python
  with engine.begin() as conn:
      conn.execute("DELETE FROM matches WHERE run_id = :run_id", {"run_id": run_id})
      conn.execute("INSERT INTO matches (...) SELECT ... FROM snapshots v JOIN snapshots g ON ...", {...})
  ```
  Атомарно — либо все pre-existing matches удалены + новые вставлены, либо ни одно из изменений. SC#4 (idempotent re-run) удовлетворён: повторный вызов на тот же `run_id` производит **те же** matches rows (deterministic SQL JOIN на immutable snapshots = same output). Перевыполнение в течение **активной транзакции** другим процессом блокируется WAL writer-lock.

- **D-411:** **Failed-crawl skip protocol**: matcher проверяет `SELECT status FROM runs WHERE run_id=:run_id`; если `status='failed'` или `status='in_progress'` для обоих retailer'ов unknown (т.е. до завершения crawls), matcher **skip-ит** с structured-log warning `match_skipped_failed_run` + counter в `runs.stats.match.skipped_reason`. **Не пишет** zero-match row (это сбивает auto-suggest history). Если виled status='success' но goldapple status='failed' (или наоборот) — тоже skip: incomplete data, не считается representative run.

- **D-412:** **CLI shape — standalone subcommand + main_run integration**:
  ```
  python -m ga_crawler matcher-run --run-id N        # standalone, idempotent re-run на existing snapshots
  python -m ga_crawler weekly-run                    # main_run.py: viled → goldapple → matcher (D-411 skip-if-failed)
  ```
  Standalone subcommand нужен для recovery: если snapshots OK но matcher упал из-за бага — оператор фиксит код и `matcher-run --run-id N` без перекраула 4 часов. Mirror Phase 3 `goldapple-smoke` / `goldapple-run` subcommand pattern.

### Module structure + stats namespace

- **D-413:** **Module layout** (mirror D-213 retailer-split pattern):
  ```
  src/ga_crawler/
    matcher/
      __init__.py
      strict_key.py         # NEW: SQL JOIN builder, denominator query, gate primitives
      stats.py              # NEW: MatchStatsBuilder("match.*" namespace, mirror Goldapple/ViledStatsBuilder)
    runners/
      matcher_run.py        # NEW: orchestrator (read status → JOIN → INSERT → patch_stats → gate → finalize)
      main_run.py           # AMEND: добавить matcher step после goldapple_run
    storage/
      sqlite.py             # AMEND: добавить Match SQLModel table + init_db создаёт matches
  ```

- **D-414:** **Stats namespace `match.*`** — exactly mirror Phase 3 `goldapple.*` + Phase 2 `viled.*` namespace pattern. `MatchStatsBuilder` enforces `match.` prefix via `StatsNamespaceError` (refactor base class `NamespaceStatsBuilder(prefix: str)` — выйдет из Phase 4 как побочный продукт, mirror D-203 retailer-agnostic refactor). Stats keys (canonical, заморожены тут чтобы Phase 5 reporter знал что читать):
  - `match.count` — int, числитель (rows in matches WHERE run_id=:N)
  - `match.rate` — REAL, percent points с 2 знаками (e.g. `42.31`)
  - `match.numerator` — int, == match.count (явный дубль для прозрачности)
  - `match.denominator` — int, comparable viled count в brand-overlap
  - `match.brand_overlap_count` — int, COUNT(DISTINCT brand_norm) пересечения
  - `match.viled_comparable_count` — int, viled SKU после фильтра multipack/volume/DELISTED (для аудита)
  - `match.goldapple_comparable_count` — int, аналогично goldapple-side
  - `match.skipped_reason` — str OR null, "failed_upstream" / "in_progress_upstream" / null если выполнился
  - `match.threshold_p` — int, applied threshold value (D-408)
  - `match.gate_passed` — bool

### DB schema migration

- **D-415:** **Phase 4 НЕ добавляет alembic** — D-220 inherited. matches table создаётся через `SQLModel.metadata.create_all` (idempotent `CREATE TABLE IF NOT EXISTS`). Существующий `init_db()` в `storage/sqlite.py` дополняется: Match class зарегистрирован в SQLModel.metadata, `init_db` обнаружит и создаст. **Existing DBs** (после Phase 2/3 deploys) на VPS не имеют matches table — первый запуск Phase 4 кода её создаст без миграции. Это безопасно: matches таблица новая, нет колоночных миграций.

### Claude's Discretion

- **Stock-state filter точный enum-set** — D-402 говорит `stock_state != 'DELISTED'`. Если empirically week 1 покажет что `UNKNOWN` snapshots массово (parse-degraded) — planner может ужесточить до `stock_state IN ('IN_STOCK','OUT_OF_STOCK','UNAVAILABLE')`. Week 1 baseline даст сигнал.
- **Precision price_delta_pct** — D-401 фиксирует REAL с 2 знаками; конкретно `ROUND(price_delta * 100.0 / viled_price, 2)` в SQL. Planner проверяет SQLite ROUND semantics.
- **Per-brand match-rate aggregation в stats** — REQUIREMENTS не требует. Если planner видит cheap win (e.g. `match.rate_by_brand` JSON) — добавить можно, но **не** в `runs.stats` (raсчёт по запросу в Phase 5 reporter). Default: skip; v2 territory (REPORT-V2-02).
- **Concurrency / async** — matcher это single SQL JOIN + INSERT внутри одной транзакции. NO async. Sync `with engine.begin():` block. Mirror viled sync-pattern (D-215).
- **Match-rate когда denominator=0** — edge case: viled brand-list ∩ goldapple brand-list = ∅. По формуле — division-by-zero. Default: writer записывает `match.rate=0.0` + `match.denominator=0` + warning-log `match_zero_denominator`. Gate D-409 не trip-ает (match_count=0 vs P=20 → fail на ОБЕИХ ветках → run failed). Consistent поведение.
- **Cron schedule для standalone matcher-run** — нет, не нужен. matcher-run — operator-driven recovery tool. main_run cron остаётся weekly (Phase 7).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — core value (weekly viled vs goldapple report), constraints §Matching strictness (strict-key v1, fuzzy = v2)
- `.planning/REQUIREMENTS.md` §Match (MATCH-01..04 active), §Data (DATA-01..06 frozen Phase 2), §Norm (NORM-01..06 frozen Phase 2), §Report (REPORT-04 consumes match_rate downstream)
- `.planning/ROADMAP.md` §"Phase 4: Matcher + Match-Rate KPI" — phase goal + 4 success criteria

### Prior phase context (decisions cascade)
- `.planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT.md` — Phase 2 frozen schema (Snapshot/Run SQLModel, `v_current_snapshots` VIEW, `RunWriter.patch_stats` atomic json_patch); D-201 viled sanity-gate-N + auto-suggest pattern (Phase 4 mirrors D-406..D-408); D-203 retailer-agnostic `auto_suggest_threshold` helper (Phase 4 reuses); D-213 module split per concern; D-214 storage in single `sqlite.py`; D-215 multipack excluded из price-per-unit (Phase 4 inherits D-402 filter); D-218 gate-fail-but-snapshot-persists invariant (Phase 4 inherits D-409 for matches); D-220 no alembic day 1; D-221 `v_current_snapshots` VIEW = single source of truth; D-222 test infra (in-memory SQLite + conftest mocks)
- `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` — Phase 3 frozen goldapple side; D-308/D-309/D-310 sanity-gate-M + auto-suggest + ops-Telegram pattern (Phase 4 D-406..D-408 mirror); D-211 stats namespace enforcement (Phase 4 `match.*` mirrors)
- `.planning/phases/01-goldapple-reconnaissance-spike/01-CONTEXT.md` — supplementary; не блокирует Phase 4 напрямую

### Research foundation
- `.planning/research/SUMMARY.md` — modular monolith, snapshot-table integration backbone
- `.planning/research/ARCHITECTURE.md` §"Major components", §"snapshots-table integration" — matcher = derived table, не affects crawler invariants
- `.planning/research/PITFALLS.md` — Pitfall 6 (atomic merge in runs.stats — Phase 4 reuses via patch_stats); Pitfall 9 (Protocol contract drift — Phase 4 НЕ trogает frozen interfaces.py Protocols, добавляет new Matcher type или прямой SQL)

### Frozen infrastructure (Phase 4 inputs)
- `src/ga_crawler/storage/sqlite.py` — Run + Snapshot SQLModel tables, `make_engine` WAL+PRAGMA, `init_db` idempotent schema bootstrap (Phase 4 ADDS Match model + augments init_db), `SqliteSnapshotWriter` append-only, `SqliteRunWriter.patch_stats(run_id, delta)` atomic json_patch (Phase 4 calls для `match.*` keys), `SqliteRunWriter.fail` / `finalize` lifecycle, `v_current_snapshots` VIEW (D-221)
- `src/ga_crawler/runner/gates.py` — `final_threshold_gate(count, threshold)` (D-203 retailer-agnostic — Phase 4 reuses для P-gate), `auto_suggest_threshold(history, factor=0.7, min_runs=4)` (D-203 retailer-agnostic — Phase 4 reuses)
- `src/ga_crawler/runner/stats.py` — GoldappleStatsBuilder + ViledStatsBuilder + StatsNamespaceError (Phase 4 adds MatchStatsBuilder с `match.*` namespace, либо рефакторит в base `NamespaceStatsBuilder(prefix)`)
- `src/ga_crawler/interfaces.py` — **FROZEN Wave 0 Phase 3** Protocols (Phase 4 НЕ изменяет; matcher не нуждается в new Protocol — это derived-table operation, не fetcher/parser)
- `src/ga_crawler/runners/main_run.py` — current orchestrator (Phase 2 + Phase 3 composition); Phase 4 amends добавлением matcher step post-goldapple
- `pyproject.toml` — current namespaces `[tool.ga_crawler.crawl.{retailer}]` + `[tool.ga_crawler.match]` нов; pinned deps (sqlmodel 0.0.38, pydantic 2.13.3, tenacity 9.1.4, pytest 8.4.2, pytest-asyncio 1.3.0)

### Test infrastructure (inherited)
- `tests/conftest.py` — 11 fixtures incl. `mock_brand_alias`, `mock_normalizer`, `mock_snapshot_writer`, `mock_run_writer`, `in_memory_sqlite_session` (Phase 2 D-222); Phase 4 inherits + adds: `synthetic_matched_snapshots` (paired viled+goldapple rows for JOIN tests), `match_rate_fixture` (denominator/numerator regression-canary).

### Project conventions
- `CLAUDE.md` (project root) §Storage SQLite vs Postgres (matcher SQL JOIN well within SQLite envelope), §Conventions, §Architecture

### Project state & accumulated decisions
- `.planning/STATE.md` — accumulated Key Decisions table; Phase 4 cascades on D-201/D-308 (sanity-gate pattern), D-211 (stats namespace), D-218 (gate-fail-but-snapshot-persists), D-220 (no alembic)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`runner/gates.py::final_threshold_gate(count, threshold)`** — retailer-agnostic после Phase 2 D-203 рефактора. Phase 4 вызывает с `final_threshold_gate(match_count, config.sanity_gate_p)`. Zero дополнительной работы.
- **`runner/gates.py::auto_suggest_threshold(history, factor=0.7, min_runs=4)`** — также retailer-agnostic. Phase 4 вызывает с `history = SELECT match.count FROM runs WHERE status='success' ORDER BY run_id DESC LIMIT 4`. Output → ops-Telegram message.
- **`runner/stats.py::StatsNamespaceError` + `GoldappleStatsBuilder` / `ViledStatsBuilder`** — паттерн namespace-enforced stats builder. Phase 4 либо (a) копирует паттерн в `MatchStatsBuilder("match.*")`, либо (b) рефакторит в base `NamespaceStatsBuilder(prefix)` с тремя сабклассами. Default: refactor (DRY win, low risk т.к. unit-tests покрывают существующие builders).
- **`storage/sqlite.py::SqliteRunWriter.patch_stats(run_id, delta)`** — atomic SQLite `json_patch` (Pitfall 6). Phase 4 calls для `match.*` keys. No collisions с `viled.*` / `goldapple.*`.
- **`storage/sqlite.py::Run` + `Snapshot` SQLModel tables** + `v_current_snapshots` VIEW (D-221) — input для matcher. NO modification.

### Established Patterns
- **Per-domain split**: D-213 retailer-split → Phase 4 mirrors как matcher-domain split (`matcher/`, `runners/matcher_run.py`). Symmetric.
- **Append-only + immutable** (DATA-03 inherits): matches тоже append-only per `run_id` через DELETE-and-reinsert внутри одного run (re-run same `run_id` идемпотентен; разные `run_id` дают разные rows).
- **`runs` lifecycle** (DATA-05): matcher НЕ создаёт runs row — она уже есть от Phase 2 crawler step. Только `patch_stats` для `match.*` keys + `fail` если gate-trip. Mirror Phase 3 D-309 «extends runs row, не создаёт».
- **Stats namespace enforcement** (Phase 3 D-211, refactored Phase 2 D-203): Phase 4 `MatchStatsBuilder` enforces `match.` prefix. Прямой `runs.stats[key]` write через builder, не bare dict.
- **Sanity-gate triplet** (D-201/D-308/D-406): static seed + auto-suggest after 4 runs + operator-PR (never auto-tune). 3-й retailer-domain экземпляр — паттерн закрепляется.
- **CLI subcommands** (mirror Phase 3 `goldapple-smoke` / `goldapple-run`): `matcher-run --run-id N` standalone + `weekly-run` (main_run composition). Phase 5/6/7 продолжат паттерн (`reporter-run`, `delivery-run`).

### Integration Points
- **Input ← `v_current_snapshots` VIEW** (Phase 2 schema): matcher читает обе стороны (viled + goldapple) одним SQL JOIN per current run_id.
- **Input ← `pyproject.toml [tool.ga_crawler.match] sanity_gate_p=20`**: new TOML namespace.
- **Output → `matches` table** (Phase 4 owns schema): D-401 денормализованная widely-keyed.
- **Output → `runs.stats.match.*` keys** через `patch_stats`: D-414 заморожены ключи. Phase 5 reporter consumes.
- **Output → `runs.status='failed'`** через `run_writer.fail` если P-gate trip: Phase 6 delivery видит failed status, скипает business-чат (DELIVER-03).
- **Output → ops-Telegram auto-suggest message**: D-407 mirror D-310. Phase 7 ops-playbook handles operator-PR workflow.
- **Output → Phase 5 reporter** consumes matches table + `runs.stats.match.*` напрямую. Никаких extra JOIN.
- **Output → CLI integration**: `__main__.py` / `cli.py` добавляется `matcher-run` subcommand.

### Open dependencies
None — Phase 4 fully unblocked. Phase 2 closed (snapshots schema frozen). Phase 3 closed (goldapple snapshots ship). Phase 4 — pure data-derivation phase, без новых fetcher/parser зависимостей.

</code_context>

<specifics>
## Specific Ideas

- **«KPI с week 1 = формула фиксируется навсегда»** (D-405) — match-rate fixture создаёт regression-canary, чтобы случайное изменение формулы (e.g. switch denominator на total viled) не прошло в код без явного обновления fixture. Защита historical baseline.
- **«N→1 keep-all, не теряем сигнал»** (D-403) — несколько goldapple-вариантов одного viled SKU — это commercial-signal (есть выбор по цене); reporter решает как показать.
- **«Никогда auto-tune sanity-gate P»** (D-407 mirror D-203/D-310) — silent KPI drift = silent business-decision corruption. PR обязателен.
- **«Symmetric filters numerator + denominator»** (D-402/-404) — иначе KPI lying: можно «улучшить» rate просто увеличив denominator-exclusions. Symmetric гарантирует честность.
- **«Standalone `matcher-run --run-id N` для recovery»** (D-412) — оператор фиксит matcher-bug и пересчитывает без 4ч перекраула.
- **«matches table = денормализованная»** (D-401) — Phase 5 reporter работает с одной таблицей, никаких JOIN-back. Production-debugging проще.

</specifics>

<deferred>
## Deferred Ideas

- **N→1 dedup по min-price в БД** — отвергнуто (D-403): теряем commercial-signal. Reporter дедуплицирует на этапе рендера если нужно.
- **`match.rate_by_brand` JSON в `runs.stats`** — отвергнуто на v1 (Claude's Discretion): расчёт on-demand в Phase 5 reporter. v2 (REPORT-V2-02 Brand-level aggregate sheet).
- **alembic migration для matches table** — отвергнуто (D-415 / D-220 inherited): CREATE TABLE IF NOT EXISTS достаточно; первая column-migration triggers alembic adoption.
- **Auto-tune P** — навсегда отвергнуто (D-407 contra). Только auto-suggest + operator-PR.
- **Fuzzy/rapidfuzz matching на v1** — отвергнуто (PROJECT.md §Matching strictness): v2 territory (REQ MATCH-V2-01). Phase 4 — строгий key.
- **Per-SKU manual override таблица** — v2 (REQ MATCH-V2-02). Если NORM-06 review queue не справляется — поднимать.
- **Mid-week matcher run** — out-of-scope: weekly cadence — это контракт PROJECT.md.
- **matcher для исторических runs (replay)** — `matcher-run --run-id N` уже работает для прошлых runs. Bulk-replay loop (`for id in 1..42: matcher-run --run-id $id`) — operator-driven shell, не нужен в коде.
- **Week-over-week price delta column в matches** — v2 (REPORT-V2-01). Phase 4 даёт single-run delta; cross-run delta — отдельная derivation в Phase 5 reporter если потребуется на v1.
- **Match-rate degradation alert при drop >10% от 4-week-average** — v2 (REPORT-V2-04). Phase 4 даёт baseline, alert — отдельный feature.
- **Поддержка multi-currency price_delta** — отвергнуто: оба ритейлера в KZT. Если когда-нибудь cross-currency — v2 + currency normalizer в Phase 2 modules.

### Reviewed Todos (not folded)
`todo match-phase 4` returned 0 matches — todos infrastructure не задействована для Phase 4 specifically.

</deferred>

---

*Phase: 4-matcher-match-rate-kpi*
*Context gathered: 2026-05-11*
*Decisions: D-401..D-415 (15 decisions). 4 areas discussed; все recommended-варианты приняты пользователем.*

## Action Items for Other Documents

The following changes propagate to other artifacts at next opportunity:

- **`.planning/REQUIREMENTS.md` MATCH-02**: amend "Результат записывается в таблицу `matches(run_id, viled_sku, goldapple_sku, price_delta, price_delta_pct)`" → "Результат записывается в денормализованную таблицу `matches(run_id, viled_sku, goldapple_sku, brand_norm, name_norm, volume_norm, viled_price, goldapple_price, viled_was_price, goldapple_was_price, price_delta, price_delta_pct, matched_at)` per D-401" — surface at planner Wave 0 verifies + amends.
- **`.planning/STATE.md`**: add to "Accumulated Key Decisions" — "Phase 4 match-rate KPI formula = `matches / viled_skus_with_brand_in_goldapple_brands × 100%` с фильтром comparable-only (multipack=0, volume_norm NOT NULL, stock_state != DELISTED) — symmetric numerator + denominator — формула frozen with week 1 baseline per D-404/-405" — surface at next phase transition.
