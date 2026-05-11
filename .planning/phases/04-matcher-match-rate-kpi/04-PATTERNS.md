# Phase 4: Matcher + Match-Rate KPI — Pattern Map

**Mapped:** 2026-05-11
**Files analyzed:** 11 (7 new + 4 amended)
**Analogs found:** 11/11 (100%) — Phase 4 is pure derivation; every primitive already lives in the codebase

## Scope Anchors

- **CONTEXT.md:** `.planning/phases/04-matcher-match-rate-kpi/04-CONTEXT.md` (D-401..D-415)
- **REQUIREMENTS.md:** MATCH-01..04 active (lines 44-47)
- **ROADMAP.md:** Phase 4 §"Matcher + Match-Rate KPI" (lines 95-106)
- **No RESEARCH.md** — user opted to skip research per orchestrator note. Every "what to do" decision must be backed by either (a) CONTEXT.md decision or (b) a verbatim analog excerpt below.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/ga_crawler/matcher/__init__.py` | package-init | n/a | `src/ga_crawler/runner/__init__.py` | exact |
| `src/ga_crawler/matcher/strict_key.py` | service (SQL builder + derivation primitives) | batch / transform / SQL | `src/ga_crawler/storage/sqlite.py` (`patch_stats` raw `text()` UPDATE; `init_db` VIEW DDL) + `src/ga_crawler/runners/main_run.py` `_derive_viled_brands_from_snapshots` (raw `text()` query) | role-match (SQL JOIN/INSERT builder is novel; SQL execution pattern is exact match) |
| `src/ga_crawler/matcher/stats.py` | model (namespace-enforced builder) | event-driven (per-run accumulator) | `src/ga_crawler/runner/stats.py::ViledStatsBuilder` + `GoldappleStatsBuilder` (D-414 explicit mirror) | exact |
| `src/ga_crawler/runners/matcher_run.py` | orchestrator (sync phase runner) | request-response (read run → JOIN → INSERT → patch_stats → fail/finalize) | `src/ga_crawler/runners/viled_run.py::run_viled_phase` (sync, sequential gates, atomic single patch_stats) | exact |
| `tests/unit/test_matcher_strict_key.py` | test (SQL builder unit) | n/a | `tests/unit/test_snapshot_writer.py` (in-memory engine + per-test fixture; `IntegrityError` boundary tests) | exact |
| `tests/unit/test_matcher_stats.py` | test (namespace builder unit) | n/a | `tests/unit/test_viled_stats_builder.py` (exact mirror; D-414 explicit) | exact |
| `tests/integration/test_matcher_run.py` | test (orchestrator integration with mocks) | n/a | `tests/integration/test_run_e2e_with_phase2_mocks.py` (orchestrator-level with mock Phase 2 protocols) + `tests/integration/test_main_run_e2e.py` (real engine + tmp_path setup) | exact |
| `src/ga_crawler/storage/sqlite.py` (AMEND) | model (add `Match` SQLModel table) | CRUD (table definition) | existing `Run` / `Snapshot` classes in same file | exact (self-analog) |
| `src/ga_crawler/runners/main_run.py` (AMEND) | orchestrator (compose matcher step) | request-response | existing viled→goldapple composition in same file (lines 154-238) | exact (self-analog) |
| `src/ga_crawler/cli.py` (AMEND) | controller (add `matcher-run` subcommand) | request-response | existing `goldapple-smoke` / `weekly-run` subcommands in same file | exact (self-analog) |
| `pyproject.toml` (AMEND) | config (add `[tool.ga_crawler.match]` namespace) | n/a | existing `[tool.ga_crawler.crawl.viled]` + `[tool.ga_crawler.crawl.goldapple]` namespaces | exact |

---

## Pattern Assignments

### NEW `src/ga_crawler/matcher/__init__.py` (package-init)

**Analog:** `src/ga_crawler/runner/__init__.py` (1-line docstring only) and `src/ga_crawler/runners/__init__.py` (1-line docstring only).

**Pattern to copy (verbatim style):**
```python
"""Strict-key matcher (Phase 4): SQL JOIN builder, denominator query, stats namespace."""
```

Single-line module docstring matching the established convention. No public re-exports needed at the package level — callers import `from ga_crawler.matcher.strict_key import build_matches_insert_sql, compute_denominator` and `from ga_crawler.matcher.stats import MatchStatsBuilder`.

---

### NEW `src/ga_crawler/matcher/strict_key.py` (SQL JOIN builder + denominator + filters)

**Analogs:**
1. **`src/ga_crawler/storage/sqlite.py`** lines 203-222 (`patch_stats` raw `text()` UPDATE pattern; atomic transaction; SQLAlchemy `engine.begin()` semantics inherited)
2. **`src/ga_crawler/runners/main_run.py`** lines 68-83 (`_derive_viled_brands_from_snapshots` — raw `text()` SELECT against snapshots table with `:rid` bind param)

**Imports pattern** (mirror `storage/sqlite.py:24-42`):
```python
from __future__ import annotations

from typing import Optional

import structlog
from sqlalchemy import text
from sqlmodel import Session

from ga_crawler.storage.sqlite import Match  # NEW SQLModel — see sqlite.py AMEND below

log = structlog.get_logger(__name__)
```

**Pattern A — Raw SQL with bind params + `engine.begin()` transaction**
Excerpt from `storage/sqlite.py:203-222` (`patch_stats`):
```python
def patch_stats(self, run_id: int, delta: dict) -> None:
    """Atomic JSON-merge into runs.stats (Pitfall 6 RFC-7396 MergePatch)."""
    ...
    with Session(self.engine) as s:
        s.exec(  # type: ignore[call-overload]
            text(
                "UPDATE runs SET stats = json_patch(stats, :delta) "
                "WHERE run_id = :rid"
            ),
            params={"delta": delta_json, "rid": run_id},
        )
        s.commit()
