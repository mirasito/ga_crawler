# Project Research Summary — v1.1

**Project:** ga_crawler — Competitive Pricing Intelligence (viled.kz vs goldapple.kz)
**Domain:** Python web-scraper milestone — parser bug fixes + live-HTML test methodology + audit paperwork carryover + first operator VPS deploy
**Researched:** 2026-05-13
**Confidence:** HIGH (parser bugs evidence-backed in `v1.1-PARSER-BUG-FINDINGS.md`; library calls validated against Context7 and in-repo fixtures; ops pitfalls reproduce v1.0 D-705 / SCHED-02 lessons)

---

## Executive Summary

v1.0 shipped clean code on `tech_debt` verdict: 803 tests green, but live-run #13 (2026-05-13) revealed three parser bugs — goldapple `volume_norm` 88/88 NULL, goldapple brand/name concatenation (`Armaniarmani code`), viled `volume_raw` = full title — that zeroed the Excel report. The audit also flagged four missing paperwork artifacts (SECURITY.md × 3, VALIDATION.md × 1), and Phase 7 UAT left four items `blocked` pending a real VPS deploy and Sunday cron tick. v1.1 is a **narrow correctness + operations milestone** that closes all three threads without re-architecting v1.0.

Across all four research dimensions (STACK / FEATURES / ARCHITECTURE / PITFALLS) the recommended approach **converges on the same plan**: keep the v1.0 pipe-and-filter monolith untouched; touch only `parsers/goldapple_microdata.py` + `parsers/viled_nextdata.py`; add live-HTML capture as a sibling test surface (NOT in the production pipeline); pay down paperwork in parallel; deploy last with `bin/setup-vps.sh` as a thin wrapper around the existing README §2 procedure. Library changes are minimal — selectolax 0.3 → 0.4 to unlock the Lexbor backend's `:lexbor-contains("ОБЪЁМ" i)` pseudo-selector (solves Bug #1 without library swap), and syrupy as a dev-only dep for HTML snapshot replay. **No infrastructure changes, no new SDKs, no Camoufox rev** (LOCKED at 0.4.11 per Phase 3 D-313).

Top risks are well-understood and pre-mitigated: (1) parser-fix overfitting to the single STEREOTYPE PDP screenshot — answered with a mandatory shape-sampling pre-spike against structured microdata (`<meta itemprop="name">`, `props.pageProps.attributes[].name == "Размер"`) rather than regex-on-title; (2) syrupy snapshots going stale — answered with `--snapshot-update` workflow and "missing snapshot = test failure" soundness rule; (3) Hetzner-vs-Yandex-Cloud-KZ provider choice — answered Hetzner-by-default (v1.0 RECON-01 already proved Camoufox-direct works from EU, no proxy needed), Yandex Cloud kept as documented fallback. v1.0 D-705 .env-loading recurrence and SCHED-02 cron-TZ traps are both wired into Phase 5 prevention.

---

## Key Findings

### Recommended Stack

v1.0 stack LOCKED. v1.1 adds two libraries, zero infrastructure.

**v1.1 additions / upgrades:**
- **selectolax** `>=0.3,<0.4` → `>=0.4.7,<0.5` — unlocks Lexbor backend (`from selectolax.lexbor import LexborHTMLParser`) with `:lexbor-contains("ОБЪЁМ" i)` pseudo-class. Exact primitive for Bug #1 (find label cell, walk to sibling holding `78`). Drop-in; Modest backend still works.
- **syrupy** `>=4.7,<5.0` (dev-only) — pytest snapshot plugin with `SingleFileSnapshotExtension`. Subclass with `file_extension = "html"`, `_write_mode = WriteMode.TEXT`. **Soundness rule:** missing snapshot = test failure (not just diff) — directly addresses run #13 root cause.

**LOCKED (do NOT change):** Camoufox 0.4.11 (Phase 3 D-313 — smoke probe `camoufox_version_expected` invariant); curl_cffi 0.15; SQLite + SQLModel.

