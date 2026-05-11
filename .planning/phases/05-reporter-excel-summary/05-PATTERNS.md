# Phase 5: Reporter (Excel + summary) - Pattern Map

**Mapped:** 2026-05-11
**Files analyzed:** 14 (8 new src + 1 modified src + 1 modified cli + 1 modified pyproject + 10 new tests + 1 modified conftest)
**Analogs found:** 14 / 14 (every Phase 5 file has a load-bearing Phase 2/3/4 analog)

Phase 5 is a "derivation phase that mirrors Phase 4 with a different output." Every architectural primitive already ships:
`MatchConfig.from_pyproject` -> `ReportConfig.from_pyproject`,
`MatchStatsBuilder("match.*")` -> `ReportStatsBuilder("report.*")`,
`run_matcher_phase` 7-step shape -> `run_reporter_phase` 7-step shape,
`matcher-run` argparse subcommand -> `report-run` argparse subcommand,
`runner.gates.read_run_status` skip-protocol -> reused verbatim (D-507 mirrors D-411).

Two patterns are new to Phase 5 (no analog in the codebase):
1. **xlsx multi-sheet build via pandas + xlsxwriter** (`excel_builder.py`) — pure-stdlib + locked stack; planner uses RESEARCH.md Patterns 1-5 verbatim.
2. **ISO-week filename + atomic write** (`archive.py`) — closest analog is `storage/norm06_writer.py` for file-on-disk-write-per-run pattern; atomic rename via `os.replace` is new.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/ga_crawler/reporter/__init__.py` | package marker | n/a | `src/ga_crawler/matcher/__init__.py` | exact |
| `src/ga_crawler/reporter/config.py` | config | file-I/O (tomllib read) | `src/ga_crawler/matcher/config.py` | exact |
| `src/ga_crawler/reporter/stats.py` | stats builder | transform (in-memory dict accumulation) | `src/ga_crawler/matcher/stats.py` | exact |
| `src/ga_crawler/reporter/excel_builder.py` | builder (pure) | transform (DataFrame -> xlsx bytes) | none — new pattern (RESEARCH.md Patterns 1-5); secondary analog `src/ga_crawler/matcher/strict_key.py` for module-level constants pattern | role-match only |
| `src/ga_crawler/reporter/summary_builder.py` | builder (pure) | transform (dict + rows -> str) | `src/ga_crawler/runner/stats.py::compute_norm06_forward` (pure transform helper outside class) + new template constants | partial |
| `src/ga_crawler/reporter/queries.py` | SQL primitives | request-response (read-only SELECT) | `src/ga_crawler/matcher/strict_key.py` | exact (SQL-constants + thin engine.connect() wrappers) |
| `src/ga_crawler/reporter/archive.py` | filesystem service | file-I/O (atomic write + stat) | `src/ga_crawler/storage/norm06_writer.py` (file-per-run write pattern) | role-match |
| `src/ga_crawler/runners/reporter_run.py` | orchestrator | request-response (sync 7-step) | `src/ga_crawler/runners/matcher_run.py` | exact |
| `src/ga_crawler/runners/main_run.py` | orchestrator (AMEND) | composition | itself, prior diff that inserted `run_matcher_phase` between goldapple and final finalize (see lines 244-302) | exact (same insertion shape) |
| `src/ga_crawler/cli.py` | controller (AMEND) | request-response (argparse) | `_cmd_matcher` + `matcher-run` subparser in same file | exact |
| `pyproject.toml` | config (AMEND) | n/a | existing `[tool.ga_crawler.match]` block (lines 91-96) | exact |
| `tests/unit/test_report_config.py` | test | n/a | `tests/unit/test_match_config.py` | exact |
| `tests/unit/test_report_stats.py` | test | n/a | `tests/unit/test_matcher_stats.py` | exact |
| `tests/unit/test_excel_builder.py` | test | n/a | `tests/unit/test_matcher_strict_key.py` (source-locked + on-disk fixtures) | role-match |
| `tests/unit/test_summary_builder.py` | test | n/a | `tests/unit/test_matcher_stats.py` (parametrize + source-lock pattern) | partial — template golden-string is new |
| `tests/unit/test_archive_iso_week.py` | test | n/a | `tests/unit/test_matcher_strict_key.py` (pure-function + parametrize) | partial |
| `tests/unit/test_archive_atomic_write.py` | test | n/a | `tests/unit/test_norm06_writer.py` (tmp_path + file-on-disk assert) | role-match |
| `tests/integration/test_archive_size_guard.py` | test | n/a | `tests/integration/test_matcher_run.py` (tmp_path engine + synthetic data) | role-match |
| `tests/integration/test_reporter_run.py` | test | n/a | `tests/integration/test_matcher_run.py` | exact |
| `tests/integration/test_main_run_with_reporter.py` | test | n/a | `tests/integration/test_main_run_e2e.py` | exact (extends, doesn't replace) |
| `tests/integration/test_cli_report_subcommand.py` | test | n/a | `tests/integration/test_cli_matcher_subcommand.py` | exact |
| `tests/conftest.py` | fixtures (AMEND) | n/a | existing Phase 2 fixtures section (lines 153-267) — append-only block per D-222 pattern | exact |

---

## Pattern Assignments

### `src/ga_crawler/reporter/__init__.py` (package marker)

**Analog:** `src/ga_crawler/matcher/__init__.py` (1 line)

**Excerpt (`src/ga_crawler/matcher/__init__.py:1`):**
```python
"""Strict-key matcher (Phase 4): SQL JOIN builder, denominator query, stats namespace."""
```

**Diffs for Phase 5:** Replace string with Phase 5 description, e.g.:
```python
"""Reporter (Phase 5): multi-sheet xlsx builder + Telegram-ready summary + archive."""
```

---

### `src/ga_crawler/reporter/config.py` (config, file-I/O)

**Analog:** `src/ga_crawler/matcher/config.py`

**Imports + docstring header pattern (`src/ga_crawler/matcher/config.py:1-15`):**
```python
"""Phase 4 matcher config loader.

Single source of truth for runtime constants pulled from pyproject.toml's
`[tool.ga_crawler.match]` namespace. Operator edits TOML; CLI overrides in
`cli.py::_cmd_matcher` (Plan 04-05).

Source: 04-CONTEXT.md D-406..D-408, D-413; 04-PATTERNS.md §"AMEND pyproject.toml".
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
```

**Frozen dataclass + defaults pattern (`src/ga_crawler/matcher/config.py:17-28`):**
```python
@dataclass(frozen=True)
class MatchConfig:
    """Operator-tunable runtime constants for the matcher.

    Defaults mirror `[tool.ga_crawler.match]` in pyproject.toml so that
    constructing `MatchConfig()` directly (e.g. in tests) yields the same
    values as `MatchConfig.from_pyproject()` against the production toml.
    """

    sanity_gate_p: int = 20
    p_auto_suggest_factor: float = 0.7
    p_auto_suggest_after_runs: int = 4
```

**from_pyproject loader pattern (`src/ga_crawler/matcher/config.py:30-54`):**
```python
@classmethod
def from_pyproject(cls, pyproject_path: Path | str = "pyproject.toml") -> "MatchConfig":
    """Read [tool.ga_crawler.match] from the given pyproject.toml.

    Missing keys (or a missing file) fall back to the dataclass defaults.
    """
    path = Path(pyproject_path)
    if not path.exists():
        return cls()
    with path.open("rb") as f:
        data = tomllib.load(f)
    match = (
        data.get("tool", {})
        .get("ga_crawler", {})
        .get("match", {})
    )
    return cls(
        sanity_gate_p=int(match.get("sanity_gate_p", cls.sanity_gate_p)),
        p_auto_suggest_factor=float(
            match.get("p_auto_suggest_factor", cls.p_auto_suggest_factor)
        ),
        p_auto_suggest_after_runs=int(
            match.get("p_auto_suggest_after_runs", cls.p_auto_suggest_after_runs)
        ),
    )
```

**Diffs for Phase 5 (`ReportConfig`):**
- Class name: `MatchConfig` -> `ReportConfig`
- Docstring source anchors: `04-CONTEXT.md D-406..D-408` -> `05-CONTEXT.md D-509, D-510, D-512, D-515, D-516`
- TOML namespace path: `data.get("tool").get("ga_crawler").get("match")` -> `... .get("report")`
- Default fields (per D-516):
  ```python
  output_dir: str = "reports"
  size_limit_mb: int = 45
  top_n_deltas: int = 3
  timezone: str = "Asia/Almaty"
  ```
- The `from_pyproject` body reads each key with its type cast (`str` for `output_dir`/`timezone`, `int` for `size_limit_mb`/`top_n_deltas`).

---

### `src/ga_crawler/reporter/stats.py` (stats builder, transform)

**Analog:** `src/ga_crawler/matcher/stats.py`

**KEYS tuple constant pattern (`src/ga_crawler/matcher/stats.py:21-32`):**
```python
# 10 match.* keys, frozen with the week-1 baseline (D-405 KPI formula freeze).
# Any new key must be added here AND the regression test in
# tests/unit/test_matcher_stats.py::test_match_stats_keys_count must be updated.
MATCH_STATS_KEYS: tuple[str, ...] = (
    "match.count",                       # int — numerator
    "match.rate",                        # REAL — percent points, 2 decimals
    "match.numerator",                   # int
    "match.denominator",                 # int
    "match.brand_overlap_count",         # int
    "match.viled_comparable_count",      # int
    "match.goldapple_comparable_count",  # int
    "match.skipped_reason",              # str — "" sentinel for the non-skipped path (Pitfall 4)
    "match.threshold_p",                 # int
    "match.gate_passed",                 # bool
)
```

**Bare-to-namespaced mapping + builder class pattern (`src/ga_crawler/matcher/stats.py:36-91`):**
```python
_MATCH_BARE_TO_NAMESPACED: dict[str, str] = {
    k.split(".", 1)[1]: k for k in MATCH_STATS_KEYS
}


class MatchStatsBuilder:
    """Mirror of ViledStatsBuilder / GoldappleStatsBuilder — match.* namespace."""

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

    def set(self, bare_key: str, value: Any) -> None:
        full = self._resolve(bare_key)
        self.delta[full] = value

    def inc(self, bare_key: str, n: int = 1) -> None:
        full = self._resolve(bare_key)
        self.delta[full] = self.delta.get(full, 0) + n

    def get(self, bare_key: str, default: Any = None) -> Any:
        try:
            full = self._resolve(bare_key)
        except StatsNamespaceError:
            return default
        return self.delta.get(full, default)

    def keys(self) -> Iterable[str]:
        return self.delta.keys()

    def __len__(self) -> int:
        return len(self.delta)
```

**Cross-namespace error reuse (`src/ga_crawler/matcher/stats.py:16`):**
```python
from ga_crawler.runner.stats import StatsNamespaceError
```

**Diffs for Phase 5 (`ReportStatsBuilder`):**
- Class name: `MatchStatsBuilder` -> `ReportStatsBuilder`
- Constant name: `MATCH_STATS_KEYS` -> `REPORT_STATS_KEYS`
- Map dict name: `_MATCH_BARE_TO_NAMESPACED` -> `_REPORT_BARE_TO_NAMESPACED`
- 7 keys per D-514 (vs 10 for match):
  ```python
  REPORT_STATS_KEYS: tuple[str, ...] = (
      "report.xlsx_path",          # str, relative path from repo_root
      "report.xlsx_size_bytes",    # int
      "report.summary_text",       # str, multi-line emoji caption (D-504)
      "report.sheet_row_counts",   # dict[str, int] — JSON-serializable
      "report.skipped_reason",     # str — "" sentinel for non-skip path (Pitfall 4)
      "report.size_guard_passed",  # bool — D-515 flag
      "report.generated_at",       # str — ISO 8601 UTC
  )
  ```
- Reject cross-namespace pollution: same `StatsNamespaceError` from `runner/stats.py` — reused, not re-defined. Disjointness test in `test_report_stats.py` extends the three-way invariant to a four-way invariant (`report.*` disjoint from `viled.*` / `goldapple.*` / `match.*`).
- The `report.sheet_row_counts` key is a dict — builder accepts it (`Any` value type); Pitfall 4 (None) still applies; planner verifies dict values serialize through `SqliteRunWriter.patch_stats`'s `json.dumps(delta, ensure_ascii=False, default=str)` (storage/sqlite.py:242).

---

### `src/ga_crawler/reporter/queries.py` (SQL primitives, request-response)

**Analog:** `src/ga_crawler/matcher/strict_key.py`

**Module-level SQL constants pattern (`src/ga_crawler/matcher/strict_key.py:49-142`):**
```python
INSERT_MATCHES_SQL = text(
    """
    INSERT INTO matches (...)
    SELECT ... FROM snapshots v JOIN snapshots g ON ...
    WHERE v.retailer='viled' AND v.run_id=:rid AND ...
    """
)

DENOMINATOR_SQL = text(
    """
    SELECT COUNT(*) FROM snapshots v
    WHERE v.retailer='viled' AND v.run_id=:rid AND ...
    """
)

# ...

RUN_STATUS_SQL = text("SELECT status FROM runs WHERE run_id = :rid")
```

**Thin engine.connect() wrapper pattern (`src/ga_crawler/matcher/strict_key.py:166-207`):**
```python
def compute_denominator(engine, run_id: int) -> int:
    """D-404 denominator: comparable viled SKUs in brand-overlap with goldapple."""
    with engine.connect() as conn:
        row = conn.execute(DENOMINATOR_SQL, {"rid": run_id}).first()
    return int(row[0]) if row else 0


def read_run_status(engine, run_id: int) -> Optional[str]:
    """D-411 input: returns the literal status column value or ``None``."""
    with engine.connect() as conn:
        row = conn.execute(RUN_STATUS_SQL, {"rid": run_id}).first()
    return row[0] if row else None
```

**Diffs for Phase 5:**
- Module purpose: D-405 frozen JOIN-INSERT primitives -> D-501/D-502/Goldapple-promos read-only SELECTs.
- Reused (NOT redefined): `read_run_status` is imported FROM `matcher.strict_key` — Phase 5 inherits D-411 helper verbatim per D-507 mirror (CONTEXT canonical_refs line 202: "runners/matcher_run.read_run_status(engine, run_id) — D-411 helper, переиспользуется в runners/reporter_run.py для D-507 status-gate").
- New SQL constants (RESEARCH.md Patterns 7 + sheet queries lines 506-523):
  ```python
  TOP_N_DELTAS_SQL = text(
      """
      SELECT brand_norm, name_norm, volume_norm, price_delta_pct
      FROM matches
      WHERE run_id = :rid
      ORDER BY ABS(price_delta_pct) DESC
      LIMIT :n
      """
  )

  PER_SKU_DELTAS_SQL = text(
      """
      SELECT brand_norm, name_norm, volume_norm,
             viled_price, viled_was_price,
             goldapple_price, goldapple_was_price,
             price_delta, price_delta_pct
      FROM matches
      WHERE run_id = :rid
      ORDER BY ABS(price_delta_pct) DESC
      """
  )

  ASSORTMENT_GAPS_SQL = text(
      """
      SELECT brand_norm, name_norm, volume_norm, current_price, was_price, url
      FROM snapshots
      WHERE retailer='goldapple' AND run_id=:rid
        AND multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED'
        AND (brand_norm, name_norm, volume_norm) NOT IN (
            SELECT brand_norm, name_norm, volume_norm FROM matches WHERE run_id=:rid
        )
      """
  )

  GOLDAPPLE_PROMOS_SQL = text(
      """
      SELECT brand_norm, name_norm, volume_norm, current_price, was_price, url,
             (was_price - current_price) AS discount_amount,
             ROUND((was_price - current_price) * 100.0 / was_price, 2) AS discount_pct
      FROM snapshots
      WHERE retailer='goldapple' AND run_id=:rid
        AND was_price IS NOT NULL AND was_price > current_price
        AND multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED'
      ORDER BY discount_pct DESC
      """
  )
  ```
- T-04-03-01 (SQL injection via bind params) inherits verbatim — every SQL uses `text("... :rid ...")` + `{"rid": run_id}`. No f-string interpolation reaches SQL.
- Each reader returns a `list[dict]` (or `pd.DataFrame` if planner chooses `pd.read_sql_query(text(...), engine, params=...)`); RESEARCH.md Pattern 7 line 522 uses `dict(zip([...], r))`. Planner picks one form consistently.

---

### `src/ga_crawler/reporter/summary_builder.py` (builder, pure transform)

**Analog:** No exact analog — closest is `src/ga_crawler/runner/stats.py::compute_norm06_forward` (pure transform helper outside class) + new template-constants pattern. Template-constants pattern itself has D-405 KPI formula freeze precedent (constants live in code, not config).

**Pure-function helper outside class pattern (`src/ga_crawler/runner/stats.py:111-137`):**
```python
def compute_norm06_forward(
    viled_brands: list[str],
    aliases: dict[str, list[str]],
    brand_bucket: dict[str, list[str]],
) -> tuple[list[str], int, list[str]]:
    """Wraps intersect_brand_pool for D-306 NORM-06 forward direction.
    ...
    Returns:
      (matched_urls, unmatched_count, unmatched_brands_list)
    """
    from ga_crawler.enumeration.slug import intersect_brand_pool
    matched, unmatched = intersect_brand_pool(viled_brands, aliases, brand_bucket)
    return matched, len(unmatched), unmatched
```

**Template-constants source-lock pattern (RESEARCH.md Pattern 6 lines 449-498) is new but mandated by D-504 + D-405 precedent:**
```python
# src/ga_crawler/reporter/summary_builder.py
SUMMARY_TEMPLATE = """\
📊 Неделя {iso_week} — viled vs goldapple

