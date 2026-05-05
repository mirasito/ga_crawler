---
phase: 01-goldapple-reconnaissance-spike
plan: 04
subsystem: research

tags: [robots-txt, tos-audit, anti-bot, curl_cffi, recon, kz-legal, sitemap]

requires:
  - phase: 01-goldapple-reconnaissance-spike
    provides: "uv venv with curl_cffi 0.15.0 (plan 01-02); spike directory skeleton + tos-audit.md stub (plan 01-01)"

provides:
  - "Snapshot viled.kz/robots.txt + goldapple.kz/robots.txt (drift baseline)"
  - "viled.kz Privacy Policy plain-text extract (only legal doc found on viled)"
  - "Committed rate-limits per site (viled=2s sequential, goldapple=3-5s random uniform concurrency=1)"
  - "Sitemap URLs for plan 01-05 page-volume estimate (viled+goldapple both declare /sitemap.xml)"
  - "Empirical anti-bot signal for goldapple: every HTML route returns identical 18 912-byte JS-challenge shell"
  - "robots.txt-derived UA strategy signal: goldapple blocks 38 bots incl. SemrushBot/MJ12bot — supports stealth-UA over honest-UA"

affects: [plan 01-05, plan 01-06, plan 01-07, plan 01-08, plan 01-11, Phase 7]

tech-stack:
  added: []
  patterns:
    - "All external fetches go through curl_cffi.requests with impersonate='chrome' (Pitfall 1, CLAUDE.md §Anti-Bot Strategy). Bare requests/httpx forbidden for both target sites."
    - "Recon snapshots saved to .planning/spikes/01-goldapple/sample-payloads/ as drift baseline (D-16); helper scripts kept for reproducibility (one-shot, prefix _)."

key-files:
  created:
    - ".planning/spikes/01-goldapple/_fetch_robots.py"
    - ".planning/spikes/01-goldapple/_fetch_tos.py"
    - ".planning/spikes/01-goldapple/_extract_viled_tos.py"
    - ".planning/spikes/01-goldapple/_scan_tos.py"
    - ".planning/spikes/01-goldapple/sample-payloads/viled-kz-robots.txt"
    - ".planning/spikes/01-goldapple/sample-payloads/goldapple-kz-robots.txt"
    - ".planning/spikes/01-goldapple/sample-payloads/goldapple-rules.html"
    - ".planning/spikes/01-goldapple/sample-payloads/viled-privacy.html"
    - ".planning/spikes/01-goldapple/sample-payloads/viled-privacy.txt"
  modified:
    - ".planning/spikes/01-goldapple/tos-audit.md"

key-decisions:
  - "Committed rate-limit viled.kz = 2s sequential (defaults from Pitfall 13, 2× safety margin since we own the site)"
  - "Committed rate-limit goldapple.kz = 3-5s random uniform, concurrency=1 (D-04 + Pitfall 13; starting point for 01-08 experiment, not final prod value)"
  - "Drop honest-UA strategy (PITFALLS.md Pitfall 14 alt-A): goldapple robots.txt blocks SemrushBot/MJ12bot/BLEXBot/DotBot — competitive-intel UAs are explicitly unwelcome. Use stealth realistic-browser UA via curl_cffi/Patchright impersonation."
  - "Defer goldapple ToS text extraction to post-01-08 (warm Patchright session). Do NOT escalate to Patchright just for ToS — overkill per plan 01-04 guidance."
  - "Keep one goldapple challenge-shell HTML (goldapple-rules.html) as evidence; the 9 byte-identical duplicates not committed."
  - "viled.kz Privacy Policy contains zero anti-scraping clauses (only KZ Law 94-V personal-data regulation) — clean ground legally and morally."

patterns-established:
  - "curl_cffi impersonate=chrome for ALL site fetches in spike (no bare requests/httpx)"
  - "snapshot-and-extract for SPA pages: save raw HTML + plain-text extract from __NEXT_DATA__ JSON blob (viled.kz pattern; likely reusable for product pages in plan 01-07)"
  - "audit-trail: every recon fetcher kept as named _-prefixed script for re-run / drift baseline"

requirements-completed: [RECON-04]

duration: 38min
completed: 2026-05-05
---

# Phase 1 Plan 04: robots.txt + ToS Audit Summary

**Empirical robots/ToS self-review of both targets: viled.kz has no anti-scraping clauses; goldapple.kz gates every HTML route behind a JS-challenge shell that curl_cffi cannot pass — confirming aggressive anti-bot from page 1 and committing 3-5s rate-limit + stealth UA strategy for plan 01-08.**

## Performance

