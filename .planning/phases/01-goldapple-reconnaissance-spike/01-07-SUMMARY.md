---
phase: 01-goldapple-reconnaissance-spike
plan: 07
subsystem: research

tags: [recon, viled, curl_cffi, feasibility, jsonld, next_data, parse-02-hot-data]

requires:
  - phase: 01-goldapple-reconnaissance-spike
    provides: "curl_cffi 0.15.0 + selectolax (plan 01-02); committed rate-limit viled=2s sequential (plan 01-04); viled is Next.js with __NEXT_DATA__ pattern (plan 01-04 privacy + 01-05 homepage); spike directory skeleton + notebook-viled.py stub (plan 01-01)"

provides:
  - "Empirical confirmation: viled.kz fully Tier 0 — 15/15 HTTP 200 via curl_cffi impersonate=chrome with 2s pause; no anti-bot, no challenges, no proxy needed"
  - "Critical finding: viled does NOT use JSON-LD schema.org on product pages (0/15); D-14-style success proxy не применим к viled"
  - "Compensating finding: viled embeds rich product data in __NEXT_DATA__ Next.js SSR JSON blob (15/15)"
  - "Phase 2 PARSE-02 hot-data table: full v1-schema field-paths in __NEXT_DATA__ (price/realPrice/brandName/name/sizeType/Размер/currency)"
  - "Side-deliverable: viled.kz/sitemap.xml plain-deliverable; sitemap-index with 9 sub-sitemaps (women/men/kids/collection/lookbooks/news/nav); 42,294 product URLs total under /item/<numeric_id> route"
  - "Side-deliverable: viled URL pattern is /item/<monotonic_numeric_id>; sitemap-driven enumeration only (no ?page=N pagination)"
  - "Side-deliverable: was_price directly available via realPrice field — Phase 2 v1 schema requirement satisfiable from week 1"
  - "Side-deliverable: viled prices are integer KZT (no decimals, no formatted strings); currency display = '₸' unicode"
  - "Reproducible feasibility script .planning/spikes/01-goldapple/notebook-viled.py (replaces 01-01 stub)"
  - "Reproducible URL harvester _fetch_viled_urls.py (substitutes Task 1 checkpoint:human-action)"
  - "Phase 2 hot-data inspector _inspect_viled_nextdata.py"

affects: [Phase 2, plan 01-11]

tech-stack:
  added: []
  patterns:
    - "Per-URL feasibility metrics pattern: HTTP status + timing_ms + content-length + content-type + JSON-LD presence (per @type) + JSON-LD price + __NEXT_DATA__ presence — record for every fetch in summary JSON for downstream auditability."
    - "viled product extraction pattern: regex-extract `<script id=\"__NEXT_DATA__\">{...}</script>` JSON blob, then `.props.pageProps.{item, attributes}` for canonical fields (NOT JSON-LD)."
    - "Diversified URL sampling: when downsizing N URLs from a large pool, use step-stride (`pool[::step]`) instead of `pool[:15]` to spread across the catalog (e.g., old IDs + new IDs both represented)."

key-files:
  created:
    - ".planning/spikes/01-goldapple/_fetch_viled_urls.py"
    - ".planning/spikes/01-goldapple/_inspect_viled_nextdata.py"
    - ".planning/spikes/01-goldapple/sample-payloads/viled-product-urls.txt"
    - ".planning/spikes/01-goldapple/sample-payloads/viled-sitemap.xml"
    - ".planning/spikes/01-goldapple/sample-payloads/viled-sitemap-1-excerpt.xml"
    - ".planning/spikes/01-goldapple/sample-payloads/viled-fetch-results.json"
    - ".planning/spikes/01-goldapple/sample-payloads/viled-nextdata-shape.json"
  modified:
    - ".planning/spikes/01-goldapple/notebook-viled.py"
    - ".planning/spikes/01-goldapple/MEMO.md"

