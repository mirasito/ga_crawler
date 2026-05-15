---
tags: [decision, schema, pydantic, retailer-asymmetry, v1-1, phase-9, parser-evidence]
date: 2026-05-14
phase: 9-contexted
status: locked
---

# Per-retailer Pydantic schema split — goldapple strict, viled relaxed для legitimate Nones

## Утверждение

Phase 9 TEST-HARNESS-06 ships **per-retailer Pydantic schema split** (НЕ unified schema):

- **`GoldappleRawProduct` (strict)**: `brand: NonEmptyStr` REQUIRED, `volume_raw: NonEmptyStr` REQUIRED, `name: NonEmptyStr` REQUIRED, `current_price: Decimal` > 0 REQUIRED, `sku_id: NonEmptyStr` REQUIRED
- **`ViledRawProduct` (relaxed)**: same поля REQUIRED **кроме** `volume_raw: NonEmptyStr | None` (legitimate Nones)
- Base class `RawProductBase` containts shared поля; per-retailer subclass'ы переопределяют только `volume_raw` тип

Это асимметричный schema design driven by fixture-evidence — НЕ over-engineering и НЕ violation of DRY.

## Reasoning

### 1. Goldapple beauty PDPs ВСЕГДА имеют volume

Phase 8 W0 spike findings (30-PDP stratified shape sampling, `.planning/spikes/v1.1-brand-name-shapes/`):

- 30/30 goldapple beauty PDPs имеют structured volume block (`78 ОБЪЁМ / МЛ` flexbox) — после PARSE-FIX-01 fix через selectolax 0.4 Lexbor `:lexbor-contains` parser извлекает volume_raw для всех 30 PDPs

Это коррелирует с domain semantics — на goldapple beauty/парфюм каталог это retailer для perfume+cosmetics, и каждый product variant обязательно имеет volume (50ml, 100ml, etc.). Если PDP не имеет volume — это **structural drift**, не legitimate data.

Поэтому strict NonEmptyStr REQUIRED для goldapple `volume_raw` — fail-loud если schema ломается.

### 2. Viled имеет legitimate None volumes — evidence

Phase 8 v1.1-PARSER-BUG-FINDINGS.md документирует **legitimate** viled SKUs без volume:

- `Frederic Malle / Парфюмерная вода Contre-Jour` — title не содержит volume keyword; viled JSON `attributes[0].attributes[].name == "Размер"` поле тоже отсутствует. Это niche perfume где volume "по умолчанию" подразумевается на brand-level
- `Creed Wild Vetiver` — same shape; volume не explicit ни в title, ни в attributes
- Beauty masks / one-size items — некоторые SKU вообще не имеют volume концепции

Strict NonEmptyStr REQUIRED для viled `volume_raw` → false-positive rejections на этих legitimate SKUs → `rejected_rate` (per [[Pydantic RawProduct validation at SqliteSnapshotWriter — 5 percent reject-rate gate orthogonal to PARSE-FIX-04]]) поднимется выше 5% threshold → run failed на legitimate data → ops alert burst → operator alarm fatigue.

`NonEmptyStr | None` (Pydantic 2 union type) accept'ит легитимные Nones без validation error. Downstream `parse_volume` normalizer уже умеет обрабатывать None (Phase 2 D-203). Matcher SQL filter `volume_norm IS NOT NULL` natural excludes их.

### 3. Альтернатива «strict unified для обоих» — РИСКОВАННА

Если унифицировать через strict NonEmptyStr для volume_raw на обоих retailers:

- Viled run #14 с 5+ Contre-Jour-shape SKUs в каталоге → 5%+ reject rate → run **failed** на legitimate data
- Operator получает Telegram alert "schema validation rejected rate exceeded" → debugging time → false alarm
- Доверие к gate'у падает — operator начнёт ignore'ить или повышать threshold → теряем fail-loud discipline для **real** schema drift

Per-retailer split = **correctness**, не over-engineering. Cost — 30 LOC дополнительной subclass пары; benefit — отсутствие false-positive run-fails на shipping product evidence.

### 4. Альтернатива «unified + Optional для всех» — теряет ценность boundary

Если все поля Optional на unified schema — Pydantic validation ловит только wrong-type errors (str где должен Decimal). Это 10% случаев. Остальные 90% (NULL где expected, list где expected str) проходят silently.

TEST-HARNESS-06 цель = **defense-in-depth** против schema drift. Optional-всё это weak defense.

