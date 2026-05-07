# Phase 2: Project Skeleton + viled Crawl + Storage - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 02-project-skeleton-viled-crawl-storage
**Areas discussed:** Sanity-gate N for viled (CRAWL-05), Brand-alias YAML (NORM-01), NORM-06 review queue format, Stub cutover & module structure
**Mid-flight scope clarification:** viled crawl restricted to `/men/catalog/1310` + `/women/catalog/1310` (beauty+parfumery only)

---

## Sanity-gate N for viled (CRAWL-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-suggest after 4 weeks, seed N=20000 (Recommended) | Mirror D-310 from Phase 3 (goldapple). Static start N=20000, ops-Telegram emits "new N-rec: 0.7 × 4-week-median viled_count" from week 5+. Operator confirms via PR. NOT auto-tune. | ✓ (with mid-flight revision: N=20000 → N=100 after scope-narrowing to catalog/1310) |
| Static absolute N=15000 | Plain catastrophic-failure detector (~35% catalog). No auto-suggest code. Manual operator adjustment later. | |
| Static absolute N=21000 (50% catalog) | Stricter — half of sitemap URLs. Risk of false aborts in early weeks if viled drops products. | |

**User's choice:** Auto-suggest pattern accepted. After scope-narrowing (mid-flight), seed value revised from N=20000 (full sitemap-based) to N=100 (catalog/1310 beauty-only sub-catalog, ~30-40% of expected SKU count). Auto-suggest mechanism unchanged.
**Notes:** Captured as D-201 (revised), D-202 (storage), D-203 (refactor `auto_suggest_threshold` from goldapple-specific into retailer-agnostic helper).

---

## Brand-alias YAML (NORM-01)

| Option | Description | Selected |
|--------|-------------|----------|
| config/brand-aliases.yaml, flat dict, manual seed (Recommended) | Top-level config/ directory; schema `{brand_norm: [aliases...]}`; planner extracts top-50 viled brands from spike artifacts + manual RU/EN variants for kyrillic-named brands. Read-once at run start. | ✓ |
| config/brand-aliases.yaml, richer schema, manual seed | `{brand_norm: {aliases, canonical, category}}`. More extensible for v2 but redundant on v1 (PROJECT locks strict-key, no fuzzy/category-routing). | |
| in-src src/ga_crawler/data/aliases.yaml, flat | Bundled with package, deploy-friendly. Operator manual edits worse (requires deploy cycle for alias-fix). v1 cron deploys via `git pull` anyway. | |

**User's choice:** Recommended (flat dict at config/, manual seed).
**Notes:** Captured as D-204..D-207. Seed sources prioritized: (1) viled-fetch-results.json from spike, (2) viled-home-brands-extract.json, (3) first probe-crawl in Phase 2 Wave 0. Manual RU/EN variants for brands with explicit kyrillic variants only. Read-once at run start; no hot-reload — weekly cron run is ~1h.

---

## NORM-06 review queue format

| Option | Description | Selected |
|--------|-------------|----------|
| File-based: .planning/runs/{run_id}/norm06-review.md (Recommended) | Markdown table per run; operator opens in Obsidian/editor; consistent with Phase 3 .planning/runs/ artifacts (sitemap-slugs.txt + runs.json). | ✓ |
| DB table norm06_review | Queryable, audit trail via SQL. But operator workflow via SQL/Excel-export is overhead for v1 internal tool. | |
| Both: file primary + DB audit | Double overhead, double-source-of-truth risk. | |

**User's choice:** Recommended (file-based markdown, single source of truth).
**Notes:** Captured as D-208..D-211. Schema: brand_or_slug | source (viled-unmatched | goldapple-new-slug) | run_id | status (pending|aliased|skip|reviewed). Audit trail = git history of `.planning/runs/{id}/norm06-review.md`. NO DB-table backup on v1; v2 territory if trend analytics needed.

---

## Stub cutover & module structure

| Option | Description | Selected |
|--------|-------------|----------|
| Delete stubs; split modules; mirror goldapple (Recommended) | Real impls in src/ga_crawler/{alias,normalizers,storage}/; stubs deleted from cli.py (tests use conftest.py mocks). viled mirrors goldapple naming (fetchers/viled.py + parsers/viled_nextdata.py). Single storage/sqlite.py module (200-300 lines). | ✓ |
| Keep stubs as --dev-stubs flag, otherwise same as Recommended | Stubs move to src/ga_crawler/storage/stubs.py, CLI has --dev-stubs option for fast dev-runs without SQLite. Risk of divergence between stub vs real code paths. | |
| Delete stubs; split storage on 3 files | src/ga_crawler/storage/{runs,snapshots,stats}.py — more modular. Each file 80-120 lines. Overhead for v1; cleaner for scaling. | |

**User's choice:** Recommended (delete stubs, single storage module, mirror goldapple naming).
**Notes:** Captured as D-212..D-216. No `--dev-stubs` flag — runtime divergence between dev/prod = risk. Tests use conftest.py mocks (already 11 fixtures shipped per Phase 3 Wave 0). Refactor storage if exceeds 500 lines.

---

## Mid-flight Scope Clarification (2026-05-07)

User clarified mid-discuss: viled crawl scope is NOT the full luxury catalog (clothing, bags, shoes, accessories). Restricted to **beauty + parfumery only** via 2 specific catalog endpoints:
- `https://viled.kz/men/catalog/1310`
- `https://viled.kz/women/catalog/1310`

