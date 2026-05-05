---
tags: [priorities, current-focus, phase-3, planning]
date: 2026-05-06
---

# Текущие приоритеты — Phase 3 план

**Phase 3 (Goldapple Crawl) контекст зафиксирован 2026-05-06.** 13 implementation-решений D-301..D-313 залочены через `/gsd-discuss-phase 3`. Следующий шаг — `/gsd-plan-phase 3` для атомарной разбивки на plans.

→ Если работаешь над Phase 2 параллельно — см. (создаётся) `[[Текущие приоритеты — Phase 2 viled]]` через `/gsd-discuss-phase 2`. Phase 2 и Phase 3 data-independent, могут идти параллельно.

## Команда следующего шага

```
/gsd-plan-phase 3
```

## Что Phase 3 plan должен учесть

**Stack залочен спайком (не пересматривать):**
- Camoufox v135.0.1-beta.24 + KZ-laptop direct + no proxy
- selectolax + microdata `<meta itemprop="price">` (НЕ JSON-LD)
- 3-5с random uniform rate-limit, sequential, concurrency=1
- Hybrid enumeration: curl_cffi sitemap (Tier 0) + Camoufox product render (Tier 2)

**Implementation decisions из 03-CONTEXT.md (применять как hard constraints):**

| Категория | Decision | Где живёт |
|---|---|---|
| URL-pool | sitemap-only, full re-crawl, stale-SKU только в `runs.stats` | D-301..D-303 |
| Brand-alias | slug-эвристика bilingual exact-match, NORM-06 двусторонний с week-over-week NEW diff | D-304..D-307 |
| Sanity-gate | M=1000 static, run-to-completion, auto-suggest после 4 недель | D-308..D-310 |
| Camoufox | fresh profile per run, integrated smoke probe ПЕРЕД crawl, pin exact version | D-311..D-313 |

**Phase 2 dependency:**
- Phase 3 контрактует к Phase 2 модулям (`ga_crawler.alias.BrandAlias`, `ga_crawler.parsers.shared`, `ga_crawler.normalizers.*`, `ga_crawler.storage.SnapshotWriter`).
- Если planner запускается до Phase 2 ready — использовать mock-интерфейсы, real integration в финальной волне.

## Critical artifacts для planner

| Файл | Зачем |
|---|---|
| `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` | 13 решений, canonical refs, code_context, deferred ideas |
| `.planning/spikes/01-goldapple/MEMO.md` | Signed-off stack source-of-truth |
| `.claude/skills/spike-01-goldapple/SKILL.md` | Phase 3 quick-reference (auto-loaded) |
| `.planning/spikes/01-goldapple/notebook.py` | Camoufox 100-fetch reference (refactor source) |
| `.planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html` | Real PDP HTML для парсер-калибровки |

## Open questions для plan-фазы

- Конкретное место config-файла (`pyproject.toml [tool.ga_crawler.crawl.goldapple]` vs dedicated `config/sanity.toml` vs `.env`) — decided default: `pyproject.toml`, planner подтверждает.
- Точные ключи `runs.stats` JSON-блока (`stale_count`, `unmatched_viled_brands`, `unmatched_goldapple_slugs_new`, `gate_shell_count`, `smoke_pass`).
- Cleanup strategy on FAIL (always-delete vs preserve last failure для forensics).

## Не теряем (Phase 7 backlog, унаследовано)

- Camoufox+EU smoke fetch перед locking Hetzner — если регрессия → revive D-08 (IPRoyal KZ ~$2/week)
- KZ-legal review (30 min с юристом) с bundle = `tos-audit.md` + `viled-privacy.txt` + robots snapshots + GroupIB vendor flag
- Camoufox upstream maintenance (daijro vs coryking fork) — switch-ready backup

## Связанные

- [[Slug-эвристика для viled→goldapple, не explicit YAML]] — D-304/305
- [[Sanity-gate M=1000 static с auto-suggest, не auto-tune]] — D-308/310
- [[Fresh Camoufox profile per run + integrated smoke probe]] — D-311/312
- [[Sitemap-only URL pool для goldapple, без brand-facet rendering]] — D-301
- [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]] — stack source
- [[2026-05-06 — Phase 3 контекст зафиксирован]] — discuss-сессия
- ~~[[Текущие приоритеты — Phase 1 спайк]]~~ — closed, audit trail