```

**Apply to Phase 4:** D-410 mandates DELETE+INSERT inside a single transaction. Use `engine.begin()` (which auto-commits/rolls-back as one atomic unit) — equivalent of the `with Session: s.commit()` block above but spanning two statements:
```python
def build_matches_for_run(engine, run_id: int) -> int:
    """D-410: idempotent DELETE-and-reinsert in one transaction."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM matches WHERE run_id = :rid"), {"rid": run_id})
        result = conn.execute(text(INSERT_SELECT_SQL), {"rid": run_id})
        return result.rowcount  # rows inserted
```

**Pattern B — Raw `text()` SELECT with `:rid` binding + `engine.connect()`**
Excerpt from `runners/main_run.py:68-83` (`_derive_viled_brands_from_snapshots`):
```python
def _derive_viled_brands_from_snapshots(engine, run_id: int) -> list[str]:
    """D-221: read DISTINCT brand_norm from this run's viled snapshots."""
    sql = text(
        "SELECT DISTINCT brand_norm FROM snapshots "
        "WHERE retailer='viled' AND run_id=:rid "
        "AND brand_norm IS NOT NULL AND brand_norm <> ''"
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"rid": run_id}).fetchall()
    return sorted({row[0] for row in rows if row[0]})
```

**Apply to Phase 4 `compute_denominator(engine, run_id) -> int`** (D-404 — comparable viled SKUs in brands with goldapple presence). Read-only query → `engine.connect()` (not `.begin()`):
```python
DENOMINATOR_SQL = text("""
    SELECT COUNT(*) FROM snapshots v
    WHERE v.retailer='viled' AND v.run_id=:rid
      AND v.multipack_flag=0
      AND v.volume_norm IS NOT NULL
      AND v.stock_state != 'DELISTED'
      AND v.brand_norm IN (
        SELECT DISTINCT g.brand_norm FROM snapshots g
        WHERE g.retailer='goldapple' AND g.run_id=:rid
      )
""")
```

**Pattern C — INSERT...SELECT for denormalized matches table**
No exact analog in current codebase (matcher is the first derived-table writer), but the SQL shape is constrained by D-401 + D-402. Reference D-401 schema verbatim and D-402 filter clauses verbatim from CONTEXT lines 18-49. The orchestrator-level invariant (single transaction wrapping DELETE+INSERT) is satisfied by Pattern A's `engine.begin()` block.

**Skeleton (assemble from CONTEXT D-401/D-402):**
```python
INSERT_MATCHES_SQL = text("""
    INSERT INTO matches (
      run_id, viled_sku, goldapple_sku,
      brand_norm, name_norm, volume_norm,
      viled_price, goldapple_price,
      viled_was_price, goldapple_was_price,
      price_delta, price_delta_pct,
      matched_at
    )
    SELECT
      :rid, v.sku_id, g.sku_id,
      v.brand_norm, v.name_norm, v.volume_norm,
      v.current_price, g.current_price,
      v.was_price, g.was_price,
      (g.current_price - v.current_price),
      ROUND((g.current_price - v.current_price) * 100.0 / v.current_price, 2),
      CURRENT_TIMESTAMP
    FROM snapshots v
    JOIN snapshots g
      ON v.brand_norm = g.brand_norm
     AND v.name_norm = g.name_norm
     AND v.volume_norm = g.volume_norm
    WHERE v.retailer='viled'    AND v.run_id=:rid
      AND v.multipack_flag=0    AND v.volume_norm IS NOT NULL
      AND v.stock_state != 'DELISTED'
      AND g.retailer='goldapple' AND g.run_id=:rid
      AND g.multipack_flag=0    AND g.volume_norm IS NOT NULL
      AND g.stock_state != 'DELISTED'
""")
```

**Pattern D — Read run status (D-411 failed-crawl skip)**
Reuse `text()` + `engine.connect()` (read-only):
```python
def _read_run_status(engine, run_id: int) -> Optional[str]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT status FROM runs WHERE run_id=:rid"),
            {"rid": run_id},
        ).first()
    return row[0] if row else None
```

**Pattern E — Gate primitive reuse**
**Do NOT re-implement.** Per D-407, import and call:
```python
from ga_crawler.runner.gates import auto_suggest_threshold, final_threshold_gate
```
- `final_threshold_gate(match_count, threshold_p)` for D-409 sanity-gate.
- `auto_suggest_threshold(history, factor=0.7, min_runs=4)` for D-407 auto-suggest after 4 runs.

Both helpers are already retailer-agnostic per D-203 refactor (`runner/gates.py:242-247` and `runner/gates.py:221-239`).

---

### NEW `src/ga_crawler/matcher/stats.py` (MatchStatsBuilder, "match.*" namespace)

**Analog:** `src/ga_crawler/runner/stats.py::ViledStatsBuilder` (lines 140-209). D-414 explicit: "exactly mirror Phase 3 `goldapple.*` + Phase 2 `viled.*` namespace pattern."

D-414 also suggests **optional refactor** to a base `NamespaceStatsBuilder(prefix: str)` class (DRY win — three near-duplicate builders is the maintenance flag). The planner should make the call: keep verbatim copy (low risk) vs refactor (DRY, but touches Phase 2 + Phase 3 unit tests). **Default per D-414 / D-203:** refactor — unit tests already lock the builder API.

**Imports pattern** (mirror `runner/stats.py:11-13`):
```python
from __future__ import annotations

from typing import Any, Iterable
```

**Core builder pattern** (exact mirror of `ViledStatsBuilder` lines 142-209):

Tuple-of-keys:
```python
MATCH_STATS_KEYS: tuple[str, ...] = (
    "match.count",                       # int — numerator (rows in matches WHERE run_id=:N)
    "match.rate",                        # REAL — percent points, 2 decimals (e.g. 42.31)
    "match.numerator",                   # int — explicit dup of match.count for audit
    "match.denominator",                 # int — comparable viled in brand-overlap
    "match.brand_overlap_count",         # int — COUNT(DISTINCT brand_norm) intersection
    "match.viled_comparable_count",      # int — viled after multipack/volume/DELISTED filter
    "match.goldapple_comparable_count",  # int — goldapple-side same filter
    "match.skipped_reason",              # str | null — "failed_upstream" / "in_progress_upstream" / null
    "match.threshold_p",                 # int — applied P threshold (D-408)
    "match.gate_passed",                 # bool
)
```
(10 keys per D-414. Verify against CONTEXT D-414 lines 121-129 before locking — unit test pins the count.)

Builder class — exact mirror of `runner/stats.py:160-209`:
```python
_MATCH_BARE_TO_NAMESPACED: dict[str, str] = {
    k.split(".", 1)[1]: k for k in MATCH_STATS_KEYS
}


