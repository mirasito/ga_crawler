# Retrospective: GA Crawler

> Living retrospective appended on each `/gsd-complete-milestone`. Cross-milestone trends accumulate at the bottom.

---

## Milestone: v1.0 — Initial Code-Ship

**Shipped:** 2026-05-13
**Phases:** 7 | **Plans executed:** 47 (3 SKIPPED per spike MEMO) | **Commits:** 284 | **Timeline:** 2026-05-05 → 2026-05-13 (8 days)

### What Was Built

A weekly competitive-pricing crawler for the viled.kz commercial team. Crawls goldapple.kz + viled.kz beauty catalogs, matches SKUs on `brand+name+volume`, computes price deltas, ships a 4-sheet Excel report + Russian-language Telegram summary to two chats (business + ops) every Sunday night Almaty time, with Healthchecks.io dead-man's-switch monitoring and cron-resilient single-writer flock guards.

### What Worked

1. **Front-loading the unknown.** Phase 1 spike timeboxed the anti-bot decision (goldapple = Camoufox-direct, 99/100, no proxy needed) BEFORE any production code. The 2-day spike retired 3 conditional plans and saved weeks of speculative IPRoyal/Tier-3 escalation work. Pattern reinforced: when a project has one defining unknown, spike it first — even if it's "wasted" code.
2. **Goal-backward phase ordering.** ROADMAP went viled-first → goldapple → matcher → reporter → delivery → scheduler. Every phase had an observable, verifiable outcome before the next started. No phase needed retroactive rework.
3. **Decision IDs as the through-line.** D-201..D-710 numbered decision records cascaded from CONTEXT.md → PLAN.md → SUMMARY.md → REQUIREMENTS.md with verbatim citations. When a plan deviated, it cited the decision row. When a future phase inherited a constraint, it linked the D-NNN. This kept 7 phases × 47 plans coherent without a separate ADR system.
4. **Atomic stats-namespace pattern (Pitfall 6).** Each phase patches a disjoint `runs.stats.{viled|goldapple|match|report|deliver}.*` namespace via a single `patch_stats` call. 5-way pairwise disjoint canary test enforces. Made parallelizing phase development trivial — no merge conflicts in `runs.stats`.
5. **Wave 0 source-lock canaries (Phase 7).** Tests written BEFORE the operator-facing artifacts (cron template, wrapper script, README) shipped, locking the exact shape we'd write. Caught a 2-line LOG_DIR/LOG_FILE split divergence in plan vs canary at the right moment.
6. **Pre-finalize-before-matcher dance.** Phase 4 ran into D-411's `read_run_status` rejecting `running` (which is always the in-flight state). The fix — pre-finalize `runs.status='success'` before matcher, let matcher's `fail()` revert on gate-trip — became a documented invariant for all future composition orchestrators.
7. **Reusable composition primitives.** `read_run_status` from Phase 4 got reused by Phase 5 and Phase 6 without modification. `SqliteRunWriter.patch_stats` used by all 5 runners. The runner protocol stayed stable through 6 phases of growth.

### What Was Inefficient

