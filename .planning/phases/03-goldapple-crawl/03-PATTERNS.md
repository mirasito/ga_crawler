# Phase 3: Goldapple Crawl — Pattern Map

**Mapped:** 2026-05-06
**Files analyzed:** 17 new + 0 modified
**Analogs found:** 9 / 17 (spike `notebook.py`); 4 protocol stubs cite `interfaces.py` (Wave 0 contract); 4 greenfield with no analog (cite RESEARCH.md spec)
**Spike used as primary analog:** `C:\Users\gstorepc\projects\ga_crawler\.planning\spikes\01-goldapple\notebook.py` (lines 1–322)

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `src/ga_crawler/interfaces.py` | interface (Protocol) | contract | RESEARCH.md §"Open Questions" Q6 spec (lines 1077–1094) | spec-only (greenfield) |
| `src/ga_crawler/enumeration/__init__.py` | package init | — | (empty package init) | trivial |
| `src/ga_crawler/enumeration/goldapple_sitemap.py` | fetcher (Tier 0) | request-response (HTTP→XML→dict) | `notebook.py` curl_cffi pattern (referenced by RESEARCH §Pattern 1, lines 326–349) | role-match (curl_cffi pattern present in research; spike file `_fetch_sitemap_pagevolume.py` is the executable analog) |
| `src/ga_crawler/enumeration/slug.py` | utility (pure) | transform | RESEARCH.md §Pattern 2 (lines 358–423) — algorithm spec | spec-only (greenfield: no transliteration analog exists) |
| `src/ga_crawler/fetchers/__init__.py` | package init | — | — | trivial |
| `src/ga_crawler/fetchers/goldapple.py` | fetcher (Tier 2 Camoufox) | event-driven (browser orchestration) | `notebook.py` `bootstrap` block lines 207–214, `fetch_one()` lines 128–191, retry loop lines 217–257 | exact (refactor-into-class of spike `fetch_one`) |
| `src/ga_crawler/parsers/goldapple_microdata.py` | parser | transform (HTML→dataclass) | `notebook.py` `has_microdata_price()` lines 94–110 + `evaluate_product_data()` lines 113–125 + RESEARCH §Pattern 4 (lines 509–673) | role-match (spike does microdata detection only; full PARSE-01..05 extraction is greenfield with priceType-discrimination spec from RESEARCH) |
| `src/ga_crawler/runner/__init__.py` | package init | — | — | trivial |
| `src/ga_crawler/runner/gates.py` | runner-gate (smoke + sanity + auto-suggest) | request-response | RESEARCH.md §"Code Examples" smoke probe lines 906–935; final M-gate lines 940–954 | spec-only (greenfield; smoke probe re-uses `GoldappleFetcher` analog) |
| `src/ga_crawler/runner/stats.py` | utility (stats writer) | transform | RESEARCH.md §"Open Questions" Q4 stats schema (lines 1043–1066) | spec-only (greenfield) |
| `tests/conftest.py` | test (fixture root) | — | RESEARCH §Project Structure line 298 | spec-only (greenfield, project-wide) |
| `tests/fixtures/goldapple/_debug-product-page.html` | fixture | — | **COPY** spike sample-payload (existing file) | exact (verbatim copy) |
| `tests/fixtures/goldapple/gate-shell.html` | fixture | — | spike sample-payload `goldapple-product-html-1.html` (gate-shell evidence per MEMO §"JSON-endpoint hunt verdict" lines 67–81) | exact (rename + copy) |
| `tests/fixtures/goldapple/stale-sku-9.5kb.html` | fixture | — | spike `tier2-camoufox-kz-results.json` row 0 (`7681000002-...`); MEMO §"Open Risks" lines 38–39 | role-match (URL identified in spike; HTML body must be re-fetched at plan-time) |
| `tests/fixtures/goldapple/sitemap-1-excerpt.xml` | fixture | — | **COPY** `goldapple-sitemap-1-excerpt.xml` | exact (verbatim copy) |
| `tests/fixtures/goldapple/tier2-camoufox-kz-results.json` | fixture | — | **COPY** spike file (empirical baseline) | exact (verbatim copy) |
| `tests/unit/test_slug_fy.py` | test (unit) | — | RESEARCH §Pattern 2 test-case table (lines 427–439) | spec-only (greenfield) |
| `tests/unit/test_goldapple_microdata_parser.py` | test (unit) | — | `_debug-product-page.html` fixture + RESEARCH §Pattern 4 priceType table (lines 499–504) | role-match (parser tests against captured HTML — standard project pattern per ARCHITECTURE.md line 481) |
| `tests/unit/test_gate_detection.py` | test (unit) | — | `notebook.py` lines 161–168 (title-check), 174–179 (size + status check) | role-match |
| `tests/unit/test_stale_sku_detection.py` | test (unit) | — | `notebook.py` `CHALLENGE_HTML_MAX_SIZE = 30_000` line 49; MEMO §"Open Risks" stale-SKU pattern | role-match |
| `tests/unit/test_norm06_diff.py` | test (unit) | — | RESEARCH §"Code Examples" lines 957–982 | spec-only (greenfield) |
| `tests/unit/test_sanity_gate.py` | test (unit) | — | RESEARCH §"Code Examples" lines 938–954 | spec-only (greenfield) |
| `tests/integration/test_goldapple_smoke_probe.py` | test (integration) | — | RESEARCH §"Code Examples" lines 904–935 | spec-only |
| `tests/integration/test_goldapple_fetch_loop_mocked.py` | test (integration) | — | `notebook.py` run-loop lines 217–257 (mocked Camoufox) | role-match |
| `tests/integration/test_run_e2e_with_phase2_mocks.py` | test (integration) | — | `interfaces.py` Protocol contracts (Wave 0); ARCHITECTURE.md §"Pattern 1" example lines 169–204 | spec-only (greenfield) |

