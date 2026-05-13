# Architecture Research — v1.1 Parser Fix + Live-HTML Harness

**Project:** ga_crawler
**Mode:** Project research — integration architecture for v1.1 milestone
**Overall confidence:** HIGH (built on direct codebase inspection; only Q-C downstream-impact has MEDIUM tail)
**Date:** 2026-05-13

---

## Executive Summary

v1.0 is a clean pipe-and-filter monolith with strict module boundaries (`fetchers → parsers → normalizers → storage → matcher → reporter → delivery`) and 803 passing tests. v1.1 must NOT re-architect any of this. The work decomposes into three orthogonal surgical changes plus one operator track:

1. **Parser bug fixes** — strictly inside `parsers/goldapple_microdata.py` and `parsers/viled_nextdata.py`. Internal contract that downstream cares about: the **dispatcher dict shape** (currently `asdict(GoldappleRawProduct)` in `parsers/dispatcher.py:51`). New separate `volume_raw` field is additive — no schema change, no normalizer rewrite.
2. **Live-HTML harness** — a new sibling capture surface that does not enter the production pipe-and-filter at all. Lives in `scripts/` (operator-run capture) + `tests/fixtures/<retailer>/_live-*.html` (captured snapshots) + `tests/live/` (drift-detection tests behind the existing `live` pytest marker, see `pyproject.toml:51`).
3. **Backfill question** — recommend **forward-only** (skip retroactive backfill of runs 1–13). Reasoning below.
4. **VPS setup script** — recommend **yes, add `bin/setup-vps.sh`**, but as a thin wrapper over README §2 steps, not a re-architecture.

**Build order (justified):** parser-fix → live-HTML harness retroactively pinned to fix → paperwork debt (parallel) → setup-script + operator deploy. This is the only order where harness measures the fix and deploy ships the fix simultaneously without re-validation cycles.

---

## A) Parser-fix integration pattern — recommendation: Option 3 + dual-fixture strategy

### File-line integration points

**Goldapple Bug #1 (volume missing 88/88) — `src/ga_crawler/parsers/goldapple_microdata.py`**

| Location | Current behavior | v1.1 change |
|----------|------------------|-------------|
| Line 64 `raw_volume_text: Optional[str]` dataclass field | Already exists | KEEP — no schema change |
| Line 358–359 `raw_volume_text = name or None` (passthrough) | Hardcodes name → volume_raw | REPLACE with `_extract_volume_block(tree)` helper |
| NEW helper `_extract_volume_block(tree)` at module level (insert near `_extract_strikethrough` line 254) | DOES NOT EXIST | Add selector for "ОБЪЁМ / МЛ" structured block (flex-box of `<div>`s, no `itemprop="size"`). Use `selectolax 0.4` Lexbor backend `:lexbor-contains("ОБЪЁМ" i)` per STACK.md |
| Line 358 fallback chain | Single source | Layered: `_extract_volume_block` → fallback to `name` (preserves backward-compat for fixtures that have volume in title) |

**Goldapple Bug #2 (brand + name concatenation) — same file**

| Location | Current behavior | v1.1 change |
|----------|------------------|-------------|
| Line 319–324 brand extraction via `<meta itemprop="name">` inside `[itemprop="brand"]` | Returns microdata value, sometimes empty | KEEP path 1 (microdata still primary) |
| Line 327–332 name extraction via `<h1>` text + title fallback | Returns full `<h1>` verbatim including embedded brand | Per STACK.md finding: read sibling `<meta itemprop="name" content="Pour Homme">` rather than `<h1>` text |
| Fallback `_strip_brand_prefix(name, brand)` | DOES NOT EXIST | Used only if structured meta missing. Strips both `STEREOTYPEsago` → `sago` and `Armaniarmani code` → `armani code` cases |

**Viled Bug #3 (volume_raw = full name) — `src/ga_crawler/parsers/viled_nextdata.py`**

| Location | Current behavior | v1.1 change |
|----------|------------------|-------------|
| Line 215 `raw_volume_text=name` | Verbatim alias | First try `_extract_volume_from_nextdata(item, a0)` — per STACK.md, read `props.pageProps.attributes[].name == "Размер"` carrying volume as `{name: "Размер", value: "200мл + 200мл + 250мл"}` |
| NEW helper at module level | DOES NOT EXIST | Inspect `__NEXT_DATA__` for dedicated volume field; fall through to `name` only if absent. **Requires Wave-0 probe against live beauty PDP** (clothing fixture confirms shape but beauty PDP path needs verification) |
| Module docstring line 20–21 | References WAVE0-PROBE for stock state | ADD new probe MEMO reference for volume field |

