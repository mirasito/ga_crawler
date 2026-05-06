---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Executing Phase 03
last_updated: "2026-05-06T05:30:00Z"
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 19
  completed_plans: 14
  percent: 73
---

# State: GA Crawler

**Last updated:** 2026-05-06
**Mode:** Phase 1 COMPLETE (signed off 2026-05-06). Phase 3 EXECUTING — Wave 0 (03-01) + Wave 1 (03-02) complete 2026-05-06: deps pinned, interfaces.py contracts frozen, conftest.py + 6 fixtures ready, enumeration primitives (bilingual slug-fy + intersect + curl_cffi sitemap fetch + week-over-week NEW-slug diff) shipping with 39/39 unit tests green. Phase 2 not yet discussed — independent of Phase 3 per ROADMAP. Next: `/gsd-execute-phase 3 03` (Wave 2 parser).

## Project Reference

**Core value:** Команда viled.kz один раз в неделю получает детализированный, сопоставленный по позициям отчёт о ценах конкурента (goldapple.kz) и может корректировать собственное ценообразование, видеть ассортиментные разрывы и отслеживать чужие промо-акции.

**Current focus:** Phase 03 — goldapple-crawl

## Current Position

Phase: 03 (goldapple-crawl) — EXECUTING
Plan: 3 of 7 (Waves 0 + 1 done; Wave 2 next)
| Field | Value |
|-------|-------|
| Phase | 3 — Goldapple Crawl (Wave 1 complete) |
| Plan | 03-01 ✓ + 03-02 ✓ (enumeration primitives shipped) — next: 03-03 (Wave 2 microdata parser) |
| Status | Phase 3 plan 03-02 (Wave 1 enumeration) executed 2026-05-06: bilingual slug-fy + intersect_brand_pool (CRAWL-02), curl_cffi Tier 0 sitemap fetcher with PRODUCT_URL_RE whitelist (Threat T-04), persist + find-previous + diff_new_slugs (D-307 NORM-06 reverse direction). 39/39 tests green; 4 bug auto-fixes (regex range, apostrophe handling, KZ whitelist, namespaced fixture). Phase 2 discuss/plan still pending. |
| Progress | `[███░░░░░░░░░░░░░░░░░] 1/7 phases` (Phase 1 complete: 9/12 plans; Phase 3: 2/7 plans) |
| Branch strategy | none (single-trunk) |
| Resume file | `.planning/phases/03-goldapple-crawl/03-03-PLAN.md` |

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases planned | 7 |
| Phases completed | 1 |
| v1 requirements mapped | 48/48 |
| v1 requirements completed | 4/48 (RECON-01, RECON-02, RECON-03, RECON-04 — all four Phase 1 requirements closed) |
| Plans created | 19 (Phase 1 = 12, Phase 3 = 7) |
| Plans completed | 10 (Phase 1: `01-01`, `01-02`, `01-04`, `01-05`, `01-06`, `01-07`, `01-08`, `01-11`, `01-12`; Phase 3: `03-01`) |
| Plans skipped | 3 (`01-03` IPRoyal, `01-09` multi-geo proxy, `01-10` Tier 3 escalation — explicit SKIP per Camoufox-fingerprint-solves-gate verdict) |
| Spawned agents (this session) | roadmapper, gsd-planner, gsd-plan-checker, gsd-executor (inline) |
| Checkpoints | 1 (Phase 1 sign-off) |

### Plan Execution Metrics