---

## Pattern Assignments

### `src/ga_crawler/interfaces.py` (interface, contract)

**Analog:** **No code analog** — Phase 2 modules do not exist yet. This file IS the Wave 0 contract that Phase 2 must conform to.

**Spec source:** `03-RESEARCH.md` lines 1077–1094 (Open Questions Q6 — recommendation block).

**Pattern (Protocol contracts to copy verbatim):**
```python
# from 03-RESEARCH.md lines 1078-1094
from typing import Protocol
from decimal import Decimal

class BrandAliasProtocol(Protocol):
    def lookup(self, brand_norm: str) -> list[str]: ...

class NormalizerProtocol(Protocol):
    def brand(self, raw: str) -> str: ...
    def name(self, raw: str) -> str: ...
    def volume(self, raw: str) -> tuple[Decimal, str, int] | None: ...
        # (amount, unit, multipack); None if unparseable

class SnapshotWriterProtocol(Protocol):
    def append(self, run_id: int, retailer: str, products: list) -> int: ...

class RunWriterProtocol(Protocol):
    def patch_stats(self, run_id: int, delta: dict) -> None: ...
    def get_stats(self, run_id: int) -> dict: ...
    def fail(self, run_id: int, reason: str) -> None: ...

class CrawlerProtocol(Protocol):
    """Per ARCHITECTURE.md §Pattern 3 — Phase 2 owns base.py with this Protocol;
    Phase 3 GoldappleFetcher conforms (sequential async __aenter__/__aexit__ context manager
    + .fetch_one(url) → dict)."""
    site: str
```

**Why no concrete analog:** Phase 2 not planned (per CONTEXT.md "Open dependency on Phase 2"); spike is monolithic and has no Protocol boundary. RESEARCH §A4–A5 mark Phase 2 contract drift as project risk → Wave 0 freezes the contract here.

---

### `src/ga_crawler/enumeration/goldapple_sitemap.py` (fetcher, request-response Tier 0)

**Analog:** `C:\Users\gstorepc\projects\ga_crawler\.planning\spikes\01-goldapple\notebook.py` (curl_cffi pattern is implicit — spike used curl_cffi for `_fetch_sitemap_pagevolume.py`, not in `notebook.py` directly). The most concrete extracted pattern is in **RESEARCH §Pattern 1, lines 326–349**.

**Imports pattern** (from RESEARCH lines 330–333):
```python
import re
from curl_cffi import requests
from selectolax.parser import HTMLParser
```

