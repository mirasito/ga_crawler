# Milestones: GA Crawler

> Living record of shipped milestones. Each entry is appended on `/gsd-complete-milestone`.

---

## v1.0 — Initial Code-Ship (2026-05-13)

**Status:** ✅ Shipped
**Tagged:** v1.0
**Audit verdict:** tech_debt (paperwork only — no code blockers; full report at `milestones/v1.0-MILESTONE-AUDIT.md`)

### Delivered

A working end-to-end weekly competitive-pricing crawler that parses viled.kz and goldapple.kz, matches SKUs on `brand+name+volume`, computes price deltas, ships an Excel report + Telegram summary, and runs autonomously under cron with Healthchecks.io dead-man's-switch monitoring.

### Stats

| Metric | Value |
|--------|-------|
| Phases | 7/7 complete |
| Plans | 47 executed (9 Phase 1 + 6 Phase 2 + 9 Phase 3 + 6 Phase 4 + 6 Phase 5 + 6 Phase 6 + 5 Phase 7) |
| Plans SKIPPED | 3 (Phase 1: 01-03 IPRoyal trial, 01-09 multi-geo proxy, 01-10 Tier-3 — retired per spike MEMO 2026-05-06 after Camoufox-direct lock proved 99/100) |
| Requirements closed | 48/48 |
| Commits | 284 |
| Timeline | 2026-05-05 → 2026-05-13 (~8 days) |
| Production LOC | 8,258 Python + 209 Bash |
| Test LOC | 14,769 Python |
| Test suite | 803 passed, 1 skipped, 0 failed |
| Branching | none (single-trunk on `master`) |

### Key Accomplishments

1. **Phase 1 — Goldapple Reconnaissance Spike (MEMO-approved 2026-05-06):** Decided Tier-2 Camoufox-direct as the anti-bot strategy after 99/100 success rate from KZ-laptop without proxy or IP rotation. Vendor identified as GroupIB/F.A.C.C.T. (fingerprint-based, not IP-rep-based). Retired conditional plans 01-03/09/10 because fingerprint solved the gate alone.
2. **Phase 2 — Project Skeleton + viled Crawl + Storage:** SQLite + SQLModel storage with WAL + atomic JSON-patch lifecycle; curl_cffi viled crawler with __NEXT_DATA__ parser; shared normalizer modules (brand/name/volume); brand-aliases.yaml seed with 58 brands + 46 Cyrillic aliases; bin/backup.sh online .backup + 4-rotate retention. 22 requirements closed.
3. **Phase 3 — Goldapple Crawl:** Camoufox-direct fetcher with warm-up nav (gap-closure for cold-start Loading race); microdata parser with priceType-aware extraction; brand-token bucket index (Path A longest-prefix-in-whitelist) closes CRAWL-02 BLOCKER. CRAWL-02 closed; 1-hour live run operator-deferred.
4. **Phase 4 — Matcher + Match-Rate KPI:** Strict-key SQL JOIN (brand+name+volume); denormalized 13-column matches table; match-rate KPI with symmetric-filter denominator (10-key stats namespace); sanity-gate P + log-only auto-suggest; standalone `matcher-run --run-id N` recovery CLI. 4 requirements closed; 11/11 verification truths green.
5. **Phase 5 — Reporter (Excel + Summary):** xlsxwriter 4-sheet workbook with 3-color conditional formatting + freeze panes + autofilter; Russian headers + emoji summary (📊 📦 🎯 🆕 💸 🔝); D-512 ISO-week archive with atomic write; standalone `report-run` CLI; 6 requirements closed; human verification resolved via programmatic OOXML inspection.
6. **Phase 6 — Telegram Delivery + Ops/Business Split:** aiogram 3.27 async client with tenacity wait_chain(5,15,45) + TelegramRetryAfter outside-tenacity loop; D-604 4-check first-fail-wins gate; D-605 invariant (Telegram failure ≠ run failure); D-606 6-enum delivery_status; D-608 idempotency + --force + --dry-run; 5 requirements closed.
7. **Phase 7 — Scheduler + Observability Hardening:** Ships ZERO production Python — operator-facing artifacts only. `bin/weekly-run.sh` with HC.io pings + flock advisory lock + log redirect + 5 reserved exit codes; `bin/test-failure-alert.sh` D-706 SC#5 orchestrator; `/etc/cron.d/ga_crawler` D-708 cron template; logrotate D-705 weekly keep-13; README.md 10-section RU operator runbook D-707. 5 requirements closed; 7/7 security threats closed (mitigated + accepted with documented rationale); Nyquist-compliant.

### Architectural Invariants Established

- **Single weekly-run pipeline:** `bin/weekly-run.sh` → `python -m ga_crawler weekly-run` → `run_weekly()` composes (viled_run → goldapple_run → matcher_run → reporter_run → delivery_run). Each phase patches a disjoint stats namespace (`viled.*`, `goldapple.*`, `match.*`, `report.*`, `deliver.*`) via single-call atomic `patch_stats` (Pitfall 6). 5-way pairwise disjoint canary enforces.
- **Storage cohesion:** Snapshots table populated by both viled + goldapple crawlers via same `SqliteSnapshotWriter`; `v_current_snapshots` VIEW; matches table read by reporter; `runs.stats` JSON merged via atomic patches.
- **Failure propagation:** D-411 read_run_status skip protocol reused by 3 downstream phases (matcher, reporter, delivery). D-605 invariant: Telegram failure never changes run.status.
- **CLI surface:** Exactly 5 subcommands (`weekly-run`, `goldapple-smoke`, `matcher-run`, `report-run`, `deliver-run`); canary source-locks the count.

