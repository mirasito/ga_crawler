---
phase: 07-scheduler-observability-hardening
plan: 05
subsystem: doc-cascade
tags: [wave-4, doc-cascade, requirements-closure, state-accumulation, roadmap-update, phase-7-close-out, v1-complete]
requires:
  - .planning/phases/07-scheduler-observability-hardening/07-01-SUMMARY.md   # Wave 1 RED-gate canaries
  - .planning/phases/07-scheduler-observability-hardening/07-02-SUMMARY.md   # Wave 2 deploy templates
  - .planning/phases/07-scheduler-observability-hardening/07-03-SUMMARY.md   # Wave 2 bash wrappers
  - .planning/phases/07-scheduler-observability-hardening/07-04-SUMMARY.md   # Wave 3 README
  - .planning/phases/07-scheduler-observability-hardening/07-CONTEXT.md      # D-701..D-710
  - .planning/REQUIREMENTS.md                                                # SCHED-01..05 source
  - .planning/STATE.md                                                       # Accumulated Key Decisions target
  - .planning/ROADMAP.md                                                     # Phase 7 plan list + Progress table target
provides:
  - .planning/REQUIREMENTS.md                                                # SCHED-01..05 closed with verbose per-plan citations; INFRA-V2-04 v2 backlog
  - .planning/STATE.md                                                       # D-701/D-708/D-709/D-710 cascade rows; Plan Execution Metrics 07-01..07-05; Current Position COMPLETE
  - .planning/ROADMAP.md                                                     # Phase 7 plan list 5 entries + Progress 5/5 Complete 2026-05-12 + top-level [x]
  - .planning/phases/07-scheduler-observability-hardening/07-CONTEXT.md      # Action Items table 12/12 [DONE Plan 07-XX] ticked
affects:
  - "v1 milestone: 47/48 v1 requirements satisfied — effectively COMPLETE (only Phase 1 RECON-01 conditional plans remain, operator-deferred per spike MEMO)"
  - "Operator handoff: VPS deploy on Hetzner CX22 EU per README §2 unblocked"
tech-stack:
  added: []                                                                  # zero new deps; pure doc cascade
  patterns:
    - "Plan 05-06 / Plan 06-06 doc cascade mirror — verbose SCHED-* closure annotations with per-plan citations"
    - "STATE.md Accumulated Key Decisions cascade pattern — 4 rows for v2/Phase-8 inheritance (D-701 + D-708 + D-709 + D-710)"
    - "ROADMAP.md Phase 7 plan list filled with reverse-chronological narrative + Progress table 5/5 Complete"
    - "07-CONTEXT.md Action Items closure annotations [DONE Plan 07-XX] mirror Phase 6 cascade convention"
key-files:
  created:
    - ".planning/phases/07-scheduler-observability-hardening/07-05-SUMMARY.md (this file)"
  modified:
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/phases/07-scheduler-observability-hardening/07-CONTEXT.md
decisions:
  - "REQUIREMENTS.md SCHED-01..05 annotations written verbatim from plan must_haves block — verbose multi-Plan citations (Plan 07-02 deploy templates + Plan 07-03 bash wrappers + Plan 07-04 README) with all D-7xx decision IDs cross-referenced."
  - "STATE.md Accumulated Key Decisions row order: existing Phase 6 rows (D-605/D-606/D-607) preserved; 4 new Phase 7 rows (D-701/D-708/D-709/D-710) appended at end of table per Plan 06-06 cascade precedent (chronological by phase close-out date)."
  - "Plan Execution Metrics 07-05 row inserted ABOVE 07-04..07-01 to preserve reverse-chronological convention used throughout Phase 4-6 blocks; 07-01..07-04 ordering left intact."
  - "Current Position Resume file flipped from `06-06-SUMMARY.md` → `07-05-SUMMARY.md` per Plan 05-06 / 06-06 cascade precedent (Resume file points to most-recently-shipped artifact)."
  - "Progress bar updated from `5/7 phases` to `7/7 phases COMPLETE` reflecting v1 milestone reach (Phase 1 conditional 9/12 counted as complete since 01-03/01-09/01-10 SKIPPED per Camoufox-direct lock)."
  - "Active Todos top entry rewritten from `/gsd-discuss-phase 7` → operator-led VPS deploy procedure citing README §2 step-by-step."
  - "07-CONTEXT.md Action Items table received [DONE Plan 07-XX] annotation per line — mirrors Phase 6 close-out convention where every line is structurally closed with execution citation."
  - "INFRA-V2-04 added to v2 Infrastructure backlog in REQUIREMENTS.md §v2 Requirements / Infrastructure — surfaces D-710 Docker defer rationale (Camoufox Firefox 135 vs Chromium-based Playwright image incompatibility)."
