---
tags: [decision, validation, storage, schema-drift, defense-in-depth, v1-1, phase-9, pydantic]
date: 2026-05-14
phase: 9-contexted
status: locked
---

# Pydantic RawProduct validation at SqliteSnapshotWriter — 5% reject-rate gate orthogonal to PARSE-FIX-04

## Утверждение

В Phase 9 TEST-HARNESS-06 валидация Pydantic `RawProduct` schema'ы происходит на границе `SqliteSnapshotWriter.persist` — НЕ раньше (не на dispatcher), НЕ позже (не на reporter input). Per-SKU violation поднимает `ValidationError` через `model_validate(row)`, writer ловит и инкрементирует `runs.stats.schema_rejected_count`. Threshold `rejected_count / total_attempted > 0.05` (5%) → run помечается `failed` reason `schema_validation_rejected_rate`.

Это **ортогональный** cascade к Phase 8 PARSE-FIX-04 null-rate gate (50% absolute null-rate на goldapple `volume_norm` или `brand` → run failed). Они ловят разные failure modes:

- **PARSE-FIX-04**: "content drift" — parser работает, но возвращает NULLs (например, новая структура volume-блока, парсер промахивается с селектором → 88/88 SKU имеют `volume_raw=None` → `volume_norm=None` после normalizer)
- **TEST-HARNESS-06**: "structural drift" — parser возвращает данные неправильного типа/формы (например, `current_price` приходит как str вместо Decimal, `brand` приходит как list вместо str)

Cascade order: **schema-rejected-rate gate срабатывает РАНЬШЕ** PARSE-FIX-04 null-rate gate (после `persist` complete, до downstream gates). Это потому что schema violations обычно проявляются ДО null patterns — если ломается сама форма data, null patterns в matcher'е/reporter'е уже не имеют смысла.

## Reasoning

### 1. SqliteSnapshotWriter — НЕ dispatcher — потому что REQUIREMENTS verbatim

REQUIREMENTS.md TEST-HARNESS-06 прямо говорит: *"Pydantic validation at `SqliteSnapshotWriter` boundary"*. Boundary == граница write в storage — там данные пересекают process boundary (in-memory dict → SQL INSERT). Это единственная точка где есть смысл валидировать: позже raw-обработка завершена и данные становятся frozen-in-DB.

Альтернатива rejected — валидировать на `parsers/dispatcher.py:51` (asdict boundary). Это early-fail но (a) нарушает REQUIREMENTS verbatim, (b) теряет visibility над всеми источниками которые могут добавлять данные в storage (если когда-нибудь добавим scripts/replay_runs.py), (c) дублирует логику в каждом downstream consumer'е dispatcher dict shape'а.

### 2. Hard-raise per-SKU + run-fail на rate, а не на первом violation

Альтернатива rejected — hard-raise на ПЕРВОМ violating SKU (run-abort). Проблема: один legitimate edge-case (Frederic Malle Contre-Jour, который legitimately не имеет volume_raw в viled JSON) положит весь run. Это false-positive failure mode из v1.0 BUG-FINDINGS.md.

Per-SKU isolation (catch ValidationError, log, increment counter) — это **Phase 2 D-211 pattern** (atomic patch_stats, per-SKU isolation в viled fetcher). Соответствует established convention.

5% threshold — analog 50% PARSE-FIX-04 но **строже** потому что schema violations это **rare-or-zero in normal operation** (parser либо работает, либо нет; должно быть 0% schema rejects на здоровом run). 5% — catch-early threshold что говорит "что-то структурно ломается".

### 3. Орогональность к PARSE-FIX-04 — два разных failure modes