key-decisions:
  - "Phase 2 PARSE-02 for viled = __NEXT_DATA__-first extraction (NOT JSON-LD-first as for goldapple per D-14). viled has zero JSON-LD on product pages (empirically verified 0/15)."
  - "Phase 2 viled enumeration = sitemap-only (https://viled.kz/sitemap.xml → 9 sub-sitemaps → /item/<id>). No HTML pagination crawl, no infinite-scroll AJAX. 42,294 product URLs available for full catalog enumeration."
  - "Phase 2 viled fetch layer = curl_cffi (Tier 0). No headless browser, no proxy, no warm session. Stateless GETs at 2s pause."
  - "Currency mapping for Phase 2 NORMALIZE-01: '₸' (display) → 'KZT' (programmatic). Hardcode for viled (single-currency site)."
  - "Phase 2 v1 schema can populate was_price directly from realPrice field — no retroactive backfill needed (matches STATE.md decision)."
  - "Task 1 checkpoint:human-action substituted by autonomous sitemap probe (same Rule 3 pattern as 01-05 Task 1) — user MEMORY.md YOLO preference + reproducible evidence trail."

patterns-established:
  - "Feasibility experiment pattern: 1 helper script for URL harvest (Task 1 substitute) + 1 main notebook for fetch loop with per-URL metrics (Task 2) + 1 inspector script for schema sampling (Phase N+1 hot-data). All three live in spike directory as reproducible artifacts."
  - "MEMO 'feasibility' section structure: Status verdict / Method / Sample size / Per-URL outcomes / Timing / Critical findings / Phase N+1 schema hot-data table / Side-deliverables table / Verdict with cross-links."

requirements-completed: [RECON-02]

duration: ~25min
completed: 2026-05-05
---

# Phase 1 Plan 07: viled curl_cffi Feasibility Summary

**viled.kz парсится Tier 0 — 15/15 HTTP 200 без anti-bot; БОНУС: __NEXT_DATA__ схема для Phase 2 PARSE-02 уже extracted, виледовский `realPrice` поле напрямую закрывает v1 схемой требование `was_price`.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-05T23:42Z (approx)
- **Completed:** 2026-05-05T~00:07Z (next day local)
- **Tasks:** 3/3 (Task 1 substituted via autonomous sitemap probe — see Deviations)
- **Files created:** 7 (2 helper scripts + 5 sample payloads)
- **Files modified:** 2 (`notebook-viled.py` from stub to real script + `MEMO.md` viled feasibility section)

## Accomplishments

- **RECON-02 closed:** 15/15 product fetches via curl_cffi impersonate=chrome at 2s pause. 100% HTTP 200, zero errors, zero challenges, zero non-200 statuses. Avg response time 485ms (min 300ms / max 671ms).
- **Critical empirical finding:** viled product pages have **zero JSON-LD `Product` schema markup** (0/15). The standard "JSON-LD price" success proxy used for goldapple (D-14) is **not applicable** to viled. This is a meaningful Phase 2 architectural input — Phase 2 PARSE-02 для viled должен использовать `__NEXT_DATA__` JSON blob, не JSON-LD.
- **Compensating finding:** 15/15 product pages contain `<script id="__NEXT_DATA__">` Next.js SSR data with rich, structured product fields. The schema is more comprehensive than typical JSON-LD: nested attributes for variants, separate `price`/`realPrice` fields (= current_price + was_price natively), category enum (`sizeType`: BEAUTY/APPAREL/JEWELLERY), subcategory, and full attribute lists.
- **Phase 2 PARSE-02 hot-data extracted** via `_inspect_viled_nextdata.py` on 4 sample products covering apparel + perfumery + cosmetics + watch:

  | v1 schema | __NEXT_DATA__ path | Sample value |
  |---|---|---|
  | current_price | `props.pageProps.attributes[0].price` | `44300` (integer KZT) |
  | was_price | `props.pageProps.attributes[0].realPrice` | `44300` (== price = no sale) |
  | currency display | `props.pageProps.attributes[0].currency` | `"₸"` |
  | brand | `props.pageProps.item.brandName` | `"Jo Malone London"` |
  | title | `props.pageProps.item.name` | `"Одеколон Wood Sage & Sea Salt Cologne"` |
  | volume (beauty only) | nested `attributes[].name == "Размер"` | `"30 мл"` |
  | category enum | `props.pageProps.item.sizeType` | `BEAUTY` / `APPAREL` / `JEWELLERY` / `null` |
  | product_id | URL path | `407682` (numeric, monotonic) |

