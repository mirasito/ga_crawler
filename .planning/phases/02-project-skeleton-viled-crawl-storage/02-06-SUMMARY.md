---
phase: 02-project-skeleton-viled-crawl-storage
plan: 06
subsystem: infra
tags: [yaml, sqlite, backup, retention, brand-alias, scope-narrowing, doc-cascade]

requires:
  - phase: 02-project-skeleton-viled-crawl-storage (Plans 02-01 to 02-05)
    provides: storage layer (SqliteRunWriter / SqliteSnapshotWriter / init_db); YamlBrandAlias loader (NORM-01 read-once D-207); ParseDispatcher; viled crawler stack (fetcher + parser + enumerator + ViledConfig); orchestrator (run_viled_phase + run_weekly + cli weekly-run)
provides:
  - "config/brand-aliases.yaml — production seed of 58 canonical brands with 46 Cyrillic alias entries (D-206 priority order)"
  - "bin/backup.sh — online sqlite3 .backup + 4-rotate retention shell script (D-219; atomic + WAL-safe per RESEARCH §Pitfall 3)"
  - "backups/ directory tracked via .gitkeep with .gitignore excluding *.db"
  - "tests/integration/test_backup_script.py — 4 GREEN integration tests for DATA-06 (atomic backup + rotation + missing source error + auto-mkdir)"
  - "Phase 2 close-out: NORM-01 + DATA-06 closed. All 22 v1 Phase 2 requirements satisfied."
  - "Doc cascades to REQUIREMENTS.md (CRAWL-01 + DATA-06 + NORM-01 + traceability) + PROJECT.md (v1 active list scope-narrowed) + ROADMAP.md (Phase 2 description + criterion + plan-list scope-narrowed) + STATE.md (Phase 2 marked complete; 27 D-2XX decisions appended; progress 2/7)"
affects: [04-matcher, 07-scheduler-ops, all-future-phases-using-brand-alias-or-backup]

tech-stack:
  added:
    - "GNU xargs `-d '\\n'` (newline-only delimiter to handle Windows backslash paths under Git Bash)"
  patterns:
    - "Operator-edited config YAML committed to git; read-once at run start (D-207)"
    - "Online sqlite3 .backup over VACUUM INTO (atomic + WAL-safe; D-219)"
    - "Cross-platform shell scripts: explicit Git Bash path resolution + xargs newline-delimiter"

key-files:
  created:
    - "config/brand-aliases.yaml (58 canonical brands; 46 Cyrillic aliases)"
    - "bin/backup.sh (executable; online sqlite3 .backup + 4-rotate)"
    - "backups/.gitkeep"
    - "tests/integration/test_backup_script.py (4 GREEN tests; replaces skip-stub)"
  modified:
    - ".gitignore (backups/*.db + prices.db rules)"
    - ".planning/REQUIREMENTS.md (CRAWL-01 description + DATA-06/NORM-01 closure + traceability)"
    - ".planning/PROJECT.md (v1 active list scope-narrowed)"
    - ".planning/ROADMAP.md (Phase 2 description + success criterion 1 + plan-list)"
    - ".planning/STATE.md (Phase 2 COMPLETE; 27 D-2XX decisions appended; progress 2/7; Plan 02-06 metrics row)"

key-decisions:
  - "config/brand-aliases.yaml seed = 58 brands per D-206 priority order (viled-home-brands-extract.json + STATE.md plan 01-05 luxury/perfumery brands; pads above ≥50 floor)"
  - "Canonical YAML keys use snake_case for aliased brands (estee_lauder, givenchy) so test corpus expectations hold; pure-Latin slug-only brands fall through to _normalize_punct (Tom Ford -> tom-ford) without explicit YAML entry"
  - "bin/backup.sh uses online sqlite3 .backup (NOT VACUUM INTO) for atomicity + WAL-safe property"
  - "xargs -d '\\n' required to handle Windows backslash paths in retention rotation pipe (Rule 1 fix in Task 2)"
  - "Test resolves Git Bash explicitly via Program Files candidate list (Microsoft's System32\\bash.exe is aliased to WSL and emits 'WSL not installed' when invoked from non-WSL contexts)"