**Rejected for v1.1:** `pytest-recording` / VCR.py (hooks urllib3; curl_cffi bypasses urllib3, Camoufox bypasses Python HTTP entirely — silently records nothing); `lxml` + `parsel` (5 MB native dep, zero incremental capability over selectolax 0.4); Patchright revisit (LOCKED out per D-313).

**Hosting:** Default Hetzner CX22 EU (€4.50–€8/mo, RECON-01 verified 99/100 from Hetzner EU). Fallback Yandex Cloud kz1 — vanilla Ubuntu + SSH confirmed (no proprietary SDK), but requires KZ/RU-resident business for billing.

### Expected Features

Scope decomposes into **four explicit buckets**, 1:1 with PROJECT.md active requirements.

**Must have (P1):**
- **Bucket A — Parser fixes:** A1 goldapple volume via Lexbor `:contains`; A2 brand/name via `<meta itemprop="name">`; A3 viled volume via `attributes[].name == "Размер"`; A4 null-rate gate validation; A5 match-rate floor alert.
- **Bucket B — Live-HTML harness:** B1 syrupy infrastructure; B2 snapshot metadata; B3 `assert html == html_snapshot`; B6 Pydantic validation at `SqliteSnapshotWriter` boundary (defense-in-depth complement to A4).
- **Bucket C — Paperwork:** C1–C3 SECURITY.md for phases 2/4/6; C4 VALIDATION.md phase 4; C5 audit-verdict flip `tech_debt` → `clean`.
- **Bucket D — Operator deploy:** D1 VPS provisioned; D2 deploy via README §2 with new `bin/setup-vps.sh`; D3 smoke; D4 first Sunday cron tick; D5 deliberate-failure verify; D6 HC↔Telegram; D7 backup verify; D8 `/gsd-verify-work 7` resume flips 4 blocked UAT items.

**Should have (P2 cheap-bundle):** B4 brand-coverage quota; B5 fixtures-refresh CLI (6th subcommand); smoke-probe URL rotation; VPS hardening doc + HC.io status URL.

**Anti-features (explicitly OUT — defer to v2):** viled SSR pagination; Docker; Postgres migration; fuzzy matching; second competitor; web dashboard; real-time/daily monitoring; KZ-legal review; ML/image capture.

### Architecture Approach

v1.0 clean pipe-and-filter monolith with strict module boundaries — v1.1 MUST NOT re-architect. Three orthogonal surgical changes + one operator track.

**Major components touched:**
1. **`parsers/goldapple_microdata.py`** — REPLACE line 358 `raw_volume_text = name or None` with `_extract_volume_block(tree)` helper (selectolax 0.4 Lexbor); REPLACE line 327–332 name extraction with sibling `<meta itemprop="name">` read inside product `itemscope`. Both fixture-verified against `_debug-product-page.html`.
2. **`parsers/viled_nextdata.py`** — REPLACE line 215 `raw_volume_text=name` with `_extract_volume_from_nextdata(item, a0)` reading `props.pageProps.attributes[].name == "Размер"`. Clothing fixture confirms shape; 30-min Wave-0 probe against live beauty PDP confirms exact JSON path.
3. **`tests/live/test_parser_drift.py`** (NEW) — sibling capture surface behind `@pytest.mark.live` (already declared unused in `pyproject.toml:51` — purpose-built). Does NOT enter production pipeline.
4. **`scripts/capture_fixtures.py`** (NEW) + `tests/fixtures/<retailer>/_live-YYYY-MM-DD-<slug>.html` — retailer-grouped slicing preserved.
5. **`bin/setup-vps.sh`** (NEW) — thin idempotent wrapper around README §2 8-step procedure. Same shape as existing `bin/weekly-run.sh` / `bin/backup.sh`. Provider-agnostic.

**Internal contract preserved:** dispatcher dict shape (`parsers/dispatcher.py:51`) unchanged; `volume_raw` field already exists at line 64 — only its source changes. No schema migration, no matcher rewrite.