PARSE-FIX-04 cascade ловит:
- 88/88 SKU имеют `volume_norm = NULL` (run #13 pattern)
- Сценарий: parser работает технически, но извлекает wrong text → normalizer не справляется → matcher SQL JOIN filter `volume_norm IS NOT NULL` выкидывает всех → 0 matches

TEST-HARNESS-06 schema-rejected-rate gate ловит:
- Parser возвращает `current_price = "1500 ₽"` вместо `Decimal("1500.00")` (новая SSR template форматирует цены)
- Parser возвращает `brand = ["Armani"]` вместо `"Armani"` (multi-brand SKU shape variant)
- Parser возвращает `sku_id = None` для какой-то PDP shape

Эти два gate'а покрывают **complementary domains**. Schema rejects = structural; null rates = content. Без обоих остаются blind spots.

### 4. Stats fields shape — Phase 2 D-211 + Phase 6 D-616 lineage

Новые `runs.stats` keys следуют established atomic patch_stats pattern:

```python
{
  "schema_rejected_count": int,
  "schema_rejected_rate": float,
  "schema_rejected_reasons": [
    {"sku_id": "...", "retailer": "goldapple", "errors": [...]},
    ...
  ]
}
```

`schema_rejected_reasons` дополнительно — diagnostic для drift output. Operator может посмотреть `runs.stats.schema_rejected_reasons` и понять что именно сломалось в schema (полезно для drift report markdown).

## Implication

- `src/ga_crawler/storage/schemas.py` (новый) — Pydantic schemas с `RawProductBase` + 2 retailer subclasses (см. [[Per-retailer Pydantic schema split — goldapple strict viled relaxed для legitimate Nones]])
- `src/ga_crawler/storage/` `SqliteSnapshotWriter.persist` — wrap `model_validate(row)` в try/except `ValidationError`; per-SKU catch, increment counter
- `src/ga_crawler/runner/gates.py` — новый `schema_rejected_rate_gate(stats)` функция, shape соответствует D-203 retailer-agnostic helpers
- `src/ga_crawler/runner/stats.py` — добавить 3 keys (`schema_rejected_count: int`, `schema_rejected_rate: float`, `schema_rejected_reasons: list[dict]`) в atomic stats patch
- Pipeline: persist → schema_rejected_rate_gate → null_rate_gate (PARSE-FIX-04) → matcher → reporter → delivery
- Phase 9 plan 09-02 (parallel-safe с TEST-HARNESS-03) ships this

## Alternative considered

- **Dispatcher boundary, soft-fail log + skip** — REJECTED. Нарушает REQUIREMENTS verbatim, теряет fail-loud discipline. Skip без gate = silent failure mode.
- **SqliteSnapshotWriter boundary, hard-raise на первом violating SKU** — REJECTED. Один legitimate edge-case (Contre-Jour) положит весь run. False-positive failure rate высокий.
- **Validation на SqliteSnapshotWriter, no run-fail — только stats key + log** — REJECTED. Теряет «defense-in-depth» из REQUIREMENTS — PARSE-FIX-04 уже жёсткий gate; здесь нужен ортогональный fail-loud cascade.

## Test artefact (Phase 9 plan 09-02 must ship)

Synthetic-regression unit test в `tests/storage/test_schema_validation_gate.py`:

```python
def test_schema_rejected_rate_gate_fires_run_failed():
    """Inject batch of 100 SKUs где 6 имеют invalid schema (current_price = str)."""
    rejected_rate = 6/100 = 0.06 > 0.05
    assert run.status == "failed"
    assert run.stats.failure_reason == "schema_validation_rejected_rate"
    assert run.stats.schema_rejected_count == 6
```

И regression test что **legitimate viled Nones** (Contre-Jour pattern) НЕ попадают в reject bucket — `ViledRawProduct.volume_raw = None` это valid value.

## Related

- [[Per-retailer Pydantic schema split — goldapple strict viled relaxed для legitimate Nones]] (D-904 — какие именно поля validate'ятся)
- [[Goldapple PDP renders volume в structured flexbox blok, не в microdata]] (PARSE-FIX-01 — почему PARSE-FIX-04 null-rate gate существует)
- [[Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text]] (D-514 — `runs.stats.*` namespace conventions)
- `.planning/phases/09-live-html-harness/09-CONTEXT.md` — D-903 verbatim
- `.planning/REQUIREMENTS.md` TEST-HARNESS-06 line 28 — verbatim contract
