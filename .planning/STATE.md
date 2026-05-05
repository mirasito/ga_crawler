# State: GA Crawler

**Last updated:** 2026-05-05
**Mode:** Phase 1 executing — Wave 0 partial (01-01, 01-02 done; 01-03 IPRoyal **deferred** до результата 01-08), Wave 1 in progress (01-04 ✓, 01-05 ✓, 01-07 ✓ — viled CONFIRMED Tier 0 with __NEXT_DATA__ schema; next 01-06 DevTools-человек)

## Project Reference

**Core value:** Команда viled.kz один раз в неделю получает детализированный, сопоставленный по позициям отчёт о ценах конкурента (goldapple.kz) и может корректировать собственное ценообразование, видеть ассортиментные разрывы и отслеживать чужие промо-акции.

**Current focus:** Phase 1 executing — Wave 0 партиал, 01-03 IPRoyal **отложен** (user decision: проверим Tier 2 с KZ-лэптопа, если ≥98/100 + challenge<10% — прокси не нужен; иначе вернёмся к 01-03 после 01-08). Wave 1 идёт: 01-04 (robots/ToS audit) ✓, 01-05 (sitemap + page-volume) ✓, 01-07 (viled curl_cffi feasibility) ✓ — **viled CONFIRMED Tier 0** (15/15 HTTP 200, avg 485ms, no anti-bot); critical Phase 2 finding: viled has zero JSON-LD on product pages, instead uses `__NEXT_DATA__` Next.js SSR blob; canonical field paths extracted (price/realPrice/brandName/name/sizeType/Размер/currency); viled sitemap also plain-deliverable (42,294 product URLs under `/item/<numeric_id>` route across 9 sub-sitemaps split by gender). Phase 2 viled stack frozen: curl_cffi + selectolax + json.parse on `__NEXT_DATA__`, sitemap-driven enumeration, no HTML pagination. **goldapple sitemap.xml IS plain-deliverable via curl_cffi** (HTTP 200, no JS-challenge — exempt from anti-bot layer); catalog enumerated: 112,317 URLs total, 100,779 product-numeric URLs across 1,461 brand slugs (~69 products/brand catalog-wide). 5 niche-perfumery brands selected for 01-08 (Jo Malone London, Tom Ford, Creed, Frederic Malle, Givenchy) после autonomous probe viled.kz (luxury fashion + niche perfumery, NOT mass-market — default plan_context list rejected). Phase 3 budget anchor: ~600 MB/week, ~$2.10 proxy, ~4.4h duration.

## Current Position

| Field | Value |
|-------|-------|
| Phase | 1 — Goldapple Reconnaissance Spike |
| Plan | 5/12 complete (`01-01` ✓, `01-02` ✓, `01-04` ✓, `01-05` ✓, `01-07` ✓), 1 deferred (`01-03` IPRoyal — revisit gate at 01-08) |
| Status | Executing Wave 1 — next plan 01-06 (DevTools JSON-endpoint hunt with human) or jump to Wave 2 (01-08 Patchright Tier 2 KZ-laptop 100-fetch) |
| Progress | `[░░░░░░░░░░░░░░░░░░░░] 0/7 phases` (Phase 1: 5/12 plans executed, 1 deferred) |
| Branch strategy | none (single-trunk) |
| Resume file | `.planning/phases/01-goldapple-reconnaissance-spike/01-06-PLAN.md` |

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases planned | 7 |
| Phases completed | 0 |
| v1 requirements mapped | 48/48 |
| v1 requirements completed | 3/48 (RECON-04, RECON-03, RECON-02) |
| Plans created | 12 (Phase 1) |
| Plans completed | 5 |
| Spawned agents (this session) | roadmapper, gsd-planner, gsd-plan-checker, gsd-executor |
| Checkpoints | 0 |

### Plan Execution Metrics