class MatchStatsBuilder:
    """Mirror of ViledStatsBuilder / GoldappleStatsBuilder — match.* namespace.

    Accumulates Phase 4 keys for atomic merge via RunWriter.patch_stats. Shares
    NO keys with viled.* / goldapple.* (different namespace), so all three
    builders can safely write the same runs.stats column via separate
    single-call json_patch UPDATEs (Pitfall 6).

    Source: 04-CONTEXT.md D-414; mirrors runner/stats.py:160-209.
    """

    def __init__(self) -> None:
        self.delta: dict[str, Any] = {}

    def _resolve(self, bare_key: str) -> str:
        if bare_key in _MATCH_BARE_TO_NAMESPACED:
            return _MATCH_BARE_TO_NAMESPACED[bare_key]
        if bare_key in MATCH_STATS_KEYS:
            return bare_key
        raise StatsNamespaceError(
            f"key {bare_key!r} not in MATCH_STATS_KEYS; "
            f"allowed: {sorted(MATCH_STATS_KEYS)}"
        )

    def set(self, bare_key: str, value: Any) -> None: ...
    def inc(self, bare_key: str, n: int = 1) -> None: ...
    def get(self, bare_key: str, default: Any = None) -> Any: ...
    def keys(self) -> Iterable[str]: ...
    def __len__(self) -> int: ...
```

**`StatsNamespaceError` import:** reuse the existing class from `runner/stats.py:41-42`. Either:
- Import from `ga_crawler.runner.stats import StatsNamespaceError` (preferred — single source of truth), OR
- If refactor to `NamespaceStatsBuilder` base happens, move `StatsNamespaceError` into a new shared module and re-export from both `runner/stats.py` and `matcher/stats.py` for backward-compat.

---

### NEW `src/ga_crawler/runners/matcher_run.py` (orchestrator)

**Analog:** `src/ga_crawler/runners/viled_run.py::run_viled_phase` (lines 151-325) — sync orchestrator, sequential gates, single atomic `patch_stats` at end, idempotent `run_writer.fail` on gate trip. **Phase 4 is sync per "Claude's Discretion" in CONTEXT lines 139-140: "matcher это single SQL JOIN + INSERT внутри одной транзакции. NO async."**

**Imports pattern** (mirror `runners/viled_run.py:26-52`):
```python
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import structlog

from ga_crawler.interfaces import RunWriterProtocol
from ga_crawler.matcher.stats import MatchStatsBuilder
from ga_crawler.matcher.strict_key import (
    build_matches_for_run,
    compute_denominator,
    compute_brand_overlap,
    compute_comparable_counts,
    read_run_status,
)
from ga_crawler.runner.gates import auto_suggest_threshold, final_threshold_gate

log = structlog.get_logger(__name__)
```

**PhaseResult dataclass** (mirror `viled_run.py:55-62`):
```python
@dataclass
class MatcherPhaseResult:
    """Outcome of run_matcher_phase."""
    status: str  # "success" | "failed" | "skipped"
    match_count: int = 0
    reason: Optional[str] = None
    stats_delta: dict = field(default_factory=dict)
```

**Orchestrator skeleton — 7-step flow** (mirror `viled_run.py:151-325` shape; substituted concerns):

```python
def run_matcher_phase(
    *,
    run_id: int,
    engine,                             # SQLAlchemy engine — direct SQL access required (D-410)
    run_writer: RunWriterProtocol,
    threshold_p: int = 20,              # D-408 seed
    p_auto_suggest_factor: float = 0.7,
    p_auto_suggest_after_runs: int = 4,
) -> MatcherPhaseResult:
    """Execute Phase 4 matcher.

      Step 1: Read runs.status (D-411 failed-crawl skip)
      Step 2: Compute denominator + comparable counts (D-404)
      Step 3: DELETE-and-reinsert matches (D-410 single TX)
      Step 4: Compute match.count / match.rate
      Step 5: Atomic stats merge (single patch_stats — Pitfall 6)
      Step 6: Sanity-gate P (D-409)
      Step 7: Auto-suggest P (D-407)
    """
    started = time.perf_counter()
    builder = MatchStatsBuilder()
    builder.set("threshold_p", threshold_p)

    # Step 1: D-411 skip-if-upstream-failed
    status = read_run_status(engine, run_id)
    if status in ("failed", "running") or status is None:
        reason = "failed_upstream" if status == "failed" else "in_progress_upstream"
        builder.set("skipped_reason", reason)
        builder.set("gate_passed", False)
        run_writer.patch_stats(run_id, dict(builder.delta))
        log.warning("match_skipped_failed_run", run_id=run_id, upstream_status=status)
        return MatcherPhaseResult(
            status="skipped", reason=reason, stats_delta=dict(builder.delta),
        )

    # Step 2-3: counts + JOIN+INSERT (D-410 inside build_matches_for_run)
    v_count = compute_comparable_counts(engine, run_id, retailer="viled")
    g_count = compute_comparable_counts(engine, run_id, retailer="goldapple")
    denom = compute_denominator(engine, run_id)
    brand_overlap = compute_brand_overlap(engine, run_id)
    match_count = build_matches_for_run(engine, run_id)

    builder.set("viled_comparable_count", v_count)
    builder.set("goldapple_comparable_count", g_count)
    builder.set("brand_overlap_count", brand_overlap)
    builder.set("denominator", denom)
    builder.set("numerator", match_count)
    builder.set("count", match_count)

    # Step 4: match.rate — guard division by zero per CONTEXT "Claude's Discretion"
    rate = round((match_count * 100.0 / denom), 2) if denom > 0 else 0.0
    builder.set("rate", rate)
    if denom == 0:
        log.warning("match_zero_denominator", run_id=run_id)

    # Step 5: Sanity-gate P
    gate_passed = final_threshold_gate(match_count, threshold_p)
    builder.set("gate_passed", gate_passed)

    # Step 6: Auto-suggest P from prior 4 runs (D-407)
    history = _gather_prior_match_counts(run_writer, run_id, lookback=p_auto_suggest_after_runs)
    suggested = auto_suggest_threshold(
        history,
        factor=p_auto_suggest_factor,
        min_runs=p_auto_suggest_after_runs,
    )
    # ^^^ NOTE: MATCH_STATS_KEYS does NOT include "auto_suggest_p" per CONTEXT D-414
    # — if planner decides operator-Telegram emission needs the value persisted,
    # add it to MATCH_STATS_KEYS and StatsBuilder accordingly. Otherwise emit
    # via structlog only (mirror Phase 3 goldapple-side handles via stats).

    # Step 7: Atomic stats merge (Pitfall 6) — SINGLE patch_stats
    run_writer.patch_stats(run_id, dict(builder.delta))

    if not gate_passed:
        reason = f"match_count_below_threshold:{match_count}<{threshold_p}"
        log.error("match_sanity_gate_failed", run_id=run_id, reason=reason)
        run_writer.fail(run_id, reason)
        return MatcherPhaseResult(
            status="failed", match_count=match_count, reason=reason,
            stats_delta=dict(builder.delta),
        )

    log.info("matcher_phase_complete", run_id=run_id, match_count=match_count, rate=rate)
    return MatcherPhaseResult(
        status="success", match_count=match_count, stats_delta=dict(builder.delta),
    )
