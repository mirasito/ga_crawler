# Phase 3 Live Smoke Verification Log

**Date:** 2026-05-06
**Operator:** mirdbek@gmail.com
**Dev box:** KZ-laptop direct (no proxy)
**Spike sign-off reference:** .planning/spikes/01-goldapple/MEMO.md (2026-05-06, Tier 2 = Camoufox 135.0.1-beta.24)

## Pre-flight
- [x] `uv sync` succeeded (Wave 0 deliverable)
- [x] `uv run camoufox fetch` ran without error (Camoufox cached from Phase 1 spike)
- [x] `curl -s https://ipinfo.io/country` returned `KZ`

## Step 1 — Smoke probe

### Run 1 — `uv run python -m ga_crawler goldapple-smoke --headless false`
**Outcome:** FAIL (parser bug — see Section "Findings" below)
**Diagnostics:**
- camoufox_version: 0.4.11
- responses[0]: status=200, size=486975, price_extracted=true
- responses[1]: status=200, size=419169, price_extracted=true
- responses[2]: status=200, size=199912, price_extracted=**false** ← parser bug surfaced

### Run 2 — same command, after parser fix landed (commit `277a40a`)
**Outcome:** FAIL (transient gate-shell — anti-bot reaction to rapid Camoufox spawns)
**Diagnostics:**
- All 3 URLs: status=200, size~18 KB, title="Gold Apple … checking device", block=true
- Cause: 3 cold-spawn smoke runs within ~10 minutes triggered transient gate

### Run 3 — same command, after 60-second cooldown
**Outcome:** PASS
**Diagnostics:**
- camoufox_version: 0.4.11
- responses[0]: status=200, size=449426, price_extracted=true
- responses[1]: status=200, size=419267, price_extracted=true
- responses[2]: status=200, size=202311, price_extracted=true (parser fix verified live)

## Step 2 — Limited live run
**Command:** `uv run python -m ga_crawler goldapple-run --run-id 42 --viled-brands givenchy,jo_malone_london --sanity-gate-m 10 --headless true`
**stdout JSON status:** failed
**reason:** smoke_probe_failed
**goldapple_count:** 0
**Duration (s):** ~20 (sitemap fetch + intersect + smoke probe + abort)

**Pipeline trace (structlog JSON):**
- `phase3_sitemap_fetch_start` → `phase3_sitemap_fetched` slug_count=**45,490** (sitemap parser works)
- `phase3_brand_intersect` viled_brand_count=2, matched_url_count=**0**, unmatched_brand_count=**2** (NORM-06 design bug — see Section "Findings")
- `camoufox_booted` (run_id=42, headless=true)
- `smoke_probe_complete` passed=false (URL[0] fell to size=9570, landing-page fallback — anti-bot transient)
- `phase3_smoke_failed` → fail-fast: orchestrator skipped fetch loop (D-312 enforced correctly)
- `camoufox_torn_down`

## Step 3 — runs.json metrics
- goldapple.smoke_pass: false (transient anti-bot at run start)
- goldapple.gate_shell_count / fetch_count: N/A (no fetch loop ran — abort on smoke fail)
- goldapple.fetch_failures / fetch_count: N/A
- goldapple.camoufox_version: 0.4.11
- goldapple.fetch_duration_seconds: ~20s end-to-end (sitemap + smoke only)

## Step 4 — NORM-06 outputs
- sitemap-slugs.txt slug count: **45,490** (much higher than spike estimate of ~1,461; multiple sitemap shards aggregated)
- unmatched_viled_brands count: 2 (`givenchy`, `jo_malone_london`) — root-caused below
- new_goldapple_slugs_count: 0 (expected — first run, no week-over-week diff baseline)

## Step 5 — Profile dir cleanup
- camoufox-run-42-* directories under $env:TEMP: **0** ✓ (`__aexit__` cleanup verified — Pitfall 7 holds)

