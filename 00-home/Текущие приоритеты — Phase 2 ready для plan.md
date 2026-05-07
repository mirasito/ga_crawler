---
tags: [priorities, phase-2, ready-for-plan, next-up]
date: 2026-05-07
---

# Текущие приоритеты — Phase 2 ready для plan

## Где мы

**Phase 3 closed cleanly через 4 audit gates 2026-05-07:**
- UAT: 8/9 pass + 1 blocked deferred (1-hour live run → first prod weekly cron)
- Security: 35/35 threats closed (29 mitigate + 5 accept + 1 inherited)
- Validation: nyquist_compliant, 192/192 tests, 18 test files, 0 gaps

**Phase 2 контекст готов** — `/gsd-discuss-phase 2` дал 27 decisions (D-201..D-227). 4 areas обсудили (sanity-N + brand-alias YAML + NORM-06 review queue + stub cutover), всё recommended-defaults.

**Mid-flight scope clarification 2026-05-07:** viled crawl ограничен `/men/catalog/1310` + `/women/catalog/1310` — beauty+парфюм only, не весь luxury каталог. Каскадные правки D-201 (N=20000→100) + D-223..D-227 (catalog-page enumeration вместо sitemap-only).

## Что дальше

```
/clear
/gsd-plan-phase 2
```

Recommend `--skip-research` потому что research уже зрелая (Phase 1 spike validated curl_cffi + `__NEXT_DATA__` strategy + 2s rate-limit; Phase 3 froze interfaces.py Protocols + pyproject deps + test framework).

### Wave 0 Phase 2 must-do

1. **Probe `/men/catalog/1310` + `/women/catalog/1310`** — verify enumeration mechanism. Order приоритета:
   - `__NEXT_DATA__` `pageProps.products[]` + `totalCount` + `pageSize` (most likely)
   - HTML pagination fallback
   - `_next/data/{buildId}/men/catalog/1310.json` optimization
2. **Extract URL pool size** — confirm/refine seed N=100 в `pyproject.toml`
3. **Pin `pyproject.toml [tool.ga_crawler.crawl.viled]`** keys: `catalog_urls`, `pause_seconds=2.0`, `sanity_gate_n=100`, `concurrency=1`
4. **Verify `__NEXT_DATA__` shape** против `viled-nextdata-shape.json` для PARSE-06 stock-state mapping (D-217: in_stock boolean → IN_STOCK/OUT_OF_STOCK; HTTP 404 → DELISTED; etc.)
5. **Seed `config/brand-aliases.yaml`** — top-50 viled beauty brands из catalog/1310 probe + manual RU/EN варианты для брендов с явным кириллическим написанием

### Phase 2 deliverables (high-level, planner детализирует)

- `src/ga_crawler/fetchers/viled.py` (curl_cffi Tier 0 + tenacity retry)
- `src/ga_crawler/parsers/viled_nextdata.py` (`__NEXT_DATA__` extraction)
- `src/ga_crawler/enumeration/viled_sitemap.py` (catalog-page pagination, NOT sitemap)
- `src/ga_crawler/runners/viled_run.py` (orchestrator)
- `src/ga_crawler/normalizers/{brand,name,volume}.py` (NORM-02..05 layered approach)
- `src/ga_crawler/alias/yaml_loader.py` (`YamlBrandAlias(BrandAliasProtocol)`)
- `src/ga_crawler/storage/sqlite.py` (Run + Snapshot SQLModel + raw json_patch helpers)
- `src/ga_crawler/runner/norm06_writer.py` (markdown ledger writer)
- `config/brand-aliases.yaml` (NEW)
- `bin/backup.sh` (online sqlite3 .backup + 4-rotate)
- `tests/unit/{viled,storage,normalizers,alias,...}_*.py` (estimate +30-50 tests)
- `tests/integration/test_viled_e2e_with_phase3_unblocked.py`
- Delete Stub* classes from `src/ga_crawler/cli.py`

Phase 3 cli.py получает real impls вместо stubs → 192/192 tests должны остаться green + добавляются Phase 2 tests.

## Что НЕ делать сейчас

- **Не запускать `/gsd-execute-phase 3` снова** — closed (UAT/Security/Validation все green).
- **Не делать 1-hour live run goldapple вручную** — anti-bot transient cooldown не позволит без долгих пауз; deferred Phase 7 cron deploy.
- **Не править D-305** — locked в текущей формулировке (longest-prefix-in-whitelist Wave 7).
- **Не парсить весь viled sitemap** — scope narrowed до catalog/1310 endpoints (D-223).
- **Не реализовывать `--dev-stubs` flag** — runtime divergence dev↔prod = risk (D-212).
- **Не добавлять alembic** — skip-on-day-1 per CLAUDE.md (D-220); add при первой schema migration.

## Open action items для propagation

Эти изменения должны попасть в other docs at next phase transition или planner Wave 0:

- **`.planning/REQUIREMENTS.md` CRAWL-01**: amend "Краулер обходит весь каталог viled.kz" → "Краулер обходит beauty+парфюмерия каталог viled.kz (`/men/catalog/1310` + `/women/catalog/1310`, через пагинацию)"
- **`.planning/PROJECT.md` v1 active list**: similar amendment
- **`.planning/STATE.md` accumulated decisions**: row "Phase 2 scope narrowed (2026-05-07): viled = beauty+parfumery only..."

## Side-quest напоминание

`docs/viled-anti-bot-recommendations.html` (38 KB) — bonus-документ для viled-команды; ещё не committed. Если хочется — `git add docs/ && git commit`. Не блокирует Phase 2.

## Connections

- [[2026-05-07 — Phase 3 audit-stack закрыт + Phase 2 контекст с scope-narrowing]] — последний session note
- [[viled scope сужен до beauty+парфюм каталога catalog 1310]] — главное design-decision для Phase 2 (NEW)
- ~~[[Текущие приоритеты — Phase 3 done, дальше Phase 2 или Phase 4]]~~ — superseded (выбран Phase 2 path)
- [[.planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT|02-CONTEXT.md]] — full discuss output
- [[.planning/PROJECT|PROJECT.md]] · [[.planning/ROADMAP|ROADMAP.md]] · [[.planning/STATE|STATE.md]]
