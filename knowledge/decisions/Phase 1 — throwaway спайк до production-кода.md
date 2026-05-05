---
tags: [decision, process, risk-management, phase-1]
date: 2026-05-05
---

# Phase 1 — throwaway спайк до production-кода

Первая фаза не пишет production-инфраструктуру. Только notebook + decision memo + robots/ToS аудит.

## Почему

Anti-bot tier для goldapple — единственный риск, способный убить проект. Если выяснится, что нужен Tier 4 (managed unblocker — $0.5–2 за каждый product fetch), экономика проекта меняется. Архитектура тоже — придётся свести количество fetches к минимуму, агрессивно кэшировать.

**Сначала меряем, потом строим.**

## Что фаза производит

1. Notebook с 100 успешными последовательными product fetches на goldapple
2. Decision memo: tier (1/2/3/4), proxy provider, browser engine
3. viled.kz feasibility через `curl_cffi` (≥10 fetches)
4. Robots.txt + ToS аудит обоих сайтов
5. Page-volume estimate для типичного бренда на goldapple

## Что фаза НЕ производит

- Никакой структуры пакета
- Никакой БД-схемы
- Никаких CLI-команд
- Никаких тестов

Всё, что написано — throwaway. Production-код стартует с Phase 2.

## Tension reconciled

ARCHITECTURE говорил "viled первым" (потому что viled feeds goldapple brand list). PITFALLS говорил "goldapple первым" (потому что anti-bot — главный риск).

**Reconciliation:** маленький throwaway-спайк на goldapple → потом dependency-correct viled-first build. Спайк не инвертирует архитектуру, а валидирует осуществимость.

## Связанные

- [[Текущие приоритеты — Phase 1 спайк]]
- [[Goldapple anti-bot — определяющий риск проекта]]
- [[Тиры anti-bot эскалации]]
