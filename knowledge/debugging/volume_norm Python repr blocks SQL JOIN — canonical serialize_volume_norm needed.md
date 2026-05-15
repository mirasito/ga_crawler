---
tags: [debugging, matcher, volume-norm, sql-join, code-review, cr-01]
date: 2026-05-15
phase: 10
commit-fix: fe03f9d
---

# volume_norm Python repr blocks SQL JOIN — canonical serialize_volume_norm needed

## Симптом

Run #16 weekly-run: viled=82, goldapple=89, brand_overlap=0, **match_count=0**. Пользователь увидел empty xlsx и cпросил "почему 0 matches".

Code review нашёл это **отдельно** от других багов — fix для goldapple persistence (CR-04) и dotenv (CR-02) только восстановил brand_overlap до 18, match_count всё ещё был бы 0 из-за этого bug.

## Root cause

`runners/viled_run.py:102-103` (старая версия):
```python
volume_norm_tuple = normalizer.volume(raw_volume_text)
volume_norm: Optional[str] = (
    str(volume_norm_tuple) if volume_norm_tuple is not None else None
)
```

`runners/goldapple_run.py:248` (старая версия):
```python
"volume_norm": normalizer.volume(product.raw_volume_text or ""),
```

Goldapple писал raw tuple object → SQLModel вызывал `str()` через ORM type-coercion. Оба пути давали Python's `tuple.__repr__()` form:

```python
>>> str((Decimal('50'), 'ml', 1))
"(Decimal('50'), 'ml', 1)"
>>> str((Decimal('50.0'), 'ml', 1))  
"(Decimal('50.0'), 'ml', 1)"  # different string!
>>> str((Decimal('50'), 'ML', 1))
"(Decimal('50'), 'ML', 1)"    # case-sensitive!
```

Strict-key matcher SQL `JOIN ON v.volume_norm = g.volume_norm` сравнивает строки **byte-for-byte**. Любая разница в Decimal precision OR unit-case OR whitespace → no match.

## Fix

Добавлен `serialize_volume_norm()` в `normalizers/volume.py`:

```python
def serialize_volume_norm(v: Optional[tuple[Decimal, str, int]]) -> Optional[str]:
    """Canonical string form for the snapshots.volume_norm column.
    Format: `(amount,unit,count)` — amount strips trailing zeros and dot.
    """
    if v is None:
        return None
    amount, unit, count = v
    a = format(amount, "f")
    if "." in a:
        a = a.rstrip("0").rstrip(".")
    return f"({a},{unit},{count})"
```

Оба runner'а теперь используют `serialize_volume_norm()` → canonical `"(50,ml,1)"`. Same input → identical string → SQL JOIN works.

## Pre-canary

Перед fix run #17 имел viled snapshots с `volume_norm = "(Decimal('100'), 'ml', 1)"` и goldapple snapshots (когда они вообще попали в DB через CR-04 fix) с `volume_norm = "(Decimal('100.00'), 'ml', 1)"`. SQL JOIN не находил совпадений несмотря на семантически equal volumes.

## После fix

Commit `fe03f9d`. Run #18: brand_overlap 0 → 18, denominator 36 → 1,774. match_count всё ещё 0 — но теперь причина другая ([[Strict-key matcher даёт 0 matches на real fashion data — fuzzy v2 нужен]]), не serialization defect.

## Lesson

**Не использовать `str(tuple)` для column values что участвуют в SQL JOIN.** Всегда explicit canonical serializer с unit tests подтверждающими `serialize(x) == serialize(y) ⟺ x semantically_equal y`.

Можно добавить в `tests/unit/test_volume_serialize.py` regression-canary:
```python
def test_canonical_form_stable():
    assert serialize_volume_norm((Decimal("50"), "ml", 1)) == "(50,ml,1)"
    assert serialize_volume_norm((Decimal("50.0"), "ml", 1)) == "(50,ml,1)"
    assert serialize_volume_norm((Decimal("50.00"), "ml", 1)) == "(50,ml,1)"
    # Different inputs that should NOT collide:
    assert serialize_volume_norm((Decimal("50"), "ml", 2)) != "(50,ml,1)"
```

## Связано

- [[2026-05-15 — Phase 10 closed + viled pagination unlocked + 4 production bugs fixed]] — session note
- [[Strict-key matcher даёт 0 matches на real fashion data — fuzzy v2 нужен]]
- Commit `fe03f9d`
- `src/ga_crawler/normalizers/volume.py:_to_decimal` — utility под `serialize_volume_norm`
- `src/ga_crawler/runners/viled_run.py:102` — fix site
- `src/ga_crawler/runners/goldapple_run.py:248-250` — fix site
