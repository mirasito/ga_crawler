---
tags: [home, priorities, phase-11, deploy, v1.1]
date: 2026-05-15
status: active
---

# Текущие приоритеты — Phase 10 done + viled pagination unlocked, Phase 11 deploy next

## Сейчас в голове

**Phase 10 (Audit Paperwork Carryover) — COMPLETE 2026-05-14:**
- 5/5 AUDIT-DEBT reqs Closed
- v1.0 milestone audit verdict: `tech_debt` → **clean**
- 4 SECURITY.md + 1 VALIDATION.md retroactively shipped
- RECON-01 traceability annotation written

**Production reality-check session 2026-05-15:**
- 4 critical bugs found+fixed (commit `fe03f9d`): volume_norm Python repr, _cmd_weekly missing dotenv, viled empty-string handling, goldapple field-name typo
- viled pagination breakthrough: `/api/viled-catalog/v2/items/content` endpoint найден через Camoufox network intercept
- `bin/viled_fast_crawl.py` shipped — 7,600-PDP 4-hour crawl → 127-API-page **2:54 sec** walk
- Run #18 ran full viled catalog (**6,019 items**) + goldapple brand-filtered (**207 items**) + matcher (brand_overlap **18**, denominator **1,774**, **match_count=0**)
- xlsx ушёл в ops-chat (`message_id 32`) + business-chat (через integrated delivery — известное routing-ограничение)

## Что дальше

**Phase 11 — Operator Deploy на Yandex Cloud kz1 (DEPLOY-01..08)** — пока **PENDING**

Phase 11 mandate:
1. Yandex Cloud kz1 VPS provisioned (Ubuntu 24.04, 2vCPU/4GB/30GB, KZ-region IP)
2. `bin/setup-vps.sh` — idempotent thin wrapper над README §2 шагами
3. `load_dotenv(verbose=True)` в `__main__.py` entrypoint (DEPLOY-03 — закрывает D-705 raz и navsegda)
4. `sudo timedatectl set-timezone Asia/Almaty` (DEPLOY-04)
5. Camoufox×Yandex smoke (DEPLOY-05)
6. KZ-egress smoke (DEPLOY-06)
7. First Sunday cron tick → real Excel в business chat (DEPLOY-07)
8. /gsd-verify-work 7 resume — unblock 4 Phase 7 UAT items

## Что параллельно нужно (v1.2/v2 backlog)

| Приоритет | Item | Why |
|---|---|---|
| HIGH | **Fuzzy-match Stage 2** (rapidfuzz token_set_ratio) | 1,774 candidate pairs дают **0 matches** через strict-key — основной KPI продукта (price delta) сегодня не работает. См. [[Strict-key matcher даёт 0 matches на real fashion data — fuzzy v2 нужен]] |
| MEDIUM | viled-fast-API в production weekly-run | сейчас standalone `bin/viled_fast_crawl.py` — operator opt-in; integration требует CRAWL-01..06 contract review |
| MEDIUM | Phase 9 D-903 schema_rejected_rate_gate wire-up | gate существует но not invoked from runners — schema rejections silent в production |
| LOW | Stale test name fix | `test_readme_has_exactly_10_h2_sections` asserts `== 11` (Phase 9 cosmetic) |
| LOW | Windows Unicode subprocess test (cp1252 em-dash) | pre-existing baseline 7d42f77, не блокер |

## v1.1 milestone progress

- Phase 8 Parser Bug Fixes: **Complete 2026-05-13** (5/5 PARSE-FIX reqs)
- Phase 9 Live-HTML Harness: **Complete 2026-05-14** (6/6 TEST-HARNESS reqs)
- Phase 10 Audit Paperwork Carryover: **Complete 2026-05-14** (5/5 AUDIT-DEBT reqs)
- Phase 11 Operator Deploy: **Pending** (0/8 DEPLOY reqs)

Coverage: **16/24 v1.1 reqs Complete; 8/24 Pending (Phase 11)**.

## Открытые треки

1. **strict-key vs fuzzy ADR**: v1 explicit избрал precision over recall — но real fashion data даёт 0 matches. ADR требуется чтобы зафиксировать когда v2 fuzzy ship'нется.
2. **delivery routing override**: integrated `weekly-run` всегда отправляет в business chat на success (нет CLI flag). Ad-hoc operator runs утекают данные в команду. Phase 11 backlog: `--delivery-target ops|business` flag.
3. **v1.0 milestone — clean audit verdict** позволяет /gsd-complete-milestone v1 если нужно (но v1.1 в работе так что подождём v1.1 close).

## Session trail

- [[2026-05-15 — Phase 10 closed + viled pagination unlocked + 4 production bugs fixed]] — main session note
- Previous: ~~[[Текущие приоритеты — Phase 9 planned, execute next]]~~ — superseded 2026-05-14

## Команды для resume

```bash
# Если нужно ещё ad-hoc run с full viled + send в ops-chat:
uv run python bin/viled_fast_crawl.py
# Извлеки run_id из output, потом:
uv run python -m ga_crawler weekly-run --goldapple-only --run-id N --sanity-gate-m 50 --sanity-gate-p 0
uv run python -m ga_crawler matcher-run --run-id N --sanity-gate-p 0
uv run python -m ga_crawler report-run --run-id N

# Phase 11 start:
/gsd-discuss-phase 11
# или сразу
/gsd-plan-phase 11
```