**Core pattern — sitemap-index → slug→URLs map** (RESEARCH lines 334–349, copy verbatim):
```python
SITEMAP_INDEX = "https://goldapple.kz/sitemap.xml"
PRODUCT_URL_RE = re.compile(r"^https://goldapple\.kz/(\d+)-([a-z0-9а-я-]+)$", re.IGNORECASE)

def fetch_sitemap_slugs() -> dict[str, list[str]]:
    """Returns {slug: [urls]} map. Each URL: /<numeric-id>-<slug>."""
    idx_xml = requests.get(SITEMAP_INDEX, impersonate="chrome", timeout=30).text
    sub_urls = re.findall(r"<loc>([^<]+)</loc>", idx_xml)
    slug_map: dict[str, list[str]] = {}
    for sub in sub_urls:
        sub_xml = requests.get(sub, impersonate="chrome", timeout=30).text
        for url in re.findall(r"<loc>([^<]+)</loc>", sub_xml):
            m = PRODUCT_URL_RE.match(url)
            if m:
                slug = m.group(2).lower()
                slug_map.setdefault(slug, []).append(url)
    return slug_map  # ~1,461 slugs / ~100,779 URLs (per spike 01-05 empirical)
```

**Retry/backoff pattern** — wrap `requests.get` with `tenacity` per RESEARCH §Pattern 5 (lines 681–699, see goldapple.py section below for the decorator template). Apply to `requests.get(SITEMAP_INDEX, ...)` and `requests.get(sub, ...)`.

**Persist + diff pattern** (RESEARCH lines 957–982, copy verbatim):
```python
def persist_sitemap_slugs(slugs: set[str], run_id: int, root: Path) -> Path:
    out = root / f"runs/{run_id}/sitemap-slugs.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(sorted(slugs)), encoding="utf-8")
    return out

def diff_new_slugs(current: set[str], previous_path: Optional[Path]) -> list[str]:
    if previous_path is None:
        return []  # first run — empty diff
    prev = set(previous_path.read_text(encoding="utf-8").splitlines())
    return sorted(current - prev)
```

**Empirical anchor:** `.planning/spikes/01-goldapple/sample-payloads/goldapple-sitemap.xml` (510 B, 3 sub-sitemaps) and `goldapple-all-urls.txt` (112,317 URLs). MEMO line 134 confirms `curl_cffi impersonate="chrome"` returned HTTP 200 plain (no JS challenge).

---

### `src/ga_crawler/enumeration/slug.py` (utility, pure transform)

**Analog:** **No code analog** — bilingual transliteration is greenfield in this codebase.

**Spec source:** `03-RESEARCH.md` §Pattern 2, lines 358–423.

**Imports pattern** (RESEARCH lines 361–362):
```python
import unicodedata
import re
```

**Core algorithm — copy verbatim** (RESEARCH lines 366–400):
```python
CYRILLIC_TO_LATIN = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh',
    'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
    'ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
    # KZ-specific
    'ә':'a','ғ':'g','қ':'q','ң':'n','ө':'o','ұ':'u','ү':'u','һ':'h','і':'i',
}

def _normalize_punct(s: str) -> str:
    """lowercase, NFKD, strip accents, non-alphanum→hyphen, collapse multi-hyphen."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9а-я]+", "-", s, flags=re.IGNORECASE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s

def slug_fy_bilingual(alias: str) -> list[str]:
    """Returns [ascii_slug, cyrillic_slug] (filter Nones)."""
    cyrillic_slug = _normalize_punct(alias)
    if not re.search(r"[а-яә-і]", cyrillic_slug):
        cyrillic_slug = None
    ascii_input = "".join(CYRILLIC_TO_LATIN.get(c, c) for c in alias.lower())
    ascii_slug = _normalize_punct(ascii_input)
    return [s for s in [ascii_slug, cyrillic_slug] if s]
```

**Intersect helper** (RESEARCH lines 402–422 — full body): copies viled_brands × aliases × sitemap_slugs into matched_urls + unmatched_brands tuple. Calls `BrandAliasProtocol.lookup()` from `interfaces.py`.

**Test cases (mandatory)** — RESEARCH lines 427–439, all 11 rows must be unit-tested.

---

### `src/ga_crawler/fetchers/goldapple.py` (fetcher, event-driven Tier 2 Camoufox)

