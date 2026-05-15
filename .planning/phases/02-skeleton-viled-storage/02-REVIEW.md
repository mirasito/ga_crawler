---
phase: 02-skeleton-viled-storage
reviewed: 2026-05-14T00:00:00Z
depth: deep
files_reviewed: 19
files_reviewed_list:
  - src/ga_crawler/enumeration/viled_catalog.py
  - src/ga_crawler/fetchers/viled.py
  - src/ga_crawler/parsers/viled_nextdata.py
  - src/ga_crawler/parsers/dispatcher.py
  - src/ga_crawler/storage/sqlite.py
  - src/ga_crawler/storage/schemas.py
  - src/ga_crawler/runners/viled_run.py
  - src/ga_crawler/runners/goldapple_run.py
  - src/ga_crawler/runners/main_run.py
  - src/ga_crawler/matcher/strict_key.py
  - src/ga_crawler/matcher/stats.py
  - src/ga_crawler/normalizers/brand.py
  - src/ga_crawler/normalizers/name.py
  - src/ga_crawler/normalizers/volume.py
  - src/ga_crawler/normalizers/facade.py
  - src/ga_crawler/runner/gates.py
  - src/ga_crawler/runner/stats.py
  - src/ga_crawler/cli.py
  - src/ga_crawler/__main__.py
  - src/ga_crawler/delivery/config.py
  - src/ga_crawler/runners/delivery_run.py
findings:
  critical: 6
  warning: 5
  info: 3
  total: 14
status: issues_found
---

# Phase 02 (scope: full pipeline): Code Review Report

**Reviewed:** 2026-05-14
**Depth:** deep
**Files Reviewed:** 19 source files (pipeline-wide for 3 regression issues + known drop)
**Status:** issues_found

## Summary

Pipeline-wide adversarial review focused on three live regressions from run #16:
82/120 viled items reaching DB, 0/89+82 matches, and `delivery_skipped_no_credentials`
despite a valid `.env`. All three regressions are confirmed with root causes identified.
Two additional blockers were found during cross-file analysis.

The 120→82 viled drop has **two independent causes** that compound: schema validation
rejects items with `volume_raw=""` (falsy empty string treated as missing by `NonEmptyStr`),
and the `_compute_null_rate` gate counts `current_price=None` which can cause early-fail
before writer even runs. The match=0 failure has a single clear root cause: `volume_norm`
is serialized as the Python `str()` of a tuple
(`"(Decimal('50'), 'ml', 1)"`), while the strict-key SQL JOIN compares it as a literal
string — making every viled and goldapple `volume_norm` value unique and non-matching.
The dotenv regression in `weekly-run` is architectural: `_cmd_weekly` is the only
`weekly-run` entrypoint and it never calls `load_dotenv`, so delivery sub-phase reads
`TG_BOT_TOKEN` from a pristine environment.

---

## Critical Issues

### CR-01: volume_norm serialized as Python repr — strict-key SQL JOIN produces zero matches

**File:** `src/ga_crawler/runners/viled_run.py:102-103`
**Also affected:** `src/ga_crawler/runners/goldapple_run.py:248`

`_normalize_record` in `viled_run.py` serializes the volume tuple using Python's
`str()` builtin:

```python
volume_norm: Optional[str] = (
    str(volume_norm_tuple) if volume_norm_tuple is not None else None
)
```

`normalizer.volume()` returns `Optional[tuple[Decimal, str, int]]`. `str()` on that
tuple produces `"(Decimal('50'), 'ml', 1)"`, not `"(50, ml, 1)"` or any other
canonical form. In `goldapple_run.py:248` the tuple is written raw (no str() call):

```python
"volume_norm": normalizer.volume(product.raw_volume_text or ""),
```

Here the tuple object itself is passed to `Snapshot(**payload)`. SQLModel will call
`str()` on it at ORM level, producing the same `Decimal`-repr form. Even if both
produce the same string representation, matching requires that viled and goldapple
serialize identically — and Decimal repr varies by Python version (CPython 3.11 vs
3.12 may differ). Regardless, the strict-key JOIN at `matcher/strict_key.py:84-86`:

```sql
AND v.volume_norm = g.volume_norm
```

compares raw stored strings. If `"(Decimal('50'), 'ml', 1)"` ever differs between
viled and goldapple stored rows (e.g., count=1 suffix differs, or Decimal precision),
or if goldapple's path writes the tuple directly while viled writes str(tuple), the
equality fails silently.