| Plan | Duration | Tasks | Files | Date |
|------|----------|-------|-------|------|
| 01-01 (spike skeleton) | ~3 min | 3/3 | 7 created | 2026-05-05 |
| 01-02 (uv init + spike deps) | ~5 min | 3/3 | 4 created | 2026-05-05 |
| 01-04 (robots/ToS audit) | ~38 min | 2/2 | 9 created, 1 modified | 2026-05-05 |
| 01-05 (sitemap + page-volume) | ~52 min | 3/3 (Task 1 substituted) | 9 created, 1 modified | 2026-05-05 |
| 01-07 (viled curl_cffi feasibility) | ~25 min | 3/3 (Task 1 substituted) | 7 created, 2 modified | 2026-05-05 |

## Accumulated Context

### Key Decisions

| Decision | Source | Constraint Imposed |
|----------|--------|--------------------|
| Strict-key matching only on v1 (`brand_norm + name_norm + volume_norm`) | PROJECT.md | Forces brand-alias YAML as v1 deliverable in Phase 2; defers fuzzy matching to v2 |
| Append-only snapshot history keyed by `run_id` | research/ARCHITECTURE.md | No in-place updates; Phase 2 schema is final from week 1 |
| `was_price` and stock-state enum captured in v1 schema | research/SUMMARY.md | Avoids retroactive backfill; prevents v1.x re-crawl |
| Match-rate as a tracked KPI from week 1 | research/SUMMARY.md | Phase 4 must log/store match-rate to establish historical baseline |
| Reporter is independent of delivery (file on disk first, Telegram wraps it) | research/ARCHITECTURE.md | Phase 5 produces archive without Telegram; Phase 6 is a thin wrapper |
| Two Telegram chats (ops vs business) | research/PITFALLS.md | Pre-send sanity-gate (Phase 4 + Phase 6) prevents broken reports reaching pricing team |
| Goldapple anti-bot tier decided empirically before any production code | research/SUMMARY.md | Phase 1 is throwaway spike; Phase 3 stack waits on its decision memo |
| SQLite + WAL on v1; Postgres only if SQLite hits limits | research/STACK.md | Single-writer batch fit; defers infra complexity |
| System cron with `CRON_TZ=Asia/Almaty`; no APScheduler/Celery/Prefect | research/STACK.md | Phase 7 minimum; one weekly job |
| Backend-only — no UI / dashboard / API | PROJECT.md (Out of Scope) | All phases `UI hint: no` |
| viled.kz committed rate-limit = 2s sequential | plan 01-04 (RECON-04) | Phase 2 viled crawler config constant; courtesy-only (no Crawl-delay, no anti-scraping clauses in Privacy Policy) |
| goldapple.kz committed rate-limit = 3-5s random uniform, concurrency=1 | plan 01-04 + D-04 + Pitfall 13 | Phase 3 goldapple crawler config; starting point for 01-08 experiment, validated/adjusted there |
| Stealth UA strategy for goldapple (NOT honest UA) | plan 01-04 — robots.txt blocks SemrushBot/MJ12bot/BLEXBot/DotBot | Phase 3 fetch layer uses curl_cffi/Patchright realistic-browser impersonation; no `ViledPriceMonitor/1.0`-style self-identification |
| goldapple anti-bot is GLOBAL (every HTML route gated, not just product pages) | plan 01-04 empirical — 11 ToS-slug candidates all return identical 18 912-byte JS-challenge shell | Strengthens D-01 (start at Tier 2 / Patchright); vanilla Playwright will likely fail too; goldapple ToS text deferred to post-01-08 warm Patchright re-fetch |
| `/rest/` Magento API is robots-Disallowed on goldapple | plan 01-04 (robots.txt §Rest API block) | plan 01-06 JSON-endpoint hunt must avoid `/rest/`; focus on `__NEXT_DATA__`/JSON-LD/non-`/rest/` ajax routes |
| goldapple sitemap.xml is **plain-deliverable** via curl_cffi (sitemapindex with 3 sub-sitemaps, 112,317 URLs total, 100,779 product-numeric URLs, 1,461 brand slugs) | plan 01-05 empirical | Phase 3 architecture splits: enumeration via curl_cffi (Tier 0) + product render via Patchright (Tier 2). No need to render brand-listing pages. Reduces total Patchright fetches by ~60% |
| Catalog-wide ~69 products/brand average (from sitemap) is Phase 3 anchor for proxy budget; sample facet count ≠ SKU count (caveat) | plan 01-05 | Phase 3 estimate: ~50 brands × 69 products = ~3,450 fetches/week; ~600 MB bandwidth, ~$2.10 IPRoyal Tier 3 proxy, ~4.4h duration at 3-5s rate-limit |
| viled.kz is luxury fashion + niche perfumery (NOT mass-market beauty); brand selection for 01-08 = Jo Malone London, Tom Ford, Creed, Frederic Malle, Givenchy | plan 01-05 — autonomous probe viled __NEXT_DATA__ | Phase 2 viled-list extraction pattern: Next.js __NEXT_DATA__ JSON-blob (confirmed for both privacy page in 01-04 and homepage in 01-05); Phase 3 product-fetch focus on luxury/niche brands |
| viled fully Tier 0 confirmed: 15/15 HTTP 200 via curl_cffi impersonate=chrome at 2s pause, avg 485ms; no Patchright, no proxy needed for Phase 2 | plan 01-07 empirical | Phase 2 viled fetch layer = curl_cffi only (consistent with research/STACK.md "Tier 0 — viled.kz" but now empirically backed) |
| Phase 2 PARSE-02 для viled = __NEXT_DATA__-first extraction (NOT JSON-LD-first as for goldapple) — viled has zero JSON-LD on product pages | plan 01-07 empirical (0/15 JSON-LD, 15/15 __NEXT_DATA__) | Phase 2 parser dispatch: per-retailer extraction front-end. viled = `props.pageProps.{item, attributes}`; goldapple D-14 = JSON-LD Product.offers.price (pending 01-08 confirmation) |
| Phase 2 viled enumeration = sitemap-only (42,294 product URLs across 9 sub-sitemaps under /item/<numeric_id>); no HTML pagination crawl needed | plan 01-07 empirical | Phase 2 CRAWL-01 simplified: sitemap-index → sub-sitemaps → product URLs. Incremental delta available via sitemap `<lastmod>` |
| viled was_price requirement (v1 schema) directly satisfiable from week 1 via realPrice field — no retroactive backfill | plan 01-07 empirical | STATE.md "was_price captured in v1 schema" decision now has data-supporting field path |
| viled currency mapping for Phase 2 NORMALIZE-01: "₸" (display unicode) → "KZT" (programmatic); single-currency site, hardcode | plan 01-07 empirical | Phase 2 normalizer constant |

