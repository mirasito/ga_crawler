---
phase: 05-reporter-excel-summary
reviewed_at: 2026-05-12T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - src/ga_crawler/reporter/__init__.py
  - src/ga_crawler/reporter/config.py
  - src/ga_crawler/reporter/stats.py
  - src/ga_crawler/reporter/queries.py
  - src/ga_crawler/reporter/excel_builder.py
  - src/ga_crawler/reporter/summary_builder.py
  - src/ga_crawler/reporter/archive.py
  - src/ga_crawler/runners/reporter_run.py
  - src/ga_crawler/runners/main_run.py
  - src/ga_crawler/cli.py
  - pyproject.toml
severity_counts:
  critical: 0
  warning: 2
  info: 6
status: issues
---

# Phase 5 Code Review — reporter-excel-summary

**Depth:** standard (per-file analysis with language-specific checks)
**Status:** issues (2 Warning, 6 Info — no Critical findings)

## Summary

All 11 production source files were inspected against the 12 invariants from the
review brief. The reporter package is correct on every load-bearing axis I can
verify statically:

- **Pitfall 6 (atomic stats merge)** — both success and skip paths in
  `reporter_run.py` call `run_writer.patch_stats` exactly once with all 7 D-514
  keys (`reporter_run.py:101`, `reporter_run.py:227`). No read-modify-write.
- **Pitfall 7 (namespace pollution)** — `ReportStatsBuilder._resolve` raises
  `StatsNamespaceError` on any non-`report.*` write. Disjointness with viled /
  goldapple / match namespaces verified by spot-check of bare-key sets.
- **D-507 skip gate** — reporter reuses `matcher.strict_key.read_run_status`
  (`reporter_run.py:37`). No re-implementation.
- **D-510 idempotency** — `archive.write_atomic` writes `*.xlsx.tmp` then
  `os.replace`. Re-run on same `run_id` overwrites without partial-write states.
- **D-515 size guard** — `check_size_guard` returns `(passed, size_bytes)`,
  never raises (oversize is flagged via stats, run.status stays `success`).
- **T-05-injection (formula injection)** — `_FORMULA_TRIGGER_CHARS = ("=", "+",
  "-", "@", "\t", "\r")` matches OWASP recommendations; applied at
  `_sanitize_cell` for every object-dtype column before xlsxwriter sees data.
- **DATA-05 lifecycle** — `reporter_run` does not catch its own exceptions;
  propagation contract preserved.
- **D-511 composition** — `main_run` gates reporter on
  `m_result.status == "success"` AFTER matcher pre-finalize, BEFORE the final
  idempotent finalize. `viled_only`/`goldapple_only` correctly skip the entire
  matcher+reporter block.
- **Path traversal** — `reporter_run.py:189-199` resolves the target path and
  applies `relative_to(repo_root_resolved)` containment check; spot-tested with
  `../..` and absolute-override traversals — both rejected.
- **SQL parameterization** — every `text(...)` constant uses `:rid` / `:n`
  binds; no f-string interpolation reaches SQL.
- **Phase 2/3/4 modules untouched** — `git log --oneline HEAD~20..HEAD --
  src/ga_crawler/matcher/ src/ga_crawler/storage/sqlite.py` returns empty.
- **Tech-stack compliance** — `pd.ExcelWriter(engine="xlsxwriter")` explicit at
  `excel_builder.py:200` (Pitfall 1). No `requests` / Selenium / BeautifulSoup
  in production paths. `openpyxl` only in `[dependency-groups].dev`.

Two Warning-class findings remain, both fixable in <15 LOC each. The Info items
are code-quality polish that does not affect correctness.

---

## Findings

### WR-01 — `_skip_path` returns `size_guard_passed=True` while DB has `False` (state divergence)

**Severity:** Warning
**File:** `src/ga_crawler/runners/reporter_run.py`
**Lines:** 97 (DB write) + 109-113 (return statement) + dataclass default at line 67

**Issue:**
In the skip path (`_skip_path`), the stats delta sets
`builder.set("size_guard_passed", False)` at line 97 (persisted to
`runs.stats.report.size_guard_passed = False`). However the function returns a
`ReporterPhaseResult` constructed without `size_guard_passed=...`, so the
dataclass default `True` (line 67) is used:

```python
return ReporterPhaseResult(
    status="skipped",
    reason=reason,
    stats_delta=dict(builder.delta),
)
```

`runners/main_run.py:345` then reads `size_guard_passed = r_result.size_guard_passed`
— i.e. `True` — and propagates that to the final `MainRunResult` (line 395)
and the `weekly_run_complete` log event. So consumers see two different
truth values for the same flag depending on whether they look in the DB or at
the orchestrator's return value.

The DB value `False` is also semantically odd on the skip path (no xlsx was
produced; "size guard failed" is a misleading flag for "no file"). The
`MainRunResult` comment at `main_run.py:172-175` even argues for `True`-as-default
meaning "no xlsx produced → no size violation."

**Recommendation:**
Make the two consistent. Either:

```python
# Option A — DB writes True on skip (no file ⇒ no size violation):
builder.set("size_guard_passed", True)
# and explicitly pass size_guard_passed=True to the result (already the default).
```