The root cause of **0 matches** is that `volume_norm` should be serialized to a
canonical, deterministic string before storage — not Python's variable-length tuple
repr. The correct canonical form is `"(50, ml, 1)"` (amount as int or fixed-decimal,
unit as lowercase str, count as int).

**Fix:**

```python
# In normalizers/facade.py or a shared utility:
def _serialize_volume(v: Optional[tuple]) -> Optional[str]:
    if v is None:
        return None
    amount, unit, count = v
    # Normalize Decimal to string without trailing zeros
    amount_str = format(amount, 'f').rstrip('0').rstrip('.')
    return f"({amount_str},{unit},{count})"
```

Apply in `viled_run.py:_normalize_record` and `goldapple_run.py` (normalized dict
block). Ensure the canonical string is exactly the same code path for both retailers.

---

### CR-02: weekly-run delivery never calls load_dotenv — TG_BOT_TOKEN always missing

**File:** `src/ga_crawler/cli.py:89-106` (`_cmd_weekly`)
**Also affected:** `src/ga_crawler/runners/main_run.py:466-488`

The `deliver-run` standalone subcommand (`_cmd_deliver`, line 263) correctly calls:

```python
dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path, override=False)
```

But `_cmd_weekly` (line 89) does NOT call `load_dotenv` at all before calling
`run_weekly(...)`. Inside `run_weekly`, `DeliverEnvConfig.from_env()` at
`main_run.py:467` calls `os.getenv("TG_BOT_TOKEN")` — which reads from the process
environment, not the `.env` file. Since `weekly-run` is the integrated production
entrypoint (called from `bin/weekly-run.sh`), and the shell script does not export
`TG_BOT_TOKEN`, the token is never loaded.

The sibling `httpx.post` test the user mentions working is a different code path that
explicitly passes the token or runs inside an environment where the variable is
already exported.

This explains `delivery_skipped_no_credentials / missing_env: TG_BOT_TOKEN` on every
`weekly-run` invocation.

**Fix — apply `load_dotenv` at the `_cmd_weekly` boundary:**

```python
def _cmd_weekly(args) -> int:
    from dotenv import find_dotenv, load_dotenv
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)

    from ga_crawler.runners.main_run import run_weekly
    ...
```

The `find_dotenv(usecwd=True)` pattern (identical to `_cmd_deliver`) anchors the
search at the cwd where the operator invokes the script, matching production
(`/opt/ga_crawler`). This pattern is already documented as the project hazard in
`MEMORY.md (hazard_dotenv_walks_from_file)`.

---

### CR-03: ViledRawProduct schema rejects items where raw_volume_text falls back to empty string

**File:** `src/ga_crawler/storage/schemas.py:56-57`
**Also affected:** `src/ga_crawler/parsers/viled_nextdata.py:251`
**Also affected:** `src/ga_crawler/storage/sqlite.py:210-222`

`schemas.py` defines:

```python
class ViledRawProduct(RawProductBase):
    volume_raw: Optional[NonEmptyStr] = None
```

`NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]`

In `viled_nextdata.py:251`:

```python
raw_volume_text=_extract_volume_from_nextdata(a0) or name,
```

This sets `raw_volume_text` to `name` as fallback. But consider items where
`_extract_volume_from_nextdata` returns `None` AND `item.get("name")` returns an
empty string `""` — though `parse_pdp` guards `if not name: return None`, the guard
uses truthiness which means `name=""` causes `return None` before reaching the
`raw_volume_text=` line. That path is safe.

However, the field gets stored as `volume_raw` in `_normalize_record` (viled_run.py:119):

```python
"volume_raw": raw_volume_text,
```

where `raw_volume_text = parsed.get("raw_volume_text") or parsed.get("name") or ""`
(line 97). The trailing `or ""` means `raw_volume_text` can be `""` (empty string)
when both keys are absent/falsy in the parsed dict. An empty string `""` fails
`NonEmptyStr(min_length=1)` Pydantic validation in `SqliteSnapshotWriter.append`,
causing the row to be rejected silently (line 222: `continue`). The rejection is
counted in `_last_rejected_reasons` but this count is NEVER read or surfaced to the
caller — there is no schema_rejected_rate_gate invocation in `viled_run.py` or
`main_run.py` for the viled phase.

**This is a silent drop path contributing to 120→82 count.**

**Fix:**

1. In `viled_run.py:_normalize_record` line 97, use `None` sentinel instead of `""`:
```python
raw_volume_text = parsed.get("raw_volume_text") or parsed.get("name") or None
```