- **Side-deliverable: pagination shape resolved.** viled.kz/sitemap.xml is plain-deliverable (HTTP 200, 1235 B sitemap-index → 9 sub-sitemaps split by gender/section). Total 42,294 product URLs across `/item/<numeric_id>` route. Phase 2 viled crawler **does not need** HTML pagination scraping or AJAX page enumeration — sitemap is the canonical source. Sub-sitemap split: women=22,378, men=11,845, kids=8,071, plus collection=1,182, lookbooks=133, news=188, nav=46.
- **Side-deliverable: URL pattern.** All product URLs follow `https://viled.kz/item/<numeric_id>`. IDs in sample range from 148026 (oldest) to 409206 (newest); IDs are monotonic sequential. Phase 2 can use sitemap `<lastmod>` for incremental delta runs.
- **Side-deliverable: UA strictness.** curl_cffi default `impersonate="chrome"` works on first request. No cookies required, no session warmup, no challenges. **viled has no anti-bot layer** — confirmed by 15/15 plain success at 2s rate.
- **Side-deliverable: was_price availability.** Phase 2 v1 schema's `was_price` requirement is **directly satisfiable** from week 1 via the `realPrice` field — no retroactive backfill needed (matches STATE.md decision).
- **Side-deliverable: pricing & currency format.** Integer (no decimal, no formatted strings). All prices in KZT denomination. Display currency = unicode `"₸"`; Phase 2 NORMALIZE-01 hardcodes `"₸" → "KZT"`.
- MEMO `## viled.kz feasibility (RECON-02)` section populated with verdict, per-URL outcomes, timing, critical findings, schema hot-data table, side-deliverables table, and cross-links to evidence files.

## Task Commits

1. **Task 1 (substituted): autonomous viled URL harvest from sitemap** — `021c354` (feat)
2. **Task 2: notebook-viled.py + 15-fetch run + __NEXT_DATA__ inspector** — `a7f6d43` (feat)
3. **Task 3: MEMO viled.kz feasibility section** — `28d7ee5` (docs)

**Plan metadata commit:** _to be assigned by final commit at end of this plan_

## Files Created/Modified

- `_fetch_viled_urls.py` — sitemap-driven URL harvester; replaces Task 1 checkpoint:human-action with autonomous probe (per user YOLO preference). Produces 15 diversified product URLs from 42,294-URL viled catalog via step-stride sampling. Reproducible.
- `_inspect_viled_nextdata.py` — schema inspector that walks `__NEXT_DATA__` JSON tree and reports field paths matching `price|brand|title|volume|currency` patterns. Used to build the Phase 2 PARSE-02 hot-data table. Reusable for future schema-drift checks.
- `notebook-viled.py` — replaced 01-01 stub with the real feasibility script: fetch loop with per-URL metrics (status, timing, content-length, content-type, JSON-LD presence, JSON-LD price, JSON-LD currency, `__NEXT_DATA__` presence) and aggregate summary. Honors 2s rate-limit. Idempotent.
- `sample-payloads/viled-sitemap.xml` (1.2 KB) — primary sitemap-index, 9 sub-sitemap declarations.
- `sample-payloads/viled-sitemap-1-excerpt.xml` (5.7 KB) — first ~200 lines of sitemap-nav.xml as evidence pattern (full 2.7 MB sitemap-items-women.xml stripped per artifact-hygiene).
- `sample-payloads/viled-product-urls.txt` (15 lines) — the 15 sampled URLs used in the feasibility run.
- `sample-payloads/viled-fetch-results.json` (~12 KB) — per-URL records (15) + aggregate summary; deterministic input for any downstream re-analysis.
- `sample-payloads/viled-nextdata-shape.json` (~8 KB) — extracted schema shape from one sample product (`/item/407682`); pageProps top-level shape + price/brand/title/currency field paths.
- `notebook-viled.py` — modified (real script, no longer raises NotImplementedError).
- `MEMO.md` — modified, populated `## viled.kz feasibility (RECON-02)` section (~75 new lines). Other sections (TL;DR, Options tested, Chosen, robots/ToS audit summary, Next-step impact, Open risks) intentionally remain `_TBD_` for plans 01-08..01-11.