or:

```python
# Option B — return matches DB:
return ReporterPhaseResult(
    status="skipped",
    size_guard_passed=False,
    reason=reason,
    stats_delta=dict(builder.delta),
)
```

Option A reads more cleanly given the `MainRunResult` comment's framing. Either
fix removes the DB-vs-memory divergence so Phase 6 delivery cannot trip on
ambiguous semantics.

**Rationale:**
DATA-05 invariant requires every run row to end in a consistent terminal state.
If the reporter row says `size_guard_passed=False` but the orchestrator log
emits `size_guard_passed=True`, debugging a real size-exceed incident requires
disambiguating which source is authoritative. Pick one.

---

### WR-02 — `archive.check_size_guard` docstring claims "never raises" but `stat()` raises on missing file

**Severity:** Warning
**File:** `src/ga_crawler/reporter/archive.py`
**Lines:** 150-179 (function body); contradiction at 151 + 166-167 + 177

**Issue:**
The docstring asserts "Read-only, flag-only — **never raises**." But the
implementation calls `file_path.stat()` (line 177) which raises
`FileNotFoundError` if `file_path` does not exist (or `PermissionError`, or
`OSError` for I/O failures). The "never raises" contract is therefore false in
the general case.

In current usage (`reporter_run.py:201-202`), `write_atomic` immediately
precedes `check_size_guard`, so the file is guaranteed to exist on a happy
path. But:

1. Documentation lies about the contract (D-515 invariant 5 of the review
   brief says the function "MUST NOT raise" — currently it CAN raise).
2. A future caller relying on the "never raises" docstring will pass an
   arbitrary path and crash unexpectedly.
3. If a separate process deletes the file between `write_atomic` and
   `check_size_guard` (extremely unlikely, but pathologically possible on a
   shared-FS multi-tenant VPS), the function raises FileNotFoundError and
   propagates out of `reporter_run` → `main_run` catch → `run_writer.fail`,
   which contradicts D-515 ("size_guard does not fail the run").

**Recommendation:**
Either wrap the `stat()` in `try/except OSError` and return `(False, 0)` on
failure with a structlog warning, OR weaken the docstring to "raises only on
filesystem errors reading the file's metadata":

```python
def check_size_guard(file_path: Path, limit_mb: int) -> tuple[bool, int]:
    try:
        size_bytes = file_path.stat().st_size
    except OSError as exc:
        log.warning("size_guard_stat_failed", path=str(file_path), error=str(exc))
        return (False, 0)
    limit_bytes = limit_mb * 1024 * 1024
    return (size_bytes <= limit_bytes, size_bytes)
```

Alternatively, since `reporter_run` already has the size in hand from
`write_atomic`'s return value, the entire `check_size_guard` re-stat could be
eliminated — pass `size_bytes` directly and compare:

```python
size_bytes = write_atomic(xlsx_bytes, target_path)
passed = size_bytes <= config.size_limit_mb * 1024 * 1024
```

The eliminate-the-restat approach is cleaner and removes the failure mode
entirely.

**Rationale:**
Invariant 5 of the review brief states verbatim: "oversize file persists,
size_guard_passed=False, run.status stays 'success'. MUST NOT raise." The
current implementation satisfies the size-comparison semantics but technically
violates "MUST NOT raise" on edge filesystem conditions. Either fix the
contract or fix the doc — the divergence is the bug.

---

### IN-01 — `derive_filename` called twice in `run_reporter_phase`

**Severity:** Info
**File:** `src/ga_crawler/runners/reporter_run.py`
**Lines:** 176 + 187

**Issue:**
```python
iso_week_stem = derive_filename(started_at, tz_name=config.timezone).removesuffix(".xlsx")
...
filename = derive_filename(started_at, tz_name=config.timezone)
```

The same pure function is invoked with identical arguments twice for the same
input. Not a bug (deterministic), but wasteful and a future-trap: if someone
changes the tz argument in one place and not the other, the xlsx filename and
the summary's `iso_week` stem will silently diverge.

**Recommendation:**
Compute once:
```python
filename = derive_filename(started_at, tz_name=config.timezone)
iso_week_stem = filename.removesuffix(".xlsx")
```

---

### IN-02 — `read_top_n_deltas` uses positional row access `r[0]..r[3]`

**Severity:** Info
**File:** `src/ga_crawler/reporter/queries.py`
**Lines:** 162-172

**Issue:**
```python
rows = conn.execute(TOP_N_DELTAS_SQL, {"rid": run_id, "n": n}).fetchall()
return [
    dict(
        brand_norm=r[0],
        name_norm=r[1],
        volume_norm=r[2],
        price_delta_pct=r[3],
    )
    for r in rows
]
```

Positional access (`r[0]`) silently breaks if `TOP_N_DELTAS_SQL` column order
is reordered. SQLAlchemy `Row` objects support `._mapping["brand_norm"]` or
attribute access (`r.brand_norm`) which fails loudly on rename.