### Key Decisions (selected; full log in archived ROADMAP / phase CONTEXT files)

- **D-13/D-15:** Tier-2 Camoufox-direct is the goldapple anti-bot strategy. No proxy needed from KZ-laptop. (2026-05-06, ✓ Good)
- **D-201:** Sanity gate `sanity_gate_n=100` after each crawl. (✓ Good)
- **D-218:** Parse-quality gate FIRST (`null_rate ≤ 5%`), sanity-N gate SECOND. (✓ Good)
- **D-401:** Matches table is denormalized 13-column shape, not normalized junction. (✓ Good — simplified reporter queries)
- **D-405:** Match-rate KPI formula frozen with source-locked canary at week 1. (✓ Good)
- **D-503/504:** Russian headers + emoji summary template golden-file canary. (✓ Good)
- **D-605:** Telegram failure ≠ run failure. (✓ Good — keeps Healthchecks signal clean)
- **D-606:** 6-enum delivery_status. (✓ Good)
- **D-701:** Healthchecks pings live in bash wrapper, NOT Python (hard-crash coverage). (✓ Good)
- **D-710:** Docker deferred to v2 (INFRA-V2-04 backlog) due to Camoufox Firefox 135 ↔ Playwright image incompatibility. (— Pending v2 review)

### Tech Debt Carried Forward

- **Audit-framework gaps:** Phases 02, 04, 06 lack SECURITY.md; Phase 04 lacks VALIDATION.md. Paperwork on already-shipped tested code (no expected vulnerabilities; phases passed VERIFICATION at higher bar). Defer to v1.1 cleanup or run retroactively via `/gsd-secure-phase` / `/gsd-validate-phase`.
- **Phase 7 HUMAN-UAT.md operator items (4 blocked):** SC#1 cron timing, SC#5 deliberate-failure E2E, smoke gate, HC↔Telegram integration. Resume via `/gsd-verify-work 7` post Hetzner CX22 deploy.
- **CRAWL-01 viled catalog pagination beyond page 1:** v1 ships page-1-only (120 SKUs across both /men/catalog/1310 + /women/catalog/1310 = above sanity_gate_n=100 floor). Full pagination deferred — SSR ignores `?page=N` and 9 other URL conventions per live probe 2026-05-07. Phase 3/7 ops backlog.
- **INFRA-V2-04 Docker image (v2 backlog):** Custom base image required because Camoufox Firefox 135 incompatible with mcr.microsoft.com/playwright/python:v1.57.0-noble Chromium-based.
- **Camoufox+EU smoke from Hetzner:** If `goldapple-smoke` regresses from EU IP, revive D-08 IPRoyal trial. Operator concern at first production cron.
- **KZ-legal review (30-min with lawyer):** Phase 7 ops backlog — bundle = tos-audit.md + viled-privacy.txt + both *-robots.txt snapshots + GroupIB/F.A.C.C.T. vendor flag.

### Known Deferred (acknowledged at close)

| Category | Item | Status |
|----------|------|--------|
| operator-uat | 07-HUMAN-UAT.md SC#1 cron timing | blocked — prior-phase (Hetzner deploy) |
| operator-uat | 07-HUMAN-UAT.md SC#5 deliberate-failure E2E | blocked — third-party (Telegram + HC.io) |
| operator-uat | 07-HUMAN-UAT.md smoke gate | blocked — prior-phase (VPS provisioning) |
| operator-uat | 07-HUMAN-UAT.md HC↔Telegram integration | blocked — third-party (HC.io UI setup) |
| audit-framework | SECURITY.md for phases 02, 04, 06 | deferred — no expected vulnerabilities |
| audit-framework | VALIDATION.md for phase 04 | deferred — 465+ tests already exist |

### Next Milestone Operator Path

1. Provision Hetzner CX22 EU (Ubuntu 24.04 LTS)
2. Install per README.md §2 (8 steps: useradd, uv install, uv sync, playwright install firefox, cp deploy/* to /etc/cron.d + /etc/logrotate.d, `.env` with TG_BOT_TOKEN + TG_*_CHAT_ID + HC_PING_URL, chmod 0600 .env)
3. Smoke gate: `sudo -u ga_crawler bin/weekly-run.sh --viled-only --sanity-gate-n 1`
4. First Sunday production cron tick (Sunday 23:00 Asia/Almaty → Monday ~02:00–03:00 Almaty report arrival)
5. Deliberate-failure verification: `sudo -u ga_crawler bin/test-failure-alert.sh`
6. Resume `/gsd-verify-work 7` to flip 4 blocked UAT items to pass

### Archives

- `milestones/v1.0-ROADMAP.md` — frozen v1 phase list and goals
- `milestones/v1.0-REQUIREMENTS.md` — frozen v1 traceability table (48 REQ-IDs)
- `milestones/v1.0-MILESTONE-AUDIT.md` — gsd-audit-milestone v1 audit report