### Safest pattern: Option 3 — dual-fixture capture (recommended)

Reasoning grounded in repo state:

- **Option 1 (feature-flag) — REJECT.** No existing feature-flag infrastructure. `pyproject.toml [tool.ga_crawler.*]` is type-locked, operator edits via git PR.
- **Option 2 (update fixtures + extraction lockstep) — REJECT.** Loses fixture-drift vs parser-drift signal.
- **Option 3 (capture new live HTML as additional fixtures, assert both pass) — RECOMMEND.** Existing test infrastructure already supports this:
  - `tests/conftest.py:23–37` loads `_debug-product-page.html` via `pathlib.Path` — adding a new fixture is a 6-line conftest addition (load `_live-2026-05-13-stereotype.html` as `@pytest.fixture(scope="session")` named `goldapple_pdp_html_live_v2`)
  - Parallel test class `TestGoldappleParserLiveV2` parametrized over the new fixture asserts same invariants PLUS new `volume_raw is not None`, `brand_raw not in name`.

**Concrete fixture additions:**
- `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` (Bug #1 evidence)
- `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` (Bug #2 evidence)
- `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` (Bug #3 evidence)

These are **append-only** — do NOT replace the Givenchy fixture (spike 01-08). Existing 60+ goldapple unit tests keep passing.

### Test-count impact estimate

- 21 existing goldapple parser tests → unchanged
- ~10 new goldapple parser tests (volume + brand-prefix stripping)
- 24 existing viled parser tests → 1 modification (`raw_volume_text == name` flips to "extracted when available, else name")
- ~5 new viled parser tests (volume from nextdata struct)

Total: ~803 → ~818 tests. No deletions.

---

## B) Live-HTML harness placement — recommendation: tests/live/ + scripts/capture_fixtures.py + retailer-domain fixture slicing

### Existing conventions (load-bearing)

- `pyproject.toml:51–53` declares two pytest markers: `live` (deselect with `'not live'`) and `integration` (mocked). The `live` marker is part of the public test surface but no test currently uses it — **purpose-built for this**.
- `scripts/` already has operational scripts (`uat3_live_run.py`, `diagnostic_xlsx.py`) — adding `scripts/capture_fixtures.py` is in-pattern.
- `tests/fixtures/{goldapple,viled,normalize,reporter,delivery}/` is existing slicing. Adding `tests/fixtures/live/` violates this (live is temporal, not domain).

### Recommended placement

| Component | Path | Rationale |
|-----------|------|-----------|
| Capture CLI | `scripts/capture_fixtures.py` | Operator-run; in line with existing precedent |
| Captured HTML | `tests/fixtures/<retailer>/_live-YYYY-MM-DD-<slug>.html` | Keeps domain-based slicing intact; `_live-` filename prefix is temporal marker |
| Drift tests | `tests/live/test_parser_drift.py` (NEW dir) | Marked `@pytest.mark.live`. Opt-in via `pytest -m live`; default CI skips |
| Capture orchestration | New CLI subcommand `python -m ga_crawler capture-fixtures` | Reuses existing dispatch (matches `weekly-run`/`report-run`/`deliver-run` shape) |

**Why NOT `src/ga_crawler/testing/`:** harness is dev infrastructure, would contaminate wheel.
**Why NOT `tests/fixtures/live/`:** breaks retailer-grouped convention.

### Harness contract (suggested)

```
scripts/capture_fixtures.py --retailer goldapple --url <URL> --out <PATH>
  → uses src/ga_crawler/fetchers/goldapple.py:GoldappleFetcher (Camoufox)
  → writes raw HTML to <PATH>
  → emits sidecar JSON with capture metadata: {date, url, status, html_size, title, camoufox_version}

tests/live/test_parser_drift.py
  @pytest.mark.live
  - Re-fetches each known SMOKE_URL (from src/ga_crawler/runner/gates.py:36)
  - Runs parse_pdp on fresh HTML
  - Asserts: name non-empty, current_price in [100, 1M], volume_raw non-null, brand not in name
  - On failure: writes diagnostic to .planning/research/parser-drift-YYYY-MM-DD.md
```

This is the gap v1.0 audit missed: frozen-fixture tests are necessary but insufficient. The `live` marker exists in pyproject for exactly this purpose and was never wired up.

---

## C) Downstream data-flow concern — recommendation: forward-only, no backfill

### What changes downstream once parsers are fixed

| Layer | Before fix (run #13) | After fix (run #14+) |
|-------|----------------------|----------------------|
| `parsers/goldapple_microdata.py:365` dispatcher dict | `raw_volume_text=name` (mostly nameless garbage) | extracted volume string |
| `normalizers/volume.py:118 parse_volume` | Mostly returns None for goldapple | Returns `Volume(amount=75, unit='ml', count=1)` |
| `storage/snapshots` `volume_norm` for goldapple | NULL for 88/88 | Populated for ~50–80% |
| `matcher/strict_key.py:58` D-402 filter requires `volume_norm IS NOT NULL` | 0 goldapple rows pass | Tens of rows pass |
| `reporter` `per_sku_deltas` + `assortment_gaps` | Empty | Populated |
| `stats.match.goldapple_comparable_count` | 0 | Tens |

This is the **intended behavior**. Matcher SQL is correct per D-402; bug is upstream. No matcher/reporter/storage changes required.

### Backfill — do NOT backfill runs 1–13

Three reasons grounded in repo:

1. **HTML is gone.** Snapshots store parsed fields only; no HTML cache. Re-parse has nothing new to re-parse — `volume_raw` already NULL in DB.
2. **Matcher idempotent per run** (`strict_key.py` D-410). Re-running produces same 0-match because inputs unchanged.
3. **History stays interpretable.** Runs 1–13 preserved as "we had parser bug then". Auto-suggest threshold takes 4-week median (`gates.py:221`) — garbage rolls out by run #17, operator-decides-not-auto-tunes (`gates.py:301` "NEVER auto-tunes").

The only artifact that needs a note: `.planning/MILESTONES.md` should mark runs 1–13 as "pre-parser-fix; goldapple match rate not meaningful". One-line annotation.

---

## D) VPS setup script — recommendation: yes, add `bin/setup-vps.sh`

### Why yes

- README §2 is 8 ordered `sudo` steps with 3 Pitfall sidebars (#5, #6 enumerated; useradd needs explicit non-`-m` flag with `install -d` workaround). Human running these one-by-one will hit Pitfall #5 trap probabilistically.
- Existing pattern: `bin/weekly-run.sh`, `bin/backup.sh`, `bin/test-failure-alert.sh` — all bash wrappers around 5–10 ordered commands. `bin/setup-vps.sh` extends pattern.
- Existing test infrastructure validates these via 7 phase-07 structural canary tests. New `test_phase07_setup_vps_shape.py` follows same pattern. Per `feedback_code_review_for_ops_phases.md`: bash/cron/deploy/README phases must run gsd-code-review; canaries can't catch cross-env bugs.

### What it should NOT do

- Provider-specific cloud-init (Hetzner-API or Yandex-API calls) — out of scope; provider choice user-driven.
- ENV-filling — `.env` editing stays manual (secrets, not idempotent).
- Self-update or git-pull logic — that's deploy, not setup.

### Recommended shape

```bash
bin/setup-vps.sh [--repo-url URL] [--hc-url URL]
  step 1: apt install
  step 2: useradd + install -d (encodes Pitfall #5+#6 fixes by construction)
  step 3: uv install as ga_crawler
  step 4: git clone + uv sync + playwright install firefox
  step 5: install -d /var/log/ga_crawler
  step 6: cp deploy/etc-cron-d-ga_crawler + cp deploy/etc-logrotate-d-ga_crawler
  step 7: cp .env.example .env + chmod 0600
  step 8: print "Now edit /opt/ga_crawler/.env then run bin/weekly-run.sh --viled-only --sanity-gate-n 1"
```

### Idempotency — required

- `id ga_crawler &>/dev/null || useradd …`
- `[[ -d /opt/ga_crawler/.git ]] || git clone …`
- `[[ -f /opt/ga_crawler/.env ]] || cp .env.example …` (NEVER clobber existing .env)
- `cp -n` for deploy/* templates (preserves manual cron tweaks)

Re-running on working VPS prints "ok" per step, exits 0. Safe as "verify deploy state" tool.

### Yandex Cloud KZ variant

Same script works on both. Per STACK.md: Yandex Cloud kz1 = vanilla Ubuntu over SSH, no proprietary SDK. Same `apt` commands work. Different default user (`yc-user` not `ubuntu`) but we create own `ga_crawler` so irrelevant. KZ-region IP is **preferable** for goldapple per CLAUDE.md Anti-Bot Tier 1.

Document provider choice in README §2 header; script stays provider-agnostic.

---

## E) Build order — recommendation: parser-fix → live-HTML harness → paperwork debt → operator deploy

### Why this order

1. **Parser-fix FIRST.** Only code change. Strongest invariant (tests stay green). Without it, operator deploy ships known-broken pipeline — first Sunday cron produces empty xlsx. Verification gate: `goldapple_comparable_count > 0` in dry-run against live HTML.

2. **Live-HTML harness SECOND.** Locks in parser-fix retroactively. New fixtures captured DURING parser-fix work ARE evidence the fix works. Phase 2 formalizes capture as `scripts/capture_fixtures.py` + `tests/live/` for repeatability. Cannot be first (harness needs known-good captures). Cannot be last (deploy validation runs with no drift-detection net).

3. **Paperwork debt THIRD (parallel-safe with phase 4).** SECURITY.md (phases 2/4/6) + VALIDATION.md (phase 4) pure documentation. No code changes. Per CLAUDE.md: v1.0 shipped as `tech_debt` — just-closing-the-audit work.

4. **Operator deploy LAST.** Ships whatever code is on `main`. With parser-fix + harness on `main`, deploy ships fixed version with drift-detection live. First Sunday cron tick = "did this all work" gate.

### Alternative order considered: harness-first → parser-fix

Rejected. Harness with no fix to test has zero signal — tests would assert "volume_raw is None for 88/88", pass on broken code, fail on fixed code.

### Phase decomposition (suggested to roadmapper)

| Phase | Scope | Verification gate |
|-------|-------|-------------------|
| P1: Parser bug fixes | Modify `parsers/goldapple_microdata.py` + `parsers/viled_nextdata.py`; add 3 live fixtures; add ~15 tests; upgrade selectolax 0.3→0.4 | All 803+~15 = ~818 tests green; live dry-run yields `goldapple_comparable_count > 0` |
| P2: Live-HTML harness | `scripts/capture_fixtures.py` + `tests/live/test_parser_drift.py` + `pytest -m live` opt-in | `pytest -m live` runs end-to-end against live URLs |
| P3: Paperwork audit closure | SECURITY.md (phases 2, 4, 6), VALIDATION.md (phase 4) | `/gsd-verify-work` audit transitions tech_debt → ship |
| P4: Operator deploy | `bin/setup-vps.sh` + structural canary test + VPS provisioning + first Sunday cron tick + UAT closure | Sunday Telegram delivery contains non-empty xlsx; HC `/start` and `/success` pings recorded; `/gsd-verify-work 7` resume converts 4 blocked UAT items to pass |

P1 and P2 tightly coupled (harness pins fix). P3 parallel-safe with P1 or P2. P4 must be last.

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| A) Parser-fix integration points | HIGH | File-line references verified via direct reads of `goldapple_microdata.py:319–375`, `viled_nextdata.py:124–216`, `parsers/dispatcher.py:38–54`, `tests/conftest.py:23–91`. Matches existing helper convention |
| B) Harness placement | HIGH | `pyproject.toml:51` `live` marker already declared unused — purpose-built. `scripts/uat3_live_run.py` precedent. Retailer-grouped fixtures consistent |
| C) Forward-only backfill | HIGH | Snapshots store parsed fields only (no HTML cache). Matcher idempotency confirmed via `strict_key.py:20–37` D-410. Auto-suggest via `gates.py:221–239` + `pyproject.toml:90` |
| D) Setup script | MEDIUM-HIGH | README §2 8-step procedure well-documented but error-prone. Existing `bin/*.sh` precedent strong. Yandex-cloud behaviors inferred from general Linux conventions, not tested |
| E) Build order | HIGH | Each ordering constraint traces to concrete artifact: tests-green (P1 first), harness-needs-fix-output (P2 second), audit-not-code (P3 parallel), deploy-ships-main-state (P4 last) |

---

## Open Questions for Roadmapper

1. **Viled volume field location** — needs Wave-0 probe against live beauty PDP (STACK.md confirms clothing fixture has `Размер` attribute; beauty PDP path needs verification). *(Recommend: include 30-min probe as P1 sub-task)*
2. **Live-test CI integration** — `pytest -m live` manual ops-runbook OR scheduled? *(Recommend: manual for v1.1; auto-schedule deferred to v1.2)*
3. **Setup-script provider validation** — validate on both Hetzner + Yandex OR only production target? *(Recommend: only production target for v1.1; document other as "untested but should work")*
4. **Goldapple smoke probe rotation** — current smoke URLs (`gates.py:36–40`) use Givenchy fixtures; parser fix driven by STEREOTYPE/Armani live evidence. Rotate smoke URLs? *(Recommend: yes, P1 task — adds one URL of each new shape, future runs catch volume regression at probe stage)*