- **Duration:** ~38 min
- **Started:** 2026-05-05T17:42Z (approx — first fetch)
- **Completed:** 2026-05-05T18:19:57Z
- **Tasks:** 2/2
- **Files created:** 9 (4 helper scripts + 5 sample payloads)
- **Files modified:** 1 (`tos-audit.md` — replaced stub with full audit)

## Accomplishments

- Both `robots.txt` files fetched (HTTP 200) via `curl_cffi impersonate=chrome` and snapshotted as drift-baseline (508 B viled, 7303 B goldapple).
- viled.kz `/privacy` (Next.js) successfully extracted: `__NEXT_DATA__` JSON blob → 16 066 chars of plain Russian text → confirmed **zero anti-scraping clauses** (only KZ Law 94-V personal-data regulation).
- goldapple.kz: probed 11 ToS-slug candidates; **all** return identical 18 912-byte JS-challenge shell with DataDome-style UUID-named JS bundle. Documented as a finding (NOT a failure) — strong empirical evidence for D-01 (start at Tier 2 / Patchright).
- `tos-audit.md` rewritten in full: per-site User-agent sections, allowed/disallowed paths, Crawl-delay (none on either), Sitemap URLs, ToS findings, committed rate-limits with rationale, summary table, risks, downstream-plan handoffs.
- Identified 5 downstream signals:
  1. goldapple anti-bot is global, not just product pages.
  2. `/rest/` is robots-Disallowed → JSON-endpoint hunt (plan 01-06) must avoid REST API.
  3. SemrushBot/MJ12bot/BLEXBot blocklist → use stealth UA, not honest UA.
  4. viled has no anti-scraping clause → polite 2s rate is courtesy, not requirement.
  5. Both sites declare `/sitemap.xml` → primary enumeration path for plan 01-05.

## Task Commits

1. **Task 1: Скачать robots.txt + сохранить snapshot'ы** — `198f579` (docs)
2. **Task 2: Прочитать ToS, заполнить tos-audit.md, committed rate-limits** — `83c5150` (docs)

**Plan metadata:** _to be assigned by final commit at end of this plan_

## Files Created/Modified

- `_fetch_robots.py` — one-shot curl_cffi fetcher for both robots.txt; kept for re-run / drift re-check
- `_fetch_tos.py` — probes 18 ToS-slug candidates across both sites, saves only HTTP 200 + size>1.5KB hits
- `_extract_viled_tos.py` — extracts viled `__NEXT_DATA__` JSON blob → plain text (Next.js SPA pattern)
- `_scan_tos.py` — keyword scanner (RU+EN) for anti-scraping clauses in saved HTML files
- `sample-payloads/viled-kz-robots.txt` — viled robots.txt snapshot
- `sample-payloads/goldapple-kz-robots.txt` — goldapple robots.txt snapshot
- `sample-payloads/goldapple-rules.html` — 1 of 11 byte-identical JS-challenge shells (evidence)
- `sample-payloads/viled-privacy.html` — raw 216 KB Next.js Privacy Policy page
- `sample-payloads/viled-privacy.txt` — extracted human-readable Privacy Policy (29 KB)
- `tos-audit.md` — full audit: 240+ lines, two committed rate-limits, summary table, downstream handoffs

## Decisions Made

See `key-decisions` in frontmatter. All consistent with PROJECT.md + CONTEXT.md D-01..D-16 + PITFALLS.md Pitfalls 1, 13, 14. No deviations from locked decisions; this plan **adds** new empirical decisions on top of locked ones (rate-limit numbers, UA-strategy direction).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Saved viled `www.` apex deduplication**
- **Found during:** Task 1
- **Issue:** Plan suggests saving both `viled.kz/robots.txt` and `www.viled.kz/robots.txt` if both serve content. In practice `www` 301-redirects to apex with byte-identical content. Saving both as separate snapshots would create false drift signal in future audit-trail runs (a `www` change could mask an apex change).
- **Fix:** Saved only the canonical `viled-kz-robots.txt`; documented the redirect in `tos-audit.md` ("`www.viled.kz/robots.txt` 301-редиректится на apex и отдаёт идентичный контент, поэтому `www`-snapshot не сохранён").
- **Files modified:** `.planning/spikes/01-goldapple/sample-payloads/`
- **Verification:** `diff` confirmed identical, then `rm` of duplicate.
- **Committed in:** `198f579` (Task 1 commit)