| Plan | Duration | Tasks | Files | Date |
|------|----------|-------|-------|------|
| 01-01 (spike skeleton) | ~3 min | 3/3 | 7 created | 2026-05-05 |
| 01-02 (uv init + spike deps) | ~5 min | 3/3 | 4 created | 2026-05-05 |
| 01-04 (robots/ToS audit) | ~38 min | 2/2 | 9 created, 1 modified | 2026-05-05 |
| 01-05 (sitemap + page-volume) | ~52 min | 3/3 (Task 1 substituted) | 9 created, 1 modified | 2026-05-05 |
| 01-07 (viled curl_cffi feasibility) | ~25 min | 3/3 (Task 1 substituted) | 7 created, 2 modified | 2026-05-05 |
| 01-06 (JSON-endpoint hunt) | ~28 min | 3/3 (Task 1 substituted) | 5 created, 1 modified | 2026-05-06 |
| 01-08 (Camoufox 100-fetch) | ~45 min (incl. plan rewrite + smoke debug) | 4/4 (D-14 revised mid-spike) | 7 created, 4 modified | 2026-05-06 |
| 01-11 (MEMO finalize) | ~10 min | 3/3 | 0 created, 1 modified | 2026-05-06 |
| 01-12 (Obsidian + skill + STATE) | ~5 min | 4/4 | 3 created (Obsidian note, project skill, this STATE update), 1 modified (this STATE.md) | 2026-05-06 |
| 03-01 (Wave 0 bootstrap) | ~9 min | 3/3 | 13 created, 2 modified | 2026-05-06 |
| 03-02 (Wave 1 enumeration) | ~6 min | 2/2 | 8 created, 0 modified | 2026-05-06 |

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
| goldapple anti-bot vendor identified as **GroupIB / F.A.C.C.T.** (Russian-market rebrand of Singapore-based GroupIB), NOT Cloudflare/DataDome | plan 01-06 empirical (challenge HTML reveals `window.gib.init({cid:'w-goldapple', gafUrl:'ru.id.facct.ru/id.html'})`) | Material reorder of Phase 1 escalation tree: **Camoufox is now a primary 01-08 candidate** (different fingerprint surface, Firefox-based vs Chromium), not Tier-4 last resort. 2026 Patchright benchmarks target Cloudflare/DataDome/Akamai, not GroupIB — uncharted territory. |
| Patchright on KZ-laptop direct (D-06 baseline, no proxy) is empirically INSUFFICIENT to clear goldapple gate (0/7 in 01-06 with 20-25s wait per page) | plan 01-06 empirical | STATE.md gate "if ≥98/100 + challenge<10% — proxy not needed" decisively fails → **01-03 IPRoyal REQUIRES REVIVAL before 01-08**; ungate it. Phase 7 prod-IP-geo flag: EU-Hetzner likely WORSE than KZ-residential (GroupIB likely whitelists local TLD/IP-geo). |
| goldapple gate API contract: `POST /web/api/v1/settings` (24/24=403 for blocked sessions); telemetry sinks `/front/api/event*` (200) and `https://sp.goldapple.ru/front/api/apm/events` (POST 202) accept blind; `https://ru.id.facct.ru/id.html` iframe loaded for cross-origin device fingerprint | plan 01-06 empirical | 01-08 must poll `/web/api/v1/settings` in background to detect gate-clearance before starting product fetches. May need 5-15min warmup pattern (idle browse, scroll). |
| D-14 success-criterion verification deferred to 01-08 post-gate-clearance (challenge shell has no `__NEXT_DATA__`/JSON-LD; cannot confirm/deny presence on real product HTML without first passing the gate) | plan 01-06 — challenge shell is the only HTML obtained | Phase 3 parser implementation BLOCKED on 01-08 reaching real product HTML. `sample-payloads/goldapple-jsonld-sample.json` is `[]` with explicit D-14 ALERT pointer. |
| **Tier 2 = Camoufox direct, no proxy** for goldapple (99/100 D-13 PASS, 0% gate-shell rate, NOT FRAGILE per D-15). D-01 (Patchright start) superseded; D-08 (IPRoyal pre-register) cancelled. Plans 01-03, 01-09, 01-10 SKIPPED. | plan 01-08 empirical (signed-off MEMO 2026-05-06) — see `.planning/spikes/01-goldapple/MEMO.md` | Phase 3 production engine LOCKED. Phase 7 hosting recommendation = Hetzner CX22 EU + smoke gate; IPRoyal KZ residential as fallback if EU+Camoufox combination fails. |
| **D-14 revised:** goldapple uses inline microdata (`<meta itemprop="price">`), NOT JSON-LD Product schema. Goldapple's only JSON-LD block is `OfferShippingDetails` (shipping policy). Phase 3 parser uses microdata extraction; viled separately uses `__NEXT_DATA__` parser. | plan 01-08 smoke test 2026-05-06 | Phase 3 has TWO parser strategies, not symmetric. Parser dispatch by site. |
| **Camoufox Python 0.4.11 == upstream Firefox 135.0.1-beta.24** — verified empirically via `camoufox.pkgman.installed_verstr()`. Pin `camoufox[geoip]==0.4.11` is the PEP 440-valid semantic equivalent of plan's `0.4.11+camoufox.135.0.1-beta.24` (which is a local-version identifier not on PyPI). | plan 03-01 (Task 1) | Phase 3 fingerprint stability anchored on PyPI-publishable pin; manual upgrade workflow per D-313 unchanged. |
| **`[build-system]` hatchling required for src/-layout** — without `[build-system]` block, `uv sync` does not install the project package itself, breaking all `from ga_crawler.* import` statements downstream. Added in plan 03-01 Task 2 as Rule 3 deviation. | plan 03-01 (Task 2 verification) | All Wave 1+ plans depend on `ga_crawler.interfaces` import — bootstrap blocker now resolved. |
| **Cyrillic-presence regex must use explicit KZ-glyph alternation, NOT contiguous range** — `[ә-і]` raises `re.error: bad character range` because KZ glyphs span U+0456 to U+04E9 with non-adjacent codepoints. Use `[а-яёәғқңөұүһі]` (explicit list). Same fix applies to the slug-whitelist regex `_normalize_punct`. RESEARCH §Pattern 2 line 396 contains the source-of-truth bug. | plan 03-02 (Task 1, first pytest run) | All bilingual slug-fy implementations downstream must use the explicit-list form; copy the constant from slug.py rather than re-typing. |
| **Apostrophes must be stripped (NOT hyphenated) before non-alphanum→hyphen step** — RESEARCH §Pattern 2 line 435 mandates `L'Oréal Paris → loreal-paris`; verbatim algorithm `[^a-z0-9а-я]+ → -` produces `l-oreal-paris`. Strip `' ’ ʼ ʹ` first. | plan 03-02 (Task 1, parametrize case 6) | Phase 2 normalizer (NORM-02) and any future slugifier MUST handle apostrophes before hyphen-replacement; same rule for curly quotes. |
| **respx is httpx-based, NOT curl_cffi-compatible** — for tests that mock `curl_cffi.requests.get`, monkey-patch the wrapper function directly (e.g. `_fetch_xml`) instead of declaring respx routes. respx routes are silently bypassed by curl_cffi. | plan 03-02 (Task 2 test design) | All Tier 0 fetcher tests follow this pattern; documented in `test_sitemap_parser.py` docstring as canonical reference. |

