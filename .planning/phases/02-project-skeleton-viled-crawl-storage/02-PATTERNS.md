# Phase 2: Project Skeleton + viled Crawl + Storage — Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 23 new + 4 modified
**Analogs found:** 21 / 23 (high-quality matches; 2 net-new primitives have no direct analog)

## File Classification

### NEW files (Phase 2 creates)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `src/ga_crawler/storage/sqlite.py` | storage / model + writers | CRUD (SQLite) | `src/ga_crawler/cli.py:StubRunWriter` + `:StubSnapshotWriter` (behavioral parity); SQLModel idiomatic | role-match (no SQLModel file exists yet) |
| `src/ga_crawler/storage/norm06_writer.py` | storage / markdown writer | file-I/O (markdown) | `src/ga_crawler/enumeration/goldapple_sitemap.py:persist_sitemap_slugs` | role-match (file-write per run-dir) |
| `src/ga_crawler/storage/__init__.py` | package marker | — | `src/ga_crawler/enumeration/__init__.py` | exact |
| `src/ga_crawler/normalizers/brand.py` | normalizer | transform (string) | `src/ga_crawler/enumeration/slug.py:_normalize_punct` + `slug_fy_bilingual` | exact (REUSE source) |
| `src/ga_crawler/normalizers/name.py` | normalizer | transform (string) | `src/ga_crawler/enumeration/slug.py:_normalize_punct` (NFKD+lower; minus apostrophe-strip) | exact (REUSE source) |
| `src/ga_crawler/normalizers/volume.py` | normalizer | transform (string + regex grammar) | NEW primitive — no analog | NO ANALOG (RESEARCH §Pattern 6 is the spec) |
| `src/ga_crawler/normalizers/facade.py` | normalizer (composition) | request-response | `src/ga_crawler/cli.py:StubNormalizer` (Protocol satisfaction) | role-match |
| `src/ga_crawler/normalizers/__init__.py` | package marker | — | `src/ga_crawler/enumeration/__init__.py` | exact |
| `src/ga_crawler/alias/yaml_loader.py` | alias loader | file-I/O (read-once) + dict lookup | `src/ga_crawler/cli.py:StubBrandAlias` (Protocol satisfaction); `enumeration/slug.py:CYRILLIC_TO_LATIN` table-load idiom | role-match |
| `src/ga_crawler/alias/__init__.py` | package marker | — | `src/ga_crawler/enumeration/__init__.py` | exact |
| `src/ga_crawler/fetchers/viled.py` | fetcher | request-response (curl_cffi sync) | `src/ga_crawler/enumeration/goldapple_sitemap.py:_fetch_xml` (curl_cffi+tenacity) + `src/ga_crawler/fetchers/goldapple.py:fetch_one_isolated` | exact |
| `src/ga_crawler/parsers/viled_nextdata.py` | parser | transform (HTML → dataclass) | `src/ga_crawler/parsers/goldapple_microdata.py:parse_pdp` + `:GoldappleRawProduct` | exact (mirror) |
| `src/ga_crawler/parsers/dispatcher.py` | parser dispatcher | request-response (Protocol) | None — `interfaces.py:ParseDispatcherProtocol` only declares; no concrete impl exists | role-match (greenfield concrete) |
| `src/ga_crawler/parsers/types.py` | shared types | data-class | `src/ga_crawler/parsers/goldapple_microdata.py:GoldappleRawProduct` | exact (frozen dataclass pattern) |
| `src/ga_crawler/enumeration/viled_catalog.py` | enumeration / paginator | request-response (curl_cffi paginated) | `src/ga_crawler/enumeration/goldapple_sitemap.py:fetch_sitemap_slugs` (curl_cffi loop + extract) | role-match (sitemap → catalog-page __NEXT_DATA__) |
| `src/ga_crawler/runners/viled_run.py` | runner / orchestrator | sequential pipeline | `src/ga_crawler/runners/goldapple_run.py:run_goldapple_phase` | exact (mirror, sync inside) |
| `src/ga_crawler/runners/main_run.py` | runner / top-level | sequential composition | `src/ga_crawler/runners/goldapple_run.py:run_goldapple_phase` (composition pattern) | role-match |
| `src/ga_crawler/config.py` | config loader | one-shot read | None — pyproject.toml is read inline by Phase 3 in callers; no central loader yet | role-match (greenfield) |
| `bin/backup.sh` | shell script | file-I/O (sqlite3 .backup) | None — first shell script in repo | NO ANALOG (RESEARCH §Don't Hand-Roll specifies single command) |
| `config/brand-aliases.yaml` | config / data | flat-dict YAML | None — first YAML data file | role-match (PyYAML standard) |
| `tests/fixtures/viled/*.html` | test fixture | static asset | `tests/fixtures/goldapple/*` (capture pattern) | exact |
| `tests/fixtures/normalize/volume-corpus.yaml` | test fixture | static asset | None | NO ANALOG (RESEARCH Open Q5) |
| `tests/unit/test_*.py` (13 new files) | test | pytest | `tests/unit/test_fetcher_isolation.py`, `test_retry_policy.py`, etc. (existing 192-test corpus) | exact |

### MODIFIED files (Phase 2 changes)

| Modified File | Role | Action | Why |
|---------------|------|--------|-----|
| `src/ga_crawler/runner/gates.py` | gate | refactor: extract retailer-agnostic `auto_suggest_threshold` + `final_threshold_gate`; keep backward-compat shims | D-203 |
| `src/ga_crawler/runner/stats.py` | stats builder | add `ViledStatsBuilder` mirror; consider extracting `NamespaceStatsBuilder` base class | RESEARCH Open Q7 |
| `src/ga_crawler/cli.py` | CLI | DELETE 4 Stub classes; ADD `weekly-run` subcommand; KEEP `goldapple-smoke`; DELETE `goldapple-run` | D-212 + RESEARCH Open Q3 |
| `pyproject.toml` | config | ADD `[tool.ga_crawler.crawl.viled]` namespace + `pyyaml` dep | D-202, D-227 |
| `tests/conftest.py` | test fixture | ADD `viled_pdp_html`, `viled_catalog_html`, `brand_alias_yaml_fixture`, `in_memory_sqlite_session`, `volume_corpus_cases` | D-222 |

---

## Pattern Assignments

### `src/ga_crawler/fetchers/viled.py` (fetcher, request-response sync)

**Analog:** `src/ga_crawler/enumeration/goldapple_sitemap.py` (curl_cffi sync) + `src/ga_crawler/fetchers/goldapple.py:fetch_one_isolated` (per-SKU isolation)

**Imports pattern** (goldapple_sitemap.py lines 17-31, copy structure):

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from curl_cffi import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)
```

**Tenacity retry pattern** (goldapple_sitemap.py lines 45-65 — VERBATIM REUSE for viled, swap exception class):

```python
class SitemapFetchError(RuntimeError):
    """Raised when sitemap-index or sub-sitemap fetch fails terminally (after retries)."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30),
    retry=retry_if_exception_type((SitemapFetchError,)),
    reraise=True,
)
def _fetch_xml(url: str) -> str:
    """Fetch one XML resource with curl_cffi impersonate=chrome.
    Raises SitemapFetchError on non-200; tenacity retries with exp+jitter.
    """
    try:
        resp = requests.get(url, impersonate="chrome", timeout=SITEMAP_TIMEOUT_S)
    except Exception as e:
        raise SitemapFetchError(f"connection error fetching {url}: {e}") from e
    if resp.status_code != 200:
        raise SitemapFetchError(f"http {resp.status_code} for {url}")
    return resp.text
```

**Phase 2 adaptation:** rename to `TransientFetchError` + `_fetch_html`, accept `(int, str)` return for status-aware caller, add Wave 0 verification of `from curl_cffi.requests.errors import RequestsError, Timeout`.

**Per-SKU isolation pattern** (goldapple.py lines 124-149 — VERBATIM REUSE, drop async):

```python
async def fetch_one_isolated(
    fetch_callable: Callable[[Any, str], Awaitable[dict]],
    page: Any,
    url: str,
    stats: dict,
) -> Optional[dict]:
    """Per-SKU isolation per CRAWL-03. Any exception from fetch_callable is
    logged + counted but does NOT propagate. Source: RESEARCH §Pattern 5
    lines 701-711 (verbatim).
    """
    try:
        return await fetch_callable(page, url)
    except Exception as e:
        log.error(
            "fetch_failed",
            url=url,
            error=str(e),
            error_type=type(e).__name__,
        )
        stats["fetch_failures"] = stats.get("fetch_failures", 0) + 1
        return None
```

**Phase 2 adaptation:** strip `async`/`await`, drop `page` parameter (no browser); signature becomes `fetch_one_isolated(fetch_callable, url, stats) -> Optional[dict]`.

**Sequential rate-limit pattern** (goldapple.py lines 292-335 — REWRITE for sync; pattern: enumerate URLs + log progress + sleep between):

```python
async def run_loop(
    self,
    urls: list[str],
    stats: dict,
    sleep_fn: Optional[Callable[[float], Awaitable[None]]] = None,
) -> list[dict]:
    """Sequential fetch loop with random.uniform(3, 5) pacing per CRAWL-06."""
    if sleep_fn is None:
        sleep_fn = asyncio.sleep
    records: list[dict] = []
    for i, url in enumerate(urls, 1):
        rec = await fetch_one_isolated(self.fetch_one, self._page, url, stats)
        stats["fetch_count"] = stats.get("fetch_count", 0) + 1
        if rec is not None:
            records.append(rec)
        log.info("fetch_progress", run_id=self.run_id, idx=i, total=len(urls), url=url)
        if i < len(urls):
            await sleep_fn(random.uniform(*PAUSE_RANGE))
    return records
```

**Phase 2 adaptation:** drop `async`/`await`, use `time.sleep(2.0)` constant (NOT random.uniform), drop `_page` arg.

---

### `src/ga_crawler/parsers/viled_nextdata.py` (parser, HTML → dataclass)

**Analog:** `src/ga_crawler/parsers/goldapple_microdata.py`

**Frozen dataclass pattern** (goldapple_microdata.py lines 42-65):

```python
@dataclass(frozen=True)
class GoldappleRawProduct:
    """Raw extracted product from a goldapple PDP. Phase 2 normalizers consume this."""
    sku_id: str
    url: str
    name: str
    brand_raw: str
    current_price: int
    was_price: Optional[int]
    currency: str
    availability: str
    raw_volume_text: Optional[str]
```

**Phase 2 adaptation:** name `ViledRawProduct`, identical 9-field shape (Phase 2 facade in `runners/viled_run.py` produces dict matching `goldapple_run.py:237-250` for `SnapshotWriter.append` — keep field names aligned).

**parse_pdp PARSE-04 sanity-range pattern** (goldapple_microdata.py lines 240-247, 339-343 — VERBATIM REUSE):

```python
value_str = (price_meta.attributes.get("content") or "").strip()
if not value_str.isdigit():
    continue
value = int(value_str)
if not (100 <= value <= 1_000_000):  # PARSE-04 applied early
    continue
```

**Wrap-and-return pattern** (goldapple_microdata.py lines 365-375 — IDIOM):

```python
return GoldappleRawProduct(
    sku_id=sku_id,
    url=url,
    name=name,
    brand_raw=brand_raw,
    current_price=current_price,
    was_price=was_price,
    currency=currency,
    availability=availability,
    raw_volume_text=raw_volume_text,
)
```

**Phase 2 viled extraction algorithm** (RESEARCH §Pattern 1 lines 376-446 is the verbatim spec):

```python
def parse_pdp(html: str, url: str) -> Optional[ViledRawProduct]:
    nd = _extract_next_data(html)
    if nd is None:
        return None
    try:
        page_props = nd["props"]["pageProps"]
        item = page_props["item"]
        attrs = page_props["attributes"]
        if not attrs:
            return None
        a0 = attrs[0]
        current_price = int(a0["realPrice"])
        if not (100 <= current_price <= 1_000_000):  # PARSE-04
            return None
        full_price = int(a0.get("price", current_price))
        was_price = full_price if full_price > current_price else None
        currency = "KZT" if a0.get("currency", "").strip() in ("₸", "KZT") else a0.get("currency", "KZT")
        in_stock_raw = a0.get("in_stock")  # ASSUMED — Wave 0 verifies
        availability = "IN_STOCK" if in_stock_raw is True else ("OUT_OF_STOCK" if in_stock_raw is False else "UNKNOWN")
        sku_id = url.rstrip("/").rsplit("/", 1)[-1]
        return ViledRawProduct(...)
    except (KeyError, TypeError, ValueError):
        return None
```

---

### `src/ga_crawler/normalizers/brand.py` (normalizer, transform)

**Analog:** `src/ga_crawler/enumeration/slug.py:_normalize_punct` (REUSE) + `:CYRILLIC_TO_LATIN`

**REUSE source** (slug.py lines 20-31, 34-51 — DO NOT DUPLICATE; IMPORT):

```python
CYRILLIC_TO_LATIN: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    # ... 34 entries including KZ-specific ә ғ қ ң ө ұ ү һ і
}

def _normalize_punct(s: str) -> str:
    """Lowercase, NFKD, strip combining marks + apostrophes, non-alphanum→hyphen,
    collapse multi-hyphen, strip outer hyphens."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"['’ʼʹ]", "", s)
    s = re.sub(r"[^a-z0-9а-яёәғқңөұүһі]+", "-", s, flags=re.IGNORECASE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s
```

**Phase 2 adaptation** (RESEARCH §Pattern 7 lines 762-774):

```python
# normalizers/brand.py
from ga_crawler.enumeration.slug import _normalize_punct  # REUSE — DO NOT DUPLICATE

def normalize_brand(raw: str, alias_lookup) -> str:
    """NORM-02: NFKD + accent strip + lowercase + alias lookup → brand_norm."""
    candidate = _normalize_punct(raw)
    canonical = alias_lookup.canonical_for(candidate)
    return canonical or candidate
```

---

### `src/ga_crawler/runners/viled_run.py` (orchestrator, sequential pipeline)

**Analog:** `src/ga_crawler/runners/goldapple_run.py:run_goldapple_phase` (mirror end-to-end)

**PhaseResult dataclass pattern** (goldapple_run.py lines 64-74 — MIRROR):

```python
@dataclass
class PhaseResult:
    """Outcome of run_goldapple_phase."""
    status: str  # "success" | "failed"
    goldapple_count: int = 0
    reason: Optional[str] = None
    stats_delta: dict = field(default_factory=dict)
    unmatched_viled_brands: list[str] = field(default_factory=list)
    new_goldapple_slugs: list[str] = field(default_factory=list)
```

**Phase 2 adaptation:** `ViledPhaseResult` with `viled_count` instead of `goldapple_count`; drop `unmatched_*` (NORM-06 forward is Phase 3 territory; Phase 2's `viled_run.py` never computes unmatched brands).

**Builder + atomic patch_stats pattern** (goldapple_run.py lines 110-113, 287-288 — MIRROR):

```python
started = time.perf_counter()
builder = GoldappleStatsBuilder()
# ... build delta during phase ...
# Step 14: Atomic stats merge (Pitfall 6) — ONE patch_stats call
run_writer.patch_stats(run_id, builder.delta)
```

**Phase 2 adaptation:** instantiate `ViledStatsBuilder()` (parallel namespace `viled.*`), single `patch_stats` call at end.

**Final M-gate + fail pattern** (goldapple_run.py lines 290-301 — MIRROR for N-gate):

```python
if not final_m_gate(goldapple_count, M=M):
    reason = f"goldapple_count {goldapple_count} < M={M}"
    log.error("phase3_final_gate_failed", run_id=run_id, reason=reason)
    run_writer.fail(run_id, reason)
    return PhaseResult(
        status="failed",
        goldapple_count=goldapple_count,
        reason=reason,
        stats_delta=dict(builder.delta),
        ...
    )
```

**Phase 2 adaptation:** call `final_threshold_gate(viled_count, threshold=N)` (refactored helper), add second gate for `parse_quality` (D-218 >5% null-rate); both checked sequentially.

**Snapshot dict-shape contract** (goldapple_run.py lines 237-250 — VERBATIM CONTRACT for `SnapshotWriter.append`; viled_run.py MUST produce same shape):

```python
normalized = {
    "sku_id": product.sku_id,
    "url": product.url,
    "name": product.name,
    "brand": product.brand_raw,
    "brand_norm": normalizer.brand(product.brand_raw),
    "name_norm": normalizer.name(product.name),
    "current_price": product.current_price,
    "was_price": product.was_price,
    "currency": product.currency,
    "stock_state": product.availability,
    "volume_norm": normalizer.volume(product.raw_volume_text or ""),
    "raw_volume_text": product.raw_volume_text,
}
final_records.append(normalized)
# ...
inserted = snapshot_writer.append(run_id, "goldapple", final_records)
```

**Phase 2 adaptation:** swap `"goldapple"` → `"viled"`, add `multipack_flag` + `volume_raw` keys (per D-215 + DATA-02). Pitfall 7 (RESEARCH) says: integration test `test_storage_round_trip.py` MUST assert this exact dict-shape against `SqliteSnapshotWriter`.

---

### `src/ga_crawler/enumeration/viled_catalog.py` (paginator, curl_cffi)

**Analog:** `src/ga_crawler/enumeration/goldapple_sitemap.py:fetch_sitemap_slugs` (curl_cffi loop + extract pattern)

**Loop-and-extract pattern** (goldapple_sitemap.py lines 68-86 — STRUCTURE MIRROR):

```python
def fetch_sitemap_slugs(sitemap_index_url: str = SITEMAP_INDEX) -> dict[str, list[str]]:
    """Returns {slug: [urls]} map. ~1,461 slugs / ~100,779 URLs per spike 01-05."""
    idx_xml = _fetch_xml(sitemap_index_url)
    sub_urls = re.findall(r"<loc>([^<]+)</loc>", idx_xml)
    slug_map: dict[str, list[str]] = {}
    for sub in sub_urls:
        sub_xml = _fetch_xml(sub)
        for url in re.findall(r"<loc>([^<]+)</loc>", sub_xml):
            m = PRODUCT_URL_RE.match(url)
            if m:
                slug = m.group(2).lower()
                slug_map.setdefault(slug, []).append(url)
    return slug_map
```

**Phase 2 adaptation** (RESEARCH §Pattern 2 lines 458-473):

```python
def fetch_catalog_urls(catalog_base: str) -> list[str]:
    page1_html = _fetch_html(catalog_base)
    nd = _extract_next_data(page1_html)
    products = nd["props"]["pageProps"].get("products", [])
    total = nd["props"]["pageProps"].get("totalCount", len(products))
    per_page = nd["props"]["pageProps"].get("pageSize", len(products))
    urls = [p["url"] for p in products]
    num_pages = (total + per_page - 1) // per_page
    for page in range(2, num_pages + 1):
        time.sleep(2.0)  # rate limit between pages too (D-225 + Open Q6)
        page_html = _fetch_html(f"{catalog_base}?page={page}")
        page_nd = _extract_next_data(page_html)
        urls.extend(p["url"] for p in page_nd["props"]["pageProps"]["products"])
    return urls
```

---

### `src/ga_crawler/storage/sqlite.py` (storage, SQLModel + atomic helpers)

**Analog:** `src/ga_crawler/cli.py:StubRunWriter` + `:StubSnapshotWriter` (behavioral parity contract)

**Behavioral contract from StubRunWriter** (cli.py lines 73-120 — Phase 2 must satisfy same external behaviour):

```python
class StubRunWriter:
    """patch_stats merges via dict.update (Pitfall 6 atomic-merge semantics —
    real Phase 2 uses SQLite json_patch which is functionally identical)."""

    def patch_stats(self, run_id: int, delta: dict) -> None:
        # Stub: load JSON from disk, merge dict, write back
        # Real: UPDATE runs SET stats = json_patch(stats, :delta)

    def get_stats(self, run_id: int) -> dict: ...

    def fail(self, run_id: int, reason: str) -> None:
        """Stub: writes status='failed' + fail_reason to JSON.
        Real: UPDATE runs SET status='failed', fail_reason=:r"""
```

**Behavioral contract from StubSnapshotWriter** (cli.py lines 57-70):

```python
class StubSnapshotWriter:
    """Append-only JSONL writer to {root}/runs/{run_id}/snapshots.jsonl (DATA-03)."""

    def append(self, run_id: int, retailer: str, products: list) -> int:
        # Append-only — never UPDATE; one row per (run_id, retailer, sku_id) (DATA-03)
        return len(products)
```

**Phase 2 SQLModel implementation** (RESEARCH §Pattern 3 lines 487-527 + §Pattern 4 lines 555-606 — verbatim spec; no in-repo SQLModel analog exists):

```python
# storage/sqlite.py
from datetime import datetime, timezone
from typing import Optional, Literal
from sqlmodel import Field, SQLModel, Index, UniqueConstraint, create_engine, Session, text

class Snapshot(SQLModel, table=True):
    __tablename__ = "snapshots"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.run_id", index=True)
    retailer: str = Field(index=True)
    sku_id: str
    url: str
    name: str
    brand: str
    brand_norm: str = Field(index=True)
    name_norm: str
    volume_raw: Optional[str] = None
    volume_norm: Optional[str] = None
    multipack_flag: bool = Field(default=False)
    parse_error_flag: bool = Field(default=False)
    current_price: Optional[int] = None
    was_price: Optional[int] = None
    currency: str = Field(default="KZT")
    stock_state: str = Field(default="UNKNOWN")
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("run_id", "retailer", "sku_id", name="uq_snapshot_run_retailer_sku"),
        Index("ix_snapshot_retailer_brand_norm", "retailer", "brand_norm"),
        Index("ix_snapshot_run_retailer", "run_id", "retailer"),
    )
```

**Atomic json_patch RunWriter** (RESEARCH §Pattern 4 lines 570-580):

```python
def patch_stats(self, run_id: int, delta: dict) -> None:
    """Atomic merge into runs.stats using SQLite json_patch (RFC-7396 MergePatch).
    Pitfall 6: Phase 2 (viled.*) and Phase 3 (goldapple.*) keys merge cleanly.
    """
    delta_json = json.dumps(delta, ensure_ascii=False, default=str)
    with Session(self.engine) as session:
        session.exec(
            text("UPDATE runs SET stats = json_patch(stats, :delta) WHERE run_id = :rid"),
            params={"delta": delta_json, "rid": run_id},
        )
        session.commit()
```

---

### `src/ga_crawler/runner/gates.py` (MODIFY — refactor)

**Analog:** itself — extract retailer-agnostic helpers from `final_m_gate` and `auto_suggest_m`

**Existing pattern** (gates.py lines 139-166 — refactor target):

```python
def final_m_gate(goldapple_count: int, M: int = 1000) -> bool:
    """D-308/D-309 final sanity gate. Returns True iff goldapple_count >= M."""
    return goldapple_count >= M

def auto_suggest_m(history_counts: list[int]) -> Optional[int]:
    """D-310: returns suggested M after 4+ runs of history.
    Formula: int(0.7 × median(last_4_run_counts))"""
    if len(history_counts) < 4:
        return None
    last_4 = history_counts[-4:]
    median = statistics.median(last_4)
    return int(0.7 * median)
```

**Phase 2 D-203 refactor** (RESEARCH §"Code Examples" lines 980-1014):

```python
def auto_suggest_threshold(
    history_counts: list[int],
    factor: float = 0.7,
    min_runs: int = 4,
) -> Optional[int]:
    """Retailer-agnostic. int(factor × median(last min_runs counts))."""
    if len(history_counts) < min_runs:
        return None
    last = history_counts[-min_runs:]
    return int(factor * statistics.median(last))

def final_threshold_gate(count: int, threshold: int) -> bool:
    """Retailer-agnostic. count >= threshold → True."""
    return count >= threshold

# Backward-compat shims (keep Phase 3 callers green):
def auto_suggest_m(history_counts: list[int]) -> Optional[int]:
    return auto_suggest_threshold(history_counts, factor=0.7, min_runs=4)

def final_m_gate(goldapple_count: int, M: int = 1000) -> bool:
    return final_threshold_gate(goldapple_count, M)

def final_n_gate(viled_count: int, N: int = 100) -> bool:
    return final_threshold_gate(viled_count, N)
```

---

### `src/ga_crawler/runner/stats.py` (MODIFY — add ViledStatsBuilder)

**Analog:** itself — `GoldappleStatsBuilder` (mirror with `viled.*` namespace)

**Existing pattern** (stats.py lines 18-32 + 45-107):

```python
GOLDAPPLE_STATS_KEYS: tuple[str, ...] = (
    "goldapple.fetch_count",
    "goldapple.fetch_failures",
    # ... 13 keys total
)

_BARE_TO_NAMESPACED: dict[str, str] = {
    k.split(".", 1)[1]: k for k in GOLDAPPLE_STATS_KEYS
}

class StatsNamespaceError(KeyError):
    """Raised when a caller tries to set a key outside GOLDAPPLE_STATS_KEYS."""

class GoldappleStatsBuilder:
    """Accumulates goldapple.* keys for atomic merge via RunWriter.patch_stats."""

    def __init__(self) -> None:
        self.delta: dict[str, Any] = {}

    def _resolve(self, bare_key: str) -> str:
        if bare_key in _BARE_TO_NAMESPACED:
            return _BARE_TO_NAMESPACED[bare_key]
        if bare_key in GOLDAPPLE_STATS_KEYS:
            return bare_key
        raise StatsNamespaceError(...)

    def set(self, bare_key: str, value: Any) -> None:
        full = self._resolve(bare_key)
        self.delta[full] = value
```

**Phase 2 mirror** (RESEARCH Open Q7 — 9 keys for viled namespace):

```python
VILED_STATS_KEYS: tuple[str, ...] = (
    "viled.fetch_count",
    "viled.fetch_failures",
    "viled.parse_failures",
    "viled.fetch_duration_seconds",
    "viled.mean_fetch_seconds",
    "viled.sanity_gate_n_pass",
    "viled.parse_quality_pass",
    "viled.null_rate_required_fields",
    "viled.auto_suggest_n",
)

class ViledStatsBuilder:
    """Mirror of GoldappleStatsBuilder — viled.* namespace."""
    # ... identical methods ...
```

**Optional refactor** (Claude's Discretion §Module organization): extract `NamespaceStatsBuilder(prefix, allowed_keys)` base class.

---

### `src/ga_crawler/cli.py` (MODIFY — stub cutover)

**Analog:** itself — current CLI structure (cli.py lines 184-214) is the template; DELETE Stubs, ADD `weekly-run`

**Current command-dispatch pattern** (cli.py lines 184-214 — KEEP):

```python
def main(argv: Optional[list[str]] = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(prog="python -m ga_crawler", ...)
    sub = parser.add_subparsers(dest="cmd", required=True)

    smoke = sub.add_parser("goldapple-smoke", ...)
    smoke.add_argument("--run-id", type=int, default=999)
    smoke.add_argument("--headless", type=_parse_bool, default=True)

    run = sub.add_parser("goldapple-run", ...)
    run.add_argument("--run-id", type=int, required=True)
    # ...

    args = parser.parse_args(argv)
    if args.cmd == "goldapple-smoke":
        return asyncio.run(_cmd_smoke(args))
    if args.cmd == "goldapple-run":
        return asyncio.run(_cmd_run(args))
```

**Phase 2 cutover plan**:
1. DELETE classes `StubBrandAlias` (lines 37-41), `StubNormalizer` (lines 44-54), `StubSnapshotWriter` (lines 57-70), `StubRunWriter` (lines 73-120)
2. DELETE `goldapple-run` subcommand handler `_cmd_run` (lines 133-167) — references stubs
3. KEEP `goldapple-smoke` subcommand (dev tool, no stubs)
4. ADD `weekly-run` subcommand → calls `runners/main_run.py:run_weekly()` with real `SqliteRunWriter`, `SqliteSnapshotWriter`, `YamlBrandAlias`, real `Normalizer` facade
5. Wire `--sanity-gate-n` and `--sanity-gate-m` overrides

---

### `src/ga_crawler/parsers/dispatcher.py` (NEW — Protocol concrete impl)

**Analog:** `src/ga_crawler/interfaces.py:ParseDispatcherProtocol` (declaration only — no concrete impl exists yet)

**Protocol definition** (interfaces.py lines 71-79):

```python
@runtime_checkable
class ParseDispatcherProtocol(Protocol):
    """Phase 2 parser dispatcher. Per-retailer dispatch (microdata for goldapple,
    __NEXT_DATA__ for viled). Phase 3 registers goldapple_microdata.parse_pdp.
    """
    def dispatch(self, retailer: str, html_or_data: str) -> Optional[dict]: ...
```

**Phase 2 concrete impl pattern** (RESEARCH does not specify; standard registry idiom):

```python
# parsers/dispatcher.py
from typing import Callable, Optional
from ga_crawler.parsers.goldapple_microdata import parse_pdp as parse_goldapple
from ga_crawler.parsers.viled_nextdata import parse_pdp as parse_viled

class ParseDispatcher:
    """Routes raw HTML to the right per-retailer parser."""
    _registry: dict[str, Callable[[str, str], Optional[dict]]] = {
        "goldapple": parse_goldapple,
        "viled": parse_viled,
    }

    def dispatch(self, retailer: str, html: str, url: str = "") -> Optional[dict]:
        parser = self._registry.get(retailer)
        if parser is None:
            return None
        return parser(html, url)
```

---

### `tests/conftest.py` (MODIFY — add fixtures)

**Analog:** existing `tests/conftest.py` (already has 11 fixtures including `mock_brand_alias`, `mock_normalizer`, `mock_snapshot_writer`, `mock_run_writer`)

**Phase 2 additions** (D-222 + RESEARCH §Wave 0 Gaps):
- `viled_pdp_html` — load from `.planning/spikes/01-goldapple/sample-payloads/viled-fetch-results.json` then capture additional from Wave 0 probe
- `viled_catalog_html` — Wave 0 probe captures
- `brand_alias_yaml_fixture` — small YAML in-memory dict
- `in_memory_sqlite_session` — `create_engine("sqlite:///:memory:")` + `SQLModel.metadata.create_all(engine)`
- `volume_corpus_cases` — load `tests/fixtures/normalize/volume-corpus.yaml`

---

## Shared Patterns

### Pattern: Module Header + Source Anchor

**Source:** Every Phase 3 module header (e.g., `goldapple_sitemap.py` lines 1-16, `goldapple_microdata.py` lines 1-25)

**Apply to:** Every NEW module in Phase 2

```python
"""<One-line purpose>.

<Why this module exists / key invariants>

<Algorithm / behavioral contract notes>

Source: 02-RESEARCH.md §Pattern N lines XXX-YYY (verbatim).
"""

from __future__ import annotations

# imports
```

**Key:** every module MUST cite its 02-RESEARCH.md §Pattern source-anchor in the docstring (consistent with Phase 3's "Source: 03-RESEARCH.md §..." convention). This is how reviewers verify code matches research.

### Pattern: structlog Logging

**Source:** All Phase 3 modules — `goldapple.py:49`, `gates.py:26`, `goldapple_run.py:61`

**Apply to:** Every NEW module that performs I/O (fetcher, parser, writer, runner)

```python
import structlog

log = structlog.get_logger(__name__)

# Use:
log.info("event_name_snake_case", run_id=run_id, key1=val1, key2=val2)
log.error("fetch_failed", url=url, error=str(e), error_type=type(e).__name__)
```

**Key:** event names are snake_case strings, all context as kwargs (NOT f-strings). Phase 3 emits ~10 structured events per run; Phase 2 should mirror density.

### Pattern: tenacity Retry Decorator

**Source:** `enumeration/goldapple_sitemap.py:49-65` + `fetchers/goldapple.py:63-89`

**Apply to:** All NEW network-call wrappers (`fetchers/viled.py:_fetch_html`, `enumeration/viled_catalog.py:_fetch_html`)

```python
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

class TransientFetchError(RuntimeError):
    """Raised on retryable network failures (5xx, network error, timeout)."""

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30),
    retry=retry_if_exception_type((TransientFetchError,)),
    reraise=True,
)
def _fetch_html(url: str, timeout_s: int = 30) -> tuple[int, str]:
    try:
        resp = requests.get(url, impersonate="chrome", timeout=timeout_s)
    except Exception as e:
        raise TransientFetchError(f"connection error: {e}") from e
    if 500 <= resp.status_code < 600:
        raise TransientFetchError(f"http {resp.status_code}")
    return resp.status_code, resp.text
