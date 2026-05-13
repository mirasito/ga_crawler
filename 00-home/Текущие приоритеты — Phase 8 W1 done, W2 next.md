---
tags: [priorities, v1-1-active, phase-8, wave-1-done, wave-2-next, hotfix-shipped]
date: 2026-05-14
status: phase-8-w1-done-w2-pending
current_phase: 8
next_command: /gsd-execute-phase 8 --wave 2
---

# Текущие приоритеты — Phase 8 W1 done, W2 next

**Wave 1 GREEN shipped 2026-05-14** + **quick-task hotfix 43dbfd7 закрыл active data egress** (test_cli_deliver subprocess тесты неявно отсылали fake-xlsx в operator's личный Telegram через .env re-load — 11+ deliveries confirmed). Suite зелёный **825/0-failed** (было 822/2-failed). Готов W2.

## Что готово

- ✅ **W0 (Plan 08-01)** — 30-PDP shape-sampling spike + 3 fixtures + project-local skill (закрыт 2026-05-13)
- ✅ **W1 (Plans 08-02 + 08-04)** — оба parser fixes shipped 2026-05-14
  - `feat(08-04) cc40621`: viled `_extract_volume_from_nextdata` (line 114)
  - `chore(08-02) f8fa492`: selectolax 0.4.8 bump
  - `feat(08-02) cf247b3`: goldapple `_extract_volume_block` (line 270) — lowercase селектор + ancestor-walk strategy (2 deviations from PATTERNS.md, see [[Goldapple PDP renders volume в structured flexbox blok, не в microdata]])
  - `docs(08) 049999b`: W1 SUMMARY-файлы
- ✅ **Quick-task `20260514-cli-dotenv-leak`** — hotfix 43dbfd7 закрыл data egress; canary regression test prevents reintroduction
- ✅ Post-mortem + STATE.md mislabel correction committed (a9c2292)

## Что осталось

| Wave | Plan | Files | Status |
|---|---|---|---|
| **2** | 08-03 (PARSE-FIX-02) | `goldapple_microdata.py` (brand+name через **h1-spans pivot** per W0 SKILL.md) | ⏸ ready — execute next |
| **3** | 08-05 (PARSE-FIX-04 + 05 + doc cascade) | `gates.py`, `stats.py`, 3 tests, 4 doc files | ⏸ ready (depends W2) |

## Plan 08-03 critical handoff

Plan 08-03 PLAN.md **still describes microdata premise** (читать brand+name через `<meta itemprop="name">`) — этот premise **invalidated W0 spike** (0/30 PDPs carry product-level itemprop="name"; они только в breadcrumb + Organization metadata + review-author).

**Executor MUST read** `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` перед coding. Pivot:

- Brand selector: `h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__brand_"]` — read `[content]` attr OR text
- Name selector: `h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__name_"]` — read text
- CSS hash suffix (`_1yrfv_339`) is build-specific — always substring-match (`class*=`)
- `_strip_brand_prefix` fallback **NOT NEEDED** — 28/30 PDPs clean
- D-816 invariant canary `brand.lower() not in name.lower()` — **soften** to log-warn (NOT fail-hard), 2/30 legitimately fail

CONTEXT.md "Claude's Discretion" блок explicitly allows downstream adaptation на основе W0 evidence.

## Doc cascade pending в W3

W3 (Plan 08-05) doc cascade должен добавить **3 hazards** из quick-task hotfix:
1. `load_dotenv()` без явного path walks от `__file__` — use `find_dotenv(usecwd=True)`. См. [[find_dotenv usecwd=True — anchor dotenv discovery at cwd для test isolation]]
2. "Pre-existing failures" annotation pattern — code smell без written root-cause. См. [[«Pre-existing failures» annotation pattern — code smell, не closure]]
3. `.env` с реальными credentials + subprocess tests = contamination hazard

## Next command

```
/gsd-execute-phase 8 --wave 2
```

Это запустит W2 (Plan 08-03 — h1-spans pivot per SKILL.md) → automatically продолжит к W3 (Plan 08-05 doc cascade) → phase verification + STATE.md close.

**Ожидаемое wall-clock:** ~20-25 min для W2+W3 (W2 ~10 min single-plan; W3 ~10-15 min doc cascade + 2 test files).

## Verification gate после Phase 8 ship

1. Live dry-run yields `goldapple_comparable_count > 0` (was 0 in run #13)
2. `goldapple_volume_norm` non-null rate ≥90% на не-volumeless категориях — **W1 W1 closure already PASSES** local 3-fixture round-trip (givenchy + stereotype + armani all yield non-null)
3. Invariant canary `brand.lower() not in name.lower()` — log-warn (NOT fail-hard) per W0 finding
4. Tests green ≥825 (current 825/0; W2 adds ~5-10 tests; W3 doc cascade may not add tests)
5. Null-rate gate (`parser_drift_null_volume_rate`) actively fails synthetic regression run per Plan 08-05 Success Criteria #5

## Что дальше после Phase 8

- **Phase 9** — Live-HTML Harness (TEST-HARNESS-01..06) — locks Phase 8 fix retroactively
- **Phase 10** — Audit Paperwork Carryover (AUDIT-DEBT-01..05) — parallel-safe с Phase 8/9
- **Phase 11** — Operator Deploy на Yandex Cloud kz1 (DEPLOY-01..08) — calendar-bound

## Related

- [[2026-05-14 — Phase 8 W1 GREEN shipped + cli.py dotenv-leak hotfix closes data egress]] (текущая сессия)
- ~~[[Текущие приоритеты — Phase 8 W0 done, Wave 1-3 next]]~~ — superseded 2026-05-14 (W1 done + hotfix shipped)
- [[fake-xlsx в личный Telegram — load_dotenv walks от file, не cwd]] (debugging — hotfix incident)
- [[find_dotenv usecwd=True — anchor dotenv discovery at cwd для test isolation]] (decision — hotfix approach)
- [[«Pre-existing failures» annotation pattern — code smell, не closure]] (decision — process lesson)
- [[Goldapple brand+name extraction — h1 spans CSS class substring, не itemprop microdata]] (W2 strategy)
- [[Goldapple PDP renders volume в structured flexbox blok, не в microdata]] (W1 Plan 08-02 strategy — refined этой сессией)
- [[viled Размер JSON path — nested attributes 0 attributes, не item attributes]] (W1 Plan 08-04 strategy)
- `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` — system-discoverable spike output (load-bearing for W2)
- `.planning/phases/08-parser-bug-fixes/08-02-SUMMARY.md` — Plan 08-02 W1 closure
- `.planning/phases/08-parser-bug-fixes/08-04-SUMMARY.md` — Plan 08-04 W1 closure
- `.planning/quick/20260514-cli-dotenv-leak/SUMMARY.md` — hotfix post-mortem

---

**Bottom line:** W1 закрыт (oба parser fixes shipped, 825 tests pass) + **active data-egress канал найден и пофикшен** (11+ fake-xlsx files в operator's Telegram — только test fixture bytes, customer data НЕ утекло). W2 (Plan 08-03 h1-spans pivot) ready — executor MUST read SKILL.md.