## Decisions Made

See `key-decisions` in frontmatter. Most consequential:

1. **Phase 2 PARSE-02 для viled = __NEXT_DATA__-first** — drives Phase 2 parser architecture. The shared parser/normalizer modules (Phase 2 + 3) need a per-retailer dispatch: viled extracts from `__NEXT_DATA__`, goldapple extracts from JSON-LD (D-14, pending 01-08 confirmation). Same data shape post-normalization, different extraction front-ends.
2. **Phase 2 viled enumeration = sitemap-only** — radically simplifies viled crawler (CRAWL-01). No need for category-tree traversal, no infinite-scroll handling, no `?page=N` enumeration. Phase 2 viled crawler boils down to: fetch sitemap-index → fetch all product sub-sitemaps → for each `<url>` element, fetch product HTML, parse `__NEXT_DATA__`, normalize → write snapshot.
3. **Phase 2 viled is fully Tier 0 (curl_cffi-only)** — no Patchright, no proxy, no anti-bot escalation. Confirmed empirically. This is consistent with research/STACK.md "Tier 0 — viled.kz" classification but now with empirical backing.

No deviations from locked decisions D-01..D-16; this plan adds new empirical decisions on top (viled __NEXT_DATA__-first, sitemap-only enumeration, curl_cffi Tier 0 confirmed).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Task 1 checkpoint:human-action substituted by autonomous sitemap probe**
- **Found during:** Task 1 (start of plan)
- **Issue:** Plan defines Task 1 as `<task type="checkpoint:human-action" gate="blocking">` — manual visual sample of 10-15 viled.kz product URLs via DevTools console. User MEMORY.md explicitly prefers "YOLO/autonomous execution"; identical pattern was already applied in 01-05 Task 1 (autonomous viled brand probe replaces checkpoint). Pure-stop human-action would block plan completion in a sequential executor session against documented user preference.
- **Fix:** Wrote `_fetch_viled_urls.py` that fetches `viled.kz/sitemap.xml` via curl_cffi (already validated as plain-deliverable in 01-04 robots audit + 01-05 sitemap pattern), traverses sitemapindex → 9 sub-sitemaps, classifies URLs by first path segment, picks 15 diversified product URLs from `/item/<id>` pool via step-stride sampling.
- **Files modified:** `_fetch_viled_urls.py` (new), `viled-product-urls.txt` (new), `viled-sitemap.xml` (new), `viled-sitemap-1-excerpt.xml` (new)
- **Verification:** 15 URLs harvested with diverse IDs (148026 oldest → 409206 newest); downstream Task 2 fetched all 15 successfully (15/15 HTTP 200).
- **Committed in:** `021c354`

