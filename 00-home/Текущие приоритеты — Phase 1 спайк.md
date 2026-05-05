---
tags: [priorities, current-focus, phase-1]
date: 2026-05-05
---

# Текущие приоритеты — Phase 1 спайк

**Сейчас:** Phase 1 — Goldapple Reconnaissance Spike. Никакого production-кода до завершения этой фазы.

## Что нужно сделать

1. Эмпирически определить anti-bot tier для goldapple.kz (1/2/3/4)
2. Подобрать резидентного провайдера прокси (или подтвердить, что прокси не нужны)
3. Проверить feasibility viled.kz через `curl_cffi` (без headless)
4. Документировать robots.txt и ToS обоих сайтов
5. Оценить объём страниц у типичного бренда на goldapple

**Артефакт:** decision memo + reproducible notebook (100 успешных фетчей подряд) + robots/ToS аудит.
**Код throwaway** — не строим production-инфраструктуру здесь.

## Почему именно так

Anti-bot — единственный риск, который может убить проект. См. [[Phase 1 — throwaway спайк до production-кода]] и [[Goldapple anti-bot — определяющий риск проекта]].

Если выйдет Tier 4 (managed unblocker), экономика проекта меняется до того, как написана архитектура.

## После завершения Phase 1

Переход к Phase 2: skeleton + viled crawl + storage. См. [[.planning/ROADMAP|ROADMAP.md]] для последующих фаз.

## Команда для запуска

```
/gsd-discuss-phase 1
```

Или сразу `/gsd-plan-phase 1`, если контекст спайка ясен.