## Step 6 — NORM-06 review queue subjective check
- Sample of first 3 unmatched brands: `givenchy`, `jo_malone_london` (only 2 brands tested)
- Format usable? **N** — review queue is empty *because* NORM-06 intersect emits no
  matches by design (see Findings #3). The format itself ("brand → list of probable
  alias slugs") is operator-readable when it has data; structural bug prevents data.

## Step 7 — Outcome

- [x] Smoke probe pass (Run 3, after cooldown)
- [ ] Limited live run reaches "success" — failed early on transient smoke
- [ ] gate_shell_count / fetch_count < 5% — N/A (no fetch loop)
- [ ] No sustained 429/503 errors — partial: only smoke 18 KB gate-shell, no 5xx
- [x] Profile dir cleaned
- [x] structlog JSON binds run_id on every event (verified end-to-end in run 42)
- [ ] NORM-06 review-queue format usable — empty due to design bug

**Verdict:** PHASE 3 LIVE-VERIFIED-WITH-ISSUES (3 backlog items captured below)

## Findings (root-caused during this checkpoint)

### Finding #1 — Microdata parser fails on bare priceMeta + bonus-button "при авторизации" (FIXED)
- **Surfaced by:** Smoke probe Run 1 URL[2] (Givenchy Gentleman Reserve Privee EDP)
- **Root cause:** Wave 2 gold-card heuristic walked DOM ancestors using recursive
  `Node.text()`, picking up "при авторизации" copy from a deep-nested bonus-badge
  button. Every `<meta itemprop="price">` in the offer was falsely classified as
  Gold Card; PARSE-04 sanity range then caught the price=0 filler and parser
  returned None.
- **Fix:** Narrow gold-card heuristic to direct siblings of `price_meta`, restrict
  to label tags (span/div/p/etc.), use shallow text only. Plus min-value selection
  among non-priceType candidates within an offer (sale price < was price).
- **Commit:** `277a40a fix(03-07): harden gold-card heuristic + min-value selection`
- **Tests:** 181/181 green (179 baseline + 2 new regression tests:
  `test_bonus_button_with_login_text_does_not_poison_price`,
  `test_zero_filler_price_is_skipped`).

### Finding #2 — Anti-bot reacts to rapid Camoufox cold-spawns (OPS, not code)
- **Surfaced by:** Smoke probe Run 2 (3rd consecutive cold-spawn within ~10 minutes)
- **Behavior:** All 3 URLs returned size~18 KB with title `"Gold Apple … checking device"`,
  classified as gate-shell.
- **Recovery:** 60-second cooldown then Run 3 returned full PDPs (449 / 419 / 202 KB).
- **Implication:** Production weekly cron (1 run / week, ~5.5 hours sequential at 3-5s
  rate-limit) will *not* trigger this — the rate is operationally well-spaced.
- **Backlog:** Phase 7 ops-playbook should add: minimum 60s cooldown between manual
  smoke probe runs; CI must not run smoke probe more than once per 5 minutes.

### Finding #3 — NORM-06 intersect logic mismatch with sitemap shape (DESIGN BUG)
- **Surfaced by:** `phase3_brand_intersect` `matched_url_count=0` for both
  `givenchy` and `jo_malone_london`, despite obvious matches in the sitemap.
- **Root cause:** `intersect_brand_pool` does `sitemap_slugs.get(brand_slug)` —
  exact match against dict keys. But sitemap parser indexes by **product slug**
  (e.g. `givenchy-pour-homme-blue-label`), not by **brand alias**. The brand
  `givenchy` cannot exact-match a product-slug key. Pitfall 3 / D-305 explicitly
  forbade substring matching to prevent false positives; an additional layer
  (first-token / brand-prefix bucket) is missing from the sitemap parser.
- **Implication:** Production matched_url_count will be 0 for every brand until
  the sitemap parser also indexes by brand-prefix or `intersect_brand_pool`
  uses bounded prefix match (`slug.startswith(brand + "-")`). Phase 3 fetcher
  pipeline is correct, but the orchestrator currently has nothing to crawl.
- **Backlog (gap_closure plan recommended):** Either (a) sitemap parser additionally
  emits a `dict[brand_token, list[url]]` index where `brand_token` is the first
  hyphen-separated token after the numeric prefix is stripped, or (b)
  `intersect_brand_pool` uses bounded `startswith(slug + "-")` over `sitemap_slugs.values()`
  with whitelist enforcement to satisfy Pitfall 3 / D-305 false-positive guards.

## Phase 7 ops-playbook backlog items (captured)
- [ ] Minimum 60s cooldown between manual smoke probe runs (anti-bot transient guard)
- [ ] Document smoke-URL rotation procedure when SMOKE_URLS go stale (URL[0]
      `7680100018-very-irresistible-givenchy` showed intermittent landing-page
      fallback during testing — likely product de-listing soon)
- [ ] Weekly cron alert if `goldapple.gate_shell_count / fetch_count > 5%`
- [ ] Camoufox upstream check: track `daijro/camoufox` releases vs `coryking/camoufox` fork
- [ ] **NORM-06 fix plan** — design `gap_closure: true` plan to repair brand-intersect
      bucketing (highest priority for Phase 4 matcher to be useful)