📦 viled: {viled_count} SKU  •  goldapple: {goldapple_count} SKU
🎯 Совпало: {match_count} ({match_rate}%)
🆕 Гэпы: {gaps_count} SKU у goldapple без viled-пары
💸 Промо у goldapple: {promo_count} SKU
"""

TOP3_HEADER = "\n🔝 Топ-3 дельты (viled vs goldapple):"
TOP3_LINE = " {n}. {brand} {name} {volume}: {delta_pct}%"


def build_summary(
    stats: dict,
    top3: list[dict],
    gaps_count: int,
    promo_count: int,
    iso_week: str,
) -> str:
    """D-504 canonical template — week-1 baseline locked.

    Reads `runs.stats.match.*` directly (D-414); does NOT recompute KPI (D-405).
    """
    viled_count = stats.get("viled.fetch_count", 0)
    goldapple_count = stats.get("goldapple.fetch_count", 0)
    match_count = stats.get("match.count", 0)
    match_rate = stats.get("match.rate", 0.0)

    body = SUMMARY_TEMPLATE.format(
        iso_week=iso_week,
        viled_count=viled_count,
        goldapple_count=goldapple_count,
        match_count=match_count,
        match_rate=match_rate,
        gaps_count=gaps_count,
        promo_count=promo_count,
    )

    # D-504: omit Top-3 header entirely if match_count == 0
    if match_count > 0 and top3:
        body += TOP3_HEADER + "\n"
        for n, row in enumerate(top3[:3], start=1):
            body += TOP3_LINE.format(
                n=n,
                brand=row["brand_norm"],
                name=row["name_norm"],
                volume=row["volume_norm"],
                delta_pct=row["price_delta_pct"],
            ) + "\n"
    return body
```

**Diffs from analog:**
- Pure function (no class) — same shape as `compute_norm06_forward`.
- Module-level template constants — new for Phase 5 but Phase 4's `INSERT_MATCHES_SQL` text constant is the precedent (`src/ga_crawler/matcher/strict_key.py:58`).
- Test (`tests/unit/test_summary_builder.py`) source-locks the template via substring asserts mirror `test_match_rate_formula_canary` style (substring in module-level `text(...)` string).

---

### `src/ga_crawler/reporter/excel_builder.py` (builder, transform)

**Analog:** No close codebase analog — this is the one genuinely new pattern. Closest secondary analog for **module-level constants** is `src/ga_crawler/matcher/strict_key.py:49-142` (SQL constants as module-level frozen dicts/text).

**Russian header dict constants pattern (source: RESEARCH.md Pattern 4 lines 374-407):**
```python
# src/ga_crawler/reporter/excel_builder.py — D-503 source-locked headers

PER_SKU_HEADERS_RU: dict[str, str] = {
    "brand_norm": "Бренд",
    "name_norm": "Название",
    "volume_norm": "Объём",
    "viled_price": "Цена viled, ₸",
    "viled_was_price": "Старая цена viled, ₸",
    "goldapple_price": "Цена goldapple, ₸",
    "goldapple_was_price": "Старая цена goldapple, ₸",
    "price_delta": "Дельта, ₸",
    "price_delta_pct": "Дельта, %",
}

GAPS_HEADERS_RU: dict[str, str] = {
    "brand_norm": "Бренд",
    "name_norm": "Название",
    "volume_norm": "Объём",
    "current_price": "Цена goldapple, ₸",
    "was_price": "Старая цена goldapple, ₸",
    "url": "URL goldapple",
}

PROMOS_HEADERS_RU: dict[str, str] = {
    "brand_norm": "Бренд",
    "name_norm": "Название",
    "volume_norm": "Объём",
    "current_price": "Цена goldapple, ₸",
    "was_price": "Старая цена goldapple, ₸",
    "discount_amount": "Скидка, ₸",
    "discount_pct": "Скидка, %",
    "url": "URL goldapple",
}
```

**Multi-sheet ExcelWriter build pattern (source: RESEARCH.md Pattern 1 lines 244-284):**
```python
import io
import pandas as pd


def build_workbook(
    matches_df: pd.DataFrame,
    gaps_df: pd.DataFrame,
    promos_df: pd.DataFrame,
    summary_text: str,
) -> bytes:
    """Build the 4-sheet xlsx workbook (D-506: always 4 sheets, even when empty)."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:  # Pitfall 1: engine= explicit
        # Sheet 1: Summary (cell A1 text via write_string)
        pd.DataFrame().to_excel(writer, sheet_name="Summary", index=False, header=False)
        workbook = writer.book
        writer.sheets["Summary"].write_string(0, 0, summary_text)

        # Sheet 2: Per-SKU deltas (CF on Дельта, %)
        matches_ru = matches_df.rename(columns=PER_SKU_HEADERS_RU)
        matches_ru.to_excel(writer, sheet_name="Per-SKU deltas", index=False)
        _apply_sheet_chrome(writer.sheets["Per-SKU deltas"], workbook, matches_ru,
                            conditional_col="Дельта, %")

        # Sheet 3: Assortment gaps (no CF per D-508)
        gaps_ru = gaps_df.rename(columns=GAPS_HEADERS_RU)
        gaps_ru.to_excel(writer, sheet_name="Assortment gaps", index=False)
        _apply_sheet_chrome(writer.sheets["Assortment gaps"], workbook, gaps_ru)

        # Sheet 4: Goldapple promos (CF on Скидка, %)
        promos_ru = promos_df.rename(columns=PROMOS_HEADERS_RU)
        promos_ru.to_excel(writer, sheet_name="Goldapple promos", index=False)
        _apply_sheet_chrome(writer.sheets["Goldapple promos"], workbook, promos_ru,
                            conditional_col="Скидка, %")

    return buffer.getvalue()
