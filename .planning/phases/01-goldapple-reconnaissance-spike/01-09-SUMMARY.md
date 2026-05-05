---
phase: 01-goldapple-reconnaissance-spike
plan: 09
subsystem: anti-bot
status: SKIPPED

tags: [skipped, multi-geo, proxy-not-needed]

requires: []
provides: []
affects: [phase-7]

key-decisions:
  - "D-05 (multi-geo measurement EU/RU residential vs KZ-laptop) value-of-information collapses to zero when fingerprint alone solves the gate."

requirements-completed: []

duration: 0min (not executed)
completed: 2026-05-06 (formally skipped)
---

# Plan 01-09: SKIPPED

**Multi-geo proxy comparison (EU/RU residential vs KZ-laptop) — value-of-information ≈ 0 when fingerprint alone solves the gate. Plan 01-08 Camoufox 99/100 from KZ-laptop direct + 01-06b 3/3 baseline + 01-06 Patchright 0/7 (control) constitute the empirical evidence that GroupIB/F.A.C.C.T. is fingerprint-based, not IP-rep-based.**

## Why skipped

01-09's purpose was to test whether IP geo (EU/RU residential proxy) makes a difference vs KZ-laptop direct. This test was meaningful when the hypothesis space was "IP-rep determines gate-pass." Plan 01-06 + 01-06b + 01-08 collapsed that hypothesis: same KZ-laptop IP, only browser-engine difference (Patchright vs Camoufox), produces 0/7 vs 99/100. Therefore IP geo is NOT the load-bearing variable; engine fingerprint IS.

## Information that 01-09 would have provided (and why we don't need it)

| Question 01-09 would answer | Why we don't need to test |
|---|---|
| Does GroupIB whitelist KZ IP-geo specifically? | Possible, but it's not the primary signal — fingerprint is. KZ-laptop direct works at 99/100 with Camoufox; this is sufficient for Phase 3 baseline. |
| Does EU residential proxy break the gate from EU-Hetzner? | Phase 7 Hetzner+EU smoke fetch will answer this directly with one fetch (deferred to Phase 7 backlog). |
| Does multi-geo improve robustness? | Robustness is gained via Camoufox fingerprint surface, not proxy diversity. |

## What this means for Phase 7

If Hetzner-EU smoke fetch fails (Camoufox+EU does NOT pass the gate), Phase 7 ops playbook activates the IPRoyal KZ residential fallback (D-08 reactivates via 01-03 SKIP-SUMMARY). At that point, multi-geo experimentation may revive — but it's a Phase 7 task, not a Phase 1 spike deliverable.

## Cross-references

- `.planning/spikes/01-goldapple/MEMO.md` — Options tested table records this SKIP under the Camoufox-PASS status block
- `.planning/phases/01-goldapple-reconnaissance-spike/01-09-PLAN.md` — original plan kept as audit trail
- `.planning/STATE.md` Key Decisions row "Tier 2 = Camoufox direct, no proxy"
- 01-03-SUMMARY.md (sibling SKIP rationale)

---
*Phase: 01-goldapple-reconnaissance-spike*
*Plan 01-09 status: SKIPPED on 2026-05-06*
