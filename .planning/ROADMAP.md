# Roadmap: GA Crawler

> Living roadmap. Completed milestones collapse into `<details>` blocks; current milestone phases stay expanded above.

## Milestones

- ✅ **v1.0 Initial Code-Ship** — Phases 1-7 (shipped 2026-05-13). Full record: `MILESTONES.md`. Frozen artifacts: `milestones/v1.0-*.md`.
- 📋 **v1.1 / v2.0 (TBD)** — pending `/gsd-new-milestone`. Likely scope candidates: viled catalog full-pagination (CRAWL-01 carryover), Docker reproducible deploy (INFRA-V2-04), Camoufox+EU smoke (D-07), KZ-legal/ToS review, fuzzy matcher if v1 strict-key coverage is low, retroactive SECURITY/VALIDATION audits for phases 2/4/6.

## Phases

<details>
<summary>✅ v1.0 Initial Code-Ship (Phases 1-7) — SHIPPED 2026-05-13</summary>

- [x] **Phase 1: Goldapple Reconnaissance Spike** (9/12 plans complete; 3 SKIPPED per spike MEMO) — completed 2026-05-06
  - Decision memo: Tier-2 Camoufox-direct (99/100 from KZ-laptop, no proxy). Vendor identified: GroupIB/F.A.C.C.T. (fingerprint-based). RECON-01..04 closed.
- [x] **Phase 2: Project Skeleton + viled Crawl + Storage** (6/6 plans) — completed 2026-05-07
  - SQLite + SQLModel storage, curl_cffi viled crawler, shared normalizers, brand-aliases.yaml seed, bin/backup.sh. DATA-01..06, CRAWL-01,03,04,05,06, PARSE-01..06, NORM-01..06 closed. 22 reqs.
- [x] **Phase 3: Goldapple Crawl** (9/9 plans) — completed 2026-05-11
  - Camoufox-direct fetcher + warm-up nav, microdata parser, brand-token bucket index (Path A). CRAWL-02 closed. VERIFICATION human_needed (Truth 4 1-hour live run operator-deferred).
- [x] **Phase 4: Matcher + Match-Rate KPI** (6/6 plans) — completed 2026-05-11
  - Strict-key SQL JOIN; denormalized 13-col matches; match-rate KPI with symmetric-filter denominator; sanity-gate P + auto-suggest; `matcher-run` recovery CLI. MATCH-01..04 closed. 11/11 verification truths.
- [x] **Phase 5: Reporter (Excel + Summary)** (6/6 plans) — completed 2026-05-12
  - xlsxwriter 4-sheet workbook with conditional formatting + freeze panes + Russian headers + emoji summary; D-512 ISO-week archive. REPORT-01..06 closed. 6/6 verification truths. Human verification resolved via OOXML inspection.
- [x] **Phase 6: Telegram Delivery + Ops/Business Split** (6/6 plans) — completed 2026-05-12
  - aiogram 3.27 with tenacity wait_chain + TelegramRetryAfter outside-tenacity loop; D-604 4-check first-fail-wins gate; D-605 invariant (Telegram failure ≠ run failure); D-606 6-enum delivery_status. DELIVER-01..05 closed.
- [x] **Phase 7: Scheduler + Observability Hardening** (5/5 plans) — completed 2026-05-12
  - `bin/weekly-run.sh` D-709 (HC.io pings + flock + log redirect); `bin/test-failure-alert.sh` D-706; cron + logrotate templates; README.md 10-section RU operator runbook D-707. SCHED-01..05 closed. Phase 7 ships ZERO production Python.
  - Security audit: 7/7 threats closed (0 open). Nyquist: 11/11 rows green.
  - HUMAN-UAT.md: 4 items blocked on operator Hetzner deploy (by design, not gaps).

**Full milestone record:** `MILESTONES.md` § v1.0
**Audit:** `milestones/v1.0-MILESTONE-AUDIT.md` (verdict: tech_debt — paperwork only, no code blockers)

</details>

### 📋 v1.1 / v2.0 (Planning)

No phases planned yet. The next milestone cycle starts with `/gsd-new-milestone`.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Goldapple Reconnaissance Spike | v1.0 | 9/12 (3 SKIPPED per MEMO) | Complete | 2026-05-06 |
| 2. Project Skeleton + viled + Storage | v1.0 | 6/6 | Complete | 2026-05-07 |
| 3. Goldapple Crawl | v1.0 | 9/9 | Complete | 2026-05-11 |
| 4. Matcher + Match-Rate KPI | v1.0 | 6/6 | Complete | 2026-05-11 |
| 5. Reporter (Excel + Summary) | v1.0 | 6/6 | Complete | 2026-05-12 |
| 6. Telegram Delivery + Ops/Business Split | v1.0 | 6/6 | Complete | 2026-05-12 |
| 7. Scheduler + Observability Hardening | v1.0 | 5/5 | Complete | 2026-05-12 |

**v1.0 totals:** 7/7 phases complete; 47 plans executed + 3 SKIPPED; 48/48 v1 requirements closed; 803 passing tests.

---
*Last updated: 2026-05-13 — v1.0 milestone archived by `/gsd-complete-milestone v1`.*