```

**Sheet chrome (freeze_panes + autofilter + autosized widths + CF) pattern (source: RESEARCH.md Pattern 3 lines 335-363):**
```python
from xlsxwriter.utility import xl_col_to_name


def _apply_sheet_chrome(worksheet, workbook, df_ru, conditional_col=None):
    """Apply frozen panes + autofilter + column widths + (optional) 3-color CF."""
    n_rows, n_cols = df_ru.shape

    worksheet.freeze_panes(1, 0)  # freeze header row

    if n_rows > 0:
        worksheet.autofilter(0, 0, n_rows, n_cols - 1)
    else:
        worksheet.autofilter(0, 0, 0, n_cols - 1)  # D-506: empty sheet header-only autofilter

    # Auto column widths capped at 50 chars per Claude's Discretion
    for col_idx, col_name in enumerate(df_ru.columns):
        col_data = df_ru[col_name].astype(str) if n_rows > 0 else pd.Series([], dtype=str)
        max_content = max([len(str(col_name))] + [len(v) for v in col_data])
        width = min(max_content + 2, 50)
        fmt = _format_for_column(col_name, workbook)
        worksheet.set_column(col_idx, col_idx, width, fmt)

    if conditional_col and conditional_col in df_ru.columns and n_rows > 0:
        delta_col_idx = list(df_ru.columns).index(conditional_col)
        col_letter = xl_col_to_name(delta_col_idx)
        cf_range = f"{col_letter}2:{col_letter}{1 + n_rows}"
        worksheet.conditional_format(cf_range, {
            "type": "3_color_scale",
            "min_color": "#F8696B",
            "mid_color": "#FFEB84",
            "max_color": "#63BE7B",
            "mid_type": "num",
            "mid_value": 0,  # D-505 anchor mid at 0 (parity)
        })
```

**Number-format helper pattern (source: RESEARCH.md Pattern 5 lines 419-437):**
```python
def _format_for_column(col_name: str, workbook):
    """Map Russian header -> xlsxwriter Format object. US-locale format strings (Pitfall 2)."""
    if col_name in (
        "Цена viled, ₸", "Старая цена viled, ₸",
        "Цена goldapple, ₸", "Старая цена goldapple, ₸",
        "Дельта, ₸", "Скидка, ₸",
    ):
        return workbook.add_format({"num_format": "#,##0 ₸"})
    if col_name in ("Дельта, %", "Скидка, %"):
        return workbook.add_format({"num_format": "0.00"})  # NOT '0.00%' — already ×100 per D-405
    return None
