---
tags: [session, phase-3, phase-4, security-audit, discuss, plan, matcher, kpi]
date: 2026-05-11
session_type: secure + discuss + plan
phase: 04-matcher-match-rate-kpi
verdict: ready-for-execute
---

# 2026-05-11 — Phase 3 security re-audit + Phase 4 discuss и plan готовы

## Что произошло за сессию

Три команды подряд: `/gsd-secure-phase 3` → `/gsd-progress` → `/gsd-discuss-phase 4` → `/gsd-plan-phase 4`. Phase 3 теперь полностью закрыт (UAT + security), Phase 4 имеет 6 готовых к исполнению планов.

## Часть 1 — Phase 3 security re-audit (commit `94989bc`)

Triggered: plans 03-08 (brand-token bucket index) и 03-09 (Camoufox warm-up + smoke retry-once) shipped после оригинального 2026-05-06 audit без отдельных threat-моделей. Re-audit под `State A` (SECURITY.md exists, 35/35 closed).

`gsd-security-auditor` re-verified все 35 threats против current code:

- **Profile-dir cleanup invariant под warm-up** (T-03-04-07/-07b/-09): `__aexit__` finally runs unconditionally; warm-up `goto` failure best-effort (logged, не raised, не aborts boot). Регрессионные тесты `test_camoufox_boot_failure_cleans_profile_dir` + `test_warmup_goto_failure_does_not_abort_boot`.
- **Smoke gate strict semantics под retry-once** (T-03-05-01/-02): single outer `for` loop preserved; retry-once predicate `_is_loading_race` имеет 7 конъюнктивных условий включая `GATE_TITLE_MARKER` exclusion (CR-01 hardening commit `05b29a8`); D-312 ALL-must-succeed sustained.
- **Stats namespace под brand-bucket forwarding** (T-03-05-06): `compute_norm06_forward` signature changed, но `StatsNamespaceError` gating неизменно для obeих namespaces (`goldapple.*` и `viled.*`).
- **Log hygiene** (T-03-04-13): новые события `phase3_smoke_probe_retry` + `camoufox_warmup_networkidle_timeout` carry только non-PII metadata.
- **Supply-chain pin**: `pyproject.toml:15` `camoufox[geoip]==0.4.11` + `uv.lock` sha256 hashes unchanged.

Result: 35/35 still closed, frontmatter `verified: 2026-05-11`. Audit-trail добавил вторую row + 2026-05-11 Audit Notes section. **Никаких регрессий.**

## Часть 2 — Phase 4 discuss (commit `a16f0e1`)

`/gsd-discuss-phase 4`. CONTEXT.md not exists, no SPEC, no checkpoint, no plans. Загрузил полный prior context (Phase 2 + Phase 3 CONTEXT.md каскады).

Presented 4 phase-specific gray areas. **Все 4 выбраны для обсуждения**, все 4 recommended-варианты приняты:

1. **Matches table — denormalized + N→1 keep-all** (D-401/-402/-403): 13-колонная таблица с brand_norm/name_norm/volume_norm/обе цены/was_prices/delta/delta_pct/matched_at; PK `(run_id, viled_sku, goldapple_sku)`. Symmetric numerator-filter: `multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED'` на обе стороны. N→1 keep-all — не теряем commercial signal про варианты.
2. **Match-rate denominator — comparable viled SKU в брендах goldapple** (D-404): symmetric с numerator-фильтром гарантирует честность KPI; формула фиксируется с week 1 как исторический baseline. D-405 защищает её source-locked regression-canary fixture.
3. **Sanity-gate P — seed=20 + auto-suggest `0.7 × 4-week-median` после 4 runs** (D-406/-407/-408/-409): третий retailer-domain экземпляр паттерна D-201/D-308; никогда auto-tune — оператор PR-ит изменения. Gate-fail оставляет matches rows в БД (audit-trail invariant mirror D-218).
4. **Idempotency + failed-crawl + CLI** (D-410/-411/-412): DELETE-and-reinsert внутри одной `engine.begin()` транзакции; skip если любой retailer status='failed' OR 'in_progress' (не пишет zero-match row — сбило бы auto-suggest history); standalone `matcher-run --run-id N` subcommand + main_run integration.

