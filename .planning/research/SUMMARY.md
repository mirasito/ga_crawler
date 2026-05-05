# Project Research Summary

**Project:** GA Crawler — Competitive Pricing Intelligence (viled.kz vs goldapple.kz)
**Domain:** Weekly batch web-scraping pipeline (beauty/cosmetics retail, KZ market)
**Researched:** 2026-05-05
**Confidence:** HIGH on tooling, architecture, feature taxonomy, and known pitfall classes; MEDIUM on goldapple.kz's specific anti-bot tier (must be confirmed empirically before committing to architecture).

## Executive Summary

This is a small internal weekly batch ETL — not a SaaS — whose job is to deliver one well-formatted Excel report (with a Telegram text summary) to the viled.kz commercial team every Monday morning. The well-trodden expert pattern is a **modular monolith in Python** with a pipe-and-filter pipeline (Crawl → Parse → Normalize → Match → Snapshot → Report → Deliver), an **append-only snapshot history keyed by `run_id`** in SQLite, and **system cron** triggering one process on a small VPS. Stack research lands on Python 3.12 + uv + Playwright/curl_cffi + selectolax + SQLModel + pandas/xlsxwriter + aiogram on Hetzner CX22, with a **tiered anti-bot escalation path** (vanilla Playwright → Patchright → residential proxies → Camoufox/Scrapling) for goldapple.kz specifically.

The single project-defining unknown is whether goldapple.kz is scrapable at all, and at what anti-bot tier. PROJECT.md commits to scraping goldapple, so if reconnaissance shows it requires a paid managed unblocker (Tier 4), the project's economics and scope materially change. Three of the four research files independently flag this as the lead risk, and STACK + PITFALLS both recommend a small spike before fixing tooling. ARCHITECTURE recommends building viled-first because viled feeds the goldapple brand list, while PITFALLS recommends probing goldapple first because anti-bot is the dominant unknown. **Reconciliation: a small Phase 1 reconnaissance spike on goldapple (just enough to confirm anti-bot tier and that scraping is feasible at all) — no parsing, no schema, no commitment — followed by the dependency-correct viled-first build order.** This bounds risk early without inverting the natural data flow.