```

**Diffs from analog (`matcher/strict_key.py` constants pattern):**
- Constants are `dict[str, str]` (header maps) — vs `text(...)` SQL constants. Same "module-level, source-locked, changed only by PR" semantic.
- New external deps: `pandas`, `xlsxwriter`, `xlsxwriter.utility.xl_col_to_name`.
- No SQL; pure DataFrame -> bytes transform. Caller (orchestrator) supplies DataFrames from `queries.py`.
- Output is `bytes` (xlsx body in memory) — `archive.write_atomic` does disk I/O. Separation per ARCHITECTURE.md "Crawler-Parser-Normalizer-Matcher = pure pipelines; Storage/Reporter/Delivery = side-effects only".

---

### `src/ga_crawler/reporter/archive.py` (filesystem service, file-I/O)

**Analog (role):** `src/ga_crawler/storage/norm06_writer.py` — file-on-disk-per-run writer pattern.

**File-write-with-mkdir + structlog pattern (`src/ga_crawler/storage/norm06_writer.py:43-82`):**
```python
def persist(
    self,
    run_id: int,
    viled_unmatched: list[str],
    goldapple_new_slugs: list[str],
) -> Path:
    """Render markdown to .planning/runs/{run_id}/norm06-review.md."""
    out_dir = self.repo_root / ".planning" / "runs" / str(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "norm06-review.md"

    today = date.today().isoformat()
    lines = [f"# NORM-06 Review Queue — Run {run_id} ({today})", ...]

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info(
        "norm06_persisted",
        run_id=run_id,
        out_path=str(out_path),
        viled_unmatched_count=len(viled_unmatched),
        goldapple_new_slugs_count=len(goldapple_new_slugs),
    )
    return out_path
```

**Diffs for Phase 5 — NEW primitives (no codebase analog), source RESEARCH.md Patterns 8-10 lines 525-607:**

`derive_filename` (RESEARCH.md Pattern 8 lines 538-552):
```python
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def derive_filename(started_at: datetime, tz_name: str = "Asia/Almaty") -> str:
    """D-512 deterministic ISO-week filename from runs.started_at.

    started_at MUST be timezone-aware UTC (SQLModel default_factory uses datetime.now(timezone.utc)).
    Edge cases:
      - 2027-01-01 (Fri) -> 2026-W53
      - 2025-12-29 (Mon) -> 2026-W01
    """
    if started_at.tzinfo is None:
        raise ValueError("started_at must be timezone-aware (DATA-05 invariant)")
    local = started_at.astimezone(ZoneInfo(tz_name))
    iso_year, iso_week, _ = local.isocalendar()
    return f"{iso_year}-W{iso_week:02d}.xlsx"
```

`write_atomic` (RESEARCH.md Pattern 9 lines 564-579):
```python
import os


def write_atomic(xlsx_bytes: bytes, target_path: Path) -> int:
    """Atomic write via temp file + os.replace. Returns final file size in bytes.

    On crash mid-write, *.xlsx.tmp may remain (Phase 7 ops playbook glob cleanup).
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)  # mirror Norm06Writer mkdir
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    tmp_path.write_bytes(xlsx_bytes)
    os.replace(tmp_path, target_path)  # atomic cross-platform per Python docs
    return target_path.stat().st_size
```

`check_size_guard` (RESEARCH.md Pattern 10 lines 590-594) — D-515 log-warn + flag, NOT fail:
```python
def check_size_guard(file_path: Path, limit_mb: int) -> tuple[bool, int]:
    """Returns (passed, size_bytes). passed=False if file > limit (D-515 flag, not fail)."""
    size_bytes = file_path.stat().st_size
    limit_bytes = limit_mb * 1024 * 1024
    return (size_bytes <= limit_bytes, size_bytes)
```

`report_overwritten` log event (D-510) — emit if target_path existed before atomic write; mirror `norm06_persisted` structured-log pattern.

**Notable contrast with norm06_writer.py:**
- Norm06Writer is a **class** (`__init__(repo_root)`); Phase 5 archive uses **module-level functions** because there is no per-instance state needed (output_dir comes from `ReportConfig`, not constructor).
- Norm06Writer uses `out_path.write_text(...)` directly (non-atomic — markdown audit artifact, partial-write is recoverable). Phase 5 uses atomic `*.tmp` + `os.replace` because xlsx is the consumed-by-Telegram artifact (Phase 6 reads back).
- Both use `mkdir(parents=True, exist_ok=True)` — same idiom.

---

### `src/ga_crawler/runners/reporter_run.py` (orchestrator, sync 7-step)

**Analog:** `src/ga_crawler/runners/matcher_run.py` — exact 7-step shape, sync.

**Module docstring + import block pattern (`src/ga_crawler/runners/matcher_run.py:1-40`):**
```python
"""Phase 4 matcher orchestrator -- `run_matcher_phase()`.

Sync 7-step pipeline mirroring `runners/viled_run.py` shape minus the
fetch/parse/normalize layers (matcher is pure SQL derivation over already-
persisted snapshots). [...]

Steps:
  1. Read run status (D-411 skip-if-failed-or-running protocol)
  2. Compute counts: ...
  3. Build matches ...
  4. Compute match.rate ...
  5. Sanity-gate P (D-409) + auto-suggest P (D-407)
  6. Atomic single-call patch_stats (Pitfall 6)
  7. Return MatcherPhaseResult; on gate-fail call run_writer.fail

Source: 04-CONTEXT.md D-409..D-414; 04-PATTERNS.md "NEW src/ga_crawler/runners/matcher_run.py".
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import structlog

from ga_crawler.interfaces import RunWriterProtocol
from ga_crawler.matcher.stats import MatchStatsBuilder
from ga_crawler.matcher.strict_key import (
    build_matches_for_run,
    compute_brand_overlap,
    compute_comparable_counts,
    compute_denominator,
    read_run_status,
)
from ga_crawler.runner.gates import auto_suggest_threshold, final_threshold_gate

log = structlog.get_logger(__name__)
```

**PhaseResult dataclass pattern (`src/ga_crawler/runners/matcher_run.py:43-51`):**
```python
@dataclass
class MatcherPhaseResult:
    """Outcome of run_matcher_phase."""

    status: str  # "success" | "failed" | "skipped"
    match_count: int = 0
    match_rate: float = 0.0
    reason: Optional[str] = None
    stats_delta: dict = field(default_factory=dict)
```

**D-411 skip-gate pattern (`src/ga_crawler/runners/matcher_run.py:108-139`):**
```python
# ---- Step 1: D-411 skip-if-upstream-failed ----
status = read_run_status(engine, run_id)
if status in (None, "failed", "running"):
    reason = (
        "failed_upstream" if status == "failed"
        else "in_progress_upstream" if status == "running"
        else "missing_run_row"
    )
    builder.set("skipped_reason", reason)
    builder.set("gate_passed", False)
    # ... other zero-value keys ...
    run_writer.patch_stats(run_id, dict(builder.delta))
    log.warning(
        "match_skipped_failed_run",
        run_id=run_id,
        upstream_status=status,
        reason=reason,
    )
    return MatcherPhaseResult(
        status="skipped",
        match_count=0,
        match_rate=0.0,
        reason=reason,
        stats_delta=dict(builder.delta),
    )
```

**Single-call patch_stats + return pattern (`src/ga_crawler/runners/matcher_run.py:197-235`):**
```python
# ---- Step 6: Atomic single-call patch_stats (Pitfall 6) ----
run_writer.patch_stats(run_id, dict(builder.delta))

elapsed = time.perf_counter() - started

# ---- Step 7: Gate-fail branch (D-409 -- audit-trail invariant) ----
if not gate_passed:
    reason = f"match_count_below_threshold:{match_count}<{threshold_p}"
    log.error("match_sanity_gate_failed", run_id=run_id, ...)
    run_writer.fail(run_id, reason)
    return MatcherPhaseResult(status="failed", ...)

log.info("matcher_phase_complete", run_id=run_id, ...)
return MatcherPhaseResult(status="success", ...)
```

**Diffs for Phase 5 (`run_reporter_phase`):**
- Function name: `run_matcher_phase` -> `run_reporter_phase`
- Dataclass name: `MatcherPhaseResult` -> `ReporterPhaseResult` with fields:
  ```python
  status: str  # "success" | "failed" | "skipped"
  xlsx_path: Optional[str] = None
  xlsx_size_bytes: int = 0
  summary_text: str = ""
  size_guard_passed: bool = True
  reason: Optional[str] = None
  stats_delta: dict = field(default_factory=dict)
  ```
- Imports change from `matcher.stats.MatchStatsBuilder` + `matcher.strict_key.{build_matches_for_run, compute_*}` to:
  ```python
  from ga_crawler.matcher.strict_key import read_run_status  # REUSED verbatim (D-507 == D-411)
  from ga_crawler.reporter.config import ReportConfig
  from ga_crawler.reporter.stats import ReportStatsBuilder
  from ga_crawler.reporter.queries import (
      read_per_sku_deltas, read_assortment_gaps, read_goldapple_promos, read_top_n_deltas,
  )
  from ga_crawler.reporter.summary_builder import build_summary
  from ga_crawler.reporter.excel_builder import build_workbook
  from ga_crawler.reporter.archive import derive_filename, write_atomic, check_size_guard
  ```
- D-507 skip-gate (Step 1) mirrors `match_skipped_failed_run` -> `report_skipped_failed_run`. Skipped path sets `report.skipped_reason="failed_upstream"` + `report.size_guard_passed=True` (no xlsx written, trivially true) + empty `report.summary_text=""` + `report.xlsx_path=""` + `report.xlsx_size_bytes=0` + `report.sheet_row_counts={}` + `report.generated_at=<now ISO>` — all 7 D-514 keys present.
- Steps 2-6 are different work (read stats -> read 3 DataFrames -> build summary -> build workbook -> archive + size-guard) but follow the same shape (logger events between steps, all stats go into `builder.delta` for atomic merge).
- Step 6 = single `run_writer.patch_stats(run_id, dict(builder.delta))` (Pitfall 6 verbatim).
- Step 7 success-return — D-515 size-guard does NOT trigger `run_writer.fail`. xlsx **always persists**; size-guard sets `report.size_guard_passed=False` flag for Phase 6 to read.
- `run_writer.fail(...)` is reached ONLY if uncaught exception bubbles to the outer caller (`main_run.py`); the orchestrator itself does NOT catch and fail per ARCHITECTURE.md "reporter independent of delivery". The `try/except DATA-05 lifecycle` is `main_run.run_weekly`'s responsibility (lines 336-373).
- No `auto_suggest_threshold` in reporter (no analog tunable to suggest); the helper `_gather_prior_match_counts` analog from `matcher_run.py:57-76` is NOT mirrored.

---

### `src/ga_crawler/runners/main_run.py` (orchestrator AMEND, composition)

**Analog:** `main_run.py` itself — the diff that inserted `run_matcher_phase` between goldapple-phase and final-finalize (`src/ga_crawler/runners/main_run.py:244-302`). Phase 5 inserts `run_reporter_phase` between matcher-phase and final-finalize using the same shape.

**Pre-finalize-before-downstream-step pattern (`src/ga_crawler/runners/main_run.py:244-269`):**
```python
# ---- Matcher phase (Plan 04-05; D-411 skip-if-failed handled inside) ----
# Composition rule: matcher needs BOTH retailer datasets. *_only modes skip it.
# D-411 makes this fire-and-let-it-handle: matcher reads runs.status itself
# and decides skip vs run. We do NOT pre-gate on upstream status here.
#
# Pre-finalize the runs row to status='success' BEFORE invoking the matcher
# so D-411's read_run_status returns 'success' (matcher proceeds) instead
# of 'running' (matcher skips). D-409 gate-fail path then calls
# run_writer.fail(...) which flips status back to 'failed' — fail() has no
# `WHERE status='running'` guard (DATA-05 idempotency).
if not viled_only and not goldapple_only:
    run_writer.finalize(run_id, status="success")
    match_config = MatchConfig.from_pyproject(pyproject_path)
    effective_p = (
        sanity_gate_p
        if sanity_gate_p is not None
        else match_config.sanity_gate_p
    )
    m_result = run_matcher_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        threshold_p=effective_p,
        p_auto_suggest_factor=match_config.p_auto_suggest_factor,
        p_auto_suggest_after_runs=match_config.p_auto_suggest_after_runs,
    )
    match_count = m_result.match_count
    match_rate = m_result.match_rate
    stats_delta_acc.update(m_result.stats_delta)
    if m_result.status == "failed":
        # ... persist Norm06 + return MainRunResult(status="failed", ...) ...