```

**`_gather_prior_match_counts` helper** — exact mirror of `viled_run.py:126-145`:
```python
def _gather_prior_match_counts(
    run_writer: RunWriterProtocol, current_run_id: int, *, lookback: int = 4
) -> list[int]:
    """Read match.count from prior runs for D-407 auto-suggest median."""
    counts: list[int] = []
    for prior in range(max(1, current_run_id - lookback), current_run_id):
        try:
            stats = run_writer.get_stats(prior)
        except Exception:  # noqa: BLE001
            continue
        if not stats:
            continue
        c = stats.get("match.count")
        if isinstance(c, int) and c > 0:
            counts.append(c)
    return counts
```

**Key contrast with `viled_run.py`:** Phase 4 takes `engine` directly (not a `SnapshotWriterProtocol`) because the matcher operates on SQL JOIN, not row-by-row append. The protocol-stack pattern (`brand_alias`, `normalizer`, `snapshot_writer`) is irrelevant — matcher doesn't fetch, parse, or normalize. **Only `run_writer` is taken via Protocol** (consistent with `patch_stats` / `fail` / `get_stats` calls).

---

### NEW `tests/unit/test_matcher_strict_key.py`

**Analogs:**
1. **`tests/unit/test_snapshot_writer.py`** (lines 1-83) — in-memory engine fixture; `_record(sku_id, **overrides)` helper for building snapshot dicts; per-test fresh engine via `init_db(tmp_path/...)`
2. **`tests/integration/test_v_current_snapshots.py`** (lines 1-42) — direct SQL execution via `engine.connect().exec_driver_sql(...)` to verify VIEW/JOIN output

**Imports + fixture pattern** (mirror `test_snapshot_writer.py:1-24`):
```python
"""Phase 4 matcher SQL builder + denominator + comparable counts unit tests."""

import pytest
from sqlmodel import Session

from ga_crawler.storage.sqlite import (
    Match,
    Run,
    Snapshot,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)
from ga_crawler.matcher.strict_key import (
    build_matches_for_run,
    compute_denominator,
    compute_comparable_counts,
    compute_brand_overlap,
)


@pytest.fixture
def setup_engine(tmp_path):
    """In-memory-ish engine on disk file (real WAL semantics, fast cleanup)."""
    db = tmp_path / "matcher.db"
    init_db(db)
    engine = make_engine(db)
    with Session(engine) as s:
        s.add(Run(run_id=1, status="running"))
        s.commit()
    return engine


def _viled(sku_id: str, **overrides) -> dict:
    base = dict(
        sku_id=sku_id, url=f"https://viled.kz/{sku_id}", name="Eau de Parfum 50 ml",
        brand="Givenchy", brand_norm="givenchy", name_norm="eau de parfum",
        volume_norm="(50, ml, 1)", multipack_flag=False, current_price=10000,
        currency="KZT", stock_state="IN_STOCK",
    )
    base.update(overrides)
    return base


def _goldapple(sku_id: str, **overrides) -> dict:
    base = _viled(sku_id, url=f"https://goldapple.kz/{sku_id}")
    base["current_price"] = 12000
    base.update(overrides)
    return base
```

**Boundary test pattern** (mirror `test_final_gate.py:43-57` `@pytest.mark.parametrize`):
```python
def test_strict_key_match_happy_path(setup_engine):
    """One viled + one goldapple sharing (brand_norm, name_norm, volume_norm) → 1 match row."""
    writer = SqliteSnapshotWriter(setup_engine, batch_size=10)
    writer.append(1, "viled", [_viled("V1")])
    writer.append(1, "goldapple", [_goldapple("G1")])
    inserted = build_matches_for_run(setup_engine, 1)
    assert inserted == 1
    with setup_engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT viled_sku, goldapple_sku, price_delta FROM matches").fetchall()
    assert rows == [("V1", "G1", 2000)]


def test_idempotent_rerun(setup_engine):
    """D-410: re-running matcher on same run_id produces same rows (DELETE+INSERT in TX)."""
    ...

def test_multipack_excluded_from_numerator(setup_engine):
    """D-402: multipack_flag=1 SKUs do NOT participate in matching."""
    ...

