# Phase 9: Live-HTML Harness — Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 18 (11 new files + 5 modified files + 2 P2-conditional)
**Analogs found:** 14 / 18 (3 greenfield, 1 P2-conditional greenfield)

> Source-of-truth for new-file inventory: `09-VALIDATION.md` "Wave 0 Requirements" block (lines 62-80).
> All file paths absolute against repo root `C:\Users\gstorepc\projects\ga_crawler`.
> Cross-reference: `09-CONTEXT.md` decisions D-901..D-907 (lines 33-67); `09-RESEARCH.md` §3, §4, §5, §6, §7 (code skeletons + landmines).

---

## File Classification

### New files

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `src/ga_crawler/storage/schemas.py` | model (Pydantic) | writer-validate path | `src/ga_crawler/storage/sqlite.py:60-87` (Snapshot SQLModel — table-shape mirrors schema-shape) + `src/ga_crawler/parsers/goldapple_microdata.py:45-67` (`GoldappleRawProduct` dataclass — field shape) | role-match (Pydantic mirrors dataclass + SQLModel) |
| `tests/_snapshot_extension.py` *(or inline in conftest if ≤30 LOC)* | helper module / pytest plugin | fixture-load path | `09-RESEARCH.md §3.1` (verbatim Context7 skeleton); no in-repo analog — first syrupy use | greenfield (verbatim spec) |
| `tests/_assert_fixture_clean` *(helper in conftest)* | helper / canary | drift-detect path | `09-RESEARCH.md §6.1` (verbatim) + `tests/conftest.py:23-37` (fixture-loader chain) | role-match (helper wrapped by loader) |
| `tests/_fixture_metadata.py` | helper module / dataclass + JSON I/O | fixture-load path | `09-RESEARCH.md §6.2` (verbatim) — greenfield | greenfield |
| `tests/_html_normalize.py` | helper / pure-function | drift-detect path | `09-RESEARCH.md §7.1` (landmine spec — verbatim) — greenfield | greenfield |
| `tests/test_snapshot_extension.py` | unit test | parser-eval path | `tests/unit/test_goldapple_microdata_parser.py:1-72` (shape: import + per-attribute assertion) | role-match (unit test of pure module) |
| `tests/test_live_fixtures_pii_canary.py` | unit test / canary | drift-detect path | `tests/runner/test_parser_drift_gate.py:21-79` (shape: pure-function gate tests; threshold sweep) | role-match |
| `tests/test_fixture_metadata.py` | unit test | fixture-load path | `tests/unit/test_goldapple_microdata_parser.py` (shape) | role-match |
| `tests/test_snapshot_soundness.py` | unit test (negative) | drift-detect path | `tests/runner/test_parser_drift_gate.py:36-65` (negative path: fail-when-rate-exceeds) | role-match |
| `tests/storage/__init__.py` | package marker | n/a | `tests/integration/__init__.py` (likely; package marker) | role-match |
| `tests/storage/test_schemas.py` | unit test | writer-validate path | `tests/unit/test_goldapple_microdata_parser.py:20-60` (round-trip assertion shape) + `tests/runner/test_parser_drift_gate.py:21-79` (boundary-style assertions) | role-match |
| `tests/integration/test_writer_schema_gate.py` | integration test | writer-validate path | `tests/integration/test_storage_integration.py:39-95` (`SqliteSnapshotWriter` integration: `_setup` + `_row` helpers; assert via `Session(engine).exec(select(Snapshot))`) | exact (same module under test) |
| `tests/runner/test_schema_rejected_gate.py` | unit test | gate-decision path | `tests/runner/test_parser_drift_gate.py:21-79` (exact analog: pure-function gate, frozen-dataclass result, threshold-sweep cases) | exact |
| `tests/live/__init__.py` | package marker | n/a | `tests/integration/__init__.py` (likely; package marker) | role-match |
| `tests/live/test_parser_drift.py` | live test (marker `@pytest.mark.live`) | parser-eval path | `tests/unit/test_goldapple_microdata_parser.py:20-60` (parse PDP + assert invariants) + `09-RESEARCH.md §5.2` (verbatim `refresh_live` branch skeleton) | role-match + spec-verbatim |
| `tests/test_brand_coverage_canary.py` *(P2 conditional)* | integration test / canary | drift-detect path | `09-RESEARCH.md §6.5` (verbatim) — greenfield; reads `v_current_snapshots` (DB inspection pattern from `tests/integration/test_v_current_snapshots.py`) | greenfield |
| `tests/integration/test_capture_fixtures_cli.py` *(P2 conditional)* | integration test | fixture-load path | `tests/integration/test_cli_report_subcommand.py` *(if exists; subcommand integration shape)* + `src/ga_crawler/cli.py:1-80` (subcommand registration pattern) | role-match |

### Modified files

| Modified File | Role | What Changes | Analog Section |
|---------------|------|--------------|----------------|
| `tests/conftest.py` | fixture-loader extension | Extend `goldapple_pdp_html_live_stereotype` (L95-104), `goldapple_pdp_html_live_armani` (L107-115), `viled_pdp_html_live_contre_jour` (L217-226) loaders to call `_assert_fixture_clean(path)` before `read_text`. Add `pytest_addoption("--refresh-live")` + `refresh_live` fixture + `html_snapshot` fixture (per `09-RESEARCH.md §3.1, §5.2`). | `tests/conftest.py:23-37` + `tests/conftest.py:95-115, 217-226` |
| `src/ga_crawler/storage/sqlite.py` | writer / persistence | Inside `SqliteSnapshotWriter.append` loop body (L186-192): wire `_SCHEMA_BY_RETAILER.get(retailer).model_validate(payload)` inside try/except `ValidationError`; on raise, accumulate `{sku_id, errors:[{loc,type}]}` into `self._last_rejected_reasons`; `continue` to skip INSERT. **NB: method is `append`, NOT `persist` (09-RESEARCH §9 Q1).** | `src/ga_crawler/storage/sqlite.py:165-199` |
| `src/ga_crawler/runner/gates.py` | gate / pure function | Append `schema_rejected_rate_gate(rejected_count, total_attempted, *, threshold=0.05) -> SchemaRejectedGateResult`. Mirror `ParserDriftGateResult` frozen-dataclass shape; STRICT `>` semantics; reason sentinel `"schema_validation_rejected_rate"`. Export in `__all__`. | `src/ga_crawler/runner/gates.py:285-342` + L382-394 |
| `src/ga_crawler/runner/stats.py` | stats keys / namespace | Append `SCHEMA_STATS_KEYS: tuple[str, ...] = ("schema.rejected_count", "schema.rejected_rate", "schema.rejected_reasons")`. **NO new `SchemaStatsBuilder`** (per `09-RESEARCH §9 Q3` — orchestrator calls `patch_stats(run_id, {"schema.rejected_count": ...})` inline). | `src/ga_crawler/runner/stats.py:149-159` (`VILED_STATS_KEYS` analog) |
| `pyproject.toml` | dependency manifest | `[dependency-groups].dev`: append `"syrupy>=4.7,<5.0"` (resolves to 4.9.1 per RESEARCH §1). NO change to `[tool.pytest.ini_options].markers` — `live` marker already declared at L51. | `pyproject.toml:31-38` |
| `README.md` | docs (RU-primary operator runbook) | Append `## Live HTML harness` section before `## Dev setup` (after `## Логи`, L199-236). Document: when to run (pre-deploy / post-suspected-drift / by operator request), how to run (`pytest -m live` cassette-replay; `pytest -m live --refresh-live --snapshot-update` operator path), how to read drift output (`.planning/research/parser-drift-YYYY-MM-DD.md`), stale-fixture warning semantics (30d). | `README.md:60-87` (ENV vars section — RU-primary tone) + `README.md:153-198` (Operations runbook subsection style) |

