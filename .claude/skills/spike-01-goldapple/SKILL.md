---
name: spike-01-goldapple-anti-bot
description: Phase 1 spike findings for goldapple.kz anti-bot tier. Use when planning Phase 3 (Goldapple Crawl) or Phase 7 (hosting/prod-IP) to recall chosen tier, browser engine, proxy provider, microdata-not-JSON-LD parser strategy, and committed rate-limits.
---

# Spike 01: Goldapple Anti-Bot Findings (Reference Skill)

**Source memo:** [[.planning/spikes/01-goldapple/MEMO]] (repo-local, signed off 2026-05-06)
**Spike completed:** 2026-05-06
**Phase 1 status:** DONE
**Sign-off:** mirdbek@gmail.com (operator), APPROVED

## What was decided

**Goldapple.kz scrapeable at Tier 2 using Camoufox (Firefox + C++ fingerprint spoof) with NO proxy from KZ-laptop.** 100-fetch run gave 99/100 success at 0% gate-shell rate, NOT FRAGILE per D-15. Anti-bot vendor identified as **GroupIB / F.A.C.C.T.** Patchright is empirically broken (0/7) for this gate. Goldapple uses inline microdata (`<meta itemprop="price">`), NOT JSON-LD Product schema. viled.kz feasibility CONFIRMED via `curl_cffi impersonate=chrome` (15/15 HTTP 200).

| Field | Value |
|---|---|
| **Chosen tier** | 2 |
| **Browser engine** | Camoufox v135.0.1-beta.24 (daijro upstream; coryking fork as backup if upstream stalls) |
| **Proxy provider** | none (KZ-laptop direct sufficient) |
| **Prod-IP target (Phase 7)** | Hetzner CX22 EU + smoke gate; IPRoyal KZ residential as fallback |

## Operational constants for Phase 3

- **Goldapple rate-limit:** 3-5 секунд random uniform, sequential, concurrency=1
- **viled rate-limit:** 2 секунды sequential
- **Goldapple persistent context:** required (cookies live across fetches per D-04)
- **Camoufox config:** `geoip=True`, `locale=['ru-RU','kk-KZ','en-US']`, `humanize=True`, `persistent_context=True`
- **Page-volume estimate:** ~4,000 fetches/week goldapple + ~5,000 fetches/week viled = ~5.5 hours/week sequential at chosen rate-limits
- **JSON-endpoint path:** Tier 0 dead for goldapple product render (JSON endpoints behind gate); Tier 0 LIVE for sitemap.xml enumeration (plain via curl_cffi). Hybrid: curl_cffi sitemap + Camoufox product render.

## Stack constraints (do not deviate without re-spike)

- **Phase 3 goldapple parser:** `selectolax` + microdata extraction via `tree.css('meta[itemprop="price"]')` and `tree.css('meta[itemprop="priceCurrency"]')`. **NOT JSON-LD** — goldapple's only JSON-LD block is `OfferShippingDetails`, no Product schema.
- **Phase 2 viled parser:** `selectolax` + `json.loads` of `__NEXT_DATA__` script content; canonical paths `props.pageProps.{item,attributes}`. **NOT JSON-LD** — viled does not emit schema.org Product markup. 8 canonical field paths captured in [[../../.planning/spikes/01-goldapple/sample-payloads/viled-nextdata-shape.json]].
- **Browser engine for goldapple:** Camoufox only. Patchright was empirically broken for this gate (0/7 plan 01-06 baseline). Vanilla Playwright skipped per D-01.
- **Proxy for goldapple:** none baseline. Reactivate IPRoyal KZ residential (~$2/week) only if Phase 7 EU-hosting+Camoufox combination fails the gate.
- **Stale-SKU detection:** distinguish "no microdata" (de-listed SKU returns 200 + 9.5 KB shell) from "gate not cleared" (anti-bot block) — title check on the response. Match-rate pipeline must NOT treat de-listed pages as scrape failures.

## Production monitoring (Phase 3 ops playbook)

- **Weekly Camoufox-vs-goldapple smoke:** does the gate still pass? Alert if pass-rate drops below 90% — early-warning before fragility.
- **Gate-shell rate threshold:** alert if any weekly run's gate-shell rate >5% (well below the 20% D-15 fragility line).
- **Camoufox upstream check:** track daijro/camoufox releases; have coryking/camoufox fork as switch-ready backup.
- **Stale-SKU rate:** track per-week count of "200 + <30 KB + no microdata" pages; if >5%, sitemap may have stale entries needing prune.

## When to consult this skill

- `/gsd-discuss-phase 3` — для anti-bot constraints, rate-limits, parser strategy
- `/gsd-plan-phase 3` — для Camoufox config, persistent_context wiring, microdata extractor implementation
- Phase 7 hosting decisions — для proxy provider choice (Hetzner EU first, IPRoyal KZ fallback)
- Any "should we use JSON-LD?" question for goldapple — the answer is NO, use microdata
- Any "should we use Patchright?" question for goldapple — the answer is NO, use Camoufox

## Critical files (entry points)

- [[../../.planning/spikes/01-goldapple/MEMO]] — full decision memo (12 sections, sign-off)
- [[../../.planning/spikes/01-goldapple/notebook.py]] — Camoufox 100-fetch reference implementation
- [[../../.planning/spikes/01-goldapple/sample-payloads/tier2-camoufox-kz-results.json]] — empirical evidence (99/100)
- [[../../.planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html]] — saved real-app HTML (for parser calibration)
- [[../../.planning/spikes/01-goldapple/sample-payloads/_debug-jsonld-blocks.json]] — proof goldapple has only OfferShippingDetails JSON-LD
- [[../../knowledge/decisions/Goldapple — Tier 2 Camoufox без proxy, 99 из 100]] — Obsidian-vault sign-off note

## What was NOT decided here (defer to relevant phase)

- Phase 7 actual hosting choice — depends on Camoufox+EU smoke test outcome (data not yet collected)
- Brand-alias YAML structure — Phase 4 deliverable, this spike just flags the brand-precision shortfall
- viled-vs-goldapple match-rate ceiling — depends on Phase 4 first-week run data
