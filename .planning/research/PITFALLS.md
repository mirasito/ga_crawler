# Pitfalls Research

**Domain:** Competitive e-commerce price scraping (beauty/cosmetics, KZ market): goldapple.kz vs viled.kz
**Researched:** 2026-05-05
**Confidence:** HIGH on anti-bot, matching, and operational pitfalls (multi-source verified). MEDIUM on KZ-specific legal/timezone specifics. LOW on goldapple.kz's exact anti-bot stack until empirically tested.

> Scope note: this document is intentionally focused on the two specific targets. "Generic web scraping advice" (rotate user-agents, use proxies, etc.) is mentioned only when the *specific failure mode* is non-obvious. Read top-to-bottom: pitfalls are ordered by how likely they are to wreck the v1 build.

---

## Critical Pitfalls

### Pitfall 1: Underestimating goldapple.kz anti-bot — building scraper around plain `httpx` first, then "adding Playwright later"

**What goes wrong:**
Developer prototypes against viled.kz with `httpx`/`requests`, gets clean data, applies the same approach to goldapple.kz, hits a Cloudflare 403 / managed challenge / `cf_clearance` cookie wall, then has to rewrite the whole fetch layer. Goldapple is the larger Russian retailer expanding into KZ — almost certainly behind Cloudflare or DataDome. Worse: a naive Playwright-without-stealth attempt also fails because `navigator.webdriver`, headless Chromium TLS fingerprint (JA3/JA4), and CDP artifacts all leak. The project loses 1-2 weeks rebuilding fetch infrastructure mid-build.

