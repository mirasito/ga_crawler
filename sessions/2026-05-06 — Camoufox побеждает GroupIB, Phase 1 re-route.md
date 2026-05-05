---
tags: [session, phase-1, anti-bot, camoufox, groupib]
date: 2026-05-06
---

# 2026-05-06 — Camoufox побеждает GroupIB, Phase 1 re-route

## Что сделано

Phase 1 спайк прошёл с **6/12 планов исполненными** + один спайк-внутри-спайка ([[Camoufox а не Patchright — engine для goldapple|Camoufox-эксперимент]]) который перевернул всю tier-стратегию.

**Wave 0 (setup):** 01-01 ✓ skeleton · 01-02 ✓ uv + Patchright + Chromium · 01-03 ⏭ IPRoyal **отложен**, потом **окончательно отменён**.

**Wave 1 (cheap recon):**
- 01-04 ✓ robots/ToS аудит — viled чистый (только KZ Law 94-V Privacy), goldapple **глобально под JS-challenge** (все HTML routes идентичный 18.9 KB shell). Committed rate-limits: viled=2s, goldapple=3-5s random. `/rest/` Magento — robots-Disallowed.
- 01-05 ✓ sitemap + page-volume — **goldapple sitemap.xml plain-deliverable** через curl_cffi. 112 317 URLs, 100 779 product, 1461 брендов. Phase 3 budget anchor: ~600 MB/week, ~$2.10 proxy, ~4.4h run. Executor сам спарсил viled `__NEXT_DATA__` чтобы выбрать **luxury parfumerie** бренды (не mass-market): Jo Malone, Tom Ford, Creed, Frederic Malle, Givenchy.
- 01-06 ✓ JSON-endpoint hunt + Patchright warm-up — **Patchright + KZ-laptop = 0/7 gate-pass** даже за 21 сек. **Tier 0 мёртв** для goldapple ([[Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом]]). Идентифицирован anti-bot vendor: [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]] — не Cloudflare/DataDome, fingerprint-based 403 на `/web/api/v1/settings`.
- 01-07 ✓ viled curl_cffi feasibility — **15/15 HTTP 200**, avg 485ms, **0/15 JSON-LD но 15/15 `__NEXT_DATA__`**. Phase 2 PARSE-02 паттерн зафиксирован: `props.pageProps.{item, attributes}` с 8 каноническими путями. viled enumeration = sitemap-only (42 294 URLs).

**Side-spike (01-06b Camoufox):** ~15 мин. **Camoufox + KZ-лэптоп прямой = 3/3 gate-pass instantly** (`wait_ms=0`), JSON-LD на всех 3, zero 403. Гипотеза 01-06 ("fingerprint-based, не IP-rep") подтверждена в чистую.

## Ключевые открытия

1. **goldapple anti-bot = GroupIB / F.A.C.C.T.** (Russian-market rebrand of Singapore-based GroupIB), не Cloudflare и не DataDome. Patchright-бенчмарки в CLAUDE.md мимо — мы в uncharted territory для public scraping community.
2. **Camoufox (Firefox + C++ fingerprint spoofing) полностью обходит GroupIB** на дефолтном fingerprint без прокси, с KZ-лэптопа. Тот же gate API `/web/api/v1/settings` даёт нам 200 на первом же вызове (vs 24×403 для Patchright).
3. **Tier 0 для goldapple частично жив:** sitemap (enumeration) — да, product data (render) — нет. Hybrid: curl_cffi sitemap + Camoufox product render.
4. **viled полностью Tier 0:** curl_cffi везде, Phase 2 stack заморожен.
5. **anti-bot хостится на goldapple.ru / facct.ru** (Russian infra). Hetzner-EU baseline для Phase 7 → нужно проверить Camoufox+EU одним запросом перед locking. Может потребоваться KZ residential обратно.

## Re-route Phase 1

| Plan | Было | Стало |
|---|---|---|
| 01-03 IPRoyal | wave 0, требовался для прокси | **SKIP** — Camoufox без прокси работает |
| 01-08 100-fetch | Patchright Tier-2 KZ-laptop | **REWRITE на Camoufox** (тот же D-13/14/15) |
| 01-09 EU-proxy comparison | multi-geo для D-05 | **SKIP** (или маленький проверочный run если нужно для Phase 7) |
| 01-10 Tier 3 escalation | условный | **SKIP** — триггер не сработает |
| 01-11 MEMO | синтез | **rewrite verdict**: Tier 2 = Camoufox direct, no proxy |
| 01-12 wrap-up | as-is | as-is |

## Что осталось

Минимум для закрытия Phase 1 (~1.5 ч wall-clock):
1. **01-08 переписать на Camoufox**, прогнать на 100 URLs (полный D-13 ≥95/100 тест), 30-60 мин
2. **01-11 MEMO** с обновлённым verdict
3. **01-12 wrap-up** (Obsidian copy MEMO + project skill)

## Связанные

- [[Camoufox а не Patchright — engine для goldapple]] — главное решение сессии
- [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]] — vendor ID
- [[Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом]] — но sitemap живой
- [[Tier 2 Patchright — стартовый tier для goldapple]] — superseded (см. ↑)
- [[Текущие приоритеты — Phase 1 спайк]] — обновлены под новый план

## Артефакты на диске

- `.planning/spikes/01-goldapple/sample-payloads/camoufox-spike-trace.md` (human-readable verdict)
- `.planning/spikes/01-goldapple/sample-payloads/camoufox-spike-trace.json` (688 response events)
- `.planning/spikes/01-goldapple/sample-payloads/goldapple-network-trace.md` (01-06 Patchright failure trace + GroupIB ID)
- `.planning/spikes/01-goldapple/scripts/01-06-network-hunt.py` (Patchright probe)
- `.planning/spikes/01-goldapple/scripts/01-06b-camoufox-spike.py` (Camoufox probe)
- `.planning/spikes/01-goldapple/MEMO.md` (заполняется по мере спайка; финал в 01-11)

## Команда продолжения

Сейчас pause перед 01-08-camoufox. Continue:
```
/gsd-execute-phase 1
```
(он подхватит plan 01-08, операторам надо будет принять решение rewrite-в-place или формальный re-plan)