```

**Idempotent re-finalize after downstream step (`src/ga_crawler/runners/main_run.py:309-315`):**
```python
# ---- Finalize ----
# If matcher ran (viled+goldapple both invoked), the run was already
# pre-finalized to 'success' before matcher; finalize() is idempotent
# (guard `WHERE status='running'`) so a second call is a no-op when
# matcher succeeded or was skipped.
run_writer.finalize(run_id, status="success")
```

**Diffs for Phase 5 (insert `run_reporter_phase` step after matcher):**
- D-511 mandates: reporter runs **AFTER matcher BEFORE final finalize** inside the `if not viled_only and not goldapple_only:` block.
- Per D-511 (CONTEXT line 69-77 verbatim):
  ```
  runs.create()
    → run_viled_phase()
    → run_goldapple_phase()
    → Norm06Writer.persist()
    → run_writer.finalize('success')      # pre-finalize per Plan 04-05 pattern
    → run_matcher_phase()                  # reads status='success' per D-411
    → run_reporter_phase()                 # NEW — reads status='success' per D-507
    → run_writer.finalize('success')       # idempotent re-finalize per Plan 04-05
  ```
- Composition insertion point: between matcher-success-handling (`stats_delta_acc.update(m_result.stats_delta)`, after `if m_result.status == "failed"/"skipped"` blocks) and the Norm06 persist call at line 304-307.
- Reporter does NOT have a gate-fail equivalent of `m_result.status == "failed"` (D-515: size-guard is flag-only, NOT fail). The only branch is `r_result.status == "skipped"` (logged via `weekly_run_reporter_skipped` warning, falls through). Success path falls through to Norm06 persist + idempotent re-finalize.
- New imports: `from ga_crawler.reporter.config import ReportConfig` + `from ga_crawler.runners.reporter_run import run_reporter_phase`.
- `MainRunResult` dataclass amendment — add fields per D-514 to surface reporter outcome to the CLI:
  ```python
  xlsx_path: Optional[str] = None
  xlsx_size_bytes: int = 0
  summary_text: str = ""
  size_guard_passed: bool = True
  ```
- The `*_only` mode skip rule: reporter runs only when matcher runs (matcher needs BOTH retailers; reporter consumes matcher output). Same `if not viled_only and not goldapple_only:` gate.

---

### `src/ga_crawler/cli.py` (controller AMEND, argparse)

**Analog:** `_cmd_matcher` handler + `matcher-run` subparser in same file (`src/ga_crawler/cli.py:96-147` + `231-259`).

**Subcommand handler pattern (`src/ga_crawler/cli.py:96-147`):**
```python
def _cmd_matcher(args) -> int:
    """ADDED Plan 04-05 (D-412): standalone matcher re-run for recovery.

    Idempotent — calling against the same run_id twice produces the same
    matches rows (Plan 04-03 DELETE+INSERT in single TX). No re-crawl;
    matcher reads existing snapshots and computes match.* stats + matches table.

    Exit codes:
      0  -> matcher status='success'
      2  -> matcher status='failed' OR status='skipped'
    """
    from ga_crawler.matcher.config import MatchConfig
    from ga_crawler.runners.matcher_run import run_matcher_phase
    from ga_crawler.storage.sqlite import (
        SqliteRunWriter,
        init_db,
        make_engine,
    )

    init_db(args.db_path)
    engine = make_engine(args.db_path)
    run_writer = SqliteRunWriter(engine)
    cfg = MatchConfig.from_pyproject(args.pyproject)
    effective_p = (
        args.sanity_gate_p if args.sanity_gate_p is not None else cfg.sanity_gate_p
    )

    result = run_matcher_phase(
        run_id=args.run_id,
        engine=engine,
        run_writer=run_writer,
        threshold_p=effective_p,
        p_auto_suggest_factor=cfg.p_auto_suggest_factor,
        p_auto_suggest_after_runs=cfg.p_auto_suggest_after_runs,
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "run_id": args.run_id,
                "match_count": result.match_count,
                "match_rate": result.match_rate,
                "reason": result.reason,
                "threshold_p": effective_p,
                "stats_delta_keys": sorted(result.stats_delta.keys()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status == "success" else 2
```

**Subparser definition pattern (`src/ga_crawler/cli.py:231-259`):**
```python
# ADDED Plan 04-05 (D-412) — matcher-run standalone recovery tool.
matcher = sub.add_parser(
    "matcher-run",
    help="Run strict-key matcher on existing snapshots for a given run_id "
         "(idempotent, D-412)",
)
matcher.add_argument(
    "--run-id",
    type=int,
    required=True,
    help="runs.run_id of an existing run to (re-)match",
)
matcher.add_argument(
    "--db-path",
    default="prices.db",
    help="SQLite database file path",
)
matcher.add_argument(
    "--sanity-gate-p",
    type=int,
    default=None,
    help="Override match-count sanity threshold P "
         "(default: pyproject.toml [tool.ga_crawler.match].sanity_gate_p = 20)",
)
matcher.add_argument(
    "--pyproject",
    default="pyproject.toml",
    help="Path to pyproject.toml for [tool.ga_crawler.match] config",
)
```

**Dispatcher patch (`src/ga_crawler/cli.py:266-268`):**
```python
if args.cmd == "matcher-run":
    return _cmd_matcher(args)
```

**Diffs for Phase 5 (`_cmd_report` + `report-run` subparser):**
- Handler: `_cmd_matcher` -> `_cmd_report`. Same shape.
- Subparser name: `matcher-run` -> `report-run` (D-509 verbatim).
- Required: `--run-id` (int, required=True). Mirror exactly.
- Optional flags per D-509:
  - `--output-dir` (str, default=None — override `ReportConfig.output_dir`)
  - `--db-path` (str, default="prices.db" — mirror matcher)
  - `--pyproject` (str, default="pyproject.toml" — mirror matcher)
  - NO `--sanity-gate-p` analog (reporter has no sanity gate; D-515 size-guard is internal).
- Inside handler: `ReportConfig.from_pyproject(args.pyproject)`; override `output_dir` via `dataclasses.replace(cfg, output_dir=args.output_dir)` if provided (mirror `main_run._config_with_overrides` pattern at lines 90-98).
- Calls `run_reporter_phase(run_id=args.run_id, engine=engine, run_writer=run_writer, config=cfg)`.
- Exit codes: 0 if `result.status == "success"`, 2 otherwise (mirror matcher).
- JSON output keys: `status`, `run_id`, `xlsx_path`, `xlsx_size_bytes`, `summary_text`, `size_guard_passed`, `reason`, `stats_delta_keys`.
- Dispatcher: append `if args.cmd == "report-run": return _cmd_report(args)`.

---

### `pyproject.toml` (config AMEND)

**Analog:** existing `[tool.ga_crawler.match]` block (`pyproject.toml:91-96`):

```toml
[tool.ga_crawler.match]
# Phase 4 operational constants. Type-locked; operator edits via git PR.
# Source anchors: 04-CONTEXT.md (D-406..D-408, D-413).
sanity_gate_p = 20                            # D-406/D-408 seed; auto-suggest from week 5
p_auto_suggest_factor = 0.7                   # D-407 mirror D-203/D-310: 0.7 × 4-week-median
p_auto_suggest_after_runs = 4                 # D-407 mirror D-203/D-310: needs 4+ history rows
```

**Production-dependency block pattern (`pyproject.toml:6-25`):**
```toml
dependencies = [
    "camoufox[geoip]==0.4.11",
    "curl-cffi>=0.15,<0.16",
    "patchright>=1.55",
    "pydantic>=2.10,<3.0",
    "python-dotenv>=1.0,<2.0",
    "pyyaml>=6.0.3",
    "selectolax>=0.3,<0.4",
    "sqlmodel>=0.0.24,<0.1",
    "structlog>=25.0,<26.0",
    "tenacity>=9.0,<10.0",
]
```

**Dev-dep block pattern (`pyproject.toml:27-33`):**
```toml
[dependency-groups]
dev = [
    "pytest>=8,<9",
    "pytest-asyncio>=0.24",
    "pytest-mock>=3.14",
    "respx>=0.21",
]
```

**Diffs for Phase 5:**
- ADD new namespace block per D-516 (append after `[tool.ga_crawler.match]`):
  ```toml
  [tool.ga_crawler.report]
  # Phase 5 operational constants. Type-locked; operator edits via git PR.
  # Source anchors: 05-CONTEXT.md (D-509, D-510, D-512, D-515, D-516).
  output_dir = "reports"                        # D-510 relative to repo_root
  size_limit_mb = 45                            # D-515 REPORT-06 threshold (50 MB Telegram - 5 MB safety)
  top_n_deltas = 3                              # D-504 REPORT-04 summary top-N
  timezone = "Asia/Almaty"                      # D-512 ISO-week derivation tz
  ```
- ADD production deps (RESEARCH.md "Installation" lines 146-150):
  ```
  "pandas>=2.2,<2.3",
  "xlsxwriter>=3.2,<3.3",
  ```
- ADD dev dep:
  ```
  "openpyxl>=3.1,<3.2",
  ```
- ADD `tzdata; sys_platform == 'win32'` to production deps per RESEARCH.md "Windows tzdata note" line 672 (so local dev on Windows doesn't `ZoneInfoNotFoundError`).
- Wave 0 plan must run `uv sync` and commit `uv.lock` delta.

---

### `tests/unit/test_report_config.py`

**Analog:** `tests/unit/test_match_config.py` (5 tests).

**Test layout pattern (`tests/unit/test_match_config.py:17-72`):**
```python
def test_match_config_defaults():
    """D-406/D-408: seed P=20; D-407: factor=0.7, after_runs=4. Dataclass
    defaults MUST mirror pyproject.toml so tests can construct MatchConfig()
    directly and get production values."""
    c = MatchConfig()
    assert c.sanity_gate_p == 20
    assert c.p_auto_suggest_factor == 0.7
    assert c.p_auto_suggest_after_runs == 4


def test_from_pyproject_reads_match_namespace(tmp_path):
    pyp = tmp_path / "pyproject.toml"
    pyp.write_text(
        '[tool.ga_crawler.match]\nsanity_gate_p = 33\n',
        encoding="utf-8",
    )
    c = MatchConfig.from_pyproject(pyp)
    assert c.sanity_gate_p == 33
    assert c.p_auto_suggest_factor == 0.7  # default
    assert c.p_auto_suggest_after_runs == 4  # default


def test_from_pyproject_missing_file_returns_defaults():
    c = MatchConfig.from_pyproject("/non/existent/path.toml")
    assert c == MatchConfig()


def test_from_pyproject_partial_namespace_uses_defaults(tmp_path):
    # ... only some keys present, others fall back to defaults ...


def test_pyproject_has_match_namespace():
    """Production pyproject.toml MUST carry the [tool.ga_crawler.match] block
    with the canonical D-406..D-408 seed values. Regression canary against
    accidental TOML removal/rename."""
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.ga_crawler.match]" in text
    assert "sanity_gate_p = 20" in text
```

**Diffs for Phase 5:**
- All 5 test names: `match_config` -> `report_config`; `match_namespace` -> `report_namespace`.
- `test_report_config_defaults` asserts D-516 defaults: `output_dir=="reports"`, `size_limit_mb==45`, `top_n_deltas==3`, `timezone=="Asia/Almaty"`.
- `test_from_pyproject_reads_report_namespace` plants `[tool.ga_crawler.report]\nsize_limit_mb = 50\n` and asserts override + the rest default.
- `test_pyproject_has_report_namespace` (regression-canary) substring-asserts `[tool.ga_crawler.report]` + each of the 4 default-value lines in production pyproject.toml.

---

### `tests/unit/test_report_stats.py`

**Analog:** `tests/unit/test_matcher_stats.py` (12 tests).

**Test layout (`tests/unit/test_matcher_stats.py:21-135`):**
```python
def test_match_stats_keys_count():
    """Plan 04-02 + D-414: 10-tuple namespace."""
    assert len(MATCH_STATS_KEYS) == 10


def test_all_keys_have_match_prefix():
    for k in MATCH_STATS_KEYS:
        assert k.startswith("match.")


@pytest.mark.parametrize(
    "expected_key",
    [
        "match.count",
        "match.rate",
        # ... 10 keys ...
    ],
)
def test_each_required_key_present(expected_key):
    assert expected_key in MATCH_STATS_KEYS


def test_set_resolves_bare_key():
    b = MatchStatsBuilder()
    b.set("count", 42)
    assert b.delta == {"match.count": 42}


def test_set_unknown_key_raises():
    with pytest.raises(StatsNamespaceError):
        MatchStatsBuilder().set("nonsense", 1)


def test_set_viled_key_rejected():
    """Cross-namespace pollution rejected."""
    with pytest.raises(StatsNamespaceError):
        MatchStatsBuilder().set("viled.fetch_count", 100)


def test_three_way_namespaces_disjoint():
    viled_set = set(VILED_STATS_KEYS)
    gold_set = set(GOLDAPPLE_STATS_KEYS)
    match_set = set(MATCH_STATS_KEYS)
    assert viled_set.isdisjoint(match_set)
    assert gold_set.isdisjoint(match_set)
    assert viled_set.isdisjoint(gold_set)
```

**Diffs for Phase 5:**
- `test_report_stats_keys_count` -> 7 (vs 10 match). Canary regression test for D-514 7-key tuple.
- `test_all_keys_have_report_prefix` substring asserts `"report."` prefix.
- `test_each_required_key_present` parametrized list = 7 D-514 keys.
- Cross-namespace pollution tests: 3 new tests (`test_set_viled_key_rejected`, `test_set_goldapple_key_rejected`, `test_set_match_key_rejected`).
- `test_four_way_namespaces_disjoint` extends three-way invariant to four-way: `report.*` disjoint from each of `viled.* / goldapple.* / match.*`.
- New test: `test_set_dict_value_accepts` — `b.set("sheet_row_counts", {"summary": 1, "per_sku_deltas": 47})` succeeds (dict value supported by builder; Pitfall 4 None-rejection still applies for nested None).

---

### `tests/unit/test_excel_builder.py`

**Analog:** `tests/unit/test_matcher_strict_key.py` (source-locked SQL constants + on-disk fixtures + synthetic data planters).

**Source-lock pattern (used by `test_match_rate_formula_canary` — not shown in file lines 1-100 but indicated by `04-CONTEXT.md` line 9):**
```python
# Pattern: substring asserts against module-level text(...) constants.
# str(INSERT_MATCHES_SQL.compile()) or str(INSERT_MATCHES_SQL) substring check.
```

**Synthetic data planter pattern (`tests/unit/test_matcher_strict_key.py:49-92`):**
```python
def _viled_payload(sku_id: str, **overrides) -> dict:
    base = dict(
        sku_id=sku_id,
        url=f"https://viled.kz/{sku_id}",
        name="Eau de Parfum 50ml",
        brand="Givenchy",
        brand_norm="givenchy",
        name_norm="eau de parfum",
        volume_norm="(50, ml, 1)",
        # ...
    )
    base.update(overrides)
    return base


def _plant(engine, run_id, viled_rows, goldapple_rows):
    writer = SqliteSnapshotWriter(engine, batch_size=10)
    if viled_rows:
        writer.append(run_id, "viled", viled_rows)
    if goldapple_rows:
        writer.append(run_id, "goldapple", goldapple_rows)
```

**Diffs for Phase 5:**
- New imports: `pandas`, `openpyxl.load_workbook`, `io.BytesIO`.
- Use `pd.DataFrame.from_records(...)` to plant synthetic matches/gaps/promos DataFrames.
- Call `build_workbook(matches_df, gaps_df, promos_df, summary_text)` -> bytes; open via `openpyxl.load_workbook(BytesIO(bytes))`.
- Assertions (RESEARCH.md "Sheet contracts" + Pattern 3):
  - 4 sheets present, in exact order: `["Summary", "Per-SKU deltas", "Assortment gaps", "Goldapple promos"]`.
  - Sheet `Summary` cell A1 contains the supplied `summary_text` (Cyrillic + emoji round-trip).
  - Each non-Summary sheet: row 1 has Russian headers per D-503 dict constants (use `ws[1]` then assert cell values match `PER_SKU_HEADERS_RU.values()` etc.).
  - Frozen panes assertion: `ws.freeze_panes == "A2"` (openpyxl serializes freeze coord).
  - Autofilter assertion: `ws.auto_filter.ref` is non-empty string covering data range.
  - CF assertion: `len(list(ws.conditional_formatting)) > 0` on `Per-SKU deltas` (Дельта, %) + `Goldapple promos` (Скидка, %); empty on `Summary` + `Assortment gaps` (D-508). RESEARCH.md Pitfall 3 line 698 cautions against asserting CF *content* — assert presence-in-range only.
  - D-506 empty-sheet test: pass empty DataFrames, assert 4 sheets still built, each with header row + frozen pane + autofilter on header-only range, 0 data rows.
- Source-lock test mirror `test_match_rate_formula_canary`:
  - `test_per_sku_headers_ru_source_locked` substring-asserts each expected Russian header in `excel_builder.py` source via `Path("src/ga_crawler/reporter/excel_builder.py").read_text(encoding="utf-8")` containing `"Дельта, %"` etc.
- Pitfall 1 enforcement: `test_excel_builder_uses_xlsxwriter_engine` asserts the build path uses `engine='xlsxwriter'` explicitly (inspect `pd.ExcelWriter` call via mock OR open the xlsx and assert `workbook._engine` flavor — easier: assert generated sheet has `conditional_formatting` rule for CF columns, which openpyxl-write path would NOT produce identically).

---

### `tests/unit/test_summary_builder.py` (NEW, no exact analog)

**Closest pattern analog:** `tests/unit/test_matcher_stats.py` parametrize + `tests/unit/test_match_config.py` substring-source-lock pattern.

**Tests to write:**

1. **D-504 happy-path template** — stats with `match.count=47, match.rate=42.31, viled.fetch_count=100, goldapple.fetch_count=8400` + 3 top deltas + gaps_count=8385 + promo_count=1247 + iso_week="2026-W19" -> assert returned string contains each emoji + each placeholder substitution + 3 `🔝 Топ-3` lines.

2. **D-504 zero-match edge case** — `match.count=0` + empty top3 list -> assert `🔝 Топ-3 дельты` header is **absent**, but `Совпало: 0 (0.0%)` line IS present.

3. **D-504 short-top (match_count == 2)** — top3 list has 2 items -> assert 2 top lines rendered with `1.` and `2.`, no `3.` line, header `🔝 Топ-3 дельты` IS present.

4. **Template constants source-lock** (regression canary mirror `test_pyproject_has_match_namespace`):
   ```python
   def test_summary_template_source_locked():
       """D-504 + D-405 KPI-formula-freeze precedent: changing the canonical
       template requires explicit PR + this test update."""
       src = Path("src/ga_crawler/reporter/summary_builder.py").read_text(encoding="utf-8")
       assert "📊 Неделя {iso_week} — viled vs goldapple" in src
       assert "📦 viled: {viled_count} SKU" in src
       assert "🎯 Совпало: {match_count} ({match_rate}%)" in src
       assert "🆕 Гэпы: {gaps_count}" in src
       assert "💸 Промо у goldapple: {promo_count}" in src
       assert "🔝 Топ-3 дельты (viled vs goldapple):" in src
   ```

5. **stats key reads from D-414 namespace, not recomputed** (D-405 anti-pattern guard): pass a stats dict where the formula `count*100/denominator` would give 50.0 but `match.rate` is the literal value `42.31` -> assert returned string contains `(42.31%)` not `(50.0%)`. Reporter cites stat, never recomputes.

---

### `tests/unit/test_archive_iso_week.py` (NEW)

**Closest analog:** `tests/unit/test_matcher_strict_key.py` parametrize + pure-function asserts.

**Tests to write (RESEARCH.md Pattern 8 line 544-549 edge cases verbatim):**

1. **Normal-week happy path** — `datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)` + Asia/Almaty -> "2026-W19.xlsx" (May 10 2026 is a Sunday, ISO week 19).

2. **ISO year-boundary edge case** — `datetime(2027, 1, 1, 0, 0, tzinfo=timezone.utc)` (Friday) -> "2026-W53.xlsx" (Thursday rule).

3. **ISO year-boundary other direction** — `datetime(2025, 12, 29, 0, 0, tzinfo=timezone.utc)` (Monday) -> "2026-W01.xlsx".

4. **tz-naive raises ValueError** — `datetime(2026, 5, 10, 12, 0)` (no tzinfo) -> `ValueError` (DATA-05 invariant per RESEARCH.md line 549).

5. **Asia/Almaty tz applied not UTC** — `datetime(2026, 5, 10, 23, 0, tzinfo=timezone.utc)` (Sunday late UTC -> Monday 5 AM Almaty UTC+5) -> "2026-W20.xlsx" (ISO week rolls to next week in local tz, demonstrating tz conversion is applied before isocalendar()).

6. **Determinism**: call `derive_filename(same_dt)` twice, assert same return — important for D-510 idempotent overwrite semantic + SC#3 re-run.

---

### `tests/unit/test_archive_atomic_write.py` (NEW)

**Closest analog:** `tests/unit/test_norm06_writer.py` (file-on-disk-tmp_path pattern).

**Tests to write:**

1. **Happy path** — `write_atomic(b"xyz", tmp_path/"reports/2026-W19.xlsx")` -> file exists with content `b"xyz"`, returned size = 3. Auto-mkdir created `reports/` subdir.

2. **Overwrite** — write bytes A, then bytes B to same path -> file ends up with B; size matches B. (D-510 overwrite policy.)

3. **Tmp file cleanup on success** — after `write_atomic`, assert `*.xlsx.tmp` does NOT exist at parent (was renamed away, not copied).

4. **Cross-platform atomic semantic** — use `unittest.mock.patch("os.replace", side_effect=...)` to simulate failure mid-rename and assert `*.xlsx.tmp` is present afterward (operator-recoverable; partial-final NOT present).

5. **Parent dir already exists** — pre-create parent dir then call `write_atomic` -> succeeds without `FileExistsError` (mirror `mkdir(parents=True, exist_ok=True)` semantic).

---

### `tests/integration/test_archive_size_guard.py` (NEW, integration)

**Closest analog:** `tests/integration/test_matcher_run.py` (real on-disk SQLite + synthetic data + orchestrator end-to-end).

**Tests to write:**

1. **Under-limit pass** — `write_atomic(b"x" * 100, ...)` + `check_size_guard(path, limit_mb=45)` -> `(True, 100)`.

2. **Over-limit fail (D-515 — flag, NOT fail)** — synthesize 46 MB bytes (`b"x" * 46 * 1024 * 1024`) or stub `Path.stat()` with `MagicMock(st_size=47*1024*1024)`; assert `check_size_guard` returns `(False, ...)`; assert file STILL exists on disk after the check (D-515 "xlsx persists for manual recovery").

3. **End-to-end via reporter_run with stubbed-large size_limit_mb=0** — plant matches in tmp_path SQLite, set `ReportConfig(size_limit_mb=0)` so any output trips the guard, run `run_reporter_phase`, assert:
   - `result.status == "success"` (run does NOT fail)
   - `result.size_guard_passed is False`
   - xlsx file exists on disk
   - `runs.stats["report.size_guard_passed"] is False`
   - structlog `report_size_exceeded` event captured (best-effort via caplog).

---

### `tests/integration/test_reporter_run.py`

**Analog:** `tests/integration/test_matcher_run.py` (exact 7-step orchestrator integration test shape; 11 tests).

**Fixture pattern (`tests/integration/test_matcher_run.py:42-58`):**
```python
@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "matcher_e2e.db"
    init_db(db)
    return make_engine(db)


