# Roadmap: GA Crawler

> Living roadmap. Completed milestones collapse into `<details>` blocks; current milestone phases stay expanded above.

## Milestones

- ✅ **v1.0 Initial Code-Ship** — Phases 1-7 (shipped 2026-05-13). Full record: `MILESTONES.md`. Frozen artifacts: `milestones/v1.0-*.md`.
- 🟢 **v1.1 Parser bug fixes + operator deploy unblock** — Phases 8-11 (active, started 2026-05-13). Goal: fix 3 parser bugs from live-run #13, add live-HTML harness, close v1.0 audit paperwork debt, deploy на Yandex Cloud kz1 + first production cron tick.

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

### 🟢 v1.1 (Active)

- [x] **Phase 8: Parser Bug Fixes** — Complete 2026-05-13. Fixed 3 live-run #13 parser bugs (goldapple volume + brand/name; viled volume_raw) via selectolax 0.4 Lexbor `:contains` + h1 `.brand`/`.name` CSS-class spans (W0 pivot — `<meta itemprop="name">` premise invalidated per 08-01 spike) + `attributes[0].attributes[].name=="Размер"` JSON; added null-rate sanity gate + SMOKE rotation. 5/5 PARSE-FIX reqs closed.
- [ ] **Phase 9: Live-HTML Harness** — syrupy 4.7 HTML snapshot harness + Pydantic write-boundary validation; locks Phase 8 fix retroactively so drift never silently zeros the report again
- [ ] **Phase 10: Audit Paperwork Carryover** — Retroactive SECURITY.md (phases 2/4/6) + VALIDATION.md (phase 4) + audit-verdict flip `tech_debt` → `clean`; parallel-safe with Phases 8-9
- [ ] **Phase 11: Operator Deploy на Yandex Cloud kz1** — First production VPS deploy with `bin/setup-vps.sh`, `load_dotenv` fix, Asia/Almaty TZ, Camoufox×Yandex + egress smokes, first Sunday cron tick, `/gsd-verify-work 7` resume

## Phase Details

