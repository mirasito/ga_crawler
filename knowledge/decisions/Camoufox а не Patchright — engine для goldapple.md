---
tags: [decision, anti-bot, phase-1, camoufox, patchright, supersedes]
date: 2026-05-06
---

# Camoufox а не Patchright — engine для goldapple

**Browser engine для goldapple.kz в Phase 3 = Camoufox** (Firefox-based, C++-level fingerprint spoofing). Не Patchright (Chromium), не vanilla Playwright, не Selenium-stealth.

**Это решение supersedes:** [[Tier 2 Patchright — стартовый tier для goldapple]].

## Почему

Эмпирический результат спайка 2026-05-06:

| Engine | Setup | Result |
|---|---|---|
| **Patchright** (Chromium) | KZ-laptop, persistent context, 21s wait | **0/7 gate-pass.** 24×403 на `/web/api/v1/settings`. Все страницы — 18 KB challenge shell. |
| **Camoufox** (Firefox) | KZ-laptop, persistent context, geoip+humanize | **3/3 gate-pass instantly** (`wait_ms=0`). 0×403. HTML 200K-724K (real Next.js app). JSON-LD 3/3. |

Тот же IP, тот же бренд URLs (Tom Ford, Givenchy product), та же сессия. Разница только в browser engine.

## Почему именно Camoufox победил

[[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]] — vendor использует fingerprint-based detection (не rate-based, не CAPTCHA, не interactive challenge). 2026 Patchright benchmarks (CLAUDE.md §Anti-Bot Strategy) targeted Cloudflare/DataDome/Akamai — GroupIB не в этих бенчмарках.

Camoufox — Firefox-based с C++-level fingerprint spoofing. Совершенно другая поверхность отпечатка против Chromium-based Patchright. GroupIB классифицирует Camoufox как обычного KZ-пользователя (с `geoip=True` для timezone/locale alignment + `humanize=True` для cursor jitter).

## Что это меняет

### Phase 1 спайк (немедленно)

- **01-03 IPRoyal trial → SKIP.** Прокси не нужен (фингерпринт-проблема, не IP-rep).
- **01-08 100-fetch test → REWRITE на Camoufox.** D-13 ≥95/100, D-14 JSON-LD success, D-15 challenge-rate <20% — все критерии остаются, меняется только engine.
- **01-09 EU-proxy multi-geo → SKIP** (или маленький Phase-7-prep run).
- **01-10 Tier 3 escalation → SKIP** (триггер не сработает).

### Phase 3 production stack

```
goldapple enumeration  : curl_cffi + sitemap.xml      (Tier 0 — открыт)
goldapple product render: Camoufox + JSON-LD parse     (Tier 2)
viled enumeration       : curl_cffi + sitemap.xml      (Tier 0)
viled product render    : curl_cffi + __NEXT_DATA__    (Tier 0)
```

- **Proxy budget:** $0 baseline. IPRoyal — back of pocket если Camoufox пробьётся со временем.
- **Hosting (Phase 7):** Hetzner-EU baseline жизнеспособен снова, но **обязательно** проверить Camoufox+EU-IP одним запросом перед locking. Если EU не проходит — KZ residential (IPRoyal trial реактивируется как Phase 7 task).

## Риски

1. **Maintenance:** `daijro/camoufox` upstream — CLAUDE.md флагует unmaintained-as-of-2025. Но мы получили v135.0.1-beta.24 (Firefox 135-based) в 2025-Q4 — fresh enough. Operational playbook должен включать periodic check "Camoufox still passes goldapple gate".
2. **Vendor adapts:** GroupIB может зарелизить fingerprint update который классифицирует Camoufox. Нужен monitoring + быстрый rollback на Tier 4 (managed unblocker, ZenRows/BrightData) если внезапный массовый фейл.
3. **Geo-binding:** anti-bot хостится на `goldapple.ru` / `facct.ru` (Russian infra). Если RuNet split / sanctions / DNS issues — фейл. Этот риск independent от browser engine.

## Доказательства

- `.planning/spikes/01-goldapple/sample-payloads/camoufox-spike-trace.md` — human-readable
- `.planning/spikes/01-goldapple/sample-payloads/camoufox-spike-trace.json` — 688 response events, 0×403
- `.planning/spikes/01-goldapple/sample-payloads/goldapple-network-trace.md` — Patchright failure baseline (24×403)
- `.planning/spikes/01-goldapple/scripts/01-06b-camoufox-spike.py` — repro

## Связанные

- [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]] — vendor identification
- [[Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом]] — но sitemap живой
- [[Tier 2 Patchright — стартовый tier для goldapple]] — **SUPERSEDED** этим решением
- [[Goldapple anti-bot — определяющий риск проекта]] — корневой risk decision
- [[2026-05-06 — Camoufox побеждает GroupIB, Phase 1 re-route]] — session log