Plus 3 structural decisions: D-413 module layout (`matcher/` + `runners/matcher_run.py`), D-414 stats namespace `match.*` (10 canonical keys frozen), D-415 no alembic.

## Часть 3 — Phase 4 plan (commit `fdbd229`)

`/gsd-plan-phase 4` без research (CONTEXT плотный, инфраструктура существует). Pattern-mapper → planner (opus) → plan-checker (sonnet).

**6 plans, 5 waves:**

| Wave | Plan | Что |
|---|---|---|
| 1 | 04-01 | Match SQLModel (13 col) + `[tool.ga_crawler.match]` pyproject + MatchConfig loader + skeleton |
| 1 | 04-02 | MATCH_STATS_KEYS 10-key tuple + MatchStatsBuilder + 3-way namespace disjoint invariant |
| 2 | 04-03 | `matcher/strict_key.py` — INSERT_MATCHES_SQL + DENOMINATOR_SQL с symmetric filters + **D-405 source-locked formula canary** |
| 3 | 04-04 | `runners/matcher_run.py` 7-step sync orchestrator (skip → DELETE+INSERT TX → patch_stats → gate → fail/finalize) |
| 4 | 04-05 | `main_run.py` matcher composition + CLI `matcher-run --run-id N` subcommand |
| 5 | 04-06 | Doc cascade — REQUIREMENTS.md MATCH-02 → 13-col schema, STATE.md D-405 freeze, ROADMAP plan list |

**Plan-checker result:** `## VERIFICATION PASSED` — 0 blockers, 1 WARNING (sanity-gate boundary `>` vs `>=` inherited from Phase 2/3 D-203 precedent — не блокирует), 5 INFO (deferred `NamespaceStatsBuilder` refactor per Claude's Discretion, tolerant log assertions, etc.). All 4 MATCH-* requirements covered; all 15 CONTEXT decisions covered.

**KPI freeze defended структурно** в 2 слоя:
1. 04-03 Test 14 `test_match_rate_formula_canary` — source-locks `INSERT_MATCHES_SQL` substring (`ROUND`, `*100.0/v.current_price`) + numeric fixture 6/5/3 → 60.0
2. 04-04 Test 10 `test_kpi_formula_end_to_end` reproduces через orchestrator

## State of play после сессии

- ROADMAP: phases 1-3 complete; Phase 4 planned, ready to execute; phases 5-7 untouched
- v1 requirements: 27/48 closed. После Phase 4 execution → 31/48 (добавятся MATCH-01..04)
- Open Warnings: те же 5 non-blocking из `03-REVIEW.md` (WR-01..05) + 1 новая WARN-1 для Phase 4 (gate boundary)
- Phase 7 ops-playbook backlog: 3 items неизменно
- Phase 4 plans committed at `fdbd229`; SECURITY.md re-audit at `94989bc`; CONTEXT at `a16f0e1`

## Что следующее

`/gsd-execute-phase 4` — pattern-mapper + planner + checker уже отработали; executor должен пройти 5 waves подряд. Ожидаемый объём изменений: 7 new files + 4 amended files + ~80 tests added.

## Connections

- [[Текущие приоритеты — Phase 4 plan ready, execute next]] — новый active priority note
- ~~[[Текущие приоритеты — Phase 3 closed окончательно, дальше Phase 4]]~~ — superseded
- [[Match-rate — KPI с первой недели]] — формула теперь locked, D-405 frozen
- [[Matches table — денормализованная, N→1 keep-all]] — новое решение
- [[Sanity-gate P — третий экземпляр паттерна auto-suggest 0.7×median]] — новое решение
- [[2026-05-11 — Phase 3 UAT Test 6 closed empirically, cold-start race fix validated на live KZ-laptop]] — предыдущая сессия