### Phase 8: Parser Bug Fixes
**Goal**: Goldapple SKUs gain non-null `volume_raw`/`volume_norm` + clean `brand`/`name` split; viled SKUs gain volume from structured `attributes[]` field — together unblocking matched-pair production and ending empty-Excel deliveries.
**Depends on**: v1.0 (Phases 1-7) shipped
**Requirements**: PARSE-FIX-01, PARSE-FIX-02, PARSE-FIX-03, PARSE-FIX-04, PARSE-FIX-05
**Success Criteria** (what must be TRUE):
  1. Live dry-run against goldapple + viled yields `goldapple_comparable_count > 0` (was 0 in run #13) and matched pairs land in `matches` table (operator-track gating)
  2. `goldapple_volume_norm` non-null rate ≥ 90% on non-volumeless categories (PARSE-FIX-01 acceptance — Plan 08-02)
  3. Invariant canary `assert brand.lower() not in name.lower()` holds across all goldapple snapshots from the dry-run (PARSE-FIX-02 — softened to log-only per 08-01 W0 evidence; Plan 08-03)
  4. Test suite remains green at ~818 tests (803 baseline + ~15-20 new parametrized tests against captured live fixtures)
  5. Null-rate sanity gate (PARSE-FIX-04) actively fails a synthetic regression run injected with >50% null volume, marking it `failed` with reason `parser_drift_null_volume_rate` (Plan 08-05)

**Plans:** 5 plans across 4 waves — all complete 2026-05-13

**Wave 0** *(sequential, blocking — requires operator interaction)*
- [x] 08-01-PLAN.md — W0 30-PDP shape-sampling spike + 3 live fixtures + skill wrap-up

**Wave 1** *(blocked on Wave 0 completion; 08-02 ∥ 08-04 parallel — disjoint files)*
- [x] 08-02-PLAN.md — PARSE-FIX-01 goldapple volume via selectolax 0.4 Lexbor
- [x] 08-04-PLAN.md — PARSE-FIX-03 viled volume via attributes[0].attributes[]

**Wave 2** *(blocked on Wave 1 / 08-02 completion — shared file `goldapple_microdata.py`)*
- [x] 08-03-PLAN.md — PARSE-FIX-02 goldapple brand+name via h1 child-spans (W0 pivot — landed h1-spans strategy, NOT microdata-walk per shape-table evidence; D-816 invariant softened to log-only canary)

**Wave 3** *(blocked on Waves 1+2 completion — gate reads stats produced by 08-02/03/04)*
- [x] 08-05-PLAN.md — PARSE-FIX-04 null-rate gate + PARSE-FIX-05 SMOKE rotation + doc cascade

**Cross-cutting constraints (must_haves shared across 2+ plans):**
- Strict TDD per fix: RED test against `_live-2026-05-13-*.html` fixture BEFORE production code; atomic RED+GREEN commits (CONTEXT.md D-811)
- selectolax pin `>=0.4.7,<0.5`; Lexbor import STRICTLY LOCAL inside helpers; existing 60+ Modest-backed parser tests stay green (D-805/806/807)
- All 5 plans must keep existing 803-test baseline green; aggregate suite target ~818-833 tests post-Phase 8
**Pitfall mitigation**: Mandatory 30-PDP shape-sampling sub-spike BEFORE any code touches `parsers/goldapple_microdata.py` or `parsers/viled_nextdata.py` (output to `.planning/spikes/v1.1-brand-name-shapes/`) — prevents over-fitting to single STEREOTYPE PDP screenshot; selectolax 0.3→0.4 upgrade required for Lexbor `:contains` primitive.

### Phase 9: Live-HTML Harness
**Goal**: A repeatable, drift-detecting test surface where parsers are exercised against captured live HTML snapshots — so future fixture-vs-live drift (the v1.0 gap that masked run #13 bugs) fails CI loudly instead of silently producing empty Excels.
**Depends on**: Phase 8 (need known-good fixtures + fixed parsers to lock in retroactively)
**Requirements**: TEST-HARNESS-01, TEST-HARNESS-02, TEST-HARNESS-03, TEST-HARNESS-04, TEST-HARNESS-05, TEST-HARNESS-06
**Success Criteria** (what must be TRUE):
  1. `pytest -m live` runs end-to-end against live PDPs and asserts both fixed-parser invariants (the "would have caught run #13" test passes against captured STEREOTYPE/Armani-code/Contre-Jour snapshots)
  2. Stale or missing snapshot is a **test failure** (not silent skip) — soundness rule wired via `HTMLSnapshotExtension(SingleFileSnapshotExtension)` with `file_extension="html"`, `WriteMode.TEXT`
  3. Snapshot directory under `tests/fixtures/<retailer>/_live-YYYY-MM-DD-<slug>.html` carries sidecar JSON metadata `{date, url, status, html_size, title, camoufox_version}` AND passes PII canary (no `cf_clearance=`, no `bot\d+:` tokens, no UUID-shaped hc-ping paths) AND stays under 50 MB size budget
  4. Pydantic `RawProduct` validation at `SqliteSnapshotWriter` boundary raises on missing `volume_raw`/`brand` — defense-in-depth complement to PARSE-FIX-04 null-rate gate (TEST-HARNESS-06)
  5. P2 cheap-bundle (B4 brand-coverage quota canary + B5 `python -m ga_crawler capture-fixtures` CLI subcommand) shipped if it lands within phase budget; otherwise explicitly deferred to v1.2 (TEST-HARNESS-04/05 conditional)
**Plans**: TBD
**Pitfall mitigation**: snapshot-PII canary + size-budget canary (<50 MB) wired BEFORE first snapshot commit; missing-snapshot-fails-test soundness rule enforced via syrupy strict mode.

### Phase 10: Audit Paperwork Carryover
**Goal**: Close v1.0 audit's `tech_debt` verdict by producing the four missing artifacts retroactively, flipping the milestone audit verdict to `clean` so the project ships without unresolved paperwork debt.
**Depends on**: nothing (parallel-safe with Phases 8-9 — pure documentation, no code coupling)
**Requirements**: AUDIT-DEBT-01, AUDIT-DEBT-02, AUDIT-DEBT-03, AUDIT-DEBT-04, AUDIT-DEBT-05
**Success Criteria** (what must be TRUE):
  1. `SECURITY.md` exists for Phase 2 (viled crawl + storage) with retroactive threat model + 6/6 mitigation-evidence rows green
  2. `SECURITY.md` exists for Phase 4 (matcher) and Phase 6 (Telegram delivery) with same coverage shape
  3. `VALIDATION.md` exists for Phase 4 (matcher) with Nyquist-compliant coverage matrix against the 465+ existing matcher tests
  4. `milestones/v1.0-MILESTONE-AUDIT.md` carries an in-place verdict-flip annotation `tech_debt` → `clean` dated 2026-05-XX with citations to AUDIT-DEBT-01..04
  5. `/gsd-verify-work` re-run on v1.0 milestone artifacts transitions verdict to `clean` (or operator-equivalent confirmation logged)
**Plans**: TBD
**Pitfall mitigation**: Per PITFALLS.md #10, retroactive paperwork loses fidelity if treated as background work — Phase 10 is a distinct phase, not folded into Phases 8/9/11; existing `/gsd-secure-phase` and `/gsd-validate-phase` skill workflows reused verbatim.

### Phase 11: Operator Deploy на Yandex Cloud kz1
**Goal**: First production deploy on a real VPS (Yandex Cloud kz1) culminating in a real Sunday cron tick that delivers a non-empty Excel report with `match_count > 0` to the business Telegram chat — closing the four blocked Phase 7 UAT items and ending operator-track debt.
**Depends on**: Phase 8 (parsers must be fixed before deploying; otherwise repeat run #13 in production) AND Phase 9 (harness should lock the fix before it ships off the dev box)
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05, DEPLOY-06, DEPLOY-07, DEPLOY-08
**Success Criteria** (what must be TRUE):
  1. Yandex Cloud kz1 VPS reachable via SSH (Ubuntu 24.04, 2 vCPU/4GB/30GB SSD, KZ-region IP, key-only auth) and `bin/setup-vps.sh` runs idempotently end-to-end against it (DEPLOY-01, DEPLOY-02)
  2. Pre-cron-handoff smokes both pass: Camoufox 0.4.11 launches successfully on Yandex Cloud Ubuntu (DEPLOY-05), AND `curl -I` reaches api.telegram.org / hc-ping.com / goldapple.kz / viled.kz from the KZ instance (DEPLOY-06)
  3. First production Sunday cron tick (next 2026-05-XX 23:00 Asia/Almaty) records HC.io `/start` + `/success` pings AND delivers an xlsx attachment with `match_count > 0` to the business chat (DEPLOY-07)
  4. `delivery_status` in `runs.stats` is one of `delivered_business` / `delivered_ops_fallback` (NEVER `skipped_no_credentials` — the D-705 recurrence that burned run #13) — proves DEPLOY-03 `load_dotenv(verbose=True)` fix at `src/ga_crawler/__main__.py` entrypoint
  5. `/gsd-verify-work 7` resume transitions all 4 blocked UAT items in `07-HUMAN-UAT.md` (SC#1 cron timing, SC#5 deliberate-failure E2E, smoke gate, HC↔Telegram integration) from `blocked` to `pass`, closing v1.1 milestone (DEPLOY-08)
**Plans**: TBD
**Pitfall mitigation**: DEPLOY-04 `sudo timedatectl set-timezone Asia/Almaty` BEFORE first cron handoff (Pitfall #7 — Yandex Cloud KZ default Moscow TZ would skew Sunday 23:00 by 3h); DEPLOY-03 `load_dotenv(verbose=True)` at CLI entrypoint (Pitfall #6 — D-705 recurrence prevention); DEPLOY-05/06 pre-cron smokes block handoff if Camoufox×Yandex regresses or KZ-egress fails.

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
| 8. Parser Bug Fixes | v1.1 | 5/5 | Complete | 2026-05-13 |
| 9. Live-HTML Harness | v1.1 | 0/? | Not started | — |
| 10. Audit Paperwork Carryover | v1.1 | 0/? | Not started | — |
| 11. Operator Deploy на Yandex Cloud kz1 | v1.1 | 0/? | Not started | — |

**v1.0 totals:** 7/7 phases complete; 47 plans executed + 3 SKIPPED; 48/48 v1 requirements closed; 803 passing tests.
**v1.1 totals (in-progress):** 1/4 phases complete (Phase 8 closed 2026-05-13); 5/24 reqs closed (PARSE-FIX-01..05); ~830 passing tests after Phase 8 Plan 08-05 GREEN (+ ~12-15 from Plans 08-02/03/04/05 over the 803 v1.0 baseline).

---
*Last updated: 2026-05-13 — Phase 8 closed via Plan 08-05 doc cascade (5/5 PARSE-FIX reqs Complete; Phase 9-11 remain Pending). Previously: v1.0 milestone archived by `/gsd-complete-milestone v1`.*