### Active Todos

(none — awaiting Phase 1 plan)

### Active Blockers

(none)

## Session Continuity

### What Was Just Done

- `/gsd-execute-phase 1` plan 01-07 executed (sequential mode, autonomous, 3 tasks; Task 1 substituted by autonomous viled-sitemap probe per user YOLO preference + 01-05 precedent):
  - Task 1 (substituted): `_fetch_viled_urls.py` fetches viled.kz/sitemap.xml via curl_cffi → sitemapindex with 9 sub-sitemaps → 42,294 product URLs (women=22,378 / men=11,845 / kids=8,071 + collection/lookbook/news) under `/item/<numeric_id>` route → step-stride sample of 15 diversified URLs (IDs 148026 oldest → 409206 newest). Sitemap plain-deliverable confirmed (1.2 KB index, 200 OK). Commit `021c354`.
  - Task 2: `notebook-viled.py` replaced 01-01 stub with real feasibility script; ran 15 fetches at 2s pause: **15/15 HTTP 200, avg 485ms (min 300, max 671), 35.3s wall-clock**. Critical finding: **0/15 product pages have JSON-LD** (D-14-style proxy НЕ применим к viled), but **15/15 have `__NEXT_DATA__`** Next.js SSR blob. `_inspect_viled_nextdata.py` extracted Phase 2 PARSE-02 hot-data from 4 cross-category samples (apparel/perfumery/cosmetics/watch): canonical paths `props.pageProps.attributes[0].{price, realPrice, currency}` + `props.pageProps.item.{brandName, name, sizeType}` + nested `attributes[].name=='Размер'` for beauty volume. Currency display `"₸"` (unicode tenge); pricing integer KZT (no decimal). Commit `a7f6d43`.
  - Task 3: MEMO `## viled.kz feasibility (RECON-02)` populated — verdict CONFIRMED (Tier 0), per-URL outcomes, timing, critical findings, Phase 2 schema hot-data table (8 v1-schema fields → __NEXT_DATA__ paths), side-deliverables table (pagination = sitemap-driven, URL pattern, UA strictness, was_price availability via realPrice, pricing format). Commit `28d7ee5`.
  - 7 files created (2 helper scripts + 5 sample payloads), 2 modified (`notebook-viled.py` + `MEMO.md`), 3 deviations (1 blocking-issue resolution = checkpoint substitution; 1 missing-critical = Phase 2 hot-data inspector; 1 artifact-hygiene = strip 1.3 MB intermediate URLs file), self-check PASSED.
  - SUMMARY → `.planning/phases/01-goldapple-reconnaissance-spike/01-07-SUMMARY.md`