**Analog (PRIMARY):** `C:\Users\gstorepc\projects\ga_crawler\.planning\spikes\01-goldapple\notebook.py` — refactor of `bootstrap` block + `fetch_one()`.

**Imports pattern** (`notebook.py` lines 24–34):
```python
import argparse
import asyncio
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog
from camoufox.async_api import AsyncCamoufox
from selectolax.parser import HTMLParser
```

**Operational constants** (`notebook.py` lines 41–49 — copy verbatim, hoist to config per CONTEXT D-308 placement):
```python
PAUSE_RANGE = (3.0, 5.0)            # D-04 random uniform
PAGE_TIMEOUT_MS = 60_000
GATE_POLL_DEADLINE_MS = 25_000      # 01-06b proven enough
GATE_POLL_STEP_MS = 500
CONSECUTIVE_BLOCK_LIMIT = 5         # D-03 stop-rule (still relevant for robustness)
RETRY_PER_URL = 1                   # D-13: timeout/exception retry разрешён
GATE_TITLE_MARKER = "checking"      # appears in "Gold Apple — checking device"
CHALLENGE_HTML_MAX_SIZE = 30_000    # GUN gate shell ~18KB; real app 200KB+
```

**Camoufox bootstrap pattern** (`notebook.py` lines 207–214, refactor into class `__aenter__`):
```python
async with AsyncCamoufox(
    headless=args.headless,
    geoip=True,
    locale=["ru-RU", "kk-KZ", "en-US"],
    humanize=True,
    persistent_context=True,
    user_data_dir=str(USER_DATA_DIR),
) as browser:
    page = browser.pages[0] if browser.pages else await browser.new_page()
```

**Profile lifecycle (D-311 fresh tmp profile)** — RESEARCH §Pattern 3 lines 461–490 — wrap the bootstrap above in a `__aenter__/__aexit__` class with:
- `tempfile.mkdtemp(prefix=f"camoufox-run-{run_id}-")` in `__init__`
- `shutil.rmtree(self.profile_dir, ignore_errors=True)` in `__aexit__` (always; per CONTEXT default)

**Core fetch pattern (gate-detection + state classification)** — `notebook.py` `fetch_one()` lines 128–191 (copy structure verbatim, refactor for class method):
```python
# notebook.py lines 149-191 — load-bearing logic:
async def fetch_one(self, page, url: str) -> dict:
    started = time.perf_counter()
    rec = {"url": url, "fetched_at": ..., "status": None, ...}
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        rec["status"] = response.status if response else None

        try:
            await page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass

        # Gate-detection poll loop — notebook.py lines 159-168
        elapsed = 0
        last_title = ""
        while elapsed < GATE_POLL_DEADLINE_MS:
            last_title = await page.title()
            if GATE_TITLE_MARKER not in last_title.lower():
                rec["gate_cleared"] = True
                rec["gate_cleared_after_ms"] = elapsed
                break
            await page.wait_for_timeout(GATE_POLL_STEP_MS)
            elapsed += GATE_POLL_STEP_MS
        rec["title"] = last_title

        html = await page.content()
        rec["html_size"] = len(html)

        # State classification (Pattern 4 detect_state) — notebook.py lines 174-185
        if not rec["gate_cleared"] and rec["html_size"] < CHALLENGE_HTML_MAX_SIZE:
            rec["block"] = True
            rec["block_reason"] = "gate_shell_not_cleared"
        elif rec["status"] not in (200, 304):
            rec["block"] = True
            rec["block_reason"] = f"http_{rec['status']}"
        else:
            rec["html"] = html  # caller dispatches to parser
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {repr(e)[:200]}"
        rec["block"] = True
        rec["block_reason"] = "exception"
    rec["timing_ms"] = int((time.perf_counter() - started) * 1000)
    return rec
```

**Retry pattern (CRAWL-04 tenacity wrapper)** — RESEARCH §Pattern 5 lines 682–699 — verbatim:
```python
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from playwright.async_api import TimeoutError as PWTimeout

class TransientFetchError(Exception): ...

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30),
    retry=retry_if_exception_type((TransientFetchError, PWTimeout)),
    reraise=True,
)
async def _goto_with_retry(page, url: str):
    response = await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    if response is None:
        raise TransientFetchError("no response")
    if response.status >= 500:
        raise TransientFetchError(f"5xx: {response.status}")
    return response
```