### Active Todos

- Run `/gsd-plan-phase 3` — Phase 3 context gathered, ready for planning. Picks up `.claude/skills/spike-01-goldapple/SKILL.md` + `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` automatically
- Run `/gsd-discuss-phase 2` — Project Skeleton + viled Crawl + Storage (viled stack hot-data ready from 01-07; can run in parallel with Phase 3 plan/exec since Phase 3 contracts to Phase 2 modules)
- [Phase 7 backlog] Camoufox+EU smoke fetch before locking Hetzner hosting — if regression, revive D-08 (IPRoyal trial)
- [Phase 7 backlog] KZ-legal review (30 min с юристом) for ToS compliance — bundle = `tos-audit.md` + `viled-privacy.txt` + both `*-robots.txt` snapshots + GroupIB/F.A.C.C.T. vendor flag
- [Phase 3 ops backlog] Weekly Camoufox-vs-goldapple smoke ("does the gate still pass?") — covered by D-312 integrated smoke probe; threshold = gate-shell rate >5% per spike-skill

### Active Blockers

(none)

## Session Continuity

### What Was Just Done

- `/gsd-execute-phase 3` plan 03-02 (Wave 1 enumeration) 2026-05-06 — 2 tasks executed sequentially:
  - **Task 1** (`954d0ea`): `enumeration/slug.py` — `slug_fy_bilingual` (NFKD + accent strip + Cyrillic→Latin transliterate, with explicit KZ-glyph list ә ғ қ ң ө ұ ү һ і) + `intersect_brand_pool` (EXACT-match via `dict.get`, NOT substring iteration — Pitfall 3 / D-305 guard against `tom-ford ⊆ tom-ford-beauty`). 11 RESEARCH-mandated parametrized cases + 4 supplementary (idempotency, KZ glyph round-trip, hyphen-collapse, map keys). Plus 6 intersect cases (exact-match guard, bilingual hit, unmatched surfacing, alias-fallback to brand_norm, empty-alias unmatched, multi-URL slug).
  - **Task 2** (`a7fa06d`): `enumeration/goldapple_sitemap.py` — `fetch_sitemap_slugs` (curl_cffi `impersonate="chrome"`, tenacity `stop_after_attempt(3) + wait_exponential_jitter`, SITEMAP_TIMEOUT_S=30s); `PRODUCT_URL_RE` whitelist (Threat T-04 sitemap-poisoning mitigation: rejects /brands/x facets, wrong domains, non-numeric IDs); `persist_sitemap_slugs / find_previous_slug_file / diff_new_slugs` (D-307 NORM-06 reverse direction, on-disk under `{root}/runs/{run_id}/sitemap-slugs.txt`, sorted). 9 sitemap-parser tests (6 regex whitelist cases + namespaced fixture extraction + mocked end-to-end + 503-retry-then-raise) + 9 norm06-diff tests (persist sorted, predecessor finder with non-numeric/future skip, first-run-empty, additions-sorted, removals-ignored, blank-line-tolerant).
  - 4 deviations all auto-fixed: Rule 1 — `[ә-і]` regex range is `re.error: bad character range` (KZ glyphs non-adjacent), fix = explicit `[а-яёәғқңөұүһі]` alternation; Rule 1 — `L'Oréal Paris → l-oreal-paris` instead of `loreal-paris`, fix = strip apostrophes BEFORE hyphen-replacement; Rule 1 — slug whitelist `[^a-z0-9а-я]+` drops KZ glyphs, fix = extend to `[^a-z0-9а-яёәғқңөұүһі]+`; Rule 3 — fixture is etree-serialized (`<ns0:loc>`), production sitemap is plain `<loc>`; fix = test regex matches both shapes, mocked end-to-end exercises production shape. 2 commits, 8 files created, 39/39 tests green, self-check PASSED.
  - SUMMARY → `.planning/phases/03-goldapple-crawl/03-02-SUMMARY.md`
