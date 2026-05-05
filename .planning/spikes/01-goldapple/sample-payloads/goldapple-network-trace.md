# Goldapple.kz JSON-Endpoint Hunt — Network Trace (D-09)

**Investigation date:** 2026-05-06
**Operator:** mirdbek@gmail.com
**Method:** Programmatic — Patchright (chromium persistent context, headless=False, KZ-laptop direct, no proxy) with `page.on("request")` + `page.on("response")` capture across 7 URLs at 3-5s rate-limit. Substitutes the plan's manual DevTools session per user authorization (rationale: 01-04 already confirmed all HTML routes are JS-gated, so DevTools would require the same browser load anyway; programmatic capture exposes the same endpoints in machine-readable form).
**Script:** `.planning/spikes/01-goldapple/scripts/01-06-network-hunt.py` (reproducible).
**Trace data:** `.planning/spikes/01-goldapple/sample-payloads/goldapple-network-trace.json` (256 events).
**Sample HTML:** `.planning/spikes/01-goldapple/sample-payloads/goldapple-product-html-1.html` (one evidence challenge shell; the other was byte-equivalent and removed per 01-04 hygiene precedent).

**Pages visited (7):**
1. `https://goldapple.kz/` (home)
2. `https://goldapple.kz/brands/` (brands index)
3. `https://goldapple.kz/brands/tom-ford` (brand listing)
4. `https://goldapple.kz/brands/givenchy` (brand listing)
5. `https://goldapple.kz/19000032744-givenchy-gentleman-reserve-privee-eau-de-parfum` (product page, Givenchy)
6. `https://goldapple.kz/f/tom-ford-tualetnaja-voda` (facet page, Tom Ford)
7. `https://goldapple.kz/26543200002-creed-royal-water` (product page, Creed)

---

## Critical finding: Patchright FAILS the challenge on KZ-laptop direct

**All 7/7 pages stayed on the 18,057-byte JS-challenge shell** even after 20-25 second wait per page (poll-loop watching for title change away from "Gold Apple — checking device" + 5s `networkidle` settle). Total wall-clock per page = ~21s. **Challenge does NOT auto-resolve** under default Patchright fingerprint from a Kazakhstan laptop IP.

This is a **load-bearing negative result** for plan 01-08:
- D-01 (start at Tier 2 / Patchright) is **not enough** for goldapple.
- KZ-laptop IP (D-06 baseline) is rejected even with Patchright.
- Either: (a) the challenge needs an interactive solver / longer human-paced presence, (b) GroupIB fingerprints out Patchright's chromium specifically, or (c) IP reputation on this KZ residential block is bad. Distinguishing requires the IPRoyal proxy comparison from deferred plan 01-03 + 01-09.

| Page | size (B) | __NEXT_DATA__ | JSON-LD | challenge | render (s) |
|------|---------:|:------------:|:-------:|:---------:|-----------:|
| home | 18,238 | False | False | True | 21.81 |
| brands-index | 18,057 | False | False | True | 21.41 |
| brand-tom-ford | 18,057 | False | False | True | 21.31 |
| brand-givenchy | 18,057 | False | False | True | 21.33 |
| product-givenchy | 18,057 | False | False | True | 21.31 |
| product-tom-ford | 18,057 | False | False | True | 21.31 |
| product-creed | 18,057 | False | False | True | 21.26 |

---

## Anti-bot vendor identified: GroupIB / FACCT (NOT Cloudflare/DataDome)

The challenge shell HTML reveals the actual anti-bot stack — material new intel beyond what 01-04 captured:

| Signal | Evidence | Implication |
|--------|---------|-------------|
| `window.gib.init({...})` | inline script in challenge HTML | `gib` is **GroupIB** (https://www.group-ib.com — formerly Singapore-based fraud-prevention vendor; **rebranded to F.A.C.C.T. for Russian market** in 2023). Has anti-bot/anti-fraud fingerprint product. |
| `gafUrl: '//ru.id.facct.ru/id.html'` | inline script | F.A.C.C.T. fingerprint origin; iframe loaded from this domain to harvest device signals. Visible in trace (response 200 https://ru.id.facct.ru/id.html). |
| `cid = 'w-goldapple'` | inline script | GroupIB customer-id confirms goldapple is a paid GroupIB customer. |
| `error.name = 'GUN_INIT_PAGE'` + `'403 ошибка нет кук'` | Elastic APM capture | GoldApple internally calls this the "GUN" (likely "GUest News" / "Guard Until Negotiated") init page. They actively log denied visitors via Elastic APM at `sp.goldapple.ru/front/api/apm/events` (response 202 in trace). |
| `POST /web/api/v1/settings` | trace (every 10s during page life, all 403) | The gate-clearance API. Frontend polls; success triggers `location.reload()`. While `apm/events` accepts our requests (202), `settings` returns **403 (24/24 attempts)** — gate never opened. |
| `/_static/js/5ae5d1cd-7037-4ce7-9a67-dc2ed4d4e6ea.umd.min.js` | challenge shell | UUID-named challenge bundle (matches 01-04 finding). Same bundle as DataDome-style but actually GroupIB-served. |
| `cookie: ga-gun-init=true` | inline script sets it | Sentinel cookie (HTTP-only and signed cookies are likely set by the upstream challenge bundle but never granted in our session). |

**Implication for tier escalation:** 2026 Patchright benchmarks (per CLAUDE.md tier-2 confidence note) cite Cloudflare / DataDome / Akamai pass-rates. GroupIB / FACCT is **not in those benchmarks**. We are in uncharted territory; the plan's "Patchright-then-Patchright+proxy" assumption may not apply directly. Tier-3+ may require **Camoufox** (different fingerprint surface) rather than just adding residential proxy.

## XHR / Fetch endpoints observed

These endpoints fire from the challenge JS itself (not the real Next.js app, which never loads). Even from a failed gate, this is the goldapple frontend telemetry contract:

| URL pattern | Method | Status | Content-Type | Auth | Notes |
|---|---|---|---|---|---|
| `/web/api/v1/settings` | GET | 403 | _(error body)_ | requires gib-fingerprint cookie | **The gate**. Frontend retries every 10s; 200 → `location.reload()`. We hit this 24× across 7 pages × per-page retry; **0/24 successes**. |
| `/front/api/event?u=<uuid>&cfidsw-goldapple=<base64>` | GET | 200 | _(text)_ | none observed | GoldApple GUN telemetry beacon. Sends per-event fingerprint blob; `cfidsw-goldapple` is the encoded fingerprint payload. ~17 distinct cfidsw values observed across 7 pages. |
| `/front/api/event/idw-goldapple` | GET | 200 | _(text)_ | none | Initial telemetry handshake; sends UUID + customer-id. |
| `https://ru.id.facct.ru/id.html` | GET | 200 | _(html)_ | none | F.A.C.C.T. iframe origin (loaded as `<iframe>` in challenge body) for cross-origin device fingerprint harvest. |
| `https://sp.goldapple.ru/front/api/apm/events` | POST | 202 | _(json)_ | none | Elastic APM telemetry sink. **Out of scope (cross-domain, Russian goldapple infra).** |

**No `__NEXT_DATA__` or `/_next/data/*` requests observed** — these would only fire if the Next.js app ever bootstrapped, which requires passing the GUN gate first.

**No `/api/graphql` or GraphQL-style endpoint observed.** If goldapple uses GraphQL, it lives behind the gate and we never saw it.

**No `/rest/V1/...` Magento REST observed.** Consistent with 01-04 finding that `/rest/` is `Disallow`-ed in robots.txt; the frontend does NOT call it from any visible code path.

## __NEXT_DATA__ presence

- **Present in any of the 7 fetched HTMLs:** **NO** (0/7).
- **Reason:** every page is the GUN challenge shell, not the real Next.js app. The challenge is a barebones HTML with a 50 KB JS bundle that polls `/web/api/v1/settings` until cleared. The Next.js application never loads.
- **Tier-0 viability via __NEXT_DATA__:** **UNVERIFIABLE in this spike phase** without first passing the gate. Cannot confirm or deny that goldapple's real product pages embed `__NEXT_DATA__`. **Likely yes** — viled.kz uses Next.js with `__NEXT_DATA__` (per 01-07), and goldapple's frontend stack appears similar (the post-gate app is referenced as `Plaid_Web_Frontend_GUN_Client` in the APM init).

## JSON-LD presence

- **Present in any of the 7 fetched HTMLs:** **NO** (0/7).
- **Same root cause:** challenge shell only; real product HTML not reached.
- **D-14 satisfaction:** **UNVERIFIABLE** in this spike phase. 01-08 must re-test once gate-clearance is established (via proxy, Camoufox, or warm long-lived session).

## GraphQL

- **Endpoint detected:** **No** — neither in challenge HTML scripts nor in observed XHR.

## Anti-bot signals during investigation

| Signal | Observed | Notes |
|--------|----------|-------|
| Cloudflare challenge (`cf_clearance` cookie) | **No** | This is NOT a Cloudflare site. |
| DataDome | **No** | This is NOT a DataDome site. |
| GroupIB / F.A.C.C.T. | **YES** | Custom anti-fraud stack, see "Anti-bot vendor" section above. |
| 403 / 429 | **24× HTTP 403** on `/web/api/v1/settings` (the gate-clearance API). Other endpoints (`/front/api/event*`, `/sp.goldapple.ru/front/api/apm/events`) returned 200/202 (telemetry is intentionally accepted to log denied visitors). |
| Captcha shown | **No** | No interactive challenge UI; the gate is fingerprint-only (silent fail). |
| rate-limit triggered | **No** explicit rate-limit headers observed. The 403 is fingerprint-based, not rate-based. |
| Persistent context preserved | **Yes** — same `browser-state/` directory across all 7 pages. Cookies (`ga-gun-init=true`, gib-set entries) survived between page loads. **Did not help** — gate did not clear despite cookie persistence. |

## D-14 ALERT (per plan 01-06)

D-14 defines "successful fetch" as `HTML 200 + JSON-LD product schema present`. **In this network-hunt session, 0/7 pages yielded JSON-LD.** This is NOT because goldapple lacks JSON-LD — we never reached real product HTML. **D-14 verification deferred to plan 01-08 post-gate-clearance.**

If 01-08 also fails to reach real HTML, D-14 needs revision (e.g., to use `__NEXT_DATA__` or Open Graph `og:price` meta tag as proxy if those are present). But we cannot revise D-14 now without evidence about the post-gate page.

## Verdict

**TIER 0 NOT VIABLE for goldapple** — no JSON endpoint observed in this hunt. **Tier 2 (Patchright direct, KZ-IP) ALSO NOT VIABLE** — gate fails on default fingerprint. **Patchright + KZ residential proxy (Tier 2.5) — UNTESTED yet (deferred to revive plan 01-03).** Camoufox or Scrapling StealthyFetcher (Tier 4) becomes a more likely escalation than originally planned because the anti-bot vendor is GroupIB/F.A.C.C.T., not Cloudflare/DataDome (which Patchright benchmarks specifically target).

**More precisely (per the 3-option D-10 framework):**
> **Option B — Tier 0 NOT viable, Tier 2+ required.** Plus: Tier 2 is itself confirmed insufficient on this baseline; further escalation needed for Phase 3.

**Open question for plan 01-08:** does the gate clear with (a) IPRoyal residential proxy (KZ or RU), (b) Camoufox (different fingerprint), (c) longer-lived warm session (>5 minutes idle browsing before first product fetch), or (d) all of the above combined? Each branch flips a different MEMO line in plan 01-11.

## Implications for plan 01-08

- **Revive deferred plan 01-03 (IPRoyal).** STATE.md said "if ≥98/100 + challenge<10% — proxy not needed". We now have 0/7 + 100% gate-fail at KZ-laptop. Proxy is needed; sign up before 01-08 starts so we don't lose a day to KYC.
- **Add Camoufox as primary 01-08 candidate**, not as Tier-4 last resort. The vendor mismatch (GroupIB vs Patchright's Cloudflare/DataDome benchmarks) reorders the escalation tree.
- **The 100-fetch experiment may need to start with a 5-15 minute warmup** (idle browsing of static pages, scrolling, etc.) before the first product fetch, to let the GUN fingerprinter accept the session. Check by polling `/web/api/v1/settings` in background and starting product fetches only after first 200.
- **Consider that goldapple is a goldapple.kz domain but anti-bot is hosted on goldapple.ru / facct.ru** (Russian infra). EU IP from Hetzner (Phase 7 baseline) likely WORSE than KZ residential, because GroupIB likely whitelists local TLD/IP-geo combinations. Hetzner-EU Phase 7 may need IPRoyal-KZ proxy as a hard requirement.

---

## Re-run

```powershell
cd C:\Users\gstorepc\projects\ga_crawler
$env:PYTHONIOENCODING = "utf-8"
uv run python .planning/spikes/01-goldapple/scripts/01-06-network-hunt.py
```

Expected wall-clock: ~3 minutes. Browser state at `.planning/spikes/01-goldapple/browser-state/` (gitignored). Delete it before re-run for a clean session.

---

*Investigation completed by gsd-executor on 2026-05-06; finding documented even though the gate was not cleared — the negative result and the GroupIB/F.A.C.C.T. discovery are themselves the load-bearing deliverable for plan 01-08 planning.*
