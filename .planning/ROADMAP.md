# Roadmap: GA Crawler

**Created:** 2026-05-05
**Granularity:** standard
**Phases:** 7
**Coverage:** 48/48 v1 requirements mapped

## Project Reference

**Core Value:** Команда viled.kz один раз в неделю получает детализированный, сопоставленный по позициям отчёт о ценах конкурента (goldapple.kz) и может корректировать собственное ценообразование, видеть ассортиментные разрывы и отслеживать чужие промо-акции.

**Strategy:** Goal-backward delivery. Each phase produces an observable, verifiable outcome. The first phase is a timeboxed reconnaissance spike that resolves the project's defining unknown (goldapple anti-bot tier) before any production code is written. Subsequent phases follow dependency-correct order: viled-first foundation, then goldapple, then matching, then reporting, then delivery, then scheduling.

## Phases

- [ ] **Phase 1: Goldapple Reconnaissance Spike** — Anti-bot tier and proxy provider for goldapple.kz are decided and validated against 100 sequential live product fetches; throwaway code, decision memo committed.
- [ ] **Phase 2: Project Skeleton + viled Crawl + Storage** — `python -m ga_crawler` executes end-to-end against viled.kz (beauty+parfumery scope: /men/catalog/1310 + /women/catalog/1310) and persists a complete, idempotent weekly snapshot with shared parser + normalizer modules.
- [ ] **Phase 3: Goldapple Crawl** — Goldapple snapshots, scoped to viled brands, are written to the same `snapshots` table at the same quality bar as viled, using the anti-bot tier from the spike.
- [ ] **Phase 4: Matcher + Match-Rate KPI** — Strict-key matches between viled and goldapple are persisted per `run_id`, match-rate is logged as a tracked KPI, and a sanity-gate blocks delivery on low match counts.
- [ ] **Phase 5: Reporter (Excel + summary)** — A multi-sheet Russian-headed Excel file and text summary are produced from the database alone, archived to disk, independent of any delivery channel.
- [ ] **Phase 6: Telegram Delivery + Ops/Business Split** — Successful runs deliver Excel + summary to the business chat; failed/incomplete runs deliver alerts only to the ops chat; pre-send sanity-gate enforces the boundary.
- [ ] **Phase 7: Scheduler + Observability Hardening** — Weekly cron in Asia/Almaty fires reliably, dead-man's-switch monitoring catches missed runs, and a deliberate-failure test confirms ops alerts route correctly.

## Phase Details

### Phase 1: Goldapple Reconnaissance Spike

**Goal**: Goldapple anti-bot strategy is decided and proven feasible against 100 live product fetches; project commits to a specific tier (1/2/3/4) and proxy provider before any production code is written.
**Depends on**: Nothing (first phase)
**Requirements**: RECON-01, RECON-02, RECON-03, RECON-04
**Success Criteria** (what must be TRUE):
  1. A signed-off decision memo exists naming the chosen anti-bot tier (1/2/3/4), proxy provider (or none), and browser engine (vanilla Playwright / Patchright / Camoufox) for goldapple.kz.
  2. A reproducible notebook demonstrates 100 sequential successful goldapple product fetches at that tier without manual intervention or captcha encounter.
  3. A page-volume estimate for a typical brand's goldapple catalog is documented (informs proxy budget and run duration expectations).
  4. viled.kz feasibility with `curl_cffi` impersonate is empirically confirmed against ≥10 product fetches.
  5. `robots.txt` and ToS for both sites are reviewed; an acceptable rate-limit per site is documented and committed to the repo.
**Plans**: 12 plans across 5 waves (Wave 0 setup -> Wave 1 cheap recon -> Wave 2 Tier 2 measurement -> Wave 3 conditional Tier 3 -> Wave 4 finalization)
- [x] 01-01-PLAN.md - Spike skeleton (.planning/spikes/01-goldapple/ directory + stub files + .gitignore)
- [x] 01-02-PLAN.md - uv init + Python 3.12 + spike deps (curl_cffi, patchright, selectolax, structlog, python-dotenv) + Patchright Chromium
- [ ] 01-03-PLAN.md - IPRoyal trial registration + .env.local + proxy smoke-test (D-08 pre-registration)
- [x] 01-04-PLAN.md - robots.txt + ToS audit (RECON-04) + committed rate-limits per site
- [x] 01-05-PLAN.md - sitemap.xml + page-volume estimate for 3-5 brands (RECON-03 part 1)
- [x] 01-06-PLAN.md - JSON-endpoint hunt via DevTools (RECON-03 part 2; D-09/D-10 Tier 0 candidate check)
- [x] 01-07-PLAN.md - viled curl_cffi feasibility, >=10 fetches (RECON-02) + side-deliverables for Phase 2
- [ ] 01-08-PLAN.md - Patchright Tier 2 100-fetch from KZ-laptop baseline (RECON-01; D-01/D-04/D-13/D-14/D-15)
- [ ] 01-09-PLAN.md - Patchright Tier 2 100-fetch through EU/RU residential proxy (RECON-01; D-05 multi-geo)
- [ ] 01-10-PLAN.md - CONDITIONAL Tier 3 escalation if 01-08/01-09 fail or fragile (RECON-01)
- [ ] 01-11-PLAN.md - MEMO.md decision-memo finalization with sign-off (closes RECON-01..04)
- [ ] 01-12-PLAN.md - Wrap-up: Obsidian copy + project skill + STATE.md update
**UI hint**: no