- `/gsd-execute-phase 3` plan 03-01 (Wave 0 bootstrap) 2026-05-06 — 3 tasks executed sequentially:
  - **Task 1** (`36d8f56`): pinned `camoufox[geoip]==0.4.11` (bundles Firefox 135.0.1-beta.24 per D-313, verified via `pkgman.installed_verstr()`); added `tenacity>=9`, `sqlmodel>=0.0.24`, `pydantic>=2.10`; dev: `pytest 8`, `pytest-asyncio 1.3.0` (asyncio_mode=auto), `pytest-mock`, `respx`. `[tool.pytest.ini_options]` block + `[tool.ga_crawler.crawl.goldapple]` namespace with 15 operational constants + 3 hardcoded smoke URLs (D-312).
  - **Task 2** (`c2716c5`): created `src/ga_crawler/__init__.py` + `interfaces.py` with 6 Protocol contracts (BrandAlias, Normalizer, SnapshotWriter, RunWriter, ParseDispatcher — `@runtime_checkable`; CrawlerProtocol — static-only). Rule 3 deviation: added `[build-system]` hatchling block to make `src/`-layout package importable as `ga_crawler` (without it, all Wave 1+ imports fail).
  - **Task 3** (`6ac04c0`): copied 5 spike sample-payloads as test fixtures verbatim (`_debug-product-page.html`, `gate-shell.html`, `sitemap-1-excerpt.xml`, `tier2-camoufox-kz-results.json`, `_debug-jsonld-blocks.json`), synthesized `stale-sku-9.5kb.html` (9189 B, "Loading" title, no microdata) per PATTERNS fixture-gap fallback. `tests/conftest.py` with 11 fixtures: 6 HTML/JSON loaders (session-scope), 4 Phase 2 protocol mocks (function-scope), 1 `tmp_camoufox_profile_dir` factory.
  - 3 deviations all auto-fixed (Rule 1: Camoufox PEP 440 string mismatch; Rule 3: hatchling build-system required for src/-layout; Rule 3: skip redundant `camoufox fetch` — binary already cached). 3 commits, 13 files created, 2 modified, self-check PASSED.
  - SUMMARY → `.planning/phases/03-goldapple-crawl/03-01-SUMMARY.md`