- Earlier this session: plan 01-05 executed (sequential mode, autonomous, 3 tasks; Task 1 substituted by autonomous viled probe per user YOLO preference):
  - Task 1 (substituted): `_fetch_viled_brands.py` probes viled.kz/ via curl_cffi → `__NEXT_DATA__` parse → 58 brand entries → discovered viled is luxury fashion + niche perfumery; selected 5 brands (Jo Malone London / Tom Ford / Creed / Frederic Malle / Givenchy). Default plan_context list (Lancôme/La Roche-Posay/Vichy etc) rejected as not-representative.
  - Task 2: goldapple sitemap fetch + per-brand counts — commit `b9cb355`. **Critical empirical finding:** goldapple.kz/sitemap.xml IS plain-deliverable via curl_cffi (HTTP 200, no JS-challenge — sitemap is exempt from anti-bot layer). Sitemapindex with 3 sub-sitemaps; 112,317 URLs total; 100,779 product-numeric URLs (89.7%); 1,461 distinct brand slugs; ~69 products/brand catalog-wide. Per-brand facet counts: Givenchy 40, Tom Ford 33, Frederic Malle 19, Creed 8, Jo Malone London 1.
  - Task 3: MEMO `## Page-volume estimate (RECON-03)` populated — commit `f00d947`. Section includes brand-selection methodology, per-brand table, catalog-wide aggregates, Phase 3 implications (~600 MB/week, ~$2.10 proxy, ~4.4h duration), sitemap-as-enumeration-strategy validation.
  - 9 files created (3 helper scripts + 6 sample payloads), 1 modified (`MEMO.md`), 5 deviations (1 blocking-issue resolution = checkpoint substitution; 1 bug = encoding; 3 artifact-hygiene; 1 critical = JSON shape), self-check PASSED.
  - SUMMARY → `.planning/phases/01-goldapple-reconnaissance-spike/01-05-SUMMARY.md`
- Earlier this session: plan 01-04 executed (sequential mode, autonomous, 2 tasks):
  - Task 1 (snapshot robots.txt): viled (508 B HTTP 200, no Crawl-delay, sitemap declared) + goldapple (7303 B HTTP 200, Magento-style, no Crawl-delay, blocks 38 bots incl. SemrushBot/MJ12bot/BLEXBot/DotBot, sitemap declared) — commit `198f579`
  - Task 2 (ToS audit + committed rate-limits): viled `/privacy` extracted via Next.js `__NEXT_DATA__` (16066 chars, **no anti-scraping clauses**, only KZ Law 94-V personal-data); goldapple — all 11 ToS-slug candidates return identical 18 912-byte JS-challenge shell ("Gold Apple — checking device", DataDome-style UUID JS bundle), text deferred to post-01-08 — commit `83c5150`
  - Committed rate-limits: viled=2s sequential, goldapple=3-5s random uniform concurrency=1
  - 9 files created (4 helper scripts + 5 sample payloads), 1 modified (`tos-audit.md`), 3 deviations (all artifact-hygiene cleanups, zero scope creep), self-check PASSED
  - SUMMARY → `.planning/phases/01-goldapple-reconnaissance-spike/01-04-SUMMARY.md`