metrics:
  duration: "~10 min"
  completed: "2026-05-12T18:35:00Z"
  tests_pre: 802
  tests_post: 802                                                            # docs-only; suite unchanged
  tests_skipped_post: 1
  files_created: 1
  files_modified: 4
requirements: [SCHED-01, SCHED-02, SCHED-03, SCHED-04, SCHED-05]
threat-refs: []
---

# Phase 07 Plan 05: Wave 4 Doc Cascade Close-Out Summary

**One-liner:** финальный doc cascade Phase 7 — REQUIREMENTS.md SCHED-01..05 закрыты с per-plan citations + Coverage 42/48 → 47/48 + INFRA-V2-04 v2 backlog; STATE.md §Accumulated Key Decisions extended с D-701/D-708/D-709/D-710 cascade rows + Plan Execution Metrics 07-01..07-05 + Current Position Phase 7 COMPLETE; ROADMAP.md Phase 7 plan list filled + Progress 5/5 Complete 2026-05-12 + top-level [x]; 07-CONTEXT.md Action Items table 12/12 [DONE Plan 07-XX] ticked. Phase 7 closes v1; only Phase 1 RECON-01 conditional remains (operator-deferred per spike MEMO).

## What Shipped

Wave 4 — это **doc cascade**: ни одной строки production-кода не изменено. Phase 7 уже была функционально готова после Plan 07-04 (802/1 test suite, all 7 Wave-0 canaries GREEN, README 10-section runbook complete). Plan 07-05 формально закрывает фазу в четырёх документах.

### Task 1 — REQUIREMENTS.md SCHED-01..05 closure (commit `bea2a7d`)

Все 5 SCHED-* блоков были `- [ ]` (Pending) до этого плана. Plan 07-05 заменил их на **verbose multi-Plan citations** дословно из must_haves блока:

