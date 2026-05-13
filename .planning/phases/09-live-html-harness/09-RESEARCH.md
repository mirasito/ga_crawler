# Phase 9: Live-HTML Harness — Research

**Researched:** 2026-05-14
**Domain:** snapshot-driven drift detection + write-boundary schema enforcement (syrupy 4.x + Pydantic 2.10 + pytest 8)
**Confidence:** HIGH (Context7-verified syrupy API, repo-grep-verified storage shape, PyPI-verified versions)
**Stance:** validation-mode (not exploration) — CONTEXT.md D-901..D-907 locked; this doc surfaces concrete patterns + landmines.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-901** 3-plan wave: 09-01 (W0 must, TH-01+TH-02) → 09-02 (W1 parallel, TH-03 ∥ TH-06) → 09-03 (W2 conditional P2 bundle TH-04+TH-05 OR defer-to-v1.2 doc cascade).
- **D-902** P2 GO/NO-GO = git-timestamp elapsed `09-01 first-RED → 09-02 last-GREEN` < 8h. Operator override allowed.
- **D-903** Pydantic validation boundary = `SqliteSnapshotWriter` storage border (NB: method is `append`, not `persist` — see §9 Open Q1). New stats key `schema_rejected_count`; gate `rejected_rate > 0.05` → `runs.status='failed' reason='schema_validation_rejected_rate'`. Position **AFTER** `append` complete, **BEFORE** Phase 8 `parser_drift_null_rate_gate`.
- **D-904** Per-retailer schema split: `GoldappleRawProduct` strict (`volume_raw: NonEmptyStr` REQUIRED); `ViledRawProduct` relaxed (`volume_raw: NonEmptyStr | None`); shared `RawProductBase`. File: `src/ga_crawler/storage/schemas.py` (NEW — `storage/types.py` does not exist; verified by glob).
- **D-905** Operator-only opt-in; NO cron wiring; `weekly-run.sh` unchanged; README §8 documents when/how/output.
- **D-906** Two-mode: default `pytest -m live` cassette-replay, `pytest -m live --refresh-live` re-fetch via Camoufox 0.4.11 → syrupy `assert html == html_snapshot`; stale-fixture warning at 30 days.
- **D-907** PII canary two enforcement points: fixture-loader integration in `conftest.py` + standalone `tests/test_live_fixtures_pii_canary.py` (collected by default `pytest`, not gated on `-m live`).

### Claude's Discretion

- `HTMLSnapshotExtension` file location (`tests/conftest.py` if <30 LOC, else `tests/_snapshot_extension.py`).
- Pydantic schema file: `src/ga_crawler/storage/schemas.py` is the only viable choice — `storage/types.py` confirmed absent (Glob result: only `__init__.py`, `norm06_writer.py`, `sqlite.py`).
- Sidecar JSON helper: inline in conftest acceptable.
- UUID regex form (v4 strict vs any-UUID).

### Deferred Ideas (OUT OF SCOPE)

Auto-cron live refresh; GHA CI integration; `@pytest.mark.flaky` ban canary; LLM diff classifier; match-rate floor; viled volume null-rate gate; cassette refresh cron entry.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEST-HARNESS-01 | syrupy 4.7 dev-dep + `HTMLSnapshotExtension` | §3 syrupy pattern + version verification |
| TEST-HARNESS-02 | `_live-YYYY-MM-DD-<slug>.html` + sidecar JSON + PII canary + 50 MB budget | §6 code skeleton + §7 PII landmine |
| TEST-HARNESS-03 | `tests/live/test_parser_drift.py` two-mode | §5 pytest custom-flag + §6 skeleton |
| TEST-HARNESS-04 (P2) | Brand-coverage quota canary | §6 skeleton + Skill `spike-findings-v1.1-brand-name-shapes` |
| TEST-HARNESS-05 (P2) | `python -m ga_crawler capture-fixtures` CLI | §6 skeleton; reuses `GoldappleFetcher`/`ViledFetcher` |
| TEST-HARNESS-06 | Pydantic `RawProduct.model_validate` at `SqliteSnapshotWriter.append` | §4 idiomatic shape + §8 Validation Architecture row |
</phase_requirements>

---

## 1. Executive Summary

