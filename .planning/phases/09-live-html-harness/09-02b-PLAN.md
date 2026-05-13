---
phase: 09-live-html-harness
plan: 02b
type: execute
wave: 1
depends_on:
  - "09-01"
files_modified:
  - src/ga_crawler/storage/schemas.py
  - src/ga_crawler/storage/sqlite.py
  - src/ga_crawler/runner/gates.py
  - src/ga_crawler/runner/stats.py
  - tests/storage/__init__.py
  - tests/storage/test_schemas.py
  - tests/integration/test_writer_schema_gate.py
  - tests/runner/test_schema_rejected_gate.py
autonomous: true
requirements:
  - TEST-HARNESS-06
tags:
  - storage
  - pydantic
  - validation
  - schema
  - gate
  - python
must_haves:
  truths:
    - "GoldappleRawProduct (strict) raises ValidationError on empty/missing volume_raw (D-904 strict goldapple)"
    - "ViledRawProduct (relaxed) accepts volume_raw=None and volume_raw missing entirely (D-904 viled-relaxed; Contre-Jour evidence)"
    - "Both schemas reject empty brand, empty name, current_price ≤ 0"
    - "SqliteSnapshotWriter.append (NOT .persist — method name corrected per RESEARCH §9 Q1) validates per-row via _SCHEMA_BY_RETAILER.get(retailer).model_validate(payload) BEFORE Snapshot(**payload)"
    - "ValidationError per-row causes that row to be SKIPPED (continue), reason captured into writer._last_rejected_reasons with {sku_id, errors:[{loc,type}]} only — NO 'input' key (T-09-PII landmine §7.2)"
    - "_last_rejected_reasons truncated at 50 entries to bound runs.stats JSON size"
    - "schema_rejected_rate_gate(rejected_count, total_attempted, threshold=0.05) frozen-dataclass returns passed=False with failure_reason='schema_validation_rejected_rate' when rate > 0.05 (STRICT > per Phase 8 D-815 convention)"
    - "SCHEMA_STATS_KEYS namespace tuple defined in runner/stats.py: 'schema.rejected_count', 'schema.rejected_rate', 'schema.rejected_reasons'"
  artifacts:
    - path: "src/ga_crawler/storage/schemas.py"
      provides: "Pydantic 2.10 RawProductBase + GoldappleRawProduct (strict) + ViledRawProduct (relaxed) per D-904"
      contains: "class GoldappleRawProduct"
    - path: "src/ga_crawler/storage/sqlite.py"
      provides: "SqliteSnapshotWriter.append wired with per-row schema_cls.model_validate(payload); _last_rejected_reasons attribute"
      contains: "_SCHEMA_BY_RETAILER"
    - path: "src/ga_crawler/runner/gates.py"
      provides: "SchemaRejectedGateResult frozen-dataclass + schema_rejected_rate_gate(threshold=0.05); added to __all__"
      contains: "schema_rejected_rate_gate"
    - path: "src/ga_crawler/runner/stats.py"
      provides: "SCHEMA_STATS_KEYS tuple namespace (run-level, not retailer-scoped per RESEARCH §9 Q3)"
      contains: "SCHEMA_STATS_KEYS"
    - path: "tests/storage/__init__.py"
      provides: "Package marker"
    - path: "tests/storage/test_schemas.py"
      provides: "TH-06a/b unit tests — strict goldapple rejects empty volume; relaxed viled accepts None"
    - path: "tests/integration/test_writer_schema_gate.py"
      provides: "TH-06c integration test — SqliteSnapshotWriter.append skips invalid rows; _last_rejected_reasons populated; no 'input' key (PII guard)"
    - path: "tests/runner/test_schema_rejected_gate.py"
      provides: "TH-06d unit test — threshold semantics (strict >; exactly 0.05 passes; 0.0501 fails); empty-input edge"
  key_links:
    - from: "src/ga_crawler/storage/sqlite.py SqliteSnapshotWriter.append loop (L186-192)"
      to: "src/ga_crawler/storage/schemas.py GoldappleRawProduct / ViledRawProduct"
      via: "schema_cls.model_validate(payload) per-row"
      pattern: "model_validate"
    - from: "src/ga_crawler/storage/sqlite.py"
      to: "_last_rejected_reasons"
      via: "self._last_rejected_reasons attribute on writer instance"
      pattern: "_last_rejected_reasons"
    - from: "src/ga_crawler/runner/gates.py schema_rejected_rate_gate"
      to: "SchemaRejectedGateResult frozen-dataclass"
      via: "return value shape; mirrors ParserDriftGateResult (Phase 8 D-815)"
      pattern: "SchemaRejectedGateResult"
---

<objective>
Phase 9 Wave 1 (parallel-B) — ship Pydantic 2.10 raw-product schemas (per-retailer strict/relaxed split per D-904), wire `model_validate` at `SqliteSnapshotWriter.append` (write-boundary per D-903; method name `append` per RESEARCH §9 Q1, NOT `persist` as CONTEXT.md uses conceptually), ship `schema_rejected_rate_gate` (threshold 0.05) following Phase 8 `parser_drift_null_rate_gate` D-815 pattern, ship `SCHEMA_STATS_KEYS` namespace.

Defense-in-depth complement to Phase 8 PARSE-FIX-04: PARSE-FIX-04 catches "all SKUs have NULL volume" (content drift, 50% threshold). This gate catches "parser emits wrong shape" (structural drift, 5% threshold). Cascade position: schema gate runs FIRST (structural drift surfaces earlier than content drift).

Purpose: if parser regresses and emits e.g. `volume_raw=""` on goldapple, `SqliteSnapshotWriter.append` rejects each invalid row, accumulates into `_last_rejected_reasons`, and the gate flips the run to `failed` if rate > 5%. Production has visibility into per-SKU rejection causes via `runs.stats.schema.rejected_reasons`.

Output:
- New file `src/ga_crawler/storage/schemas.py` (Pydantic schemas — greenfield; verified `storage/types.py` absent per RESEARCH §9 Q2)
- New tests: `tests/storage/__init__.py`, `tests/storage/test_schemas.py`, `tests/integration/test_writer_schema_gate.py`, `tests/runner/test_schema_rejected_gate.py`
- Modified `src/ga_crawler/storage/sqlite.py` (per-row `model_validate` injection at L186-192)
- Modified `src/ga_crawler/runner/gates.py` (append `schema_rejected_rate_gate` + result class; update `__all__`)
- Modified `src/ga_crawler/runner/stats.py` (append `SCHEMA_STATS_KEYS` + update `__all__`)