---

## Pattern Assignments

### `src/ga_crawler/storage/schemas.py` (model, writer-validate)

**Analog:** `src/ga_crawler/parsers/goldapple_microdata.py:45-67` (field shape) + `src/ga_crawler/storage/sqlite.py:60-87` (table-shape mirror)

**Pydantic 2.10 schema pattern** — verbatim from `09-RESEARCH.md §4.4`:

```python
# src/ga_crawler/storage/schemas.py
"""Pydantic raw-product schemas — write-boundary validation at SqliteSnapshotWriter.append.

Phase 9 TEST-HARNESS-06 (D-903 + D-904):
  - GoldappleRawProduct: STRICT — volume_raw REQUIRED (NonEmptyStr).
    Evidence: goldapple beauty PDPs carry [...] ОБЪЁМ / МЛ block on 25/30 spike pages
    (spike-findings-v1.1-brand-name-shapes/SKILL.md L39).
  - ViledRawProduct: RELAXED — volume_raw Optional[NonEmptyStr]=None.
    Evidence: Frederic Malle Contre-Jour, Creed Wild Vetiver legitimately lack
    `Размер` attribute (08-01-SUMMARY.md Bug #3 + BUG-FINDINGS.md).

Schema field shape mirrors:
  - GoldappleRawProduct dataclass (parsers/goldapple_microdata.py:45-67) — 9-field
    dispatcher dict (asdict() at parsers/dispatcher.py:51).
  - Snapshot SQLModel column types (storage/sqlite.py:60-87) — but TIGHTENED:
    current_price: int>0 vs Optional[int] (D-904 + 09-RESEARCH §4.4 footnote).
"""

from __future__ import annotations

from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class RawProductBase(BaseModel):
    """Shared fields between goldapple/viled raw product dicts (post-dispatcher)."""
    model_config = ConfigDict(extra="ignore")  # SqliteSnapshotWriter.append pre-filters via valid_fields

    sku_id: NonEmptyStr
    url: NonEmptyStr
    name: NonEmptyStr
    brand: NonEmptyStr
    current_price: int = Field(gt=0)  # KZT integer; gt=0 rejects 0/negative


class GoldappleRawProduct(RawProductBase):
    """Strict: goldapple beauty PDPs always carry volume per shape-table.md.
    Null volume at append-time => parser drift, reject row + count toward 5% gate."""
    volume_raw: NonEmptyStr


class ViledRawProduct(RawProductBase):
    """Relaxed: Contre-Jour / Wild Vetiver legitimately lack `Размер` attribute
    per 08-01-SUMMARY Bug #3 + BUG-FINDINGS.md."""
    volume_raw: Optional[NonEmptyStr] = None
```

**Cross-reference for planner:** Field set MUST mirror `GoldappleRawProduct` dataclass (`parsers/goldapple_microdata.py:46-67`): `sku_id, url, name, brand_raw→brand, current_price, was_price, currency, availability, raw_volume_text→volume_raw`. The dispatcher `asdict()` (dispatcher.py:51) is the actual dict shape Pydantic sees — confirm key names (e.g., `brand_raw` vs `brand`) by reading `parsers/goldapple_microdata.py:45-67` before sealing.

---

### `src/ga_crawler/storage/sqlite.py` MODIFICATION (writer, writer-validate)

**Analog:** Self — extend the existing `SqliteSnapshotWriter.append` loop at L177-199.

**Existing loop pattern** (`sqlite.py:177-199`):
```python
def append(self, run_id: int, retailer: str, products: list) -> int:
    if not products:
        return 0
    inserted = 0
    valid_fields = set(Snapshot.model_fields.keys())
    with Session(self.engine) as session:
        try:
            for product in products:
                payload = {k: v for k, v in product.items() if k in valid_fields}
                payload["run_id"] = run_id
                payload["retailer"] = retailer
                row = Snapshot(**payload)
                session.add(row)
                inserted += 1
                if inserted % self.batch_size == 0:
                    session.commit()
            session.commit()
        except Exception:
            session.rollback()
            raise
    return inserted
```

**Inject Pydantic validation** per `09-RESEARCH.md §4.2`:
- After `payload` is built (L188-189), BEFORE `row = Snapshot(**payload)` (L190): wrap `schema_cls.model_validate(payload)` in try/except `ValidationError`.
- On `ValidationError`: append `{"sku_id": product.get("sku_id", "<unknown>"), "errors": [{"loc": list(err["loc"]), "type": err["type"]} for err in e.errors()]}` to `rejected_reasons`; `continue` (skip `row = Snapshot(**payload)` and `session.add`).
- After loop: `self._last_rejected_reasons = rejected_reasons[:50]` (cap per RESEARCH §4.2 memory note).
- Add module-level `_SCHEMA_BY_RETAILER = {"goldapple": GoldappleRawProduct, "viled": ViledRawProduct}`.
- **LANDMINE (RESEARCH §7.2):** Do NOT include `'input'` key from `e.errors()` — Pydantic emits original input value which may carry PII; project to `{loc, type}` only.