@pytest.fixture
def real_run_writer(engine):
    return SqliteRunWriter(engine)


@pytest.fixture
def writer_engine_with_run(engine, real_run_writer):
    run_id = real_run_writer.create()
    return engine, real_run_writer, run_id
```

**Happy-path E2E test (`tests/integration/test_matcher_run.py:112-126`):**
```python
def test_happy_path_writes_matches_and_stats(writer_engine_with_run):
    engine, rw, run_id = writer_engine_with_run
    rw.finalize(run_id, status="success")
    _plant(engine, run_id, [_viled("V1")], [_goldapple("G1")])
    result = run_matcher_phase(
        run_id=run_id, engine=engine, run_writer=rw, threshold_p=1
    )
    assert isinstance(result, MatcherPhaseResult)
    assert result.status == "success"
    assert result.match_count == 1
    stats = rw.get_stats(run_id)
    for key in MATCH_STATS_KEYS:
        assert key in stats, f"missing {key}"
    assert _count_matches(engine, run_id) == 1
```

**Skip-protocol test (`tests/integration/test_matcher_run.py:129-142`):**
```python
def test_skipped_when_upstream_failed(writer_engine_with_run):
    """D-411: upstream run.status='failed' -> matcher skips, matches not touched."""
    engine, rw, run_id = writer_engine_with_run
    rw.fail(run_id, "viled crash")
    _plant(engine, run_id, [_viled("V1")], [_goldapple("G1")])
    result = run_matcher_phase(
        run_id=run_id, engine=engine, run_writer=rw, threshold_p=1
    )
    assert result.status == "skipped"
    assert result.reason == "failed_upstream"
    stats = rw.get_stats(run_id)
    assert stats["match.skipped_reason"] == "failed_upstream"
