---
phase: 02
plan: 01
wave: 0
probe_date: 2026-05-07
verdict: VERIFIED-WITH-CASCADING-REVISIONS
---

# Wave 0 viled.kz Probe — A1, A2, A3, A4, A10 Verification

Live probe ran 2026-05-07 against viled.kz via `curl_cffi.requests.get(url, impersonate="chrome", timeout=30)`. Every URL returned HTTP 200 first try; no anti-bot signals. 5 fixtures pinned under `tests/fixtures/viled/`. This memo locks down field paths and import paths for Plan 04 (parser implementation).

## Scope-narrowing reality-check

D-223 framed `/men/catalog/1310` and `/women/catalog/1310` as **beauty + парфюмерия only**. The probe shows otherwise:

| catalog | total SKUs | totalPages × pageSize |
|---------|-----------|----------------------|
| `/men/catalog/1310` | **1947** | 33 × 60 |
| `/women/catalog/1310` | **5750** | 96 × 60 |

Combined ≈ 7697 SKUs across 129 catalog pages. This is materially bigger than D-226's "100–600 SKUs" estimate — `/catalog/1310` is the **full luxury catalog**, not a beauty subtree. The catalog endpoint id `1310` is `viled` root catalog id, not a beauty filter. Plan 04 should expect ~8k catalog pages × ~135 KB = ~1 GB total HTML download budget if all pages are crawled. **Actionable for Plan 04**: re-confirm the scope-narrowing assumption with operator OR plan a category filter that hits only beauty SKUs (likely via `groupId` / `catalogId` filter on the items.content[] response).

_Cascade target: 02-CONTEXT.md D-223 ("ТОЛЬКО косметика+парфюмерия") + D-226 (URL pool 100-600). Both must be revisited before Plan 04._

## A1 — `in_stock` field path (REVISED — cascading)

**ASSUMED in 02-RESEARCH.md §Pattern 1**: `attributes[0].in_stock: bool`.

**FOUND**: Field name **does not exist**. `attributes[0]` exposes `{id, price, realPrice, currency, itemImages, enableDiscount, attributes, article, namePlates}`. There is **no boolean `in_stock`** anywhere in `pageProps`.

**Stock signal lives on `props.pageProps.item`, not `attributes`:**

| field | type | observed values | semantic |
|-------|------|-----------------|----------|
| `item.count` | `int` | 2, 23, 57, 74, 146, 547, 760, ... | inventory count for this SKU |
| `item.purchaseType` | `str` | `"ONLINE"` (every probed SKU) | purchase channel; `"PREORDER"` likely the preorder marker |

**Plan 04 must use:**
```python
def detect_stock_state(pp: dict) -> StockState:
    item = pp.get("item") or {}
    count = item.get("count")
    if not isinstance(count, int):
        return StockState.UNKNOWN
    if count == 0:
        return StockState.OUT_OF_STOCK
    if item.get("purchaseType") == "PREORDER":  # to be verified empirically
        return StockState.UNAVAILABLE
    return StockState.IN_STOCK
```

**Status**: VERIFIED with REVISED path — RESEARCH §Pattern 1 must be amended in Plan 04 (replace `attributes[0].in_stock` → `item.count > 0`).

**Caveat**: **No OOS fixture pinned**. 6 sampled PDPs all returned `count > 0` (range 2..760). Plan 04 must synthesize a `viled-pdp-out-of-stock.html` (clone canonical and patch `count = 0`) for unit-test coverage; first weekly production run will surface a real one for re-pin.

## A2 — discount semantics (VERIFIED)

**ASSUMED**: discount = `attributes[0].price > attributes[0].realPrice`.

**FOUND**: confirmed on PDP `/item/367251` (men/perfume): `attributes[0].price=356745`, `realPrice=419700`. So **price (current) < realPrice (was)** — the convention is **inverted from the assumption**. Field semantics for Plan 04:

| field | meaning |
|-------|---------|
| `attributes[0].price` | **current selling price** (after discount, in tiyn — ₸ × 100? actually tenge whole-units, no decimals — see currency note below) |
| `attributes[0].realPrice` | **MSRP / pre-discount price** |
| `attributes[0].enableDiscount` | bool flag — `True` when item is on sale |
| catalog row `it.minPrice` / `it.realMinPrice` | catalog mirror (smallest variant price) |

**Discount detection (Plan 04 PARSE-03)**:
```python
price = a0["price"]; real = a0["realPrice"]; flag = a0.get("enableDiscount")
current_price = price                            # what customer pays now
was_price = real if (flag is True and real != price) else None  # only set if discounted
```