**Backfill decision: forward-only — do NOT backfill runs 1–13** (HTML is gone; matcher idempotent; auto-suggest 4-week median rolls garbage out by run #17). Single-line annotation in `MILESTONES.md`.

**Test count impact:** 803 → ~818 (15 new tests; no deletions).

### Critical Pitfalls

1. **Parser-fix overfitting to single PDP.** STEREOTYPE regex breaks on TOM FORD, Dolce & Gabbana, 19-69 capri, НАТУРА СИБИРИКА. **Prevention:** mandatory 30-PDP shape-sampling sub-phase BEFORE code; prefer structured microdata fields over title regex; invariant canary `assert brand.lower() not in name.lower()`.
2. **Stale snapshots going silent.** v1.0 fixtures captured May 5–11 didn't cover live May 13 PDPs. **Prevention:** syrupy `--snapshot-update` + missing-snapshot-fails-test soundness + scheduled `capture-fixtures` CLI.
3. **PII / secrets in committed snapshots.** Snapshot scope is HTML body only (not headers/cookies); pre-commit `gitleaks`; canary scans for `cf_clearance=`, `bot\d+:`, UUID-shaped hc-ping paths.
4. **D-705 .env-loading recurrence.** Run #13 already burned us. **Prevention:** `load_dotenv(verbose=True)` at CLI entrypoint (`src/ga_crawler/__main__.py`), idempotent; clean-shell canary test.
5. **Cron TZ gotcha — Yandex Cloud KZ default Moscow.** `CRON_TZ` is file-scoped; bash `date` and Python `datetime.now()` use system TZ. **Prevention:** README §2 step 1.5 adds `sudo timedatectl set-timezone Asia/Almaty`; reject naive `datetime.now()` in v1.1 new code.

See PITFALLS.md for full 10-pitfall list (drift detection bypass, Camoufox×Yandex compat, snapshot repo bloat, JS-race-flake hiding drift, retroactive paperwork losing fidelity).

---

## Implications for Roadmap

**4 phases minimum.** FEATURES and ARCHITECTURE both propose 4; PITFALLS suggests 6 but the extras (shape-sampling spike, drift-detection-extensions) fold cleanly into Phase 1 sub-task and v1.2 defer respectively.

### Convergence Across Research Files

All four agents land on the same phase order: **parser-fix → harness → paperwork → deploy**. Justifications:

| Dimension | "Why parser-fix first" |
|-----------|----------------------|
| STACK | selectolax 0.4 needed for Bug #1; library change must precede test rebuild |
| FEATURES | Bucket A is sole blocker for Bucket D — deploying broken parsers just produces more empty Excels |
| ARCHITECTURE | Harness with no fix to test has zero signal |
| PITFALLS | Sampling-first protocol must precede code; harness pins fix retroactively |

### Phase 1: Parser Bug Fixes (Bucket A + selectolax upgrade)

**Rationale:** Only code-change phase; strongest invariant (tests stay green); harness needs known-good captures to lock in retroactively.

**Delivers:** selectolax bump; 30-PDP shape-sampling spike (mandatory pre-code, output to `.planning/spikes/v1.1-brand-name-shapes/`); goldapple volume + brand/name fixes; viled volume_raw fix (with 30-min Wave-0 probe); 3 new live fixtures (`_live-2026-05-13-{stereotype,armani-code,contre-jour}.html`); ~15 parametrized tests; invariant canary; A4/A5; smoke-probe URL rotation in `gates.py:36`.

**Verification gate:** ~818 tests green; live dry-run yields `goldapple_comparable_count > 0`; `goldapple_volume_norm` non-null rate ≥ 90% for non-volumeless categories.

### Phase 2: Live-HTML Harness (Bucket B + syrupy)

**Rationale:** Locks Phase 1 fix retroactively. New fixtures captured during Phase 1 ARE evidence the fix works; Phase 2 formalizes as repeatable.

**Delivers:** syrupy dev-dep; `HTMLSnapshotExtension`; `scripts/capture_fixtures.py`; new `python -m ga_crawler capture-fixtures` CLI subcommand (6th — update Phase 7 source-locked canary); `tests/live/test_parser_drift.py` with `@pytest.mark.live`; B6 Pydantic validation at writer boundary; snapshot-PII canary; snapshot size budget canary (<50 MB).

**Verification gate:** `pytest -m live` runs end-to-end; regression test loads Armani/STEREOTYPE/Contre-Jour snapshot and asserts fixed parser produces correct output (the "would have caught it" test).

**P2-bundle-if-cheap:** B4 brand-coverage quota; B5 weekly schedule.

### Phase 3: Audit Paperwork Carryover (Bucket C)

**Rationale:** Fully independent — pure documentation, no code coupling. Per Pitfall #10, retroactive paperwork loses fidelity if treated as background work — must be distinct phase.

**Delivers:** SECURITY.md for phases 2/4/6 via `/gsd-secure-phase`; VALIDATION.md phase 4 via `/gsd-validate-phase`; verdict-flip annotation in `milestones/v1.0-MILESTONE-AUDIT.md`.

**Verification gate:** `/gsd-verify-work` transitions v1.0 verdict `tech_debt` → `clean`.

**Parallel-safe:** can run alongside Phase 1 or 2 by a separate workstream.

### Phase 4: Operator Deploy + First Production Cron Tick (Bucket D)

**Rationale:** Ships whatever code is on main. D4 calendar-bound (next Sunday after D1–D3 land); plan v1.1 close at a Sunday boundary.

**Delivers:** VPS provisioned (Hetzner default; Yandex fallback); `bin/setup-vps.sh` + structural canary test; `load_dotenv(verbose=True)` at CLI entrypoint (Pitfall #6 / D-705); README §2 step 1.5 `timedatectl set-timezone Asia/Almaty` (Pitfall #7); D2/D3/D5/D6/D7 ops verification; if Yandex Cloud → Camoufox launch-smoke before cron handoff + `curl -I` to hc-ping.com/api.telegram.org/goldapple.kz; D4 first Sunday cron tick; D8 `/gsd-verify-work 7` resume.

**Verification gate:** Sunday Telegram delivery contains non-empty xlsx with `match_count > 0`; HC `/start` and `/success` pings recorded; 4 UAT items flip to `pass`; milestone closes.

### Phase Ordering Rationale

- Parser-fix FIRST (only code; harness needs fix to pin)
- Harness SECOND (locks fix retroactively; cannot precede Phase 1)
- Paperwork PARALLEL (no code coupling; Pitfall #10 forces distinct phase)
- Deploy LAST (ships main; D4 calendar-bound)

### Research Flags

**Needs research during planning:**
- **Phase 1** — 30-PDP shape-sampling sub-spike (≤2h): exact `:lexbor-contains()` literal whitespace/case for goldapple volume; viled `props.pageProps.item.attributes` path on beauty PDPs (clothing fixture confirms shape, beauty needs verification).
- **Phase 4** — provider-choice (Hetzner vs Yandex Cloud KZ). v1.0 RECON-01 proved Camoufox-direct works from EU at 99/100 but didn't compare providers head-to-head. Default → Hetzner unless smoke regresses.

**Standard patterns (skip research-phase):**
- **Phase 2** — syrupy well-documented (Context7-verified); `SingleFileSnapshotExtension` subclass is 6-line addition.
- **Phase 3** — pure paperwork via existing `/gsd-secure-phase` and `/gsd-validate-phase` workflows.

---

## What's Already Locked (Decision-Free Going Into Planning)

- selectolax `>=0.4.7,<0.5` upgrade (Lexbor backend)
- syrupy `>=4.7,<5.0` (dev-only) for HTML snapshot replay
- **NO architecture changes** — pipe-and-filter monolith preserved
- **Forward-only — no backfill** of runs 1–13
- **`bin/setup-vps.sh` thin wrapper** (NOT cloud-init / Terraform / Ansible)
- Camoufox 0.4.11 LOCKED (Phase 3 D-313)
- SQLite stays (Postgres triggers not tripped)
- Strict-key matching stays (fuzzy deferred to v2)

## Open Questions That Block Roadmapping

The user must decide before roadmapper runs:

1. **Hetzner CX22 EU vs Yandex Cloud kz1.** Recommended default: **Hetzner.** Decision can be deferred to deploy-time if pre-deploy smoke from Hetzner EU passes.
2. **Viled volume Wave-0 probe — P1 sub-task or separate phase?** Recommended: **P1 sub-task** (~1h impact; no calendar impact).
3. **Smoke-probe URL rotation — Phase 1 or deferred?** Recommended: **bundle into Phase 1** (~30 min; future runs benefit immediately).
4. **B4 brand-coverage + B5 fixtures-refresh — P1 or P2?** Recommended: **P2** — bundle into Phase 2 if it lands quickly; otherwise defer to v1.2.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | selectolax 0.4 + Lexbor + syrupy Context7-verified; Yandex Cloud kz1 vanilla-Ubuntu confirmed against vendor docs; in-repo fixtures confirm microdata shapes |
| Features | HIGH | Parser bugs evidence-backed (DB samples + live PDP screenshots); harness pattern corroborated across syrupy + Pydantic + Scrapy-Testmaster literature; 4-bucket decomposition maps 1:1 to PROJECT.md active reqs |
| Architecture | HIGH | File-line references verified via direct code reads; `pyproject.toml:51` `live` marker already declared unused (purpose-built); forward-only backfill grounded in `strict_key.py` D-410 idempotency + `gates.py` 4-week median |
| Pitfalls | HIGH on parser-overfit + snapshot-stale + D-705 + cron-TZ (multi-source 2024–2026 retros + v1.0 already-burned evidence); MEDIUM on Yandex×Camoufox compat (region 2024 launch, limited corpus); MEDIUM on HC.io reachability from KZ |

**Overall confidence: HIGH.**

### Gaps to Address During Planning

- Exact `:lexbor-contains()` literal for goldapple volume label — resolve via syrupy live capture in Phase 1 (15 min)
- Viled `props.pageProps.item.attributes` exact JSON path for beauty PDPs — resolve via syrupy live capture (15 min)
- Yandex Cloud kz1 Ubuntu 24.04 availability — verify at deploy time in console (no functional impact; uv installs Python 3.12 either way)
- Goldapple geo-sensitivity (Hetzner EU vs KZ IP) — resolve with one Camoufox smoke probe from each before committing deploy target

---

## Sources

**Primary (HIGH):**
- Context7 `/syrupy-project/syrupy` — `SingleFileSnapshotExtension` API, `WriteMode.TEXT`, missing-snapshot soundness
- Context7 `/websites/selectolax_readthedocs_io_en` — `:lexbor-contains("text" i)`, `LexborSelector.text_contains`
- Yandex Cloud official docs — [compute/vm-create/create-linux-vm](https://yandex.cloud/en/docs/compute/operations/vm-create/create-linux-vm)
- In-repo fixtures — `tests/fixtures/goldapple/_debug-product-page.html` (microdata); `tests/fixtures/viled/viled-pdp-multipack.html` (`{name: "Размер", value: "200мл + 200мл + 250мл"}`)
- `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` — DB samples + live PDP screenshots
- v1.0 `RETROSPECTIVE.md` § "What Was Inefficient" #4, #5

**Secondary (MEDIUM):**
- [DCD: Yandex launches kz1 in Karaganda](https://www.datacenterdynamics.com/en/news/yandex-launches-new-cloud-region-in-kazakhstan/)
- [Bright Data: Web Scraping with curl_cffi (2026)](https://brightdata.com/blog/web-data/web-scraping-with-curl-cffi)
- [Simon Willison: Snapshot testing with Syrupy](https://til.simonwillison.net/pytest/syrupy)
- [Stop Silent Scraper Failures: Pydantic Layout Change Detection](https://dev.to/withatte/stop-silent-scraper-failures-using-pydantic-for-instant-layout-change-detection-4p1k)

**Inherited from v1.0 (LOCKED):** Python 3.12, uv 0.11.x, Camoufox 0.4.11, curl_cffi 0.15, SQLModel 0.0.24, pandas 2.2, xlsxwriter 3.2, aiogram 3.27, structlog 25, tenacity 9, pydantic 2.10, pytest 8, respx 0.21.

---
*Research completed: 2026-05-13*
*Ready for roadmap: yes*
