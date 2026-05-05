---
tags: [priorities, current-focus, phase-1]
date: 2026-05-05
---

# Текущие приоритеты — Phase 1 спайк

**Сейчас:** Phase 1 контекст зафиксирован. Готов к `/gsd-plan-phase 1`.

## Что нужно сделать (по 16 решениям из CONTEXT.md)

1. Зарегистрировать **IPRoyal или Decodo** trial-аккаунт (заранее, до старта тестов)
2. Гонять **Patchright** (Tier 2) с **двух IP-гео** — laptop KZ + один proxy
3. Параллельно — **JSON-endpoint hunt** на goldapple: DevTools, sitemap.xml, `__NEXT_DATA__`
4. Notebook с **100 sequential goldapple fetches**, threshold **≥95/100** с JSON-LD как fetch-OK критерием
5. **viled feasibility** через `curl_cffi impersonate="chrome"` (≥10 product fetches + side-deliverables: timing, JSON-LD, pagination)
6. **Robots.txt + ToS** аудит обоих сайтов → `tos-audit.md`
7. **Page-volume estimate** через sitemap.xml + pagination meta
8. **Decision memo**: tier (0/1/2/3/4), proxy provider, browser engine, prod-IP-гео — подписан и закоммичен

**Артефакты:** `.planning/spikes/01-goldapple/MEMO.md` + `notebook.py` + `tos-audit.md`. Копия memo в `knowledge/decisions/` после `/gsd-spike --wrap-up`.

**Timebox:** 1 неделя. После — вердикт «Tier 4 / managed unblocker» если ничего ниже не сработало.

## Ключевые решения

- [[Tier 2 Patchright — стартовый tier для goldapple]] — скип Tier 1
- [[Multi-geo измерение в спайке — laptop KZ плюс один proxy]] — две метрики в memo
- [[JSON-endpoint hunt — явный deliverable Phase 1]] — может убрать browser tier совсем
- [[Спайковый fetch-OK = HTML 200 плюс product JSON-LD]] — ≥95/100 threshold

## Stop-rules в спайке

- **5 подряд блоков** (403/429) или первая Cloudflare interstitial / DataDome captcha → tier failed, эскалация
- **Persistent context (warm)** для Patchright, slow rate 3-5с между fetches
- **Auto-resolved challenges** = проход (но challenge-rate логируется как отдельная метрика)

## Почему именно так

См. [[Phase 1 — throwaway спайк до production-кода]] и [[Goldapple anti-bot — определяющий риск проекта]]. Anti-bot tier — единственный риск, способный убить проект; спайк построен ровно под этот де-рискинг.

## После завершения Phase 1

Переход к Phase 2: skeleton + viled crawl + storage. См. [[.planning/ROADMAP|ROADMAP.md]] для последующих фаз.

## Команда для запуска

```
/gsd-plan-phase 1
```

Контекст лежит в `.planning/phases/01-goldapple-reconnaissance-spike/01-CONTEXT.md`.