```

**Diffs for Phase 5:**
- Test names: `match_*` -> `report_*`; `matcher_*` -> `reporter_*`.
- Synthetic planter must seed **both snapshots AND matches** (reporter consumes the matches table directly per D-401). Use `SqliteSnapshotWriter` + then `build_matches_for_run(engine, run_id)` to also populate matches (or directly INSERT into matches table via `engine.execute(text("INSERT INTO matches ..."))`).
- Test 1: `test_happy_path_writes_xlsx_and_stats` — plant 1 matched pair, run `run_reporter_phase`, assert `result.status == "success"`, all 7 D-514 keys in stats, xlsx file exists at `result.xlsx_path`, openpyxl can open it.
- Test 2: `test_skipped_when_upstream_failed` — `rw.fail(run_id, "...")` -> reporter status="skipped", `report.skipped_reason="failed_upstream"`, xlsx NOT created.
- Test 3: `test_skipped_when_upstream_running` — leave status='running' -> reporter skips.
- Test 4: `test_skipped_when_run_missing` — non-existent run_id -> reporter status="skipped".
- Test 5: `test_idempotent_orchestrator_rerun` — D-510 overwrite policy: run twice on same run_id, assert second call overwrites first (file mtime updated, content matches latest matches snapshot).
- Test 6: `test_size_guard_does_not_fail_run` (D-515) — set tiny `size_limit_mb=0`, assert `result.status == "success"` AND `stats["report.size_guard_passed"] is False`. NEW behavior (no analog in matcher; matcher's gate DOES fail; reporter's does NOT).
- Test 7: `test_single_patch_stats_call_on_success_path` — mock RunWriter, assert `patch_stats.call_count == 1` with delta containing all 7 keys (Pitfall 6 invariant).
- Test 8: `test_all_seven_report_keys_present_on_success` — analog to `test_all_ten_match_keys_present_on_success`.
- Test 9: `test_summary_text_in_stats_matches_xlsx_a1` (D-514 source-of-truth invariant) — open xlsx, read sheet "Summary" cell A1, assert it equals `stats["report.summary_text"]`. Defends against drift.
- Test 10: `test_no_async_in_orchestrator` — `assert not inspect.iscoroutinefunction(run_reporter_phase)` (D-513 sync, mirror matcher).
- Test 11: `test_iso_week_filename_from_started_at` — set `run.started_at = datetime(2026, 5, 10, ...)`, assert `result.xlsx_path` ends with `2026-W19.xlsx` (D-512).

---

### `tests/integration/test_main_run_with_reporter.py`

**Analog:** `tests/integration/test_main_run_e2e.py` (full pipeline integration with `run_weekly`; existing fakes for fetchers).

**Setup-repo fixture pattern (`tests/integration/test_main_run_e2e.py:40-75`):**
```python
@pytest.fixture
def setup_repo(tmp_path, brand_alias_yaml_fixture):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "brand-aliases.yaml").write_text(...)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """\
[project]
name = "ga-crawler-test"
version = "0.0.1"

[tool.ga_crawler.crawl.viled]
sanity_gate_n = 5
...
""",
        encoding="utf-8",
    )
    return {"repo_root": tmp_path, "db_path": tmp_path / "prices.db",
            "pyproject_path": pyproject}
```

**Patch-based fake fetcher pattern (`tests/integration/test_main_run_e2e.py:156-181`):**
```python
def test_full_run_cycle_viled_only(setup_repo):
    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            viled_only=True,
            pyproject_path=setup_repo["pyproject_path"],
        )
    assert result.status == "success"