def test_volume_norm_null_excluded(setup_engine):
    """D-402: volume_norm IS NULL → skipped (strict key requires volume)."""
    ...

def test_delisted_excluded(setup_engine):
    """D-402: stock_state='DELISTED' → skipped (stale-by-definition price)."""
    ...

def test_n_to_1_keep_all(setup_engine):
    """D-403: 2 goldapple SKUs with same key as 1 viled → both pairs persisted."""
    ...

def test_denominator_only_in_brand_overlap(setup_engine):
    """D-404: viled SKU in brand NOT present on goldapple → excluded from denominator."""
    ...

def test_denominator_zero_when_no_brand_overlap(setup_engine):
    """Edge case: no shared brands → denominator=0; match.rate=0.0 in orchestrator."""
    ...
```

**Schema regression canary** (per D-405 — formula frozen with week 1 baseline):
```python
def test_match_rate_formula_canary(setup_engine):
    """D-405: formula = matches / viled_skus_in_overlap × 100 with 2-decimal rounding.
    Synthetic fixture pins behavior — any change requires updating this test +
    a v2-migration plan."""
    # Plant 6 viled SKUs in brand-overlap (5 comparable, 1 DELISTED),
    # 3 of which match goldapple → denominator=5, numerator=3, rate=60.00
    ...
```

---

### NEW `tests/unit/test_matcher_stats.py`

**Analog:** `tests/unit/test_viled_stats_builder.py` (lines 1-126) — exact mirror.

**Copy structure verbatim, substitute namespace:**
```python
"""MATCH_STATS_KEYS namespace + MatchStatsBuilder tests.

Mirrors tests/unit/test_viled_stats_builder.py for the match.* side. The three
builders (viled.*, goldapple.*, match.*) share NO keys — Pitfall 6 atomic
merge invariant.
"""

import pytest

from ga_crawler.matcher.stats import (
    MATCH_STATS_KEYS,
    MatchStatsBuilder,
)
from ga_crawler.runner.stats import (
    GOLDAPPLE_STATS_KEYS,
    VILED_STATS_KEYS,
    StatsNamespaceError,
)


def test_match_stats_keys_count():
    """D-414: 10 keys (see CONTEXT lines 121-129)."""
    assert len(MATCH_STATS_KEYS) == 10  # adjust if planner adds keys


def test_all_keys_have_match_prefix():
    for k in MATCH_STATS_KEYS:
        assert k.startswith("match.")


@pytest.mark.parametrize("expected_key", [
    "match.count", "match.rate", "match.numerator", "match.denominator",
    "match.brand_overlap_count", "match.viled_comparable_count",
    "match.goldapple_comparable_count", "match.skipped_reason",
    "match.threshold_p", "match.gate_passed",
])
def test_each_required_key_present(expected_key):
    assert expected_key in MATCH_STATS_KEYS


def test_set_resolves_bare_key():
    b = MatchStatsBuilder()
    b.set("count", 42)
    assert b.delta == {"match.count": 42}


def test_set_namespaced_key_passes():
    b = MatchStatsBuilder()
    b.set("match.rate", 42.31)
    assert b.delta == {"match.rate": 42.31}


def test_set_unknown_key_raises():
    b = MatchStatsBuilder()
    with pytest.raises(StatsNamespaceError):
        b.set("nonsense", 1)


def test_namespaces_three_way_disjoint():
    """Pitfall 6: viled.*, goldapple.*, match.* are mutually disjoint."""
    v, g, m = set(VILED_STATS_KEYS), set(GOLDAPPLE_STATS_KEYS), set(MATCH_STATS_KEYS)
    assert v.isdisjoint(g)
    assert v.isdisjoint(m)
    assert g.isdisjoint(m)
