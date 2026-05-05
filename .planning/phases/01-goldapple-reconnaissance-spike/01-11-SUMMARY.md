---
phase: 01-goldapple-reconnaissance-spike
plan: 11
subsystem: anti-bot

tags: [memo, decision, sign-off, tier-2, camoufox, microdata, groupib]

requires:
  - phase: 01
    provides: tier2-camoufox-kz-results.json (99/100 PASS), 01-04 ToS audit, 01-05 page-volume + sitemap, 01-06 GroupIB vendor ID + Patchright supersedure, 01-06b Camoufox baseline, 01-07 viled feasibility
provides:
  - Final MEMO.md signed-off with Tier 2 / Camoufox / no-proxy verdict
  - Phase 3 stack-decision (locked): Camoufox+microdata for goldapple, curl_cffi+__NEXT_DATA__ for viled
  - Phase 7 hosting recommendation (Hetzner EU + smoke gate, IPRoyal KZ fallback)
  - All 12 MEMO sections populated (zero TBDs)
  - 4 RECON requirements closed (RECON-01 in Options/Chosen, RECON-02 in viled feasibility, RECON-03 in Page-volume + JSON-endpoint hunt, RECON-04 in robots/ToS summary)
affects: [01-12, phase-2, phase-3, phase-4, phase-7]

tech-stack:
  added: []
  patterns:
    - "Decision-memo template with TL;DR + Chosen + Next-step impact + Open Risks + Appendix Challenge-rate + Sign-off"

key-files:
  created: []
  modified:
    - .planning/spikes/01-goldapple/MEMO.md (TL;DR + Chosen + robots/ToS rate-limits + Next-step impact + Open risks + Appendix + Sign-off)

key-decisions:
  - "Tier 2 Camoufox direct, no proxy — committed as Phase 3 production engine"
  - "Phase 7 hosting = Hetzner CX22 EU baseline + Camoufox+EU smoke gate before locking; IPRoyal KZ residential as fallback"
  - "Phase 3 prod-monitoring early-warning threshold = gate-shell rate >5% (well below 20% fragility line)"

patterns-established:
  - "Pattern: spike sign-off with explicit RECON checklist (RECON-01..04 marked CLOSED in Sign-off block)"
  - "Pattern: Open Risks section enumerates discoveries that materially change downstream-phase work"

requirements-completed: [RECON-01, RECON-02, RECON-03, RECON-04]

duration: ~10min
completed: 2026-05-06
---

# Plan 01-11: MEMO Finalize Summary

**MEMO.md signed off 2026-05-06 with Tier 2 Camoufox direct (no proxy) verdict; all 12 obligatory sections populated, zero TBDs, RECON-01..04 closed.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 3 (Task 1 mental data sweep, Task 2 MEMO rewrite of TL;DR + Chosen + Next-step + Open Risks + Appendix + Sign-off, Task 3 grep verify)
- **Files modified:** 1 (MEMO.md)

## Accomplishments

- Final MEMO with one-paragraph TL;DR, four quick-reference bullets (tier, engine, proxy, prod-IP), and a 5-bullet Chosen rationale
- robots/ToS rate-limit TBDs replaced with committed values (viled 2s, goldapple 3-5s random uniform); KZ-legal review explicitly deferred to Phase 7
- Next-step impact section locks Phase 2 + Phase 3 + Phase 4 + Phase 7 inputs
- 6 Open Risks captured (microdata-not-JSON-LD, Camoufox upstream maintenance, Hetzner-EU compatibility, brand-precision shortfall, stale-SKU pattern, GroupIB-uncharted-territory)
- Appendix Challenge-rate appendix records 0% Camoufox vs 100% Patchright + sets Phase 3 prod-monitoring threshold at >5% gate-shell
- Sign-off block with explicit RECON-01..04 checklist all checked

## Task Commits

1. **Tasks 1+2+3 (in-place MEMO rewrite + verify):** `70fdffa` (docs)

Single commit because the data sweep (Task 1) is a mental step with no file changes, and the verify (Task 3) is grep against the same file Task 2 produced.

## Files Created/Modified

- `.planning/spikes/01-goldapple/MEMO.md` — finalized 12 sections (was 282 lines with TBDs → 355 lines with concrete data); also picks up 01-08 Options-tested rows and Open Risks block from earlier commits

## Decisions Made

- **Tier 2 Camoufox direct as Phase 3 production engine** — anchored in 99/100 D-13 PASS at 0% gate-shell rate (plan 01-08 evidence)
- **Phase 7 hosting = Hetzner EU + smoke-test before locking** — explicit acknowledgment that GroupIB IP-geo whitelist may demote EU; IPRoyal KZ fallback path documented
- **Prod-monitoring early-warning threshold at >5% gate-shell** — half the 20% fragility line, gives ops time to react before Tier 2 fully degrades

## Deviations from Plan

None — Tasks 1, 2, 3 executed in place against the structure 01-11-PLAN.md specified. (One pre-existing deviation: 01-11-PLAN.md Task 1 read_first path was updated from `tier2-kz-laptop-results.json` to `tier2-camoufox-kz-results.json` — that path edit happened during 01-08 execution and was committed alongside this 01-11 finalize commit `70fdffa`.)

## Issues Encountered

None — all source data was present (result-JSONs from 01-04..01-08, network-trace from 01-06, sitemap data from 01-05, viled feasibility from 01-07).

## Next Phase Readiness

**Ready for plan 01-12 (wrap-up):**
- MEMO signed off and structurally complete (12 sections, 0 TBDs, ≥150 lines)
- Phase 3 stack-decision can be picked up by `/gsd-discuss-phase 3` directly from MEMO without re-deriving
- Obsidian copy filename suggested by data: `2026-05-06-goldapple-tier-2-camoufox-direct-no-proxy.md` (assertion-style)

**Ready for Phase 2 (skeleton + viled crawl):**
- viled feasibility CONFIRMED, `__NEXT_DATA__` 8-field schema captured
- viled rate-limit committed at 2s sequential
- Sitemap-only enumeration pattern locked

**Ready for Phase 3 (goldapple crawl):**
- Camoufox + microdata extraction stack frozen
- 100,779 product URL pool enumerated via plain curl_cffi sitemap (Tier 0 enumeration despite Tier 2 render)
- Rate-limit 3-5s random uniform locked

**Outstanding (handled by 01-12):**
- 01-12 Task 1: confirm Obsidian vault path
- 01-12 Task 2: write assertion-style decision note in Obsidian
- 01-12 Task 3: project-local skill in `.claude/skills/spike-01-goldapple/SKILL.md`
- 01-12 Task 4: STATE.md Phase 1 close + Key Decisions Tier 2 row

---
*Phase: 01-goldapple-reconnaissance-spike*
*Completed: 2026-05-06*