```

**Diffs for Phase 5:**
- EXTEND `test_main_run_e2e.py` (existing file) OR create new sibling `test_main_run_with_reporter.py` (clean separation; existing 5+ tests untouched). Per CONTEXT requirement, new file is canonical.
- Extend `setup_repo` fixture to also write `[tool.ga_crawler.report]` block to tmp_path pyproject.toml.
- New tests:
  1. **Full-cycle viled+goldapple+matcher+reporter success** — patch fetchers for both retailers, assert `MainRunResult.status == "success"` + `result.xlsx_path` is non-None + file exists + `report.*` keys in stats.
  2. **Reporter NOT invoked on viled_only mode** — D-511 + matcher needs both retailers; reporter does too. `result.xlsx_path is None`.
  3. **Reporter skipped on matcher-failed** — patch matcher to return status="failed"; reporter D-507 skip-gate trips because pre-finalize -> matcher.fail() flips status back to "failed" -> reporter sees status=failed and skips. Assert `result.xlsx_path is None`, `result.status == "failed"`.
  4. **Reporter invoked AFTER matcher BEFORE final-finalize (D-511 ordering)** — patch `run_reporter_phase` with a side_effect that asserts `runs.status == "success"` at call-time (post-pre-finalize); patch `Norm06Writer.persist` with a side_effect that asserts reporter has already been called.
  5. **Size-guard tripped does NOT fail the weekly run** — provide synthetic-large stub for excel_builder; assert `result.status == "success"`, `report.size_guard_passed=False` in stats.

---

### `tests/integration/test_cli_report_subcommand.py`

**Analog:** `tests/integration/test_cli_matcher_subcommand.py` (6 tests via subprocess).

**subprocess helper pattern (`tests/integration/test_cli_matcher_subcommand.py:74-77`):**
```python
def _run_cli(*args, cwd=None):
    """Invoke `python -m ga_crawler ...` via subprocess. Returns CompletedProcess."""
    cmd = [sys.executable, "-m", "ga_crawler", *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
```

**planted_db fixture pattern (`tests/integration/test_cli_matcher_subcommand.py:60-71`):**
```python
@pytest.fixture
def planted_db(tmp_path):
    db = tmp_path / "p.db"
    init_db(db)
    eng = make_engine(db)
    rw = SqliteRunWriter(eng)
    rid = rw.create()
    SqliteSnapshotWriter(eng).append(rid, "viled", [_viled("V1")])
    SqliteSnapshotWriter(eng).append(rid, "goldapple", [_goldapple("G1")])
    rw.finalize(rid, status="success")
    return db, rid
```

**Help + success + skip tests (`tests/integration/test_cli_matcher_subcommand.py:83-134`):**
```python
def test_cli_help_lists_matcher_run():
    r = _run_cli("--help")
    assert r.returncode == 0
    assert "matcher-run" in r.stdout


def test_cli_matcher_run_success(planted_db):
    db, rid = planted_db
    r = _run_cli("matcher-run", "--run-id", str(rid), "--db-path", str(db), "--sanity-gate-p", "1")
    assert r.returncode == 0, f"stderr={r.stderr}"
    assert '"match_count": 1' in r.stdout
    assert '"status": "success"' in r.stdout


def test_cli_matcher_run_requires_run_id():
    r = _run_cli("matcher-run")
    assert r.returncode != 0
    combined = r.stderr + r.stdout
    assert "--run-id" in combined or "run_id" in combined
```

**Diffs for Phase 5:**
- planted_db fixture must additionally populate matches table (call `build_matches_for_run(engine, rid)` after snapshot insert + before finalize), so reporter has data to query for top-3 deltas / per-sku deltas sheet.
- 6 tests:
  1. `test_cli_help_lists_report_run` — `--help` mentions `report-run`.
  2. `test_cli_report_run_success(planted_db)` — successful invocation, exit 0, output contains `"status": "success"` + `"xlsx_path"` with non-null value + file at that path exists.
  3. `test_cli_report_run_skipped_when_upstream_failed` — plant a failed run (via `rw.fail(...)`); invoke report-run; exit 2 + `"status": "skipped"` + `"failed_upstream"`.
  4. `test_cli_report_run_requires_run_id` — argparse error path.
  5. `test_cli_report_run_output_dir_override` — invoke with `--output-dir custom/`; assert xlsx written to `tmp_path/custom/...xlsx` not `tmp_path/reports/...xlsx`.
  6. `test_cli_report_run_idempotent` — invoke twice; both succeed; xlsx exists; D-510 overwrite policy (no error).

---

### `tests/conftest.py` (AMEND, append-only)

**Analog:** existing append-only block pattern (`tests/conftest.py:153-267`):
```python
# ===== Phase 2 fixtures (D-222) =====
# Added Wave 0 of Phase 2. The 11 Phase 3 fixtures above remain untouched.
# Source: 02-CONTEXT.md D-222 + 02-PATTERNS.md §"Pattern: conftest fixture extension".

import yaml  # noqa: E402  -- import-after-block intentional for section grouping
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402
# ...

@pytest.fixture(scope="session")
def viled_pdp_html() -> str:
    """Canonical viled PDP HTML pinned Wave 0..."""
    return (VILED_FIXTURES_DIR / "viled-pdp-407682.html").read_text(encoding="utf-8")
```

**Diffs for Phase 5 (append at bottom; do not modify existing fixtures):**
```python
# ===== Phase 5 fixtures =====
# Added Wave 0 of Phase 5. Phase 2/3/4 fixtures above remain untouched.
# Source: 05-CONTEXT.md D-514 + 05-PATTERNS.md §"tests/conftest.py".

from datetime import datetime, timezone  # noqa: E402


@pytest.fixture
def tmp_reports_dir(tmp_path: Path) -> Path:
    """Per-test reports/ output dir. Auto-cleanup via pytest tmp_path."""
    p = tmp_path / "reports"
    p.mkdir()
    return p


@pytest.fixture
def synthetic_report_run(tmp_path):
    """End-to-end planted Run + Snapshots + Matches in real on-disk SQLite.

    Returns (engine, run_writer, run_id) suitable for reporter integration tests.
    """
    from ga_crawler.matcher.strict_key import build_matches_for_run
    from ga_crawler.storage.sqlite import (
        SqliteRunWriter, SqliteSnapshotWriter, init_db, make_engine,
    )

    db = tmp_path / "reporter.db"
    init_db(db)
    engine = make_engine(db)
    rw = SqliteRunWriter(engine)
    rid = rw.create()

    # Plant N viled + M goldapple snapshots with K overlapping for matches.
    SqliteSnapshotWriter(engine).append(rid, "viled", [...])
    SqliteSnapshotWriter(engine).append(rid, "goldapple", [...])

    rw.finalize(rid, status="success")
    build_matches_for_run(engine, rid)
    # Plant match.* stats so summary_builder has match.count/rate to read
    rw.patch_stats(rid, {
        "match.count": 1, "match.rate": 20.0,
        "viled.fetch_count": 1, "goldapple.fetch_count": 1,
    })
    return engine, rw, rid


@pytest.fixture
def openpyxl_workbook_reader():
    """Helper: open xlsx bytes-or-path and return openpyxl Workbook."""
    from io import BytesIO
    from openpyxl import load_workbook

    def _open(src):
        if isinstance(src, (bytes, bytearray)):
            return load_workbook(BytesIO(src))
        return load_workbook(src)

    return _open
```

---

## Shared Patterns

### Pattern A: D-411 / D-507 skip-protocol (read_run_status)

**Source:** `src/ga_crawler/matcher/strict_key.py:199-207`

```python
RUN_STATUS_SQL = text("SELECT status FROM runs WHERE run_id = :rid")


def read_run_status(engine, run_id: int) -> Optional[str]:
    """D-411 input: returns the literal status column value or ``None``.

    Caller (matcher_run orchestrator) interprets None / 'running' / 'failed'
    as skip-conditions; only 'success' OR 'partial' allow matching to proceed.
    """
    with engine.connect() as conn:
        row = conn.execute(RUN_STATUS_SQL, {"rid": run_id}).first()
    return row[0] if row else None
```

**Apply to:** `src/ga_crawler/runners/reporter_run.py` — import + call this helper directly per CONTEXT canonical_refs line 202 ("переиспользуется в runners/reporter_run.py для D-507 status-gate"). DO NOT re-implement.

### Pattern B: Pitfall 6 atomic patch_stats — single call per phase

**Source:** `src/ga_crawler/storage/sqlite.py:232-251`

```python
def patch_stats(self, run_id: int, delta: dict) -> None:
    """Atomic JSON-merge into runs.stats (Pitfall 6 RFC-7396 MergePatch).

    Pitfall 4: delta MUST NOT contain None/null values (would DELETE keys).
    """
    if any(v is None for v in delta.values()):
        raise ValueError(
            "Pitfall 4: delta contains None — RFC-7396 MergePatch DELETES "
            "the key. Use sentinels (-1, '', []) or omit the key."
        )
    delta_json = json.dumps(delta, ensure_ascii=False, default=str)
    with Session(self.engine) as s:
        s.exec(
            text(
                "UPDATE runs SET stats = json_patch(stats, :delta) "
                "WHERE run_id = :rid"
            ),
            params={"delta": delta_json, "rid": run_id},
        )
        s.commit()
```

**Apply to:** `src/ga_crawler/runners/reporter_run.py` Step 6 — `run_writer.patch_stats(run_id, dict(builder.delta))` called **exactly once** at end of orchestrator. Both success path and skip path emit one call each. Test invariant: `mock_rw.patch_stats.call_count == 1` per phase invocation (mirror `test_single_patch_stats_call_on_success_path` at `tests/integration/test_matcher_run.py:206-226`).

**Pitfall 4 (None-rejection) consequence for Phase 5:** `report.skipped_reason` uses `""` empty-string sentinel for the non-skip path (mirror `matcher_run.py:171` `builder.set("skipped_reason", "")`).

### Pattern C: Stats-namespace enforcement + cross-namespace disjointness

**Source:** `src/ga_crawler/matcher/stats.py:60-69` + `src/ga_crawler/runner/stats.py:41-43`

```python
class StatsNamespaceError(KeyError):
    """Raised when a caller tries to set a key outside the namespace."""

# In builder:
def _resolve(self, bare_key: str) -> str:
    if bare_key in _MATCH_BARE_TO_NAMESPACED:
        return _MATCH_BARE_TO_NAMESPACED[bare_key]
    if bare_key in MATCH_STATS_KEYS:
        return bare_key
    raise StatsNamespaceError(
        f"key {bare_key!r} not in MATCH_STATS_KEYS; "
        f"allowed: {sorted(MATCH_STATS_KEYS)}"
    )
```

**Apply to:** `ReportStatsBuilder` rejects `viled.* / goldapple.* / match.*` keys (cross-namespace pollution). Test extends three-way to **four-way disjointness invariant** (existing `test_three_way_namespaces_disjoint` at `tests/unit/test_matcher_stats.py:102-109`).

### Pattern D: DATA-05 lifecycle owned by outer caller, not the phase

**Source:** `src/ga_crawler/runners/main_run.py:336-373`

```python
except Exception as e:  # noqa: BLE001
    # DATA-05 invariant: every code path closes the runs row.
    tb = traceback.format_exc()
    reason = f"{type(e).__name__}: {e}"
    log.error("weekly_run_crashed", run_id=run_id, error=reason, traceback=tb)
    try:
        run_writer.fail(run_id, reason)
    except Exception as fail_exc:
        log.error("weekly_run_fail_failed", run_id=run_id, error=str(fail_exc))
    # ... return MainRunResult(status="failed", ...) ...
```

**Apply to:** Phase 5 reporter does NOT wrap its body in try/except DATA-05. Uncaught reporter exception bubbles to `main_run.run_weekly`'s outer try/except. The `*.xlsx.tmp` artifact may remain on disk (operator-recoverable). Matcher's D-409 internal `run_writer.fail` for gate-fail is matcher-specific (audit invariant); reporter has no analog because D-515 size-guard is flag-only.

### Pattern E: Sync orchestrator (no async)

**Source:** `tests/integration/test_matcher_run.py:328-330`

```python
def test_no_async_in_orchestrator():
    """D-413 / Claude's Discretion: matcher is sync, no async."""
    assert not inspect.iscoroutinefunction(run_matcher_phase)
```

**Apply to:** Phase 5 reporter is sync (D-513 mirror). All file I/O sync (`Path.write_bytes`, `os.replace`). All DB I/O sync (`engine.connect()`). All pandas/xlsxwriter sync. Test invariant in `tests/integration/test_reporter_run.py::test_no_async_in_orchestrator`.

### Pattern F: Pre-finalize-before-downstream-step composition (Plan 04-05)

**Source:** `src/ga_crawler/runners/main_run.py:244-302` (the matcher composition block)

```python
# Pre-finalize the runs row to status='success' BEFORE invoking the matcher
# so D-411's read_run_status returns 'success' (matcher proceeds) instead
# of 'running' (matcher skips).
run_writer.finalize(run_id, status="success")
match_config = MatchConfig.from_pyproject(pyproject_path)
m_result = run_matcher_phase(run_id=run_id, engine=engine, run_writer=run_writer, ...)
# ... handle m_result.status == "failed" / "skipped" ...
```

**Apply to:** Phase 5 composition does NOT re-pre-finalize (already pre-finalized by matcher composition). Sequence inside `if not viled_only and not goldapple_only:`:
1. pre-finalize (existing line 255)
2. matcher_run (existing lines 256-269)
3. handle matcher fail/skip (existing lines 273-302)
4. **NEW: reporter_run** — runs.status already "success" (from step 1) unless matcher gate-failed (in which case we already returned at step 3). Reporter D-507 sees status="success".
5. handle reporter skip (NEW lightweight branch — reporter has no fail-path)
6. Norm06 persist (existing line 305)
7. idempotent re-finalize (existing line 315)

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/ga_crawler/reporter/excel_builder.py` | builder | DataFrame -> bytes transform | No existing pandas/xlsxwriter code in the codebase. **Planner relies on RESEARCH.md Patterns 1-5 verbatim** (lines 244-437) which cite Context7-verified xlsxwriter docs. Secondary analog `matcher/strict_key.py` provides "module-level frozen constants" pattern for `PER_SKU_HEADERS_RU` etc. |
| `src/ga_crawler/reporter/archive.py` derive_filename | utility (pure) | datetime transform | No existing zoneinfo/isocalendar code in codebase. **Planner relies on RESEARCH.md Pattern 8 verbatim** (lines 525-553) + stdlib `date.isocalendar()`. |
| `src/ga_crawler/reporter/archive.py` write_atomic | filesystem service | bytes -> file with atomic rename | No existing atomic-rename code (Norm06Writer is non-atomic). **Planner relies on RESEARCH.md Pattern 9 verbatim** (lines 555-580). |
| `tests/unit/test_summary_builder.py` | test | n/a | Template golden-file regression-canary is new. **Planner uses `test_pyproject_has_match_namespace` (`tests/unit/test_match_config.py:63-71`) source-lock substring-assert pattern** + parametrize from `test_matcher_stats.py:31-47`. |
| `tests/unit/test_archive_iso_week.py` | test | n/a | ISO-week edge-case testing is new. **Planner uses parametrize pattern from `test_matcher_stats.py:31-47`** + edge cases verbatim from RESEARCH.md Pattern 8 line 544-549. |
| `tests/unit/test_archive_atomic_write.py` | test | n/a | Atomic-rename testing is new. **Planner uses `tmp_path` + file-on-disk assert pattern from `tests/unit/test_norm06_writer.py`** (existing — implies pattern). |
| `tests/integration/test_archive_size_guard.py` | test | n/a | Size-guard-without-fail testing is new. **Planner uses `tests/integration/test_matcher_run.py::test_sanity_gate_fail_persists_matches_and_fails_run`** as inverted analog (matcher DOES fail on gate-fail; reporter does NOT — both assert persistence after gate-event). |

---

## Metadata

**Analog search scope:** `src/ga_crawler/matcher/`, `src/ga_crawler/runner/`, `src/ga_crawler/runners/`, `src/ga_crawler/storage/`, `src/ga_crawler/cli.py`, `tests/unit/`, `tests/integration/`, `tests/conftest.py`, `pyproject.toml`.

**Files scanned (read or grep'd):** 17 source files + 6 test files + pyproject.toml + 05-CONTEXT.md + 05-RESEARCH.md (partial — Patterns 1-10 + Open Questions). All Phase 5 dependencies and analogs covered.

**Key pattern signal:** Phase 5 is **the third instance** of "domain package + sync orchestrator + stats namespace + CLI subcommand + pyproject namespace + integration test E2E" — viled (Phase 2), goldapple (Phase 3 imported), matcher (Phase 4). The 7-step orchestrator shape, stats-builder shape, config dataclass shape, CLI subcommand shape, conftest fixture-append shape are all **regression-canary-proof analogs**. Planner can copy-rename-edit with high confidence.

**Pattern extraction date:** 2026-05-11
