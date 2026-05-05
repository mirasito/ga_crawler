---
tags: [decision, anti-bot, goldapple, scraping, ga_crawler, tier-2, camoufox, sign-off]
date: 2026-05-06
project: ga_crawler
phase: 1-goldapple-reconnaissance-spike
tier: 2
source_memo: "[[.planning/spikes/01-goldapple/MEMO]]"
---

# Goldapple — Tier 2 Camoufox без proxy, 99 из 100

> Decision date: 2026-05-06
> Source: GA Crawler Phase 1 reconnaissance spike sign-off (plan 01-08 + 01-11)
> Full memo: [[.planning/spikes/01-goldapple/MEMO]] (repo-local source of truth)

## Bottom line

**Goldapple.kz scrapeable at Tier 2 using Camoufox (Firefox + C++ fingerprint spoof) with NO proxy from KZ-laptop.** 100-fetch run: 99/100 success, 0% gate-shell rate, NOT FRAGILE per D-15. Anti-bot vendor identified as **GroupIB / F.A.C.C.T.** (Russian-market fraud-prevention). Patchright 0/7 (superseded), Camoufox 99/100 (chosen). Goldapple uses inline microdata (`<meta itemprop="price">`), NOT JSON-LD Product schema — D-14 revised mid-spike. viled.kz feasibility: CONFIRMED via `curl_cffi impersonate=chrome` (15/15 HTTP 200).

- **Chosen tier:** 2
- **Browser engine:** Camoufox v135.0.1-beta.24 (Firefox-based; daijro upstream)
- **Proxy provider:** none (KZ-laptop direct sufficient)
- **Production IP recommendation (Phase 7):** Hetzner CX22 EU + ONE-fetch Camoufox+EU smoke test before locking. If smoke fails → IPRoyal KZ residential (~$2/week). If passes → no proxy, $0/week.

## Why this matters

- **Phase 3 stack-decision unblocked.** Camoufox + selectolax + microdata extraction = goldapple parser. NOT JSON-LD as previously assumed.
- **Phase 7 hosting is now a smoke-gate, not a re-spike.** Hetzner EU is the working hypothesis; proxy budget reactivates only if EU+Camoufox combination breaks the gate.
- **viled.kz curl_cffi confirmed (RECON-02 closed).** Phase 2 ETL pipe is unblocked: curl_cffi + selectolax + json on `__NEXT_DATA__`.
- **Plans 01-09 (multi-geo proxy) and 01-10 (Tier 3 escalation) were SKIPPED.** Fingerprint alone solves the gate. D-08 (IPRoyal pre-register) cancelled.
- **Spike timebox honored:** 2 days of 1-week budget (per D-02).

## Operational constraints

- **Goldapple rate-limit:** 3-5 секунд random uniform между fetch'ами, sequential, concurrency=1
- **viled rate-limit:** 2 секунды между fetch'ами, sequential
- **Goldapple persistent context:** required (cookies live across fetches per D-04)
- **Camoufox config:** `geoip=True`, `locale=['ru-RU','kk-KZ','en-US']`, `humanize=True`, `persistent_context=True`, `user_data_dir=.camoufox-state` (gitignored)
- **Production budget:** $0/week proxy (baseline), ~$2/week if IPRoyal KZ fallback activates
- **Production duration:** ~5.5 hours/week sequential (goldapple ~4.4h + viled ~70min); fits Sunday-night cron

## Open risks (transferred to Phase 7 / Phase 3 backlog)

- goldapple is microdata-only, NOT JSON-LD — Phase 3 parser strategy is asymmetric vs viled
- Brand-precision shortfall on Tom Ford / Jo Malone London in numeric-id sitemap (Phase 4 brand-alias YAML compensates)
- Camoufox upstream maintenance (daijro vs coryking fork — weekly check in Phase 3 ops playbook)
- Hetzner-EU + Camoufox compatibility unverified — smoke test before locking Phase 7 hosting
- Stale-SKU 200-but-9.5KB pattern — Phase 3 parser must distinguish "no microdata" (de-listed SKU) from "gate not cleared" (block)
- GroupIB is in uncharted public-scraping territory — no community pre-vetted next-step engine if Camoufox drift breaks the gate

## Cross-references

- [[.planning/PROJECT]]
- [[.planning/ROADMAP]]
- [[.planning/research/STACK]]
- [[.planning/research/PITFALLS]]
- [[Camoufox а не Patchright — engine для goldapple]] — earlier engine-choice decision; this note is the final sign-off after the 100-fetch confirmed the choice at scale
- [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]] — vendor ID
- [[Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом]] — but sitemap.xml IS Tier 0 deliverable (enumeration)
- [[2026-05-06 — Camoufox побеждает GroupIB, Phase 1 re-route]] — session note that triggered the rewrite

## Related decisions

- ~~[[Tier 2 Patchright — стартовый tier для goldapple]]~~ — superseded by this note