**Stats integration (outside the writer):** Orchestrator reads `writer._last_rejected_reasons` after `append()` returns, then:
```python
run_writer.patch_stats(run_id, {
    "schema.rejected_count": len(writer._last_rejected_reasons),
    "schema.rejected_rate": len(writer._last_rejected_reasons) / total_attempted,
    "schema.rejected_reasons": writer._last_rejected_reasons,  # already capped at 50
})
```

---

### `src/ga_crawler/runner/gates.py` MODIFICATION (gate, gate-decision)

**Analog:** `src/ga_crawler/runner/gates.py:285-342` — `ParserDriftGateResult` + `parser_drift_null_rate_gate` (exact analog, D-815 helper that Phase 8 added).

**Pattern to copy** (gates.py:288-342, verbatim shape):

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
    v_fail = volume_null_rate > threshold
    b_fail = brand_null_rate > threshold
    # ... priority pick ...
    return ParserDriftGateResult(
        passed=(not v_fail and not b_fail),
        volume_null_rate=volume_null_rate,
        brand_null_rate=brand_null_rate,
        failure_reason=reason,
    )
```

**New gate** — verbatim from `09-RESEARCH.md §6.3` (apply same `frozen=True` + strict-`>` + `Optional[str]` failure reason patterns):

```python
@dataclass(frozen=True)
class SchemaRejectedGateResult:
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

    Position in run pipeline: AFTER SqliteSnapshotWriter.append, BEFORE
    parser_drift_null_rate_gate (cascade: structural-drift catches earlier
    than content-drift).
    """
    if total_attempted == 0:
        return SchemaRejectedGateResult(True, 0.0, 0, 0, None)
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

**Append to `__all__`** at `gates.py:382-394`: add `"schema_rejected_rate_gate"` and `"SchemaRejectedGateResult"`.

---

### `src/ga_crawler/runner/stats.py` MODIFICATION (stats keys, gate-decision)

**Analog:** `src/ga_crawler/runner/stats.py:149-159` — `VILED_STATS_KEYS` tuple constant.

**Pattern to copy** (stats.py:149-159 verbatim):
```python
VILED_STATS_KEYS: tuple[str, ...] = (
    "viled.fetch_count",
    "viled.fetch_failures",
    ...
)
```

**New constant** — append (per `09-RESEARCH.md §6.4` + §9 Q3 NO new builder):
```python
# Run-level (NOT retailer-scoped) — first such namespace.
# Per 09-RESEARCH §9 Q3: orchestrator calls patch_stats inline; NO SchemaStatsBuilder.
SCHEMA_STATS_KEYS: tuple[str, ...] = (
    "schema.rejected_count",         # int  — per-row Pydantic ValidationError catches
    "schema.rejected_rate",          # float — rejected_count / total_attempted_persist
    "schema.rejected_reasons",       # list[{sku_id, errors:[{loc, type}, ...]}], capped at 50
)
```

**No new class.** Do NOT add `SchemaStatsBuilder` (see RESEARCH §9 Q3). Future run-level stats (delivery, schedule) could warrant a builder; deferred to v1.2.

---

### `tests/conftest.py` MODIFICATION (fixture-loader extension, fixture-load)

**Analog:** `tests/conftest.py:23-37` (`goldapple_pdp_html` loader pattern) + `tests/conftest.py:95-115, 217-226` (existing `_live-*.html` loaders).

**Existing loader pattern** (`conftest.py:95-104`):
```python
@pytest.fixture(scope="session")
def goldapple_pdp_html_live_stereotype() -> str:
    """STEREOTYPE / SAĜO live PDP captured 2026-05-13 (Bug #1+#2 evidence)."""
    return (FIXTURES_DIR / "_live-2026-05-13-stereotype.html").read_text(encoding="utf-8")
```

**Extension pattern (D-907)** — wrap with `_assert_fixture_clean(path)` BEFORE `.read_text(...)`:
```python
@pytest.fixture(scope="session")
def goldapple_pdp_html_live_stereotype() -> str:
    """... (existing docstring) ..."""
    path = FIXTURES_DIR / "_live-2026-05-13-stereotype.html"
    _assert_fixture_clean(path)        # D-907 fixture-loader integration
    return path.read_text(encoding="utf-8")
```

Apply the same wrapping to:
- `goldapple_pdp_html_live_armani` (`conftest.py:107-115`)
- `viled_pdp_html_live_contre_jour` (`conftest.py:217-226`)

**`_assert_fixture_clean(path)` helper** — verbatim paste from `09-RESEARCH.md §6.1` into `conftest.py` (Claude's Discretion: keep inline if ≤30 LOC; otherwise extract to `tests/_assert_fixture_clean.py`).

**`pytest_addoption("--refresh-live")` + `refresh_live` fixture** — verbatim paste from `09-RESEARCH.md §5.2` into `conftest.py`. The custom flag pattern is in-pattern with pytest 8 docs.

**`html_snapshot` fixture** — verbatim paste from `09-RESEARCH.md §3.1` (wraps `snapshot.with_defaults(extension_class=HTMLSnapshotExtension)`).

**Stale-fixture age warning** — verbatim from `09-RESEARCH.md §5.3` (`_check_fixture_age(sidecar_path)` using stdlib `warnings.warn`).

---

### `tests/test_snapshot_extension.py` (unit test, parser-eval)

**Analog:** `tests/unit/test_goldapple_microdata_parser.py:1-72` (shape: simple unit-test file with module-level imports, per-attribute assertion functions).

**Pattern from analog** (test_goldapple_microdata_parser.py:1-30):
```python
"""Goldapple microdata parser tests - round-trip + priceType + sanity + enum."""

from __future__ import annotations

import pytest
from selectolax.parser import HTMLParser

from ga_crawler.parsers.goldapple_microdata import (
    GoldappleRawProduct,
    parse_pdp,
)


def test_parse_real_pdp_returns_product(goldapple_pdp_html: str) -> None:
    product = parse_pdp(goldapple_pdp_html, GIVENCHY_URL)
    assert product is not None
    assert isinstance(product, GoldappleRawProduct)
```

**For `tests/test_snapshot_extension.py`**, mirror the import + assert shape:
```python
"""TEST-HARNESS-01 sanity: HTMLSnapshotExtension exists + correct class config."""

from __future__ import annotations

from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

# Adjust import path per Claude's Discretion (conftest vs _snapshot_extension.py):
from tests._snapshot_extension import HTMLSnapshotExtension  # or from tests.conftest


def test_extension_subclasses_single_file() -> None:
    assert issubclass(HTMLSnapshotExtension, SingleFileSnapshotExtension)


def test_extension_file_extension_is_html() -> None:
    assert HTMLSnapshotExtension._file_extension == "html"


def test_extension_write_mode_is_text() -> None:
    assert HTMLSnapshotExtension._write_mode == WriteMode.TEXT
```

---

### `tests/test_live_fixtures_pii_canary.py` (unit test / canary, drift-detect)

**Analog:** `tests/runner/test_parser_drift_gate.py:21-79` (pure-function gate-tests shape: per-case `def test_X_threshold_case`).

**Pattern from analog** (test_parser_drift_gate.py:36-49):
```python
def test_volume_exceeds_threshold_fails() -> None:
    r = parser_drift_null_rate_gate(volume_null_rate=0.6, brand_null_rate=0.0)
    assert not r.passed
    assert r.failure_reason == "parser_drift_null_volume_rate"
```

**For PII canary tests**, mirror per-case shape (per VALIDATION.md TH-02a + TH-02b):
```python
"""TH-02 PII canary + 50 MB size budget.

Collected by default `pytest` invocation (NOT gated on -m live). D-907.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from tests.conftest import _assert_fixture_clean  # or wherever helper lives


def test_dirty_fixture_fails(tmp_path: Path) -> None:
    """Fixture containing cf_clearance= cookie → pytest.fail with pattern, NOT content."""
    dirty = tmp_path / "_live-dirty.html"
    dirty.write_text("<html>cf_clearance=secret_value_should_not_leak</html>")
    with pytest.raises(Exception) as exc:
        _assert_fixture_clean(dirty)
    assert "cf_clearance" in str(exc.value)
    assert "secret_value_should_not_leak" not in str(exc.value)  # T-09-PII: no content leak


def test_oversize_rejected(tmp_path: Path) -> None:
    """50 MB per-file budget."""
    huge = tmp_path / "_live-huge.html"
    huge.write_bytes(b"x" * (51 * 1024 * 1024))   # 51 MB
    with pytest.raises(Exception) as exc:
        _assert_fixture_clean(huge)
    assert "51" in str(exc.value) or "byte" in str(exc.value).lower()


def test_clean_phase8_fixture_passes() -> None:
    """Phase 8 _live-2026-05-13-*.html fixtures are PII-clean (RESEARCH A6 verification)."""
    for path in [
        Path("tests/fixtures/goldapple/_live-2026-05-13-stereotype.html"),
        Path("tests/fixtures/goldapple/_live-2026-05-13-armani-code.html"),
        Path("tests/fixtures/viled/_live-2026-05-13-contre-jour.html"),
    ]:
        _assert_fixture_clean(path)  # must not raise
```

**Regex patterns:** verbatim from `09-RESEARCH.md §6.1` `_PII_PATTERNS` tuple (cf_clearance, bot token shape, Authorization Bearer, UUID v4, hc-ping path).

---

### `tests/test_fixture_metadata.py` (unit test, fixture-load)

**Analog:** `tests/unit/test_goldapple_microdata_parser.py` round-trip pattern (assert object-roundtrip via construct → serialize → reconstruct).

**Pattern shape:**
```python
"""TH-02c sidecar JSON round-trip."""

from __future__ import annotations
from pathlib import Path
from tests._fixture_metadata import FixtureMetadata, write_sidecar, read_sidecar


def test_sidecar_round_trip(tmp_path: Path) -> None:
    fixture_path = tmp_path / "_live-test.html"
    fixture_path.write_text("<html/>", encoding="utf-8")
    meta = FixtureMetadata(
        date="2026-05-14T12:00:00+00:00",
        url="https://goldapple.kz/test",
        status=200,
        html_size=8,
        title="Test",
        camoufox_version="0.4.11",
    )
    sidecar_path = write_sidecar(fixture_path, meta)
    assert sidecar_path.exists()
    loaded = read_sidecar(fixture_path)
    assert loaded == meta
```

**`FixtureMetadata` + `write_sidecar` + `read_sidecar`:** verbatim from `09-RESEARCH.md §6.2`.

---

### `tests/test_snapshot_soundness.py` (unit test, drift-detect)

**Analog:** `tests/runner/test_parser_drift_gate.py:36-65` (negative-path: fail-when-condition).

**Pattern shape** (TH-03c — missing-snapshot fails CI loudly):
```python
"""TH-03c missing-snapshot soundness negative test.

D-906: syrupy DEFAULT behavior is to FAIL on missing snapshot (no --strict needed).
This test confirms the regression DOES NOT silently pass.
"""

from __future__ import annotations
import pytest


@pytest.mark.live
def test_missing_snapshot_raises(refresh_live: bool, html_snapshot, tmp_path) -> None:
    """If a snapshot file is absent and we don't pass --snapshot-update, syrupy fails."""
    if refresh_live:
        pytest.skip("This soundness test runs only in cassette-replay mode.")
    # Simulate missing snapshot via syrupy AbsentSnapshotException equivalent.
    # (Exact API form TBD per planner; pseudo-code below.)
    with pytest.raises(AssertionError):
        assert "<html/>" == html_snapshot  # missing → AssertionError
```

---

### `tests/storage/test_schemas.py` (unit test, writer-validate)

**Analog:** `tests/runner/test_parser_drift_gate.py:21-79` (pure-function boundary tests) + `tests/unit/test_goldapple_microdata_parser.py:50-72` (per-attribute assertion).

**Pattern shape** (TH-06a + TH-06b):
```python
"""TH-06a + TH-06b — per-retailer Pydantic schema D-904."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ga_crawler.storage.schemas import GoldappleRawProduct, ViledRawProduct


_VALID_PAYLOAD = {
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


def test_both_reject_empty_brand() -> None:
    for cls in (GoldappleRawProduct, ViledRawProduct):
        bad = dict(_VALID_PAYLOAD)
        bad["brand"] = ""
        with pytest.raises(ValidationError):
            cls.model_validate(bad)
```

---

### `tests/integration/test_writer_schema_gate.py` (integration test, writer-validate)

**Analog (EXACT):** `tests/integration/test_storage_integration.py:39-95` — `SqliteSnapshotWriter` integration tests.

**Pattern from analog** (test_storage_integration.py:39-79):
```python
def _setup(tmp_path: Path):
    db = tmp_path / "test.db"
    init_db(db)
    engine = make_engine(db)
    return engine


def _row(sku_id: str, name: str = "X", price: int = 1000) -> dict:
    return {
        "sku_id": sku_id,
        "url": f"https://example.com/{sku_id}",
        "name": name,
        "brand": "TestBrand",
        "brand_norm": "testbrand",
        "name_norm": name.lower(),
        "current_price": price,
        "currency": "KZT",
        "stock_state": "IN_STOCK",
    }


def test_snapshot_writer_appends_rows(tmp_path: Path) -> None:
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    products = [_row("100", "A", 1000), _row("200", "B", 2000)]
    n = writer.append(run_id=rid, retailer="goldapple", products=products)
    assert n == 2
    with Session(engine) as s:
        from sqlmodel import select
        rows = list(s.exec(select(Snapshot)))
    assert len(rows) == 2
```

**For schema-gate integration** (TH-06c), extend `_row` with `volume_raw` field and add cases:
```python
def test_append_skips_invalid_goldapple_rows_and_increments_rejected_count(tmp_path: Path) -> None:
    """D-903: invalid row (empty volume_raw) skipped; rejected_reasons captures it."""
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    products = [
        _row_with_volume("100", "Valid", "75 мл"),     # accepted
        _row_with_volume("200", "Empty",   ""),         # rejected (volume_raw="")
        _row_with_volume("300", "Missing", None),       # rejected (volume_raw=None)
    ]
    n = writer.append(run_id=rid, retailer="goldapple", products=products)
    assert n == 1  # only 1 row INSERTED
    assert len(writer._last_rejected_reasons) == 2
    assert {r["sku_id"] for r in writer._last_rejected_reasons} == {"200", "300"}
    # Verify DB has 1 row
    with Session(engine) as s:
        from sqlmodel import select
        rows = list(s.exec(select(Snapshot)))
    assert len(rows) == 1
    assert rows[0].sku_id == "100"


def test_append_accepts_viled_null_volume(tmp_path: Path) -> None:
    """D-904: viled-relaxed schema lets None pass."""
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    products = [_row_with_volume("v-contre-jour", "Contre-Jour", None)]
    n = writer.append(run_id=rid, retailer="viled", products=products)
    assert n == 1
    assert writer._last_rejected_reasons == []


def test_append_no_pii_in_rejected_reasons(tmp_path: Path) -> None:
    """LANDMINE §7.2: rejected_reasons must NOT include `'input'` (Pydantic-default)."""
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    bad = _row_with_volume("sensitive", "name-with-token-abc123", "")
    writer.append(run_id=rid, retailer="goldapple", products=[bad])
    for reason in writer._last_rejected_reasons:
        for err in reason["errors"]:
            assert "input" not in err
            assert set(err.keys()) == {"loc", "type"}
```

---

### `tests/runner/test_schema_rejected_gate.py` (unit test, gate-decision)

**Analog (EXACT):** `tests/runner/test_parser_drift_gate.py:21-79` — same shape, same threshold-sweep cases.

**Pattern verbatim** (test_parser_drift_gate.py:21-79) — only swap function name + field semantics:

```python
"""TH-06d — schema_rejected_rate_gate threshold semantics.

Mirrors tests/runner/test_parser_drift_gate.py shape (Phase 8 D-815 helper).
"""

from __future__ import annotations
import pytest
from ga_crawler.runner.gates import (
    SchemaRejectedGateResult,
    schema_rejected_rate_gate,
)


def test_below_threshold_passes() -> None:
    r = schema_rejected_rate_gate(rejected_count=4, total_attempted=100)
    assert r.passed
    assert r.failure_reason is None
    assert r.rejected_rate == 0.04


def test_exactly_at_threshold_passes() -> None:
    """STRICT > 0.05 — exactly 5% PASSES (mirror parser_drift_null_rate_gate semantics)."""
    r = schema_rejected_rate_gate(rejected_count=5, total_attempted=100)
    assert r.passed
    assert r.failure_reason is None


def test_above_threshold_fails() -> None:
    r = schema_rejected_rate_gate(rejected_count=6, total_attempted=100)
    assert not r.passed
    assert r.failure_reason == "schema_validation_rejected_rate"
    assert r.rejected_rate == 0.06


def test_zero_total_attempted_passes() -> None:
    """Empty-input safety: rate undefined → pass."""
    r = schema_rejected_rate_gate(rejected_count=0, total_attempted=0)
    assert r.passed
    assert r.rejected_rate == 0.0


def test_custom_threshold() -> None:
    r = schema_rejected_rate_gate(rejected_count=3, total_attempted=10, threshold=0.2)
    assert not r.passed
    assert r.failure_reason == "schema_validation_rejected_rate"


def test_result_is_frozen_dataclass() -> None:
    r = schema_rejected_rate_gate(0, 100)
    assert isinstance(r, SchemaRejectedGateResult)
    with pytest.raises(Exception):
        r.passed = False  # type: ignore[misc]  # frozen
```

---

### `tests/live/test_parser_drift.py` (live test, parser-eval)

**Analog:** `tests/unit/test_goldapple_microdata_parser.py:20-60` (parse-and-assert pattern) + `09-RESEARCH.md §5.2` (verbatim `refresh_live` branch).

**Pattern combining both** (RESEARCH §5.2 verbatim + parser-test invariants):

```python
"""TH-03 live parser-drift harness. Two modes:
  - default `pytest -m live`: cassette-replay (loads _live-2026-05-13-*.html, parses, asserts)
  - `pytest -m live --refresh-live`: re-fetch via Camoufox/curl_cffi, syrupy-diff vs cassette

D-906 + D-905 (operator-only opt-in; NO cron wiring).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ga_crawler.parsers.goldapple_microdata import parse_pdp as parse_goldapple
from ga_crawler.parsers.viled_nextdata import parse_pdp as parse_viled

pytestmark = pytest.mark.live  # apply to ALL tests in this module (RESEARCH §5.1)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---- Goldapple STEREOTYPE drift test (Bug #1+#2 retroactive lock) ----

@pytest.mark.asyncio
async def test_goldapple_stereotype_drift(refresh_live: bool, html_snapshot) -> None:
    url = "https://goldapple.kz/19000440474-stereotype-sago"
    fixture_path = FIXTURES_DIR / "goldapple" / "_live-2026-05-13-stereotype.html"
    if refresh_live:
        from ga_crawler.fetchers.goldapple import GoldappleFetcher
        from tests._html_normalize import normalize_for_snapshot
        async with GoldappleFetcher(run_id=-1, headless=True) as fetcher:
            rec = await fetcher.fetch_one(fetcher._page, url)
        normalized = normalize_for_snapshot(rec["html"])
        assert normalized == html_snapshot  # syrupy diff (T-09-DRIFT mitigation)
    html = fixture_path.read_text("utf-8")
    product = parse_goldapple(html, url)
    assert product is not None, "STEREOTYPE PDP must parse non-None"
    assert product.brand_raw, "brand must be non-empty"
    assert product.name, "name must be non-empty"
    assert product.raw_volume_text, "volume_raw must be non-empty (goldapple-strict)"
    assert product.brand_raw.lower() not in product.name.lower(), \
        "Bug #2: brand string must NOT be a substring of name (Armani-style regression)"
    assert product.current_price > 0


# ---- Goldapple Armani drift test (Bug #2 retroactive lock) ----

@pytest.mark.asyncio
async def test_goldapple_armani_code_drift(refresh_live, html_snapshot) -> None:
    ...  # mirror stereotype; url = "https://goldapple.kz/19000195723-armani-code"


# ---- Viled Contre-Jour drift test (Bug #3 legitimate-None volume) ----

@pytest.mark.asyncio
async def test_viled_contre_jour_drift(refresh_live, html_snapshot) -> None:
    url = "https://viled.kz/item/408872"
    fixture_path = FIXTURES_DIR / "viled" / "_live-2026-05-13-contre-jour.html"
    if refresh_live:
        from ga_crawler.fetchers.viled import ViledFetcher
        from tests._html_normalize import normalize_for_snapshot
        rec = ViledFetcher().fetch_one(url)
        normalized = normalize_for_snapshot(rec["html"])
        assert normalized == html_snapshot
    html = fixture_path.read_text("utf-8")
    product = parse_viled(html, url)
    assert product is not None
    assert product.brand_raw
    assert product.name
    # NB: volume_raw legitimately None for Contre-Jour (D-904 viled-relaxed)
    assert product.current_price > 0
```

**Key cross-references:**
- `pytestmark = pytest.mark.live` at module top — RESEARCH §5.1.
- `refresh_live` fixture comes from conftest (RESEARCH §5.2).
- `html_snapshot` fixture comes from conftest (RESEARCH §3.1).
- `normalize_for_snapshot` lives in `tests/_html_normalize.py` (RESEARCH §7.1 landmine mitigation).
- Fetcher reuse: `GoldappleFetcher` (`src/ga_crawler/fetchers/goldapple.py`) + `ViledFetcher` (`src/ga_crawler/fetchers/viled.py`) — verbatim, no new fetcher code.

---

### `tests/_html_normalize.py` (helper, drift-detect)

**Greenfield** — no in-repo analog. Pattern spec verbatim from `09-RESEARCH.md §7.1`:

```python
"""HTML normalization for syrupy snapshot diff (T-09-DRIFT mitigation).

Camoufox HTML capture is non-deterministic on goldapple PDP:
  - <meta name="csrf-token" content="..."> rotates per request
  - cf_clearance cookie echoes in inline <script> JSON payloads
  - CSS-class build-hash suffix (_ga-pdp-title__heading_<HASH>) rotates on deploys
  - __NEXT_DATA__ buildId field

Without normalization, every --refresh-live run produces false-positive drift.
"""

from __future__ import annotations
import re

_CSRF_TOKEN_RE = re.compile(r'(<meta name="csrf-token" content=")[^"]*(")')
_CF_CLEARANCE_RE = re.compile(r'cf_clearance=[^;"]*')
_BUILD_HASH_RE = re.compile(r'(_ga-pdp-(?:title__heading|brand|name)_)[a-z0-9_]+')
_BUILD_ID_RE = re.compile(r'("buildId":")[^"]*(")')


def normalize_for_snapshot(html: str) -> str:
    """Strip rotating tokens. Idempotent: normalize(normalize(x)) == normalize(x)."""
    html = _CSRF_TOKEN_RE.sub(r'\1NORM\2', html)
    html = _CF_CLEARANCE_RE.sub('cf_clearance=NORM', html)
    html = _BUILD_HASH_RE.sub(r'\1NORM', html)
    html = _BUILD_ID_RE.sub(r'\1NORM\2', html)
    return html
```

**Test idempotence** — add to `tests/test_snapshot_extension.py` or stand-alone `tests/test_html_normalize.py`:
```python
def test_normalize_is_idempotent() -> None:
    sample = "...captured html..."
    assert normalize_for_snapshot(normalize_for_snapshot(sample)) == normalize_for_snapshot(sample)
```

---

### `tests/_snapshot_extension.py` (helper, fixture-load)

**Greenfield** — verbatim spec from `09-RESEARCH.md §3.1`:

```python
"""HTMLSnapshotExtension — Phase 9 TEST-HARNESS-01.

Single-file syrupy extension for .html snapshots in TEXT mode.
Per RESEARCH §3.1: 7 LOC, no inline tests needed beyond test_snapshot_extension.py.
"""

from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode


class HTMLSnapshotExtension(SingleFileSnapshotExtension):
    """One .html file per snapshot, text mode (not binary)."""
    _file_extension = "html"
    _write_mode = WriteMode.TEXT
```

**Claude's Discretion (CONTEXT.md):** If this is the ONLY content of the file, planner may inline into `tests/conftest.py` (≤7 LOC). If multiple syrupy extensions emerge, keep as standalone.

---

### `tests/_fixture_metadata.py` (helper, fixture-load)

**Greenfield** — verbatim spec from `09-RESEARCH.md §6.2` (FixtureMetadata dataclass + write/read sidecar helpers). See §6.2 of RESEARCH for paste-ready code.

---

### `tests/test_brand_coverage_canary.py` (P2 conditional integration test)

**Conditional on P2 GO** (D-902, 8h time-budget gate). Greenfield. Verbatim spec from `09-RESEARCH.md §6.5`.

**DB-inspection analog:** `tests/integration/test_v_current_snapshots.py` (likely; read brand list from `v_current_snapshots` view). Planner confirms file existence at task-write time.

---

### `tests/integration/test_capture_fixtures_cli.py` (P2 conditional integration test)

**Conditional on P2 GO** (D-902). Analog: existing CLI subcommand integration tests (e.g., `tests/integration/test_cli_report_subcommand.py`, `test_cli_matcher_subcommand.py`).

**CLI dispatch pattern to extend** (`src/ga_crawler/cli.py:1-80` shape):
- Add `_cmd_capture_fixtures(args)` handler.
- Register subcommand `capture-fixtures` in argparse setup.
- Per RESEARCH §6.6: handler reuses `GoldappleFetcher` / `ViledFetcher` verbatim; calls `_scrub_html(content)` (D-907 belt-and-suspenders); writes fixture + sidecar JSON via `write_sidecar(...)`.

---

### `README.md` MODIFICATION (docs, RU-primary operator runbook)

**Analog:** `README.md` Operations runbook section (L153-198) — RU-primary tone, code-block-driven runbook.

**Existing tone example** (README.md:157-164):
```markdown
### `undelivered_telegram_unreachable` после weekly run

Telegram API был временно недоступен; xlsx остался на диске (`reports/YYYY-WNN.xlsx`; Phase 6 D-605 invariant — НИКОГДА не удаляем pending xlsx). Повторная доставка:

\`\`\`bash
sudo -u ga_crawler /opt/ga_crawler/.venv/bin/python -m ga_crawler deliver-run --run-id N
\`\`\`
```

**New `## Live HTML harness` section** (append between `## Логи` L199-236 and `## Dev setup` L238). Follows same RU-primary + code-block-driven pattern:

```markdown
## Live HTML harness

Phase 9 harness фиксирует parser-fix Phase 8 ретроактивно: ловит fixture-vs-live drift в parser shape таких mode'ах как run #13 (Givenchy frozen fixture green, STEREOTYPE/Armani/Contre-Jour shapes 88/88 NULL volume в проде). D-905: **operator-only opt-in, НЕ в cron.**

### Когда запускать

- **Pre-deploy** (после parser changes): убедиться что текущие 3 Phase 8 fixtures parse без regression.
- **Post-suspected-drift**: если weekly run #N показал низкий match-rate / NULL-rate spike — refresh live cassettes и сравнить с frozen.
- **По запросу operator**: при routine quarterly check goldapple/viled HTML shape.

### Cassette-replay (быстро, no network)

\`\`\`bash
uv run pytest -m live -x
\`\`\`

Парсит 3 frozen `_live-2026-05-13-*.html` fixtures, assert'ит brand / name / volume_raw invariants. ~10s wallclock.

### Refresh (operator-only, hits Camoufox + curl_cffi)

\`\`\`bash
uv run pytest -m live --refresh-live -x
\`\`\`

Re-fetches SMOKE_URLs через Camoufox 0.4.11 (goldapple) и curl_cffi (viled). Syrupy diff vs frozen fixture. ~30+s wallclock.

Если drift detected → syrupy fails + пишет `.planning/research/parser-drift-YYYY-MM-DD.md` с per-assertion verdict.

### Принять drift (overwrite fixture)

\`\`\`bash
uv run pytest -m live --refresh-live --snapshot-update -x
\`\`\`

Перезаписывает `tests/fixtures/<retailer>/_live-YYYY-MM-DD-<slug>.html` + регенерирует sidecar JSON.

### Stale-fixture warning (30 days)

Если sidecar `date` > 30 дней, pytest emits UserWarning (НЕ fail). Считается напоминанием — operator решает refresh'ить или нет.
```

**Cross-reference for tone consistency:**
- Existing section headers use `### <descriptive subhead>` and code blocks for runbook commands (L165-198).
- RU-primary text + English code/identifiers — same convention as `## VPS setup` (L10) and `## ENV vars` (L60).
- Cross-link to drift-md location (`.planning/research/parser-drift-YYYY-MM-DD.md`) per ARCH §B.

---

## Shared Patterns

### Authentication / Authorization

**N/A** for Phase 9 — all new files are test infrastructure or schema validation. No auth surface added.

### Error Handling

**Pattern source:** `src/ga_crawler/storage/sqlite.py:196-198` (writer try/except/rollback) + `tests/runner/test_parser_drift_gate.py` (gate failure_reason sentinel pattern).

**Apply to:**
- `SqliteSnapshotWriter.append` Pydantic wire-in: per-row try/except `ValidationError` → accumulate to `rejected_reasons`, `continue`. Do NOT bubble — that would lose the whole batch.
- `schema_rejected_rate_gate` failure: sentinel reason `"schema_validation_rejected_rate"` (string), NOT exception (mirror `parser_drift_null_rate_gate` D-815 pattern at `gates.py:332-336`).
- `_assert_fixture_clean(path)` — uses `pytest.fail(...)` (not raise) so canary failure halts collection cleanly without traceback noise (D-907).

### Validation

**Source:** `src/ga_crawler/storage/schemas.py` (new — D-904 per-retailer split).
**Apply to:** `SqliteSnapshotWriter.append` write-boundary at `storage/sqlite.py:186-192`.

**Pattern:**
```python
from ga_crawler.storage.schemas import GoldappleRawProduct, ViledRawProduct
from pydantic import ValidationError

_SCHEMA_BY_RETAILER = {
    "goldapple": GoldappleRawProduct,
    "viled": ViledRawProduct,
}

# Inside append() loop, after payload built:
schema_cls = _SCHEMA_BY_RETAILER.get(retailer)
if schema_cls is not None:
    try:
        schema_cls.model_validate(payload)
    except ValidationError as e:
        rejected_reasons.append({
            "sku_id": product.get("sku_id", "<unknown>"),
            "errors": [{"loc": list(err["loc"]), "type": err["type"]}
                       for err in e.errors()],  # NO 'input' key (RESEARCH §7.2)
        })
        continue
```

### Atomic stats merge (Pitfall 6)

**Source:** `src/ga_crawler/storage/sqlite.py:232-251` (`SqliteRunWriter.patch_stats` RFC-7396 json_patch).
**Apply to:** All `schema.*` keys — single `patch_stats(run_id, {...})` call from orchestrator after `append` returns. NO per-row patch_stats (Pitfall 6 contention).

**Pattern (RESEARCH §9 Q3 — inline, no builder):**
```python
total_attempted = len(products)
n_inserted = writer.append(run_id, retailer, products)
rejected = writer._last_rejected_reasons
run_writer.patch_stats(run_id, {
    "schema.rejected_count": len(rejected),
    "schema.rejected_rate": len(rejected) / total_attempted if total_attempted else 0.0,
    "schema.rejected_reasons": rejected,  # already truncated [:50] inside writer
})
gate_result = schema_rejected_rate_gate(len(rejected), total_attempted)
if not gate_result.passed:
    run_writer.fail(run_id, gate_result.failure_reason)
```

### Frozen-dataclass gate result

**Source:** `src/ga_crawler/runner/gates.py:288-306` (`ParserDriftGateResult`).
**Apply to:** New `SchemaRejectedGateResult` (verbatim shape, swap fields).

### TDD discipline (D-811 from Phase 8)

**Pattern:** Every test file is written FIRST and committed RED before production code. Per-task atomic commit pairs (RED commit → GREEN commit).
**Apply to:** All Wave 0 test stubs. Source of pattern: `08-CONTEXT.md` D-811 + Phase 8 SUMMARY commits.

### Append-only retailer-grouped fixtures

**Source:** `tests/fixtures/goldapple/_live-2026-05-13-*.html`, `tests/fixtures/viled/_live-2026-05-13-*.html` (Phase 8 W0).
**Apply to:** Snapshot fixture path convention — `tests/fixtures/<retailer>/_live-YYYY-MM-DD-<slug>.html` per ARCH §B + Phase 8 D-811. Sidecar JSON: `<fixture>.json` (same dir, swap suffix). NOT in `tests/fixtures/live/`.

---

## No Analog Found (Greenfield Files)

These files have no in-repo analog. Planner uses RESEARCH skeletons verbatim (cite §s already provided above).

| File | Role | Reason | RESEARCH cite |
|------|------|--------|---------------|
| `tests/_snapshot_extension.py` (or inline) | syrupy custom extension | First syrupy use in project | §3.1 (Context7 verbatim, 7 LOC) |
| `tests/_fixture_metadata.py` | sidecar JSON helper | First sidecar-JSON pattern | §6.2 (verbatim) |
| `tests/_html_normalize.py` | HTML normalization for syrupy diff | First snapshot-diff use case; specific to Camoufox non-determinism | §7.1 landmine spec |
| `tests/test_brand_coverage_canary.py` (P2 cond.) | brand-coverage quota canary | First DB-snapshot-driven test-coverage check | §6.5 (verbatim) |

---

## Modification Sites (precise line ranges)

For planner's direct reference in plan task `<action>` fields:

| File | Lines | What | Source |
|------|-------|------|--------|
| `tests/conftest.py` | L95-104 | Wrap `goldapple_pdp_html_live_stereotype` loader with `_assert_fixture_clean(path)` | D-907 fixture-loader integration |
| `tests/conftest.py` | L107-115 | Wrap `goldapple_pdp_html_live_armani` loader | D-907 |
| `tests/conftest.py` | L217-226 | Wrap `viled_pdp_html_live_contre_jour` loader | D-907 |
| `tests/conftest.py` | append after L298 | Add `_assert_fixture_clean`, `_PII_PATTERNS`, `pytest_addoption("--refresh-live")`, `refresh_live` fixture, `html_snapshot` fixture | RESEARCH §3.1, §5.2, §6.1 |
| `src/ga_crawler/storage/sqlite.py` | L186-192 (loop body) | Wire `schema_cls.model_validate(payload)` per-row try/except `ValidationError`; accumulate `rejected_reasons[:50]` to `self._last_rejected_reasons`; `continue` on raise | D-903 + RESEARCH §4.2 |
| `src/ga_crawler/storage/sqlite.py` | new imports + L173 (init) | `from ga_crawler.storage.schemas import GoldappleRawProduct, ViledRawProduct`; `from pydantic import ValidationError`; `_SCHEMA_BY_RETAILER = {...}`; init `self._last_rejected_reasons = []` in `__init__` | D-903 |
| `src/ga_crawler/runner/gates.py` | append after L342 (before `__all__`) | New `SchemaRejectedGateResult` frozen-dataclass + `schema_rejected_rate_gate` function | D-903 + RESEARCH §6.3 |
| `src/ga_crawler/runner/gates.py` | L382-394 `__all__` | Append `"schema_rejected_rate_gate"`, `"SchemaRejectedGateResult"` | — |
| `src/ga_crawler/runner/stats.py` | append after L159 | `SCHEMA_STATS_KEYS` tuple (3 keys) | RESEARCH §6.4 + §9 Q3 |
| `src/ga_crawler/runner/stats.py` | L219-226 `__all__` | Append `"SCHEMA_STATS_KEYS"` | — |
| `pyproject.toml` | L33 | Insert `"syrupy>=4.7,<5.0",` line (alphabetical placement: after `respx>=0.21`) | TEST-HARNESS-01 + RESEARCH §1 |
| `README.md` | between L236 and L238 | Insert new `## Live HTML harness` section | TEST-HARNESS-03 + D-905 docs cascade |

---

## Metadata

**Analog search scope:**
- `src/ga_crawler/storage/` (sqlite.py read in full)
- `src/ga_crawler/runner/` (gates.py + stats.py read in full)
- `src/ga_crawler/parsers/` (dispatcher.py + goldapple_microdata.py + viled_nextdata.py heads read)
- `tests/conftest.py` (read in full)
- `tests/runner/test_parser_drift_gate.py` (read in full — exact analog for new gate test)
- `tests/integration/test_storage_integration.py` (head read — exact analog for writer integration)
- `tests/unit/test_goldapple_microdata_parser.py` (head read — analog for parser unit test shape)
- `README.md` (full structure + ops-runbook section read)
- `pyproject.toml` (read in full)
- `src/ga_crawler/cli.py` + `src/ga_crawler/__main__.py` (heads read — CLI dispatch pattern for P2 TH-05)

**Files scanned:** ~12 source files read; ~25 candidate test files Globbed.

**Pattern extraction date:** 2026-05-14

**Cross-references for planner:**
- `09-CONTEXT.md` D-901..D-907 (lines 33-67) — locked decisions
- `09-RESEARCH.md` §3 (syrupy), §4 (Pydantic), §5 (pytest marker/flag), §6 (paste-ready skeletons), §7 (landmines), §8 (validation map), §9 (open Qs for planner)
- `09-VALIDATION.md` Wave 0 Requirements (lines 62-80) — authoritative test-file inventory