patterns-established:
  - "Operator config files at repo root /config/ (YAML schema documented inline + loader is single class with read-once semantics)"
  - "Shell-script + integration-test pairing for ops scripts: every script ships alongside a pytest integration test that exercises happy + edge paths"
  - "Doc-cascade pattern: scope-narrowing operator clarifications captured in CONTEXT.md Action Items propagate to REQUIREMENTS / PROJECT / ROADMAP / STATE in the close-out plan with grep-verifiable acceptance"

requirements-completed: [DATA-06, NORM-01]

duration: 12min
completed: 2026-05-07
---

# Phase 2 Plan 06: Wave 5 closeout — alias seed + backup script + scope-narrowing cascades Summary

**58-brand operator-seeded brand-aliases YAML (46 Cyrillic aliases) + online sqlite3 backup script with 4-rotate retention + DATA-06 integration tests + Phase 2 doc cascades — Phase 2 fully closed.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-07T17:50:00Z
- **Completed:** 2026-05-07T18:15:00Z
- **Tasks:** 2
- **Files created:** 4 (`config/brand-aliases.yaml`, `bin/backup.sh`, `backups/.gitkeep`, `tests/integration/test_backup_script.py` rewrite)
- **Files modified:** 5 (`.gitignore`, `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`)

## Accomplishments

- **`config/brand-aliases.yaml` seeded with 58 canonical brands** per D-206 priority order. Cyrillic↔Latin alias coverage for all top luxury+perfumery brands relevant to KZ viled vs goldapple comparison: Estée Lauder ↔ Эсте Лаудер; Givenchy ↔ Живанши; Chanel ↔ Шанель; Dior / Christian Dior ↔ Диор / Кристиан Диор; Tom Ford ↔ Том Форд; Jo Malone London ↔ Джо Малон Лондон; Creed ↔ Крид; Frédéric Malle ↔ Фредерик Маль; Amouage ↔ Амуаж; Kilian ↔ Килиан; Armani ↔ Армани; etc. Pure-Latin homepage extracts (Yuzefi, Aje, YVMIN, etc.) seeded as one-element lists. 46 of the 58 entries carry at least one Cyrillic alias.
- **`bin/backup.sh` ships executable** — `sqlite3 prices.db ".backup backups/$(date +%Y-%m-%d).db"` + retention rotation `ls -t backups/*.db | tail -n +5 | xargs -r -d '\n' rm -f` (keeps 4 most recent). Defaults to `prices.db -> backups/`; supports custom paths via positional args. Documents Phase 7 cron entry inline. Smoke-tested locally: produces 36864-byte backup with all 3 SQLite objects (runs / snapshots / v_current_snapshots) intact.
- **DATA-06 integration tests (4 GREEN)** verify: (1) backup creates valid SQLite at `backups/YYYY-MM-DD.db` with expected schema; (2) 4-rotate retention with 6 stale + 1 new = 7 -> 4 remaining; (3) missing source DB exits non-zero; (4) target dir auto-created via `mkdir -p`.
- **Phase 2 doc cascades propagated** per CONTEXT.md Action Items: REQUIREMENTS.md CRAWL-01 description scope-narrowed; DATA-06 + NORM-01 marked closed with Plan 02-06 references; PROJECT.md v1 list scope-narrowed; ROADMAP.md Phase 2 description + success criterion 1 mention `/men/catalog/1310` + `/women/catalog/1310`; STATE.md Phase 2 marked complete (6/6 plans, 22/22 v1 reqs); 27-decision D-201..D-227 summary + scope-narrowing decision + Phase 2 close-out summary appended to Key Decisions table.
- **Test suite: 381 -> 385 passed (+4 backup tests); 2 -> 1 skipped** (placeholder removed; only intentional viled_run e2e parse-quality skip remains). All 24 Phase 2 test files transitioned from skip-stubs (Plan 02-01) to GREEN over Plans 02-01..02-06. Phase 1 + Phase 3 modules untouched.