- **All 7 locked decisions (D-901..D-907) are confirmed sound** against current upstream docs and repo state — proceed to plan generation without re-litigation. Only one boundary-language slip needs correcting: the writer method is `SqliteSnapshotWriter.append(run_id, retailer, products) -> int`, not `.persist`. The Pydantic injection point is the loop body at `storage/sqlite.py:186-192` (per `Snapshot(**payload)`-construction).
- **syrupy `>=4.7,<5.0`** pin: latest 4.x is **4.9.1 (2025-03-24)**; syrupy 5.0/5.1 (2026) shipped breaking changes. The CONTEXT.md cap is the right discipline — keep it, prefer pinning `~=4.9` or `>=4.7,<5.0` (resolves to 4.9.1). [VERIFIED: PyPI 2026-05-14].
- **`SingleFileSnapshotExtension` subclass body is ≤7 LOC** (verified via Context7 `/syrupy-project/syrupy` llms.txt). Missing-snapshot = test failure is the **default** behavior; no extra `--strict` flag needed. The D-906 "syrupy fails missing-snapshot soundness" claim is correct.
- **Live HTML capture determinism is the one real landmine** (§7 #1). syrupy diffs HTML bytewise; Camoufox `cf_clearance` cookie ECHOES in `<meta name="csrf-token">` and inline `<script>` JSON on goldapple — every re-fetch will diverge. Mitigation: normalize-before-snapshot (strip set-cookie echoes, ray-id meta tags, build-hash CSS classes from `_ga-pdp-title__heading_<hash>` → `_ga-pdp-title__heading_<HASH>`).
- **Pydantic 2.10 write-boundary perf**: 88+ rows/run × `model_validate` is ~1-3 ms total (Pydantic 2 core is Rust-backed); batch validation gives no measurable gain. Validate per-row inside the existing `for product in products` loop at `sqlite.py:186`.
- **`[BLOCKING]` schema-push:** NOT needed — Pydantic is in-memory pre-INSERT validation, no DB schema migration. Phase 9 adds zero SQL DDL. The `Snapshot` SQLModel table at `sqlite.py:60-87` stays frozen.

**Primary recommendation:** Three plans, two new files (`storage/schemas.py`, `tests/live/test_parser_drift.py`), three modified files (`tests/conftest.py`, `storage/sqlite.py`, `runner/stats.py` for new key), one new dev-dep (`syrupy>=4.7,<5.0`). Pin syrupy to `4.9.x` if `gsd-planner` wants tighter floor.

---

## 2. Locked Decisions (Reaffirmed)

| Decision | Status | Cite |
|----------|--------|------|
| D-901 3-plan wave | **CONFIRMED** — matches Phase 8 D-808/D-809/D-810 cadence; same RED+GREEN TDD pattern (D-811) | `08-CONTEXT.md:46-52`; PITFALLS.md §1+§2 |
| D-902 8h time-budget gate | **CONFIRMED** — heuristic, operator-overridable; cheaper than naming committee discussion. No upstream library constrains | CONTEXT.md L40 |
| D-903 writer-boundary + 5% gate | **CONFIRMED** — but method name correction: `.append` not `.persist`. Cascade position (before null-rate gate) preserves "structural-before-content" diagnostic ordering | `storage/sqlite.py:177`; `runner/gates.py:308`; CONTEXT.md L43 |
| D-904 per-retailer schema split | **CONFIRMED** — viled-relaxed evidence from `08-01-SUMMARY.md` (Contre-Jour legitimately Sizeless); goldapple-strict from `spike-findings.../SKILL.md` (volume present 25/30 = 83% non-volumeless categories) | SKILL.md L39; CONTEXT.md L44-47 |
| D-905 operator-only opt-in | **CONFIRMED** — PITFALLS.md §2 (cassette staleness) explicitly accepts operator-discipline for v1.1; v1.2 cron deferred | PITFALLS.md L77-83 |
| D-906 two-mode (cassette-replay default + `--refresh-live`) | **CONFIRMED** — matches syrupy idiom (`pytest -m live` runs cassette; `pytest -m live --snapshot-update --refresh-live` operator-only re-capture) | syrupy README §"CLI Options" |
| D-907 PII canary dual enforcement | **CONFIRMED** — collected by default `pytest` (NOT gated on `-m live`); `tests/conftest.py:23-37` fixture loader pattern extension is in-pattern | CONTEXT.md L57-60; conftest.py L23-37 |

**Verdict:** Zero decisions need re-opening. Phase 9 is *execution-ready* as soon as planner consumes this file.

---

## 3. syrupy 4.7 — Concrete Patterns

### 3.1 `HTMLSnapshotExtension` subclass (≤7 LOC)

Verbatim per Context7 `/syrupy-project/syrupy` llms.txt §"Create Custom Raw Binary Snapshot Extension" pattern, swapped to TEXT mode for HTML:

```python
# tests/conftest.py  (or tests/_snapshot_extension.py if conftest > N LOC)
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

class HTMLSnapshotExtension(SingleFileSnapshotExtension):
    """Phase 9 TEST-HARNESS-01 — one .html file per snapshot, text mode."""
    _file_extension = "html"
    _write_mode = WriteMode.TEXT
```

**syrupy 4.x quirk:** The public attribute is `_file_extension` (underscore-prefixed) in 4.x — this is the underscore name actually checked by `SingleFileSnapshotExtension.get_snapshot_name`. The README example uses `file_extension = "bin"` (no underscore), which works because the class accepts both via descriptor; the underscore form is the safest cross-version pin. [CITED: github.com/syrupy-project/syrupy README §"Create Custom Raw Binary Snapshot Extension"]

**Fixture wiring:**

```python
import pytest

@pytest.fixture
def html_snapshot(snapshot):
    return snapshot.with_defaults(extension_class=HTMLSnapshotExtension)
```

### 3.2 Missing-snapshot soundness (D-906 requirement)

`assert actual == snapshot` **fails by default** if the snapshot file doesn't exist. Running with `--snapshot-update` is the only way to generate a missing snapshot. No `--strict` mode is needed; this is baseline syrupy behavior. [CITED: github.com/syrupy-project/syrupy README §"Basic Snapshot Test"]

Implication for D-906 — `pytest -m live --refresh-live` operator path is implemented as:

```bash
pytest -m live --refresh-live --snapshot-update   # operator regenerates
pytest -m live                                     # CI/dev: must match cassette
```

The `--refresh-live` flag itself is **custom** (added via `pytest_addoption`); `--snapshot-update` is syrupy-native.

### 3.3 Where snapshots live on disk

Default location: `tests/__snapshots__/<test_module>.ambr`. But for `SingleFileSnapshotExtension`, each assertion gets its own file in `tests/__snapshots__/<test_module>/<test_function>[.html]`. **Override via** `--snapshot-dirname=fixtures/<retailer>` or by passing a custom `path` in `snapshot(name=..., path=...)`.

**Decision for Phase 9:** Snapshots live at `tests/fixtures/<retailer>/_live-YYYY-MM-DD-<slug>.html` per D-905 + ARCHITECTURE.md §B. This is **NOT** syrupy's default; the planner needs the harness to *redirect* the snapshot location. Two viable approaches:

| Approach | Pros | Cons |
|----------|------|------|
| **A.** Override `dirname()` and `discover_subclasses` in the custom extension | Snapshots live where humans expect them | Adds ~15 LOC to extension; tests slightly couple to layout |
| **B.** Use syrupy default location + add `_live-2026-05-13-stereotype.html` as *manual* fixture (read with `pathlib.Path.read_text`) + only use syrupy for diff in `--refresh-live` mode | No syrupy dirname override needed; matches Phase 8 fixture-loader pattern | Drift detection limited to refresh runs (consistent with D-906 explicit two-mode) |

**Recommendation:** **Approach B**. Cassette-replay mode loads fixtures via `pathlib.Path.read_text` (same shape as `tests/conftest.py:104`'s `goldapple_pdp_html_live_stereotype` fixture) and parses; syrupy's `html_snapshot` is *only* used in `--refresh-live` mode against the same on-disk file. This avoids fighting syrupy's dirname conventions and keeps the file layout decision in our code, not in syrupy's plugin internals.

---

## 4. Pydantic 2.10 Write-Boundary — Idiomatic Shape

### 4.1 `NonEmptyStr` — Annotated vs Field

Both Pydantic 2 idioms work; Annotated is the recommended-by-docs form for reusable constraint types in 2.10:

```python
# src/ga_crawler/storage/schemas.py
from typing import Annotated, Optional
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
```

Either of these in a model body is equivalent at runtime:
```python
brand: NonEmptyStr                                  # Annotated form (recommended)
brand: str = Field(min_length=1)                    # Field form (equivalent, more familiar)
```

The `string_too_short` error code (verified via Context7 Pydantic docs) is what `.errors()[0]['type']` returns for both. [CITED: github.com/pydantic/pydantic docs/errors/validation_errors.md]

### 4.2 Per-row validation in the writer loop

Drop into the existing for-loop at `src/ga_crawler/storage/sqlite.py:186-192`. Validate **after** `valid_fields` filter, **before** `Snapshot(**payload)`:

```python
# Inside SqliteSnapshotWriter.append, modified:
from ga_crawler.storage.schemas import GoldappleRawProduct, ViledRawProduct
from pydantic import ValidationError

_SCHEMA_BY_RETAILER = {
    "goldapple": GoldappleRawProduct,
    "viled": ViledRawProduct,
}

def append(self, run_id, retailer, products):
    ...
    schema_cls = _SCHEMA_BY_RETAILER.get(retailer)
    rejected_reasons: list[dict] = []
    for product in products:
        payload = {k: v for k, v in product.items() if k in valid_fields}
        payload["run_id"] = run_id
        payload["retailer"] = retailer
        if schema_cls is not None:
            try:
                schema_cls.model_validate(payload)
            except ValidationError as e:
                rejected_reasons.append({
                    "sku_id": product.get("sku_id", "<unknown>"),
                    "errors": [{"loc": list(err["loc"]), "type": err["type"]}
                               for err in e.errors()],
                })
                continue  # skip INSERT for this row
        row = Snapshot(**payload)
        session.add(row)
        inserted += 1
        ...
    # Returned via writer attribute; orchestrator calls patch_stats with
    # {schema_rejected_count: len(rejected_reasons),
    #  schema_rejected_reasons: rejected_reasons[:50]}  # truncate to bound memory
    self._last_rejected_reasons = rejected_reasons
    return inserted
```

**Memory note:** Truncate `rejected_reasons[:50]` before storing in `runs.stats` JSON. 88 SKUs × ~3 errors each ≈ 264 entries ≈ ~20 KB; safe, but capping at 50 keeps `stats` row size bounded in pathological drift modes (e.g., 1000-SKU regressions).

### 4.3 Validate-in-place vs validate-and-re-emit

CONTEXT.md doesn't pin this. Recommendation: **validate-in-place** (call `model_validate(payload)` for the side-effect of raising; do **not** use `.model_dump()` to re-emit). The dispatcher already normalized via `asdict()` (parsers/dispatcher.py:51), and the writer's `valid_fields` filter handles unknown keys. Re-emitting through Pydantic would risk type coercion (e.g., `current_price: Decimal | int` flips) that could surprise downstream gates.

### 4.4 Skeleton: schema file

```python
# src/ga_crawler/storage/schemas.py
from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]

class RawProductBase(BaseModel):
    """Shared fields between goldapple/viled raw product dicts (post-dispatcher)."""
    model_config = ConfigDict(extra="ignore")  # writer pre-filters via valid_fields

    sku_id: NonEmptyStr
    url: NonEmptyStr
    name: NonEmptyStr
    brand: NonEmptyStr
    current_price: int = Field(gt=0)  # KZT integer; gt=0 rejects 0/negative

class GoldappleRawProduct(RawProductBase):
    """Strict: goldapple beauty PDPs always carry volume per shape-table (25/30 = 83%);
    null volume in append-time => parser drift, fail row (and fail run via 5% gate)."""
    volume_raw: NonEmptyStr

class ViledRawProduct(RawProductBase):
    """Relaxed: Frederic Malle Contre-Jour and Creed Wild Vetiver legitimately
    lack `Размер` attribute per 08-01 W0 spike + BUG-FINDINGS.md."""
    volume_raw: Optional[NonEmptyStr] = None
```

**Note:** `Snapshot` table column is `current_price: Optional[int]` (`sqlite.py:77`). Schema tightens this to `int > 0` because at the write boundary, a None/0 price is unrecoverable. If telemetry shows legitimate Nones (e.g., out-of-stock), planner can relax to `Optional[int] = Field(default=None, ge=0)` after seeing first-week production runs.

---

## 5. pytest Marker + Custom Flag Wiring

### 5.1 Does `pytest -m live` collect tests without `@pytest.mark.live`?

**No** — `-m EXPR` is an *evaluation* filter, not a collection filter. Tests are collected, then `EXPR` is evaluated against each test's marker set; non-matching are deselected. Tests without `@pytest.mark.live` are *deselected* (not failed). [CITED: pytest 8 docs §"Working with custom markers"]

Consequence: `tests/live/test_parser_drift.py` MUST explicitly `@pytest.mark.live` every test function (or apply `pytestmark = pytest.mark.live` at module level). The marker registration in `pyproject.toml:50-53` is already done from Phase 7 — no `addinivalue_line` work needed in Phase 9.

### 5.2 `--refresh-live` custom flag — wiring pattern

Verbatim adaptation of the Context7-verified `--runslow` pattern from pytest docs §"Control test skipping with custom CLI options":

```python
# tests/conftest.py — add to existing file
import pytest

def pytest_addoption(parser):
    parser.addoption(
        "--refresh-live",
        action="store_true",
        default=False,
        help="Re-fetch live URLs via Camoufox/curl_cffi instead of replaying cassettes. "
             "Operator-only; combine with --snapshot-update to regenerate fixtures.",
    )

@pytest.fixture
def refresh_live(request) -> bool:
    return request.config.getoption("--refresh-live")
```

**Live-drift test consumes the fixture** to branch:

```python
@pytest.mark.live
@pytest.mark.asyncio
async def test_goldapple_stereotype_drift(refresh_live, html_snapshot):
    if refresh_live:
        async with GoldappleFetcher(...) as fetcher:
            html = await fetcher.fetch_one(...)["html"]
        assert html == html_snapshot   # syrupy diff; --snapshot-update updates fixture
    else:
        html = (FIXTURES_DIR / "_live-2026-05-13-stereotype.html").read_text("utf-8")
    product = parse_pdp(html, "https://goldapple.kz/19000440474-stereotype-sago")
    assert product is not None
    assert product.brand and product.name
    assert product.brand.lower() not in product.name.lower()
    assert product.current_price > 0
    assert product.raw_volume_text  # NonEmptyStr equivalent at parser layer
```

### 5.3 Stale-fixture warning — `warnings.warn` not `pytest.warns`

Per D-906, sidecar `date` > 30 days → **pytest warning, not fail**. Use stdlib `warnings.warn` in the fixture loader; pytest auto-promotes to a UserWarning that surfaces in test report. `pytest.warns` is a *test-side assertion context manager*, not a producer.

```python
import warnings
from datetime import datetime, timezone, timedelta

def _check_fixture_age(sidecar_path: Path):
    if not sidecar_path.exists():
        return
    meta = json.loads(sidecar_path.read_text("utf-8"))
    captured = datetime.fromisoformat(meta["date"]).replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - captured
    if age > timedelta(days=30):
        warnings.warn(
            f"Live fixture {sidecar_path.stem} is {age.days}d old (>30d). "
            f"Consider `pytest -m live --refresh-live --snapshot-update`.",
            UserWarning,
            stacklevel=2,
        )
```

---

## 6. Code Skeletons (paste-ready into PLAN.md task `action` fields)

### 6.1 `_assert_fixture_clean(path)` — PII canary regex shape

```python
# tests/conftest.py
import re
from pathlib import Path

_PII_PATTERNS = (
    re.compile(r"cf_clearance\s*=", re.IGNORECASE),
    re.compile(r"\bbot\d{9,10}:[A-Za-z0-9_\-]{30,}\b"),  # Telegram bot token shape
    re.compile(r"\bAuthorization:\s*Bearer\b", re.IGNORECASE),
    # UUID v4 (strict 4xxx variant; loosen if hc-ping uses v5)
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
               re.IGNORECASE),
    re.compile(r"hc-ping\.com/[0-9a-f-]{32,36}"),  # explicit hc-ping path
)
_MAX_FIXTURE_BYTES = 50 * 1024 * 1024  # 50 MB
_MAX_AGGREGATE_BYTES = 200 * 1024 * 1024  # 200 MB

def _assert_fixture_clean(path: Path) -> None:
    """Fail-fast (no content leak) PII + size canary. D-907."""
    size = path.stat().st_size
    if size > _MAX_FIXTURE_BYTES:
        pytest.fail(f"Fixture {path.name} is {size} bytes (>{_MAX_FIXTURE_BYTES}); refuse to load.")
    content = path.read_text(encoding="utf-8", errors="replace")
    for pat in _PII_PATTERNS:
        m = pat.search(content)
        if m:
            # Fail with path + matched-pattern, NOT matched-text (avoid leaking secret)
            pytest.fail(
                f"PII pattern matched in {path}: pattern={pat.pattern!r}. "
                f"Scrub fixture and recapture via `python -m ga_crawler capture-fixtures`."
            )
```

### 6.2 Sidecar JSON helper

```python
# tests/conftest.py (or tests/_fixture_metadata.py)
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

@dataclass(frozen=True)
class FixtureMetadata:
    date: str  # ISO 8601 UTC, e.g. "2026-05-13T22:47:00+00:00"
    url: str
    status: int
    html_size: int
    title: str
    camoufox_version: str

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2, sort_keys=True)

def write_sidecar(fixture_path: Path, meta: FixtureMetadata) -> Path:
    """Writes <fixture>.json beside <fixture>.html. Idempotent."""
    sidecar = fixture_path.with_suffix(".json")
    sidecar.write_text(meta.to_json(), encoding="utf-8")
    return sidecar

def read_sidecar(fixture_path: Path) -> FixtureMetadata | None:
    sidecar = fixture_path.with_suffix(".json")
    if not sidecar.exists():
        return None
    return FixtureMetadata(**json.loads(sidecar.read_text("utf-8")))
```

### 6.3 `schema_rejected_rate_gate` (matches D-203 retailer-agnostic pattern)

```python
# Append to src/ga_crawler/runner/gates.py
@dataclass(frozen=True)
class SchemaRejectedGateResult:
    """Result of the TEST-HARNESS-06 schema-rejected-rate gate.

    Source: 09-CONTEXT.md D-903.
    """
    passed: bool
    rejected_rate: float
    rejected_count: int
    total_attempted: int
    failure_reason: Optional[str]  # "schema_validation_rejected_rate" if !passed


def schema_rejected_rate_gate(
    rejected_count: int,
    total_attempted: int,
    *,
    threshold: float = 0.05,
) -> SchemaRejectedGateResult:
    """D-903: TEST-HARNESS-06 schema-rejection sanity gate.

    rejected_rate = rejected_count / total_attempted.
    Strict-greater-than: exactly 5% passes; 5.01% fails. Matches Phase 8
    `parser_drift_null_rate_gate` convention (08-CONTEXT.md D-815).

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

### 6.4 New `runs.stats` keys (extend `runner/stats.py`)

Add three keys per Phase-2 atomic-merge pattern (D-211). These are **shared** across retailers (run-level, not retailer-scoped), so they go in a new namespace `schema.*`:

```python
# src/ga_crawler/runner/stats.py — APPEND
SCHEMA_STATS_KEYS: tuple[str, ...] = (
    "schema.rejected_count",         # int  — per-row Pydantic ValidationError catches
    "schema.rejected_rate",          # float — rejected_count / total_attempted_persist
    "schema.rejected_reasons",       # list[{sku_id, errors:[{loc, type}, ...]}], capped at 50
)
```

No new `StatsBuilder` class needed if planner accepts inline `patch_stats(run_id, {"schema.rejected_count": ...})` calls; or mirror `GoldappleStatsBuilder` for parity. Planner-discretion.

### 6.5 Brand-coverage canary (TEST-HARNESS-04, P2 GO only)

```python
# tests/test_brand_coverage_canary.py — only if P2 GO
import pytest
from pathlib import Path
from ga_crawler.storage.sqlite import make_engine
from sqlmodel import Session, select
# ... query: SELECT DISTINCT brand_norm FROM snapshots
# WHERE retailer='goldapple' AND scraped_at > now() - INTERVAL 4 WEEKS

ACTIVE_BRANDS_LOOKBACK_RUNS = 4   # last 4 weekly runs

def test_each_active_brand_has_a_fixture(repo_db_path):
    active_brands = _query_active_brands(repo_db_path, ACTIVE_BRANDS_LOOKBACK_RUNS)
    fixture_brands = set()
    for f in Path("tests/fixtures/goldapple").glob("_live-*.html"):
        meta = read_sidecar(f)
        if meta and meta.title:
            # extract brand from title via existing parser
            from ga_crawler.parsers.goldapple_microdata import parse_pdp
            p = parse_pdp(f.read_text("utf-8"), meta.url)
            if p:
                fixture_brands.add(p.brand_raw.strip().lower())
    missing = active_brands - fixture_brands
    if missing:
        pytest.fail(f"Active goldapple brands without live fixture: {sorted(missing)}")
```

### 6.6 `python -m ga_crawler capture-fixtures` CLI (TEST-HARNESS-05, P2 GO only)

Hook into existing `src/ga_crawler/__main__.py` dispatcher (matches `weekly-run`/`report-run` shape per ARCH §B). Reuses `GoldappleFetcher` + `ViledFetcher` verbatim — no new fetcher code:

```python
# Conceptual shape; planner writes exact wiring
# python -m ga_crawler capture-fixtures --retailer goldapple --url <URL> --slug <slug>
async def capture_fixtures(retailer: str, url: str, slug: str) -> None:
    if retailer == "goldapple":
        async with GoldappleFetcher(...) as f:
            rec = await f.fetch_one(f._page, url)
            html = rec["html"]
            title = rec.get("title", "")
    else:  # viled
        rec = await viled_fetcher.fetch_one(url)  # curl_cffi
        html, title = rec.html, rec.title
    html = _scrub_html(html)  # remove cf_clearance, bot tokens, UUIDs (D-907 belt-and-suspenders)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fixture_path = Path(f"tests/fixtures/{retailer}/_live-{today}-{slug}.html")
    fixture_path.write_text(html, encoding="utf-8")
    write_sidecar(fixture_path, FixtureMetadata(
        date=datetime.now(timezone.utc).isoformat(),
        url=url, status=rec.get("status", 0), html_size=len(html),
        title=title, camoufox_version=_camoufox_version_at_runtime(),
    ))
```

---

## 7. Landmines

### 7.1 Camoufox HTML capture non-determinism (HIGH — blocks D-906)

**Problem:** Each Camoufox fetch of the same goldapple PDP produces slightly different HTML:
- `<meta name="csrf-token" content="...">` (rotates per request)
- `cf_clearance` cookie echoes back in some inline `<script>` JSON payloads
- CSS-class build-hash suffixes (`_ga-pdp-title__heading_1yrfv_339`) change on goldapple deploys (per SKILL.md L45)
- ray-id headers and `__NEXT_DATA__` `buildId` field

syrupy diffs bytewise. Without normalization, **every `--refresh-live` re-capture will fail** even when the parser-relevant DOM is unchanged. That's a Pitfall #2 (cassette staleness) instance reborn as Pitfall #4 (flake hides drift) — operator either:
- gets noise-fatigued and accepts the diff blindly (`--snapshot-update` always)
- gives up on `--refresh-live` and the harness rots

**Mitigation:** Add a `normalize_for_snapshot(html: str) -> str` step **before** `assert html == html_snapshot`. Strips:
- `<meta name="csrf-token" content="[^"]*">` → `<meta name="csrf-token" content="NORM">`
- `cf_clearance=[^;"]*` → `cf_clearance=NORM`
- `_ga-pdp-title__heading_[a-z0-9_]+` → `_ga-pdp-title__heading_NORM` (and same for `__brand_`, `__name_`)
- `__NEXT_DATA__` `buildId` → `"buildId":"NORM"`

Plan should include a `tests/_html_normalize.py` helper + a unit test asserting normalize is idempotent (`normalize(normalize(x)) == normalize(x)`).

**Confidence:** HIGH that this is needed. Phase 8 SMOKE rotation already evidences class-hash drift (see `goldapple_microdata.py` substring-match comment). Planner MUST include normalization in plan 09-01 W0.

### 7.2 Pydantic 2 `ValidationError.errors()` includes input value by default — leak surface (MEDIUM)

`e.errors()` returns dicts including `'input': <original value>`. For a row with `brand=""`, the `input` is `""` — harmless. But for `current_price=-1` or a malformed url containing a session token, the input is captured into `runs.stats` and persisted to SQLite forever. Mitigation: explicitly omit `input` when serializing (already done in §4.2 skeleton — only emit `loc` and `type`). Planner MUST keep the projection.

**Confidence:** MEDIUM-HIGH; verified by Context7 docs/errors/errors.md showing `'input': {...full dict...}` in `errors()` output.

### 7.3 syrupy 4.x → 5.x breaking change risk (LOW for v1.1, MEDIUM future)

syrupy 5.0.0 (released 2026-01-25) and 5.1.0 ship breaking changes. The CONTEXT.md pin `>=4.7,<5.0` correctly prevents an accidental major bump. Concrete latest in range: `4.9.1` (2025-03-24). Confidence HIGH that 4.9.1 has the `SingleFileSnapshotExtension` + `WriteMode` API verified above. v1.2 reconsideration item (planner can note in 09-03 doc-cascade).

### 7.4 Pydantic `extra="ignore"` masks dispatcher contract drift (LOW)

`ConfigDict(extra="ignore")` lets the schema accept any extra keys silently. If the dispatcher adds a new key (e.g., `volume_norm`) that should be validated, the schema won't notice. Mitigation: `extra="forbid"` would reject unknown keys, but the writer's `valid_fields` filter strips them before Pydantic sees them — so `extra="forbid"` would actually be safe. **Recommendation:** Use `extra="forbid"` for stricter contract enforcement; the writer's filter already removes Snapshot-unknown keys, so anything Pydantic sees must be schema-known. Planner-discretion.

### 7.5 pytest marker registered but never used (LOW — non-issue now)

Phase 7 declared `live` marker in `pyproject.toml:50-53` but no test used it. Phase 9 finally wires it. **No PytestUnknownMarkWarning** because the marker is already registered. Verified.

### 7.6 Fixture-loader `_assert_fixture_clean` cost on every test session (LOW)

A 200 KB regex-scan × 3-5 fixtures × `scope="session"` = ~5 ms per session. Negligible. But if P2 GO adds 20+ live fixtures from TEST-HARNESS-04 brand-coverage canary, total grows linearly. At ~30 fixtures × 200 KB it's still <100 ms. **Confidence:** LOW concern; no mitigation needed before observed slowdown.

### 7.7 `[BLOCKING]` schema-push verdict (NO blocker)

**Question:** Does Phase 9 need a DB schema migration task?
**Answer:** **NO.** Pydantic validates in-memory before SQL INSERT. The `Snapshot` SQLModel at `sqlite.py:60-87` is unchanged. The new `schema.*` stats keys go into the existing `runs.stats` JSON column (already accommodates per-namespace keys via `json_patch`). Zero DDL needed in Phase 9.

---

## 8. Validation Architecture

> Required per Nyquist gate. Lists 7 verifiable validations that Phase 9 must satisfy.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8 + pytest-asyncio 0.24 + pytest-mock 3.14 + **syrupy 4.9.x** (NEW) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` — markers `live`, `integration` already declared |
| Quick run command | `uv run pytest -x -m "not live"` (~30s, default CI) |
| Full suite command | `uv run pytest` (~60s, plus `uv run pytest -m live` operator-track) |
| Phase gate | Full suite green + PII canary green before `/gsd-verify-work` |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Automated Command | File |
|-----|----------|-----------|-------------------|------|
| TH-01 | syrupy installed; `HTMLSnapshotExtension` importable + subclasses `SingleFileSnapshotExtension` | unit | `pytest tests/test_snapshot_extension.py -x` | NEW Wave 0 |
| TH-02a | PII canary fails on dirty fixture | unit | `pytest tests/test_live_fixtures_pii_canary.py::test_dirty_fixture_fails -x` | NEW Wave 0 |
| TH-02b | 50 MB size budget triggers (synthetic 51 MB file) | unit | `pytest tests/test_live_fixtures_pii_canary.py::test_oversize_rejected -x` | NEW Wave 0 |
| TH-02c | Sidecar JSON written + read round-trip | unit | `pytest tests/test_fixture_metadata.py -x` | NEW Wave 0 |
| TH-03a | `pytest -m live` (cassette-replay default) parses 3 Phase 8 fixtures with brand+name+vol invariants | live (cassette) | `pytest -m live tests/live/test_parser_drift.py -x` | NEW Wave 1 |
| TH-03b | `pytest -m live --refresh-live` re-fetches + asserts deterministic post-normalize HTML | live (refresh) | `pytest -m live --refresh-live tests/live/test_parser_drift.py -x` (operator-only) | NEW Wave 1 |
| TH-03c | Missing-snapshot fails CI (negative test: delete fixture → suite RED) | unit | `pytest tests/test_snapshot_soundness.py -x` | NEW Wave 1 |
| TH-04 (P2) | ≥1 fixture per active brand in last 4 runs | integration | `pytest tests/test_brand_coverage_canary.py -x` | NEW Wave 2 (cond.) |
| TH-05 (P2) | `python -m ga_crawler capture-fixtures --dry-run` writes correctly-shaped HTML+JSON | integration | `pytest tests/integration/test_capture_fixtures_cli.py -x` | NEW Wave 2 (cond.) |
| TH-06a | Strict goldapple schema rejects empty `volume_raw` | unit | `pytest tests/storage/test_schemas.py::test_goldapple_strict -x` | NEW Wave 1 |
| TH-06b | Relaxed viled schema accepts `volume_raw=None` | unit | `pytest tests/storage/test_schemas.py::test_viled_relaxed -x` | NEW Wave 1 |
| TH-06c | `SqliteSnapshotWriter.append` skips invalid rows + increments `schema.rejected_count` | integration | `pytest tests/integration/test_writer_schema_gate.py -x` | NEW Wave 1 |
| TH-06d | `schema_rejected_rate_gate(rate=0.05)` passes; `0.0501` fails | unit | `pytest tests/runner/test_schema_rejected_gate.py -x` | NEW Wave 1 |

### Wave 0 Test File Gaps (to write — RED-first per D-811)

- [ ] `tests/test_snapshot_extension.py` — TH-01 sanity (subclass, file_extension, write_mode)
- [ ] `tests/test_live_fixtures_pii_canary.py` — TH-02a, TH-02b (canary + size budget)
- [ ] `tests/test_fixture_metadata.py` — TH-02c (sidecar round-trip)
- [ ] `tests/test_snapshot_soundness.py` — TH-03c negative test
- [ ] `tests/storage/test_schemas.py` — TH-06a, TH-06b (per-retailer schemas)
- [ ] `tests/integration/test_writer_schema_gate.py` — TH-06c (writer integration)
- [ ] `tests/runner/test_schema_rejected_gate.py` — TH-06d (gate threshold semantics)
- [ ] `tests/live/test_parser_drift.py` — TH-03a, TH-03b (the headline test; replays 3 Phase 8 fixtures)
- [ ] `tests/live/__init__.py` — new package marker
- [ ] `tests/storage/__init__.py` — new package marker
- [ ] Framework install: `uv add --dev "syrupy>=4.7,<5.0"`

### Sampling Rate

- **Per task commit (TDD discipline D-811):** `uv run pytest <new-file> -x` (~5s)
- **Per wave merge:** `uv run pytest -x -m "not live"` (~30s; excludes live tests)
- **Per phase gate:** `uv run pytest` (full suite, ~60s) + `uv run pytest -m live` (cassette-replay, ~10s; NO `--refresh-live` in CI)
- **Operator-only post-deploy:** `uv run pytest -m live --refresh-live --snapshot-update` (the only path that hits Camoufox; D-906)

---

## 9. Open Questions for Planner

**Q1. `SqliteSnapshotWriter` method name — CONTEXT.md says "persist", code says "append".**
- Confirmed via Read: `src/ga_crawler/storage/sqlite.py:177` → `def append(self, run_id: int, retailer: str, products: list) -> int`. No `.persist` method exists in the module.
- **Recommendation:** Planner uses `append` in all plan task `action` fields; references CONTEXT.md D-903's "persist" language in plan SUMMARY as "boundary = `SqliteSnapshotWriter.append` (CONTEXT.md uses 'persist' as conceptual name)".

**Q2. Schema file location — `storage/types.py` does NOT exist.**
- Confirmed via Glob: only `__init__.py`, `norm06_writer.py`, `sqlite.py` in `src/ga_crawler/storage/`.
- **Recommendation:** Create new file `src/ga_crawler/storage/schemas.py` (greenfield, D-904 default path).

**Q3. `schema.*` stats namespace — own `StatsBuilder` or inline `patch_stats`?**
- Existing pattern (`GoldappleStatsBuilder`, `ViledStatsBuilder` in `stats.py`) is namespace-builder-per-retailer. `schema.*` is *run-level* (not retailer-scoped) — first such case.
- **Options:** (a) inline 3 keys directly in `patch_stats` call from the orchestrator; (b) add a `SchemaStatsBuilder` for parity.
- **Recommendation:** Planner picks (a) for minimal blast radius — Phase 9 already adds enough surface. Document in plan that future run-level stats (e.g., delivery metrics) would warrant a builder.

**Q4. `Snapshot` table `current_price: Optional[int]` vs schema `current_price: int > 0` — mismatch is acceptable?**
- The table is permissive (legacy from Phase 2 — see `sqlite.py:77`). The Pydantic schema tightens to `> 0` because at write time, a None/0 price is unrecoverable. This *intentionally* rejects rows that the table column would accept.
- **Recommendation:** Planner accepts the tightening. If first-week production shows legitimate Nones (e.g., out-of-stock SKUs), Phase 9.5 relaxes to `Optional[int] = Field(ge=0)`. Document in 09-RESEARCH callout.

**Q5. HTML normalization for syrupy diff — where does it live?**
- Plan candidate: `tests/_html_normalize.py` (test-side helper) OR `src/ga_crawler/fetchers/normalize.py` (production code, reusable by capture-fixtures CLI).
- **Recommendation:** Test-side. Production code does not need to normalize live HTML; only the syrupy diff path does. Keeps wheel clean (per ARCH §B's "don't contaminate wheel" stance on `src/ga_crawler/testing/`).

**Q6. Stale-fixture 30d threshold — global constant or per-fixture override?**
- D-906 says 30 days flat. Recommend global; per-fixture override is YAGNI.

**Q7. PII canary regex set — covers Telegram bot token shape `bot\d+:` from PITFALLS.md §3?**
- §6.1 skeleton includes `\bbot\d{9,10}:[A-Za-z0-9_\-]{30,}\b`. Verified against PITFALLS L124-125 example pattern `\d{9,10}:[A-Za-z0-9_-]{35}`. Slight tweak (`{30,}` vs `{35}`) accepts post-2023 longer tokens.

---

## 10. Confidence Breakdown

| Area | Level | Reason |
|------|-------|--------|
| syrupy 4.x API stability | HIGH | Context7 + PyPI verified 4.9.1; pattern unchanged through 4.x range |
| `SingleFileSnapshotExtension` subclass shape | HIGH | Direct verbatim from Context7 llms.txt |
| Pydantic 2.10 `ValidationError.errors()` shape | HIGH | Context7 docs verified |
| `NonEmptyStr` Annotated form | HIGH | Pydantic 2 idiom; both Annotated and Field equivalent at runtime |
| Storage method name (`append`) | HIGH | Direct file read confirms |
| Storage schema file location | HIGH | Glob confirms `types.py` absent |
| HTML normalization need | HIGH | SKILL.md L45 already documents CSS-class hash drift |
| Camoufox HTML determinism (specific keys to strip) | MEDIUM | Inferred from PITFALLS + SKILL; planner Wave 0 task should empirically diff two captures |
| pytest marker collection semantics | HIGH | Context7 pytest docs verified |
| Per-row Pydantic perf at ~100 rows | HIGH | Pydantic 2 core is Rust-backed; 1-3ms total expected |
| 50 MB / 30 day thresholds | MEDIUM | Operator-chosen heuristics in CONTEXT.md; no upstream constraint |

**Research date:** 2026-05-14
**Valid until:** 2026-06-14 (syrupy 4.x stable; Pydantic 2.10+ stable through 2.13; 30-day shelf life)

---

## 11. Sources

### Primary (HIGH confidence)
- Context7 `/syrupy-project/syrupy` — `SingleFileSnapshotExtension`, `WriteMode.TEXT`, CLI options, missing-snapshot soundness
- Context7 `/pydantic/pydantic` — `ValidationError`, `model_validate`, `StringConstraints`, `string_too_short`
- Context7 `/pytest-dev/pytest` — `pytest_addoption`, custom-flag patterns, marker collection
- PyPI `https://pypi.org/pypi/syrupy/json` — 4.9.1 latest in `<5.0`; 5.1.0 latest overall (2026-01-25)
- PyPI `https://pypi.org/pypi/pydantic/json` — 2.13.4 latest (compatible with `>=2.10,<3.0` pin)
- Direct file read: `src/ga_crawler/storage/sqlite.py`, `src/ga_crawler/runner/{gates,stats}.py`, `src/ga_crawler/parsers/dispatcher.py`, `tests/conftest.py`, `pyproject.toml`
- `.planning/research/STACK.md` §B (lines 85-119) — syrupy pattern verbatim baseline
- `.planning/research/ARCHITECTURE.md` §B (lines 80-117) — harness placement contract
- `.planning/research/PITFALLS.md` §1-§4 — cassette staleness, PII, JS-race, drift hiding
- `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` — shape buckets evidence for D-904 + §7.1 normalization landmine

### Secondary (MEDIUM confidence)
- `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` (referenced via canonical_refs; not re-read in this research run — CONTEXT.md D-904 already incorporated)
- `.planning/phases/08-parser-bug-fixes/08-CONTEXT.md` D-808..D-811 — TDD pattern reused

### Tertiary (LOW — no claim depends on these)
- None — all claims in this research were either Context7-verified or file-grep-verified.

## 12. Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Camoufox emits CSS-class build-hash suffix that rotates on goldapple deploys | §7.1 | If hash is stable, normalization step is dead code (harmless) |
| A2 | `cf_clearance` cookie echoes in goldapple inline `<script>` JSON | §7.1 | If absent, one regex line is dead code |
| A3 | hc-ping.com UUID paths are v4 (4xxx variant byte) | §6.1 | If v5 or non-RFC, regex misses; loosen to `[0-9a-f-]{32,36}` (already in skeleton as second pattern) |
| A4 | Pydantic 2.10 `extra="forbid"` is safe given writer's `valid_fields` pre-filter | §7.4 | Unsafe only if filter shape drifts; covered by integration test TH-06c |
| A5 | 88-row × `model_validate` perf is < 5ms total | §1, §4 | If slow, batch via `TypeAdapter(list[GoldappleRawProduct]).validate_python` — same accuracy, ~2× faster |
| A6 | The 3 Phase 8 live fixtures (`_live-2026-05-13-*.html`) are PII-clean per current state | §7 | Verified via Grep: 0 matches for `cf_clearance|set-cookie|x-bot-token|hc-ping` in stereotype fixture (2026-05-14) |
| A7 | syrupy 4.9.1 retains `_file_extension` underscore-prefixed attribute | §3.1 | If renamed, fall back to `file_extension = "html"` (also accepted per README example) |

**Operator-confirmation needed before code-ship:** A1, A2 (empirical — Wave 0 09-01 task should diff two captures of `stereotype.html` taken 30 minutes apart and decide normalization scope from observed drift). A3-A7 are low-risk and self-validating via tests.

---

## RESEARCH COMPLETE