The other risks are well-understood: silent parser drift, Cyrillic↔Latin brand-name divergence (the dominant cause of missed matches in the RU/KZ beauty market), volume/multipack ambiguity, picking the wrong price field (strikethrough vs current vs Gold Card vs "from"), and silent cron failures. All have known prevention patterns: hard-fail invariants, run-level sanity gates, dead-man's-switch monitoring, JSON-LD-first parsing, a brand-alias YAML seeded from viled's top brands, and a stock-state enum (even if v1's UI surfaces it as a boolean — capturing the richer signal in the schema avoids a forced migration in v1.x). Capture strikethrough/`was_price` and track match-rate as a KPI from week 1 — both are nearly free to add now and prohibitively expensive to backfill later.

## Key Findings

### Recommended Stack

The stack is intentionally boring everywhere except anti-bot, where goldapple.kz may force a tooling escalation. Single-process, single-VPS, no Celery, no Docker Swarm, no orchestrators. See `.planning/research/STACK.md` for the full tiered anti-bot strategy.

**Core technologies:**
- **Python 3.12 + uv** — 2026 default for new Python projects; 10–100× faster dep management than pip+venv.
- **Playwright 1.57** — headless browser for goldapple.kz (JS-rendered + anti-bot). Industry standard in 2026.
- **curl_cffi 0.15** — HTTP client with browser TLS/JA3 fingerprinting; drop-in `requests` replacement that defeats the cheap layer of anti-bot. Use for viled.kz directly and for any goldapple endpoints that don't need JS.
- **selectolax** — 10–30× faster than BeautifulSoup; sufficient for product-card extraction.
- **SQLModel + SQLite (WAL mode)** — append-only snapshot history; right tool for "weekly batch, single writer, archival." Migration to Postgres is trivial later via SQLAlchemy 2.x.
- **pandas 2.x + xlsxwriter** — Excel output with conditional formatting, frozen panes, autofilter — what commercial users expect.
- **aiogram 3.27** — async-native Telegram bot for `send_document` + caption.
- **System cron on Hetzner CX22** (~€4.50–€8/month) — single weekly job. APScheduler/Celery/Prefect are overkill.

**Anti-bot escalation tiers (decided per goldapple spike, not project-wide):**
- Tier 0 (viled): curl_cffi `impersonate="chrome"`, no proxy.
- Tier 1: vanilla Playwright + realistic UA + slow rate.
- Tier 2: **Patchright** (drop-in for Playwright; passes Cloudflare/DataDome/Akamai in 2026).
- Tier 3: Patchright + **Decodo or IPRoyal residential proxies** (KZ/RU geo, ~$0.50–$2/run).
- Tier 4: **Camoufox** (maintained `coryking` fork) or **Scrapling StealthyFetcher**; last resort = managed unblocker (ZenRows/Bright Data).

**To avoid:** `requests`, `cloudscraper`, `playwright-stealth v1.x` (unmaintained), Selenium, Celery, Heroku/Fly.io for batch cron.

### Expected Features

Feature taxonomy is well-established across SaaS pricing tools (Prisync, Skuuudle, Competera, Wiser); PROJECT.md has already cleanly eliminated platform-shaped features (dashboards, real-time alerts, repricing, multi-tenant). What remains is the smallest-useful Monday report. See `.planning/research/FEATURES.md`.

**Must have (table stakes — all locked in PROJECT.md):**
- Full viled.kz catalogue parser; brand-scoped goldapple.kz parser
- Field extraction: name, brand, volume, current price, **strike-through/`was_price`**, in-stock, URL, currency
- Strict-key matching: `lower(brand) + lower(name) + normalized_volume`
- Brand and volume normalization tables (seeded from viled's top brands)
- Append-only snapshot storage in SQLite, keyed by `(week_iso, retailer, sku)`
- Excel report (Summary, Per-SKU deltas, Assortment gaps, Goldapple promos)
- Telegram delivery (text headline + xlsx attachment)
- Weekly cron, Sunday night Asia/Almaty
- Run logs + parser-failure alert + retry/backoff + per-SKU isolation
- **Match-rate as a KPI in the headline from week 1** (silent-failure canary)

**Should have (post-v1 cheap wins):** week-over-week price delta column, brand-level aggregate sheet, new/disappeared SKU sheet, match-rate degradation alert, promo-frequency view.

**Defer (v2+):** deterministic fuzzy matching with review queue, Postgres migration, second competitor / dashboard / email channel.

**Anti-features explicitly rejected:** real-time monitoring, ML matching, image scraping, login/Gold-Card pricing, dynamic repricing, MAP compliance, share-of-shelf.

**Two implicit additions worth flagging (not in PROJECT.md but strongly recommended):**
1. **Capture strike-through / `was_price` in the v1 schema even if not surfaced in the v1 report** — PROJECT.md lists "цена до скидки"; keep it in storage from week 1 to avoid a re-crawl backfill later.
2. **Track match-rate as a tracked KPI from day one** — canary for silent matching/parser failure; cheap to compute, expensive to add later because it has no historical baseline.

### Architecture Approach

A modular monolith with a pipe-and-filter pipeline. Each stage is a pure function (or DAO call) wired by a thin orchestrator (`run.py`) inside one process. Side effects (DB, Telegram, files) are isolated to Storage / Reporter / Delivery; Crawl / Parse / Normalize / Match are pure and trivially testable against captured HTML fixtures. The SQLite database is the integration backbone — every cross-stage hand-off goes through it, which makes any phase re-runnable for a `run_id`. See `.planning/research/ARCHITECTURE.md` for the full schema sketch and project layout.

**Major components:**
1. **Orchestrator** — opens `run_id`, sequences phases, aggregates partial-failure status, ensures `runs` row is updated on every exit path.
2. **Crawlers (per-site adapter)** — viled (curl_cffi/httpx) and goldapple (Playwright/Patchright + proxy) behind a common `Crawler` Protocol. Anti-bot strategy lives inside the adapter.
3. **Parsers (per-site)** — JSON-LD first, `__NEXT_DATA__` / inline JSON second, CSS selectors as last-resort fallback. Hard-fail invariants on missing required fields.
4. **Normalizer** — pure functions: brand alias resolution (Cyrillic↔Latin, NFKD + accent strip), volume canonicalization (multipack/kit detection, ml/g/oz unification), name lowercase + punctuation strip.
5. **Matcher** — SQL JOIN on `(brand_norm, name_norm, volume_norm)` between viled and goldapple snapshots; writes `matches` table.
6. **Storage** — SQLite with WAL: `runs` (failure-first), `snapshots` (append-only immutable history), `matches` (precomputed convenience). A `v_current_snapshots` view replaces a "current products" table.
7. **Reporter** — pandas + xlsxwriter; writes a multi-sheet `.xlsx` to disk and a summary string. No Telegram coupling.
8. **Delivery** — aiogram `send_document`; ops chat (failures) and business chat (clean reports) are separate.
9. **Observability** — structlog JSON logs, `runs` row status counts, dead-man's-switch (Healthchecks.io), hard run-level sanity gates before any report is sent.

### Critical Pitfalls

Top five that materially shape the roadmap:

1. **Underestimating goldapple.kz anti-bot.** Building against viled-with-`httpx` first and "adding Playwright later" loses 1–2 weeks. Vanilla Playwright is also detected immediately in 2026. **Mitigation:** probe goldapple first (small spike); design fetch layer with two pluggable backends; residential proxies from start; never use datacenter proxies for goldapple.
2. **Silent parser drift.** A class-name change ships "0 совпадений" with a green checkmark. **Mitigation:** hard-fail invariants; run-level sanity gate (`viled_count > 1000`, `goldapple_count > 500`, `match_count > 100`); golden-product fixtures verified before each run; ops chat separate from business chat.
3. **Volume + multipack normalization eats matches.** `30 мл` ≠ `30мл` ≠ `30ml`; `3×50 мл` matched against single `50 мл` produces a 3× wrong delta. **Mitigation:** `Volume(amount, unit, multipack)` value object; explicit multipack/kit regex pre-pass; kits flagged and excluded from price-per-unit comparison in v1.
4. **Cyrillic vs Latin brand divergence.** `Estée Lauder` / `Эсте Лаудер` / `Estee Lauder` — strict matching loses 30–50% of overlap. PROJECT.md locks in strict-key matching, but a brand alias table is the only way strict matching works in this market. **Mitigation: brand-alias YAML seeded from viled's top-50 brands as a v1 deliverable** (not a v2 nice-to-have); NFKD + accent strip; log "brands seen on goldapple but not in alias table" as a manual review queue.
5. **Wrong price field (strikethrough / Gold Card / "from"-variant) extracted.** Bimodal price distribution and 0% discount on every product are the symptoms. **Mitigation:** JSON-LD `Product.offers.price` first; reject CSS classes containing `old`/`was`/`crossed`/`club`/`gold`/`from`; capture both `current_price` and `original_price`; sanity-check `100 ≤ price ≤ 1_000_000 ₸`.

**Stock signal — schema vs surface tension:** PROJECT.md treats stock as a boolean ("в наличии или нет"), but PITFALLS argues for a richer state enum (`IN_STOCK`, `OUT_OF_STOCK`, `UNAVAILABLE`, `DELISTED`, `URL_CHANGED`, `UNKNOWN`) because conflating "OOS" with "delisted" produces three different downstream bugs. **Recommended resolution: store the enum from week 1, surface it as a boolean (`IN_STOCK` vs everything else) in the v1 report.** This avoids a retroactive schema migration when the team inevitably asks "why does this product keep flickering between weeks?"

## Implications for Roadmap

Suggested phase structure. The first phase is a **timeboxed reconnaissance spike** that reconciles the viled-first vs goldapple-first tension; everything after follows the dependency-correct order from ARCHITECTURE.md.

### Phase 1: Goldapple reconnaissance spike (timeboxed, throwaway)

**Rationale:** Anti-bot on goldapple.kz is the project-defining unknown. STACK.md, PITFALLS.md, and ARCHITECTURE.md all flag it as the top risk; PITFALLS argues for probing goldapple first because if the answer is "Tier 4 / managed unblocker" the project's economics change. We do not invert the build order on the strength of that risk alone, but we do gate everything else on a tiny spike.
**Delivers:** A signed-off answer to: (a) does vanilla Playwright pass goldapple? (b) if not, does Patchright pass it from the Hetzner EU IP? (c) if not, does Patchright + residential proxy pass it? (d) does goldapple expose a JSON catalog endpoint that lets us skip the browser? (e) what's the page-volume estimate for a typical brand's catalog (informs proxy budget)? Output is a one-page decision memo + 100 sequential successful goldapple product fetches in a notebook. Code is throwaway.
**Stack decisions made here:** anti-bot tier (Tier 1/2/3/4), proxy provider (Decodo vs IPRoyal vs none), browser engine (Playwright vs Patchright vs Camoufox).

### Phase 2: Project skeleton + viled crawl + storage

**Rationale:** With anti-bot tier known, build the dependency-correct foundation. Viled feeds the goldapple brand list, so it must be parsed first within each run anyway. Viled is also the easier target — proves the pipeline shape end-to-end before adding goldapple's anti-bot complexity.
**Delivers:** `python -m ga_crawler` runs end-to-end and writes a complete viled.kz snapshot to SQLite; `runs` row updated; structured logs to file. Schema is final (`snapshots`, `runs`, `matches` tables; **`was_price` and stock-state-enum columns present from day 1**, even if not yet surfaced).
**Uses:** Python 3.12 + uv + curl_cffi + selectolax + SQLModel + structlog.
**Implements:** Orchestrator, viled Crawler, viled Parser, Normalizer, Storage DAO.

### Phase 3: Goldapple crawl + parse (anti-bot tier from spike)

**Rationale:** Apply the spike's findings against the now-stable storage and brand-list infrastructure. Brand-list is derived from viled snapshot at run start. Highest-risk phase even after the spike — expect iteration on selectors and proxy/cookie handling.
**Delivers:** Brand-scoped goldapple snapshot writing to the same `snapshots` table; per-SKU failure isolation; sanity assertions (price range, currency, scraped count ≥ 95% of declared total).
**Uses:** Playwright/Patchright (per spike), Decodo or IPRoyal residential proxy (per spike), JSON-LD-first parsing.

### Phase 4: Matcher + brand alias table

**Rationale:** Strict-key matching is locked in PROJECT.md, but the dominant cause of missed matches in this market is Cyrillic↔Latin brand divergence, not weak matching algorithms. The brand-alias YAML is therefore a v1 deliverable, not a v2 nice-to-have. Volume canonicalization (including multipack/kit detection) belongs here too.
**Delivers:** `matches` table populated for a `run_id`; `brand_aliases.yaml` seeded with viled's top-50 brands and observed Cyrillic variants from goldapple; `Volume` value object; "unmapped brands" log as a weekly review queue. **Match-rate is computed and logged.**

### Phase 5: Reporter (Excel + summary)

**Rationale:** Reporting reads from the DB only — no entanglement with delivery. Building it before Telegram lets us iterate on the format with the pricing team using `.xlsx` files on disk.
**Delivers:** Multi-sheet Excel (Summary, Per-SKU deltas, Assortment gaps, Goldapple promos) with conditional formatting and Russian headers; text summary including counts, **match-rate as a tracked KPI from week 1**, top-3 movers; archived to disk.
**Uses:** pandas + xlsxwriter.

### Phase 6: Telegram delivery + ops/business chat split

**Rationale:** Wrap the on-disk report in delivery only after the reporter is rock-solid. Two chats (ops + business) is the precondition for the run-level sanity gate to actually protect the team from broken reports.
**Delivers:** `send_document` with caption to business chat on success; failure alerts to ops chat; pre-send file-size check; rate-limit / retry-after handling.
**Uses:** aiogram 3.27.

### Phase 7: Scheduler + observability hardening

**Rationale:** Manual `python -m ga_crawler` must be rock-solid before automation can hide issues. Schedule last.
**Delivers:** Cron entry with `CRON_TZ=Asia/Almaty`; Healthchecks.io dead-man's-switch (start/success/fail pings); run-level sanity gate enforced before any business-chat delivery; deliberate-failure test confirming ops alert fires and business chat stays clean; nightly SQLite backup.

### Phase Ordering Rationale

- **Why a spike first, not viled first:** anti-bot risk is a binary project-feasibility gate, not a build-order question.
- **Why viled before goldapple in the build:** viled produces the brand list that scopes the goldapple crawl, and viled is the easier target.
- **Why matcher + alias table is its own phase:** strict-key matching is necessary but insufficient in this market; brand aliases are core infrastructure.
- **Why reporter before delivery:** the on-disk Excel is independently testable; coupling them entangles "we built a report" with "Telegram credentials are right."
- **Why scheduler last:** the system that's supposed to alert is the same system being scheduled — manual reliability must precede automation.

### Research Flags

Phases likely needing deeper research during planning (`/gsd-plan-phase`):
- **Phase 1 (Goldapple spike):** the whole phase *is* research.
- **Phase 3 (Goldapple crawl):** depending on spike outcome, may need tier-specific research (e.g., "Patchright + Cloudflare Turnstile + KZ residential" if Tier 3, "self-hosted Camoufox tuning" if Tier 4).
- **Phase 4 (Matcher + aliases):** beauty-vertical Cyrillic↔Latin transliteration patterns are MEDIUM confidence; spot-check 10 known overlapping brands during the phase.

Phases with standard patterns:
- **Phase 2 (Skeleton + viled):** modular monolith + SQLModel + curl_cffi is well-trodden.
- **Phase 5 (Reporter):** pandas + xlsxwriter is industry-standard.
- **Phase 6 (Telegram):** aiogram `send_document` is documented; delivery is a thin wrapper.
- **Phase 7 (Cron + Healthchecks):** standard ops; PITFALLS provides full checklist.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core libraries verified via Context7 + Astral/PyPI/official docs (Jan–May 2026 sources). MEDIUM only on which anti-bot tier goldapple actually needs — by design, that's the spike. |
| Features | HIGH | Feature taxonomy corroborated across 7+ SaaS pricing tools. PROJECT.md scope is already tight. |
| Architecture | HIGH | Modular monolith + append-only snapshot pattern is canonical (SCD Type 2, idempotent ETL). |
| Pitfalls | HIGH on anti-bot mechanics, drift detection, monitoring patterns, product-matching edge cases. MEDIUM on KZ-specific legal exposure. LOW on goldapple's exact anti-bot stack (resolved by spike). |

**Overall confidence:** HIGH. The single MEDIUM-LOW spot — goldapple's anti-bot tier — is explicitly de-risked by Phase 1 before any architecture commitment.

### Gaps to Address

- **Goldapple anti-bot tier (LOW until spike).** Resolved by Phase 1. Outcome dictates Phase 3 stack.
- **viled.kz defense level (LOW).** Assumption is "simpler than goldapple" but unverified. Spike should also probe a single viled product fetch with curl_cffi to confirm.
- **Match-rate baseline for triggering v2 fuzzy matching (LOW).** No public data for cosmetics RU/KZ. Will be observed in weeks 1–4 of v1; threshold for v2 trigger to be set after that.
- **KZ-specific legal exposure for B2B competitive intel (MEDIUM).** robots.txt + ToS review documented in Phase 1; ideally followed by a 30-min local lawyer review before Phase 7.
- **Realistic page-volume estimate for goldapple brand-cross-section (UNKNOWN).** Determines proxy budget. Resolved during Phase 1 spike.
- **Stock-signal DOM patterns per retailer (MEDIUM).** Need to capture into a `stock_signals.md` reference during Phase 2 (viled) and Phase 3 (goldapple).

## Sources

### Primary (HIGH confidence)
- **Context7:** `/microsoft/playwright-python`, `/lexiforest/curl_cffi`, `/aiogram/aiogram`, `/jmcnamara/xlsxwriter`, `/agronholm/apscheduler`, `/scrapy/scrapy`, `/scrapy-plugins/scrapy-playwright`.
- **Official docs / PyPI:** uv (Astral), curl_cffi ReadTheDocs v0.11.4, Patchright GitHub, Camoufox `coryking` fork, aiogram PyPI, SQLModel, Healthchecks.io, tdlib/telegram-bot-api.
- **Canonical:** Wikipedia SCD Type 2; AWS Builders' Library — Timeouts/Retries/Backoff; SQLite Forum on temporal tables; Telegram Bot API; schema.org `Product`.

### Secondary (MEDIUM confidence — multi-source verified)
- **Anti-bot 2026:** Scrapfly, ZenRows, AlterLab, Scrapewise, Browserless (TLS fingerprinting), Datahut (curl_cffi), Round Proxies (residential).
- **SaaS feature landscape:** Prisync, Skuuudle, Price2Spy, Competera, Wiser, Intelligence Node, DataWeave, ClearDemand.
- **Architecture/ETL:** breadcrumbscollector.tech (modular monolith), Hitchhiker's Guide to Python, Pmunhoz Blog (dbt SCD2), Fivetran (idempotent pipelines), Firecrawl reference.
- **Hosting:** 1vps.com (Hetzner vs DO vs Fly.io 2026).
- **Operations:** PromptCloud, Ficstar, ScrapingAnt, Better Stack.

### Tertiary (LOW confidence — single-source or inference)
- **KZ legal:** Adilet (Law 94-V), DLA Piper, Gratanet — would benefit from local lawyer validation.
- **Beauty-vertical Cyrillic↔Latin transliteration patterns:** derived from general normalization principles plus PROJECT.md context.
- **Match-rate threshold for fuzzy-matching trigger:** observed empirically.
- **Goldapple's exact anti-bot stack:** unverified until Phase 1 spike.

---
*Research completed: 2026-05-05*
*Ready for roadmap: yes*