**2. [Rule 2 - Missing critical] Added _inspect_viled_nextdata.py for Phase 2 hot-data extraction**
- **Found during:** post-Task 2, before MEMO write
- **Issue:** Plan's Task 2 records JSON-LD presence per fetch but JSON-LD = 0/15 on viled. Without an additional inspection step, MEMO would only document "JSON-LD absent" without saying what Phase 2 PARSE-02 should use instead. Per CONTEXT.md "Не обсуждали явно" the spike must capture Phase 2 hot-start data — that requires walking the `__NEXT_DATA__` tree to identify canonical price/brand/title/volume field paths.
- **Fix:** Wrote `_inspect_viled_nextdata.py` that fetches one product URL, parses `__NEXT_DATA__`, walks the JSON tree with regex-matched key patterns (`price|brand|title|volume|currency`), prints first 5 examples per category, and saves a compact shape extract. Ran on 4 sample products (apparel + perfumery + cosmetics + watch) to verify schema consistency across categories.
- **Files modified:** `_inspect_viled_nextdata.py` (new), `viled-nextdata-shape.json` (new)
- **Verification:** Identified canonical `props.pageProps.attributes[0].price` / `realPrice` / `currency` / `props.pageProps.item.brandName` / `name` / `sizeType` paths; documented in MEMO Phase 2 hot-data table.
- **Committed in:** `a7f6d43`

**3. [Rule 1 - Bug avoidance] Stripped 1.3 MB intermediate viled-all-urls.txt**
- **Found during:** end of Task 1 substitute
- **Issue:** `_fetch_viled_urls.py` saved `viled-all-urls.txt` (1.3 MB) as the union of all 9 sub-sitemap URLs. Committing 1.3 MB to git wastes space; the data is fully reproducible from `_fetch_viled_urls.py` OR from the `viled-sitemap.xml` index. Same hygiene pattern as plan 01-05 (which stripped 9.9 MB raw sub-sitemap and 257 KB intermediate JSON) and plan 01-04 (which stripped 9 byte-identical challenge shells).
- **Fix:** Deleted `viled-all-urls.txt`; kept primary `viled-sitemap.xml` (1.2 KB) + first sub-sitemap excerpt `viled-sitemap-1-excerpt.xml` (5.7 KB) as evidence pattern.
- **Files modified:** `.planning/spikes/01-goldapple/sample-payloads/`
- **Verification:** Re-running `_fetch_viled_urls.py` regenerates everything; commit `021c354` did not include the stripped file.
- **Committed in:** `021c354`

---

**Total deviations:** 3 auto-fixed (1 blocking-issue resolution = checkpoint substitution; 1 missing-critical = Phase 2 hot-data inspector; 1 artifact-hygiene = strip 1.3 MB intermediate).
**Impact on plan:** Zero scope creep. Task 1 substitution drives same deliverable (URL list) with reproducible evidence. Hot-data inspector goes beyond plan letter to fully serve plan intent ("side-deliverables for Phase 2 hot-start" per CONTEXT.md). Hygiene is consistent with 01-04/01-05 pattern.

## Issues Encountered

- **JSON-LD absent on viled** — initially looked like a partial failure (success proxy at 0%), but on inspection this is structural: viled simply doesn't use JSON-LD. The `__NEXT_DATA__` finding more than compensates (richer schema, includes `was_price` natively).
- **One sample URL was a watch** (`/item/378292` = Zenith Pilot at 11.4M KZT). Caught early during `_inspect_viled_nextdata.py` cross-category check; flagged that viled's catalog spans far beyond beauty (includes luxury watches, jewellery, apparel). Phase 2 should filter to `sizeType=BEAUTY` for v1 (matching the goldapple beauty-only competitive set).
- **Step-stride sampling (every Nth URL)** vs `pool[:15]` (first 15) — chose stride to spread sample across the catalog age range; otherwise all 15 would have been newest IDs. Documented as a small but meaningful pattern for similar future sampling jobs.

## User Setup Required

None — entirely autonomous, read-only HTTP GETs, no credentials, no external service config. URL selection autonomous via sitemap probe (no DevTools, no manual click-through needed).

