---
tags: [debugging, goldapple, phase-9, schema-validation, code-review, cr-04, field-mismatch]
date: 2026-05-15
phase: 10
commit-fix: fe03f9d
---

# goldapple_run wrote raw_volume_text key instead of volume_raw — Phase 9 schema exposed it

## Симптом (post-Phase-9)

Run #16 weekly-run: log emit `phase3_snapshots_written inserted: 0` для goldapple — но final summary говорил `goldapple_count: 89`. **Zero persisted, 89 фетчены** = bug. Затем `match_count: 0` потому что goldapple snapshots table пустой.

## Pre-Phase-9 (silent)

`runners/goldapple_run.py:249` исторически писал в payload dict:
```python
"raw_volume_text": product.raw_volume_text,  # WRONG key name
```

`Snapshot` SQL column column называется `volume_raw` (singular). `SqliteSnapshotWriter.append` имеет pre-filter:
```python
valid_fields = set(Snapshot.model_fields.keys())  # includes 'volume_raw'
payload = {k: v for k, v in product.items() if k in valid_fields}
```

`raw_volume_text` не в `valid_fields` → filter сбрасывает поле → INSERT отрабатывает с `volume_raw=NULL`. **Silent data loss** — goldapple snapshots сохранялись с NULL volume_raw. Parse-quality gate (PARSE-FIX-04) ловил **content drift** не **field-name drift**.

## Phase 9 D-903 exposed it

[[Phase 9]] добавил `GoldappleRawProduct` Pydantic schema (`storage/schemas.py`) с **strict** `volume_raw: NonEmptyStr`. SqliteSnapshotWriter.append теперь:

```python
schema_cls = _SCHEMA_BY_RETAILER.get(retailer)
if schema_cls is not None:
    try:
        schema_cls.model_validate(payload)
    except ValidationError as ve:
        rejected_reasons.append(...)
        continue  # skip INSERT
```

Pre-filtered payload не содержит `volume_raw` → `model_validate` raises `ValidationError("volume_raw: field required")` → row rejected → `continue` skips INSERT.

89/89 goldapple rows fail validation → 0 persisted. Validation error reasons captured в `writer._last_rejected_reasons` но **runner никогда их не читает** (см. [[Phase 9 D-903 schema_rejected_rate_gate disconnected from runner pipeline]]).

## Fix

`goldapple_run.py:249`:
```diff
-                "raw_volume_text": product.raw_volume_text,
+                "volume_raw": product.raw_volume_text,
```

One-line key rename. viled_run.py:119 уже корректно писал `"volume_raw"` — bug был asymmetric.

## После fix (run #17)

`phase3_snapshots_written inserted: 89` ✓. goldapple snapshots table populated. brand_overlap 0 → 6. xlsx empty → 70+46 rows.

## Lesson

**Pre-filter `valid_fields` + strict schema validation — комбинация которая может либо silent-drop fields либо hard-reject rows depending on field requiredness.** Add structural canary test:

```python
def test_goldapple_snapshot_payload_uses_volume_raw_key():
    """Regression guard for CR-04 (raw_volume_text/volume_raw typo)."""
    from ga_crawler.runners.goldapple_run import _normalize_goldapple_product
    payload = _normalize_goldapple_product(fake_product)
    assert "volume_raw" in payload  # The Snapshot column name
    assert "raw_volume_text" not in payload  # The parser attr name (should be remapped)
```

Похожий guard для viled_run уже есть имплицитно в `tests/integration/test_writer_schema_gate.py` (которые проходили потому что viled-runner был correct).

## Связано

- [[2026-05-15 — Phase 10 closed + viled pagination unlocked + 4 production bugs fixed]] — session note
- [[volume_norm Python repr blocks SQL JOIN — canonical serialize_volume_norm needed]] — sibling CR-01
- [[Phase 9 D-903 schema_rejected_rate_gate disconnected from runner pipeline]] — CR-04 родственный
- Commit `fe03f9d`
- `src/ga_crawler/storage/schemas.py:GoldappleRawProduct` — strict schema что exposed bug
- `src/ga_crawler/runners/goldapple_run.py:249` — fix site
- `tests/storage/test_schemas.py` — Phase 9 schema tests что покрывали schema но не runner mapping