**Per-SKU isolation pattern (CRAWL-03)** — RESEARCH lines 701–711 (copy verbatim, calls into `interfaces.RunWriterProtocol.patch_stats(run_id, {...})` for failure counter).

**Run-loop with random pacing** — `notebook.py` lines 217–257; key load-bearing line:
```python
# notebook.py line 257
if i < len(urls):
    await asyncio.sleep(random.uniform(*PAUSE_RANGE))
```

**Logging** — `notebook.py` lines 51–58 — `structlog.configure(...)` with `JSONRenderer`. Phase 3 inherits the project-wide logger from `src/ga_crawler/obs/logging.py` (Phase 2 deliverable; mock as no-op until then).

---

### `src/ga_crawler/parsers/goldapple_microdata.py` (parser, transform)

**Analog (PRIMARY for detection):** `notebook.py` lines 94–125.

**Imports pattern** (`notebook.py` line 34 + RESEARCH line 512–514):
```python
from selectolax.parser import HTMLParser, Node
from dataclasses import dataclass
from typing import Optional
```

**Microdata-detection primitive** — `notebook.py` lines 94–110 — verbatim (foundation, NOT extraction):
```python
def has_microdata_price(html: str) -> tuple[bool, bool]:
    """Goldapple uses inline microdata. Returns (has_offer_marker, has_price_value)."""
    tree = HTMLParser(html)
    nodes = tree.css('meta[itemprop="price"]')
    if not nodes:
        return False, False
    has_value = False
    for n in nodes:
        v = (n.attributes.get("content") or "").strip()
        if v and v != "0":
            has_value = True
            break
    return True, has_value
```

**State classification (gate-shell vs stale-SKU vs real-PDP)** — RESEARCH §Pattern 4 lines 528–541 — verbatim:
```python
GATE_SHELL_MAX_BYTES = 30_000
GATE_TITLE_MARKER = "checking"

def detect_state(html: str, title: str) -> str:
    """Returns 'gate-shell' / 'stale-sku' / 'real-pdp'."""
    sz = len(html)
    if GATE_TITLE_MARKER in title.lower() and sz < GATE_SHELL_MAX_BYTES:
        return "gate-shell"
    if sz < GATE_SHELL_MAX_BYTES:
        return "stale-sku"
    return "real-pdp"
```

**Core extraction with priceType discrimination (PARSE-02 inverted, PARSE-03 strengthened)** — RESEARCH §Pattern 4 lines 543–672, copy verbatim. Key sub-pieces:
- `_extract_top_level_offer(tree)` — lines 543–578 — selects the `[itemprop="offers"][itemtype$="/Offer"]` block whose `meta[itemprop="price"]` is NOT inside `priceSpecification` and has NO `StrikethroughPrice`/`ListPrice` sibling priceType + NOT in "при авторизации" (Gold Card) section.
- `_extract_strikethrough(tree)` — lines 580–590 — picks the `priceSpecification` block whose `priceType` href contains `StrikethroughPrice`.
- `parse_pdp(html, url)` — lines 592–672 — full record builder; returns `Optional[GoldappleRawProduct]`; returns `None` on gate-shell, stale-SKU, missing required fields, or PARSE-04 sanity-fail (`100 ≤ price ≤ 1_000_000`).

**Output dataclass** — RESEARCH lines 516–526 (copy verbatim — `GoldappleRawProduct`).

**Empirical anchor:** `.planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html` is the validation fixture for every selector — RESEARCH §Pattern 4 explicitly says "verified against" this file (line 511). Tests must round-trip parse → dataclass against this HTML.

**Anti-pattern (do NOT copy):** `notebook.py` `has_jsonld_product()` lines 61–91 — this is the JSON-LD path which goldapple does NOT emit (only `OfferShippingDetails`). It is preserved in spike for evidence-collection only; production goldapple parser must NOT JSON-LD-first. See RESEARCH §"Anti-Patterns to Avoid" line 717.

---

### `src/ga_crawler/runner/gates.py` (runner-gate, request-response)

**Analog:** None directly. Uses `GoldappleFetcher` analog (above) + RESEARCH spec.

**Smoke probe pattern (D-312)** — RESEARCH lines 906–935, copy verbatim.