## Authentication Gates

None. No login, no API keys, no external service config. viled.kz public pages only.

## Next Phase Readiness

- **Plan 01-06 (DevTools / JSON-endpoint hunt) — UNCHANGED:** focused on goldapple, not affected by this plan's findings.
- **Plan 01-08 (Patchright Tier 2 100-fetch goldapple) — UNCHANGED:** brand list + URL pool source already finalized in 01-05.
- **Plan 01-11 (MEMO finalize) — INPUT READY:** viled.kz feasibility section now populated; MEMO finalizer just needs to cross-link from TL;DR (`Tier 0 confirmed для viled, viable Phase 2 stack = curl_cffi + selectolax + json.parse`).
- **Phase 2 (viled crawler) — INFORMED HEAVILY:**
  - Fetch layer: curl_cffi (Tier 0) confirmed; no Patchright, no proxy
  - Enumeration: sitemap-driven (`https://viled.kz/sitemap.xml` → 9 sub-sitemaps → 42,294 `/item/<id>` URLs); no HTML pagination
  - Parser (PARSE-02): `__NEXT_DATA__`-first extraction with the 8 canonical field paths documented in this SUMMARY's hot-data table
  - was_price availability confirmed (`realPrice` field) — v1 schema requirement satisfiable week 1
  - Currency normalization: `"₸"` → `"KZT"` hardcoded
  - Pricing format: integer, no parsing/regex needed
  - Rate-limit: 2s sequential (already committed in 01-04)
  - Beauty-only filter: `sizeType=BEAUTY` (Phase 2 v1 scope)
- **Phase 7 (KZ-legal review) — UNCHANGED.**

## Self-Check: PASSED

**Files created (verified to exist):**
- `.planning/spikes/01-goldapple/_fetch_viled_urls.py` ✓
- `.planning/spikes/01-goldapple/_inspect_viled_nextdata.py` ✓
- `.planning/spikes/01-goldapple/sample-payloads/viled-product-urls.txt` ✓
- `.planning/spikes/01-goldapple/sample-payloads/viled-sitemap.xml` ✓
- `.planning/spikes/01-goldapple/sample-payloads/viled-sitemap-1-excerpt.xml` ✓
- `.planning/spikes/01-goldapple/sample-payloads/viled-fetch-results.json` ✓
- `.planning/spikes/01-goldapple/sample-payloads/viled-nextdata-shape.json` ✓
- `.planning/spikes/01-goldapple/notebook-viled.py` (modified, no longer stub) ✓
- `.planning/spikes/01-goldapple/MEMO.md` (modified, viled feasibility section populated) ✓

**Commits verified in `git log`:**
- `021c354` (Task 1 — autonomous URL harvest) ✓
- `a7f6d43` (Task 2 — feasibility experiment + hot-data) ✓
- `28d7ee5` (Task 3 — MEMO section) ✓

**Plan-level acceptance criteria:**
- `test -f notebook-viled.py` ✓
- `! grep -q "NotImplementedError" notebook-viled.py` ✓ (stub replaced)
- `test -f viled-fetch-results.json` ✓
- JSON acceptance assertion (`'summary' in d and 'results' in d`, `len(d['results']) >= 10`) ✓ (15 results)
- ≥1 result with status=200 ✓ (15/15 — full success)
- `grep -c "## viled.kz feasibility (RECON-02)" MEMO.md` ✓ (1 occurrence)
- `grep -q "Side-deliverables" MEMO.md` ✓
- `grep -q "viled-fetch-results.json" MEMO.md` ✓
- `grep -q "HTTP 200" MEMO.md` ✓
- No `_TBD_` or `_<...>_` placeholders in viled feasibility section ✓ (other sections still TBD by design for 01-11)

---

*Phase: 01-goldapple-reconnaissance-spike*
*Completed: 2026-05-05*