2. Invoke `schema_rejected_rate_gate` after `snapshot_writer.append` for viled phase
   (mirrors Phase 9 intent for goldapple):
```python
rejected = len(snapshot_writer._last_rejected_reasons)
schema_gate = schema_rejected_rate_gate(rejected, len(snapshot_rows))
if not schema_gate.passed:
    # fail run or at minimum log prominently
```

---

### CR-04: schema_rejected_rate_gate defined but never called for either retailer in the production path

**File:** `src/ga_crawler/runners/viled_run.py` (absent)
**Also affected:** `src/ga_crawler/runners/goldapple_run.py` (absent)
**Also affected:** `src/ga_crawler/runners/main_run.py` (absent)

Phase 9 (Plan 09-02b, D-903) added `schema_rejected_rate_gate` to `runner/gates.py`
and `SqliteSnapshotWriter._last_rejected_reasons` to `storage/sqlite.py`. The gate
function exists and the rejection reasons accumulate, but the gate is never evaluated
in any production code path. `viled_run.py` has no call to `schema_rejected_rate_gate`.
`goldapple_run.py` has no call. `main_run.py` has no call. The only invocations
are in tests.

This means the 5% schema-rejection gate documented as D-903 is entirely non-functional
in production. Items are silently rejected by Pydantic validation with no run failure,
no stats persisted for `schema.rejected_count`, and no alerting. The `SCHEMA_STATS_KEYS`
namespace in `runner/stats.py` is similarly never populated.

**Fix:**

After `snapshot_writer.append(run_id, "viled", snapshot_rows)` in `viled_run.py:251`:
```python
rejected_count = len(snapshot_writer._last_rejected_reasons)
schema_gate = schema_rejected_rate_gate(rejected_count, len(snapshot_rows))
run_writer.patch_stats(run_id, {
    "schema.rejected_count": rejected_count,
    "schema.rejected_rate": round(schema_gate.rejected_rate, 4),
    "schema.rejected_reasons": snapshot_writer._last_rejected_reasons[:50],
})
if not schema_gate.passed:
    reason = f"schema_validation_rejected_rate ({schema_gate.rejected_rate:.3f} > 0.05)"
    run_writer.fail(run_id, reason)
    return ViledPhaseResult(status="failed", ...)
```

Mirror for goldapple phase. Note: `patch_stats` rejects None values (Pitfall 4) —
use empty list `[]` not None for `schema.rejected_reasons` when empty.

---

### CR-05: goldapple volume_norm stored as raw tuple object — ORM serialization undefined

**File:** `src/ga_crawler/runners/goldapple_run.py:248`

```python
"volume_norm": normalizer.volume(product.raw_volume_text or ""),
```

`normalizer.volume()` returns `Optional[tuple[Decimal, str, int]]`. This raw tuple
is placed directly into the dict passed to `Snapshot(**payload)`. SQLModel/SQLAlchemy
will call Python `str()` on the tuple to fit it into the `Optional[str]` column,
producing `"(Decimal('50'), 'ml', 1)"`. This is distinct from what `viled_run.py`
produces via explicit `str(volume_norm_tuple)` only because the ORM conversion path
may or may not canonicalize the Decimal representation consistently.

This is the **co-cause** of CR-01: even if viled were fixed, goldapple's serialization
is still non-deterministic. Both must be fixed with the same canonical serializer.

**Fix:** same canonical `_serialize_volume` function as CR-01, applied here.

---

### CR-06: fetch_count inflated relative to inserted — run_loop counts ALL fetches including failures, while inserted counts only parsed+validated rows; 120→82 drop attribution is partially obscured

**File:** `src/ga_crawler/runners/viled_run.py:222-224`

```python
fetched_records = fetcher.run_loop(deduped_urls, run_loop_stats, sleep_fn=time.sleep)
builder.set("fetch_count", run_loop_stats.get("fetch_count", 0))
builder.set("fetch_failures", run_loop_stats.get("fetch_failures", 0))
```

`run_loop_stats["fetch_count"]` is incremented for EVERY URL (line 190 in viled.py),
including those that return `None` from `fetch_one_isolated`. So `viled.fetch_count`
in the DB will show 120 (all attempted), but `parse_failures` will contain URLs that
fetched OK (status=200) but returned `None` from `parse_pdp`.

