# State: GA Crawler

**Last updated:** 2026-05-05
**Mode:** Phase 1 executing — Wave 0 partial (01-01, 01-02 done; 01-03 IPRoyal **deferred** до результата 01-08), Wave 1 in progress (01-04 ✓, next 01-05 sitemap → 01-07 viled → 01-06 DevTools человек)

## Project Reference

**Core value:** Команда viled.kz один раз в неделю получает детализированный, сопоставленный по позициям отчёт о ценах конкурента (goldapple.kz) и может корректировать собственное ценообразование, видеть ассортиментные разрывы и отслеживать чужие промо-акции.

**Current focus:** Phase 1 executing — Wave 0 партиал, 01-03 IPRoyal **отложен** (user decision: проверим Tier 2 с KZ-лэптопа, если ≥98/100 + challenge<10% — прокси не нужен; иначе вернёмся к 01-03 после 01-08). Wave 1 идёт: 01-04 (robots/ToS audit) завершён — committed rate-limits зафиксированы (viled=2s, goldapple=3-5s random uniform), sitemap URLs переданы в 01-05, **goldapple anti-bot подтверждён глобальным** (все HTML-routes под JS-challenge'ем).

## Current Position

| Field | Value |
|-------|-------|
| Phase | 1 — Goldapple Reconnaissance Spike |
| Plan | 3/12 complete (`01-01` ✓, `01-02` ✓, `01-04` ✓), 1 deferred (`01-03` IPRoyal — revisit gate at 01-08) |
| Status | Executing Wave 1 — next plan 01-05 (sitemap.xml + page-volume estimate) |
| Progress | `[░░░░░░░░░░░░░░░░░░░░] 0/7 phases` (Phase 1: 3/12 plans executed, 1 deferred) |
| Branch strategy | none (single-trunk) |
| Resume file | `.planning/phases/01-goldapple-reconnaissance-spike/01-05-PLAN.md` |

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases planned | 7 |
| Phases completed | 0 |
| v1 requirements mapped | 48/48 |
| v1 requirements completed | 1/48 (RECON-04) |
| Plans created | 12 (Phase 1) |
| Plans completed | 3 |
| Spawned agents (this session) | roadmapper, gsd-planner, gsd-plan-checker, gsd-executor |
| Checkpoints | 0 |

### Plan Execution Metrics

| Plan | Duration | Tasks | Files | Date |
|------|----------|-------|-------|------|
| 01-01 (spike skeleton) | ~3 min | 3/3 | 7 created | 2026-05-05 |
| 01-02 (uv init + spike deps) | ~5 min | 3/3 | 4 created | 2026-05-05 |
| 01-04 (robots/ToS audit) | ~38 min | 2/2 | 9 created, 1 modified | 2026-05-05 |

## Accumulated Context

### Key Decisions

| Decision | Source | Constraint Imposed |
|----------|--------|--------------------|
| Strict-key matching only on v1 (`brand_norm + name_norm + volume_norm`) | PROJECT.md | Forces brand-alias YAML as v1 deliverable in Phase 2; defers fuzzy matching to v2 |
| Append-only snapshot history keyed by `run_id` | research/ARCHITECTURE.md | No in-place updates; Phase 2 schema is final from week 1 |
| `was_price` and stock-state enum captured in v1 schema | research/SUMMARY.md | Avoids retroactive backfill; prevents v1.x re-crawl |
| Match-rate as a tracked KPI from week 1 | research/SUMMARY.md | Phase 4 must log/store match-rate to establish historical baseline |
| Reporter is independent of delivery (file on disk first, Telegram wraps it) | research/ARCHITECTURE.md | Phase 5 produces archive without Telegram; Phase 6 is a thin wrapper |
| Two Telegram chats (ops vs business) | research/PITFALLS.md | Pre-send sanity-gate (Phase 4 + Phase 6) prevents broken reports reaching pricing team |
| Goldapple anti-bot tier decided empirically before any production code | research/SUMMARY.md | Phase 1 is throwaway spike; Phase 3 stack waits on its decision memo |
| SQLite + WAL on v1; Postgres only if SQLite hits limits | research/STACK.md | Single-writer batch fit; defers infra complexity |
| System cron with `CRON_TZ=Asia/Almaty`; no APScheduler/Celery/Prefect | research/STACK.md | Phase 7 minimum; one weekly job |
| Backend-only — no UI / dashboard / API | PROJECT.md (Out of Scope) | All phases `UI hint: no` |
| viled.kz committed rate-limit = 2s sequential | plan 01-04 (RECON-04) | Phase 2 viled crawler config constant; courtesy-only (no Crawl-delay, no anti-scraping clauses in Privacy Policy) |
| goldapple.kz committed rate-limit = 3-5s random uniform, concurrency=1 | plan 01-04 + D-04 + Pitfall 13 | Phase 3 goldapple crawler config; starting point for 01-08 experiment, validated/adjusted there |
| Stealth UA strategy for goldapple (NOT honest UA) | plan 01-04 — robots.txt blocks SemrushBot/MJ12bot/BLEXBot/DotBot | Phase 3 fetch layer uses curl_cffi/Patchright realistic-browser impersonation; no `ViledPriceMonitor/1.0`-style self-identification |
| goldapple anti-bot is GLOBAL (every HTML route gated, not just product pages) | plan 01-04 empirical — 11 ToS-slug candidates all return identical 18 912-byte JS-challenge shell | Strengthens D-01 (start at Tier 2 / Patchright); vanilla Playwright will likely fail too; goldapple ToS text deferred to post-01-08 warm Patchright re-fetch |
| `/rest/` Magento API is robots-Disallowed on goldapple | plan 01-04 (robots.txt §Rest API block) | plan 01-06 JSON-endpoint hunt must avoid `/rest/`; focus on `__NEXT_DATA__`/JSON-LD/non-`/rest/` ajax routes |

### Active Todos

(none — awaiting Phase 1 plan)

### Active Blockers

(none)

## Session Continuity

### What Was Just Done

- `/gsd-execute-phase 1` plan 01-04 executed (sequential mode, autonomous, 2 tasks):
  - Task 1 (snapshot robots.txt): viled (508 B HTTP 200, no Crawl-delay, sitemap declared) + goldapple (7303 B HTTP 200, Magento-style, no Crawl-delay, blocks 38 bots incl. SemrushBot/MJ12bot/BLEXBot/DotBot, sitemap declared) — commit `198f579`
  - Task 2 (ToS audit + committed rate-limits): viled `/privacy` extracted via Next.js `__NEXT_DATA__` (16066 chars, **no anti-scraping clauses**, only KZ Law 94-V personal-data); goldapple — all 11 ToS-slug candidates return identical 18 912-byte JS-challenge shell ("Gold Apple — checking device", DataDome-style UUID JS bundle), text deferred to post-01-08 — commit `83c5150`
  - Committed rate-limits: viled=2s sequential, goldapple=3-5s random uniform concurrency=1
  - 9 files created (4 helper scripts + 5 sample payloads), 1 modified (`tos-audit.md`), 3 deviations (all artifact-hygiene cleanups, zero scope creep), self-check PASSED
  - SUMMARY → `.planning/phases/01-goldapple-reconnaissance-spike/01-04-SUMMARY.md`
- Earlier (this session): plan 01-02 → 4 файла, 2 коммита (`d47b800`, `0b98407`); plan 01-01 (spike skeleton) → 7 файлов, 3 коммита (c2da755, 02e8cf5, 8a2d5c5)
- Earlier (planning): `/gsd-plan-phase 1` создал 12 атомарных плана (01-01..01-12) в 5 волнах; gsd-plan-checker VERIFICATION PASSED

### Earlier (this session)

- Phase 1 discuss session: 4 gray areas обсуждены (Tier escalation & timebox, IP-гео, JSON-endpoint hunt, success criteria)
- Locked-in 16 implementation decisions (D-01..D-16) для recon-спайка
- Создан `.planning/phases/01-goldapple-reconnaissance-spike/01-CONTEXT.md` с canonical refs на research/* и project docs
- Создан `.planning/phases/01-goldapple-reconnaissance-spike/01-DISCUSSION-LOG.md` (audit trail)

### Earlier (initialization)

- Read PROJECT.md and REQUIREMENTS.md
- Read research/SUMMARY.md, STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md
- Derived 7-phase roadmap aligned with research synthesis (Phase 1 spike, viled-first build, goldapple-second, matcher, reporter, delivery, scheduler)
- Mapped all 48 enumerated v1 requirements to phases (no orphans, no duplicates)
- Wrote ROADMAP.md with phase details and success criteria
- Updated REQUIREMENTS.md traceability section

### What's Next

1. Continue Phase 1 Wave 1 — plan 01-05 (sitemap.xml + page-volume estimate for 3-5 brands; consume sitemap URLs delivered by 01-04). Then 01-07 (viled curl_cffi) → 01-06 (DevTools JSON-endpoint hunt с человеком).
2. Wave 2 (Patchright Tier-2 100-fetch): 01-08 KZ-laptop (apply committed rate-limit 3-5s random uniform from 01-04; pre-flight verify sitemap.xml plain delivery), 01-09 EU-proxy. Conditional Wave 3 (01-10 Tier 3 escalation if fails). Wave 4 (01-11 MEMO finalize, 01-12 wrap-up).
3. Spike outcome (decision memo `.planning/spikes/01-goldapple/MEMO.md`) feeds Phase 3 stack selection. MEMO must reference 01-04 audit summary + committed rate-limits as Phase 3 config constants.
4. Open follow-ups (Phase 7): KZ-legal review with bundle = `tos-audit.md` + `viled-privacy.txt` + both `*-robots.txt` snapshots + flag «goldapple ToS not obtainable in spike».

### Resume Instructions

To continue this project from a fresh session:
1. Read `.planning/PROJECT.md` for core value and constraints.
2. Read `.planning/ROADMAP.md` for phase structure.
3. Read this STATE.md for current position.
4. Run `/gsd-execute-phase 1` to continue Phase 1 execution from plan 01-05.

---
*State initialized: 2026-05-05 by gsd-roadmapper; updated by gsd-plan-phase 2026-05-05; updated by gsd-executor (plan 01-01) 2026-05-05; updated by gsd-executor (plan 01-02) 2026-05-05; updated by gsd-executor (plan 01-04) 2026-05-05*