**Rationale:** Goldapple is a beauty/parfumery retailer. Matching clothing/bags from viled against goldapple has no commercial value. Scope-narrowing aligns viled crawl with Phase 4 matcher's strict-key invariant (brand+name+volume) — only beauty SKUs are matchable.

**Cascading revisions to discussion outputs:**
- D-201: seed N revised from 20000 (full sitemap) → 100 (catalog/1310 sub-catalog, ~30-40% of expected baseline)
- D-223 NEW: catalog-page enumeration replaces sitemap-only (sitemap has no category metadata for filtering)
- D-224 NEW: enumeration mechanism = `__NEXT_DATA__` pagination on category page (likely), HTML pagination fallback, internal Next.js API as optimization
- D-225 NEW: per-catalog rate-limit + concurrency=1 across both endpoints, sequential men → women
- D-226 NEW: expected URL pool ~100-600 SKUs (refined Wave 0 probe)
- D-227 NEW: catalog endpoints in `pyproject.toml [tool.ga_crawler.crawl.viled] catalog_urls = [...]`

**Spike RECON-02 caveat:** Phase 1 spike used 15 random `/item/{id}` URLs (not from catalog/1310). Spike validated `curl_cffi` Tier 0 feasibility (15/15 success at 2s pause), NOT category structure. Wave 0 of Phase 2 will probe catalog/1310 endpoints to confirm enumeration mechanism + URL pool size.

---

## Claude's Discretion

Items not explicitly asked but auto-decided based on locked context. User may revisit any:

- **Volume normalizer (NORM-03)**: layered approach (regex tokenize → unit-table lookup → multipack-detect). Spike payloads show multilocale (`мл/ml/oz/шт`).
- **Stock-state mapping (PARSE-06)**: D-217 — `attributes.in_stock` boolean → IN_STOCK/OUT_OF_STOCK; HTTP 404 → DELISTED; 301/302 → URL_CHANGED; exception → UNKNOWN; UNAVAILABLE for not-orderable intermediate. MEDIUM confidence — Wave 0 verifies against `viled-nextdata-shape.json`.
- **Hard-fail invariant (PARSE-05)**: D-218 — aggregate post-crawl gate, parallel CRAWL-05 N-gate. >5% null on required fields → runs.status='failed', reason='parse_quality_below_threshold'.
- **DATA-06 backup**: D-219 — Phase 2 ships `bin/backup.sh` (online `sqlite3 .backup` + 4-rotate `ls -t | tail -n +5 | xargs rm -f`); Phase 7 adds cron entry.
- **Alembic**: D-220 — skip on day 1 per CLAUDE.md; add at first migration.
- **CRAWL-01 brand-list provenance**: D-221 — derive from `v_current_snapshots.brand_norm` SQL view; no separate brand-list extraction step.
- **Test infrastructure inheritance**: D-222 — inherit Phase 3 conftest.py + add viled-specific fixtures (viled_pdp_html, brand_alias_yaml_fixture, in_memory_sqlite_session).
- **Module organization**: split normalizers into 3 files (`brand,name,volume.py`); single storage module; viled fetcher/parser mirror goldapple structure.
- **Volume unit-table contents**: planner extracts mapping from spike payloads at Wave 0.
- **HTTP retry classes for curl_cffi**: planner verifies `curl_cffi.requests.errors.*` exception classes at Wave 0; mirror Phase 3 tenacity policy.
- **viled `__NEXT_DATA__` JSON paths**: planner extracts dot-paths from `viled-nextdata-shape.json` + first probe-fetch.
- **Concurrency for viled curl_cffi**: sync `for` loop with `time.sleep(2)` (NOT async); goldapple stays async (Camoufox lifecycle), viled stays sync. Orchestrator composes.
- **JSONB column type**: SQLite TEXT-encoded JSON; raw SQL `json_patch(stats, ?)` for atomic merge.

---

## Deferred Ideas

Captured for future phases (avoid scope creep on Phase 2):

- `--dev-stubs` flag — rejected (D-212): runtime divergence risk
- Richer brand-alias YAML schema (canonical, category) — rejected on v1 (D-205): PROJECT.md strict-key locked; v2 territory
- Auto-tune `sanity_gate_n` — permanently rejected (D-203 contra)
- DB-table backup for NORM-06 review queue — rejected on v1 (D-210); v2 trend analytics
- Persistent `goldapple_count + viled_count` separate table — rejected: `runs.stats` json_patch handles
- Hot-reload brand-alias YAML during run — rejected (D-207)
- Storage split into 3 files — rejected (D-214): overkill for v1
- alembic on day 1 — rejected (D-220)
- VACUUM INTO for backup — rejected (D-219): online `.backup` is atomic + WAL-safe
- Cron entry for backup in Phase 2 — rejected: Phase 7 ops-playbook
- Async curl_cffi for viled symmetry with goldapple — open; default sync
- viled JSON-LD parser fallback — rejected (plan 01-07 empirical 0/15)
- CRAWL-01 separate brand-list extraction step — rejected (D-221)
- Multipack price-per-unit splitting / kit decomposition — rejected on v1 (PROJECT.md NORM-04)
- Camoufox for viled fallback — rejected on v1
- Real-time viled probe (mid-week) — out-of-scope (PROJECT.md weekly cadence)