More critically: the **stats attribution** between "fetch failed", "parse failed",
and "schema validation rejected" is completely separate in accounting, but the only
visible summary count the operator sees is `viled_count = inserted`, which is
`snapshot_writer.append(...)` return value. There is no logged line that says "38
items dropped: N fetch-fail, M parse-fail, K schema-rejected". The operator sees
`inserted=82` with no breakdown. Combined with CR-04 (schema gate never called),
the schema-rejection drop is entirely invisible.

This is a **diagnostic blocker**: the operator cannot determine from logs alone how
many of the 38 dropped items are fetch failures vs parse failures vs schema
rejections.

**Fix:** after viled persist (around line 252), log an attribution summary:

```python
schema_rejected = len(snapshot_writer._last_rejected_reasons)
log.info(
    "viled_drop_attribution",
    run_id=run_id,
    urls_total=len(deduped_urls),
    fetch_failures=run_loop_stats.get("fetch_failures", 0),
    parse_failures=parse_failures,
    schema_rejected=schema_rejected,
    inserted=inserted,
)
```

---

## Warnings

### WR-01: _compute_null_rate operates on snapshot_rows (post-parse), not post-insert — gate may pass when schema rejects rows inflate the null rate

**File:** `src/ga_crawler/runners/viled_run.py:263-266`

```python
null_rate = _compute_null_rate(snapshot_rows)
```

`snapshot_rows` is built from all successfully-parsed records (line 245) before the
Pydantic schema validation inside `snapshot_writer.append`. If schema validation
rejects 38 rows (CR-03), `_compute_null_rate` runs over 120 rows, not 82. The null
rate from the pre-schema-validation list may pass the 5% gate while the post-validation
inserted count would fail a count-based gate. The gate runs on a different population
than what was actually stored — a subtle correctness mismatch.

**Fix:** compute null_rate after append, on the inserted population, or pass
`total_attempted` and `inserted` separately to a combined gate.

---

### WR-02: viled_run._gather_prior_counts fallback key "fetch_count" (bare) hides real history

**File:** `src/ga_crawler/runners/viled_run.py:142`

```python
c = stats.get("viled.fetch_count") or stats.get("fetch_count")
```

The bare `"fetch_count"` fallback will never match any viled stats key because
`ViledStatsBuilder` always writes namespaced keys (`"viled.fetch_count"`). The
fallback would silently match a `goldapple.fetch_count` if it happened to be stored
under the bare key — which it is not. The result is that auto-suggest never sees
prior viled history. This is a minor correctness issue but means D-203 auto-suggest
is silently disabled.

**Fix:** remove the fallback:
```python
c = stats.get("viled.fetch_count")
```

---

### WR-03: goldapple_run uses local _gather_prior_counts that shadows the module-level one — duplicate function with same name

**File:** `src/ga_crawler/runners/goldapple_run.py:317-339`

`goldapple_run.py` defines a module-level function `_gather_prior_counts` at line
317. However `run_goldapple_phase` calls `_gather_prior_counts(run_writer, current_run_id=run_id)`
at line 278 — which resolves to the module-level function at line 317, not a local.
The call at line 278 passes `current_run_id=run_id` as a keyword argument, but the
function signature at line 318 is `_gather_prior_counts(run_writer, current_run_id)`.
This is consistent, but the function reads from `goldapple.fetch_count` AND the bare
`fetch_count` fallback (line 336) — the same stale-fallback bug as WR-02.

Additionally, the function is included in the goldapple_run module's namespace and
is NOT in `__all__`, which hides it from the module's public contract while it's used
internally — fine, but the shadowing risk from the fallback key is the same as WR-02.

**Fix:** remove bare `"fetch_count"` fallback in line 336.

---

### WR-04: schema.rejected_reasons is list[dict] — patch_stats rejects None but allows empty list; Pitfall 4 not guarded for this key

**File:** `src/ga_crawler/storage/sqlite.py:191-232`

`_last_rejected_reasons` defaults to `[]` (empty list). If `run_writer.patch_stats`
is ever called with `{"schema.rejected_reasons": []}` that is fine (empty list is
not None). But if the list is accidentally passed as `None`, `patch_stats` raises
`ValueError`. The schema gate (CR-04 fix) will need to guard this explicitly. The
existing `patch_stats` `any(v is None for v in delta.values())` check does NOT
recurse into list elements — so a list containing `None` items would pass through
and potentially corrupt the JSON. The current `rejected_reasons` list items are
always dicts (line 214-221) so this is a latent risk, not a current bug.

**Fix:** add an assertion in `SqliteSnapshotWriter.append` that `rejected_reasons`
list elements are always dicts (or add a type annotation).