**Final M-gate (D-308/D-309)** — RESEARCH lines 944–946:
```python
def final_m_gate(goldapple_count: int, M: int = 1000) -> bool:
    return goldapple_count >= M
```

**Auto-suggest M (D-310)** — RESEARCH lines 948–954:
```python
import statistics

def auto_suggest_m(history_counts: list[int]) -> Optional[int]:
    if len(history_counts) < 4:
        return None
    median = statistics.median(history_counts[-4:])
    return int(0.7 * median)
```

**Smoke URL list (3 hardcoded Givenchy URLs from spike)** — RESEARCH lines 908–913 (verify they match the per-URL outcomes table in `tier2-camoufox-kz-results.json`; A12 says do NOT include `7681000002-...` row 0).

**Stats writer integration:** on smoke failure / sanity gate failure, call `interfaces.RunWriterProtocol.fail(run_id, reason)` + `patch_stats(run_id, {...})`. See stats.py below.

---

### `src/ga_crawler/runner/stats.py` (utility, transform)

**Analog:** None — greenfield.

**Spec source:** RESEARCH §"Open Questions" Q4, lines 1043–1066 (flat schema with phase-namespace prefix).

**Pattern (the goldapple. namespace keys):**
```python
# from 03-RESEARCH.md lines 1051-1066 — keys Phase 3 writes:
GOLDAPPLE_STATS_KEYS = (
    "goldapple.fetch_count",
    "goldapple.fetch_failures",
    "goldapple.gate_shell_count",
    "goldapple.stale_count",
    "goldapple.parse_failures",
    "goldapple.unmatched_viled_brands",
    "goldapple.unmatched_goldapple_slugs_new",
    "goldapple.smoke_pass",
    "goldapple.smoke_diagnostics",
    "goldapple.fetch_duration_seconds",
    "goldapple.mean_fetch_seconds",
    "goldapple.camoufox_version",
    "goldapple.auto_suggest_m",
)
```

Module exposes a `GoldappleStatsBuilder` (or pure functions) that accumulates an in-memory delta dict during the run, then calls `RunWriterProtocol.patch_stats(run_id, delta)` once at end-of-phase.

---

### Test fixtures (`tests/fixtures/goldapple/`)

**Analog:** existing spike `sample-payloads/` files. **Wave 0 task: copy verbatim.**

| Test fixture path | Source spike file | Notes |
|---|---|---|
| `tests/fixtures/goldapple/_debug-product-page.html` | `.planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html` | Verbatim. Givenchy PDP — primary parser fixture (RESEARCH §Pattern 4 line 511). |
| `tests/fixtures/goldapple/gate-shell.html` | `.planning/spikes/01-goldapple/sample-payloads/goldapple-product-html-1.html` | Verbatim copy with rename. ~18 KB GUN challenge shell sample (MEMO §"What was found" lines 78–81). |
| `tests/fixtures/goldapple/sitemap-1-excerpt.xml` | `.planning/spikes/01-goldapple/sample-payloads/goldapple-sitemap-1-excerpt.xml` | Verbatim. First 50 URL entries — feeds slug-fy unit tests. |
| `tests/fixtures/goldapple/tier2-camoufox-kz-results.json` | `.planning/spikes/01-goldapple/sample-payloads/tier2-camoufox-kz-results.json` | Verbatim. Empirical baseline (99/100). Used by `test_stale_sku_detection.py` to assert detection on row 0. |
| `tests/fixtures/goldapple/_debug-jsonld-blocks.json` | `.planning/spikes/01-goldapple/sample-payloads/_debug-jsonld-blocks.json` | Verbatim. Proof goldapple emits ONLY `OfferShippingDetails` — used as anti-fixture in parser tests. |
| `tests/fixtures/goldapple/stale-sku-9.5kb.html` | **No spike file** — must be re-fetched at plan-time from `https://goldapple.kz/7681000002-givenchy-pour-homme-blue-label` (per MEMO line 39, A12) | Best alternative: synthesize from spike result row 0 metadata (status=200, html_size≈9500, title cleared). |

---

### Test files (`tests/unit/*.py`, `tests/integration/*.py`)

**Imports pattern** (project-wide, derived from CLAUDE.md stack):
```python
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "goldapple"
```