## Task Commits

Each task was committed atomically:

1. **Task 1: Seed brand-aliases.yaml + ship bin/backup.sh + backups/ + .gitignore** — `57f1edf` (feat)
2. **Task 2: DATA-06 backup integration tests + scope-narrowing doc cascades** — `d1899c1` (test)

_Task 2 also embeds the bin/backup.sh xargs fix (Rule 1 deviation auto-fixed inline)._

## Files Created/Modified

### Created
- `config/brand-aliases.yaml` — 58 canonical brands, 46 with Cyrillic aliases. D-205 flat-dict schema; canonical keys snake_case for aliased brands; one-element lists for pure-Latin homepage extracts.
- `bin/backup.sh` — executable; defaults `prices.db -> backups/`; documents Phase 7 cron entry inline; exit codes 0/1/2.
- `backups/.gitkeep` — empty marker; preserves directory in git.
- `tests/integration/test_backup_script.py` — 4 GREEN tests (replaces skip-stub from Plan 02-01).

### Modified
- `.gitignore` — explicit `backups/*.db` + `prices.db` rules appended (existing global `*.db` rule preserved; explicit rules document intent for reviewers).
- `.planning/REQUIREMENTS.md` — CRAWL-01 description scope-narrowed; DATA-06 + NORM-01 marked closed; traceability table updated.
- `.planning/PROJECT.md` — v1 active list scope-narrowed.
- `.planning/ROADMAP.md` — Phase 2 description + success criterion 1 amended; Plan 02-06 marked [x]; progress 0/6 -> 6/6 / Complete.
- `.planning/STATE.md` — frontmatter status -> Phase 2 COMPLETE; progress 1/7 -> 2/7; v1 reqs 4/48 -> 27/48; Plan 02-06 added to Plan Execution Metrics; 4 new key-decisions rows.

## Decisions Made

- **Brand seed source priority**: viled-home-brands-extract.json (52 product cards across 5 sections) + STATE.md plan 01-05 brand selection (Jo Malone London, Tom Ford, Creed, Frédéric Malle, Givenchy) + KZ-market luxury/perfumery padding. The viled-fetch-results.json file does NOT carry brand strings (only URL+status+timing), so it served as a confidence proof, not a seed source. Final count 58 (above ≥50 floor) provides margin for the first-week NORM-06 feedback loop without operator scramble.
- **Canonical YAML key format**: snake_case (`estee_lauder`, `givenchy`, `tom_ford`) for aliased brands so the brand-corpus test expectation `expected_brand_norm: "estee_lauder"` holds. Pure-Latin slug-only brands without YAML entries (e.g. Tom Ford in test corpus where `alias_present: false`) fall through to `_normalize_punct(raw)` which returns hyphenated form `tom-ford`. Both cases work — the corpus carefully separates aliased vs pure-slug expectations.
- **Backup atomicity via online .backup, not VACUUM INTO**: matches D-219 + RESEARCH §Pitfall 3. SQLite's `.backup` is page-by-page atomic and WAL-safe; VACUUM INTO requires holding a write lock for the duration which is not safe to run concurrent with a writer. Cron schedule (Phase 7) places backup at 01:00 daily AFTER the weekly Sunday batch completes, but defense-in-depth: the script itself must be safe even if a writer holds the DB.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] xargs strips backslashes from Windows path filenames in pipe input**