Parallel-safe with 09-02a (TH-03 live drift) — disjoint files. 09-02a writes `tests/live/` + `tests/test_snapshot_soundness.py`; 09-02b writes `src/ga_crawler/storage/`, `src/ga_crawler/runner/`, `tests/storage/`, `tests/integration/`, `tests/runner/`. Zero file overlap.

**STATS WIRE-UP SCOPE NOTE:** This plan ships the *gate function* and writer integration. The orchestrator (`runners/main_run.py` or equivalent) wire-up of `patch_stats(run_id, {schema.rejected_count: ...})` + `gate_result.passed → run_writer.fail(...)` is documented in the writer integration test (proves end-to-end) but the actual orchestrator call-site change is left for `runners/main_run.py` to pick up via the standard pattern. Integration test exercises the writer + gate together so the contract is locked.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/09-live-html-harness/09-CONTEXT.md
@.planning/phases/09-live-html-harness/09-RESEARCH.md
@.planning/phases/09-live-html-harness/09-VALIDATION.md
@.planning/phases/09-live-html-harness/09-PATTERNS.md
@.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md
@src/ga_crawler/storage/sqlite.py
@src/ga_crawler/runner/gates.py
@src/ga_crawler/runner/stats.py
@src/ga_crawler/parsers/goldapple_microdata.py
@src/ga_crawler/parsers/dispatcher.py
@tests/integration/test_storage_integration.py
@tests/runner/test_parser_drift_gate.py

<interfaces>
<!-- Storage writer API (verbatim per source file) -->

From `src/ga_crawler/storage/sqlite.py:165-199` (existing):
```python
class SqliteSnapshotWriter:
    def __init__(self, engine, *, batch_size: int = 100):
        self.engine = engine
        self.batch_size = batch_size

    def append(self, run_id: int, retailer: str, products: list) -> int:
        """Returns count of INSERTed rows. Pre-09-02b: no schema validation."""
```

From `src/ga_crawler/runner/gates.py:285-342` (Phase 8 D-815 analog):
```python
@dataclass(frozen=True)
class ParserDriftGateResult:
    passed: bool
    volume_null_rate: float
    brand_null_rate: float
    failure_reason: Optional[str]

def parser_drift_null_rate_gate(
    volume_null_rate: float,
    brand_null_rate: float,
    *,
    threshold: float = 0.5,
) -> ParserDriftGateResult:
    """STRICT >: rate > threshold fails; rate == threshold passes."""
```

From `src/ga_crawler/runner/gates.py:382-394` (`__all__`):
```python
__all__ = [
    "SMOKE_URLS", "load_smoke_urls_from_config", "smoke_probe",
    "auto_suggest_threshold", "final_threshold_gate", "parse_quality_gate",
    "parser_drift_null_rate_gate", "ParserDriftGateResult",
    "final_m_gate", "final_n_gate", "auto_suggest_m",
]
```

From `src/ga_crawler/runner/stats.py:149-159` (existing `VILED_STATS_KEYS` analog):
```python
VILED_STATS_KEYS: tuple[str, ...] = (
    "viled.fetch_count", "viled.fetch_failures", ...
)
```

From `src/ga_crawler/runner/stats.py:219-226` (`__all__`):
```python
__all__ = [
    "GOLDAPPLE_STATS_KEYS", "VILED_STATS_KEYS",
    "StatsNamespaceError", "GoldappleStatsBuilder", "ViledStatsBuilder",
    "compute_norm06_forward",
]
```

From `src/ga_crawler/storage/sqlite.py:60-87` (Snapshot SQLModel — DO NOT modify; schema mirrors loosely):
```python
class Snapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int
    retailer: str
    sku_id: str
    url: str
    name: Optional[str] = None
    brand: Optional[str] = None
    current_price: Optional[int] = None
    # ... etc
```

From `tests/integration/test_storage_integration.py:39-95` (analog for integration test shape):
```python
def _setup(tmp_path: Path):
    db = tmp_path / "test.db"; init_db(db); return make_engine(db)

def _row(sku_id, name="X", price=1000) -> dict:
    return {"sku_id": sku_id, "url": f"https://example.com/{sku_id}",
            "name": name, "brand": "TestBrand", "current_price": price, ...}
```

From `tests/runner/test_parser_drift_gate.py:21-79` (EXACT analog for new gate test):
```python
def test_volume_exceeds_threshold_fails() -> None:
    r = parser_drift_null_rate_gate(volume_null_rate=0.6, brand_null_rate=0.0)
    assert not r.passed
    assert r.failure_reason == "parser_drift_null_volume_rate"
```
</interfaces>