- Earlier (this session): plan 01-02 → 4 файла, 2 коммита (`d47b800`, `0b98407`); plan 01-01 (spike skeleton) → 7 файлов, 3 коммита (c2da755, 02e8cf5, 8a2d5c5)
- Earlier (planning): `/gsd-plan-phase 1` создал 12 атомарных плана (01-01..01-12) в 5 волнах; gsd-plan-checker VERIFICATION PASSED

### Earlier (this session)

- Phase 1 discuss session: 4 gray areas обсуждены (Tier escalation & timebox, IP-гео, JSON-endpoint hunt, success criteria)
- Locked-in 16 implementation decisions (D-01..D-16) для recon-спайка
- Создан `.planning/phases/01-goldapple-reconnaissance-spike/01-CONTEXT.md` с canonical refs на research/* и project docs
- Создан `.planning/phases/01-goldapple-reconnaissance-spike/01-DISCUSSION-LOG.md` (audit trail)

### Earlier (initialization)

- Read PROJECT.md and REQUIREMENTS.md
- Read research/SUMMARY.md, STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md
- Derived 7-phase roadmap aligned with research synthesis (Phase 1 spike, viled-first build, goldapple-second, matcher, reporter, delivery, scheduler)
- Mapped all 48 enumerated v1 requirements to phases (no orphans, no duplicates)
- Wrote ROADMAP.md with phase details and success criteria
- Updated REQUIREMENTS.md traceability section

### What's Next

1. Continue Phase 1 — Wave 1 has 01-06 (DevTools JSON-endpoint hunt с человеком, RECON-03 part 2 — D-09/D-10) remaining; OR jump to Wave 2 Patchright work since RECON-02 is now closed.
2. Wave 2 (Patchright Tier-2 100-fetch): 01-08 KZ-laptop (sitemap.xml plain-delivery pre-flight already validated in 01-05; brand list ready: Jo Malone London / Tom Ford / Creed / Frederic Malle / Givenchy; URL pool source = `goldapple-all-urls.txt` numeric-product URLs), 01-09 EU-proxy. Conditional Wave 3 (01-10 Tier 3 escalation if fails). Wave 4 (01-11 MEMO finalize, 01-12 wrap-up).
3. Spike outcome (decision memo `.planning/spikes/01-goldapple/MEMO.md`) feeds Phase 3 stack selection. MEMO must reference 01-04 audit summary + committed rate-limits + 01-05 sitemap plain-delivery + 01-07 viled __NEXT_DATA__ schema + ~600 MB/week budget as Phase 3 config constants.
4. **Phase 2 hot-start ready:** viled stack frozen (curl_cffi + selectolax + json.parse on `__NEXT_DATA__`), 8 canonical field paths documented, sitemap-driven enumeration, was_price field located, currency mapping defined. Phase 2 can start immediately after spike wrap-up without further reconnaissance.
5. Open follow-ups (Phase 7): KZ-legal review with bundle = `tos-audit.md` + `viled-privacy.txt` + both `*-robots.txt` snapshots + flag «goldapple ToS not obtainable in spike».

### Resume Instructions

To continue this project from a fresh session:
1. Read `.planning/PROJECT.md` for core value and constraints.
2. Read `.planning/ROADMAP.md` for phase structure.
3. Read this STATE.md for current position.
4. Run `/gsd-execute-phase 1` to continue Phase 1 execution from plan 01-06 (DevTools JSON-endpoint hunt) or jump to 01-08 (Patchright Tier 2 KZ-laptop).

---
*State initialized: 2026-05-05 by gsd-roadmapper; updated by gsd-plan-phase 2026-05-05; updated by gsd-executor (plan 01-01) 2026-05-05; updated by gsd-executor (plan 01-02) 2026-05-05; updated by gsd-executor (plan 01-04) 2026-05-05; updated by gsd-executor (plan 01-05) 2026-05-05; updated by gsd-executor (plan 01-07) 2026-05-05*
