---
tags: [priorities, current-focus, phase-3, execute]
date: 2026-05-06
---

# Текущие приоритеты — Phase 3 execute

**Phase 3 (Goldapple Crawl) plan создан 2026-05-06.** 7 plans / 7 waves / ~5,150 строк plan-text. Verification passed на первой итерации. Следующий шаг — `/gsd-execute-phase 3` после `/clear`.

→ Phase 2 (viled) ещё не запланирована. Phase 3 plan параллельный — Wave 0 строит `interfaces.py` Protocol контракты для Phase 2 модулей, Wave 5 orchestrator потребляет через них. Когда Phase 2 ship-нется, заменить stubs на real imports.

## Команда следующего шага

```
/clear
/gsd-execute-phase 3
```

## Wave-структура (план)

| Wave | Plan | Что строит |
|---|---|---|
| 0 | 03-01 | bootstrap: deps pin, interfaces.py Protocols, fixtures, conftest |
| 1 | 03-02 | sitemap + bilingual slug-fy + brand intersection + NORM-06 reverse |
| 2 | 03-03 | microdata parser (priceType discrimination) + state classifier |
| 3 | 03-04 | Camoufox fetcher (fresh tmp profile) + tenacity retry + per-SKU isolation |
| 4 | 03-05 | smoke probe + M-gate + auto-suggest + runs.stats namespace + NORM-06 forward |
| 5 | 03-06 | orchestrator + CLI через Phase 2 Protocols |
| 6 | 03-07 | **manual checkpoint** — 1h live smoke на KZ-laptop |

## Что execute должен учесть

**Stack залочен спайком + planом (не пересматривать):**
- Camoufox v135.0.1-beta.24 exact pin в `uv.lock`
- selectolax + microdata `<meta itemprop="price">`
- 3-5с random uniform, sequential, concurrency=1
- Hybrid enumeration: curl_cffi sitemap + Camoufox PDP

**Implementation decisions из 03-CONTEXT.md (D-301..D-313) — все 13 уже backed конкретными tasks в plans:**

| Категория | Decisions | Где в плане |
|---|---|---|
| URL-pool | D-301..D-303 | 03-02 (sitemap + stale-SKU) |
| Brand-alias | D-304..D-307 | 03-02 (slug-fy) + 03-05 (NORM-06) |
| Sanity-gate | D-308..D-310 | 03-05 (M-gate + auto-suggest) |
| Camoufox | D-311..D-313 | 03-01 (pin) + 03-04 (fresh profile) + 03-05 (smoke) |

**Phase 2 dependency:**
- Phase 3 контрактует к Phase 2 модулям через `src/ga_crawler/interfaces.py` Protocols (Wave 0 deliverable).
- Wave 5 orchestrator импортирует только через Protocol типы — никаких concrete imports `ga_crawler.parsers.shared` etc.
- Когда Phase 2 ship-нется — заменить stubs в `cli.py` на real Phase 2 imports + добавить `tests/integration/test_run_e2e_with_phase2_real.py`.

## Critical artifacts

| Файл | Зачем |
|---|---|
| `.planning/phases/03-goldapple-crawl/03-{01..07}-PLAN.md` | 7 plan files (commit `c1b1929`) |
| `.planning/phases/03-goldapple-crawl/03-RESEARCH.md` | Domain research, validation architecture, threat model |
| `.planning/phases/03-goldapple-crawl/03-VALIDATION.md` | Nyquist sampling, per-task verification map |
| `.planning/phases/03-goldapple-crawl/03-PATTERNS.md` | File analogs, code excerpts (notebook.py line ranges) |
| `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` | 13 D-NN decisions (locked) |
| `.planning/spikes/01-goldapple/notebook.py` | Camoufox bootstrap + microdata reference impl |

## Open questions для execute

- Wave 6 (Plan 07) — operator checklist на 1-hour live smoke. Можно отложить до первой "production-ready" недели или прогнать сейчас на сэмпле URL? — operator decision.
- Phase 2 timing — если Phase 2 ship-нется до Phase 3 Wave 5, ускоряем real-integration; иначе stubs остаются в финальной волне.

## Не теряем (Phase 7 backlog, унаследовано)

- Camoufox+EU smoke fetch перед locking Hetzner — если регрессия → revive D-08 (IPRoyal KZ ~$2/week)
- KZ-legal review (30 min с юристом) с bundle = `tos-audit.md` + `viled-privacy.txt` + robots snapshots + GroupIB vendor flag
- Camoufox upstream maintenance (daijro vs coryking fork) — switch-ready backup

## Связанные

- [[2026-05-06 — Phase 3 план создан, 7 plans across 7 waves]] — текущая plan-сессия
- [[2026-05-06 — Phase 3 контекст зафиксирован]] — предшествующая discuss-сессия
- [[Sitemap-only URL pool для goldapple, без brand-facet rendering]] — D-301
- [[Slug-эвристика для viled→goldapple, не explicit YAML]] — D-304/305
- [[Sanity-gate M=1000 static с auto-suggest, не auto-tune]] — D-308/310
- [[Fresh Camoufox profile per run + integrated smoke probe]] — D-311/312
- [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]] — stack source-of-truth
