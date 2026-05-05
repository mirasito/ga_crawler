---
tags: [decision, anti-bot, vendor-id, phase-1, groupib, facct]
date: 2026-05-06
---

# Goldapple anti-bot — это GroupIB / F.A.C.C.T., не Cloudflare

**Anti-bot/anti-fraud vendor goldapple.kz = GroupIB (F.A.C.C.T. — Russian-market rebrand).** Не Cloudflare, не DataDome, не Akamai, не Kasada. Все 2026-public Patchright-bypass benchmarks (CLAUDE.md §Anti-Bot Strategy Tier 2-3) targetят первые три — для GroupIB они **не валидны**.

## Доказательства (network trace 01-06)

| Signal | Evidence | Implication |
|---|---|---|
| `window.gib.init({...})` | inline script в challenge HTML | `gib` = **GroupIB** (https://www.group-ib.com — Singapore, 2003) → анти-фрод/анти-бот fingerprint product |
| `gafUrl: '//ru.id.facct.ru/id.html'` | inline script | F.A.C.C.T. — российский ребрендинг GroupIB (2023, после санкций) → fingerprint origin iframe |
| `cid = 'w-goldapple'` | inline script | GroupIB customer-id — goldapple платный клиент GroupIB |
| `error.name = 'GUN_INIT_PAGE'` | Elastic APM capture | GoldApple-internal термин: "GUN" (Guard Until Negotiated) для denied-visitor flow |
| `POST /web/api/v1/settings` → 403 (24/24) | Patchright run trace | Gate-clearance API. Frontend polls each 10s; 200 → `location.reload()`; 403 → бесконечный poll |
| `/_static/js/<UUID>.umd.min.js` | challenge HTML | UUID-named challenge bundle (DataDome-стиль, но goldapple-served) |

## Что это меняет

### Tier escalation tree (research/STACK.md обновляется)

| Tier | Технология | Применимо к goldapple (GroupIB)? |
|---|---|---|
| 0 | curl_cffi impersonate | НЕТ — gate fingerprint-based, требуется browser |
| 1 | Vanilla Playwright | НЕТ — заведомо детектится (research/PITFALLS.md) |
| 2 | Patchright (Chromium stealth) | **НЕТ** — empirical 0/7 (01-06). 2026 benchmarks для Cloudflare/DataDome не транслируются |
| 2.5 | Patchright + residential proxy | НЕИЗВЕСТНО (не тестировали; вероятно тоже нет — fingerprint, не IP) |
| 3 | **Camoufox** (Firefox stealth) | **ДА** — empirical 3/3 instantly (01-06b) |
| 4 | Managed unblocker (ZenRows/BrightData) | контингенция если Camoufox сломается |

### Operational playbook (Phase 7)

- **Health-check:** регулярный (weekly?) Camoufox spike против goldapple — если fingerprint drift сломает Camoufox, узнаём ДО того как weekly run упадёт
- **Monitoring:** structlog должен логировать `/web/api/v1/settings` response code на каждый product fetch. 403-rate >5% — emergency alert на ops chat
- **Vendor-watching:** мониторить GroupIB/F.A.C.C.T. blog/changelog на fingerprint detection updates

### Geo / hosting (Phase 7 решение)

Anti-bot endpoints хостятся на:
- `goldapple.ru` (не `goldapple.kz`!) — корневой backend в Russian infra
- `facct.ru` — F.A.C.C.T. fingerprint iframe

Implications:
- **EU-IP (Hetzner) skepticism:** GroupIB вероятно whitelistит local TLD/IP-geo комбинации. Hetzner-EU может работать на Camoufox (фингерпринт-проблема не в IP) **или** не работать (если есть geo-rule). Empirical test перед Phase 7 lock-in — **обязателен**.
- **Sanctions/DNS risk:** RuNet split, EU sanctions on Russian infra, или DNS issues → возможно `facct.ru` недоступен из EU. Worst case → Camoufox перестаёт проходить gate из-за timeout на iframe load. Mitigation: residential KZ proxy через IPRoyal.

## Связанные

- [[Camoufox а не Patchright — engine для goldapple]] — winning engine
- [[Tier 2 Patchright — стартовый tier для goldapple]] — **SUPERSEDED**
- [[Goldapple anti-bot — определяющий риск проекта]] — vendor ID был unknown unknown
- [[Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом]] — следствие fingerprint-gate
- [[2026-05-06 — Camoufox побеждает GroupIB, Phase 1 re-route]] — session log

## Артефакты

- `.planning/spikes/01-goldapple/sample-payloads/goldapple-network-trace.md` — полный детальный трейс vendor identification
- `.planning/spikes/01-goldapple/sample-payloads/goldapple-product-html-1.html` — challenge shell sample (18 KB)
- `.planning/spikes/01-goldapple/sample-payloads/goldapple-network-trace.json` — 256 raw events