### 5. Альтернатива «per-retailer + custom validator для viled brand-list» — over-engineering

Можно было сделать `ViledRawProduct.volume_raw: NonEmptyStr | None` + custom `@model_validator(mode="after")` который проверяет `brand` против allow-list `LEGITIMATE_NO_VOLUME_BRANDS = {"Frederic Malle", "Creed", ...}` — если brand НЕ в этом списке И volume_raw is None → raise.

Это over-engineering для v1.1 потому что:
- Brand-list maintenance overhead (новый Frederic Malle-style niche brand → нужно обновить allow-list)
- Brand-evidence уже sparse (фикстура run #13 только 2 brand'а с этим pattern'ом)
- Lemma: better catch shape drift Pydantic-level и let normalizer decide legitimacy

V1.2 reconsider если post-deploy evidence показывает что viled None volume rate >20% — тогда стоит brand-list allow-list.

## Implication

- `src/ga_crawler/storage/schemas.py` (новый):
  ```python
  from pydantic import BaseModel, Field
  from decimal import Decimal
  from typing import Annotated

  NonEmptyStr = Annotated[str, Field(min_length=1)]

  class RawProductBase(BaseModel):
      sku_id: NonEmptyStr
      brand: NonEmptyStr
      name: NonEmptyStr
      current_price: Annotated[Decimal, Field(gt=0)]

  class GoldappleRawProduct(RawProductBase):
      volume_raw: NonEmptyStr

  class ViledRawProduct(RawProductBase):
      volume_raw: NonEmptyStr | None = None
  ```
- `src/ga_crawler/storage/SqliteSnapshotWriter.persist` инжектит `GoldappleRawProduct.model_validate(row)` для goldapple persists, `ViledRawProduct.model_validate(row)` для viled persists (per-retailer dispatch уже existing pattern в dispatcher.py)
- Tests: `tests/storage/test_pydantic_schemas.py` covers happy path + legitimate viled None + invalid types

## Test cases (Phase 9 plan 09-02 must ship)

```python
def test_goldapple_strict_volume_required():
    """goldapple SKU без volume_raw → ValidationError."""
    with pytest.raises(ValidationError, match="volume_raw"):
        GoldappleRawProduct(brand="Armani", name="Code", volume_raw="", current_price=Decimal("100"), sku_id="abc")

def test_viled_relaxed_volume_allows_none():
    """viled Contre-Jour shape passes."""
    obj = ViledRawProduct(brand="Frederic Malle", name="Contre-Jour", volume_raw=None, current_price=Decimal("75000"), sku_id="408872")
    assert obj.volume_raw is None

def test_both_retailers_strict_brand():
    """brand REQUIRED на обоих retailer'ах."""
    with pytest.raises(ValidationError, match="brand"):
        GoldappleRawProduct(brand="", name="X", volume_raw="50 мл", current_price=Decimal("1"), sku_id="x")
    with pytest.raises(ValidationError, match="brand"):
        ViledRawProduct(brand="", name="X", volume_raw=None, current_price=Decimal("1"), sku_id="x")
```

## Alternative considered

- **Unified schema, всё Optional, ловим только типы** — REJECTED. Теряет 90% ценности boundary; невозможно отличить legitimate Nones от broken parser
- **Strict unified, NonEmptyStr для обоих** — REJECTED. False-positive run-fail на legitimate viled data → ops alert fatigue
- **Per-retailer + custom validator + brand allow-list** — DEFERRED to v1.2 если post-deploy evidence warrants

## Related

- [[Pydantic RawProduct validation at SqliteSnapshotWriter — 5 percent reject-rate gate orthogonal to PARSE-FIX-04]] (D-903 — где именно schema enforce'ится, какой gate)
- [[Goldapple PDP renders volume в structured flexbox blok, не в microdata]] (PARSE-FIX-01 — goldapple volume evidence)
- [[viled volume — в attributes Размер JSON-поле, не в name]] (PARSE-FIX-03 — viled volume evidence)
- [[viled Размер JSON path — nested attributes 0 attributes, не item attributes]] (RES-08-01 — viled volume path)
- `.planning/phases/09-live-html-harness/09-CONTEXT.md` — D-904 verbatim
- `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` — Contre-Jour / Wild Vetiver evidence
- `.planning/spikes/v1.1-brand-name-shapes/MEMO.md` — 30-PDP goldapple shape evidence