**Currency**: `attributes[0].currency = "₸"`; `initialState.checkout.cart.currency = "KZT"` (ISO). Plan 04 hardcodes `currency_norm="KZT"` (per STATE.md `viled currency: ₸ → KZT hardcoded`).

**Status**: VERIFIED. RESEARCH §Pattern 1 / §Pattern 2 already implicitly assumed this; no doc change needed beyond clarifying which is current vs. was. Discounted fixture **pinned** (`viled-pdp-discounted.html`, id=367251, price 356745 < real 419700, ratio ~85%).

## A3 — catalog accessibility (VERIFIED)

| URL | HTTP | bytes | `__NEXT_DATA__` present | items.content len |
|-----|------|-------|-------------------------|-------------------|
| `/men/catalog/1310` | **200** | 238 212 | yes | 60 |
| `/women/catalog/1310` | **200** | 255 108 | yes | 60 |

No login redirect, no 403, no Cloudflare challenge. `curl_cffi.impersonate="chrome"` Tier 0 sufficient. Pitfall 8 fallback (sitemap+brand allowlist) is **NOT** required.

**Status**: VERIFIED.

## A4 — pagination metadata (REVISED — cascading)

**ASSUMED** (RESEARCH §Pattern 2): `pageProps.products[]` + `pageProps.totalCount` + `pageProps.currentPage`.

**FOUND**: keys are nested under `pageProps.items` (not at pageProps top level), and the names differ:

```
props.pageProps = {
    "items": {
        "content":     [<Item>, ...],   # 60 entries on page 1, list of catalog rows
        "pageNumber":  1,                # 1-indexed
        "totalPages":  33,               # men=33, women=96
        "total":       1947,             # men=1947, women=5750
        "pageSize":    60,
    },
    "filters": {...},
    "sorts":   [{"name":..., "value":...}, ...],
    "_nextI18Next": {...},
}
```

Catalog **row** shape (different from PDP `item`/`attributes` shape):
```
items.content[i] = {
    "id":             <int>,           # used for /item/{id} fetch
    "enableDiscount": <bool>,
    "realMinPrice":   <int>,           # was-price for the cheapest variant
    "minPrice":       <int>,           # current price for the cheapest variant
    "imageUrl":       <str>,
    "hasGift":        <bool>,
    "isForKaspiJuma": <bool>,
    "kaspiJumaNameplateUrl": <str|null>,
    "season":         <null|str>,
    "brandName":      <str>,           # human-readable brand
    "groupName":      <str>,           # human-readable product name
    "isFavourite":    <bool>,
    "currency":       "₸",
    "images":         [<str>, ...],
    "collectionTypes":[<str>, ...],
    "namePlates":     [<dict>, ...],   # promo badges
    "attributes":     [<dict>, ...],   # variant rollup
}
```

**Plan 04 catalog enumerator (CRAWL-01)**:
```python
def enumerate_catalog(base_url: str) -> list[str]:
    urls = []
    page = 1
    while True:
        nd = extract_next_data(fetch(f"{base_url}?page={page}").text)
        block = nd["props"]["pageProps"]["items"]
        urls.extend(f"https://viled.kz/item/{r['id']}" for r in block["content"])
        if page >= block["totalPages"]:
            break
        page += 1
        time.sleep(2.0)
    return urls
```

**Pagination caveat**: `?page=N` query param did NOT change the response in the probe (men page 2/3/5/10 all returned the same 238 212-byte HTML as page 1). Two explanations are possible — Plan 04 must verify in Wave 1:

1. **Server-side render only emits page 1 in HTML; subsequent pages load via Next.js `_next/data/{buildId}/...json` route on client navigation.** This is the common Next.js SSR + ISR pattern.
2. **Different query-param convention** (e.g., `pageNumber=2`, `p=2`, or path-segment `/men/catalog/1310/page/2`).

**Recommended Plan 04 strategy**: try the internal Next.js data route first (`https://viled.kz/_next/data/<buildId>/men/catalog/1310.json?page=2`), fall back to the path-segment style if that fails. The `buildId` is in `nd["buildId"]` of the page-1 response.

**Status**: VERIFIED that `__NEXT_DATA__` carries pagination metadata, but **REVISED** key names (`items.content/pageNumber/totalPages/total/pageSize`) and **OPEN QUESTION** on the actual page-2+ fetch URL convention. Cascading to Plan 04 Wave 1.

