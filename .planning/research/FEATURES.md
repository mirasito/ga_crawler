# Feature Research

**Domain:** Competitive e-commerce price intelligence (internal tool, single beauty retailer, two .kz sites, weekly cadence)
**Researched:** 2026-05-05
**Confidence:** HIGH (feature taxonomy is well-established across Prisync / Price2Spy / Skuuudle / Competera / Wiser / DataWeave / Intelligence Node; the specific PROJECT.md scope is already tightly constrained by the user)

---

## Framing — What This Tool Actually Is

This is **not** a competitive-intelligence SaaS. It is a small internal pipeline producing **one weekly report** for the viled.kz commercial team comparing **two retailers** (viled.kz vs goldapple.kz) on **public prices only**. PROJECT.md has already eliminated whole categories of features (real-time, dashboards, ML matching, multi-competitor, login-gated prices). The job here is to ruthlessly distinguish what the team needs in the Monday-morning Excel from what would just inflate scope.

A useful mental model: a SaaS like Prisync sells the *platform*. This project sells the *report*. So features that exist to make a platform marketable (dashboards, dynamic repricing rules, integrations, multi-tenant alerts) become anti-features here.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Without these, the pricing team will not trust or use the report. PROJECT.md already commits to all of these — they are non-negotiable.

#### Crawling / Parsing

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Full catalogue discovery on viled.kz | Without it the report's denominator (our assortment) is wrong; assortment-gap analysis requires it | MEDIUM | Likely category/sitemap walk; 1000s of SKUs not 100k. Locked in PROJECT.md |
| Targeted catalogue discovery on goldapple.kz, scoped to viled.kz brands | Goldapple has ~100k SKUs; only overlapping brands are useful and safer to crawl. Locked in PROJECT.md | MEDIUM | Brand list derived from viled.kz pass; iterate brand-by-brand |
| Product attribute extraction: name, brand, volume/weight, current price, original/strike-through price, in-stock flag, URL | Every comparison row depends on these fields; "price" alone is not enough — promo detection needs original price | MEDIUM | Per-site parsers with selector-based extraction; volume is the trickiest field (often embedded in name) |
| Promotional price detection (current price vs MSRP / strike-through) | The team explicitly cares about goldapple promos; without strike-through detection a 30%-off SKU looks like a permanent low price | LOW–MEDIUM | Mostly a parser concern: capture both prices, derive `is_on_promo = strike != null && current < strike` |
| Stock / availability detection | "Out of stock" prices are noise and shouldn't drive pricing decisions; goldapple frequently lists OOS items | LOW | Boolean per SKU; usually a DOM signal ("В наличии" / button state) |
| Anti-bot resilience for goldapple.kz (headless / proxy / pacing) | Without this the crawl simply fails. Locked in PROJECT.md | HIGH | Stack research handles the *how*; the *requirement* is non-negotiable |
| Idempotent weekly snapshot (re-runs don't duplicate or corrupt history) | A failed Sunday run gets re-run Monday; the team must trust there's exactly one snapshot per week | LOW | Snapshot keyed by `(retailer, week_iso)`; upsert semantics |

#### Product Matching

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Strict normalized-key matching: `lower(brand) + lower(name) + normalized_volume` | The whole report hinges on "same product, two prices." Without matching there is no comparison. Locked in PROJECT.md | MEDIUM | Normalization is the actual work: lowercase, strip punctuation, normalize ml/мл/g/г, collapse whitespace, strip vendor codes |
| Brand normalization (synonyms, transliteration, casing) | Beauty brands routinely appear as `L'Oréal` / `L'Oreal` / `Лореаль` / `loreal`. Without a synonym map, half the matches die silently | MEDIUM | Hand-curated brand dictionary seeded from viled.kz brand list; grows over weeks |
| Volume normalization (50ml = 50 мл = 50 ML = 0.05L) | Same reason — silent match loss. Cosmetics units are messy: ml, g, шт, set sizes | LOW–MEDIUM | Regex + unit table; locked to canonical `(value, unit)` tuple |
| Match-rate visibility in the report (X of Y viled SKUs matched on goldapple) | The team needs to know when matching is degrading vs the assortment is genuinely diverging | LOW | One number in the Telegram summary; trend it week over week |

#### Reporting

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-SKU price delta table (matched products, our price, their price, abs delta, % delta) | Core deliverable. Locked in PROJECT.md | LOW | One sheet in the Excel; sortable by % delta |
| Assortment summary (total SKUs each side, matched count, match rate %) | Headline KPI for the Telegram message | LOW | Aggregates of the same data |
| Assortment gap list (brands/products on goldapple not on viled, scoped to overlapping brands) | One of three explicit use cases in PROJECT.md ("ассортиментные разрывы") | LOW–MEDIUM | Just a `LEFT ANTI JOIN`; need a brand-overlap filter so it's actionable |
| Promo monitoring sheet (goldapple SKUs currently with strike-through, discount %) | Explicit use case #3 in PROJECT.md | LOW | Filter on `is_on_promo = true` from snapshot |
| Telegram text summary (top-line numbers + Excel attachment) | Locked in PROJECT.md | LOW | python-telegram-bot or raw Bot API; the summary is ~10 lines |
| Excel-friendly output (xlsx with frozen headers, sortable, no merged cells) | Pricing teams live in Excel filters/pivots; a CSV is a downgrade | LOW | `openpyxl` or `pandas.to_excel`; small effort, high satisfaction |

#### Delivery

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Weekly cron-triggered run, Sunday night → Monday morning delivery | Locked in PROJECT.md; Monday delivery is the entire point | LOW | OS cron / systemd timer / cloud scheduler — pick one in stack research |
| Telegram bot delivery (text + Excel) | Locked in PROJECT.md; team lives in Telegram | LOW | One bot, one chat (group or DM) |

#### History / Analytics

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Persistent history of every weekly snapshot in DB (not just the latest) | Locked in PROJECT.md; required for week-over-week deltas and promo trends | LOW | SQLite v1; schema: `snapshot(week, retailer, sku, price, was_price, in_stock, ...)` |
| Week-over-week price change column in the report | "Same SKU, what changed since last Monday" is the highest-signal column for a pricing manager | LOW | Self-join `snapshot` on `week-1` |

#### Operations

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Run logs (started, finished, duration, counts per stage) | Locked in PROJECT.md; the team needs to know whether Monday's data is real or stale | LOW | Structured logs to file + stdout; one log per weekly run |
| Parser-failure alerting (Telegram message when a run fails or counts drop suspiciously) | Silent failure is the #1 risk in scraping per industry consensus. If goldapple parser breaks on Sunday and nobody notices, Monday's report is wrong | MEDIUM | Two checks: (a) hard failure → exception → alert; (b) "soft failure" → SKU count this week << last week → alert |
| Retry with exponential backoff on transient errors (429, 5xx, timeouts) | Industry standard; without it a transient blip kills the whole run | LOW | tenacity / urllib3 Retry; standard pattern |
| Per-SKU failure isolation (one bad page doesn't kill the run) | A single malformed product page on goldapple should not invalidate the entire crawl | LOW | try/except around parse, log + continue, dead-letter list |

---

### Differentiators (Worth Adding If Cheap, But Not for v1)

These are where commercial tools compete. For an internal weekly report most of them are **not justified** — but a few are cheap enough that they'd add real signal once v1 is live.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Per-SKU price history chart (small PNG embedded in Telegram or extra Excel sheet) | Pricing managers love trend lines; one glance shows "they've been undercutting us for 6 weeks" | MEDIUM | Cheap-ish with matplotlib; defer until v1 ships and team asks |
| Brand-level summary sheet (avg delta % per brand, # SKUs per side, share of overlap) | Useful for category managers ("we lose worst on La Roche-Posay this week"); just an aggregate over the per-SKU sheet | LOW | Add in v1.x once the team confirms they want it |
| Promo-history tracking (this SKU went on promo X weeks ago; promo frequency per brand) | Lets the team predict goldapple's next campaign window | MEDIUM | Already implicit in the snapshot history; just a query |
| New / disappeared SKU detection (week-over-week additions and removals on each side) | Surfaces both assortment opportunities and competitor delisting signals | LOW | `FULL OUTER JOIN` on adjacent snapshots |
| Matching review queue (low-confidence matches surfaced in a sheet for human override) | Catches the ~5–15% of products the strict key misses; a manual override file feeds back into normalization | MEDIUM | Only useful once fuzzy matching is added (v2). Skip for v1 |
| Configurable brand-of-interest filter in the report | Lets the team focus a given week on a category they're repricing | LOW | One CLI/env flag; easy add post-v1 |
| Extra delivery channel — email or Google Sheets push | Nice for archiving / forwarding outside Telegram | LOW–MEDIUM | Defer; Telegram + xlsx already covers requirement |
| Currency/FX-aware comparison (KZT vs RUB if goldapple displays RU prices in some surfaces) | Goldapple.kz should serve KZT, but a sanity check column protects against accidentally comparing currencies | LOW | Cheap insurance; record `currency` field in snapshot |
| Match-rate trend alert (alert when match rate drops > N% week-over-week) | Catches silent matching regressions caused by site HTML changes | LOW | One extra threshold check in operations |

---

### Anti-Features (Tempting But Wrong For This Tool)

Features SaaS pricing tools advertise that the team will not benefit from — and that would explode scope, cost, or risk.

| Feature | Why Requested / Surface Appeal | Why Problematic Here | Alternative |
|---------|-------------------------------|----------------------|-------------|
| Real-time / hourly / daily monitoring | "Faster is better" intuition; SaaS marketing | Weekly cadence is locked; daily crawls multiply anti-bot risk on goldapple by 7x and add zero business value to a weekly pricing review | Stay weekly per PROJECT.md |
| Real-time price-change alerts (Telegram ping per SKU) | Sounds responsive | Pricing managers don't act per SKU per hour; alerts become noise; weekly digest is the actual workflow | Aggregate in the Monday report |
| Web dashboard / charts UI | Looks professional in demos | Excel + Telegram already match the team's tooling; a dashboard is a second product to maintain with no users | Excel sheet with frozen panes |
| ML / deep-learning fuzzy product matching | Marketed by Competera / DataWeave / Intelligence Node | Two-retailer overlap on a single language pair (RU/KZ) does not justify ML infra; strict key + brand/volume normalization will hit acceptable coverage. Locked in PROJECT.md as v2 | Strict key v1; deterministic fuzzy (token sort ratio) only if v1 coverage is poor |
| Image-based matching | Some SaaS use it for marketplace dedup | Both sites have structured product names; image matching is huge effort for marginal lift on overlapping brands | Skip entirely |
| Login-gated / Gold Card / personalized pricing | "We want the *real* price" | Account-blocking risk, ToS violations, and viled.kz competitor is the *public* price; comparing public-to-loyalty is unfair anyway. Locked out in PROJECT.md | Public price only |
| Dynamic repricing / auto-adjustment of viled.kz prices | Headline feature of Prisync, Wiser, Omnia | Out of scope; this tool informs human decisions, it does not write to viled.kz catalogue | Humans set prices using the report |
| Multi-competitor / multi-marketplace expansion (Mechta, Sulpak, Wildberries…) | "While we're at it…" | Each new site is a new parser, new anti-bot story, new normalization edge cases — and goldapple alone covers the strategic question. Locked out in PROJECT.md | Add a second competitor only after v1 ships and the team explicitly requests it |
| MAP (Minimum Advertised Price) compliance reporting | Standard SaaS feature | viled.kz is a retailer, not a brand owner; MAP enforcement is the brand's job, not theirs | Skip |
| "Share of shelf" / digital-shelf ranking (search result position) | Hot topic in retail intelligence (Particl, Intelligence Node) | Requires crawling search results pages (very different parser) and is a marketing/SEO question, not a pricing-team question | Skip |
| Image and description scraping | Convenient for a richer "product detail" view | Multiplies bandwidth, storage, and parse complexity for zero pricing value. Locked out in PROJECT.md | Name + brand + volume + price only |
| Multi-tenant / per-user / role-based access | SaaS necessity | Single team, one chat, no auth model needed | One Telegram chat, done |
| In-tool ticketing / annotation / approval workflows | Enterprise add-ons | Excel comments + chat already cover this | None needed |
| API / external integrations (Shopify, Magento, ERP) | Standard SaaS bullet | viled.kz integration is a separate, much bigger project; the report is the integration | None for v1 |
| Forecasting / predictive pricing (ML-based price recommendations) | Competera/Wiser headline feature | Forecasting on 2 retailers × ~weekly observations is statistically thin; pricing managers want *visibility*, not predictions | Show history, let humans decide |
| CDC (change-data-capture) streaming pipeline | "Modern data stack" appeal | Weekly snapshots written to a single SQLite/Postgres are sufficient; CDC is a hammer for an entirely different problem (continuous downstream consumers) | Snapshot table + week-over-week query |

---

## Feature Dependencies

```
[Catalogue discovery (viled)]
    └──feeds──> [Brand list]
                   └──scopes──> [Catalogue discovery (goldapple)]
                                       └──feeds──> [Product extraction]
                                                          └──feeds──> [Snapshot storage]
                                                                            ├──feeds──> [Matching]
                                                                            │              └──feeds──> [Per-SKU delta report]
                                                                            │              └──feeds──> [Assortment gap list]
                                                                            ├──feeds──> [Promo report] (needs strike-through field)
                                                                            └──feeds──> [Week-over-week deltas]
                                                                                              └──feeds──> [Match-rate trend alert]

[Snapshot storage] ──requires──> [Idempotent weekly key]
[Brand normalization] ──enables──> [Matching]
[Volume normalization] ──enables──> [Matching]
[Run logs] ──enables──> [Parser-failure alerting]
[Retry logic] ──reduces failures into──> [Run logs]
[Per-SKU failure isolation] ──prevents──> [Whole-run loss from one bad page]
[Telegram text summary] ──depends on──> [Excel report] (summary numbers come from the same data)
```

### Dependency Notes

- **Goldapple crawl requires viled brand list:** the brand-scoping decision in PROJECT.md means viled.kz must be parsed first within each weekly run. Sequence within the run, not just within the roadmap.
- **All reports require snapshot storage:** the schema design is upstream of every reporting feature; getting it right early avoids painful rewrites once history accumulates.
- **Normalization is upstream of matching, not bundled with it:** a matching bug is usually a normalization bug. Build normalization as a separately testable layer with its own unit tests so the brand/volume dictionaries can grow without breaking matching.
- **Promo detection requires capturing strike-through during parsing, not derived later:** if v1 only stores `current_price`, the team will ask for promo detection in v1.1 and the only way to backfill is re-crawl. Capture both prices in the v1 schema even if the v1 report doesn't surface them.
- **Match-rate alerts depend on history:** these can't run on the first crawl; they activate from week 2 onward.
- **Per-SKU failure isolation is a precondition for retry logic being useful:** without isolation, the retry just re-fails the whole batch.

---

## MVP Definition

### Launch With (v1) — The Smallest Useful Monday Report

A v1 the team will actually open every Monday:

- [ ] **viled.kz full catalogue parser** — denominator of every comparison
- [ ] **goldapple.kz brand-scoped catalogue parser** — competitor side of comparison
- [ ] **Field extraction with strike-through and stock** — even if v1 reports don't use them, capture in schema
- [ ] **Brand + volume normalization tables** — seeded by hand from the viled.kz catalogue
- [ ] **Strict-key matching (`brand+name+volume`)** — locked in PROJECT.md
- [ ] **Snapshot storage in SQLite, keyed by `(week_iso, retailer, sku)`** — idempotent
- [ ] **Excel report with sheets: Summary, Per-SKU deltas, Assortment gaps, Goldapple promos**
- [ ] **Telegram delivery: text headline (counts, match rate, top movers) + xlsx attachment**
- [ ] **Weekly cron, Sunday night**
- [ ] **Run logs + parser-failure Telegram alert** — silent-failure prevention
- [ ] **Retry with backoff + per-SKU failure isolation**
- [ ] **Match rate printed in the headline** — visibility into matching health from week 1

That's it. No charts, no dashboard, no fuzzy matching, no extra channels.

### Add After Validation (v1.x) — Cheap Wins Once v1 Works

- [ ] **Week-over-week price delta column in per-SKU sheet** — trigger: history has 2+ weeks
- [ ] **New / disappeared SKU sheet** — trigger: team asks "what's new?"
- [ ] **Brand-level aggregate sheet** — trigger: team filters Excel by brand every Monday
- [ ] **Match-rate degradation alert** — trigger: a parser break ships an under-counted report
- [ ] **Promo-frequency / promo-history view** — trigger: team wants to predict goldapple campaigns
- [ ] **Per-SKU price history mini-chart** — trigger: team explicitly asks for trends
- [ ] **Configurable brand-of-interest filter** — trigger: team is repricing a specific category that week

### Future Consideration (v2+) — Only If Justified By v1 Pain

- [ ] **Deterministic fuzzy matching (token-set ratio + manual review queue)** — trigger: v1 strict-key match rate falls below acceptable threshold (PROJECT.md already names this)
- [ ] **Migration to Postgres** — trigger: SQLite hits performance/concurrency limits (unlikely at this scale)
- [ ] **Second competitor** — trigger: team explicitly requests after using v1 for a quarter
- [ ] **Web dashboard** — trigger: report consumers expand beyond the current Telegram chat
- [ ] **Email or Google Sheets channel** — trigger: archival or external-stakeholder requirement
- [ ] **Currency / FX-aware columns** — trigger: actual currency mismatch observed in data

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| viled.kz catalogue parser | HIGH | MEDIUM | P1 |
| goldapple.kz brand-scoped parser | HIGH | HIGH | P1 |
| Strike-through / promo price capture | HIGH | LOW | P1 |
| In-stock flag capture | MEDIUM | LOW | P1 |
| Brand + volume normalization | HIGH | MEDIUM | P1 |
| Strict-key matching | HIGH | MEDIUM | P1 |
| Snapshot history schema | HIGH | LOW | P1 |
| Excel report (per-SKU, gaps, promos, summary) | HIGH | LOW | P1 |
| Telegram delivery | HIGH | LOW | P1 |
| Weekly cron | HIGH | LOW | P1 |
| Run logs + failure alert | HIGH | MEDIUM | P1 |
| Retry/backoff + per-SKU isolation | HIGH | LOW | P1 |
| Match-rate visibility in summary | HIGH | LOW | P1 |
| Week-over-week delta column | HIGH | LOW | P2 |
| New/disappeared SKU sheet | MEDIUM | LOW | P2 |
| Brand-level aggregate sheet | MEDIUM | LOW | P2 |
| Match-rate degradation alert | MEDIUM | LOW | P2 |
| Promo-history / promo-frequency view | MEDIUM | MEDIUM | P2 |
| Per-SKU price history chart | MEDIUM | MEDIUM | P2 |
| Brand-of-interest filter | LOW–MEDIUM | LOW | P2 |
| Currency/FX sanity column | LOW | LOW | P2 |
| Fuzzy matching + review queue | MEDIUM (if strict matching is weak) | HIGH | P3 |
| Postgres migration | LOW (until forced) | MEDIUM | P3 |
| Second competitor | MEDIUM (case-by-case) | HIGH | P3 |
| Email / Google Sheets channel | LOW | LOW–MEDIUM | P3 |
| Web dashboard | LOW | HIGH | P3 |
| Image/description scraping | LOW (anti-feature) | HIGH | P3 (avoid) |
| Real-time alerts | NEGATIVE | MEDIUM | Anti-feature |
| ML matching / forecasting | NEGATIVE for this scope | HIGH | Anti-feature |
| Dynamic repricing | OUT OF SCOPE | HIGH | Anti-feature |

**Priority key:**
- P1: Required for v1 — Monday report cannot exist without it
- P2: Add post-v1 once usage validates the report itself
- P3: Defer indefinitely until concrete pain or explicit team request

---

## Competitor Feature Analysis

How leading SaaS handle each capability and what we adopt vs reject.

| Feature | Prisync | Skuuudle | Competera | Our Approach |
|---------|---------|----------|-----------|--------------|
| Crawling cadence | Daily, sometimes 3x/day | Daily managed | Continuous + on-demand | **Weekly** — business cycle, lower anti-bot risk |
| Product matching | URL-based + AI variant matching | Human QA, named analysts sign off | AI matching, 99% SLA | **Strict normalized key**; revisit only if coverage poor |
| Stock tracking | Yes | Yes | Yes | **Yes** — captured in schema, surfaced in promo sheet |
| Promo / strike-through capture | Yes | Yes (RRP/MAP/promo) | Yes | **Yes** — explicit use case |
| MAP monitoring | Yes | Yes | Yes | **No** — viled.kz is a retailer, not a brand owner |
| Repricing automation | Rule-based | No (intel-only) | AI-driven | **No** — human pricing decisions only |
| Alerting | Real-time per-SKU | Quality-control sign-off | AI Assistant + dashboards | **Weekly digest + parser-failure alerts only** |
| Reporting surface | Web dashboard + email | Delivered reports + portal | Dashboard + AI Assistant | **Telegram text + Excel** — matches team workflow |
| History / trend | Yes, in dashboard | Yes | Yes, AI-summarized | **Yes** — full snapshot history in DB, week-over-week column post-v1 |
| Multi-competitor scaling | Unlimited | Hundreds of sites | Enterprise scale | **Two retailers** — explicit scope |
| Operations / observability | Internal | Three-pronged QA | SLA-backed | **Run logs + alert on failure or count drop** — minimum viable observability |
| Image / description capture | Variants | Yes | Yes | **No** — pricing-only |

The pattern: SaaS features either (a) exist to make a *platform* sellable to many retailers (dashboards, integrations, multi-tenant, automation), or (b) provide marginal lift via heavy infrastructure (ML matching, image recognition, real-time pipelines). For a single team with a weekly Excel, neither category pays off.

---

## Cross-Reference Against PROJECT.md

| PROJECT.md Active Requirement | Mapped Feature |
|-------------------------------|----------------|
| "Полный парсинг каталога viled.kz (название, бренд, объём/вес, цена, цена до скидки, ссылка, наличие)" | Table stakes — Crawling: viled full catalogue + field extraction + strike-through + stock |
| "Парсинг goldapple.kz, ограниченный брендами viled.kz" | Table stakes — Crawling: goldapple brand-scoped |
| "Нормализация и сопоставление по `brand + название + объём`" | Table stakes — Matching: strict-key + brand + volume normalization |
| "База данных с историей всех еженедельных срезов" | Table stakes — History: snapshot storage; enables WoW deltas (P2) |
| "Сводный отчёт: размер ассортимента, пересечения, дельты цен" | Table stakes — Reporting: assortment summary + per-SKU delta + gap list |
| "Доставка отчёта в Telegram (текст + Excel/CSV)" | Table stakes — Delivery: Telegram bot + xlsx |
| "Еженедельный автозапуск (cron, ночь воскресенья)" | Table stakes — Delivery: weekly cron |
| "Устойчивость к anti-bot-защите" | Table stakes — Crawling: anti-bot resilience (stack research details how) |
| "Логи запуска и ошибок" | Table stakes — Operations: run logs + parser-failure alert |

| PROJECT.md Out-of-Scope | Confirmed As Anti-Feature |
|-------------------------|---------------------------|
| Gold Card / залогиненные цены | Anti-feature: login-gated pricing |
| Полный парсинг goldapple.kz | Anti-feature: implicit — brand scoping is the alternative |
| Real-time / ежедневный мониторинг | Anti-feature: real-time monitoring |
| Алерты на скидки в реальном времени | Anti-feature: real-time alerts |
| Веб-дашборд / UI | Anti-feature: web dashboard |
| Прочие маркетплейсы / другие конкуренты | Anti-feature: multi-competitor expansion |
| Картинки и описания | Anti-feature: image/description scraping |
| ML / fuzzy-сопоставление | Anti-feature for v1; explicit v2 candidate (P3) |

Every PROJECT.md item maps cleanly. Two implicit additions worth flagging that aren't yet in PROJECT.md but are strongly recommended:

1. **Capture promo / strike-through fields in v1 schema even if not surfaced in the v1 report.** Otherwise promo-history (P2) requires a re-crawl backfill, which on goldapple is expensive and risky. PROJECT.md already lists "цена до скидки" — this is consistent, but worth highlighting that schema must include it from week 1.
2. **"Match rate" as a tracked KPI from day one.** It's the canary for silent matching failure and silent parser failure. Cheap to compute, expensive to add later because it has no historical baseline.

---

## Sources

- [Prisync — Competitor Price Tracking](https://prisync.com/) — feature taxonomy for SaaS price intelligence (variant matching, stock, alerts, repricing)
- [Prisync — Price Intelligence Software](https://prisync.com/price-intelligence-software/)
- [Skuuudle — Competitive Pricing Intelligence](https://skuuudle.com/) — managed-service feature set: base/shelf/promo/RRP/MAP, named QA analysts
- [Skuuudle — Price Monitoring](https://skuuudle.com/price-monitoring) — quality-control three-pronged approach (preventative, active, post-collection)
- [Price2Spy](https://www.price2spy.com/) — alerting + repricing model
- [Competera — Competitive Intelligence](https://competera.ai/solutions/by-need/competitive-intelligence) — MAP, promo, stock, AI matching, AI Assistant features
- [Competera — Competitive Data Platform](https://competera.ai/products/competitive-data) — 99% match SLA, data-quality program
- [Wiser — Pricing Intelligence](https://www.wiser.com/pricing-intelligence-wiser-solutions/) — execution-oriented framing
- [Wiser — Top Pricing Intelligence Platforms Compared](https://www.wiser.com/blog/top-pricing-intelligence-platforms-compared) — vendor landscape
- [Intelligence Node — Product Matching](https://www.intelligencenode.com/solutions/by-need/product-matching/) — brand and attribute normalization patterns
- [42signals — Product Matching in E-commerce](https://www.42signals.com/blog/product-matching-ecommerce-benefits/) — normalization examples (HP/Hewlett-Packard, units)
- [DataWeave — AI-powered Product Matching](https://dataweave.com/blog/ai-powered-product-matching-the-key-to-competitive-pricing-intelligence-in-ecommerce) — ML matching upper bound (rejected for this scope)
- [ClearDemand — Assortment Gap Management](https://cleardemand.com/create-conversions-with-effective-assortment-gap-management/) — assortment-gap framing
- [Particl](https://www.particl.com/) — share-of-shelf / digital-shelf framing (rejected)
- [PromptCloud — 10 Web Scraping Monitoring and Observability Challenges](https://www.promptcloud.com/blog/web-scraping-monitoring-challenges/) — silent-failure detection, observability vs monitoring
- [Ficstar — How to Detect Scraper Failures](https://www.ficstar.com/how-to-detect-scraper-failures) — failure-categorization patterns
- [ScrapingAnt — Exception Handling Strategies for Robust Web Scraping](https://scrapingant.com/blog/python-exception-handling) — try/except + dead-letter patterns
- [Scrape.do — 6 Key Steps to Large Scale Web Scraping](https://scrape.do/blog/large-scale-web-scraping/) — retry queues, backoff
- [Firecrawl — Web Scraping Mistakes and Fixes](https://www.firecrawl.dev/blog/web-scraping-mistakes-and-fixes) — common pitfalls

**Confidence notes:**
- Feature taxonomy across SaaS pricing tools — **HIGH** (corroborated across Prisync, Skuuudle, Price2Spy, Competera, Wiser, Intelligence Node, DataWeave)
- Operations / observability practices — **HIGH** (corroborated across multiple scraping-engineering sources)
- Beauty-vertical specifics (volume parsing, brand transliteration RU↔EN) — **MEDIUM**, derived from general normalization principles plus the .kz / RU-language context in PROJECT.md; concrete edge cases will only surface during v1 parser implementation
- Match-rate threshold for triggering v2 fuzzy matching — **LOW**, no public data on strict-key match rates for cosmetics in RU/KZ markets; will need to be observed empirically

---
*Feature research for: competitive e-commerce price intelligence (internal beauty-retail tool)*
*Researched: 2026-05-05*