- `/gsd-discuss-phase 3` 2026-05-06 — 4 gray areas обсуждены (URL-pool, Brand-alias coverage, Sanity-gate threshold M, Camoufox profile lifecycle). 13 implementation decisions D-301..D-313 locked: sitemap-only URL pool, full re-crawl weekly, slug-эвристика bilingual exact-match, NORM-06 viled-side + week-over-week NEW goldapple-slug diff, M=1000 static + run-to-completion + auto-suggest after 4 weeks, fresh Camoufox profile per run + integrated smoke probe before crawl + pinned Camoufox version. Created `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` (canonical refs to spike-MEMO + spike-skill + research/* + Phase 1 context, code_context with reusable assets/patterns/integration points, deferred ideas list including v2 incremental + fuzzy + persistent-profile-warm). Created `.planning/phases/03-goldapple-crawl/03-DISCUSSION-LOG.md` audit trail. Committed `b100932`.
- `/gsd-execute-phase 1` Phase 1 closure session 2026-05-06 (continuation of session that committed `1ff7d4d` Camoufox-spike + `789e51b` re-route session note):
  - **Plan 01-08 rewritten** Patchright→Camoufox (commit `532b37c`); URL pool collected (`649eb6c`); notebook.py replaced with Camoufox 100-fetch implementation including D-14 revision to microdata-or-JSON-LD (`90f112d`); 100-fetch run executed at 99/100 success, 0% gate-shell, NOT FRAGILE (`f9ace33`); MEMO Options-tested table updated with both Patchright (historical 0/7) and Camoufox (actual 99/100) rows + Open Risks (post 01-08) subsection (`e13e47a`); SUMMARY → `.planning/phases/01-goldapple-reconnaissance-spike/01-08-SUMMARY.md` (`175d6de`).
  - **Plan 01-11 finalized** MEMO sign-off (commit `70fdffa`) — TL;DR + Chosen + robots/ToS rate-limits + Next-step impact + Open risks + Appendix Challenge-rate + Sign-off block; all 12 obligatory sections populated, zero TBDs; SUMMARY → `01-11-SUMMARY.md` (`e4a5a1b`).
  - **Plan 01-12 wrap-up** (this commit) — Obsidian decision note `knowledge/decisions/Goldapple — Tier 2 Camoufox без proxy, 99 из 100.md` created with frontmatter (tags, date, project, phase, tier, source_memo); project-local skill `.claude/skills/spike-01-goldapple/SKILL.md` created for Phase 3 discuss/plan auto-discovery; STATE.md (this file) updated — Phase 1 closed, Tier 2 in Key Decisions, Phase 2 next; SUMMARY pending.
  - **Plans skipped (formal):** 01-03 (IPRoyal trial — D-08 cancelled), 01-09 (multi-geo proxy — VOI ≈ 0), 01-10 (Tier 3 escalation — trigger never fires). Documented in MEMO Options-tested status block.
- `/gsd-execute-phase 1` plan 01-06 executed (sequential mode, Task 1 substituted by programmatic Patchright network capture per user pre-authorization in spawn prompt):
  - **Task 1 (substituted):** `scripts/01-06-network-hunt.py` — Patchright (chromium persistent context per D-04, headless=False, KZ-laptop direct per D-06, no proxy) probes 7 URLs (home, brands index, 2 brand listings, 3 product/facet pages from selected brands per D-12) at 3-5s rate-limit per 01-04. Page-on-request/page-on-response captures 256 events. Initial 5s wait extended to 20s poll-loop watching for title change off "checking device" + 5s networkidle settle. Commit `0439cb2`.
  - **Loud-flag finding:** 0/7 pages cleared the gate even at 20-25s wait. Deferral gate "≥98/100 + challenge<10%" decisively fails. **Anti-bot vendor identified as GroupIB / F.A.C.C.T.** (Russian-market rebrand of Singapore-based GroupIB) via inline `window.gib.init({cid:'w-goldapple', gafUrl:'ru.id.facct.ru/id.html'})` in challenge HTML — material reorder of escalation tree.
  - **Task 2:** `goldapple-network-trace.md` (human-readable summary: per-page metrics, anti-bot vendor identification, XHR endpoint table including `/web/api/v1/settings` 24/24=403 + telemetry sinks, D-14 ALERT, 5 implications for 01-08, re-run instructions); `goldapple-jsonld-sample.json` is `[]` per D-14 ALERT (challenge shell has no schema.org markup). Commit `42763ca`.
  - **Task 3:** MEMO `## JSON-endpoint hunt verdict (D-09, D-10)` populated — Variant B (Tier 0 not viable, Tier 2+ required) PLUS additional finding that Tier 2 baseline is itself insufficient. 5 explicit implications for 01-08 captured. Commit `a22034a`.
  - 5 files created (1 helper script + 4 sample payloads), 1 modified (`MEMO.md`), 3 deviations (1 blocking-issue resolution = checkpoint substitution; 1 bug-fix = wait-loop logic; 1 artifact-hygiene = byte-equivalent challenge-shell dedup), self-check PASSED.
  - SUMMARY → `.planning/phases/01-goldapple-reconnaissance-spike/01-06-SUMMARY.md`
- Earlier this session: `/gsd-execute-phase 1` plan 01-07 executed (sequential mode, autonomous, 3 tasks; Task 1 substituted by autonomous viled-sitemap probe per user YOLO preference + 01-05 precedent):
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

1. **`/gsd-execute-phase 3 03`** — Wave 2 microdata parser: `parsers/goldapple_microdata.py` priceType-aware extractor (PARSE-01..06) + `detect_state` three-axis classifier (Pitfall 4 / D-303). Wave 1 enumeration primitives ready (slug-fy + intersect + sitemap fetch + week-diff); Wave 0 fixtures (`_debug-product-page.html`, `gate-shell.html`, `stale-sku-9.5kb.html`) cover all parser test surfaces.
2. **`/gsd-discuss-phase 2`** — Project Skeleton + viled Crawl + Storage. Phase 2 viled stack is hot-data ready from 01-07 (curl_cffi + selectolax + `__NEXT_DATA__` parser; 8 canonical field paths; sitemap-driven enumeration; was_price via realPrice; currency map "₸"→"KZT"). Phase 2 does NOT depend on Phase 3 and can run in parallel — Phase 3 codes against `interfaces.py` Protocols, Phase 2 implementations swap in at Wave 5.
3. **Phase 7 hosting decision (pending one smoke fetch):** Hetzner CX22 EU is the working hypothesis. Before locking, one Camoufox+EU smoke fetch against goldapple. If gate passes → no proxy, $0/week. If gate fails → revive D-08 (IPRoyal KZ residential, ~$2/week steady-state). If both fail → managed unblocker (ZenRows / Bright Data Web Unlocker, pay-per-page; reframes economics per D-02).
4. **Phase 3 ops playbook items (deferred to Phase 7):**
   - Weekly Camoufox-vs-goldapple smoke ("does the gate still pass?") — alert if pass-rate <90% or gate-shell rate >5%
   - Camoufox upstream check (daijro releases vs coryking fork) — switch fork if daijro stalls
   - Stale-SKU 200-but-9.5KB rate tracking — if >5%, sitemap may have stale entries needing prune
5. Open follow-ups (Phase 7 backlog): KZ-legal review (30 min с юристом) with bundle = `tos-audit.md` + `viled-privacy.txt` + both `*-robots.txt` snapshots + GroupIB/F.A.C.C.T. vendor flag + Camoufox-fingerprint-spoof note for legal nuance.

### Resume Instructions

To continue this project from a fresh session:

1. Read `.planning/PROJECT.md` for core value and constraints.
2. Read `.planning/ROADMAP.md` for phase structure.
3. Read this STATE.md for current position.
4. Read `.planning/spikes/01-goldapple/MEMO.md` — signed-off decision memo, source-of-truth for Phase 3 stack constraints.
5. Read `.claude/skills/spike-01-goldapple/SKILL.md` — quick-reference Phase 3 entry-point.
6. Run `/gsd-discuss-phase 2` (viled crawl + storage) OR `/gsd-discuss-phase 3` (goldapple crawl). Phase 2 and Phase 3 are independent — order is operator preference.

---
*State initialized: 2026-05-05 by gsd-roadmapper; updated by gsd-plan-phase 2026-05-05; updated by gsd-executor (plan 01-01) 2026-05-05; updated by gsd-executor (plan 01-02) 2026-05-05; updated by gsd-executor (plan 01-04) 2026-05-05; updated by gsd-executor (plan 01-05) 2026-05-05; updated by gsd-executor (plan 01-07) 2026-05-05; updated by gsd-executor (plan 01-06) 2026-05-06; updated by gsd-executor (plans 01-08, 01-11, 01-12) 2026-05-06 — Phase 1 CLOSED; updated by gsd-executor (plan 03-01) 2026-05-06 — Phase 3 Wave 0 done; updated by gsd-executor (plan 03-02) 2026-05-06 — Phase 3 Wave 1 done*