```

**Key:** wrap-and-reraise pattern — Phase 3 uses `factory _make_retry_decorator()` for monkeypatch testability; Phase 2 may follow same idiom or use module-level decorator (simpler for sync code).

### Pattern: Per-SKU Isolation (CRAWL-03)

**Source:** `fetchers/goldapple.py:124-149`

**Apply to:** `fetchers/viled.py` outer fetch loop

```python
def fetch_one_isolated(fetch_callable, url: str, stats: dict) -> Optional[dict]:
    try:
        return fetch_callable(url)
    except Exception as e:
        log.error("fetch_failed", url=url, error=str(e), error_type=type(e).__name__)
        stats["fetch_failures"] = stats.get("fetch_failures", 0) + 1
        return None
```

**Key:** per-SKU isolation is a STRUCTURAL invariant (DATA-04 + CRAWL-03) — never let one fetch exception abort the loop. Phase 3 uses async; Phase 2 sync — same shape, drop async.

### Pattern: Test File Naming + Marker Discipline

**Source:** existing `tests/unit/test_*.py` (192 tests passing)

**Apply to:** All NEW test files

- `tests/unit/test_<module_or_function>.py` — pure-logic, no network
- `tests/integration/test_<feature>.py` — uses `in_memory_sqlite_session` or fixture HTML
- `pytest -m "live"` markers reserved for Wave 0 probes + Wave 6 acceptance against real viled.kz

**Key:** Phase 3 has 192 passing tests; Phase 2 must keep them green AND add ~30-50 new (RESEARCH §Phase Requirements → Test Map line 1117-1142 enumerates 24 new test files).

### Pattern: pyproject.toml Namespace Mirror

**Source:** `pyproject.toml:49-67` `[tool.ga_crawler.crawl.goldapple]`

**Apply to:** new `[tool.ga_crawler.crawl.viled]` namespace (D-202, D-227)

```toml
[tool.ga_crawler.crawl.viled]
sanity_gate_n = 100
pause_seconds = 2.0
concurrency = 1
retry_attempts = 3
catalog_urls = [
    "https://viled.kz/men/catalog/1310",
    "https://viled.kz/women/catalog/1310",
]
n_auto_suggest_factor = 0.7
n_auto_suggest_after_runs = 4
```

**Key:** key names mirror `goldapple.*` where semantically equivalent (e.g., `m_auto_suggest_factor` → `n_auto_suggest_factor`).

---

## No Analog Found

Files with no close match in the codebase (planner uses 02-RESEARCH.md patterns directly):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/ga_crawler/normalizers/volume.py` | normalizer | regex grammar | First volume parser; greenfield. RESEARCH §Pattern 6 lines 651-756 is verbatim spec (UNIT_TABLE + MULTIPACK_PATTERNS + SINGLE_VOLUME_RE + Volume VO). |
| `src/ga_crawler/storage/sqlite.py` (SQLModel models) | model | ORM | First SQLModel file in repo. RESEARCH §Pattern 3 lines 487-527 is verbatim spec. |
| `src/ga_crawler/config.py` | config loader | one-shot | First config-loader; pyproject.toml currently read inline. Use `tomllib` (3.12 stdlib). |
| `bin/backup.sh` | shell script | sqlite3 .backup | First shell script in repo. RESEARCH §Don't Hand-Roll specifies `sqlite3 prices.db ".backup target.db"` single command. |
| `config/brand-aliases.yaml` | data file | YAML | First operator-edited YAML config. Schema flat-dict per D-205. |
| `tests/fixtures/normalize/volume-corpus.yaml` | test fixture | YAML | First test corpus. RESEARCH Open Q5 specifies location + shape (≥15 cases). |