<critical_method_name_note>
**RESEARCH §9 Q1 finding:** CONTEXT.md D-903 uses conceptual name "persist". The ACTUAL method on `SqliteSnapshotWriter` is `append(run_id, retailer, products) -> int`. All task `<action>` fields below use `append` verbatim — DO NOT introduce a `.persist` method, DO NOT rename `.append`.
</critical_method_name_note>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Ship src/ga_crawler/storage/schemas.py with Pydantic 2 per-retailer schemas (RED-first)</name>
  <files>
    src/ga_crawler/storage/schemas.py,
    tests/storage/__init__.py,
    tests/storage/test_schemas.py
  </files>
  <read_first>
    - 09-RESEARCH.md §4 (Pydantic 2.10 idiomatic shape — NonEmptyStr Annotated, RawProductBase, GoldappleRawProduct strict, ViledRawProduct relaxed)
    - 09-RESEARCH.md §4.4 (schema file skeleton verbatim)
    - 09-RESEARCH.md §7.4 (extra="forbid" vs "ignore" — recommendation: stay "ignore" since writer's valid_fields filter pre-strips)
    - 09-CONTEXT.md D-904 (per-retailer split rationale + evidence: Contre-Jour legitimately None per BUG-FINDINGS.md)
    - 09-PATTERNS.md lines 52-110 (`storage/schemas.py` analog + cross-references)
    - src/ga_crawler/parsers/goldapple_microdata.py (verify actual field names — dispatcher dict shape that schema receives)
    - src/ga_crawler/parsers/dispatcher.py:51 (asdict() dispatcher dict shape)
    - .claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md L39 (goldapple 25/30 = 83% have volume; strict justified)
  </read_first>
  <behavior>
    - Test 1 (`test_goldapple_strict_accepts_valid`): valid payload with all required fields succeeds; `volume_raw` preserved
    - Test 2 (`test_goldapple_strict_rejects_empty_volume`): payload with `volume_raw=""` raises `ValidationError` with at least one error of type `string_too_short`
    - Test 3 (`test_goldapple_strict_rejects_missing_volume`): payload without `volume_raw` key raises `ValidationError`
    - Test 4 (`test_viled_relaxed_accepts_none_volume`): payload with `volume_raw=None` succeeds (D-904 viled-relaxed)
    - Test 5 (`test_viled_relaxed_accepts_missing_volume`): payload without `volume_raw` key succeeds; defaults to None
    - Test 6 (`test_both_reject_zero_price`): `current_price=0` raises `ValidationError` for both classes
    - Test 7 (`test_both_reject_empty_brand`): `brand=""` raises for both classes
    - Test 8 (`test_both_reject_empty_name`): `name=""` raises for both
    - Test 9 (`test_both_reject_empty_sku_id`): `sku_id=""` raises for both
    - Test 10 (`test_both_reject_empty_url`): `url=""` raises for both
    - Test 11 (`test_extra_keys_ignored`): payload with extra unknown key does NOT raise (writer's valid_fields filter handles unknowns)
  </behavior>
  <action>
    **First — confirm dispatcher dict field names** by reading `src/ga_crawler/parsers/dispatcher.py:51` and `src/ga_crawler/parsers/goldapple_microdata.py:45-70`. The dispatcher emits `asdict(GoldappleRawProduct)` — the schema field names MUST match what comes out of `asdict()`.

    Per RESEARCH §4.4 + PATTERNS.md analog map, the dispatcher dict is built around the `Snapshot` SQLModel field names (after `valid_fields` filter at sqlite.py:183). So the Pydantic schema should use those FIELD names verbatim: `sku_id, url, name, brand, current_price, volume_raw`.

    1. Create `tests/storage/__init__.py` with single docstring:
    ```python
    """Phase 9 TEST-HARNESS-06 storage-side test package."""
    ```

    2. Create `tests/storage/test_schemas.py` (RED first — schemas module does not exist yet):
    ```python
    """TH-06a + TH-06b — per-retailer Pydantic schemas (D-904 strict/relaxed split).

    Goldapple beauty PDPs have volume on 25/30 = 83% of shape-table samples
    (spike-findings-v1.1-brand-name-shapes/SKILL.md L39). Strict justified.

    Viled Frederic Malle Contre-Jour and Creed Wild Vetiver legitimately lack
    `Размер` attribute (08-01-SUMMARY Bug #3 + BUG-FINDINGS.md). Relaxed required.
    """

    from __future__ import annotations

    import pytest
    from pydantic import ValidationError

    from ga_crawler.storage.schemas import GoldappleRawProduct, ViledRawProduct


    _VALID_PAYLOAD: dict = {
        "sku_id": "19000440474",
        "url": "https://goldapple.kz/19000440474-stereotype-sago",
        "name": "SAĜO",
        "brand": "Stereotype",
        "current_price": 50000,
        "volume_raw": "75 мл",
    }


    def test_goldapple_strict_accepts_valid() -> None:
        p = GoldappleRawProduct.model_validate(_VALID_PAYLOAD)
        assert p.volume_raw == "75 мл"
        assert p.brand == "Stereotype"


    def test_goldapple_strict_rejects_empty_volume() -> None:
        bad = dict(_VALID_PAYLOAD)
        bad["volume_raw"] = ""
        with pytest.raises(ValidationError) as exc:
            GoldappleRawProduct.model_validate(bad)
        assert any(err["type"] == "string_too_short" for err in exc.value.errors())


    def test_goldapple_strict_rejects_missing_volume() -> None:
        bad = dict(_VALID_PAYLOAD)
        del bad["volume_raw"]
        with pytest.raises(ValidationError):
            GoldappleRawProduct.model_validate(bad)


    def test_viled_relaxed_accepts_none_volume() -> None:
        """D-904 evidence: Frederic Malle Contre-Jour legitimately lacks `Размер`."""
        payload = dict(_VALID_PAYLOAD)
        payload["volume_raw"] = None
        p = ViledRawProduct.model_validate(payload)
        assert p.volume_raw is None


    def test_viled_relaxed_accepts_missing_volume() -> None:
        payload = dict(_VALID_PAYLOAD)
        del payload["volume_raw"]
        p = ViledRawProduct.model_validate(payload)
        assert p.volume_raw is None


    def test_both_reject_zero_price() -> None:
        for cls in (GoldappleRawProduct, ViledRawProduct):
            bad = dict(_VALID_PAYLOAD)
            bad["current_price"] = 0
            with pytest.raises(ValidationError):
                cls.model_validate(bad)


    def test_both_reject_negative_price() -> None:
        for cls in (GoldappleRawProduct, ViledRawProduct):
            bad = dict(_VALID_PAYLOAD)
            bad["current_price"] = -1
            with pytest.raises(ValidationError):
                cls.model_validate(bad)


    def test_both_reject_empty_brand() -> None:
        for cls in (GoldappleRawProduct, ViledRawProduct):
            bad = dict(_VALID_PAYLOAD)
            bad["brand"] = ""
            with pytest.raises(ValidationError):
                cls.model_validate(bad)


    def test_both_reject_empty_name() -> None:
        for cls in (GoldappleRawProduct, ViledRawProduct):
            bad = dict(_VALID_PAYLOAD)
            bad["name"] = ""
            with pytest.raises(ValidationError):
                cls.model_validate(bad)


    def test_both_reject_empty_sku_id() -> None:
        for cls in (GoldappleRawProduct, ViledRawProduct):
            bad = dict(_VALID_PAYLOAD)
            bad["sku_id"] = ""
            with pytest.raises(ValidationError):
                cls.model_validate(bad)


    def test_both_reject_empty_url() -> None:
        for cls in (GoldappleRawProduct, ViledRawProduct):
            bad = dict(_VALID_PAYLOAD)
            bad["url"] = ""
            with pytest.raises(ValidationError):
                cls.model_validate(bad)


    def test_extra_keys_ignored() -> None:
        """ConfigDict(extra='ignore') lets unknown keys pass — writer pre-filters anyway."""
        payload = dict(_VALID_PAYLOAD)
        payload["completely_unknown_field"] = "ignored_value"
        p = GoldappleRawProduct.model_validate(payload)
        assert not hasattr(p, "completely_unknown_field")
    ```

    3. Run `uv run pytest tests/storage/test_schemas.py -x` — MUST fail RED (`ModuleNotFoundError: ga_crawler.storage.schemas`).
    4. Commit RED: `test(09-02b): RED — TH-06a/b per-retailer Pydantic schema stubs`.

    **GREEN step — ship the schemas module.**

    5. Create `src/ga_crawler/storage/schemas.py` per RESEARCH §4.4 verbatim:
    ```python
    """Pydantic raw-product schemas — write-boundary validation at SqliteSnapshotWriter.append.

    Phase 9 TEST-HARNESS-06 (D-903 + D-904):
      - GoldappleRawProduct (STRICT): volume_raw REQUIRED (NonEmptyStr).
        Evidence: goldapple beauty PDPs carry [...] ОБЪЁМ / МЛ block on 25/30
        spike-sampled pages (spike-findings-v1.1-brand-name-shapes/SKILL.md L39).
      - ViledRawProduct (RELAXED): volume_raw Optional[NonEmptyStr]=None.
        Evidence: Frederic Malle Contre-Jour, Creed Wild Vetiver legitimately
        lack `Размер` attribute (08-01-SUMMARY Bug #3 + BUG-FINDINGS.md).

    Cascade position: this is *structural* drift detection (parser emits wrong
    shape). Phase 8 PARSE-FIX-04 null-rate gate catches *content* drift (all
    SKUs have NULL volume). Schema gate runs FIRST (structural before content).

    Source anchors: 09-CONTEXT.md D-903/D-904; 09-RESEARCH.md §4 + §6.4.
    """

    from __future__ import annotations

    from typing import Annotated, Optional

    from pydantic import BaseModel, ConfigDict, Field, StringConstraints

    NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


    class RawProductBase(BaseModel):
        """Shared fields between goldapple/viled raw product dicts (post-dispatcher).

        ConfigDict(extra='ignore'): SqliteSnapshotWriter.append pre-filters payload
        via valid_fields set (sqlite.py:183), so anything Pydantic sees is already
        Snapshot-known. RESEARCH §7.4 — 'ignore' is safe given pre-filter contract.
        """

        model_config = ConfigDict(extra="ignore")

        sku_id: NonEmptyStr
        url: NonEmptyStr
        name: NonEmptyStr
        brand: NonEmptyStr
        current_price: int = Field(gt=0)  # KZT integer; gt=0 rejects 0/negative


    class GoldappleRawProduct(RawProductBase):
        """STRICT: goldapple beauty PDPs always carry volume per shape-table.
        Null/empty volume_raw at append-time => parser drift, reject row + count
        toward 5% gate threshold (D-903)."""

        volume_raw: NonEmptyStr


    class ViledRawProduct(RawProductBase):
        """RELAXED: Contre-Jour / Wild Vetiver legitimately lack `Размер` attr
        per 08-01-SUMMARY Bug #3 + BUG-FINDINGS.md. volume_raw=None must NOT
        false-positive reject (would burn ops with alert noise)."""

        volume_raw: Optional[NonEmptyStr] = None
    ```

    6. Run `uv run pytest tests/storage/test_schemas.py -x` — MUST pass GREEN (11 tests).
    7. Run `uv run pytest -x -m "not live"` — confirm baseline still green.
    8. Commit GREEN: `feat(09-02b): GREEN — per-retailer Pydantic schemas (TH-06a/b, D-904)`.
  </action>
  <verify>
    <automated>uv run pytest tests/storage/test_schemas.py -x</automated>
  </verify>
  <done>
    - `src/ga_crawler/storage/schemas.py` exists with NonEmptyStr + RawProductBase + GoldappleRawProduct (strict volume_raw) + ViledRawProduct (Optional volume_raw)
    - `tests/storage/__init__.py` + `tests/storage/test_schemas.py` exist
    - 11 schema tests green
    - Atomic RED+GREEN commit pair landed
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire model_validate into SqliteSnapshotWriter.append + integration test (RED-first)</name>
  <files>
    src/ga_crawler/storage/sqlite.py,
    tests/integration/test_writer_schema_gate.py
  </files>
  <read_first>
    - 09-RESEARCH.md §4.2 (per-row validation in writer loop — verbatim skeleton)
    - 09-RESEARCH.md §7.2 (Pydantic ValidationError.errors() includes `input` by default — PII leak surface; project to {loc, type} ONLY)
    - 09-RESEARCH.md §9 Q1 (writer method is `append`, NOT `persist`)
    - 09-CONTEXT.md D-903 (writer-boundary, 5% gate, cascade position before PARSE-FIX-04 null-rate gate)
    - 09-PATTERNS.md lines 112-156 (sqlite.py modification site map + integration test analog)
    - src/ga_crawler/storage/sqlite.py:165-199 (SqliteSnapshotWriter.append — modify in-place)
    - tests/integration/test_storage_integration.py:39-95 (EXACT analog: `_setup`, `_row`, `SqliteSnapshotWriter` integration pattern)
  </read_first>
  <behavior>
    - Test 1 (`test_writer_validates_goldapple_strictly`): 3 products [valid, empty-volume, missing-volume] → only 1 INSERTed; `_last_rejected_reasons` has 2 entries with sku_id keys
    - Test 2 (`test_writer_relaxes_viled_volume_none`): viled product with `volume_raw=None` → 1 INSERTed; `_last_rejected_reasons` empty
    - Test 3 (`test_writer_no_input_key_in_rejected_reasons`): rejected reason dict structure is `{"sku_id": ..., "errors": [{"loc": [...], "type": "..."}, ...]}` — NO `"input"` key (T-09-PII guard per RESEARCH §7.2)
    - Test 4 (`test_writer_truncates_at_50_rejected`): if >50 rows fail validation, `_last_rejected_reasons` length is exactly 50 (memory bound per RESEARCH §4.2)
    - Test 5 (`test_writer_unknown_retailer_skips_validation`): if `retailer` is not in `_SCHEMA_BY_RETAILER` (e.g. "test"), validation is skipped (backward compat — Phase 2/3 don't break)
    - Test 6 (`test_writer_existing_baseline_still_passes`): the existing `test_snapshot_writer_appends_rows`-style integration (Phase 2 D-222) still green after wire-up
  </behavior>
  <action>
    **RED step — write integration test against the not-yet-modified writer.**

    1. Create `tests/integration/test_writer_schema_gate.py`:
    ```python
    """TH-06c — SqliteSnapshotWriter.append integration with Pydantic write-boundary.

    D-903: per-row schema_cls.model_validate(payload) inside the existing
    append() loop. ValidationError → row SKIPPED, reason captured into
    writer._last_rejected_reasons (truncated at 50; no `input` key per
    RESEARCH §7.2 PII landmine).

    Cascade position: structural drift caught here BEFORE Phase 8 PARSE-FIX-04
    null-rate gate (content drift).
    """

    from __future__ import annotations

    from pathlib import Path
    from typing import Optional

    import pytest
    from sqlmodel import Session, select

    from ga_crawler.storage.sqlite import (
        Snapshot,
        SqliteRunWriter,
        SqliteSnapshotWriter,
        init_db,
        make_engine,
    )


    def _setup(tmp_path: Path):
        db = tmp_path / "test.db"
        init_db(db)
        return make_engine(db)


    def _row(
        sku_id: str,
        name: str = "X",
        brand: str = "TestBrand",
        price: int = 1000,
        volume_raw: Optional[str] = "75 мл",
        **extras,
    ) -> dict:
        return {
            "sku_id": sku_id,
            "url": f"https://example.com/{sku_id}",
            "name": name,
            "brand": brand,
            "current_price": price,
            "volume_raw": volume_raw,
            **extras,
        }


    def _row_no_volume_key(sku_id: str, **kw) -> dict:
        r = _row(sku_id, **kw)
        del r["volume_raw"]
        return r


    def test_writer_validates_goldapple_strictly(tmp_path: Path) -> None:
        """3 products: valid, empty-volume, missing-volume → 1 INSERTed; 2 rejected."""
        engine = _setup(tmp_path)
        rw = SqliteRunWriter(engine)
        rid = rw.create()
        writer = SqliteSnapshotWriter(engine)
        products = [
            _row("100", name="Valid", volume_raw="75 мл"),
            _row("200", name="Empty", volume_raw=""),       # rejected
            _row_no_volume_key("300", name="Missing"),       # rejected
        ]
        n = writer.append(run_id=rid, retailer="goldapple", products=products)
        assert n == 1
        assert len(writer._last_rejected_reasons) == 2
        assert {r["sku_id"] for r in writer._last_rejected_reasons} == {"200", "300"}
        with Session(engine) as s:
            rows = list(s.exec(select(Snapshot)))
        assert len(rows) == 1
        assert rows[0].sku_id == "100"


    def test_writer_relaxes_viled_volume_none(tmp_path: Path) -> None:
        """D-904 viled-relaxed: volume_raw=None must NOT reject."""
        engine = _setup(tmp_path)
        rw = SqliteRunWriter(engine)
        rid = rw.create()
        writer = SqliteSnapshotWriter(engine)
        products = [_row("v-contre-jour", name="Contre-Jour", volume_raw=None)]
        n = writer.append(run_id=rid, retailer="viled", products=products)
        assert n == 1
        assert writer._last_rejected_reasons == []


    def test_writer_no_input_key_in_rejected_reasons(tmp_path: Path) -> None:
        """RESEARCH §7.2: e.errors() default emits 'input' (PII surface).
        Projection must yield ONLY {'loc', 'type'} per error."""
        engine = _setup(tmp_path)
        rw = SqliteRunWriter(engine)
        rid = rw.create()
        writer = SqliteSnapshotWriter(engine)
        bad = _row("sensitive", name="potentially-secret-data", volume_raw="")
        writer.append(run_id=rid, retailer="goldapple", products=[bad])
        assert len(writer._last_rejected_reasons) == 1
        reason = writer._last_rejected_reasons[0]
        assert reason["sku_id"] == "sensitive"
        assert isinstance(reason["errors"], list)
        for err in reason["errors"]:
            assert "input" not in err, f"PII landmine: 'input' leaked into rejected_reasons: {err}"
            assert set(err.keys()) == {"loc", "type"}


    def test_writer_truncates_at_50_rejected(tmp_path: Path) -> None:
        """Memory bound: _last_rejected_reasons capped at 50 entries (RESEARCH §4.2)."""
        engine = _setup(tmp_path)
        rw = SqliteRunWriter(engine)
        rid = rw.create()
        writer = SqliteSnapshotWriter(engine)
        # 100 invalid rows (all volume_raw="")
        products = [_row(str(i), name=f"S{i}", volume_raw="") for i in range(100)]
        writer.append(run_id=rid, retailer="goldapple", products=products)
        assert len(writer._last_rejected_reasons) == 50


    def test_writer_unknown_retailer_skips_validation(tmp_path: Path) -> None:
        """Backward compat: unknown retailer = no schema_cls => no validation.
        Phase 2/3 don't break."""
        engine = _setup(tmp_path)
        rw = SqliteRunWriter(engine)
        rid = rw.create()
        writer = SqliteSnapshotWriter(engine)
        # Note: schema would reject volume_raw="", but retailer="test" has no
        # entry in _SCHEMA_BY_RETAILER, so validation skipped.
        products = [_row("999", volume_raw="")]
        # Use a non-goldapple/non-viled retailer to bypass the dispatch table.
        # If 'test' is reserved by the writer, swap to 'unknown' or similar.
        n = writer.append(run_id=rid, retailer="test", products=products)
        assert n == 1
        assert writer._last_rejected_reasons == []


    def test_writer_baseline_appends_valid_rows(tmp_path: Path) -> None:
        """Regression guard: pre-existing valid-row INSERT still works post-wire-up."""
        engine = _setup(tmp_path)
        rw = SqliteRunWriter(engine)
        rid = rw.create()
        writer = SqliteSnapshotWriter(engine)
        products = [
            _row("100", name="A", volume_raw="50 мл"),
            _row("200", name="B", volume_raw="100 мл"),
        ]
        n = writer.append(run_id=rid, retailer="goldapple", products=products)
        assert n == 2
        with Session(engine) as s:
            rows = list(s.exec(select(Snapshot)))
        assert len(rows) == 2
    ```

    2. Run `uv run pytest tests/integration/test_writer_schema_gate.py -x` — MUST fail RED on `AttributeError: 'SqliteSnapshotWriter' has no attribute '_last_rejected_reasons'` or similar (writer not yet modified).
    3. Commit RED: `test(09-02b): RED — TH-06c writer + Pydantic integration stubs`.

    **GREEN step — wire `model_validate` into SqliteSnapshotWriter.append.**

    4. Edit `src/ga_crawler/storage/sqlite.py`. Add imports near top of file (alongside existing Snapshot/SQLModel imports):
    ```python
    from pydantic import ValidationError

    from ga_crawler.storage.schemas import (
        GoldappleRawProduct,
        RawProductBase,
        ViledRawProduct,
    )

    _SCHEMA_BY_RETAILER: dict[str, type[RawProductBase]] = {
        "goldapple": GoldappleRawProduct,
        "viled": ViledRawProduct,
    }

    _REJECTED_REASONS_CAP = 50  # RESEARCH §4.2 memory bound
    ```

    5. Modify `class SqliteSnapshotWriter.__init__` (sqlite.py:173-175) to initialize `_last_rejected_reasons`:
    ```python
    def __init__(self, engine, *, batch_size: int = 100):
        self.engine = engine
        self.batch_size = batch_size
        self._last_rejected_reasons: list[dict] = []  # Phase 9 TH-06c (D-903)
    ```

    6. Modify `SqliteSnapshotWriter.append` (sqlite.py:177-199) to wire `model_validate` inside the per-product loop. Replace the existing body with:
    ```python
    def append(self, run_id: int, retailer: str, products: list) -> int:
        if not products:
            self._last_rejected_reasons = []
            return 0
        inserted = 0
        rejected_reasons: list[dict] = []
        valid_fields = set(Snapshot.model_fields.keys())
        schema_cls = _SCHEMA_BY_RETAILER.get(retailer)  # Phase 9 D-903
        with Session(self.engine) as session:
            try:
                for product in products:
                    payload = {k: v for k, v in product.items() if k in valid_fields}
                    payload["run_id"] = run_id
                    payload["retailer"] = retailer
                    # Phase 9 TH-06c (D-903): per-row schema validation BEFORE INSERT.
                    # RESEARCH §7.2: project errors() to {loc, type} only — never 'input'.
                    if schema_cls is not None:
                        try:
                            schema_cls.model_validate(payload)
                        except ValidationError as ve:
                            if len(rejected_reasons) < _REJECTED_REASONS_CAP:
                                rejected_reasons.append({
                                    "sku_id": product.get("sku_id", "<unknown>"),
                                    "errors": [
                                        {"loc": list(err["loc"]), "type": err["type"]}
                                        for err in ve.errors()
                                    ],
                                })
                            continue  # skip INSERT for invalid row
                    row = Snapshot(**payload)
                    session.add(row)
                    inserted += 1
                    if inserted % self.batch_size == 0:
                        session.commit()
                session.commit()
            except Exception:
                session.rollback()
                raise
        self._last_rejected_reasons = rejected_reasons
        return inserted
    ```

    **NB:** This MUST keep `valid_fields` filter ordering unchanged (filter first, then validate). Schema's `extra="ignore"` works in concert with the filter.

    7. Run `uv run pytest tests/integration/test_writer_schema_gate.py -x` — MUST pass GREEN (6 tests).
    8. Run `uv run pytest tests/integration/test_storage_integration.py -x` — Phase 2 baseline integration still green.
    9. Run `uv run pytest -x -m "not live"` — full default suite still green; Phase 2/3/8 integration unaffected.
    10. Commit GREEN: `feat(09-02b): GREEN — wire Pydantic model_validate at SqliteSnapshotWriter.append (TH-06c, D-903)`.
  </action>
  <verify>
    <automated>uv run pytest tests/integration/test_writer_schema_gate.py tests/integration/test_storage_integration.py -x</automated>
  </verify>
  <done>
    - `_SCHEMA_BY_RETAILER` dict declared at module level in sqlite.py
    - `SqliteSnapshotWriter.__init__` initializes `self._last_rejected_reasons: list[dict] = []`
    - `SqliteSnapshotWriter.append` calls `schema_cls.model_validate(payload)` inside the loop with try/except `ValidationError`; on raise, append `{sku_id, errors:[{loc,type}]}` and `continue`
    - Errors projection contains ONLY `loc` and `type` keys (no `input`)
    - Rejected reasons capped at 50 entries
    - 6 new integration tests pass + existing storage integration baseline pass
    - Atomic RED+GREEN commit pair landed
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Ship schema_rejected_rate_gate + SCHEMA_STATS_KEYS + unit tests (RED-first)</name>
  <files>
    src/ga_crawler/runner/gates.py,
    src/ga_crawler/runner/stats.py,
    tests/runner/test_schema_rejected_gate.py
  </files>
  <read_first>
    - 09-RESEARCH.md §6.3 (schema_rejected_rate_gate — verbatim skeleton)
    - 09-RESEARCH.md §6.4 (SCHEMA_STATS_KEYS tuple — verbatim)
    - 09-RESEARCH.md §9 Q3 (NO new StatsBuilder; inline patch_stats only)
    - 09-CONTEXT.md D-903 (threshold 0.05; strict >; failure_reason='schema_validation_rejected_rate')
    - 09-PATTERNS.md lines 159-256 (gates.py + stats.py modification site map)
    - src/ga_crawler/runner/gates.py:285-342 (EXACT analog: ParserDriftGateResult + parser_drift_null_rate_gate Phase 8 D-815)
    - src/ga_crawler/runner/gates.py:382-394 (`__all__` append target)
    - src/ga_crawler/runner/stats.py:149-159 (`VILED_STATS_KEYS` analog)
    - src/ga_crawler/runner/stats.py:219-226 (`__all__` append target)
    - tests/runner/test_parser_drift_gate.py:21-79 (EXACT analog: pure-function gate tests; threshold sweep)
  </read_first>
  <behavior>
    - Test 1 (`test_below_threshold_passes`): rate 0.04 < 0.05 → passed=True; failure_reason=None
    - Test 2 (`test_exactly_at_threshold_passes`): rate = exactly 0.05 → passed=True (STRICT >; mirrors Phase 8 D-815 convention)
    - Test 3 (`test_above_threshold_fails`): rate 0.06 → passed=False; failure_reason='schema_validation_rejected_rate'
    - Test 4 (`test_zero_total_attempted_passes`): empty-input edge — rate undefined → pass cleanly
    - Test 5 (`test_custom_threshold`): threshold=0.2; 3/10 = 0.3 > 0.2 → fail
    - Test 6 (`test_result_is_frozen_dataclass`): SchemaRejectedGateResult is frozen — `r.passed = False` raises
    - Test 7 (`test_gate_in_all_export`): both `schema_rejected_rate_gate` and `SchemaRejectedGateResult` are in `gates.__all__`
    - Test 8 (`test_schema_stats_keys_namespace`): `SCHEMA_STATS_KEYS` tuple is exported from `stats` module and contains the 3 expected keys with `schema.` prefix
  </behavior>
  <action>
    **RED step — write gate unit test first.**

    1. Create `tests/runner/test_schema_rejected_gate.py`:
    ```python
    """TH-06d — schema_rejected_rate_gate threshold semantics + SCHEMA_STATS_KEYS.

    Mirrors tests/runner/test_parser_drift_gate.py shape (Phase 8 D-815 helper).
    STRICT > convention: exactly threshold passes; anything above fails.
    """

    from __future__ import annotations

    import pytest

    from ga_crawler.runner import gates as gates_mod
    from ga_crawler.runner import stats as stats_mod
    from ga_crawler.runner.gates import (
        SchemaRejectedGateResult,
        schema_rejected_rate_gate,
    )


    def test_below_threshold_passes() -> None:
        r = schema_rejected_rate_gate(rejected_count=4, total_attempted=100)
        assert r.passed is True
        assert r.failure_reason is None
        assert r.rejected_rate == pytest.approx(0.04)
        assert r.rejected_count == 4
        assert r.total_attempted == 100


    def test_exactly_at_threshold_passes() -> None:
        """STRICT > 0.05 — exactly 5% PASSES (mirror parser_drift_null_rate_gate D-815)."""
        r = schema_rejected_rate_gate(rejected_count=5, total_attempted=100)
        assert r.passed is True
        assert r.failure_reason is None


    def test_just_above_threshold_fails() -> None:
        """0.0501 (6/100 ≈ 0.06) fails."""
        r = schema_rejected_rate_gate(rejected_count=6, total_attempted=100)
        assert r.passed is False
        assert r.failure_reason == "schema_validation_rejected_rate"
        assert r.rejected_rate == pytest.approx(0.06)


    def test_zero_total_attempted_passes() -> None:
        """Empty-input safety: rate undefined → pass cleanly (matches gate skeleton §6.3)."""
        r = schema_rejected_rate_gate(rejected_count=0, total_attempted=0)
        assert r.passed is True
        assert r.rejected_rate == 0.0
        assert r.failure_reason is None


    def test_custom_threshold_fails() -> None:
        r = schema_rejected_rate_gate(rejected_count=3, total_attempted=10, threshold=0.2)
        assert r.passed is False
        assert r.failure_reason == "schema_validation_rejected_rate"


    def test_custom_threshold_passes_at_boundary() -> None:
        r = schema_rejected_rate_gate(rejected_count=2, total_attempted=10, threshold=0.2)
        assert r.passed is True


    def test_result_is_frozen_dataclass() -> None:
        r = schema_rejected_rate_gate(0, 100)
        assert isinstance(r, SchemaRejectedGateResult)
        with pytest.raises(Exception):
            r.passed = False  # type: ignore[misc]


    def test_gate_in_all_export() -> None:
        assert "schema_rejected_rate_gate" in gates_mod.__all__
        assert "SchemaRejectedGateResult" in gates_mod.__all__


    def test_schema_stats_keys_namespace() -> None:
        assert hasattr(stats_mod, "SCHEMA_STATS_KEYS")
        assert "SCHEMA_STATS_KEYS" in stats_mod.__all__
        keys = stats_mod.SCHEMA_STATS_KEYS
        assert "schema.rejected_count" in keys
        assert "schema.rejected_rate" in keys
        assert "schema.rejected_reasons" in keys
        # All keys must carry the schema. namespace prefix (run-level not retailer)
        for k in keys:
            assert k.startswith("schema."), f"key {k!r} not in schema.* namespace"
    ```

    2. Run `uv run pytest tests/runner/test_schema_rejected_gate.py -x` — MUST fail RED on `ImportError: cannot import name 'schema_rejected_rate_gate'`.
    3. Commit RED: `test(09-02b): RED — TH-06d schema_rejected_rate_gate + SCHEMA_STATS_KEYS stubs`.

    **GREEN step — append gate + stats namespace.**

    4. Edit `src/ga_crawler/runner/gates.py`. After line 342 (end of `parser_drift_null_rate_gate` function), BEFORE `# ---- Backward-compat shims` block, INSERT:
    ```python
    # ---- D-903 TEST-HARNESS-06 schema-rejected-rate sanity gate (Phase 9 Plan 09-02b) ----


    @dataclass(frozen=True)
    class SchemaRejectedGateResult:
        """Result of the TEST-HARNESS-06 schema-rejection sanity gate.

        Fields:
          passed: True if rejected_rate is at-or-below threshold.
          rejected_rate: float in [0, 1].
          rejected_count: int — per-row Pydantic ValidationError catches.
          total_attempted: int — products handed to SqliteSnapshotWriter.append.
          failure_reason: None if passed; otherwise 'schema_validation_rejected_rate'.

        Source: 09-CONTEXT.md D-903; 09-RESEARCH.md §6.3; mirrors
        ParserDriftGateResult (Phase 8 D-815) shape verbatim.
        """

        passed: bool
        rejected_rate: float
        rejected_count: int
        total_attempted: int
        failure_reason: Optional[str]


    def schema_rejected_rate_gate(
        rejected_count: int,
        total_attempted: int,
        *,
        threshold: float = 0.05,
    ) -> SchemaRejectedGateResult:
        """D-903: TEST-HARNESS-06 schema-rejection sanity gate.

        rejected_rate = rejected_count / total_attempted.

        Threshold semantics: STRICT GREATER-THAN (`> 0.05` fails; exactly 0.05
        passes). Matches Phase 8 parser_drift_null_rate_gate convention (D-815):
        synthetic regression at rate == threshold passes cleanly, while
        threshold + epsilon correctly fails.

        Position in run pipeline: AFTER SqliteSnapshotWriter.append, BEFORE
        Phase 8 parser_drift_null_rate_gate (cascade: structural drift catches
        earlier than content drift).

        Source: 09-CONTEXT.md D-903; 09-RESEARCH.md §6.3.
        """
        if total_attempted == 0:
            return SchemaRejectedGateResult(
                passed=True,
                rejected_rate=0.0,
                rejected_count=0,
                total_attempted=0,
                failure_reason=None,
            )
        rate = rejected_count / total_attempted
        failed = rate > threshold
        return SchemaRejectedGateResult(
            passed=(not failed),
            rejected_rate=rate,
            rejected_count=rejected_count,
            total_attempted=total_attempted,
            failure_reason=("schema_validation_rejected_rate" if failed else None),
        )
    ```

    5. Edit `src/ga_crawler/runner/gates.py` `__all__` block (L382-394): add `"schema_rejected_rate_gate"` and `"SchemaRejectedGateResult"` entries (alphabetical position is fine; place them adjacent to Phase 8's `parser_drift_null_rate_gate` and `ParserDriftGateResult` for grouping).

    6. Edit `src/ga_crawler/runner/stats.py`. After line 159 (end of `VILED_STATS_KEYS`), BEFORE the `_VILED_BARE_TO_NAMESPACED` line, INSERT:
    ```python


    # ---- Phase 9 TH-06c schema.* namespace (run-level, NOT retailer-scoped) ----
    # Per RESEARCH §9 Q3: orchestrator calls patch_stats inline with these keys
    # after SqliteSnapshotWriter.append returns; NO SchemaStatsBuilder class
    # (single-source namespace; future run-level stats may warrant a builder).

    SCHEMA_STATS_KEYS: tuple[str, ...] = (
        "schema.rejected_count",     # int — per-row Pydantic ValidationError catches
        "schema.rejected_rate",      # float — rejected_count / total_attempted
        "schema.rejected_reasons",   # list[{sku_id, errors:[{loc,type},...]}], cap 50
    )
    ```

    7. Edit `src/ga_crawler/runner/stats.py` `__all__` block (L219-226): add `"SCHEMA_STATS_KEYS"` entry adjacent to `"VILED_STATS_KEYS"`.

    8. Run `uv run pytest tests/runner/test_schema_rejected_gate.py -x` — MUST pass GREEN (9 tests).
    9. Run `uv run pytest tests/runner/test_parser_drift_gate.py -x` — Phase 8 baseline still green (regression guard).
    10. Run `uv run pytest -x -m "not live"` — full default suite green.
    11. Commit GREEN: `feat(09-02b): GREEN — schema_rejected_rate_gate + SCHEMA_STATS_KEYS (TH-06d, D-903)`.
  </action>
  <verify>
    <automated>uv run pytest tests/runner/test_schema_rejected_gate.py tests/runner/test_parser_drift_gate.py -x</automated>
  </verify>
  <done>
    - `SchemaRejectedGateResult` frozen-dataclass + `schema_rejected_rate_gate` defined in `runner/gates.py`
    - Both added to `gates.__all__`
    - `SCHEMA_STATS_KEYS` tuple defined in `runner/stats.py` with 3 keys all prefixed `schema.`
    - Added to `stats.__all__`
    - 9 gate tests green + Phase 8 parser-drift-gate tests still green
    - Atomic RED+GREEN commit pair landed
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| parser output (dispatcher dict) → SqliteSnapshotWriter.append | Untrusted shape; Phase 8 parser regression may emit wrong types/empties |
| ValidationError.errors() → runs.stats persistence | Pydantic default includes `input` field with raw value (PII surface per RESEARCH §7.2) |
| Schema-gate threshold (5%) | Too tight → false-positive run-fail; too loose → silent passthrough |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-09-SCHEMA | Tampering | SqliteSnapshotWriter.append (storage boundary) | mitigate | Per-row `model_validate` inside loop; raises `ValidationError` → row SKIPPED + reason captured to `_last_rejected_reasons` (truncated 50); rate-gate flips run to `failed` at >5% — proves structural drift visible BEFORE SQL INSERT |
| T-09-GATE | Tampering (false positive/negative) | `schema_rejected_rate_gate` threshold | mitigate | 0.05 chosen as 10× tighter than Phase 8 PARSE-FIX-04's 0.5 (structural drift is order-of-magnitude rarer than content nulls); STRICT `>` mirrors D-815 convention — exactly 0.05 passes; threshold revisitable post-deploy without API break (kw-only `threshold` arg) |
| T-09-PII | Information Disclosure | Pydantic `ValidationError.errors()` includes `'input'` (raw value) | mitigate | Writer projects each error dict to `{"loc": list(err["loc"]), "type": err["type"]}` ONLY — never persists raw input; integration test `test_writer_no_input_key_in_rejected_reasons` asserts `set(err.keys()) == {"loc", "type"}` |
</threat_model>

<verification>
- `uv run pytest tests/storage/test_schemas.py -x` — 11 schema tests green
- `uv run pytest tests/integration/test_writer_schema_gate.py tests/integration/test_storage_integration.py -x` — writer integration + Phase 2 baseline green
- `uv run pytest tests/runner/test_schema_rejected_gate.py tests/runner/test_parser_drift_gate.py -x` — new gate + Phase 8 baseline green
- `uv run pytest -x -m "not live"` — full default suite green (~860 tests after 09-01 + 09-02b)
- `grep -n "model_validate" src/ga_crawler/storage/sqlite.py` — at least one hit inside `append`
- `grep -n "_SCHEMA_BY_RETAILER" src/ga_crawler/storage/sqlite.py` — module-level dict declared
- `grep -n "_last_rejected_reasons" src/ga_crawler/storage/sqlite.py` — both `__init__` and tail assignment
- `grep -n "schema_rejected_rate_gate" src/ga_crawler/runner/gates.py` — function + `__all__` entries
- `grep -n "SCHEMA_STATS_KEYS" src/ga_crawler/runner/stats.py` — tuple + `__all__` entry
- `grep -nv '^#' src/ga_crawler/storage/sqlite.py | grep -c '"input"'` — exactly 0 hits (no `input` key persisted, per §7.2 guard); be aware bare comment-strip is for the writer module only
</verification>

<success_criteria>
- `src/ga_crawler/storage/schemas.py` exists with NonEmptyStr / RawProductBase / GoldappleRawProduct (strict volume_raw) / ViledRawProduct (Optional volume_raw) — TEST-HARNESS-06 a/b
- `SqliteSnapshotWriter.append` wires per-row `schema_cls.model_validate(payload)` via `_SCHEMA_BY_RETAILER`; `_last_rejected_reasons` capped at 50, errors projected to `{loc, type}` only — TEST-HARNESS-06 c
- `schema_rejected_rate_gate(rejected_count, total_attempted, *, threshold=0.05)` ships as frozen-dataclass-returning function with STRICT `>` semantics — TEST-HARNESS-06 d
- `SCHEMA_STATS_KEYS` tuple shipped in `runner/stats.py` (`schema.rejected_count`, `schema.rejected_rate`, `schema.rejected_reasons`)
- Both `gates.__all__` and `stats.__all__` updated
- 4 new test files exist: `tests/storage/__init__.py`, `tests/storage/test_schemas.py`, `tests/integration/test_writer_schema_gate.py`, `tests/runner/test_schema_rejected_gate.py`
- All new tests GREEN; Phase 2/3/8 baselines unaffected
- T-09-PII guard proven by `test_writer_no_input_key_in_rejected_reasons`
- Atomic RED+GREEN commit pairs landed for each task (D-811 inheritance)
- `uv run pytest -x -m "not live"` GREEN after merge
</success_criteria>

<output>
After completion, create `.planning/phases/09-live-html-harness/09-02b-SUMMARY.md` per `summary.md` template:
- Wave executed: 1 (parallel-B; depends_on [09-01])
- Requirements closed: TEST-HARNESS-06 (a strict goldapple, b relaxed viled, c writer integration, d gate threshold)
- Files created: 5 (schemas.py, tests/storage/__init__.py, tests/storage/test_schemas.py, tests/integration/test_writer_schema_gate.py, tests/runner/test_schema_rejected_gate.py)
- Files modified: 3 (sqlite.py, gates.py, stats.py)
- Boundary-language note: writer method confirmed `append` (per RESEARCH §9 Q1); CONTEXT.md D-903 "persist" is conceptual; cross-ref for any future reader
- Tests delta: +22 tests (11 schema + 6 writer integration + 9 gate; minus inevitable double-count if any)
- Time-stamp last GREEN commit (anchor for 09-03 D-902 P2 GO/NO-GO 8h gate measurement — coordinate with 09-02a's last commit)
- Orchestrator wire-up note: this plan ships the gate function + writer integration; full orchestrator call-site change (patch_stats `schema.*` + gate result → run_writer.fail) carried by `runners/main_run.py` via standard pattern OR may be follow-on plan in v1.2 if explicit wiring needed
</output>