**Why it happens:**
viled.kz "just works" with httpx, so engineers extrapolate. Cloudflare detection in 2026 is multi-layer: TLS fingerprint (JA3/JA4 must match the User-Agent's claimed browser), HTTP/2 frame order, IP ASN reputation, and behavioral signals. Stealth plugins fix navigator-level signals but cannot fix a Linux Playwright TLS handshake claiming to be Chrome on Windows. Result: every layer above the fix layer leaks the bot.

**How to avoid:**
- **Probe goldapple.kz FIRST**, before touching viled.kz. The harder target dictates the architecture.
- Build the fetch layer with two pluggable backends from day 1: (a) `curl_cffi` with `chrome124+` impersonation profile for cheap requests, (b) Playwright/Camoufox for JS-rendered pages and challenge solving. Pick per-target, not project-wide.
- Use **residential proxies** for goldapple.kz from the start. Datacenter ASNs (AWS/Hetzner/OVH) are cataloged in detection databases — 40-60% success vs 85-99% for residential. Budget ~$8-15/GB; weekly run with bandwidth-frugal HTML-only fetches keeps cost low.
- For Playwright path, prefer **Camoufox** (Firefox, binary-patched fingerprint, ~0% headless detection) or `playwright-stealth` v2.x (Apr 2026 update) over vanilla Playwright. Vanilla Playwright is detected immediately in 2026.
- Match TLS profile to User-Agent. If you claim Chrome 124 on Windows, your JA4 must look like Chrome 124 on Windows. `curl_cffi` handles this; raw `httpx` does not.

**Warning signs:**
- First scrape of goldapple.kz returns a Cloudflare interstitial HTML (look for "Just a moment...", "cf-mitigated", `<title>Just a moment</title>`).
- HTTP 403 with `cf-ray` header.
- HTTP 200 but suspiciously small response body (~5KB challenge page instead of full product HTML).
- Captcha image / Turnstile widget appears in rendered HTML.
- Request succeeds the first time and fails on the 5th — IP got flagged.

**Phase to address:**
**Phase 1 (Reconnaissance + Fetch layer)** before any parsing work. Treat "can we fetch a goldapple product page reliably 100 times in a row" as a hard gate.

---

### Pitfall 2: Silent parser drift — site redesign produces zero matches, weekly report says "ассортимент конкурента сократился на 100%"

**What goes wrong:**
goldapple.kz tweaks a CSS class from `.product-card__price` to `.pdp-price-current`, parser silently returns `None` for every product. The pipeline doesn't crash — empty fields are valid Python. Telegram report fires Monday morning saying "0 совпадающих позиций" or "у Goldapple теперь 12 SKU вместо 3000". Pricing team makes decisions on garbage data. Discovery happens 1-2 weeks later when someone manually checks.

**Why it happens:**
Selectors fail "soft" — they return empty results, not exceptions. Tests pass against fixed HTML fixtures that never change. CI doesn't hit the live site. No one looks at intermediate output between runs.

**How to avoid:**
- **Hard-fail invariants**: After parsing each product, assert `price is not None`, `name is not None and len(name) > 3`, `volume is not None OR is_volumeless_category`. Raise, don't return None.
- **Run-level sanity gates**: Reject the run if `len(products) < 0.7 × last_week_count`, or if the null-rate on any required field exceeds a threshold (e.g., >5% products without price). Send a "RUN REJECTED — likely structural drift" alert instead of a normal report.
- **Field-distribution monitoring**: Log per-run cardinality: products parsed, % with price, % with volume, % with brand, mean price, distinct-brand count. Compare to last week. Slack/Telegram alert on >X% deviation.
- **Per-target smoke fixtures**: Keep 5-10 known product URLs from each retailer in a `golden_products.json` file with expected fields. Before main run, fetch those 5-10 and verify exact match. If golden set fails, abort run.
- **Use multiple selector strategies**: structured data (JSON-LD `Product` schema, `og:` meta tags, `<script type="application/ld+json">`) + CSS selectors as fallback. JSON-LD is more stable across redesigns than class names.

**Warning signs:**
- Parsed product count drops >20% week-over-week with no announced site changes.
- Null rate on any field jumps from <1% to >10%.
- Mean price changes by >30% (indicates wrong selector, not a real promo).
- Any field is `None` for 100% of products in a run.

**Phase to address:**
**Phase 2 (Parsing)** for hard-fail invariants and JSON-LD-first strategy.
**Phase 4 (Pipeline/Operations)** for run-level gates and field-distribution monitoring.

---

### Pitfall 3: Volume normalization eats matches — "30мл" ≠ "30 мл" ≠ "30ml" ≠ "30 ml" ≠ "1 fl oz"

**What goes wrong:**
viled has product as `Крем для лица 50 мл`, goldapple has it as `Крем для лица 50ml` (no space, Latin units). Strict `brand+name+volume` key produces zero matches. Pricing team sees "0% пересечения" and assumes the scraper is broken (it is, but not how they think). Or worse: viled lists `Крем 50 мл (3 шт)` (multipack of 3), goldapple lists single `Крем 50 мл`, key matches, price comparison is wrong by 3×.

**Why it happens:**
Cosmetics volume notation is wildly inconsistent across Russian retailers:
- Spacing: `50мл` / `50 мл` / `50 МЛ`
- Unit: `мл` / `ml` / `g` / `г` / `гр` / `oz` / `fl oz`
- Decimal: `1.5 мл` / `1,5 мл` / `1.5мл`
- Multipack: `3×50 мл`, `3 шт × 50 мл`, `3*50 ml`, `набор 3 × 50 мл`, `(3 pcs)`
- Set vs single: `Набор: крем 50мл + сыворотка 30мл` (a kit, not one product)
- Volume in name vs separate field: sometimes only in title, sometimes in attribute, sometimes both (and they disagree)
- Missing volume: hair brush has no volume; fragrance always does — must be category-aware

**How to avoid:**
- Build a `Volume` value object: `(amount: Decimal, unit: enum {ML, G, OZ, FL_OZ, COUNT}, multipack: int = 1)`.
- Parse with regex into canonical form: `(\d+[.,]?\d*)\s*(мл|ml|г|g|гр|oz|fl\s*oz)`. Normalize comma→dot, lowercase, strip.
- Detect multipack pre-normalization: regex `(\d+)\s*(?:×|x|\*|шт)\s*(\d+\s*(?:мл|ml|г|g))` → expand to `(amount, unit, multipack=N)`.
- Detect kits/sets: keywords `набор`, `set`, `комплект`, `kit`, `подарочный` in name → flag as `is_set=True`, **exclude from price-per-unit comparison** in v1.
- Compare on **(brand, normalized_name, amount_ml_equivalent, multipack)**. Convert g↔ml only when category warrants (oils ≈ density 0.9; not safe for hair tools).
- Log all unmatched-but-seemingly-similar pairs to a `match_review.csv` file. Manually review weekly to catch normalization gaps.
- **Out of scope but plan for it**: v2 fuzzy matching (rapidfuzz) on normalized name when exact key fails. Don't ship in v1, but design schema to allow fuzzy candidates later.

**Warning signs:**
- Match rate <30% on brands you know exist on both sites (sanity-check 5 known overlapping SKUs by hand).
- Price delta column shows ratio close to integer (3×, 2×) — suggests multipack mismatch.
- Single-product matches with wildly divergent prices (>50% difference) — likely wrong volume.

**Phase to address:**
**Phase 3 (Matching)** — must include explicit multipack/kit detection and unit normalization.

---

### Pitfall 4: Cyrillic vs Latin brand name divergence — "Estée Lauder" / "Эсте Лаудер" / "Estee Lauder" / "ESTÉE LAUDER"

**What goes wrong:**
Goldapple.kz, being a Russian-roots retailer, sometimes lists international brands in Cyrillic transliteration (`Эсте Лаудер`, `Шанель`, `Диор`), sometimes in Latin (`Estée Lauder`, `Chanel`, `Dior`), sometimes inconsistently between the catalog page and the product page. viled.kz typically uses Latin. Strict brand-key match misses 30-50% of overlap. Diacritics (`é` vs `e`), case (`CHANEL` vs `Chanel`), and ampersand (`Dolce&Gabbana` vs `Dolce & Gabbana` vs `D&G`) compound the problem.

**Why it happens:**
- No standard transliteration: `ESTEE LAUDER` → `ЭСТЕ ЛАУДЕР` or `ЭСТИ ЛАУДЕР` are both seen.
- Editorial inconsistency at the retailer (different categories curated by different teams).
- Unicode normalization: `é` (single codepoint U+00E9) vs `é` (e + combining acute U+0301) compare unequal byte-wise.
- Trademark variations: `L'Oréal` vs `LOreal` vs `Лореаль` vs `Loreal Paris` vs `L'Oréal Paris`.

**How to avoid:**
- Build a **brand alias table** seeded from viled.kz brands as canonical. For each viled brand, manually map known Cyrillic variants. Start with the top-50 brands by SKU count — covers 90% of catalog.
- Apply Unicode NFKD normalization + accent stripping (`unicodedata.normalize('NFKD', s).encode('ascii', 'ignore')`) before comparison — handles `é`→`e`.
- For unmapped brands, try transliteration libraries (`transliterate` package for ru↔en) as a fallback candidate, but **flag for human review** rather than auto-accept.
- Lowercase, strip punctuation (`'`, `&`, `.`, `-`), collapse whitespace before comparison.
- Maintain alias table in version control (`brand_aliases.yaml`); review weekly when unmatched-brand list grows.
- Log "brands seen on goldapple but not in alias table" each run — this is your manual review queue.

**Warning signs:**
- A specific brand has >20 SKUs on goldapple but zero matches against viled — likely an unmapped Cyrillic alias.
- Brand alias table hasn't grown in weeks but unmatched-brand log keeps growing.
- Two brands in alias table with similar names (`Эсте Лаудер` and `Эсти Лаудер` both mapping to `Estée Lauder`) suggests inconsistent source data.

**Phase to address:**
**Phase 3 (Matching)** — alias table is core infrastructure, not a v2 nice-to-have.

---

### Pitfall 5: Pricing extraction — picking strikethrough/from/club price instead of current public price

**What goes wrong:**
A goldapple product card shows: `~~6 990 ₸~~ **4 990 ₸** | По Gold Card: 4 490 ₸ | от 4 990 ₸`. The parser grabs whichever number happens to be in the first `.price` element and reports it. Sometimes it's the strikethrough (old price), sometimes Gold Card price (out of scope per PROJECT.md), sometimes the lowest variant ("from"). Comparison to viled.kz is meaningless. Worse: parser silently picks differently for different products in the same run.

**Why it happens:**
Beauty retailers display 3-5 prices simultaneously: original, current, member/loyalty, "from" (variant range), bulk-discount. CSS classes are often non-semantic (`.price-1`, `.price-2`). Markup changes per A/B test. The "obvious" price visually is not always the first in the DOM.

**How to avoid:**
- **Prefer JSON-LD / structured data**: `<script type="application/ld+json">` with `Product.offers.price` is the canonical current public price per schema.org. Use this first.
- If falling back to HTML: **explicitly select for semantic intent**, not position. Look for `data-price-type="final"`, `[itemprop="price"]`, or class names containing `current` / `final` / `actual`. Reject classes containing `old`, `was`, `crossed`, `striked`, `club`, `member`, `gold`, `from`.
- Capture **both** prices when possible: `current_price` and `original_price` (for discount %). Discount = (1 - current/original). Useful for "промо-мониторинг" goal.
- Filter products where price text contains `от` / `from` — these are variant ranges, not single prices. Handle as "needs variant selection" or skip.
- Sanity-check: assert `100 ≤ price ≤ 1_000_000` (₸). Cosmetics outside this range = parsing error.
- Currency: assert `₸` or `KZT` is in the source text. If you scrape a `.ru` mirror by accident, you get rubles, and your delta math is off by ~5×.

**Warning signs:**
- Distribution of prices is bimodal (cluster at low + high) — suggests sometimes catching strikethrough.
- Median price changes >30% week-over-week — wrong field.
- Discount column shows 0% for all products on goldapple (parser caught only one price field, original=current).
- Negative discount (current > original) — swapped fields.

**Phase to address:**
**Phase 2 (Parsing)** with mandatory currency + range assertions. **Phase 5 (Reporting)** must surface discount% so anomalies are visible.

---

### Pitfall 6: Stock detection — "out of stock" vs "hidden" vs "removed" vs "URL changed"

**What goes wrong:**
Last week a product had `Цена: 5 990 ₸ | В наличии`. This week the URL returns 404, or shows "Товар временно недоступен", or returns a redirect to the category page, or the price is 0, or a "Уведомить о поступлении" button instead of "В корзину". Treating all of these the same — "product disappeared, exclude from comparison" — produces three different bugs:
1. False "ассортимент сократился": product is just out of stock, not delisted.
2. False "новый товар появился": URL changed (slug edit on goldapple side), same product imported as new.
3. False price delta: `price=0` for OOS products treated as "now free".

**Why it happens:**
Retailers don't have a single signal. Goldapple in particular has multiple states: in stock / OOS / coming soon / pre-order / regional unavailable / archived. The DOM only weakly distinguishes them. URLs are not stable identifiers — slug changes (`krem-uvlazhnyayushchiy-50ml` → `krem-uvlazhnyayushchiy-novyy-50ml`) reset identity.

**How to avoid:**
- Define a **stock state enum**: `IN_STOCK`, `OUT_OF_STOCK`, `UNAVAILABLE`, `DELISTED`, `URL_CHANGED`, `UNKNOWN`. Map every product to exactly one. Never collapse to a boolean.
- For each retailer, document the DOM signals per state (text patterns: `В наличии`, `Нет в наличии`, `Скоро в продаже`, `Уведомить о поступлении`, button presence, schema.org `availability` field). Capture in a `stock_signals.md` reference file.
- **Never use price=0 as OOS signal** — assert price>0 or set state=OOS explicitly.
- For "disappeared" products (last seen N=1 week ago, now 404), don't immediately mark `DELISTED`. Set `state=URL_CHANGED_OR_DELISTED`, and try to re-find them by `(brand, name, volume)` key against current week's full catalog. If found at new URL → update URL. If not found after 2-3 weeks → mark `DELISTED`.
- Compute identity by `(brand, normalized_name, volume)` not URL. URL is a pointer, not the identity.
- Use `Product.offers.availability` from JSON-LD (`InStock` / `OutOfStock` / `PreOrder` / `Discontinued`) when available.

**Warning signs:**
- Week-over-week "delta delisted" jumps significantly while "delta added" jumps similarly — likely URL-rotation, not real churn.
- All disappeared products are from one brand or category — likely a scraping/pagination issue, not delisting.
- Products oscillate between "delisted" and "active" weekly — definitely identity bug.

**Phase to address:**
**Phase 2 (Parsing)** for state enum. **Phase 3 (Matching)** for identity-based reconciliation across weeks.

---

### Pitfall 7: Pagination / infinite-scroll truncation — silently scraping only first 30 products of 3000

**What goes wrong:**
Goldapple category page uses infinite scroll. `httpx` fetches the initial HTML and gets only the first 30-60 products. Parser reports "Goldapple has 60 products in 'Уход за лицом'". Real catalog: 2000+. Comparison is on ~3% of actual catalog.

**Why it happens:**
- Modern e-commerce uses lazy-load: products beyond fold are fetched via XHR/GraphQL on scroll.
- Pagination might not have visible page links — just a "Показать ещё" button.
- Listing page might be SSR for SEO (first N products) but client-rendered for the rest.
- API behind the scroll might be authenticated/CSRF-tokened, looking different from the web call.

**How to avoid:**
- **Find the underlying API**: open DevTools → Network → XHR while scrolling a category page. Almost always there's a `/api/catalog/products?page=N&category=X` endpoint returning JSON. Hit that directly — far more reliable than scrolling a headless browser.
- If only browser-driven scraping works, use Playwright with explicit scroll loop: scroll to bottom, wait for new product count to stabilize, repeat. Cap iterations and assert final count matches the displayed "Total: N products" label on the page.
- **Always extract total-count from the listing page** (most catalogs show "Найдено: 2 437 товаров" or similar) and assert your scraped count ≥ 95% of declared total. Hard-fail on mismatch.
- Track sub-pagination: a single category may have multi-page listings even with infinite scroll (page 1 = first 240 results, page 2 = next 240, etc.). Iterate `?page=N` until empty.
- For viled.kz: site is smaller, traditional pagination likely sufficient — but apply the same total-count check.

**Warning signs:**
- Scraped count is suspiciously round (exactly 30, 60, 120 — page sizes).
- Scraped count ≪ declared count on category header.
- Always missing the same brands (those with many products → exceeded the loaded slice).

**Phase to address:**
**Phase 1 (Reconnaissance)** to identify pagination strategy per site. **Phase 2 (Parsing)** to enforce total-count assertion.

---

### Pitfall 8: "Bran goldapple, only пересекающиеся бренды" — getting the brand list wrong, scraping useless brands or missing them

**What goes wrong:**
Per PROJECT.md, goldapple is scraped only for brands present on viled.kz. Two sub-failures:
1. **Brand-list staleness**: viled.kz adds a brand mid-week → goldapple scrape misses it that week → first-week artificial gap in report.
2. **Brand-name mismatch leaks**: the brand-list filter uses viled's brand spelling, goldapple lists it differently (Pitfall 4) → filter excludes valid brand → scraping nothing useful for that brand.
3. **Goldapple has the brand under a different category structure** → category-level filtering misses products that exist under a different taxonomy.

**Why it happens:**
- Naive filter: `if product.brand.lower() in viled_brands_lowercase: keep`. Cyrillic/Latin/diacritics break it.
- Brand list is built once at parser-init, not refreshed mid-run → drift between viled and goldapple scrape.
- Goldapple search-by-brand may be more reliable than scraping all categories and filtering — but easier to miss in initial design.

**How to avoid:**
- Build the brand list **at the start of every run** by scraping viled.kz fully first, then deriving the brand set from real data, then scraping goldapple.
- Use the **brand alias table** (Pitfall 4) when filtering goldapple. Don't compare raw strings.
- On goldapple, prefer scraping by brand directly: `goldapple.kz/brand/<slug>` typically lists all SKUs of that brand across categories. More reliable than category-then-filter.
- Log "viled brands not found on goldapple" per run — interesting business signal (brand absent at competitor) AND a sanity check on filter bugs.
- Capture `goldapple_brand_url` per brand alongside the alias — caches a known-good URL.

**Warning signs:**
- A specific viled brand has 30 SKUs but zero goldapple matches across multiple weeks — alias gap, not real absence.
- Goldapple scraped count for a brand wildly varies week-over-week — pagination or filter instability.

**Phase to address:**
**Phase 1 (Reconnaissance)** to confirm brand-page URLs exist. **Phase 3 (Matching)** for alias-aware filtering.

---

### Pitfall 9: Empty-result reports and silent cron failures — Monday morning report says "успешно: 0 товаров"

**What goes wrong:**
Three classic failure modes that all look identical to the user:
1. The cron job didn't run at all (server reboot, time zone change, crontab syntax, container OOM).
2. Cron ran, scraper crashed early, "report" is the partial empty state.
3. Scraper "succeeded" but parsed 0 products (Pitfalls 1, 2, 7) and dutifully reported "0 совпадений".

In all three the team gets either nothing or a useless report Monday morning. By the time someone investigates, the failed run can't be reproduced (target site state has changed).

**Why it happens:**
- Cron silently swallows stdout/stderr unless redirected.
- "Successful exit code" doesn't mean "scraped successfully" — only "didn't crash".
- No external watchdog; the system that's supposed to alert is the same system that's down.

**How to avoid:**
- **Dead-man's-switch monitoring**: free tier of Healthchecks.io or Cronitor. Scraper pings `/start` at run start, `/success` at successful end, `/fail` on exception. If no ping arrives within grace window, Healthchecks alerts via email/Telegram. This catches "didn't run at all".
- **Run-result hard gate** before sending to Telegram: assert `viled_count > 1000`, `goldapple_count > 500`, `match_count > 100` (or whatever historical baselines warrant). On gate fail → send `RUN FAILED — see logs` to ops Telegram, do NOT send the broken report to the business team.
- **Two Telegram targets**: ops chat (you, with full logs) and business chat (pricing team, with clean report). Failures route to ops only. Successes route to both.
- **Structured logs with rotation**: `loguru` or `structlog` to `logs/run-YYYY-MM-DD.log`. Every parsed product, every fetch, every retry. Keep 12 weeks.
- Capture run metrics in DB: `runs(id, started_at, ended_at, viled_count, goldapple_count, match_count, status, error)`. Lets you build trend charts and detect anomalies.
- Test the **failure path** on day 1: deliberately break the parser, confirm ops alert fires, confirm business chat doesn't get a broken report.

**Warning signs:**
- Empty/sparse reports.
- Healthchecks.io shows "down".
- Run metrics row missing for a week.

**Phase to address:**
**Phase 4 (Pipeline/Operations)** — ship monitoring before automating the schedule. Manually-triggered runs need fewer guardrails; scheduled runs absolutely require them.

---

### Pitfall 10: Time zone bug — weekly cron on UTC server fires at the wrong KZ time

**What goes wrong:**
PROJECT.md says: "ночь воскресенья → отчёт в понедельник". Server hosted in EU/US-East datacenter runs UTC. `cron 0 0 * * 0` fires Sunday 00:00 UTC = Sunday 06:00 Almaty (UTC+5). Run completes ~08:00 Almaty Sunday. Team checks Monday 09:00 expecting the report — it's been there for 25 hours, but the data covers Saturday-into-Sunday, missing Sunday's pricing changes. Or worse: scheduled `0 0 * * 1` (Monday 00:00 UTC) fires Monday 05:00 Almaty, run takes 3 hours, report arrives 08:00 Almaty Monday — but if scrape took 4 hours, report misses morning standup.

KZ doesn't observe DST so at least that pitfall is avoided — but if you host in a DST-observing region and cron uses local server time, the run shifts 1 hour twice a year.

**Why it happens:**
- Cron defaults to system time zone. Cloud VPS images often default to UTC.
- Developers think in their local time when writing schedules.
- "Sunday night" is ambiguous — KZ Sunday-into-Monday or developer's Sunday-into-Monday?

**How to avoid:**
- Set crontab `CRON_TZ=Asia/Almaty` at the top, or run scheduler under a process that accepts TZ-aware schedules (e.g., APScheduler with `timezone='Asia/Almaty'`).
- Use `Asia/Almaty` explicitly. Kazakhstan unified to UTC+5 in March 2024 (single time zone). Avoid `Asia/Aqtobe`, `Asia/Qyzylorda` — historical aliases, may behave unexpectedly with stale tzdata.
- Document the schedule decision: "Run starts Sunday 22:00 Asia/Almaty, expected duration 2-4h, report delivered before Monday 06:00 Almaty for morning standup."
- All timestamps in DB and logs in UTC ISO-8601. Convert to Almaty only at presentation layer (Telegram message, Excel header).
- Verify on first deploy: `date` on server, `crontab -l`, plus a test run to confirm actual fire time.

**Warning signs:**
- Report consistently arrives 5h earlier or later than expected.
- Run-metrics `started_at` doesn't match Sunday-22:00-Almaty (in UTC: 17:00 Sunday).
- DST transition weeks: report 1h offset from baseline (only if hosted in DST region).

**Phase to address:**
**Phase 4 (Pipeline/Operations)**.

---

## Moderate Pitfalls

### Pitfall 11: Telegram 50MB hard limit on Bot API uploads — Excel report grows past it

**What goes wrong:**
Initial Excel is 2MB. Six months in, with full snapshot history embedded, multi-sheet report and >5000 matched SKUs, the file crosses 50MB. `sendDocument` fails with "Request Entity Too Large". Report silently fails to deliver; only the text summary gets through.

**How to avoid:**
- Excel report should NOT embed all historical snapshots. Embed: latest snapshot, last 4 weeks of price history per SKU, top-N changes. History lives in DB.
- Compression: write `.xlsx` (already zipped) not `.xls`. Avoid embedded images. Set column types correctly (numeric not string).
- If you need bigger payloads: self-host the Telegram Bot API server (`tdlib/telegram-bot-api`) — raises limit to 2GB. Or use the user-bot approach (Telethon/Pyrogram) — uploads up to 1.5GB.
- Realistic v1 estimate: well under 50MB. But add a pre-send check: `if file_size > 45MB: send_compressed_or_warn`.
- Telegram also rate-limits: ~30 messages/sec to different chats, 1 msg/sec to same chat, 20 msgs/min for bulk. Not a concern for weekly delivery, but don't burst-send 50 separate messages.

**Warning signs:**
- Report file approaches 30MB.
- Telegram returns `RetryAfter` or `Request Entity Too Large`.

**Phase to address:** **Phase 5 (Reporting)** — set file-size budget upfront.

---

### Pitfall 12: Database history bloat — full weekly snapshots compound to GBs

**What goes wrong:**
Naive schema: every Sunday, INSERT all ~3000 goldapple + ~500 viled SKUs into `price_history` with full row. After 1 year: 52 × 3500 = ~180K rows. After 3 years and growth: millions. Sub-100MB (manageable for SQLite), but unindexed queries slow to seconds. If you also store full HTML for forensics, multiply by 100.

**How to avoid:**
- **Don't store full HTML in DB**. Store HTML to `snapshots/YYYY-MM-DD/<retailer>/<sku_hash>.html.gz` filesystem-side. Reference from DB by path. 10-100x storage savings.
- **Schema**: `products` (SKU identity, current state) + `price_observations` (sku_id, run_id, price, original_price, availability, observed_at). Latter is append-only time-series.
- **Index**: `(sku_id, observed_at DESC)` for "latest price per SKU" queries — most common access pattern.
- **Retention**: retain weekly snapshots for 2 years, then downsample to monthly for years 2-5. Or just keep all — at 200K rows/year, SQLite handles fine through year 5+.
- **SQLite is appropriate for v1**. Migration to Postgres is warranted only if (a) multiple writers, (b) >10M observations, (c) need TimescaleDB hypertables. None apply at weekly cadence.
- VACUUM periodically (monthly cron) to reclaim space.

**Warning signs:**
- DB file >1GB before year 1.
- Report-gen queries take >30s.
- Backup/restore takes minutes.

**Phase to address:** **Phase 4 (Persistence/Pipeline)** — get the schema right early; migrating later is painful.

---

### Pitfall 13: Aggressive scraping → IP banned mid-run → partial weekly report

**What goes wrong:**
Scraper runs 10 concurrent requests against goldapple. Halfway through, all IPs in proxy pool get rate-limited or blocked. Run fails with 200 products parsed of 3000 expected. Run gate (Pitfall 9) catches it and alerts ops, but you've burned proxy budget and now have to wait out the IP cooldown.

**How to avoid:**
- **Concurrency: 1-3 max** for goldapple. Weekly cadence means you have hours; speed is irrelevant. Sequential is fine for v1.
- **Delay between requests**: random uniform 2-5 seconds. NOT a fixed delay (looks robotic).
- **Honor `Retry-After` header**: if 429, wait the indicated time. If no header, exponential backoff with jitter: `2^attempt × random(1.0, 1.5)`, capped at 60s. Max 3 retries per URL, then give up and log.
- **Distinguish retryable from non-retryable**: 429, 503, 502 → retry. 403, 401, 404 → don't retry (different action needed).
- **Session persistence**: Cloudflare's `cf_clearance` cookie is per-IP and per-fingerprint. Reuse browser session across requests. Don't open a fresh browser per page — looks bot-like AND wastes the clearance you earned.
- **viled.kz**: smaller, less defended, but be polite. 1 req/sec is plenty. You're a guest, not a customer. (And: the team owns viled.kz — be extra polite to your own infrastructure.)

**Warning signs:**
- Increasing 429/503 rate during a run.
- Cloudflare challenge pages partway through a run that wasn't there at start.
- Run completes but with significant gaps.

**Phase to address:** **Phase 1 (Fetch layer)** — bake rate limits in from start, don't bolt on after blocks.

---

### Pitfall 14: Robots.txt and ToS exposure — moral/practical, not just legal

**What goes wrong:**
Both sites likely have `robots.txt` disallowing automated access to product listings, and ToS prohibiting scraping. Legally enforceable in KZ for **public** product data is weak (Pitfall: KZ Law 94-V regulates *personal* data, not commercial product info; public re-collection is permitted with attribution). But: violating ToS gives the target legitimate ground to block your IP range, send a cease-and-desist, or pursue civil action under unfair competition statutes. For a competitor scraping a competitor (viled scraping goldapple), this isn't theoretical.

**How to avoid:**
- **Read both robots.txt files** at project start. Most likely, `goldapple.kz/robots.txt` disallows `/api/`, `/search`, etc. but allows category and product pages (those are SEO targets — they want crawled). Document what's allowed/disallowed and design around it.
- Read ToS for both. Note any explicit anti-scraping clauses.
- **Identify yourself honestly in User-Agent** when feasible, with contact email: `Mozilla/5.0 ... ViledPriceMonitor/1.0 (contact: ops@viled.kz)`. This converts you from "anonymous scraper" to "identifiable competitor doing competitive intelligence" — legally weaker target for blocking, harder to argue malicious intent. Trade-off: makes you trivially identifiable, so you'd better not be doing anything sketchy.
- **OR** the opposite: use realistic browser UAs for stealth. Pick one, document the choice, don't mix. (For goldapple, given Cloudflare, realistic UA is operationally necessary.)
- Stay strictly on **public unauthenticated pages** (PROJECT.md already commits to this — good).
- Don't republish goldapple content. Internal use for pricing only is far more defensible than republishing/aggregating publicly.
- Rate-limit conservatively (Pitfall 13). Demonstrating low-impact scraping helps if challenged.
- Capture the legal reasoning in a doc the team and lawyer can review. Useful when leadership asks "are we sure this is OK?"

**Warning signs:**
- Cease-and-desist email.
- Sudden permanent IP block across all proxies (manual action, not rate limit).
- ToS update on goldapple.kz that explicitly mentions automated access or competitive intelligence.

**Phase to address:** **Phase 0 (Project setup)** — review and document before writing code.

---

### Pitfall 15: Excel report unfit for human use — pricing team complains it's noise

**What goes wrong:**
Report includes 5000 matched SKUs, all columns, raw numeric prices. Pricing team opens it, sees a wall of numbers, can't tell what changed, what matters. Reverts to manual spot-checks. Tool gets ignored within 2 months — exactly the "это никто не использует" failure mode a non-validated v1 risks.

**How to avoid (preview — own pitfall area, but flag here for roadmap):**
- Excel report: separate sheets `Summary`, `Top movers (week)`, `Promo activity`, `Assortment gaps`, `Full data`. Top sheets are short and curated; full data is for drilling.
- Conditional formatting on price-delta column (red/green).
- Sort by absolute price-delta or by % delta — biggest movers first.
- Telegram text summary ≤10 lines: counts, top-3 price changes, top-3 new products at competitor, link to full report.
- Show **Last week's price** alongside this week — pricing team thinks in deltas, not absolutes.
- Validate the format with one pricing-team user **before** automating weekly delivery.

**Phase to address:** **Phase 5 (Reporting)** — design with the actual user, not in isolation.

---

## Minor Pitfalls

### Pitfall 16: Encoding bugs — Cyrillic mojibake in Excel

**What goes wrong:** Excel opens CSV in Windows-1251 by default; UTF-8 without BOM displays as `Ð£Ð²Ð»Ð°Ð¶Ð½ÑÑÑÐ¸Ð¹` instead of `Увлажняющий`.

**How to avoid:** Write `.xlsx` (always UTF-8 internally) not raw CSV. If CSV is required, write UTF-8 **with BOM** (`utf-8-sig` in Python). Use `openpyxl` or `xlsxwriter` for xlsx, never csv.writer for international data.

**Phase to address:** Phase 5.

---

### Pitfall 17: Currency rounding drift

**What goes wrong:** Storing prices as `float` (`5990.0`) is fine until subtraction: `5990.0 - 5989.99 = 0.010000000000218279`. Reports show "delta = 0.0100000..." occasionally.

**How to avoid:** Store as `Decimal` (Python `decimal.Decimal`) or as integer-tenge (`int`, kopecks-equivalent). Round to whole tenge for display. KZT has no fractional unit in practice on retail prices.

**Phase to address:** Phase 2.

---

### Pitfall 18: Captcha encountered, no plan

**What goes wrong:** Cloudflare Turnstile or hCaptcha widget appears mid-run. Scraper has no solver, fails the run.

**How to avoid:** v1 design: **avoid** triggering captcha (residential proxies, low rate, stealth browser). If captcha appears, log + abort + alert. v2 if regular: integrate 2Captcha/Capsolver API ($0.001-0.003 per solve). Don't build solver as a primary v1 feature — it's a band-aid that adds complexity and cost.

**Phase to address:** Phase 1 (avoid). Backlog for v2 (solve).

---

### Pitfall 19: HTML changes per A/B test, run-to-run

**What goes wrong:** Goldapple runs A/B test on layout. Some users see variant A, some variant B. Your scraper, with consistent fingerprint, lands on one bucket — but the bucket changes by IP. Selectors that worked yesterday break today, then work tomorrow.

**How to avoid:** Maintain selectors for both variants where detected. Use JSON-LD primarily — A/B tests rarely change structured data. On selector failure, try alternate selector before failing.

**Phase to address:** Phase 2.

---

### Pitfall 20: Volume disagreement between title and attribute

**What goes wrong:** Title says `Крем 50 мл`, attribute panel says `Объём: 30 мл` (data-entry error at retailer). Parser picks one; matching fails against other retailer.

**How to avoid:** Capture both, prefer attribute (more structured) but log mismatches. If they disagree, lower confidence on the SKU and exclude from automatic matching — surface in a "review" sheet.

**Phase to address:** Phase 2/3.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Vanilla Playwright (no stealth) for goldapple | Fast prototype | Detected immediately by Cloudflare; rebuild required | **Never** for goldapple. OK for viled if it works. |
| Hard-coded brand alias list in code | Zero infra | Code change every time a brand is added | Only first 2-3 weeks; promote to YAML/DB by Phase 3 |
| `requests`/`httpx` only, no curl_cffi | Simpler dep | Goldapple blocks within hours | Never for goldapple. OK for viled. |
| Skip run-level gate, just send report | One less feature | Garbage reports erode user trust → tool dies | Never if scheduled. OK for manual ad-hoc runs. |
| Single Telegram chat (ops + business) | Simpler config | Ops noise leaks to business; failures look like reports | Day 1 only — split before scheduling. |
| SQLite + filesystem snapshots | Zero infra cost | Manual backup discipline; no concurrent writers | Through year 2 / single-machine deployment |
| `float` for prices | Trivial | Off-by-cent reports, hard-to-debug delta noise | Never. Use Decimal/int from start. |
| URL as product identity | Easy join | URL changes break weekly continuity (Pitfall 6) | Never. Use (brand, name, volume) hash. |
| No total-count assertion on listing pages | One less line of code | Silent partial scrape (Pitfall 7) | Never. |
| Skip JSON-LD, parse HTML directly | Don't have to learn schema.org | Brittle; rebuild on every redesign | When site has no JSON-LD (rare). Try JSON-LD first always. |
| One UA, no rotation | Simpler | More likely to fingerprint-flag | OK at low volume (weekly, ~3K requests). Rotation matters at higher volume. |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Cloudflare-protected goldapple.kz | Plain httpx; vanilla Playwright | curl_cffi (chrome124+ profile) for HTML pages; Camoufox or playwright-stealth for JS-rendered/challenged. Residential proxy. |
| viled.kz | Skipping it because "it's our site, no anti-bot" | Still rate-limit politely; still treat as flaky external system. Same parser architecture as goldapple. |
| Telegram Bot API | Sending raw report; no error handling | Retry with backoff on 5xx; on 429 honor `retry_after`; pre-validate file size <45MB; separate ops/business chats. |
| JSON-LD product schema | Not checking it exists | Always check `<script type="application/ld+json">` first. Many KZ retailers use Bitrix → standard schema.org Product output. |
| Cron / scheduler | System-time vs. business-time | `CRON_TZ=Asia/Almaty` or APScheduler with explicit timezone. |
| Healthchecks.io | Pinging only on success | Ping start/success/fail separately. Set grace time = expected_duration × 2. |
| Excel writer | csv.writer for Cyrillic | openpyxl/xlsxwriter (UTF-8 by default in xlsx). |
| Proxy provider | Datacenter proxies for goldapple | Residential. Budget ~$10-30/month for weekly 2-3GB. |
| Logger | print() / default logging | loguru or structlog — structured, rotated, easy to grep. |
| Git | Committing logs / DB / .env | .gitignore for `*.log`, `*.db`, `.env`, `snapshots/`, `secrets/`. |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Concurrent fetch on goldapple | Cloudflare blocks across pool | Sequential or concurrency=2 max | Day 1 if too aggressive |
| Loading full HTML history into memory for diff | Run uses 4GB+ RAM | Stream from DB; diff per-SKU | Year 2 (~200K observations) |
| No DB index on (sku_id, observed_at) | Report-gen takes minutes | Composite index | After ~50K observations |
| Storing HTML in DB | DB size in GBs; backup slow | Filesystem + path reference | Within first 6 months |
| Re-fetching unchanged products | Wastes proxy bandwidth | Conditional GET (If-Modified-Since); skip if last-week's hash matches | Goldapple-scale (~3K SKUs/week) — bandwidth costs add up |
| Headless browser per request | 10x slower; more detectable | Single browser, multiple pages, persistent context | Goldapple has 3000+ products |
| Synchronous Excel write of all sheets | Memory spike at end of run | xlsxwriter streaming mode (`constant_memory=True`) | When report >50MB |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Telegram bot token in repo | Anyone can hijack the bot, send fake reports, or read incoming messages | `.env` file, gitignored. Token in env var. Rotate if leaked. |
| Proxy credentials in code | Bandwidth theft, billing surprise | Same — env var. Use provider's IP allowlist if available. |
| Logging full request/response with cookies | `cf_clearance` and session cookies leaked to log files / log aggregator / git | Redact `Cookie`, `Authorization`, `set-cookie` headers in logs. |
| Storing raw HTML with potentially-PII responses | Goldapple might leak A/B-test user IDs, recommendation tokens in HTML | Strip script tags before storing; periodic purge of snapshots >90d unless needed. |
| Running scraper as root in container | Compromised scraper = compromised host | Non-root user in Dockerfile; minimal capabilities. |
| Trusting scraped HTML in Excel formulas | Malicious product name `=cmd|...` (CSV injection) opens calculator on user's machine | Prefix any cell value starting with `=`, `+`, `-`, `@`, tab, CR with `'` — disables formula interpretation. |
| Pickling untrusted objects | Code execution if cache file tampered | Use JSON for caches, not pickle. |
| No auth on dead-man's-switch ping URL | Anyone with the URL can fake a healthy ping | Use random UUID in URL; treat as a secret. |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Report dumps 5000 rows of raw data | "Слишком много, не понятно что важно" — gets ignored | Top 50 movers + summary + full sheet. Conditional formatting. |
| Telegram text mirrors entire Excel | Spam fatigue | 8-12 line summary; counts + top-3 deltas + Excel link. |
| Failure delivered same channel as success | Team can't tell broken from real | Two chats: ops vs. business. |
| No "what changed since last week" | Team has to manually compare to last week's file | "Δ vs предыдущая неделя" column. New SKUs flagged. Disappeared SKUs flagged. |
| All Cyrillic OR all English in headers | Mixed audience confusion | Russian headers (audience is RU-speaking pricing team). UTF-8 throughout. |
| Tенге shown as `5990.0` | Hard to read, looks like float bug | Format `5 990 ₸` (NBSP thousands separator, ₸ symbol). |
| Time stamps in UTC | "When was this scraped??" confusion | Almaty time in user-facing surfaces; UTC in DB only. |
| No URL link to product page | Can't verify suspect prices manually | Every row links to both viled and goldapple product URLs. |

---

## "Looks Done But Isn't" Checklist

- [ ] **Goldapple fetch**: Often missing residential proxy — verify with VPN-off test from different IPs over a week.
- [ ] **Stealth setup**: Often missing TLS fingerprint match — verify with bot.sannysoft.com or creepjs.
- [ ] **Pagination**: Often missing total-count assertion — verify scraped count ≥ 95% of category-page-displayed total.
- [ ] **Brand filter**: Often missing Cyrillic alias entries — verify by spot-checking 10 known overlapping brands.
- [ ] **Volume parsing**: Often missing multipack / kit detection — verify with regex test suite covering all observed formats.
- [ ] **Stock state**: Often missing distinct OOS vs. delisted — verify state enum coverage with sample of 50 known products in each state.
- [ ] **Price field**: Often grabs strikethrough or club price — verify spot-check 20 products against site-displayed price.
- [ ] **Currency**: Often missing currency assertion — verify all parsed prices have ₸/KZT in source.
- [ ] **Run gate**: Often passes empty-result runs — verify by deliberately breaking parser and confirming the gate catches it.
- [ ] **Cron monitoring**: Often missing dead-man's-switch — verify by stopping cron and confirming Healthchecks alert fires.
- [ ] **Time zone**: Often UTC — verify report arrives at expected Almaty time on first scheduled run.
- [ ] **Telegram delivery**: Often missing rate-limit and size handling — verify with intentionally-too-big test file.
- [ ] **Encoding**: Often UTF-8-without-BOM CSV — verify Cyrillic readable when opened in Excel-Windows.
- [ ] **DB schema**: Often product-by-URL — verify URL change doesn't lose product identity across weeks.
- [ ] **Logs**: Often missing redaction — verify no `cf_clearance` cookie or proxy password appears in any log.
- [ ] **Excel injection**: Often missing — verify a product named `=1+1` doesn't render as `2` in Excel.
- [ ] **Decimal pricing**: Often `float` — verify `5990.00 - 5989.99` displays as expected, not as `0.0100000...`.
- [ ] **Brand list**: Often built once — verify it refreshes from current viled scrape each run.
- [ ] **Discount detection**: Often shows 0% always — verify on known-promo product.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Goldapple IP banned | LOW | Wait 24-48h. Rotate residential proxy pool. Reduce concurrency to 1. Re-test. |
| Cloudflare hardened — stealth no longer works | MEDIUM | Switch from Playwright-stealth to Camoufox; or upgrade curl_cffi profile to newest Chrome. |
| Site redesign breaks parser | MEDIUM | Run gate catches the run (no broken report sent). Manually update selectors. Add fixture. Backfill missed week if possible by re-scraping (Goldapple won't have history but viled snapshot might be cached). |
| Brand alias misconfigured | LOW | Update YAML alias table. Re-run last week's matching against existing snapshots (don't need to re-scrape). |
| Telegram delivery fails | LOW | Manual file send via desktop client. Add retry logic with self-hosted Bot API server for >50MB. |
| Cron didn't run | LOW | Manual trigger; Healthchecks already alerted. |
| DB corruption | MEDIUM | SQLite has built-in `.recover`. Restore from latest backup (you DO have nightly backup of `*.db` to filesystem snapshot, right?). |
| Wrong prices shipped to pricing team | HIGH (trust damage) | Send correction Telegram message immediately. Document root cause publicly to team. Add a regression test. Trust takes weeks to rebuild. |
| Cease-and-desist from goldapple | HIGH | Stop scraping immediately. Consult lawyer. Re-evaluate project scope vs. risk. May need to switch to manual collection or licensed data feed (e.g., DataFeedWatch, e-comma). |
| Disk full from snapshots | LOW | Run snapshot retention cleanup. Add monitoring. |

---

## Pitfall-to-Phase Mapping

Roadmap-friendly summary. Phase numbering is a recommendation; reorder to match your actual roadmap.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Anti-bot underestimation | Phase 1 (Reconnaissance + Fetch) | 100 sequential successful goldapple product fetches |
| 2. Silent parser drift | Phase 2 (Parsing) + Phase 4 (Operations) | Deliberately break a selector in a test, confirm hard-fail + alert |
| 3. Volume normalization | Phase 3 (Matching) | Regex unit tests on 30+ real volume strings; multipack tests |
| 4. Brand Cyrillic/Latin | Phase 3 (Matching) | Top-50 brands have aliases; manual spot-check 10 known matches |
| 5. Price field selection | Phase 2 (Parsing) | Spot-check 20 prices against rendered page values |
| 6. Stock state ambiguity | Phase 2 (Parsing) + Phase 3 (Matching) | State enum covers 5 documented signals per retailer |
| 7. Pagination truncation | Phase 1 (Reconnaissance) + Phase 2 | Scraped count ≥ 95% of declared total |
| 8. Brand-list filter for goldapple | Phase 3 (Matching) | Brand list refreshed per-run; alias-aware filter |
| 9. Empty/silent runs | Phase 4 (Operations) | Healthchecks fires; run gate blocks empty reports; ops vs business chats |
| 10. Time zone | Phase 4 (Operations) | First scheduled run lands at expected Almaty time |
| 11. Telegram 50MB | Phase 5 (Reporting) | Synthetic 60MB test file fails gracefully with ops alert |
| 12. DB bloat | Phase 4 (Persistence) | Schema review; snapshots on filesystem not DB |
| 13. Aggressive scraping | Phase 1 (Fetch) | Sustained 1-hour run with no 429/503 spike |
| 14. Legal/ToS exposure | Phase 0 (Setup) | robots.txt + ToS reviewed and documented |
| 15. Unusable report | Phase 5 (Reporting) | Pricing team uses report 4 weeks running |
| 16-20. Encoding/precision/captcha/AB/volume-disagreement | Phases 2-5 | Specific to each — see pitfall body |

---

## Sources

Anti-bot detection (HIGH confidence — multi-source):
- [Scrapfly — Bypass DataDome 2026](https://scrapfly.io/blog/posts/how-to-bypass-datadome-anti-scraping)
- [ZenRows — Bypass DataDome Complete Guide 2026](https://www.zenrows.com/blog/datadome-bypass)
- [Scrapfly — Bypass Cloudflare 2026](https://scrapfly.io/blog/posts/how-to-bypass-cloudflare-anti-scraping)
- [AlterLab — Playwright Anti-Bot Detection 2026](https://alterlab.io/blog/playwright-anti-bot-detection-what-actually-works-in-2026)
- [Scrapewise — Playwright Stealth 2026](https://scrapewise.ai/blogs/playwright-stealth-2026)
- [Scrapfly — Playwright Stealth Bypass](https://scrapfly.io/blog/posts/playwright-stealth-bypass-bot-detection)
- [Browserless — TLS Fingerprinting](https://www.browserless.io/blog/tls-fingerprinting-explanation-detection-and-bypassing-it-in-playwright-and-puppeteer)
- [Datahut — curl_cffi Cloudflare 2026](https://www.blog.datahut.co/post/web-scraping-without-getting-blocked-curl-cffi)
- [Scrapfly — curl-impersonate](https://scrapfly.io/blog/posts/curl-impersonate-scrape-chrome-firefox-tls-http2-fingerprint)
- [Camoufox — Stealth Firefox](https://github.com/jo-inc/camofox-browser)
- [pim97/anti-detect-browser-tools](https://github.com/pim97/anti-detect-browser-tools-tech-comparison)
- [Plain Proxies — Residential vs Datacenter](https://plainproxies.com/blog/integrations/residential-vs-datacenter-proxies-difference)
- [AlterLab — Cloudflare 6-Layer Guide 2026](https://alterlab.io/blog/scrape-cloudflare-protected-sites)
- [Cloudflare — AI Crawler Permission 2025 announcement](https://www.cloudflare.com/press/press-releases/2025/cloudflare-just-changed-how-ai-crawlers-scrape-the-internet-at-large/)

Operational reliability (HIGH):
- [Healthchecks.io — Cron Monitoring](https://healthchecks.io/docs/monitoring_cron_jobs/)
- [Healthchecks.io — Dead Man's Switch](https://blogs.snehangshu.dev/dead-mans-switch-style-application-monitoring-with-healthchecksio)
- [AWS Builders' Library — Timeouts/Retries/Backoff](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
- [Better Stack — Exponential Backoff](https://betterstack.com/community/guides/monitoring/exponential-backoff/)

Telegram delivery (HIGH):
- [tdlib/telegram-bot-api — self-hosted](https://github.com/tdlib/telegram-bot-api)
- [DEV — Self-Hosted Telegram API for 50MB bypass](https://dev.to/joybtw/how-i-self-hosted-the-telegram-bot-api-with-docker-to-bypass-50mb-upload-limits-483a)

Storage (HIGH):
- [SQLite Forum — Temporal Tables / Time-Series](https://www.sqliteforum.com/p/sqlite-and-temporal-tables)
- [Timescale — TimescaleDB vs Postgres time-series](https://medium.com/timescale/timescaledb-vs-6a696248104e)
- [DataCamp — SQLite vs PostgreSQL](https://www.datacamp.com/blog/sqlite-vs-postgresql-detailed-comparison)

Drift detection (MEDIUM):
- [DEV — Self-Healing CSS Selector Repair](https://dev.to/viniciuspuerto/when-the-scraper-breaks-itself-building-a-self-healing-css-selector-repair-system-312d)
- [Apify — Selector Auto Fixer](https://apify.com/quantifiable_bouquet/selector-auto-fixer)
- [Medium — Smart Site Detection / Dynamic CSS](https://medium.com/@yukselcosgun/smart-site-detection-and-dynamic-css-selector-generation-for-resilient-scraping-ba8a5ba6ce26)

Product matching (MEDIUM):
- [BrightData — Guide to Data Matching](https://brightdata.com/blog/web-data/guide-to-data-matching)
- [PromptCloud — Price Scraping and Matching in eCommerce](https://www.promptcloud.com/price-scraping-in-ecommerce/)
- [NetOwl — Fuzzy Name Matching](https://www.netowl.com/how-to-choose-a-fuzzy-name-matching-product)

Legal / KZ (MEDIUM — domain-specific KZ guidance is sparse, used official law text):
- [Adilet — Law of RK on Personal Data Z1300000094 (94-V)](https://adilet.zan.kz/eng/docs/Z1300000094)
- [DLA Piper — Kazakhstan Data Protection](https://www.dlapiperdataprotection.com/index.html?t=law&c=KZ)
- [Gratanet — Personal Data Protection KZ — State Oversight Updates](https://gratanet.com/publications/persona-data-protection-state-oversight-and-legislative-updates)
- [ByteTunnels — Is robots.txt Legally Binding](https://bytetunnels.com/posts/is-robots-txt-legally-binding-scraping-law-explained/)
- [Browserless — Is Web Scraping Legal 2026](https://www.browserless.io/blog/is-web-scraping-legal)

Confidence flags:
- [LOW] Goldapple.kz's *exact* anti-bot stack — empirical reconnaissance required in Phase 1.
- [LOW] viled.kz's defense level — assumption ("simpler") needs verification.
- [MEDIUM] KZ-specific legal exposure for B2B competitive intel scraping — would benefit from a local lawyer review.
- [HIGH] Generic Cloudflare/DataDome detection mechanics, residential vs datacenter, stealth tooling, monitoring patterns — all multi-source verified.

---
*Pitfalls research for: competitive e-commerce price scraper (goldapple.kz vs viled.kz), beauty/cosmetics, KZ market*
*Researched: 2026-05-05*