### Phase 2: Project Skeleton + viled Crawl + Storage

**Goal**: `python -m ga_crawler` runs end-to-end against viled.kz, writes a complete idempotent weekly snapshot to SQLite, and the shared parser/normalizer modules (designed to handle goldapple in Phase 3) are exercised against real viled HTML.
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, CRAWL-01, CRAWL-03, CRAWL-04, CRAWL-05, CRAWL-06, PARSE-01, PARSE-02, PARSE-03, PARSE-04, PARSE-05, PARSE-06, NORM-01, NORM-02, NORM-03, NORM-04, NORM-05, NORM-06
**Success Criteria** (what must be TRUE):
  1. Running `python -m ga_crawler` opens a `runs` row, crawls the viled.kz beauty+parfumery catalog (`/men/catalog/1310` + `/women/catalog/1310`) with retry/backoff and per-SKU isolation, and writes immutable snapshots in a single per-run transaction (with WAL enabled).
  2. The `runs` row is closed (success/partial/failed) on every code path, including crashes and sanity-gate failures; nightly DB backup directory contains at least the last 4 backups.
  3. The viled snapshot for a run contains all required fields (name, brand, volume_raw, current_price, was_price, currency, stock_state enum, url, brand_norm, name_norm, volume_norm, multipack_flag, scraped_at) with <5% null rate on required fields, otherwise the run is marked `failed`.
  4. The brand-alias YAML (seeded with viled's top-50 brands and Cyrillic↔Latin variants) and Volume value object correctly normalize a documented test suite of real strings (including `30 мл`, `30мл`, `30ml`, `1.0 oz`, `3 шт x 50мл`, kits/sets); kits are flagged and excluded from price-per-unit comparison.
  5. A sanity-assertion gate after the crawl marks the run `failed` when `viled_count < N` (configurable threshold), preventing downstream phases from running on bad data.
**Plans**: 6 plans across 6 waves (Wave 0 bootstrap -> Wave 1 storage -> Wave 2 normalizers -> Wave 3 viled parser/fetcher/enumeration -> Wave 4 gates+orchestrator+CLI cutover -> Wave 5 alias seed+backup+doc cascades)
- [x] 02-01-PLAN.md - Wave 0: pyproject [tool.ga_crawler.crawl.viled] namespace + PyYAML dep + Wave 0 live probe (A1/A2/A3/A4/A10) + 5 viled fixtures + volume/brand corpus YAMLs + 24 skip-marked test stubs + 02-WAVE0-PROBE.md memo
- [x] 02-02-PLAN.md - Wave 1: storage/sqlite.py SQLModel Run+Snapshot tables + WAL engine + atomic json_patch RunWriter (Pitfall 6) + per-batch SnapshotWriter (DATA-04) + v_current_snapshots VIEW (D-221); storage/norm06_writer.py markdown ledger (D-208/D-211); 7 test files GREEN
- [x] 02-03-PLAN.md - Wave 2: alias/yaml_loader.py YamlBrandAlias (read-once D-207) + normalizers/{brand,name,volume}.py (NORM-02/05/03/04 — REUSE _normalize_punct from slug.py) + facade.py Normalizer satisfying NormalizerProtocol; 4 test files GREEN
- [x] 02-04-PLAN.md - Wave 3: parsers/viled_nextdata.py (PARSE-01..04, PARSE-06 — __NEXT_DATA__ first, NO json-ld) + parsers/dispatcher.py (PARSE-02 routing) + enumeration/viled_catalog.py (__NEXT_DATA__ pagination D-224 — runtime SSR-pagination guard, v1 page-1-only fallback documented) + fetchers/viled.py (curl_cffi sync + tenacity 3-retry + per-SKU isolation + 2s rate-limit per D-225, exception types from .exceptions per A10) + config.py ViledConfig loader; 8 test files GREEN, +74 tests, 321 passed
- [x] 02-05-PLAN.md - Wave 4: runner/gates.py D-203 retailer-agnostic refactor + parse_quality_gate (D-218) + Phase 3 backward-compat shims; runner/stats.py ViledStatsBuilder mirror; runners/viled_run.py 8-step orchestrator with sequential parse-quality + sanity-N gates + atomic patch_stats; runners/main_run.py composition with try/except DATA-05 lifecycle; cli.py D-212 cutover (DELETED 4 stubs + goldapple-run; ADDED weekly-run); 9 test files GREEN, +60 tests, 381 passed
- [x] 02-06-PLAN.md - Wave 5: config/brand-aliases.yaml seeded with 58 viled brands (D-206 — 46 Cyrillic aliases); bin/backup.sh (online sqlite3 .backup + 4-rotate D-219); backups/ dir + .gitignore; tests/integration/test_backup_script.py (DATA-06 — 4 integration tests); CONTEXT Action Items cascade to REQUIREMENTS.md/PROJECT.md/STATE.md/ROADMAP.md (scope-narrowing to /men/catalog/1310 + /women/catalog/1310)
**UI hint**: no

### Phase 3: Goldapple Crawl

**Goal**: Goldapple snapshots, restricted to brands present in the current run's viled snapshot, are written to the same `snapshots` table at the same quality bar as viled, using the anti-bot tier decided in Phase 1.
**Depends on**: Phase 2
**Requirements**: CRAWL-02
**Success Criteria** (what must be TRUE):
  1. The goldapple crawler derives its brand list from the current run's viled snapshot (not a static list) and respects the alias table when filtering, so Cyrillic-only goldapple brand pages are reached.
  2. Goldapple snapshots written to the `snapshots` table pass the same per-SKU isolation, retry/backoff, rate-limit, and parse-quality invariants used for viled (re-using the Phase 2 parser/normalizer modules).
  3. The post-crawl sanity-assertion gate marks the run `failed` when `goldapple_count < M` (configurable threshold) — a single gate now protects both retailers.
  4. A 1-hour live run completes without sustained 429/503 spikes or Cloudflare interstitial encounters at the chosen tier; per-page proxy/cookie reuse is verified.
  5. The "brands seen on goldapple but not in alias table" review queue (defined in Phase 2) is populated by a real goldapple run and committed for weekly manual review.
**Plans**: 8 plans across 8 waves (Wave 0 bootstrap -> Wave 1 enumeration -> Wave 2 parser -> Wave 3 fetcher -> Wave 4 gates+stats -> Wave 5 orchestrator+CLI -> Wave 6 live smoke checkpoint -> Wave 7 gap-closure: brand-token bucket index for CRAWL-02)
- [x] 03-01-PLAN.md - Wave 0: pyproject.toml pins (Camoufox 135.0.1.beta24, tenacity, sqlmodel, pydantic, pytest), interfaces.py Phase 2 Protocols, conftest.py fixtures, spike sample-payloads as test fixtures
- [x] 03-02-PLAN.md - Wave 1: enumeration/slug.py bilingual slug-fy + intersect_brand_pool (CRAWL-02), enumeration/goldapple_sitemap.py curl_cffi Tier 0 + week-over-week NEW slug diff (D-307)
- [x] 03-03-PLAN.md - Wave 2: parsers/goldapple_microdata.py priceType-aware extractor (PARSE-01..06) + detect_state three-axis classifier (Pitfall 4 / D-303)
- [x] 03-04-PLAN.md - Wave 3: fetchers/goldapple.py Camoufox bootstrap + tenacity retry (CRAWL-04) + per-SKU isolation (CRAWL-03) + run_loop with rate-limit (CRAWL-06)
- [x] 03-05-PLAN.md - Wave 4: runner/gates.py smoke probe (D-312) + final M-gate (D-308/D-309) + auto-suggest M (D-310); runner/stats.py 13-key namespace (Pitfall 6) + NORM-06 forward (D-306)
- [x] 03-06-PLAN.md - Wave 5: runners/goldapple_run.py orchestrator + cli.py (python -m ga_crawler) + stub Phase 2 protocol implementations + storage integration tests
- [x] 03-07-PLAN.md - Wave 6: Manual operator checkpoint - live smoke probe + limited live run on KZ-laptop; Success Criteria 4 and 5 verification
- [x] 03-08-PLAN.md - Wave 7 (gap_closure): brand-token bucket index in goldapple_sitemap.py + intersect_brand_pool refactor to brand_bucket shape; closes CRAWL-02 BLOCKER from 03-VERIFICATION.md (Truth 1: matched_url_count=0 against real 45,490-slug sitemap)
**UI hint**: no

### Phase 4: Matcher + Match-Rate KPI

**Goal**: Per-`run_id` strict-key matches between viled and goldapple are persisted with price deltas, match-rate is computed and logged as a tracked KPI from week 1, and a sanity-gate blocks delivery on low match counts.
**Depends on**: Phase 3
**Requirements**: MATCH-01, MATCH-02, MATCH-03, MATCH-04
**Success Criteria** (what must be TRUE):
  1. For each `run_id`, the `matches` table contains one row per `(brand_norm, name_norm, volume_norm)` pair found in both viled and goldapple snapshots, with `price_delta` and `price_delta_pct` populated.
  2. Match-rate (`matches / viled_skus_with_brand_in_goldapple_brands * 100%`) is computed, logged in structured JSON, and stored on the `runs` row for every run — establishing the historical baseline from week 1.
  3. A configurable match-count sanity-gate (`match_count > P`) marks the run `failed` and records the failure reason on the `runs` row when the threshold is not met.
  4. The matcher is idempotent for a given `run_id` — re-running matching against existing snapshots produces the same `matches` rows without re-crawling.
**Plans**: TBD
**UI hint**: no

### Phase 5: Reporter (Excel + summary)

**Goal**: A multi-sheet Russian-headed Excel file and text summary are produced from the database alone for any successful `run_id`, archived to disk, completely independent of any delivery channel.
**Depends on**: Phase 4
**Requirements**: REPORT-01, REPORT-02, REPORT-03, REPORT-04, REPORT-05, REPORT-06
**Success Criteria** (what must be TRUE):
  1. For a successful `run_id`, a `.xlsx` file is written to `reports/YYYY-WNN.xlsx` with sheets `Summary`, `Per-SKU deltas`, `Assortment gaps`, `Goldapple promos`, all with Russian column headers, frozen panes, autofilter, and conditional formatting on price-delta columns (green = viled cheaper, red = viled more expensive).
  2. A text summary string is generated containing `viled_count`, `goldapple_count`, `match_count`, `match_rate %`, assortment-gap size, top-3 largest deltas, and goldapple promo count — all computed from the DB only.
  3. The reporter reads exclusively from the database (no Telegram, no network, no orchestrator state) and can be invoked for any historical `run_id` to regenerate its archive.
  4. Pre-send file-size validation raises an explicit error if the `.xlsx` exceeds 45 MB (Telegram 50 MB limit guard) — visible to the operator before any delivery is attempted.
**Plans**: TBD
**UI hint**: no

### Phase 6: Telegram Delivery + Ops/Business Split

**Goal**: Successful runs deliver Excel + summary to the business chat; failed or incomplete runs deliver alerts only to the ops chat; the pre-send sanity-gate guarantees a broken report cannot reach the pricing team.
**Depends on**: Phase 5
**Requirements**: DELIVER-01, DELIVER-02, DELIVER-03, DELIVER-04, DELIVER-05
**Success Criteria** (what must be TRUE):
  1. On `runs.status = 'success'`, the business chat receives the text summary as caption + the archived `.xlsx` via `send_document`; the ops chat receives nothing extra.
  2. On `runs.status != 'success'`, the business chat receives nothing and the ops chat receives an alert containing run_id, the failed phase, and the recorded error — verified by a deliberate-failure test.
  3. Bot configuration (`TG_BOT_TOKEN`, `TG_BUSINESS_CHAT_ID`, `TG_OPS_CHAT_ID`) is loaded from ENV; missing variables produce an ops-chat alert (or, if the bot itself can't start, a fail-loud crash logged to disk).
  4. Telegram rate-limit / `retry-after` is honored on transient failures; if Telegram is unreachable after retries, the report remains on disk and is marked as undelivered for manual recovery.
**Plans**: TBD
**UI hint**: no

### Phase 7: Scheduler + Observability Hardening

**Goal**: A weekly cron entry in Asia/Almaty fires reliably on Sunday night with the report arriving Monday morning, dead-man's-switch monitoring catches missed runs, and a deliberate-failure test confirms ops alerts route correctly end-to-end.
**Depends on**: Phase 6
**Requirements**: SCHED-01, SCHED-02, SCHED-03, SCHED-04, SCHED-05
**Success Criteria** (what must be TRUE):
  1. A system cron entry on the VPS uses `CRON_TZ=Asia/Almaty` and runs `python -m ga_crawler` in the night of Sunday → Monday; the first scheduled run lands at the expected Almaty time (no UTC drift).
  2. Healthchecks.io (or equivalent) receives `/start`, `/success`, and `/fail` pings from the run; a deliberately skipped run triggers an external alert independent of the scraper itself.
  3. Structured JSON logs (structlog) are written to disk with rotation; a single `tail`/`grep` session shows run progress, retries, and errors with `run_id` bound as context.
  4. A `README.md` documents from-scratch VPS setup (uv install, Playwright deps, cron entry, ENV vars, healthcheck URL) and includes a deliberate-failure test procedure that confirms the ops alert fires and the business chat stays clean.
  5. End-to-end: a deliberately broken parser run shows the ops chat receives an alert, the business chat receives nothing, Healthchecks records a failure, and the `runs` row is `failed` with the error captured.
**Plans**: TBD
**UI hint**: no

## Phase Dependencies

```
Phase 1 (Spike — decision memo)
    ↓
Phase 2 (Skeleton + viled + shared parser/normalizer + storage)
    ↓
Phase 3 (Goldapple crawl, re-uses Phase 2 modules)
    ↓
Phase 4 (Matcher + match-rate KPI)
    ↓
Phase 5 (Reporter — DB-only, file on disk)
    ↓
Phase 6 (Telegram delivery + ops/business split)
    ↓
Phase 7 (Scheduler + observability hardening)
```

Strict linear dependency. The `snapshots` table is the integration backbone — every phase from 2 onward reads/writes through it, which makes any phase re-runnable for a given `run_id`.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Goldapple Reconnaissance Spike | 9/12 | Complete (3 plans skipped) | 2026-05-06 |
| 2. Project Skeleton + viled Crawl + Storage | 6/6 | Complete | 2026-05-07 |
| 3. Goldapple Crawl | 8/8 | Complete | 2026-05-06 |
| 4. Matcher + Match-Rate KPI | 0/0 | Not started | - |
| 5. Reporter (Excel + summary) | 0/0 | Not started | - |
| 6. Telegram Delivery + Ops/Business Split | 0/0 | Not started | - |
| 7. Scheduler + Observability Hardening | 0/0 | Not started | - |

## Coverage Validation

**v1 requirements:** 48 total
**Mapped:** 48
**Unmapped:** 0
**Duplicates:** 0

| Category | Count | Phase(s) |
|----------|-------|----------|
| RECON-01..04 | 4 | Phase 1 |
| CRAWL-01, 03, 04, 05, 06 | 5 | Phase 2 |
| CRAWL-02 | 1 | Phase 3 |
| PARSE-01..06 | 6 | Phase 2 (modules shared with Phase 3) |
| NORM-01..06 | 6 | Phase 2 (modules shared with Phase 3) |
| DATA-01..06 | 6 | Phase 2 |
| MATCH-01..04 | 4 | Phase 4 |
| REPORT-01..06 | 6 | Phase 5 |
| DELIVER-01..05 | 5 | Phase 6 |
| SCHED-01..05 | 5 | Phase 7 |

**Note on count:** REQUIREMENTS.md `Coverage` block reports "47 total" but enumerated requirements (RECON 4 + CRAWL 6 + PARSE 6 + NORM 6 + MATCH 4 + DATA 6 + REPORT 6 + DELIVER 5 + SCHED 5) sum to 48. Roadmap maps the actual 48 enumerated IDs; the `Coverage` summary in REQUIREMENTS.md should be corrected to 48 during the next requirements update.

## Notes

- **Phase 1 produces no production code.** It is a timeboxed reconnaissance spike whose only output is a decision memo, a feasibility notebook, and a robots/ToS audit. If the memo concludes "Tier 4 / managed unblocker required," Phase 3's stack and budget materially change before any code is written.
- **Phase 2 builds shared infrastructure exercised on viled.** PARSE-* and NORM-* modules are designed and built in Phase 2 against viled HTML, but the same modules will handle goldapple in Phase 3 — they are shared infrastructure, not viled-specific. The brand-alias YAML is seeded from viled's top-50 brands in Phase 2 and grown with goldapple Cyrillic variants in Phase 3.
- **CRAWL-05 (sanity-assertion) spans Phase 2 and Phase 3.** The viled threshold (`viled_count > N`) is enforced in Phase 2; the goldapple threshold (`goldapple_count > M`) is added to the same gate in Phase 3.
- **Match-rate KPI baseline.** Phase 4 begins logging match-rate from week 1, which is necessary for the v2 fuzzy-matching trigger condition ("match-rate stable below acceptable after 4 weeks").
- **Backend-only project, no UI.** Every phase has `**UI hint**: no`. Output surfaces are: SQLite database, on-disk Excel files, structured JSON logs, Telegram messages.

---
*Roadmap created: 2026-05-05*
