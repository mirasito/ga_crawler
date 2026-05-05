---
phase: 01-goldapple-reconnaissance-spike
plan: 03
subsystem: anti-bot
status: SKIPPED

tags: [skipped, iproyal, proxy-cancelled]

requires: []
provides: []
affects: [phase-7]

key-decisions:
  - "D-08 (IPRoyal pre-register before Tier 2 test) CANCELLED on 2026-05-06."
  - "01-03 SKIPPED — Camoufox + KZ-laptop direct passes goldapple gate without proxy (plan 01-08 99/100 evidence)."

requirements-completed: []

duration: 0min (not executed)
completed: 2026-05-06 (formally skipped)
---

# Plan 01-03: SKIPPED

**Plan formally skipped — D-08 (IPRoyal pre-register) cancelled on 2026-05-06 after side-spike 01-06b and full plan 01-08 confirmed Camoufox + KZ-laptop direct passes the goldapple GroupIB/F.A.C.C.T. gate without any proxy at 99/100 success rate.**

## Why skipped

The hypothesis underlying 01-03 was: "Tier 2 Patchright direct on KZ-laptop will likely fail; pre-register IPRoyal trial so Tier 3 escalation doesn't lose a day to KYC."

Plan 01-06 confirmed Patchright fails (0/7). But the side-spike 01-06b (commit `1ff7d4d`) and follow-on plan 01-08 (commit `f9ace33`) showed Camoufox passes the gate from KZ-laptop without proxy — fingerprint surface alone defeats GroupIB. Multi-geo proxy adds zero value-of-information when the gate is fingerprint-based.

## Rationale chain

- Plan 01-06: Patchright 0/7 baseline → originally would have triggered 01-03 IPRoyal revival
- Plan 01-06b side-spike: Camoufox 3/3 instantly → hypothesized 01-03 may not be needed
- Plan 01-08 main run: Camoufox 99/100 with 0% gate-shell rate → 01-03 confirmed not needed

## What this means for Phase 7

D-08 is **not dead** — it can be **reactivated** as a Phase 7 task if:
- Hetzner-EU + Camoufox combination breaks the gate (GroupIB likely whitelists IP-geo); OR
- Daijro/camoufox upstream stalls and the coryking fork also fails to bypass GroupIB after a vendor update

In either case, Phase 7 ops playbook revives this plan: register IPRoyal trial, switch fetch layer to Camoufox + KZ-residential proxy, re-baseline against goldapple.

## Cross-references

- `.planning/spikes/01-goldapple/MEMO.md` — Options tested table records this SKIP under the Camoufox-PASS status block
- `.planning/phases/01-goldapple-reconnaissance-spike/01-03-PLAN.md` — original plan kept as audit trail
- `.planning/STATE.md` Key Decisions row "Tier 2 = Camoufox direct, no proxy"
- `[[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]]` — Obsidian sign-off note

---
*Phase: 01-goldapple-reconnaissance-spike*
*Plan 01-03 status: SKIPPED on 2026-05-06*