**Per-file pattern source:**

| Test file | Pattern source |
|-----------|---------------|
| `test_slug_fy.py` | RESEARCH lines 427–439 — 11 mandatory test cases as `@pytest.mark.parametrize` table |
| `test_goldapple_microdata_parser.py` | Round-trip `parse_pdp()` against `_debug-product-page.html` fixture; assert priceType filtering on synthetic StrikethroughPrice / ListPrice / Gold Card snippets per RESEARCH lines 499–504 priceType table |
| `test_gate_detection.py` | `notebook.py` lines 161–179 → `detect_state()` and gate-poll loop; cases: title="checking…" + size<30k → gate-shell; title=clean + size<30k → stale-sku; size≥30k → real-pdp |
| `test_stale_sku_detection.py` | Use spike `tier2-camoufox-kz-results.json` row 0 as the canonical stale-SKU case; MEMO §"Open Risks" line 39 spec |
| `test_norm06_diff.py` | RESEARCH lines 957–982 — 3 cases: first-run (empty diff), additions, removals (removals are ignored per code) |
| `test_sanity_gate.py` | RESEARCH lines 944–954 — boundary tests at M=1000 (999/1000/1001), auto-suggest at len(history) ∈ {3, 4, 5} |
| `test_goldapple_smoke_probe.py` (integration) | RESEARCH lines 906–935; mock `GoldappleFetcher.fetch_one` to return canned dicts |
| `test_goldapple_fetch_loop_mocked.py` (integration) | Mock Camoufox via spike `notebook.py` run-loop structure (lines 217–257), assert per-SKU isolation + stats accumulation + D-03 stop-rule (5 consecutive blocks) |
| `test_run_e2e_with_phase2_mocks.py` (integration) | Mock `interfaces.{BrandAlias,Normalizer,SnapshotWriter,RunWriter}Protocol`; ARCHITECTURE.md §Pattern 1 example lines 169–204 as orchestration template |

---

## Shared Patterns

### Stealth / Anti-bot — Camoufox Bootstrap

**Source:** `notebook.py` lines 207–214 + RESEARCH §Pattern 3 lines 461–490
**Apply to:** `fetchers/goldapple.py` only. Do NOT use for sitemap fetch (overkill — Tier 0 curl_cffi is sufficient per RESEARCH §Pattern 1).

Always six locked kwargs (D-04 / SKILL operational constants):
```python
AsyncCamoufox(
    headless=True,                          # configurable for dev
    geoip=True,                             # SKILL-locked
    locale=["ru-RU", "kk-KZ", "en-US"],     # SKILL-locked
    humanize=True,                          # SKILL-locked
    persistent_context=True,                # D-04 — cookies live across fetches WITHIN run
    user_data_dir=str(self.profile_dir),    # tempfile.mkdtemp per D-311
)
```

### Retry + backoff (CRAWL-04)

**Source:** RESEARCH §Pattern 5 lines 682–699 (tenacity decorator template)
**Apply to:** every network call —
- `enumeration/goldapple_sitemap.py::fetch_sitemap_slugs()` — both `requests.get` calls
- `fetchers/goldapple.py::_goto_with_retry()` — `page.goto`
- `runner/gates.py::smoke_probe()` — implicit through fetcher

Decorator (verbatim):
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30),
    retry=retry_if_exception_type((TransientFetchError, PWTimeout)),
    reraise=True,
)
```

### Per-SKU isolation (CRAWL-03)

**Source:** RESEARCH §Pattern 5 lines 701–711
**Apply to:** every per-URL operation in `fetchers/goldapple.py` and `runner/gates.py::smoke_probe`. A single SKU's exception MUST NOT bubble up to terminate the run loop.

Pattern:
```python
try:
    response = await _goto_with_retry(page, url)
    # ... title-check, content extract, parse ...
    return record
except Exception as e:
    log.error("fetch_failed", url=url, error=str(e), error_type=type(e).__name__)
    stats["fetch_failures"] = stats.get("fetch_failures", 0) + 1
    return None