---

## Metadata

**Analog search scope:** `src/ga_crawler/**/*.py` (16 files), `tests/conftest.py`, `pyproject.toml`, `src/ga_crawler/cli.py` (Stub impls)

**Files scanned:** 16 source modules + 1 conftest + 1 pyproject (Phase 3 frozen surface)

**Pattern extraction date:** 2026-05-07

**Key insight:** Phase 2 is ~80% mirror-and-adapt of Phase 3 frozen modules. Net-new primitives: (1) Volume value-object grammar (`normalizers/volume.py`), (2) SQLModel storage layer (`storage/sqlite.py`), (3) `__NEXT_DATA__` parser (`parsers/viled_nextdata.py`), (4) Catalog/1310 paginator (`enumeration/viled_catalog.py`), (5) YAML alias loader (`alias/yaml_loader.py`), (6) Norm06 markdown writer (`storage/norm06_writer.py`). Everything else copies a Phase 3 pattern verbatim with retailer/data-flow swap.

**Frozen-do-not-modify** (Phase 3 closed):
- `src/ga_crawler/fetchers/goldapple.py`
- `src/ga_crawler/parsers/goldapple_microdata.py`
- `src/ga_crawler/enumeration/goldapple_sitemap.py`
- `src/ga_crawler/enumeration/slug.py` (REUSE via import only)
- `src/ga_crawler/runners/goldapple_run.py`
- `src/ga_crawler/interfaces.py`

**Modify-with-care** (Phase 3 callers depend on these, but Phase 2 may extend):
- `src/ga_crawler/runner/gates.py` — add new helpers, KEEP backward-compat shims
- `src/ga_crawler/runner/stats.py` — add `ViledStatsBuilder`, KEEP `GoldappleStatsBuilder` unchanged
- `src/ga_crawler/cli.py` — DELETE Stubs + `goldapple-run`, ADD `weekly-run`, KEEP `goldapple-smoke`
- `pyproject.toml` — ADD `[tool.ga_crawler.crawl.viled]`, ADD `pyyaml` dep
- `tests/conftest.py` — ADD viled fixtures, KEEP existing 11 fixtures