- **Found during:** Task 2 (`test_backup_4_rotation_retention` — 7 files remaining instead of 4 after script invocation under pytest)
- **Issue:** The retention command `ls -t "$BACKUP_DIR"/*.db | tail -n +5 | xargs -r rm -f` worked correctly when invoked directly from Git Bash but failed silently when invoked from `subprocess.run([bash, ...])` with Windows-path arguments. Root cause: `xargs` (without `-d`) treats backslashes as escape characters and converts `C:\Users\…\backups/2025-01-15.db` to `C:UsersgstorepcAppDataLocal…backups/2025-01-15.db` — a non-existent path that `rm` silently accepts. Files accumulate without rotation, breaking DATA-06's "minimum 4 backups" requirement.
- **Fix:** Changed retention to `xargs -r -d '\n'` — `-d '\n'` tells GNU xargs to use newline as the ONLY delimiter and disable backslash escape interpretation. This is portable across Linux, macOS, Git Bash, and WSL (all use GNU xargs).
- **Files modified:** `bin/backup.sh`
- **Verification:** `test_backup_4_rotation_retention` flips from FAIL (7 remaining) to PASS (4 remaining); 4/4 backup tests pass; full suite `pytest -m "not live"` 385 passed, 1 skipped.
- **Committed in:** `d1899c1` (Task 2 commit)

**2. [Rule 3 - Blocking] subprocess.run(['bash', ...]) on Windows resolves to WSL, not Git Bash**

- **Found during:** Task 2 (`test_backup_creates_valid_sqlite` — first run output Cyrillic "WSL not installed" message + exit code 1)
- **Issue:** Microsoft ships `C:\Windows\System32\bash.exe` aliased to `wsl.exe` on Windows 10/11. When `subprocess.run(['bash', ...])` resolves via PATH, Windows picks `System32\bash.exe` BEFORE `C:\Program Files\Git\usr\bin\bash.exe` even though Git Bash is on PATH at a lower priority. The result is `wsl.exe` invoking a non-existent Linux distribution and emitting a localized error message.
- **Fix:** `_resolve_bash()` helper checks the canonical Git Bash candidate paths first (`C:\Program Files\Git\usr\bin\bash.exe`, `C:\Program Files (x86)\Git\usr\bin\bash.exe`) before falling back to `shutil.which("bash")`. The test pytestmark uses the resolved path and still falls back to skipif on platforms without bash at all.
- **Files modified:** `tests/integration/test_backup_script.py`
- **Verification:** subprocess.run uses `C:\Program Files\Git\usr\bin\bash.exe` directly; tests run cleanly on Windows; semantics unchanged on Linux/macOS where the Program Files path doesn't exist and the helper falls back to `shutil.which("bash")`.
- **Committed in:** `d1899c1` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 Rule 3 blocking)
**Impact on plan:** Both deviations are environment-specific (Windows + Git Bash + pytest subprocess). On Linux/macOS hosting (Phase 7 Hetzner CX22), neither would have occurred — the rotation pipe would have worked verbatim and `bash` would have resolved correctly. Both fixes are zero-cost on the production target platform; they pay off entirely for local Windows development.

## Issues Encountered

None beyond the two auto-fixed deviations above. The seed list build (Task 1) completed without surprises after consulting the two spike payload sources + STATE.md plan 01-05 brand selection. Backup smoke-test produced a 36864-byte valid SQLite snapshot on first try.

## Stub tracking

No stubs introduced in this plan. The brand-aliases YAML is the production seed (operator extends via PR, NORM-06 review queue feeds back); bin/backup.sh is the production cron target (Phase 7 ops-playbook adds the cron entry).

## Phase 2 Close-out: Requirement Coverage

| Category | Requirements | Status |
|----------|--------------|--------|
| CRAWL | CRAWL-01, CRAWL-03, CRAWL-04, CRAWL-05, CRAWL-06 | All 5 closed (Plans 02-04, 02-05) |
| PARSE | PARSE-01, PARSE-02, PARSE-03, PARSE-04, PARSE-05, PARSE-06 | All 6 closed (Plans 02-04, 02-05) |
| NORM | NORM-01, NORM-02, NORM-03, NORM-04, NORM-05, NORM-06 | All 6 closed (Plans 02-02, 02-03, **02-06**) |
| DATA | DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06 | All 6 closed (Plans 02-02, **02-06**) |

**Phase 2: 22/22 v1 requirements satisfied.**

## Self-Check

Verifying claims before declaring complete:

**1. Files exist:**
- `config/brand-aliases.yaml` — FOUND (58 brands)
- `bin/backup.sh` — FOUND (executable)
- `backups/.gitkeep` — FOUND
- `tests/integration/test_backup_script.py` — FOUND (4 tests, no unconditional skip)

**2. Commits exist:**
- `57f1edf` (Task 1) — FOUND
- `d1899c1` (Task 2) — FOUND

**3. Cascades grep:**
- `grep -c "men/catalog/1310" .planning/REQUIREMENTS.md` = 1 (CRAWL-01 amended)
- `grep -c "men/catalog/1310" .planning/PROJECT.md` = 1 (v1 list amended)
- `grep -c "Phase 2 scope narrowed" .planning/STATE.md` = 1 (decision logged)
- `grep -c "catalog/1310" .planning/ROADMAP.md` = 3 (header + criterion + plan list — exceeds ≥2 floor)

**4. Test suite green:**
- `uv run pytest -m "not live" -q` -> **385 passed, 1 skipped** (intentional parse_quality e2e skip)
- `uv run pytest tests/integration/test_backup_script.py -x -q` -> **4 passed**

**5. No unconditional skips remaining in Phase 2 tests:**
- `grep -rn "pytestmark = pytest.mark.skip[^i]" tests/` returns ZERO matches.

## Self-Check: PASSED

## Cascading Constraints for Phase 4

- **Matcher reads `v_current_snapshots`**: `SELECT * FROM v_current_snapshots WHERE retailer IN ('viled','goldapple')`. The view filters to `MAX(run_id) WHERE status='success'` — Phase 4 must run AFTER both Phase 2 + Phase 3 phase-runners have called `run_writer.finalize(run_id, "success")` (or the view returns 0 rows).
- **Strict-key join**: `JOIN ON viled.brand_norm = goldapple.brand_norm AND viled.name_norm = goldapple.name_norm AND viled.volume_norm = goldapple.volume_norm`. The brand-alias YAML seeded in Plan 02-06 is the canonicalization source for `brand_norm` on both sides — Phase 4's brand-coverage diagnostics should report aliased-vs-unaliased separately.
- **NULL volume_norm rows do NOT match**: per D-215 + Phase 2 normalizer behavior, unparseable volumes emit `volume_norm=NULL`. Phase 4 strict-key join naturally drops these rows; reporter (Phase 5) should surface them as "matchable but excluded due to volume parse failure" diagnostics.
- **Multipack rows excluded from per-unit price comparison**: `WHERE multipack_flag = false` (PROJECT.md NORM-04 contract). Phase 4 reporter still includes them in match-count but flags them in the report.
- **Brand-token bucket index reuse**: Phase 3 ships `index_by_brand_token` (Plan 03-08) which Phase 4 may reuse for fuzzy v2 alias-expansion (REQ MATCH-V2-01..02). Pattern documented in STATE.md key-decisions D-305 entry.
- **Phase 7 ops backlog**: viled XHR pagination beyond page 1 (current limit = 120 SKUs across both catalog/1310 endpoints). Operator-driven; not blocking Phase 4.

## Next Phase Readiness

- **Phase 4 (Matcher) is fully unblocked.** Both retailer pipelines (Phase 2 viled + Phase 3 goldapple) write to the same `snapshots` table at the same quality bar; brand normalization is consistent (shared `Normalizer` facade); brand-alias YAML has production seed data; backup script protects the DB.
- **Phase 7 hosting decision** (Hetzner CX22 EU vs IPRoyal proxy fallback) remains a parallel-track decision — does not block Phase 4 build-out.
- **No blockers, no open critical follow-ups for Phase 4.** Operator can run `/gsd-discuss-phase 4` immediately.

---
*Phase: 02-project-skeleton-viled-crawl-storage*
*Completed: 2026-05-07*
*Phase 2 fully closed. All 22 v1 Phase 2 requirements satisfied. Test suite 385 passed, 1 skipped (intentional).*