| Requirement | Closure citation key plans + decisions |
|-------------|----------------------------------------|
| SCHED-01 | Plan 07-02 `deploy/etc-cron-d-ga_crawler` D-708 verbatim + Plan 07-04 README §2 + §4 deploy procedure; Sunday 23:00 Almaty cron row |
| SCHED-02 | Plan 07-02 D-708 — `CRON_TZ=Asia/Almaty` first non-comment line + `MAILTO=""` (Pitfall #2 / T-07-01 mitigation); canary `test_cron_contains_cron_tz_almaty` |
| SCHED-03 | Plan 07-03 `bin/weekly-run.sh` D-709 — `/start` before exec + bare URL on EXIT=0 + `/fail` with `--data-raw` on EXIT≠0; D-703 fail-loud exit 4 if HC_PING_URL missing; Plan 07-04 README §5 |
| SCHED-04 | Plan 07-03 wrapper redirects stdout/stderr to datestamped logfile + Plan 07-02 `deploy/etc-logrotate-d-ga_crawler` D-705 — weekly + rotate 13 + compress; D-704 `_configure_logging()` source unchanged |
| SCHED-05 | Plan 07-04 README.md 10 H2 sections per D-707 RU-primary + Plan 07-03 `bin/test-failure-alert.sh` D-706 5-step orchestrator |

Traceability table rows SCHED-01..05 flipped Pending → Done with per-plan + per-decision citations. Coverage block updated: `Closed: 42/48` → `47/48` (Phase 7 closes 5 SCHED). v2 Infrastructure backlog gains INFRA-V2-04 per D-710. Phase 7 close-out footer line appended preserving Phase 4/5/6 footers.

### Task 2 — STATE.md cascade (commit `7864e31`)

3 surgical sections updated:

1. **§Accumulated Key Decisions** — 4 new rows appended after Phase 6 D-607 row (preserving chronological order):
   - **D-701 Phase 7** — HC pings live в bash wrapper, не Python (hard-crash coverage). CLI exit codes уже семантически правильные через Phase 6 D-606 enum→exit-code mapping. Структурный canary: `git diff src/ga_crawler/cli.py` empty Phase 6→Phase 7. Cascade target: Phase 7+ monitoring extensions MUST follow wrapper-owned-pings pattern.
   - **D-708 Phase 7** — `/etc/cron.d/ga_crawler` (root-edited, user column) preferred над user-crontab для ops visibility + git-trackability. Repo template at `deploy/etc-cron-d-ga_crawler`. Pitfall #1 filename (no dot, no extension) per Vixie cron rules. Cascade target: future cron-driven jobs extend `deploy/etc-cron-d-ga_crawler`.
   - **D-709 Phase 7** — flock(1) advisory lock в `/var/lock/ga_crawler-weekly.lock` предотвращает double-run от cron+manual overlap. Exit code 5 reserved. `set -euo pipefail` + `set -a; source .env; set +a` + `set +e/EXIT=$?/set -e` dance preserves Python exit code. Cascade target: future bash wrappers use same pattern (flock + reserved exit code + log redirect + HC ping triad).
   - **D-710 Phase 7** — Docker defer to v2 (INFRA-V2-04). Camoufox Firefox 135-pinned не совместим с `mcr.microsoft.com/playwright/python:v1.57.0-noble` (Chromium-based); custom image — separate effort. Cascade target: future v2 infra MUST inherit constraint (custom base image required OR pivot anti-bot strategy).

2. **§Plan Execution Metrics** — 5 rows inserted ABOVE 06-06 (preserves reverse-chronological convention): 07-05 → 07-04 → 07-03 → 07-02 → 07-01. Each row contains verbose narrative citing Wave, files created/modified, deviations, test counts before/after.

3. **§Current Position + frontmatter** — `status: Phase 7 CONTEXT GATHERED` → `status: Phase 7 COMPLETE 2026-05-12 — SCHED-01..05 closed; 47/48 v1 requirements satisfied`; `completed_phases: 6 → 7`; `total_plans: 45 → 50`; `completed_plans: 45 → 50`. Current Position narrative `Phase: 07 — CONTEXT GATHERED` → `Phase: 07 — COMPLETE`. Plan field updated to `07-05 — COMPLETE 2026-05-12`. New `Phase 7 status: COMPLETE` line added above existing `Phase 6 status: COMPLETE`. Resume file flipped to `07-05-SUMMARY.md`. Progress bar `5/7 phases` → `7/7 phases COMPLETE`. Performance Metrics `Phases completed 6 → 7` + `Plans completed 33 → 38` (07-01..07-05 added) + `v1 requirements completed 42/48 → 47/48`. §Active Todos top entry rewritten from `/gsd-discuss-phase 7` to operator-led VPS deploy procedure citing README §2 step-by-step.

### Task 3 — ROADMAP.md Phase 7 close-out + 07-CONTEXT.md Action Items (commit `d87c44e`)

**(a) ROADMAP.md:**
- Top-level `- [ ] **Phase 7: ...**` flipped to `- [x]`.
- Plan list `**Plans**: TBD` replaced with 5 entries (07-01..07-05) each annotated with Wave number + key D-decisions + closure narrative.
- Progress table row Phase 7 updated from `0/0 / Not started / -` → `5/5 / Complete (verbose Wave 1..4 narrative citing operator-facing-artifacts + manual-only-verifications + ARCHITECTURE.md extension «delivery independent of run-correctness» → «monitoring independent of business logic») / 2026-05-12`.
- Phase 7 close-out footer line appended preserving Phase 5/6 footers; documents v1 milestone reach + INFRA-V2-04 v2 backlog + operator handoff for first production weekly cron tick.

**(b) 07-CONTEXT.md Action Items:** all 12 bullets received `[DONE Plan 07-XX Task N]` annotation with execution citation. Each line now traceable from intent (Wave 0 plan-time) to delivery (Wave 1..4 execution):
- `.env.example` HC_PING_URL → [DONE Plan 07-02 Task 3]
- pyproject.toml NO changes → [DONE — verified by tests/test_phase07_structural_canaries.py]
- REQUIREMENTS.md SCHED-01..05 closure → [DONE Plan 07-05 Task 1]
- STATE.md 4 D-7xx cascade rows → [DONE Plan 07-05 Task 2]
- REQUIREMENTS.md INFRA-V2-04 → [DONE Plan 07-05 Task 1]
- README.md → [DONE Plan 07-04]
- deploy/etc-cron-d-ga_crawler → [DONE Plan 07-02 Task 1]
- deploy/etc-logrotate-d-ga_crawler → [DONE Plan 07-02 Task 2]
- bin/weekly-run.sh → [DONE Plan 07-03 Task 1]
- bin/test-failure-alert.sh → [DONE Plan 07-03 Task 2]
- .gitignore audit → [DONE Plan 07-01 audit]

### Task 4 — Full regression suite green

```
uv run pytest -x --tb=short -q
→ 802 passed, 1 skipped, 181 warnings in 130.81s (0:02:10)
```

**Zero regressions.** Same baseline as Plan 07-04 close: 802 passed / 1 skipped. The 1 skipped is the pre-existing Phase 3 viled artificial-mutation test (`tests/integration/test_viled_run_e2e_with_real_storage.py::test_parse_quality_gate_fails`) — NOT Phase 7-related. Plan 07-05 is docs-only; suite unchanged.

## Phase 7 Totals (cumulative across 5 plans)

| Metric | Value |
|--------|-------|
| **Production artifacts created** | 6 (2 `deploy/*` templates + 2 `bin/*.sh` wrappers + 1 `.env.example` edit + 1 `README.md`) |
| **Production Python LOC** | 0 (zero new lines in `src/ga_crawler/*` — structural canary `test_phase07_structural_canaries.py::test_zero_production_python_phase7` enforces) |
| **New pyproject namespaces** | 0 (no `[tool.ga_crawler.schedule]` added — operator config lives in shell + cron + logrotate files, not Python) |
| **New `runs.stats.*` namespaces** | 0 (5-way disjoint invariant preserved: viled / goldapple / match / report / deliver; no `schedule.*` keys) |
| **New deps** | 0 (curl/flock/logrotate already in base Ubuntu; no Python imports) |
| **Wave 0 test files (canaries)** | 7 — `tests/test_phase07_*.py` (56 tests, 684 lines total) |
| **Tests after Phase 7** | 802 passed / 1 skipped (746 → 802 = +56 across Wave 0; zero regressions in Phase 1-6) |
| **Total Phase 7 commits** | 14 (Plan 07-01 = 3 commits; Plan 07-02 = 3 commits; Plan 07-03 = 2 commits; Plan 07-04 = 1 commit; Plan 07-05 = 5 commits including doc-cascade + final close-out commits) |
| **D-decisions locked** | 10 (D-701..D-710) |
| **SCHED-* requirements closed** | 5 (SCHED-01..05) |
| **v1 requirements satisfied** | 47/48 (Phase 1-7 complete; only Phase 1 RECON-01 conditional remains — operator-deferred per spike MEMO) |

## Phase 6 Suite Preservation Verification

Phase 6 functionality (Telegram delivery + ops/business split) **remained GREEN throughout Phase 7** — verified by:

1. **Phase 7 Wave 0 canaries (Plan 07-01)** included `tests/test_phase07_structural_canaries.py::test_no_aiogram_imports_outside_telegram_client_phase7` cross-phase invariant — assertion that Phase 7 mustn't break Phase 6's pure-Python invariant (only `delivery/telegram_client.py` may import aiogram).
2. **Phase 7 production artifacts ship ZERO Python** — by construction, Phase 6 production code untouched. `git diff` on `src/ga_crawler/delivery/*` between Phase 6 close-out commit `1a3b0c8` (Plan 06-05 ship) and Phase 7 close-out commit (this plan) is EMPTY.
3. **Test suite baseline** — 746 passed / 1 skipped at Phase 6 close; 802 passed / 1 skipped at Phase 7 close (+56 from Wave 0 canaries only). All 6 E2E tests from `tests/integration/test_weekly_run_with_delivery.py` (SC#1 happy path + SC#2 sanity-fail + SC#2 size-guard + D-605 invariant + reporter-skipped cascade + 5-namespace integrity) remain GREEN.

## Verification Canaries

| Canary | Command | Result |
|--------|---------|--------|
| REQUIREMENTS.md SCHED-01..05 closed | `grep -c "^- \[x\] \*\*SCHED-0" .planning/REQUIREMENTS.md` | 5/5 |
| REQUIREMENTS.md Traceability 5/5 Done | `grep "^\| SCHED-" .planning/REQUIREMENTS.md \| grep -c Done` | 5 |
| REQUIREMENTS.md Coverage 47/48 line present | `grep "47/48" .planning/REQUIREMENTS.md` | OK |
| REQUIREMENTS.md INFRA-V2-04 present | `grep "INFRA-V2-04" .planning/REQUIREMENTS.md` | OK |
| Phase 7 footer line present | `grep "Phase 7 update: 2026-05-12" .planning/REQUIREMENTS.md` | OK |
| STATE.md D-701/D-708/D-709/D-710 cascade rows present | Python quadruple-substring check | OK |
| STATE.md Plan Execution Metrics 07-01..07-05 rows present | `grep -c "^\| 07-0" .planning/STATE.md` | 5 |
| STATE.md Phase 7 status COMPLETE | `grep "Phase 7 status: \*\*COMPLETE\*\*" .planning/STATE.md` | OK |
| STATE.md Resume file flipped to 07-05-SUMMARY.md | `grep "07-05-SUMMARY.md" .planning/STATE.md` | OK |
| ROADMAP.md Phase 7 [x] + 07-01..07-05 plan list | Python quadruple-substring check | OK |
| ROADMAP.md Progress 5/5 Complete | `grep "5/5 \| Complete" .planning/ROADMAP.md` | OK |
| 07-CONTEXT.md Action Items ticked | `grep -c "\[DONE" .planning/phases/07-scheduler-observability-hardening/07-CONTEXT.md` | 12+ |
| Pytest full suite | `uv run pytest -x --tb=short -q` | 802 passed, 1 skipped |

## Deviations from Plan

**None.** Plan 07-05 executed exactly as written. All 4 plan tasks complete; all 5 must_haves.truths verified; all <success_criteria> rows green. No Rule 1-3 auto-fixes triggered (docs-only changes — no production code touched).

### Notable details

- **REQUIREMENTS.md Coverage line** updated from `Closed: 42/48` → `Closed: 47/48` (+5 SCHED; 47 = 48 − 1 RECON-01 conditional). The "previous '47 total' was an off-by-one" note line preserved verbatim — that note refers to the enumeration count not the closure count, and is still accurate.
- **STATE.md frontmatter `total_plans` 45 → 50** reflects the 5 Phase 7 plans now counted (Plans Execution Metrics already had 45 rows across Phase 1-6; +5 Phase 7 = 50 total). `completed_plans` matches `total_plans` since all Phase 7 plans shipped.
- **STATE.md `Phases completed: 6 → 7` arithmetic** — Phase 1 counted as complete despite 9/12 plans shipped (3 SKIPPED per spike MEMO Camoufox-direct lock); Phases 2-7 all 100% complete with respective plan counts. This matches the existing convention from Phase 5/6 close-outs.

## Auth Gates

None encountered. Plan 07-05 is purely docs-only (REQUIREMENTS.md / STATE.md / ROADMAP.md / 07-CONTEXT.md edits). No environment variables, no Telegram credentials, no DB access, no deploy operations required.

## Decisions Made

- **Per-plan citation depth in SCHED-01..05 closure annotations** — verbatim from plan must_haves block: each citation references at least 1 Plan ID (07-02 / 07-03 / 07-04) AND at least 1 decision ID (D-701..D-710). Mirrors Plan 06-06's DELIVER-* closure precedent. Operator reading REQUIREMENTS.md gets full traceability from requirement → implementation plan → design decision without needing to chase down secondary artifacts.
- **STATE.md cascade row count = 4 (D-701/D-708/D-709/D-710), NOT all 10 D-7xx** — per Plan 07-05 frontmatter must_haves.truths line. D-702..D-707 are scoped to single-plan / non-cascading invariants documented in respective plan SUMMARYs (Healthchecks.io SaaS choice, grace period 2h, logrotate keep 13, deliberate-failure orchestrator, README 10-section ordering, VPS layout `/opt/ga_crawler` system user). Only D-701/D-708/D-709/D-710 are cross-cutting cascade invariants requiring v2/Phase-8 inheritance.
- **`Coverage: 47/48` NOT `48/48`** — Phase 1 RECON-01 conditional plans (01-03 IPRoyal / 01-09 multi-geo / 01-10 Tier-3) remain Pending in REQUIREMENTS.md Traceability since they're explicitly SKIPPED per spike MEMO (Camoufox-direct lock proven 99/100 at Phase 1 close). They are not "closed" in the traditional sense — closure would require either delivering the conditional plans OR formally retiring the requirement to v2 backlog. Operator can decide at v2 milestone discussion. 47/48 reflects current accurate state.
- **Plan Execution Metrics 07-05 row position** — inserted ABOVE 07-04 (and 07-04 above 07-03, etc.) so the Phase 7 block reads reverse-chronologically (07-05 → 07-04 → 07-03 → 07-02 → 07-01), matching the pre-existing convention used for Phase 4 + 5 + 6 blocks in the same table.
- **Progress bar update `5/7 → 7/7 phases COMPLETE`** — Phase 1 counted as complete (9/12 with 3 skipped per spike MEMO); Phase 2-7 all 100% complete. This is the v1 milestone reach. Operator-led VPS deploy is the only remaining unblock for first production weekly cron tick — but that's not a "plan to execute," it's a deployment action.

## Threat Model Surface

**No new threats introduced by this plan.** Phase 7 threat model fully covered by Plans 07-02 (T-07-01 cron MAILTO leak + T-07-04 HC.io UUID in git + T-07-05 world-writable rotated logs) / 07-03 (T-07-02 double-run DB corruption + T-07-04 HC UUID + T-07-07/T-07-08 accepted) / 07-04 (T-07-01 cron mail leak documentation + T-07-04 HC.io URL only in .env + T-07-05 logrotate-during-write edge case + T-07-08 .env code injection). Plan 07-05 is docs-only.

## Wave 4 → v1 Milestone Handoff

Plan 07-05 closes Phase 7 entirely. v1 milestone effectively COMPLETE. Operator reads:

- **STATE.md §Active Todos top entry** — operator-led VPS deploy on Hetzner CX22 EU per README §2 step-by-step.
- **README.md §2** — 8-step Hetzner CX22 + Ubuntu 24.04 setup with Pitfall #5/#6 user-first ordering.
- **README.md §3** — ENV table + 5 reserved exit codes (0/2/3/4/5).
- **README.md §4** — verbatim cron content quoted from `deploy/etc-cron-d-ga_crawler`.
- **README.md §5** — 6-step Healthchecks.io setup.
- **README.md §6** — 5-step Telegram bot setup.
- **README.md §7** — `bin/test-failure-alert.sh` deliberate-failure procedure + 5-item operator verification checklist for SC#5 manual smoke.

### Operator handoff note

**Phase 7 is the last code-shipping phase in v1.** From here, ops takes over:

1. **VPS provisioning** — Hetzner CX22 EU (Falkenstein/Helsinki); Ubuntu 24.04 LTS.
2. **From-scratch install** per README §2 (8 steps: apt-update / useradd ga_crawler / uv install / git clone / uv sync / playwright install firefox / install -d /var/log/ga_crawler / cp deploy/ templates to /etc/cron.d + /etc/logrotate.d).
3. **Healthchecks.io account + check + ping URL** per README §5.
4. **Telegram bot account + business chat + ops chat** per README §6.
5. **`.env` file** with 4 required ENV (TG_BOT_TOKEN / TG_BUSINESS_CHAT_ID / TG_OPS_CHAT_ID / HC_PING_URL) — chmod 0600 ga_crawler.
6. **Smoke gate** — `sudo -u ga_crawler bin/weekly-run.sh --viled-only --sanity-gate-n 1` (mini-run; ~2 min; SC#1 setup verification).
7. **First production Sunday cron tick** — Sunday 23:00 Almaty → Monday 02:00-03:00 Almaty report arrival.
8. **Deliberate-failure verification** — `sudo -u ga_crawler bin/test-failure-alert.sh` + operator manual smoke per 07-VALIDATION.md «Manual-Only Verifications» (SC#5).

### v2 / Phase 8 backlog

Surfaced during Phase 7:

- **INFRA-V2-04** (REQUIREMENTS.md): Docker image для reproducible redeploys — Camoufox Firefox 135 vs Chromium-based Playwright image; custom base image required.
- **viled catalog pagination beyond page 1** (Phase 3/7 ops backlog from STATE.md): reverse-engineer XHR pagination OR per-`groupId` filter walks; current v1 limit 120 SKUs/run.
- **Camoufox+EU smoke fetch from Hetzner** (Phase 7 ops backlog): if `goldapple-smoke` regresses from EU IP, revive D-08 IPRoyal trial.
- **KZ-legal review** (Phase 7 backlog): 30 min с юристом for ToS compliance; bundle = tos-audit.md + viled-privacy.txt + both *-robots.txt snapshots + GroupIB/F.A.C.C.T. vendor flag.

## Self-Check: PASSED

Files verified to exist on disk:

- `.planning/REQUIREMENTS.md` — MODIFIED (SCHED-01..05 closure annotations + Traceability 5/5 Done + Coverage 47/48 + INFRA-V2-04 + Phase 7 footer)
- `.planning/STATE.md` — MODIFIED (frontmatter + Current Position + Performance Metrics + 4 cascade rows D-701/D-708/D-709/D-710 + 5 Plan Execution Metrics rows 07-01..07-05 + Active Todos + Phase 7 status line + Resume file + Progress bar)
- `.planning/ROADMAP.md` — MODIFIED (top-level Phase 7 `[x]` + plan list 5 entries 07-01..07-05 + Progress 5/5 Complete 2026-05-12 + Phase 7 footer)
- `.planning/phases/07-scheduler-observability-hardening/07-CONTEXT.md` — MODIFIED (Action Items table all 12 lines annotated `[DONE Plan 07-XX]`)
- `.planning/phases/07-scheduler-observability-hardening/07-05-SUMMARY.md` — CREATED (this file)

Commits verified in `git log --oneline`:

- `bea2a7d` (Task 1) — `docs(07-05): close SCHED-01..05 with per-plan citations + INFRA-V2-04 backlog`
- `7864e31` (Task 2) — `docs(07-05): STATE.md cascade — D-701/D-708/D-709/D-710 + Plan Execution Metrics + Current Position COMPLETE`
- `d87c44e` (Task 3) — `docs(07-05): ROADMAP Phase 7 close-out + 07-CONTEXT Action Items ticked`
- (Final commit pending — bundles this SUMMARY.md + any final STATE.md tweaks)

Suite at HEAD: **802 passed, 1 skipped**. Zero new tests; zero regressions; zero production code touched. Phase 7 effectively closes v1 milestone (47/48 v1 requirements satisfied).
