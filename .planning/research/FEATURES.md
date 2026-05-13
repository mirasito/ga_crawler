# Feature Research — v1.1

**Domain:** Subsequent milestone for ga_crawler — parser-bug fixes, live-HTML test harness, audit-paperwork carryover, operator deploy
**Researched:** 2026-05-13
**Confidence:** HIGH (parser bugs are evidence-backed in `v1.1-PARSER-BUG-FINDINGS.md`; harness patterns corroborated across VCR.py, pytest-recording, Scrapy-Testmaster, snapshot-testing literature; operator-UAT checklist already drafted in `07-HUMAN-UAT.md` from v1.0)

---

## Framing — What v1.1 Actually Is

v1.0 shipped with audit verdict **`tech_debt`** — code clean, paperwork incomplete, three parser bugs discovered in live-run #13. v1.1 is a **narrow correctness + operations milestone**:

1. Fix three parsers (goldapple volume, goldapple brand/name, viled volume_raw) so the Monday Excel actually contains matched rows.
2. Install a **live-HTML test methodology** so fixture-vs-live drift cannot silently zero out the report a second time.
3. Pay down paperwork debt (SECURITY.md × 3, VALIDATION.md × 1) flagged by v1.0 audit.
4. Stand the pipeline up on a VPS and complete the four `blocked` UAT items in `07-HUMAN-UAT.md` so the first production cron tick on a real Sunday closes v1.1.

Scope discipline: this milestone does **NOT** revisit v1.0 feature scope (no pagination, no Docker, no fuzzy matching, no second competitor). Anything outside the four buckets above is deferred to v2.

Mental model: v1.0 was "build the thing." v1.1 is "make the thing produce correct data on a real schedule, with tests that would have caught the bugs we shipped, and the paperwork the auditor asked for."

---

## Feature Landscape

### Table Stakes (Must Ship in v1.1)

Each row below is mandatory: missing it means either the Excel still ships empty, the v1.0 audit findings remain open, or operator deploy stays in `blocked` UAT limbo.

#### Bucket A — Parser Fixes (the bugs that made run #13's Excel empty)

| Feature | Why Required | Complexity | Notes / v1.0 dependency |
|---------|--------------|------------|--------------------------|
| **A1. Goldapple volume extraction from structured PDP block** | 78/78 SKU in run #13 had `volume_raw=NULL` → matcher produced zero comparable rows → empty Excel. Bug #1 in `v1.1-PARSER-BUG-FINDINGS.md`. | M | Touches `src/ga_crawler/parsers/goldapple_*.py` (microdata path from Phase 3). Live PDP renders volume as flexbox `<div>`s with literal label "ОБЪЁМ / МЛ" — must move from microdata/`itemprop="size"` selector to positional/textual selector. Dependency on v1.0: `SqliteSnapshotWriter` schema + `volume_norm` normalizer (unchanged — only feed it the right string). |
| **A2. Goldapple brand / name separation** | Names like `Armaniarmani code` and empty `brand` column poison the matcher key. Bug #2. | M | Same module as A1. Parser currently appears to concatenate two adjacent text nodes into a single `name` string. Fix likely lives at the title-extraction site, not in the normalizer. v1.0 `brand-aliases.yaml` (58 brands, 46 Cyrillic aliases) stays unchanged — fix is upstream of alias resolution. |
| **A3. Viled volume_raw distinct from name** | `volume_raw` currently equals the entire `name` verbatim; volume only survives when literally embedded as `"100 мл"` in the title. Bug #3. | S–M | `src/ga_crawler/parsers/viled_nextdata.py`. Needs spike against the live `__NEXT_DATA__` payload to find a dedicated volume field; if no such field exists, document the limitation explicitly in the normalizer + emit an audit-log line per parse so the count is visible. v1.0 normalizer logic survives. |
| **A4. Hard-fail / null-rate gate enforcement validation** | v1.0 has D-218 "parse-quality gate FIRST (`null_rate ≤ 5%`)" but run #13 finished `status=success` despite 100% null `volume_norm` on goldapple. Pitfall #2 from PITFALLS.md ("silent parser drift") materialized exactly as documented. | S | Likely a sanity-gate threshold or scope bug — verify the gate runs against `volume_norm` (not just `current_price`), and that `goldapple_comparable_count=0` short-circuits the run to `failure`. v1.0 D-411 `read_run_status skip protocol` is the right place to extend. |
| **A5. Match-rate floor alert in delivery** | v1.0 ships match-rate KPI (Phase 4 D-405) but did not alert when it crashed to zero. Should at minimum tag the Telegram business message with an exclamation-state when match-rate falls below floor (e.g. 30%). | S | Lives in delivery message template (Phase 6). Does NOT change D-605 invariant — Telegram still doesn't fail the run, but the human-readable summary surfaces the regression. |