## A10 — `curl_cffi` exception class import path (REVISED — cascading)

**ASSUMED** (RESEARCH §Pattern, Pitfall 1): `from curl_cffi.requests.errors import RequestsError, Timeout`.

**FOUND**: `curl_cffi.requests.errors` does **NOT** export `Timeout`. Available members: `CookieConflict, CurlError, RequestsError, SessionClosed`.

**The full exception stack lives in `curl_cffi.requests.exceptions`** (note: `exceptions`, not `errors`):
```python
from curl_cffi.requests.exceptions import (
    RequestException,   # base; subclass of curl_cffi.curl.CurlError + OSError + Exception
    Timeout,            # base for ConnectTimeout / ReadTimeout
    ConnectTimeout,
    ReadTimeout,
    ConnectionError,    # alias to requests-style
    HTTPError,
    SSLError,
    ProxyError,
    RetryError,
    InvalidURL,
    TooManyRedirects,
)
```

`requests.errors.RequestsError` aliases `requests.exceptions.RequestException` (verified via MRO walk).

**Plan 04 tenacity retry policy** must import from `.exceptions`:
```python
from curl_cffi.requests.exceptions import (
    ConnectionError as CCConnectionError,
    HTTPError,
    RequestException,
    Timeout,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(2, 30),
    retry=retry_if_exception_type((Timeout, CCConnectionError, HTTPError, RequestException)),
)
def fetch(url): ...
```

**Status**: VERIFIED with REVISED import path. **CASCADING**: Plan 04 RESEARCH §Pattern 4 (retry policy) and §Pitfall 1 must be updated to import from `curl_cffi.requests.exceptions`. The failing-import was caught **before** any production code was written — Wave 0 working as designed.

## Decisions cascading to Plan 04

| Cascade | Effect on Plan 04 |
|---------|-------------------|
| A1 REVISED — no `in_stock` boolean | PARSE-06 stock-state derivation reads `item.count` + `item.purchaseType`, not `attributes[0].in_stock`. RESEARCH §Pattern 1 must be amended. Synthetic OOS fixture (clone + patch `count=0`) needed in Plan 04 Wave 1. |
| A4 REVISED — pagination keys live under `pageProps.items.{content,total,totalPages,pageSize,pageNumber}` | CRAWL-01 enumerator code uses these names verbatim. RESEARCH §Pattern 2 must be amended. |
| A4 OPEN — `?page=N` does not paginate via SSR HTML | Plan 04 Wave 1 must verify pagination URL convention (Next.js internal data route vs path-segment). Defer to first impl spike, not blocking now. |
| A10 REVISED — exception classes at `curl_cffi.requests.exceptions`, not `.errors` | Plan 04 retry policy import line: `from curl_cffi.requests.exceptions import RequestException, Timeout, ConnectTimeout, ReadTimeout, ConnectionError as CCConnectionError, HTTPError`. RESEARCH §Pattern 4 + §Pitfall 1 must reflect this. |
| Catalog scope wider than D-223 assumed | Plan 04 must clarify with operator whether scope-narrowing means category filter (operator picks specific `catalogId` / `groupId` subset) or trust the 1310 root and accept ~8k SKUs. D-201 N=100 seed is now obviously low — but auto-suggest will dial it up after 4 weeks. No immediate change to seed; document for future-Mirzhan to revisit. |
| Discount discounting = `price < realPrice` (semantically inverted convention) | PARSE-03 — `current_price = a0.price`, `was_price = a0.realPrice if a0.enableDiscount else None`. Already locked in RESEARCH; this probe just confirms field naming. |

## Fixture inventory