1. **TWO parser strategies for two retailers.** viled.kz uses `__NEXT_DATA__` JSON; goldapple.kz uses inline microdata (`<meta itemprop="price">`). The CLAUDE.md research notes anticipated JSON-LD for both — wrong. Phase 3 had to ship `ParseDispatcher` routing logic to keep the parser modules decoupled. Mid-project parser strategy revision (D-14) costs were absorbed cleanly but added Wave-3 LOC that v1 didn't need.
2. **Catalog pagination dead-end.** Phase 2 Wave-3 live probe tested 10 viled URL conventions for `?page=N` — SSR ignored all of them. v1 ships page-1-only (60 men + 60 women = 120 SKUs above sanity_gate_n=100 floor). Reverse-engineering pagination would have eaten Wave-3+ in Phase 2; rightly deferred to v2 ops backlog. Documented as accepted limitation in REQUIREMENTS.md CRAWL-01.
3. **Goldapple Wave-7 brand-token bucket index gap-closure.** UAT-3 surfaced `matched_url_count=0` against the real 45,490-slug sitemap — original `intersect_brand_pool` only checked exact-prefix slugs; brand-extensions like `tom_ford_beauty` weren't being routed. Required a Wave-7 gap-closure plan (`03-08`) to ship a Path A longest-prefix-in-whitelist bucket index. Caught at UAT but should have been caught at design.
4. **Cold-start Loading race.** UAT-3 also caught a 4-of-4 reproduction of a `Loading…` shell never clearing on URL[0] after fresh Camoufox boot. Required Wave-8 gap-closure plan (`03-09`): warm-up nav in `__aenter__` + retry-once safety net in `smoke_probe`. Lesson: any browser-bootstrap fetcher should expect cold-start anomalies and warm-up before the first real fetch.
5. **Audit-framework lag.** SECURITY.md was only generated for phases 3, 5, 7. VALIDATION.md only for 2, 3, 5, 6, 7. Phases 2, 4, 6 shipped with implicit threat handling baked into code reviews and tests — but the formal `/gsd-secure-phase` and `/gsd-validate-phase` artifacts were never run. Carried into v1.1 backlog. If we'd run them inline at each phase close, we'd have ended v1 at "passed" not "tech_debt".
6. **Python 3.12 sqlite default datetime adapter deprecation.** Bit us in Phase 6 with a DeprecationWarning that pytest captured in caplog and failed an assertion. Fixed inline with `_coerce_started_at` helper. The same kind of stdlib drift may bite again.
7. **Late integration-checker invocation.** The cross-phase integration check ran at milestone audit (Phase 7's end), not at each phase boundary. Result was clean (0 blockers, 0 warnings), but running the checker after Phase 4 or Phase 5 would have given earlier confidence on composition correctness.

### Patterns Established

- **`bin/<task>.sh` as operator-facing wrappers** that call `python -m ga_crawler <subcommand>`. Bash owns: HC.io pings, flock, log redirect, exit-code semantics, .env loading. Python owns: business logic, parsing, persistence, delivery. Hard separation; HC pings live in bash so they fire even on Python hard-crash (D-701).
- **Source-lock canary tests** as the cheap insurance for operator-facing files (cron templates, README sections, .env.example values). Substring greps with D-NNN citations in failure messages. Catch verbatim regressions without exercising runtime.
- **Goal-backward Verification.md per phase.** Each phase's VERIFICATION.md is a TRUTH-numbered table with file:line evidence. Forces the verifier to point at a specific commit/line, not gesture at "the implementation."
- **Single `runs.stats` JSON column patched per phase.** All phase results merge into one JSON via atomic patch — no schema changes mid-milestone. v2 adds keys by extending namespace tuples + canary disjointness tests.
- **5-key delivery_status enum + asymmetric ENV handling.** `pending / delivered_business / delivered_ops_only / undelivered_telegram_unreachable / skipped_no_credentials / skipped_already_delivered`. TG_BOT_TOKEN missing = fail-loud exit 2; chat IDs missing = degrade gracefully to ops-only route. Pattern transfers to any external-service integration.
- **D-411 read_run_status skip protocol.** Reused 3 times after creation. Once a primitive proves load-bearing, document it as a phase-invariant and let future phases import it as-is.

### Key Lessons

1. **A 2-day timeboxed spike on the one defining unknown is the highest-leverage move at project start.** Spike outcomes either close conditional scope (the v1 case — IPRoyal, multi-geo, Tier-3 all retired) or expand it with eyes open. Either way the operator gets to allocate energy correctly.
2. **Decision IDs scale where ADRs don't.** ADRs are 1 markdown file per decision and lose searchability past ~30. D-NNN records inline in CONTEXT.md tables stay grep-able through 47 plans and are cheap to cross-reference.
3. **"Zero production Python" can be a phase deliverable.** Phase 7 shipped operator artifacts (bash scripts, cron templates, README) and not a single Python LOC. Source-lock canaries on shape, not behavior. Operator-time verification handled by HUMAN-UAT.md. Cleaner separation than trying to script the operator's runbook into Python.
4. **Run /gsd-secure-phase and /gsd-validate-phase at each phase close, not at milestone close.** Retroactive audits are paperwork on cold code; inline audits are checkpoint discipline. The marginal cost per phase is small; the audit-framework debt at milestone close was painful to acknowledge.
5. **Cold-start a browser fetcher with a warm-up nav.** Empirically necessary for Camoufox; likely necessary for any anti-detect engine. Add to project skill.
6. **Treat operator-manual UAT as `blocked` not `pending`.** Semantically accurate (environment-blocked, not undone work) and keeps the verification debt readable on resume.
7. **Match-rate KPI needs a frozen formula canary at week 1.** D-405 source-locked `ROUND(match_count * 100.0 / denominator, 2)` as a literal substring in the matcher source. If someone "improves" the formula without coordinating with reporter/delivery, the canary trips. Saved future grief.

### Cost Observations

- Model mix: predominantly Opus 4.7 for orchestration (this milestone) and Sonnet 4.6 for executor subagents. No formal cost telemetry.
- Sessions: ~12 inferred from STATE.md activity bursts.
- Notable: parallel subagent dispatch (4-way researcher fan-out in /gsd-new-project, 5-way phase-mapper) materially compressed long-context work. Single-shot integration checker at milestone audit was 65s wall + ~64K tokens — efficient for the breadth covered.

---

## Cross-Milestone Trends

> Tables accumulate across milestones. v1.0 is the seed row.

### Velocity

| Milestone | Phases | Plans | Days | Plans/Day | Test LOC growth |
|-----------|--------|-------|------|-----------|-----------------|
| v1.0 | 7 | 47 | 8 | 5.9 | 0 → 14,769 |

### Audit Verdicts

| Milestone | Audit verdict | Tech-debt items | Reqs closed |
|-----------|---------------|-----------------|-------------|
| v1.0 | tech_debt | 4 (3 SECURITY missing + 1 VALIDATION missing) | 48/48 |

### Patterns That Held Across Milestones

(Seed entry — will populate as v1.1+ ships)

- TBD

### Patterns That Required Revision

(Seed entry — will populate as v1.1+ ships)

- TBD

---
*Last updated: 2026-05-13 — v1.0 archival.*