**Recommendation:**
Use mapping access for robustness against schema drift:
```python
return [
    dict(
        brand_norm=r._mapping["brand_norm"],
        name_norm=r._mapping["name_norm"],
        volume_norm=r._mapping["volume_norm"],
        price_delta_pct=r._mapping["price_delta_pct"],
    )
    for r in rows
]
```

---

### IN-03 — D-507 status-gate accepts only `'success'` (rejects `'partial'`) — diverges from matcher's gate

**Severity:** Info
**File:** `src/ga_crawler/runners/reporter_run.py`
**Lines:** 147-151

**Issue:**
`matcher/strict_key.py::read_run_status` documents (line 202-203): "Caller
interprets None / 'running' / 'failed' as skip-conditions; only 'success' OR
'partial' allow matching to proceed." But `reporter_run.py:148` does
`if status != "success"` — i.e. `'partial'` triggers `_skip_path`. This is a
silent divergence from the helper's documented intent.

In current orchestration the run is always pre-finalized to `'success'` before
the matcher runs (`main_run.py:271`), so `'partial'` never reaches the reporter
in practice. But the standalone `report-run` CLI tool (D-509 recovery) could
legitimately encounter a `'partial'` row and skip it — possibly surprising the
operator who would expect "partial = some matches, some not, still report what
we have."

**Recommendation:**
Either:
1. Accept `status in ("success", "partial")` and treat both as runnable (mirrors
   matcher), or
2. Document the divergence in `reporter_run.py` docstring so a future
   maintainer doesn't "fix" it.

Given that `'partial'` isn't currently emitted by any phase (matcher uses
`'success'` / `'failed'` / `'skipped'`), option 2 (document) is the
lower-risk fix.

---

### IN-04 — `summary_builder` interpolates `match_rate` and `delta_pct` without format spec

**Severity:** Info
**File:** `src/ga_crawler/reporter/summary_builder.py`
**Lines:** 33 (`match_rate`), 41 (`delta_pct`)

**Issue:**
```python
SUMMARY_TEMPLATE = """\
...
🎯 Совпало: {match_count} ({match_rate}%)
...
"""
TOP3_LINE = " {n}. {brand} {name} {volume}: {delta_pct}%"
```

`match_rate` is a float (from `match.rate` stats key); `price_delta_pct` is a
float from `matches.price_delta_pct`. With no format spec, values like
`12.345678901` render verbatim — readable but ugly. Telegram captions usually
look nicer with `:.2f`.

**Recommendation:**
Either pre-round at the SQL layer (`ROUND(price_delta_pct, 2)`) or apply
formatting in the template:
```python
"🎯 Совпало: {match_count} ({match_rate:.1f}%)"
" {n}. {brand} {name} {volume}: {delta_pct:+.2f}%"
```
The `+` sign forces explicit `+12.34%` / `-5.67%` rendering — useful for
delta semantics. Be aware the golden-file canary
(`tests/fixtures/reporter/expected-summary-text.txt`) needs regeneration if
template changes.

---

### IN-05 — `_sanitize_cell` operates only on `object`-dtype columns; misses pandas `StringDtype`

**Severity:** Info
**File:** `src/ga_crawler/reporter/excel_builder.py`
**Lines:** 84-92

**Issue:**
```python
def _sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].map(_sanitize_cell)
    return out
```

The filter `out[col].dtype == object` covers DataFrames built from
`pd.read_sql` against SQLite (which yields object dtype for TEXT columns).
But if pandas configuration changes (e.g. `pd.set_option("future.infer_string",
True)` becomes default in pandas 3.x), text columns get `StringDtype` and
the sanitizer silently no-ops. Formula injection becomes possible.

**Recommendation:**
Cover both object and string dtypes defensively:
```python
import pandas as pd
from pandas.api.types import is_string_dtype

for col in out.columns:
    if is_string_dtype(out[col]) or out[col].dtype == object:
        out[col] = out[col].map(_sanitize_cell)
```

`pd.api.types.is_string_dtype` returns True for both object-of-strings and
the new `StringDtype`. Add a regression test passing a `StringDtype`
DataFrame with `"=SUM(A:A)"` content.

---

### IN-06 — `wrap_fmt` applied three ways (column + row + write_string) on Summary sheet

**Severity:** Info
**File:** `src/ga_crawler/reporter/excel_builder.py`
**Lines:** 208-212

**Issue:**
```python
wrap_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})
ws_summary.set_column(0, 0, 60, wrap_fmt)
ws_summary.set_row(0, 192, wrap_fmt)
ws_summary.write_string(0, 0, summary_text, wrap_fmt)
```

xlsxwriter applies format precedence cell > row > column, so the
`set_column` and `set_row` calls are functionally redundant once `write_string`
passes `wrap_fmt`. Not a bug — just clutter. Worth noting because the next
maintainer might "optimize" by removing one of these and get inconsistent
behavior in edge cases (Summary sheet rows other than A1).

**Recommendation:**
Keep `set_column` (gives the 60-char width default for any future cells
written below A1) and `write_string`; drop `set_row(0, 192, wrap_fmt)` and
just call `ws_summary.set_row(0, 192)` for the row height. Minor polish.

---

_Reviewed: 2026-05-12T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
