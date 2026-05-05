---
tags: [session, phase-1, sign-off, camoufox, microdata]
date: 2026-05-06
---

# 2026-05-06 — Phase 1 closure через 01-08 Camoufox + 01-11 MEMO + 01-12 wrap-up

Продолжение сессии [[2026-05-06 — Camoufox побеждает GroupIB, Phase 1 re-route]]. Закрыли Phase 1 формально: 01-08 переписан под Camoufox и прогнан, 01-11 MEMO подписан, 01-12 wrap-up развернул spike в Obsidian-decision + project-skill + STATE.

## Что сделано

**01-08 rewrite + run.** План был ещё на Patchright; переписали (commit `532b37c`). Собрали 100 product URLs из sitemap (49 brand-matched + 51 random — Tom Ford / Jo Malone отсутствуют в numeric-id sitemap entirely; commit `649eb6c`). Заменили stub `notebook.py` на Camoufox 100-fetch loop с D-03 stop-rule (commit `90f112d`). Smoke-test на 5 URL вскрыл что **goldapple JSON-LD = только OfferShippingDetails**, не Product schema — D-14 пришлось revisit. Доделали extractor (microdata `itemprop="price"` OR JSON-LD Product), оба сигнала логируются. **Run 100/100 завершился: 99 success, 100 gate cleared (1× 1000ms wait, 99 instant), 0% gate-shell rate.** D-13 PASS, NOT FRAGILE. 1 block — стейл-SKU `/7681000002-givenchy-pour-homme-blue-label` рендерит 200+9.5KB shell без microdata (де-листинг, не anti-bot). Commits `f9ace33`, `e13e47a`, `175d6de`.

**01-11 MEMO finalize.** TL;DR + Chosen + Next-step impact + Open Risks + Appendix Challenge-rate + Sign-off. robots/ToS rate-limit TBDs заменены: viled 2s, goldapple 3-5s random uniform. KZ-legal deferred to Phase 7. Все 12 obligatory секций populated, zero TBDs. Sign-off mirdbek@gmail.com 2026-05-06 APPROVED. Commits `70fdffa`, `e4a5a1b`.

**01-12 wrap-up.** Obsidian decision-нота `[[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]]` создана с frontmatter (tier: 2, source_memo wiki-link). Project-local skill `.claude/skills/spike-01-goldapple/SKILL.md` написан — Phase 3 discuss/plan теперь автоматически имеет quick-reference. STATE.md обновлён: Phase 1 closed, 9/12 plans completed + 3 skipped explicitly, Tier 2 row в Key Decisions, Phase 2/3 в What's Next, Active Todos сброшены/перевыставлены. Obsidian index.md обновил живые/superseded блоки.

## Ключевые открытия в этой сессии

1. **Goldapple uses INLINE MICRODATA, NOT JSON-LD Product schema.** Только один JSON-LD блок в продуктовой странице — `OfferShippingDetails`. Цена через `<meta itemprop="price"><meta itemprop="priceCurrency">`. D-14 revised: success = JSON-LD Product OR microdata. Phase 3 parser asymmetric: microdata для goldapple, `__NEXT_DATA__` для viled. (Это новая, материальная разница.)

2. **Camoufox при scale (100 vs 3) держится отлично.** 0% gate-shell rate, 1× 1000ms wait, 99 instant. Hypothesis 01-06b ("fingerprint-based, не IP-rep") empirically validated на 100-pool.

3. **Стейл-SKU 200-but-9.5KB pattern.** Реальные продукты на goldapple могут быть de-listed но возвращать 200 с shell-sized payload. Title clear ("checking device" не остался), microdata отсутствует — это НЕ anti-bot, а просто пустой product page. Phase 3 парсер должен это различать чтобы match-rate не отравлялся.

4. **Brand-precision shortfall на Tom Ford / Jo Malone London.** Numeric-id sitemap (`/<digits>-<slug>`) не содержит product URLs для этих 2 брендов вообще — они только под `/brands/<slug>/...` facet routes. Spike substituted random URLs, документировано как Open Risk; Phase 4 brand-alias YAML строится отдельно.

## Производительность сессии

- ~12 мин wall-clock на 100-fetch run
- ~30 мин на plan rewrite + URL collection + smoke-debug + D-14 revision
- ~20 мин на 01-11 MEMO + 01-12 Obsidian/skill/STATE
- **Итого Phase 1:** 2 дня из 7-дневного timebox (D-02). 9/12 plans + 3 skip. spike окупился — anti-bot вердикт получен decisively.

## Phase 3 stack (locked)

```
goldapple enumeration   : curl_cffi + sitemap.xml          (Tier 0 ✓)
goldapple product render: Camoufox + selectolax + microdata (Tier 2 ✓ NEW: not JSON-LD)
viled enumeration       : curl_cffi + sitemap.xml          (Tier 0 ✓)
viled product render    : curl_cffi + __NEXT_DATA__        (Tier 0 ✓)
proxy budget            : $0 baseline (KZ-laptop direct sufficient)
host (Phase 7)          : Hetzner-EU + Camoufox+EU smoke gate; IPRoyal KZ как fallback
maintenance risk        : Camoufox upstream daijro vs coryking fork — weekly gate-pass check в playbook
```

## Что дальше

`/gsd-discuss-phase 2` (viled crawl + storage) или `/gsd-discuss-phase 3` (goldapple crawl). Они data-independent. Phase 2 hot-data (8 viled `__NEXT_DATA__` field paths) уже зафиксирован в 01-07.

## Связанные

- [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]] — финальное sign-off-решение
- [[2026-05-06 — Camoufox побеждает GroupIB, Phase 1 re-route]] — пред-сессия (re-route)
- [[Текущие приоритеты — Phase 1 спайк]] — обновлены в "closed" статус
- [[Camoufox а не Patchright — engine для goldapple]] — engine choice
- [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]] — vendor ID
- [[Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом]] — sitemap живой, products gated

## Артефакты на диске

- `.planning/spikes/01-goldapple/MEMO.md` — signed-off (12 sections, 355 lines)
- `.planning/spikes/01-goldapple/notebook.py` — Camoufox 100-fetch reproducible
- `.planning/spikes/01-goldapple/sample-payloads/tier2-camoufox-kz-results.json` — 99/100 evidence
- `.planning/spikes/01-goldapple/sample-payloads/tier2-camoufox-kz-log.txt` — structlog per-fetch
- `.planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html` — saved real-app HTML (microdata reference)
- `.planning/spikes/01-goldapple/sample-payloads/_debug-jsonld-blocks.json` — proof goldapple has only OfferShippingDetails
- `.planning/spikes/01-goldapple/_collect_urls.py` — URL harvester (reproducible)
- `.planning/phases/01-goldapple-reconnaissance-spike/01-08-SUMMARY.md`, `01-11-SUMMARY.md`, `01-12-SUMMARY.md` — plan summaries
- `.claude/skills/spike-01-goldapple/SKILL.md` — Phase 3 quick-reference

## Команда продолжения

```
/gsd-discuss-phase 2
```