```

---

### NEW `tests/integration/test_matcher_run.py`

**Analogs:**
1. **`tests/integration/test_run_e2e_with_phase2_mocks.py`** (lines 1-444) — orchestrator-level integration with mocked Phase 2 protocols; mock `run_writer.patch_stats.call_args.args[1]` introspection for stats-merge assertions
2. **`tests/integration/test_main_run_e2e.py`** (lines 1-311) — real engine via `setup_repo` fixture; `Session(engine)` + `s.get(Run, result.run_id)` for end-state checks

**Imports + fixture** (mirror `test_main_run_e2e.py:1-67` + `test_run_e2e_with_phase2_mocks.py:1-22`):
```python
"""Phase 4 matcher orchestrator integration — real engine + mock Phase 2 protocols.

Mock-injected `run_writer` keeps the test fast and assertion-friendly via
patch_stats.call_args. Real `engine` is used for the SQL JOIN itself
(can't mock SQL semantics).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlmodel import Session

from ga_crawler.runners.matcher_run import MatcherPhaseResult, run_matcher_phase
from ga_crawler.storage.sqlite import (
    Match,
    Run,
    SqliteRunWriter,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)


@pytest.fixture
def setup_engine_with_run(tmp_path):
    """Real engine + a 'running' run row + Phase 2 SqliteRunWriter."""
    db = tmp_path / "matcher_e2e.db"
    init_db(db)
    engine = make_engine(db)
    run_writer = SqliteRunWriter(engine)
    run_id = run_writer.create()
    # Mark "success" so D-411 skip doesn't trigger
    run_writer.finalize(run_id, status="success")
    return engine, run_writer, run_id
```

**Test list** (mirror `test_run_e2e_with_phase2_mocks.py` happy/fail/idempotent shape):

```python
def test_e2e_happy_path(setup_engine_with_run):
    """Snapshots planted; matcher runs; matches table populated; stats patched."""

def test_e2e_skipped_if_upstream_failed(setup_engine_with_run):
    """D-411: status='failed' → matcher skips, writes match.skipped_reason."""

def test_e2e_skipped_if_upstream_running(setup_engine_with_run):
    """D-411: status='running' → matcher skips (incomplete crawl)."""

def test_e2e_idempotent_rerun(setup_engine_with_run):
    """D-410: re-run matcher_run on same run_id → same matches rows; no duplicates."""

def test_e2e_sanity_gate_fail_persists_matches(setup_engine_with_run):
    """D-409: match_count <= P → run failed, BUT matches rows still in DB (audit-trail
    invariant; mirror D-218 gate-fail-but-snapshot-persists)."""

def test_e2e_atomic_stats_merge_one_call(setup_engine_with_run):
    """Pitfall 6: patch_stats called EXACTLY ONCE on success path
    (mirror test_run_e2e_with_phase2_mocks.py::test_e2e_atomic_stats_merge_one_call)."""

def test_e2e_zero_denominator_edge_case(setup_engine_with_run):
    """Brand-overlap empty → denominator=0; rate=0.0; gate fails on count=0."""

def test_e2e_match_rate_formula_canary(setup_engine_with_run):
    """D-405: KPI formula frozen with week 1. Synthetic fixture pins value.
    Any change to the formula must update this test + STATE.md note."""
```

---

### AMEND `src/ga_crawler/storage/sqlite.py` — add `Match` SQLModel + `init_db` extension

**Analog:** existing `Run` (lines 48-57) and `Snapshot` (lines 60-87) class definitions in the same file.

**Pattern to copy** — the `Snapshot` class declaration (lines 60-87):
```python
class Snapshot(SQLModel, table=True):
    """Append-only snapshot row per (run_id, retailer, sku_id). DATA-01..03."""

    __tablename__ = "snapshots"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.run_id", index=True)
    ...
    __table_args__ = (
        UniqueConstraint("run_id", "retailer", "sku_id", name="uq_snapshot_run_retailer_sku"),
        Index("ix_snapshot_retailer_brand_norm", "retailer", "brand_norm"),
        Index("ix_snapshot_run_retailer", "run_id", "retailer"),
    )
```

**Apply to Phase 4** — D-401 schema verbatim. **Note PK is composite**, not `id: Optional[int]` like Snapshot:
```python
class Match(SQLModel, table=True):
    """Denormalized strict-key matches per run. Phase 4 owns schema (D-401).

    PK is composite (run_id, viled_sku, goldapple_sku) — supports N→1 keep-all
    (D-403). All denormalized columns from snapshots so Phase 5 reporter can
    project directly without JOIN-back.
    """

    __tablename__ = "matches"
    run_id: int = Field(foreign_key="runs.run_id", primary_key=True, index=True)
    viled_sku: str = Field(primary_key=True)
    goldapple_sku: str = Field(primary_key=True)
    brand_norm: str
    name_norm: str
    volume_norm: str
    viled_price: int
    goldapple_price: int
    viled_was_price: Optional[int] = None
    goldapple_was_price: Optional[int] = None
    price_delta: int
    price_delta_pct: float
    matched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_match_run_brand", "run_id", "brand_norm"),
    )
```

**`init_db` extension** — none needed. The existing `init_db` at line 112-130 already calls `SQLModel.metadata.create_all(engine)` which picks up any registered SQLModel table. Per D-415, **no alembic migration**. The matches table is created automatically on first `init_db` call after Phase 4 deploys (idempotent `CREATE TABLE IF NOT EXISTS` semantics).

**Update `__all__`** at the bottom of `sqlite.py` (line 262-269):
```python
__all__ = [
    "Run",
    "Snapshot",
    "Match",                  # NEW
    "SqliteSnapshotWriter",
    "SqliteRunWriter",
    "make_engine",
    "init_db",
]
```

**`test_storage_models.py` extension** — mirror existing pattern (lines 25-39):
```python
def test_match_columns():
    cols = set(Match.model_fields.keys())
    expected = {
        "run_id", "viled_sku", "goldapple_sku",
        "brand_norm", "name_norm", "volume_norm",
        "viled_price", "goldapple_price",
        "viled_was_price", "goldapple_was_price",
        "price_delta", "price_delta_pct", "matched_at",
    }
    assert expected.issubset(cols)


def test_match_composite_pk(engine):
    """D-403 N→1 keep-all: PK is (run_id, viled_sku, goldapple_sku). 
    Two rows with same run_id+viled_sku but different goldapple_sku are allowed."""
    ...
```

---

### AMEND `src/ga_crawler/runners/main_run.py` — insert matcher step after goldapple

**Analog:** existing viled→goldapple composition in same file (lines 154-238).

**Pattern to copy** — the goldapple phase block at lines 184-231:
```python
# ---- Goldapple phase ----
if not viled_only:
    from ga_crawler.runners.goldapple_run import run_goldapple_phase
    ...
    g_result = asyncio.run(run_goldapple_phase(...))
    goldapple_count = g_result.goldapple_count
    stats_delta_acc.update(g_result.stats_delta)
    ...
    if g_result.status == "failed":
        norm06_path = Norm06Writer(repo_root).persist(...)
        ...
        return MainRunResult(status="failed", ...)
```

**Apply to Phase 4** — insert AFTER the goldapple block (line ~232), BEFORE Norm06 persist (line 234). Per D-411, matcher skips itself if either crawl failed, so no extra guard is needed at the composition layer — `run_matcher_phase` reads `runs.status` and short-circuits.

```python
# ---- Matcher phase (Phase 4 — D-411 skip-if-failed handled inside) ----
if not viled_only and not goldapple_only:
    from ga_crawler.runners.matcher_run import run_matcher_phase

    m_result = run_matcher_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        threshold_p=sanity_gate_p or _load_match_p_from_pyproject(pyproject_path),
    )
    stats_delta_acc.update(m_result.stats_delta)
    if m_result.status == "failed":
        # Gate-trip: matches rows persisted (audit invariant), but run.status='failed'.
        # Norm06 ledger still gets written below for the audit artifact.
        norm06_path = Norm06Writer(repo_root).persist(
            run_id, viled_unmatched, goldapple_new_slugs
        )
        log.error("weekly_run_matcher_failed", run_id=run_id, reason=m_result.reason)
        return MainRunResult(
            status="failed",
            run_id=run_id,
            viled_count=viled_count,
            goldapple_count=goldapple_count,
            reason=m_result.reason,
            norm06_path=norm06_path,
            stats_delta=dict(stats_delta_acc),
        )
    # status == "skipped" or "success" → continue to Norm06 + finalize
```

**Update `run_weekly` signature** — add `sanity_gate_p: Optional[int] = None` to function params (mirror existing `sanity_gate_m` flow). Add `_load_match_p_from_pyproject` helper modeled on `ViledConfig.from_pyproject` reading `[tool.ga_crawler.match]`.

**Update `MainRunResult` dataclass** (line 56-65) — add `match_count: int = 0`:
```python
@dataclass
class MainRunResult:
    status: str
    run_id: int
    viled_count: int = 0
    goldapple_count: int = 0
    match_count: int = 0          # NEW
    ...
```

---

### AMEND `src/ga_crawler/cli.py` — add `matcher-run --run-id N` subcommand

**Analog:** existing `goldapple-smoke` (lines 41-46) and `weekly-run` (lines 49-78) handlers + argparse subcommand registration (lines 104-153).

**Pattern to copy** — `_cmd_weekly` handler (lines 49-78):
```python
def _cmd_weekly(args) -> int:
    from ga_crawler.runners.main_run import run_weekly
    repo_root = Path(args.repo_root).resolve()
    result = run_weekly(
        repo_root=repo_root,
        db_path=args.db_path,
        ...
    )
    print(json.dumps({...}, ensure_ascii=False, indent=2))
    return 0 if result.status == "success" else 2
```

**Apply to Phase 4 — D-412 `matcher-run --run-id N`** (standalone recovery tool, idempotent re-run on existing snapshots):
```python
def _cmd_matcher(args) -> int:
    """D-412: standalone matcher re-run for recovery (no re-crawl)."""
    from ga_crawler.runners.matcher_run import run_matcher_phase
    from ga_crawler.storage.sqlite import SqliteRunWriter, init_db, make_engine

    init_db(args.db_path)
    engine = make_engine(args.db_path)
    run_writer = SqliteRunWriter(engine)

    result = run_matcher_phase(
        run_id=args.run_id,
        engine=engine,
        run_writer=run_writer,
        threshold_p=args.sanity_gate_p or 20,  # CONTEXT D-408 seed
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "match_count": result.match_count,
                "reason": result.reason,
                "stats_delta_keys": sorted(result.stats_delta.keys()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status == "success" else 2
```

**Argparse registration pattern** (mirror lines 112-153 `weekly` subparser):
```python
# ADDED Plan 04 — matcher-run (D-412)
matcher = sub.add_parser(
    "matcher-run",
    help="Run strict-key matcher on existing snapshots for a given run_id (idempotent, D-412)",
)
matcher.add_argument("--run-id", type=int, required=True)
matcher.add_argument("--db-path", default="prices.db")
matcher.add_argument(
    "--sanity-gate-p",
    type=int,
    default=None,
    help="Override match-count sanity threshold P (default: pyproject.toml [tool.ga_crawler.match].sanity_gate_p = 20)",
)
```

And in `main()`:
```python
if args.cmd == "matcher-run":
    return _cmd_matcher(args)
```

---

### AMEND `pyproject.toml` — add `[tool.ga_crawler.match]` namespace

**Analog:** existing `[tool.ga_crawler.crawl.viled]` (lines 77-90) and `[tool.ga_crawler.crawl.goldapple]` (lines 50-69) sections.

**Pattern to copy:**
```toml
[tool.ga_crawler.crawl.viled]
sanity_gate_n = 100
pause_seconds = 2.0
...
n_auto_suggest_factor = 0.7
n_auto_suggest_after_runs = 4
```

**Apply to Phase 4** — D-408:
```toml
[tool.ga_crawler.match]
# Phase 4 operational constants. Type-locked; operator edits via git PR.
# Source anchors: 04-CONTEXT.md (D-406..D-415).
sanity_gate_p = 20                            # D-406/D-408 seed; auto-suggest from week 5
p_auto_suggest_factor = 0.7                   # D-407 mirror D-203/D-310: 0.7 × 4-week-median
p_auto_suggest_after_runs = 4                 # D-407 mirror D-203/D-310: needs 4+ history rows
```

**Optional `MatchConfig` dataclass loader** — mirror `src/ga_crawler/config.py::ViledConfig` (1:1 mirror at `src/ga_crawler/matcher/config.py` OR inline in `matcher_run.py`). Per CONTEXT D-413 the file is not listed as a new module — planner decides between inline config-loading vs separate `matcher/config.py` module. **Recommend separate `MatchConfig` mirroring `ViledConfig` for consistency** — pyproject namespace reader is a 30-line pattern that earns its own module.

---

## Shared Patterns

### Pattern: Stats namespace builder (`*StatsBuilder`)

**Source:** `src/ga_crawler/runner/stats.py:160-209` (`ViledStatsBuilder`)

**Apply to:** `MatchStatsBuilder` in `matcher/stats.py`. D-414 explicit mirror.

**Code shape (verbatim minus prefix):**
```python
class XxxStatsBuilder:
    def __init__(self) -> None:
        self.delta: dict[str, Any] = {}

    def _resolve(self, bare_key: str) -> str:
        if bare_key in _XXX_BARE_TO_NAMESPACED:
            return _XXX_BARE_TO_NAMESPACED[bare_key]
        if bare_key in XXX_STATS_KEYS:
            return bare_key
        raise StatsNamespaceError(
            f"key {bare_key!r} not in XXX_STATS_KEYS; "
            f"allowed: {sorted(XXX_STATS_KEYS)}"
        )

    def set(self, bare_key: str, value: Any) -> None:
        full = self._resolve(bare_key)
        self.delta[full] = value

    def inc(self, bare_key: str, n: int = 1) -> None:
        full = self._resolve(bare_key)
        self.delta[full] = self.delta.get(full, 0) + n
```

### Pattern: Atomic single-call `patch_stats` at end of phase (Pitfall 6)

**Source:** `src/ga_crawler/runners/viled_run.py:312-313`:
```python
# Step 8: Atomic stats merge (Pitfall 6) — SINGLE patch_stats on success path.
run_writer.patch_stats(run_id, dict(builder.delta))
```

**Apply to:** `runners/matcher_run.py` final step. NEVER call `patch_stats` more than once per phase — Pitfall 6 RFC-7396 merge contract.

### Pattern: Gate-fail-but-data-persists (audit-trail invariant)

**Source:** `src/ga_crawler/runners/viled_run.py:298-310` (sanity-gate-N fails AFTER snapshot writes already happened):
```python
if not sanity_pass:
    reason = (
        f"sanity_gate_n_failed: viled_count {inserted} < N={config.sanity_gate_n}"
    )
    log.error("viled_sanity_gate_failed", run_id=run_id, reason=reason)
    run_writer.fail(run_id, reason)
    run_writer.patch_stats(run_id, dict(builder.delta))
    return ViledPhaseResult(status="failed", ...)
```

**Apply to:** `matcher_run.py` Step 6 (sanity-gate P trip). D-409 explicit: "matches rows всё равно остаются в БД (audit-trail invariant — mirror DATA-03 immutable + D-218 gate-fail-but-snapshot-persists)."

### Pattern: Raw SQL with bind params + structured logger

**Source:** `src/ga_crawler/runners/main_run.py:68-83` (`_derive_viled_brands_from_snapshots`) and `src/ga_crawler/storage/sqlite.py:203-222` (`patch_stats`).

**Apply to:** All `matcher/strict_key.py` query helpers. Always use `text("... :rid ...")` + `params={"rid": run_id}` (never f-string SQL).

### Pattern: Mock `run_writer.patch_stats.call_args.args[1]` for stats-assertion

**Source:** `tests/integration/test_run_e2e_with_phase2_mocks.py:159-162`:
```python
mock_run_writer.patch_stats.assert_called_once()
delta = mock_run_writer.patch_stats.call_args.args[1]
assert delta["goldapple.fetch_count"] >= 2
assert delta["goldapple.smoke_pass"] is True
```

**Apply to:** `test_matcher_run.py` orchestrator tests — use the existing `mock_run_writer` fixture from `tests/conftest.py:124-139` (it accumulates patch_stats deltas into `_stats` and exposes via `call_args`).

---

## No Analog Found

None. Every Phase 4 file maps to an existing analog with role-match or exact-match quality. The only genuinely-novel surface is the SQL JOIN/INSERT statement itself (no prior derived-table writer exists), but its shape is fully constrained by CONTEXT D-401 + D-402 — no design freedom remains for the planner there.

---

## Metadata

**Analog search scope:**
- `src/ga_crawler/storage/` (sqlite.py, norm06_writer.py)
- `src/ga_crawler/runner/` (gates.py, stats.py)
- `src/ga_crawler/runners/` (viled_run.py, goldapple_run.py, main_run.py)
- `src/ga_crawler/cli.py`
- `src/ga_crawler/config.py`
- `tests/unit/` (focus: test_*_stats_builder, test_*_gate, test_snapshot_writer, test_storage_models, test_run_writer)
- `tests/integration/` (focus: test_main_run_e2e, test_run_e2e_with_phase2_mocks, test_run_writer_lifecycle, test_v_current_snapshots)
- `pyproject.toml`

**Files read (no duplicates):**
1. `.planning/phases/04-matcher-match-rate-kpi/04-CONTEXT.md` (D-401..D-415, 261 lines)
2. `.planning/REQUIREMENTS.md` (MATCH-01..04, full file)
3. `.planning/ROADMAP.md` (Phase 4 section, full file)
4. `src/ga_crawler/storage/sqlite.py` (270 lines — full read for Match table analog + patch_stats pattern)
5. `src/ga_crawler/runner/gates.py` (319 lines — full read for final_threshold_gate + auto_suggest_threshold reuse)
6. `src/ga_crawler/runner/stats.py` (220 lines — full read for ViledStatsBuilder mirror)
7. `src/ga_crawler/runners/goldapple_run.py` (343 lines — orchestrator analog)
8. `src/ga_crawler/runners/viled_run.py` (329 lines — sync orchestrator analog, PRIMARY model for matcher_run.py)
9. `src/ga_crawler/runners/main_run.py` (295 lines — composition + DATA-05 lifecycle)
10. `src/ga_crawler/cli.py` (166 lines — subcommand registration pattern)
11. `src/ga_crawler/config.py` (73 lines — pyproject loader pattern)
12. `src/ga_crawler/storage/norm06_writer.py` (86 lines — file-I/O writer pattern, not directly applicable but read for completeness)
13. `tests/conftest.py` (267 lines — mock_run_writer fixture)
14. `tests/unit/test_stats_namespace.py` (136 lines — GoldappleStatsBuilder tests)
15. `tests/unit/test_viled_stats_builder.py` (126 lines — ViledStatsBuilder tests, PRIMARY model for test_matcher_stats.py)
16. `tests/unit/test_run_writer.py` (83 lines — RunWriter atomic merge tests)
17. `tests/unit/test_storage_models.py` (61 lines — SQLModel table tests)
18. `tests/unit/test_snapshot_writer.py` (83 lines — append-only writer tests)
19. `tests/unit/test_final_gate.py` (57 lines — boundary test pattern)
20. `tests/unit/test_sanity_n_gate.py` (87 lines — boundary test pattern with @parametrize)
21. `tests/unit/test_auto_suggest_threshold.py` (74 lines — auto-suggest test pattern)
22. `tests/integration/test_main_run_e2e.py` (311 lines — real-engine e2e setup, PRIMARY model)
23. `tests/integration/test_run_e2e_with_phase2_mocks.py` (444 lines — orchestrator mock-injection, PRIMARY model)
24. `tests/integration/test_run_writer_lifecycle.py` (35 lines — multi-phase stats merge integration)
25. `tests/integration/test_v_current_snapshots.py` (42 lines — direct SQL execution against engine)
26. `pyproject.toml` (90 lines — tool namespace pattern)

**Pattern extraction date:** 2026-05-11