**2. [Rule 1 - Bug avoidance] Stripped 9 byte-identical goldapple challenge-shells**
- **Found during:** Task 2
- **Issue:** `_fetch_tos.py` saved 11 separate HTML files for goldapple ToS-slug candidates, but inspection showed all 11 are byte-identical 18 912-byte JS-challenge shells (`Gold Apple — checking device`). Committing all 11 wastes git space and obscures the audit signal.
- **Fix:** Kept `goldapple-rules.html` as single evidence sample; deleted the other 9 before committing. Documented in `tos-audit.md` ("Один из shell'ов (`/rules`) сохранён в sample-payloads/goldapple-rules.html как evidence; остальные 10 не коммитятся (byte-identical копии — drift baseline избыточен)").
- **Files modified:** `.planning/spikes/01-goldapple/sample-payloads/`
- **Verification:** Pre-commit `git status` showed exactly the kept files; size totals match audit document text.
- **Committed in:** `83c5150` (Task 2 commit)

**3. [Rule 1 - Bug avoidance] Stripped 222 KB intermediate JSON dump**
- **Found during:** Task 2
- **Issue:** `_extract_viled_tos.py` was originally written to save both the raw `__NEXT_DATA__` JSON (222 KB, machine-readable intermediate) and the human-readable plain-text extract (29 KB). The JSON dump duplicates the data already in `viled-privacy.html` and is re-derivable via the same script.
- **Fix:** Deleted `viled-privacy-nextdata.json` before committing. Kept `viled-privacy.html` (raw) + `viled-privacy.txt` (human-readable) as the two-file canonical pair.
- **Files modified:** `.planning/spikes/01-goldapple/sample-payloads/`
- **Verification:** `_extract_viled_tos.py` still recreates the JSON on-demand if needed for further analysis.
- **Committed in:** `83c5150` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all artifact-hygiene cleanups, no logic/correctness deviations from plan).
**Impact on plan:** Zero scope creep. All three deviations reduce committed-noise — same audit conclusions, cleaner git history.

## Issues Encountered

- **PowerShell Cyrillic display in stdout** (cosmetic, not blocking). All fetched Cyrillic content saved correctly to UTF-8 files (verified by Read tool which displayed proper Russian text from `viled-privacy.txt`); only the live console showed mojibake. No data loss.
- **goldapple ToS unobtainable via curl_cffi.** Documented in `tos-audit.md` as a finding (per plan 01-04 guidance: don't escalate to Patchright). Re-fetch deferred to post-01-08 with warm-Patchright session.

## User Setup Required

None — entirely autonomous, read-only HTTP GETs, no credentials, no external service config.

## Next Phase Readiness

- **Plan 01-05 (sitemap / page-volume) — READY:** sitemap URLs delivered (`https://viled.kz/sitemap.xml`, `https://goldapple.kz/sitemap.xml`); D-11 enumeration approach validated.
- **Plan 01-06 (DevTools / JSON-endpoint hunt) — READY with constraint:** `/rest/` is robots-Disallowed for goldapple, so hunt must focus on non-`/rest/` ajax routes + `__NEXT_DATA__` / JSON-LD patterns. viled.kz `__NEXT_DATA__` pattern is confirmed and reusable.
- **Plan 01-07 (viled curl_cffi) — READY:** rate-limit = 2s sequential, sitemap available, no robots-blocked product paths, no anti-scraping clauses.
- **Plan 01-08 (Patchright 100-fetch goldapple) — READY:** rate-limit = 3-5s random uniform, concurrency=1, persistent-context warm; pre-flight check added (validate sitemap.xml plain delivery vs. challenge).
- **Plan 01-11 (MEMO) — input ready:** audit summary will be referenced; committed rate-limits become Phase 3 config constants.
- **Phase 7 (KZ-legal review) — input bundle ready:** audit + Privacy snapshot + both robots snapshots + flag "goldapple ToS not obtainable in spike, requires browser-fetch".

---

## Self-Check: PASSED

**Files created (verified to exist):**
- `.planning/spikes/01-goldapple/tos-audit.md` ✓
- `.planning/spikes/01-goldapple/_fetch_robots.py` ✓
- `.planning/spikes/01-goldapple/_fetch_tos.py` ✓
- `.planning/spikes/01-goldapple/_extract_viled_tos.py` ✓
- `.planning/spikes/01-goldapple/_scan_tos.py` ✓
- `.planning/spikes/01-goldapple/sample-payloads/viled-kz-robots.txt` ✓
- `.planning/spikes/01-goldapple/sample-payloads/goldapple-kz-robots.txt` ✓
- `.planning/spikes/01-goldapple/sample-payloads/goldapple-rules.html` ✓
- `.planning/spikes/01-goldapple/sample-payloads/viled-privacy.html` ✓
- `.planning/spikes/01-goldapple/sample-payloads/viled-privacy.txt` ✓

**Commits verified in `git log`:**
- `198f579` (Task 1) ✓
- `83c5150` (Task 2) ✓

**Plan-level acceptance criteria:** all PASS (run-time verified before commit, see Task 2 verify block).

---

*Phase: 01-goldapple-reconnaissance-spike*
*Completed: 2026-05-05*