```

### Structured logging (`structlog` JSONRenderer)

**Source:** `notebook.py` lines 51–58 — `structlog.configure(processors=[add_log_level, TimeStamper(fmt="iso"), JSONRenderer()])`
**Apply to:** all production modules. Bind `run_id`, `retailer="goldapple"`, `url` (where relevant) on every log call. Use `log.bind(...)` at top of fetch loops.

CLAUDE.md confirms `structlog 25.x` is the project standard.

### Rate limiting (3–5s random uniform between fetches)

**Source:** `notebook.py` lines 41 (`PAUSE_RANGE = (3.0, 5.0)`) + 257 (`asyncio.sleep(random.uniform(*PAUSE_RANGE))`)
**Apply to:** `fetchers/goldapple.py` fetch loop ONLY (CONTEXT line 102: viled uses `(2, 2)`; goldapple uses `(3, 5)`). Concurrency=1 per CONTEXT line 102 + RESEARCH line 207.

### State classification (gate-shell / stale-SKU / real-PDP)

**Source:** `notebook.py` lines 174–179 (binary block check) + RESEARCH §Pattern 4 lines 531–541 (three-axis classifier)
**Apply to:** `fetchers/goldapple.py` (block decision) AND `parsers/goldapple_microdata.py::detect_state` (parse decision). Both modules call the same `detect_state()` function imported from parser; this prevents Pitfall 4 (gate-shell vs stale-SKU conflation poisons sanity-gate).

### Stats accumulation contract

**Source:** RESEARCH lines 1043–1066 (flat `goldapple.*` namespace) + `interfaces.RunWriterProtocol.patch_stats`
**Apply to:** every counter-increment in fetcher/parser/gates. Call `RunWriterProtocol.patch_stats(run_id, {"goldapple.fetch_count": +1})` at end of phase, not per-fetch (atomic merge through `json_patch` per RESEARCH).

---

## No Analog Found

Files truly greenfield (no closest match anywhere — implement from RESEARCH spec):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/ga_crawler/interfaces.py` | interface | contract | Phase 2 not implemented; this file is the contract Phase 2 must conform to. Spec: RESEARCH §Q6. |
| `src/ga_crawler/enumeration/slug.py` | utility | transform | Bilingual Cyrillic/Latin transliteration is novel to this project. Spec: RESEARCH §Pattern 2 (lines 358–423). |
| `src/ga_crawler/runner/gates.py` | runner-gate | request-response | Smoke + sanity + auto-suggest are Phase 3-specific. Spec: RESEARCH §"Code Examples" lines 906–954. |
| `src/ga_crawler/runner/stats.py` | utility | transform | `runs.stats` namespace and accumulator are Phase 3-specific. Spec: RESEARCH §Q4 (lines 1043–1066). |

**Planner note:** for these four files, planner generates code directly from RESEARCH spec text (verbatim copy of the example blocks is acceptable — they are the contract, not just illustration).

---

## Metadata

**Analog search scope:**
- `C:\Users\gstorepc\projects\ga_crawler\.planning\spikes\01-goldapple\notebook.py` (PRIMARY analog — 322 lines fully read)
- `C:\Users\gstorepc\projects\ga_crawler\.planning\spikes\01-goldapple\sample-payloads\` (28 files inventoried; 5 marked for verbatim copy as fixtures)
- `C:\Users\gstorepc\projects\ga_crawler\.planning\spikes\01-goldapple\MEMO.md` (signed-off decisions; cited inline)
- `C:\Users\gstorepc\projects\ga_crawler\.planning\research\ARCHITECTURE.md` (modular monolith template — used for orchestration analogy in `test_run_e2e_with_phase2_mocks.py`)
- `C:\Users\gstorepc\projects\ga_crawler\.planning\phases\03-goldapple-crawl\03-RESEARCH.md` (1293 lines — module decomposition lines 243–318, patterns 320–712, code examples 850–982, open questions 1023–1100)

**Files scanned:** 5 high-signal docs + 28 spike sample-payload entries + 15 spike `_*.py` scripts (only `notebook.py` is a production-quality analog; the rest are throwaway research scripts per Phase 1 D-16).

**Codebase analog density:** LOW (greenfield project; no `src/ga_crawler/` exists yet — verified by absence in research notes and Phase 2 unplanned status). Spike notebook is the single production-pattern reference. Test-fixture density is HIGH because spike captured high-quality real payloads.

**Pattern extraction date:** 2026-05-06

---

## PATTERN MAPPING COMPLETE