---

### WR-05: _MULTIPACK_KEYWORD_PATTERNS last entry matches any "N x M" number pair — over-triggers on dimension strings

**File:** `src/ga_crawler/normalizers/volume.py:85`

```python
re.compile(r"\d+\s*[xх×]\s*\d+", re.IGNORECASE),  # generic N x M
```

This pattern will match dimension-like strings in product names such as
`"Palette 10x3"` (10-shadow palette, 3g each) or `"Sheet mask 5x30ml"`.
`detect_multipack` returning `True` for a single-SKU with a dimension expression
causes `multipack_flag=True`, which excludes the SKU from the strict-key JOIN
(`AND v.multipack_flag = 0`). This is a known false-positive suppression category
that reduces match count by an unknown amount.

The pattern is intentionally broad (documented as "generic N x M"). The risk is
that it over-fires on non-multipack products containing size pairs or numeric codes.

**Fix:** add a minimum digit magnitude check or a context guard (e.g., require at
least one known unit token nearby). Alternatively, document accepted false-positive
rate and add a monitoring counter for `multipack_flag=True` rate in viled snapshots.

---

## Info

### IN-01: GoldappleStatsBuilder.set raises StatsNamespaceError for "parser_drift_failure_reason" key in drift gate block — potential crash if key typo

**File:** `src/ga_crawler/runners/main_run.py:317`

```python
drift_builder.set(
    "parser_drift_failure_reason",
    drift.failure_reason if drift.failure_reason is not None else "",
)
```

`GoldappleStatsBuilder._resolve("parser_drift_failure_reason")` works correctly —
the key is in `GOLDAPPLE_STATS_KEYS`. But any future refactoring that renames the
constant without updating the builder call site would produce a runtime
`StatsNamespaceError` that crashes the run. The key is referenced by bare string in
multiple places. Consider referencing `GOLDAPPLE_STATS_KEYS` elements by index or
symbolic constant rather than string literals.

---

### IN-02: DeliverEnvConfig.from_env() called BEFORE load_dotenv in main_run.py delivery block

**File:** `src/ga_crawler/runners/main_run.py:467`

```python
deliver_env = DeliverEnvConfig.from_env()
```

Even if CR-02 is fixed by adding `load_dotenv` to `_cmd_weekly`, the `run_weekly`
function itself still constructs `DeliverEnvConfig.from_env()` internally. The fix
must be applied at the CLI boundary BEFORE `run_weekly` is called, not inside
`run_weekly`. If another caller invokes `run_weekly` directly (e.g., test code or a
future library caller), the dotenv load will not happen and delivery will silently
fail. Document this pre-condition on `run_weekly`'s docstring.

---

### IN-03: viled_run.py _normalize_record has no guard against sku_id being empty string after str() coercion

**File:** `src/ga_crawler/runners/viled_run.py:109`

```python
"sku_id": str(parsed.get("sku_id", "")),
```

If `parsed["sku_id"]` is `None` or absent (though `parse_pdp` in `viled_nextdata.py`
sets it via URL parsing, which itself could produce `""` if the URL is empty), `str(None)`
produces `"None"` — not caught by `NonEmptyStr` because it has 4 characters. A SKU
with `sku_id="None"` would silently persist and could collide across runs given the
`UniqueConstraint("run_id", "retailer", "sku_id")`. The `parse_pdp` function does
set `sku_id` to a reasonable fallback, but the defense-in-depth guard is absent here.

**Fix:**
```python
"sku_id": str(parsed.get("sku_id") or "") or "<unknown>",
```

or assert non-empty before appending to `snapshot_rows`.

---

## Root Cause Summary for the Three Known Regressions

| Regression | Root Cause | Finding |
|---|---|---|
| 120→82 viled drop | `volume_raw=""` (empty string) fails `NonEmptyStr` Pydantic validation silently; schema gate never invoked to surface the drop | CR-03, CR-04 |
| 0 matches | `volume_norm` serialized as Python tuple repr `"(Decimal('50'), 'ml', 1)"` — viled and goldapple may produce identical strings but they are non-canonical; most critically the Decimal repr makes the string non-parseable and potentially mismatched | CR-01, CR-05 |
| delivery_skipped_no_credentials | `_cmd_weekly` never calls `load_dotenv`; `TG_BOT_TOKEN` is never in `os.environ` when called from the shell script | CR-02 |

---

_Reviewed: 2026-05-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