#### Bucket B — Live-HTML Test Harness (so v1.1 bugs don't recur)

The v1.0 audit identified the methodology gap explicitly: 803 unit tests all green, but fixtures captured at Phase 2/3 build time (May 5–11) didn't cover the PDP shapes live on May 13. Industry-standard pattern for this gap is **cassette-based HTTP recording + scheduled re-capture + schema validation**. See [pytest-recording (VCR.py for pytest)](https://github.com/kiwicom/pytest-recording), [Scrapy-Testmaster](https://github.com/ThomasAitken/Scrapy-Testmaster), and [Pydantic for layout-change detection](https://dev.to/withatte/stop-silent-scraper-failures-using-pydantic-for-instant-layout-change-detection-4p1k).

| Feature | Why Required | Complexity | Notes / v1.0 dependency |
|---------|--------------|------------|--------------------------|
| **B1. Cassette capture + replay infrastructure** | Foundation for everything in Bucket B. Lets us save a real PDP as a fixture file with metadata (URL, captured-at timestamp, SHA256), then replay it under pytest. | M | Two viable patterns: (a) **VCR.py + pytest-recording** for the curl_cffi viled path (records full HTTP cassettes); (b) **raw `.html` files with sidecar `.json` metadata** for the Camoufox/Playwright goldapple path (VCR doesn't intercept browser traffic cleanly — write a thin helper that calls Camoufox + saves `page.content()` to disk). Pick (b) for goldapple to avoid a VCR-vs-browser detour; (a) for viled is cheap. |
| **B2. Cassette schema: live-captured-at YYYY-MM-DD + brand + URL + SHA256** | Without metadata we cannot answer "is this fixture stale?" or "do we cover Armani-branded SKUs?" Required for B3 + B4. | S | One JSON sidecar per HTML file. Schema: `{retailer, url, captured_at, brand, sku_id, html_sha256, parser_version}`. Stored under `tests/fixtures/live/{retailer}/{brand}/{sku_id}.{html,json}`. Aligns with v1.0 `brand-aliases.yaml` taxonomy. |
| **B3. Assertion API: parser output vs expected snapshot** | The "did parsing produce the right fields" test. Without this the cassettes are inert files. | S | Either approval-test style (parser output checked into `expected/*.json`, diff is the test) via [syrupy](https://github.com/syrupy-project/syrupy), or explicit assertions on Pydantic-validated dicts. Approval-style is lower-friction; pick syrupy. Each fixture has both an input (`.html`) and an expected output (`.snap.json`); `pytest --snapshot-update` regenerates when parser is intentionally changed. |
| **B4. Brand-coverage quota per parser** | Run #13 missed Armani because no Armani fixture existed at build time. Fixture coverage must be tracked **per brand-prefix** (or per category) so adding a brand to viled automatically demands a fixture or fails CI. | M | Custom pytest check: for each brand in `brand-aliases.yaml`, assert ≥1 fixture exists under `tests/fixtures/live/goldapple/{brand}/`. The check skips brands explicitly listed as `volumeless` or `not-on-goldapple`. Smaller scope: enforce only for brands that appeared in last 4 weekly runs (avoids forcing fixtures for one-off brands). |
| **B5. Scheduled re-capture CLI (`fixtures-refresh`)** | Cassettes go stale; sites change. Need a one-command operator step to re-fetch every fixture URL, diff against stored HTML, and flag drifted ones. This is the [Scrapy-Testmaster dynamic update](https://github.com/ThomasAitken/Scrapy-Testmaster) pattern adapted to our two parsers. | M | New CLI subcommand (current count = 5: weekly-run, goldapple-smoke, matcher-run, report-run, deliver-run; this adds a 6th — update the source-locked canary in Phase 7). For each fixture: re-fetch via the production fetcher (curl_cffi or Camoufox), compute new SHA256, compare. Output: list of `unchanged | minor-drift | major-drift | unreachable`. Major-drift → run parser against new HTML, surface diff, prompt operator to accept (regenerate snapshot) or fix (parser bug). Run weekly or monthly, NOT in the Sunday-night pipeline. |
| **B6. Schema validation on every snapshot insert** | Defense-in-depth: even if parsers silently change, [Pydantic validators](https://dev.to/withatte/stop-silent-scraper-failures-using-pydantic-for-instant-layout-change-detection-4p1k) at the DB boundary will reject `volume_norm=NULL` for non-`volumeless` categories. Closes the gap A4 partially addresses by making it structural, not gate-based. | S | Add a Pydantic model `SnapshotRecord` in front of `SqliteSnapshotWriter.write_*`. Run #13-style failure becomes a `ValidationError` at insert time, surfaces in logs immediately, doesn't reach the matcher. v1.0 dependency: `SqliteSnapshotWriter` is the only writer (per architectural invariant in MILESTONES.md). |

#### Bucket C — Paperwork Carryover (v1.0 audit findings)

| Feature | Why Required | Complexity | Notes / v1.0 dependency |
|---------|--------------|------------|--------------------------|
| **C1. SECURITY.md for Phase 2** | v1.0 audit verdict `tech_debt` lists this. Phase 2 ships SQLite + viled curl_cffi crawler + brand-aliases.yaml — needs explicit threat enumeration (creds in `.env`, `.db` file permissions, brand-aliases as supply-chain). | S | Run `/gsd-secure-phase 2` retroactively per audit recommendation. No code change — paperwork. |
| **C2. SECURITY.md for Phase 4** | Audit-flagged. Matcher reads from snapshots, writes denormalized matches table; threat surface is SQL injection on brand alias / volume normalization input. | S | Same workflow as C1. |
| **C3. SECURITY.md for Phase 6** | Audit-flagged. Telegram delivery handles bot token + chat IDs from `.env`, sends files to external API. Threat surface: secret-leak on log, oversized-file rejection, abuse via chat-ID spoofing. | S | Same workflow as C1. |
| **C4. VALIDATION.md for Phase 4** | Audit-flagged. Phase 4 has 465+ tests but no VALIDATION.md document — the audit framework expects the meta-doc. | S | Run `/gsd-validate-phase 4`. No code change. |
| **C5. Audit-framework completion record (in MILESTONES.md or v1.1 archive)** | Once C1–C4 land, v1.0 audit verdict can flip from `tech_debt` to `clean` retroactively. Worth recording the transition. | S | Single line in `milestones/v1.0-MILESTONE-AUDIT.md` (or a v1.1 patch file). |

#### Bucket D — Operator Deploy + First Production Cron Tick

`07-HUMAN-UAT.md` already documents 4 `blocked` items; this milestone unblocks them via real-VPS execution. Hetzner CX22 EU is the v1.0 recommended path (`MILESTONES.md` § "Next Milestone Operator Path"). Yandex Cloud KZ remains a fallback if EU geofencing fires on goldapple.

| Feature | Why Required | Complexity | Notes / v1.0 dependency |
|---------|--------------|------------|--------------------------|
| **D1. VPS provisioned (Hetzner CX22 EU OR Yandex Cloud KZ small)** | Without a real server no UAT item can flip from `blocked`. | S (ops) | Decision gate: EU first (default per v1.0 STACK.md); if `goldapple-smoke` regresses from EU IP, fall back to Yandex Cloud KZ. Hetzner CX22 ≈ €4.50–€8/month (from v1.0 STACK.md). |
| **D2. Deploy per README.md §2 (8-step Russian operator runbook)** | The runbook exists from Phase 7 D-707. Executing it once is the v1.1 deploy. | M (ops) | Steps: useradd, uv install, uv sync, `playwright install firefox`, copy `deploy/*` to `/etc/cron.d` + `/etc/logrotate.d`, populate `.env` (TG_BOT_TOKEN, TG_BUSINESS_CHAT_ID, TG_OPS_CHAT_ID, HC_PING_URL), `chmod 0600 .env`. |
| **D3. Smoke gate: `bin/weekly-run.sh --viled-only --sanity-gate-n 1`** | Flips one `blocked` UAT item to `pass`. Validates that the bash wrapper + flock + log redirect work on the target VPS. | S (ops) | UAT smoke-gate item from `07-HUMAN-UAT.md`. |
| **D4. First production cron tick (Sunday 23:00 Asia/Almaty → Monday ~02:00–03:00 report)** | UAT SC#1 cron timing item. Cannot be simulated — must be a real Sunday. | S (wait) | After D2 + D3 pass, the next Sunday's tick is the test. |
| **D5. Deliberate-failure verification: `bin/test-failure-alert.sh`** | UAT SC#5 item. Exercises D-605 invariant (Telegram failure ≠ run failure) and HC.io dead-man's-switch flag-on-failure semantics. | S (ops) | Already built in Phase 7 (`bin/test-failure-alert.sh`); just run it on the real server. |
| **D6. HC↔Telegram integration UAT** | UAT item — HC.io's webhook should fire a Telegram ops-channel alert when the cron run fails to ping. Real-world test of the alert path. | S (ops) | Requires HC.io UI setup (3rd-party); already documented in README.md §6. |
| **D7. Backup verification: first `bin/backup.sh` execution on VPS** | Phase 2 ships `bin/backup.sh` (SQLite online `.backup` + 4-rotate retention). Has not been exercised on real production data. | S (ops) | Verify file is created with correct permissions, retention rotates. |
| **D8. Resume `/gsd-verify-work 7` to flip 4 blocked UAT items** | After D3–D7 pass, the verification workflow can mechanically flip the 4 `blocked` items in `07-HUMAN-UAT.md` to `pass`, closing Phase 7 audit at full bar. | S | Mechanical follow-up. |

---

### Differentiators (Add Only If Cheap During v1.1)

These would harden v1.1 but are not required for the milestone to ship. Most belong to a later cycle.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Random live-URL sampling per CI run** | Beyond fixed fixtures: each CI run also fetches N random PDPs from production and asserts the parser produces non-empty fields. Catches drift in real-time, not just on `fixtures-refresh` runs. | M | Risk: makes CI flaky if goldapple rate-limits — keep N small (3 viled + 3 goldapple) and skip on PR builds, run only on weekly CI. Adds operational complexity; defer unless B5 alone proves insufficient. |
| **Cassette diff visualization on PR** | When a parser change updates `.snap.json` files, surface the diff inline in PR review. Lowers the "did I mean to change this snapshot?" cognitive cost. | M | syrupy already produces decent diffs in pytest output; PR-comment integration is nice-to-have. |
| **Match-rate trend chart in Telegram business message** | Pricing team would see "match-rate has dropped from 65% to 12% in 3 weeks" before silent failure becomes a problem. Extends v1.0 A5 from a floor-alert to a trend signal. | M | Needs matplotlib + small PNG attachment. Defer to v1.2 unless team explicitly asks. |
| **Operator status dashboard URL (HC.io status page)** | HC.io provides public/shared status URLs; bookmark for team. | S | Pure ops, near-zero code. Worth adding to README.md during D2 if time permits. |
| **VPS firewall + fail2ban hardening doc** | Improves the SECURITY.md set with a deploy-time hardening checklist. | S | Belongs to README.md or a new `deploy/HARDENING.md`. Cheap; consider bundling with D2. |

---

### Anti-Features (Explicitly Out of v1.1 Scope)

Easy to get pulled into during a "while-we're-at-it" deploy. Locked out below with reasoning to prevent re-adding.

| Anti-Feature | Why Tempting | Why Not in v1.1 | Defer To |
|--------------|--------------|-----------------|----------|
| Viled SSR pagination beyond page 1 | Run #13 only had 82 SKU (page 1 only); doubling coverage seems valuable. | v1.0 CARRYOVER section (`MILESTONES.md`) explicitly defers this — SSR ignores `?page=N` and 9 other URL conventions per Phase 3/7 ops backlog. Belongs to v2 (separate spike). | v2 |
| Docker image for the crawler | Phase 7 D-710 deferred to v2 because Camoufox Firefox 135 ≠ Playwright Chromium-based image. Would simplify VPS install. | Resolving D-710 requires a Camoufox-compatible base image build — multi-day spike. Not in v1.1's narrow scope. | v2 (INFRA-V2-04 backlog) |
| Postgres migration | Tempting "while we're touching the schema for B6 Pydantic validation". | v1.0 STACK.md migration criteria not met (single writer, weekly, no remote dashboard yet). SQLite still right tool. | v2+ when criteria trip |
| Fuzzy / token-set matching | Match-rate may look low after parser fixes land — tempting to "just add fuzzy". | PROJECT.md locks strict-key for v1.x; fuzzy is explicit v2 candidate. Adding now confounds the "did the parser fixes actually work?" measurement. | v2 (only if v1.1 strict-key match-rate is empirically unacceptable) |
| Second competitor (mechta / sulpak / wildberries) | Operator deploy is "the time to add another retailer". | Each new site = new parser + new anti-bot story + new normalization. PROJECT.md anti-feature. | v2+ when team explicitly requests |
| Web dashboard or status UI | Run #13 silent-failure pain is fresh; "we need a dashboard" feels natural. | PROJECT.md anti-feature for v1.x. Telegram + Excel + HC.io already cover the workflow. Differentiator D-table-row covers the cheap version (HC.io status page). | v2+ |
| Real-time / daily monitoring | Run #13 missed a problem for ~hours — "more frequent runs would have caught it". | False premise: parser bug would have produced empty Excels daily instead of weekly. Right answer is B5 + B6, not higher cadence. PROJECT.md anti-feature. | Never (locked out) |
| KZ-legal review bundled into v1.1 | v1.0 CARRYOVER lists it; deploy time seems "the right time". | 30-min lawyer engagement is a separate workstream — orthogonal to code or deploy. Bundle into next ops cycle. | v1.2 or operator backlog |
| Camoufox+EU "smoke from Hetzner" pre-validation as a v1.1 phase | v1.0 CARRYOVER calls this out as an operator concern. | The validation happens in D3 naturally; doesn't need a separate phase. | Subsumed into D3 |
| ML / image / description capture | None of these came up in run #13. | Anti-features in v1.0 FEATURES.md; nothing changed. | Never (locked out) |

---

## Feature Dependencies

```
[A1 Goldapple volume]     ─┐
[A2 Goldapple brand/name] ─┼─required-by──> [A4 null-rate gate validates again]
[A3 Viled volume_raw]     ─┘                       └──> [matcher produces non-zero rows again]
                                                              └──> [Excel sheets stop being empty]
                                                                       └──> [A5 match-rate floor alert]

[B1 Cassette infra]
    └──enables──> [B2 metadata schema]
                       └──enables──> [B3 assertion API (syrupy)]
                                          ├──enables──> [B4 brand-coverage quota]
                                          └──enables──> [B5 fixtures-refresh CLI]
[B6 Pydantic validation at DB boundary] ──independent of B1–B5──> [defense-in-depth A4]

[A1/A2/A3] ──verified-by──> [B3 against newly captured fixtures]   # parser fixes are validated by harness
[B1–B6]   ──verified-by──> [B5 first refresh] + [tests/ green]

[C1 SECURITY.md ph2]  ─┐
[C2 SECURITY.md ph4]  ─┼──all-must-land──> [C5 audit-record flip to clean]
[C3 SECURITY.md ph6]  ─┤
[C4 VALIDATION.md ph4]─┘

[D1 VPS] ──prerequisite-of──> [D2 deploy] ──prerequisite-of──> [D3 smoke]
                                                                    └──> [D4 first cron]
                                                                              └──> [D5 deliberate-failure] + [D6 HC↔TG] + [D7 backup]
                                                                                          └──> [D8 verify-work flip 4 UAT items]

[Bucket B] ──not-blocking──> [Bucket D]   # deploy doesn't have to wait for harness
[Bucket A] ──must-land-before──> [Bucket D]  # don't deploy known-broken parsers
[Bucket C] ──independent──> all other buckets  # paperwork can be parallel
```

### Dependency Notes

- **Bucket A is the only blocker for Bucket D.** Operator deploy a broken parser would just produce more empty Excels on the new VPS. A1–A4 must land before D4 (first cron tick), and ideally before D3 (smoke) so smoke covers the real fixed parser path.
- **Bucket B is not on the deploy critical path** but should land in the same milestone — it's the methodology fix for "why didn't v1.0 catch this?" Skipping B means v1.2 risks another silent-failure incident.
- **Bucket C is fully independent.** Could be done in parallel by a separate workstream or sequentially after Bucket A. No code coupling.
- **Within Bucket B: B1 → B2 → B3 → {B4, B5}** is the strict ordering. B6 is independent (different code path — Pydantic at the writer, not at the parser test) and can land at any time.
- **D4 (first cron tick) is calendar-bound.** Once D1–D3 land mid-week, D4 happens on the next Sunday. Plan v1.1 close to land at a Sunday boundary.
- **A4 (null-rate gate validation) and B6 (Pydantic validation) are partial duplicates by design.** A4 is a sanity check on the run pipeline; B6 is a schema check at the DB boundary. Defense-in-depth — both wanted, neither replaces the other.

---

## MVP Definition

### v1.1 Minimum Viable Milestone

What's required to call v1.1 "shipped" and flip v1.0 audit from `tech_debt` to `clean`:

- [ ] **A1 + A2 + A3** — three parser bugs fixed, snapshot table produces non-NULL volumes and separated brand/name for ≥95% of SKUs.
- [ ] **A4** — sanity gate (or equivalent) refuses to mark a run `success` when match-rate is zero or null-rate exceeds threshold (already-documented D-218 behavior, just validated against the run #13 regression).
- [ ] **A5** — Telegram business message tags match-rate-floor breaches (low cost, high signal).
- [ ] **B1 + B2 + B3** — cassettes capture/replay infrastructure + metadata + assertion API land in `tests/`. At minimum: a regression test that loads the run #13 Armani PDP cassette and asserts the fixed parser produces correct brand/name/volume. (This is the "would have caught it" test.)
- [ ] **B6** — Pydantic validation at `SqliteSnapshotWriter` boundary. Rejects empty volumes for non-volumeless categories.
- [ ] **C1 + C2 + C3 + C4 + C5** — audit paperwork lands, v1.0 audit flips to `clean`.
- [ ] **D1 → D8** — VPS provisioned, deploy completed, first Sunday cron tick produces non-empty Excel, all 4 `blocked` UAT items flipped to `pass`.

That's the milestone. No discretionary differentiators.

### Add If Cheap During v1.1 (No Roadmap Slot Yet)

- [ ] **B4 brand-coverage quota** — high value if the v1.1 spike for B1–B3 lands quickly; can be skipped if time-pressured (B5 partially covers via re-fetch).
- [ ] **B5 fixtures-refresh CLI** — high value but adds a 6th CLI subcommand (touches v1.0's source-locked canary). Worth doing in v1.1 to close the methodology gap fully; skip only if time forces.
- [ ] **VPS hardening doc + HC.io status URL** — bundle into D2 if time permits.

### Defer To v1.2 / v2

- [ ] **Differentiators table** — all rows that aren't bumped to "Add If Cheap" above.
- [ ] **All v1.0 carryover items not in scope** — viled pagination, Docker, KZ-legal review, Postgres migration.
- [ ] **Fuzzy matching** — only revisit if v1.1 strict-key match-rate (post-fix) is empirically below acceptable.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| A1 Goldapple volume extraction | HIGH (unblocks matcher) | MEDIUM | P1 |
| A2 Goldapple brand/name separation | HIGH (unblocks matcher) | MEDIUM | P1 |
| A3 Viled volume_raw distinct | HIGH (improves match-rate) | LOW–MEDIUM | P1 |
| A4 null-rate gate validation | HIGH (silent-failure prevention) | LOW | P1 |
| A5 match-rate floor alert | MEDIUM (early-warning) | LOW | P1 |
| B1 Cassette infra | HIGH (foundation) | MEDIUM | P1 |
| B2 Cassette metadata schema | HIGH (B3/B4 prerequisite) | LOW | P1 |
| B3 Assertion API (syrupy) | HIGH (the regression test) | LOW | P1 |
| B4 Brand-coverage quota | MEDIUM (prevents future Armani-class gaps) | MEDIUM | P2 |
| B5 fixtures-refresh CLI | MEDIUM (drift detection) | MEDIUM | P2 |
| B6 Pydantic at DB boundary | HIGH (defense-in-depth) | LOW | P1 |
| C1–C5 Audit paperwork | MEDIUM (closes v1.0 audit) | LOW × 5 | P1 |
| D1 VPS provisioned | HIGH (deploy prerequisite) | LOW | P1 |
| D2 Deploy per README §2 | HIGH (deploy) | MEDIUM | P1 |
| D3 Smoke gate | HIGH (UAT) | LOW | P1 |
| D4 First production cron tick | HIGH (the actual milestone goal) | LOW (calendar) | P1 |
| D5 Deliberate-failure verify | MEDIUM (UAT closure) | LOW | P1 |
| D6 HC↔Telegram integration | MEDIUM (UAT closure) | LOW | P1 |
| D7 Backup verification | MEDIUM (operational hygiene) | LOW | P1 |
| D8 Verify-work flip 4 UAT | MEDIUM (mechanical closure) | LOW | P1 |
| Random live-URL sampling | LOW–MEDIUM (B5 partly covers) | MEDIUM | P3 |
| Cassette diff in PR | LOW (syrupy diff is enough) | MEDIUM | P3 |
| Match-rate trend chart | MEDIUM (post-v1.1 nice-to-have) | MEDIUM | P3 |
| VPS hardening doc | LOW (cheap to add) | LOW | P2 |
| HC.io status URL | LOW | LOW (ops) | P2 |

**Priority key:**
- P1: Required for v1.1 — milestone cannot close without it
- P2: Bundle into v1.1 if time permits, otherwise defer to v1.2
- P3: Out of v1.1 scope, revisit only if explicitly justified

---

## Mapping to PROJECT.md Active Requirements

| PROJECT.md Active Requirement | Mapped v1.1 Features |
|-------------------------------|----------------------|
| "Goldapple parser: извлекать volume из structured-блока PDP" | **A1** |
| "Goldapple parser: разделять brand и name из title" | **A2** |
| "Viled parser: extract volume как отдельное поле" | **A3** |
| "Live HTML fixture harness в тестах" | **B1 + B2 + B3 + B4 + B5 + B6** (B6 is the defense-in-depth complement) |
| "Audit paperwork debt: SECURITY.md для phases 2/4/6 + VALIDATION.md для phase 4" | **C1 + C2 + C3 + C4 (+ C5 record)** |
| "Operator deploy: VPS + первый live Sunday cron tick + UAT closure" | **D1 → D8** |

Every active requirement maps to a P1 feature. No active requirement is unmapped, and no P1 feature is unjustified by an active requirement.

---

## Sources

### Live-HTML / cassette harness pattern (Bucket B)
- [kiwicom/pytest-recording — VCR.py-powered pytest plugin](https://github.com/kiwicom/pytest-recording) — record/replay HTTP traffic in pytest; foundation for B1 (curl_cffi path)
- [VCR.py — Usage docs](https://vcrpy.readthedocs.io/en/latest/usage.html) — `once` / `new_episodes` / `all` record modes; cassette YAML format
- [Test a Web Scraper using VCR — datawookie](https://datawookie.dev/blog/2025-01-28-test-a-web-scraper-using-vcr/) — concrete pytest+VCR pattern; gap noted: article does NOT cover drift detection or cassette refresh, confirming this is a known weakness we must address explicitly (B5)
- [Scrapy-Testmaster (ThomasAitken)](https://github.com/ThomasAitken/Scrapy-Testmaster) — static-vs-dynamic validation pattern; `testmaster update --dynamic` is the inspiration for B5 `fixtures-refresh`
- [syrupy — pytest snapshot plugin](https://github.com/syrupy-project/syrupy) — assertion API for B3; `pytest --snapshot-update` workflow
- [Snapshot Testing — Jest docs](https://jestjs.io/docs/snapshot-testing) — conceptual reference for snapshot-based regression testing
- [Stop Silent Scraper Failures: Using Pydantic for Instant Layout Change Detection](https://dev.to/withatte/stop-silent-scraper-failures-using-pydantic-for-instant-layout-change-detection-4p1k) — B6 design pattern; Pydantic at the parse/write boundary detects layout shifts instantly
- [Data Quality at Scale: Validating Scrapes with Pydantic](https://dev.to/deepak_mishra_35863517037/data-quality-at-scale-validating-scrapes-with-pydantic-2gf0) — schema-validation framing for scraper pipelines
- [Bulletproof Data Pipelines: Adding Schema Validation to Nike Scrapers](https://dev.to/withatte/bulletproof-data-pipelines-adding-schema-validation-to-nike-scrapers-3p10) — concrete example of Pydantic-on-scraper-output pattern
- [Scrapy Spider Contracts docs](https://docs.scrapy.org/en/latest/topics/contracts.html) — `@url`, `@returns`, `@scrapes` contract idea; informed B4 brand-coverage thinking (we don't use Scrapy, but the contract concept maps cleanly to "every brand has a fixture")

### Operator deploy (Bucket D)
- v1.0 `.planning/README.md` §2 — 8-step Russian operator runbook (Phase 7 D-707)
- v1.0 `.planning/07-HUMAN-UAT.md` — 4 `blocked` UAT items map directly to D3–D6
- v1.0 STACK.md "Deployment / Hosting" — Hetzner CX22 €4.50–€8/month rationale
- `MILESTONES.md` § v1.0 "Next Milestone Operator Path" — 6-step deploy plan (D1–D8 expand on this)

### Parser bugs evidence (Bucket A)
- `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` — three bug reports + DB samples + live PDP screenshot
- v1.0 `.planning/research/PITFALLS.md` Pitfall #2 ("silent parser drift") — exactly predicted run #13 failure mode

### Audit framework (Bucket C)
- v1.0 `milestones/v1.0-MILESTONE-AUDIT.md` — `tech_debt` verdict, paperwork-only findings
- v1.0 MILESTONES.md § "Tech Debt Carried Forward" — enumerates C1–C4 items

**Confidence notes:**
- Parser-bug evidence — **HIGH** (DB samples + live PDP screenshot in v1.1-PARSER-BUG-FINDINGS.md)
- Cassette/harness pattern — **HIGH** (multiple corroborating sources: VCR.py, syrupy, Pydantic, Scrapy-Testmaster all converge on the same shape)
- B5 re-capture CLI specifics — **MEDIUM** (pattern is well-established but our concrete implementation depends on Camoufox session reuse semantics; spike likely in plan execution)
- D1 Hetzner-vs-Yandex Cloud decision — **MEDIUM** (default is Hetzner EU per v1.0 STACK.md, but EU IP geofencing on goldapple is empirically unverified from Hetzner specifically; first smoke is the test)
- v1.1 milestone completing in single calendar window — **MEDIUM** (D4 is Sunday-gated; depending on when A+B+C+D1–D3 land, milestone close could slip by up to 6 calendar days)

---
*Feature research for: ga_crawler v1.1 (parser fixes + live-HTML harness + audit paperwork + operator deploy)*
*Researched: 2026-05-13*