| File | Bytes | Source | Purpose |
|------|-------|--------|---------|
| `tests/fixtures/viled/viled-pdp-407682.html` | 145 011 | `https://viled.kz/item/407682` (Alice+Olivia "Кружевное боди") | Canonical PDP — non-discount, non-OOS, non-multipack. Drives PARSE-01/02 happy path. |
| `tests/fixtures/viled/viled-pdp-discounted.html` | 132 679 | `https://viled.kz/item/367251` (Frederic Malle perfume) | Discounted PDP: price=356745 < realPrice=419700, enableDiscount=True. Drives PARSE-03 was_price assertion. |
| `tests/fixtures/viled/viled-pdp-multipack.html` | 132 188 | `https://viled.kz/item/398309` (men page-1 кит/набор candidate) | Multipack PDP — name carries kit/set token. Drives NORM-04 multipack detection. |
| `tests/fixtures/viled/viled-pdp-out-of-stock.html` | DEFERRED | none of 6 sampled PDPs had count==0 | Plan 04 Wave 1 task: clone canonical PDP, patch `props.pageProps.item.count` to 0, save as OOS fixture. Real one will surface in first weekly run. |
| `tests/fixtures/viled/viled-catalog-men-1310-page1.html` | 238 212 | `https://viled.kz/men/catalog/1310` | Page-1 catalog HTML (men). Drives CRAWL-01 enumeration tests. |
| `tests/fixtures/viled/viled-catalog-women-1310-page1.html` | 255 108 | `https://viled.kz/women/catalog/1310` | Page-1 catalog HTML (women). |
| `tests/fixtures/viled/viled-nextdata-shape.json` | 410 240 | extracted from canonical PDP | Pretty-printed `__NEXT_DATA__` for human inspection / cross-reference. Replaces the spike-01 stale shape file. |
| `tests/fixtures/viled/_probe-log.json` | 440 | probe runtime | HTTP status + bytes per request. |

## Network behavior

- **8 fetches** (3 catalog + 5 PDP retries during hunt) against viled.kz, all HTTP 200 first try.
- 2.0 s pause between fetches (D-225). No throttling, no 429, no anti-bot challenge.
- `impersonate="chrome"` only — no proxy, no Patchright/Camoufox. **viled fully Tier 0 confirmed for catalog endpoints, not just `/item/{id}`** (extends spike-01-07 finding).
- Probe scripts deleted after capture per spike convention (see commit).

## Addendum 2026-05-07 — A4 follow-up probe (Plan 02-04 implementation)

During Plan 02-04 Task 2 implementation, an additional live probe was run to
resolve A4's open question: *what URL convention actually paginates the
catalog?*

**Tested URL conventions** (all against `https://viled.kz/men/catalog/1310`):

| Convention                                                | HTTP | bytes   | `pageProps.items.pageNumber` | content[0].id |
|-----------------------------------------------------------|------|---------|------------------------------|---------------|
| `?page=2`                                                 | 200  | 238 212 | **1**                         | 408872        |
| `?pageNumber=2`                                           | 200  | 238 212 | **1**                         | 408872        |
| `?p=2`                                                    | 200  | 238 212 | **1**                         | 408872        |
| `?offset=60`                                              | 200  | 238 212 | **1**                         | 408872        |
| `?from=60`                                                | 200  | 238 212 | **1**                         | 408872        |
| `/page/2`                                                 | 404  | —       | —                            | —             |
| `/2`                                                      | 404  | —       | —                            | —             |
| `_next/data/{buildId}/men/catalog/1310.json?page=2`       | 200  | 215 357 | **1**                         | 408872        |
| `_next/data/{buildId}/men/catalog/1310.json?pageNumber=2` | 200  | 215 357 | **1**                         | 408872        |
| `/api/items?catalogId=1310&page=2` (and 4 variants)       | 404  | 0       | —                            | —             |

**Verdict**: NONE of the public URL conventions paginate the SSR HTML or the
Next.js `/_next/data` route. The catalog endpoint always returns page 1
regardless of query params. Inspection of the page-1 HTML found no `/api/`
references, no `getServerSideProps` hints, and no fetch hooks pointing at a
specific endpoint. The pagination is presumably driven by client-side JS via
an XHR endpoint that requires a CSRF token or other request signing not
exposed through a simple GET.

**Plan 02-04 implementation response** (Rule 3 deviation — auto-fix blocking):

- `enumeration/viled_catalog.py::fetch_catalog_urls` walks page 1, then
  attempts `?page=2..N` for `totalPages` per A4 metadata.
- A runtime guard inspects each subsequent response: if `pageNumber` is
  unchanged or `content[0].id` matches page 1, the loop logs
  `catalog_pagination_not_supported` and breaks early.
- v1 effective output: **120 SKUs** (60 men + 60 women) instead of 7,697.
- Sufficient for D-201 `sanity_gate_n=100` catastrophic-failure detector;
  the auto-suggest mechanism (D-203) takes over week-5 onward.
- Resolution path deferred to Phase 3/7 ops follow-up — likely candidates:
  reverse-engineer the XHR pagination call by capturing a real browser
  session, or escalate to a categorised crawl per `groupId` filter on
  `pageProps.filters`.

This finding closes A4 as **REVISED + LIMITATION-DOCUMENTED**.
