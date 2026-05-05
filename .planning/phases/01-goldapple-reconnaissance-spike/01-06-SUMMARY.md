---
phase: 01-goldapple-reconnaissance-spike
plan: 06
subsystem: research

tags: [json-endpoint-hunt, anti-bot, patchright, groupib, facct, recon, goldapple, network-trace]

requires:
  - phase: 01-goldapple-reconnaissance-spike
    provides: "patchright + chromium installed (01-02); committed rate-limit goldapple=3-5s random uniform (01-04); goldapple-all-urls.txt URL pool with selected brands (01-05)"

provides:
  - "Programmatic Patchright network trace of 7 goldapple URLs (256 events captured)"
  - "Definitive negative finding: Patchright on KZ-laptop direct (no proxy) does NOT pass goldapple gate (0/7 successful HTML loads even at 20-25s wait)"
  - "Anti-bot vendor identified: GroupIB / F.A.C.C.T. (NOT Cloudflare/DataDome) — fundamental shift in expected escalation tree"
  - "Gate API mapped: POST /web/api/v1/settings (24/24=403); telemetry sinks /front/api/event* and sp.goldapple.ru/front/api/apm/events"
  - "D-14 ALERT: JSON-LD verification deferred to 01-08 (cannot confirm/deny on real product HTML without first passing the gate)"
  - "5 explicit implications for 01-08: revive 01-03 IPRoyal, add Camoufox as primary candidate, consider warmup pattern, KZ-IP-geo hypothesis flag, EU-Hetzner-may-be-worse-than-KZ-residential"
  - "Reproducible recon script for re-test in 01-08 (.planning/spikes/01-goldapple/scripts/01-06-network-hunt.py)"

affects: [plan 01-03, plan 01-08, plan 01-09, plan 01-10, plan 01-11, Phase 3, Phase 7]

tech-stack:
  added: []
  patterns:
    - "Patchright persistent context per D-04 (cookies live across page-loads); headless=False for spot-watching first run, flip True for 01-08 batch."
    - "Network capture pattern: page.on('request') + page.on('response') on a shared captured[] list with current-label tagging — produces machine-readable trace for post-hoc analysis (deterministic, re-analyzable, faster than human DevTools)."
    - "Render markers: per-page snapshot of (title, html_size, has_next_data, has_jsonld, still_challenge, render_seconds) — proxies for 'real content vs challenge shell' detection."
    - "Browser-state directory `.planning/spikes/01-goldapple/browser-state/` (gitignored per 01-01); delete before re-run for fresh session."
    - "Artifact hygiene continued from 01-04/05/07: byte-equivalent challenge shells deduplicated, 1 sample retained as evidence."

key-files:
  created:
    - ".planning/spikes/01-goldapple/scripts/01-06-network-hunt.py"
    - ".planning/spikes/01-goldapple/sample-payloads/goldapple-network-trace.json"
    - ".planning/spikes/01-goldapple/sample-payloads/goldapple-network-trace.md"
    - ".planning/spikes/01-goldapple/sample-payloads/goldapple-product-html-1.html"
    - ".planning/spikes/01-goldapple/sample-payloads/goldapple-jsonld-sample.json"
  modified:
    - ".planning/spikes/01-goldapple/MEMO.md"

key-decisions:
  - "Task 1 substituted: programmatic Patchright network capture replaces manual DevTools session — pre-authorized by user; deliverables identical (same XHR + render markers data) but in machine-readable form, faster, and reproducible."
  - "Patchright on KZ-laptop direct (D-06 baseline) is empirically rejected: 0/7 gate-clearance — STATE.md gate '≥98/100 + challenge<10% — proxy not needed' decisively fails."
  - "Anti-bot vendor is GroupIB / F.A.C.C.T. (Russian-market rebrand of Singapore-based GroupIB), NOT Cloudflare/DataDome. Material reorder of Phase 3 escalation tree: Camoufox is now a primary 01-08 candidate, not Tier-4 last resort."
  - "01-03 (IPRoyal) revival required before 01-08 starts — sign up to avoid losing a day to KYC. Updates STATE.md '01-03 deferred' decision."
  - "D-14 verification deferred to 01-08 — sample-payloads/goldapple-jsonld-sample.json is empty []; D-14 ALERT logged in trace.md and MEMO."
  - "Phase 7 prod-IP-geo flag added: EU-Hetzner baseline likely WORSE than KZ-residential because GroupIB/F.A.C.C.T. is a Russian-market vendor likely whitelisting local TLD/IP-geo pairs."
  - "Single product-HTML sample retained (the second was byte-equivalent challenge shell, removed per 01-04 hygiene precedent)."

patterns-established:
  - "Programmatic-substitute-for-DevTools recon: Patchright with on-event handlers produces same data as a human session in DevTools, with the advantages of being deterministic, re-analyzable, and committed alongside the script."
  - "Negative-result documentation: even when the gate is not cleared, the failure mode (which endpoints are 403 vs 200, which fingerprint bundle is loaded) is itself the load-bearing deliverable."
  - "When a recon step yields a vendor-identification finding, document the implications for the escalation tree explicitly — escalation branches are not interchangeable across vendors."

requirements-completed: [RECON-03]

duration: ~28min
completed: 2026-05-06
---

# Phase 1 Plan 06: JSON-Endpoint Hunt Summary

**Programmatic Patchright network trace finds NO usable Tier-0 JSON endpoint AND empirically confirms Tier-2 baseline (KZ-laptop direct, no proxy) is INSUFFICIENT to clear goldapple's gate (0/7); identifies anti-bot vendor as GroupIB / F.A.C.C.T. (not Cloudflare/DataDome) — fundamental reorder of the expected Phase 3 escalation tree.**

## Performance

- **Duration:** ~28 min (Task 1 ~12min + Task 2 ~10min + Task 3 ~6min)
- **Started:** 2026-05-06T~17:00Z (approx)
- **Completed:** 2026-05-06T~17:28Z
- **Tasks:** 3/3 (Task 1 substituted with programmatic capture per user pre-authorization)
- **Files created:** 5 (1 helper script + 4 sample payloads)
- **Files modified:** 1 (`MEMO.md` — populated `## JSON-endpoint hunt verdict (D-09, D-10)` section)

## Accomplishments

- **Programmatic substitute for plan 01-06 Task 1's manual DevTools session.** `.planning/spikes/01-goldapple/scripts/01-06-network-hunt.py` (Patchright persistent context, KZ-laptop direct, no proxy, 3-5s rate-limit per 01-04, 5+15s wait poll-loop watching for title change away from "checking device") captures 256 events across 7 URLs (home, brands index, 2 brand listings, 3 product/facet pages from selected brands per D-12). Same data as a human DevTools session, just machine-readable, deterministic, and committed alongside the script.
- **Definitive negative finding on Patchright KZ-laptop:** even with 20-25s per-page wait (poll-loop + networkidle), 7/7 pages stuck on the 18,057-byte JS-challenge shell. **0/7 gate-clearance.** STATE.md's deferral gate ("≥98/100 + challenge<10% — proxy not needed") decisively fails — IPRoyal is needed for 01-08.
- **Anti-bot vendor identified: GroupIB / F.A.C.C.T.** (not Cloudflare/DataDome as 01-04 had to leave open). Evidence captured in challenge HTML:
  - `window.gib.init({cid: 'w-goldapple', gafUrl: '//ru.id.facct.ru/id.html'})` — `gib` = GroupIB / F.A.C.C.T. (Russian-market rebrand 2023).
  - `cid: 'w-goldapple'` — paid customer.
  - `error.name = 'GUN_INIT_PAGE'; '403 ошибка нет кук'` — frontend internally calls this the "GUN init" challenge state, logged via Elastic APM.
- **Gate API contract mapped:**
  - `POST /web/api/v1/settings` — the gate. 24/24 attempts = 403 in our session. Frontend retries every 10s; success triggers `location.reload()`.
  - `/front/api/event?u=<uuid>&cfidsw-goldapple=<base64>` — GUN telemetry beacon (per-event fingerprint). Returns 200.
  - `https://sp.goldapple.ru/front/api/apm/events` (POST 202) — Elastic APM sink. Logs denied visitors.
  - `https://ru.id.facct.ru/id.html` (200) — F.A.C.C.T. iframe origin (cross-origin device fingerprint harvest).
  - **No `/_next/data/`, no `__NEXT_DATA__`, no GraphQL, no Magento `/rest/`** observed — the real Next.js app never bootstraps without first passing the gate.
- **D-14 ALERT logged:** JSON-LD verification deferred to plan 01-08 post-gate-clearance. `sample-payloads/goldapple-jsonld-sample.json` is `[]` (challenge shell has no schema.org markup); cannot revise D-14 yet without evidence about the post-gate page.
- **MEMO.md `## JSON-endpoint hunt verdict (D-09, D-10)` populated** (Variant B: "Tier 0 not viable, Tier 2+ required" PLUS the additional finding that Tier 2 baseline is itself insufficient on KZ-laptop). 5 explicit implications for 01-08 captured.

## Task Commits

1. **Task 1: Patchright network-trace hunt for goldapple JSON endpoints** — `0439cb2` (feat)
2. **Task 2: goldapple network-trace findings + GroupIB anti-bot vendor identification** — `42763ca` (docs)
3. **Task 3: MEMO JSON-endpoint hunt verdict (D-09, D-10) — Variant B + Tier-2 baseline insufficient** — `a22034a` (docs)

## Files Created/Modified

- `scripts/01-06-network-hunt.py` (new) — Patchright async script: 7 URL probe with on-request/on-response capture + 20-25s per-page wait (poll-loop watching for title change + networkidle settle) + render-marker extraction + per-product HTML save. Reproducible via `uv run python ...`. ~140 lines.
- `sample-payloads/goldapple-network-trace.json` (new) — 256 events in 3 phases: 127 requests + 122 responses + 7 render-markers. Machine-readable input for re-analysis without re-fetch.
- `sample-payloads/goldapple-network-trace.md` (new) — human-readable summary: per-page metrics table, anti-bot vendor identification with evidence, XHR endpoint table, D-14 ALERT, 5 implications for 01-08, re-run instructions.
- `sample-payloads/goldapple-product-html-1.html` (new) — one evidence GUN challenge shell (~18 KB; the second product-page HTML was byte-equivalent and removed per 01-04 hygiene precedent — only style-id differed).
- `sample-payloads/goldapple-jsonld-sample.json` (new) — `[]` (empty) per D-14 ALERT; valid JSON for assertion compliance.
- `MEMO.md` (modified) — replaced `_TBD_` stub in `## JSON-endpoint hunt verdict (D-09, D-10)` section with full verdict + method + findings + new intel + Phase 3 implications + open risks. Other sections (TL;DR, Problem, Options tested, etc.) intentionally left as `_TBD_` for plans 01-08..01-11.

## Decisions Made

See `key-decisions` in frontmatter. Most consequential:

1. **Anti-bot vendor is GroupIB / F.A.C.C.T., not Cloudflare/DataDome.** This is **load-bearing** for the rest of Phase 1 because the expected escalation tree (Patchright → Patchright+proxy → Camoufox → managed unblocker) was calibrated against Cloudflare/DataDome benchmarks. GroupIB is a Russian-market vendor not in those benchmarks; the right escalation order may be Patchright → Camoufox → Patchright+proxy (different fingerprint surface gets us further than just adding a residential IP from the same Chromium fingerprint).
2. **Tier-2 baseline INSUFFICIENT.** STATE.md's deferral logic for plan 01-03 (IPRoyal) explicitly required "if ≥98/100 + challenge<10% — proxy not needed". 0/7 ≪ 98 — IPRoyal is **required**, not optional, for 01-08.
3. **D-14 verification deferred** — cannot revise the success criterion without first reaching real product HTML. 01-08 must validate `__NEXT_DATA__` / JSON-LD presence on a post-gate page before any commitment to D-14 alternatives.

No deviations from locked decisions D-01..D-16; this plan **adds** new empirical decisions on top of locked ones (vendor identification, baseline insufficiency, escalation reorder).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Task 1 checkpoint:human-verify substituted by programmatic Patchright probe**
- **Found during:** Task 1 (start of plan)
- **Issue:** Plan defines Task 1 as `<task type="checkpoint:human-verify">` — manual DevTools investigation. User MEMORY.md explicitly prefers "YOLO/autonomous execution"; user pre-authorized this specific substitution in the executor spawn prompt with the rationale: 01-04 already established every goldapple HTML route is JS-gated, so DevTools requires loading the same gate-blocked browser anyway; programmatic capture via `page.on('request')`/`page.on('response')` exposes the SAME endpoints DevTools would, just in machine-readable form.
- **Fix:** Wrote `01-06-network-hunt.py` that runs Patchright headed (so operator can spot-watch first run) with full network event capture across 7 URLs at 3-5s rate-limit per 01-04. Persistent context per D-04. KZ-laptop direct (D-06).
- **Files modified:** `scripts/01-06-network-hunt.py` (new), `sample-payloads/goldapple-network-trace.json` (new)
- **Verification:** Trace JSON contains 256 events, 7 render-markers, 5 distinct non-static endpoint patterns. All deliverables the plan asks for (XHR list, NEXT_DATA/JSON-LD presence, anti-bot signals) are populated from this trace.
- **Committed in:** `0439cb2` (Task 1 commit).

**2. [Rule 1 - Bug fix] Initial 5-second wait was insufficient for the JS-challenge to potentially auto-resolve**
- **Found during:** First run of `01-06-network-hunt.py` (all 7/7 still on challenge shell)
- **Issue:** Initial implementation waited a fixed 5 seconds after `domcontentloaded` and immediately captured HTML. While the result (challenge unfilled) was the same as the eventual finding, 5s was too short to definitively conclude "Patchright cannot pass". A challenge that auto-resolves at 8-15s would have been incorrectly classified as "fails" with only 5s of slack.
- **Fix:** Replaced fixed 5s wait with a 20s poll-loop (`while time.monotonic() < deadline: poll page.title() every 1.5s, break early when title changes off 'checking device'`) plus `wait_for_load_state("networkidle", timeout=5000)`. Cleared `browser-state/` between runs for a clean session test.
- **Verification:** Re-ran with the longer wait; result was unchanged (7/7 still on challenge shell), but now the conclusion is robust because we waited up to 25s.
- **Committed in:** `0439cb2` (Task 1 commit, in same script).

**3. [Rule 1 - Bug avoidance] Stripped byte-equivalent product-HTML duplicate**
- **Found during:** Pre-Task-1-commit hygiene
- **Issue:** Plan asks for `goldapple-product-html-1.html` AND `goldapple-product-html-2.html` (different brands). Both fetched (Givenchy and Creed) but the captured HTMLs are byte-equivalent challenge shells (only the inline `<style id="_s..."` per-render fingerprint differs by digits). Committing both wastes git space and obscures the audit signal.
- **Fix:** Kept `goldapple-product-html-1.html` as single evidence sample; deleted `goldapple-product-html-2.html`. Documented in trace.md ("the other was byte-equivalent and removed per 01-04 hygiene precedent"). Same hygiene pattern as plan 01-04 (which stripped 9 byte-identical challenge shells).
- **Files modified:** `.planning/spikes/01-goldapple/sample-payloads/`
- **Verification:** `git status` showed exactly 1 product-HTML before commit; trace.md explicitly documents the dedup decision.
- **Committed in:** `0439cb2` (Task 1 commit).

---

**Total deviations:** 3 auto-fixed (1 blocking-issue resolution = checkpoint substitution; 1 bug fix = wait-loop logic; 1 artifact-hygiene = consistent with 01-04/05/07 pattern).
**Impact on plan:** Zero scope creep. Task 1 substitution authorized by user; all original deliverables (XHR table, NEXT_DATA/JSON-LD verdict, sample HTML, anti-bot signals, MEMO verdict) are produced via different (programmatic) gathering method.

## Issues Encountered

- **Patchright failed the goldapple gate on default fingerprint + KZ-laptop direct (no proxy).** This is the loud-flag finding for 01-08. Documented thoroughly in trace.md and MEMO.md so 01-08 planner doesn't re-discover it.
- **PowerShell stdout `—` (em-dash) Cyrillic display:** cosmetic only; the script's print statements show `Gold Apple � checking device` because Windows cp1251 cannot render the em-dash. The actual HTML and trace JSON are saved as proper UTF-8. Same family of issue as 01-05 deviation 2 — script avoided non-ASCII glyphs in print() output (used `->` and ASCII labels) and PYTHONIOENCODING=utf-8 was set as belt-and-suspenders, but the em-dash in the page title comes from goldapple's HTML itself, not from our script.
- **No real product HTML reached** — Phase 3 parser implementation is blocked on 01-08 confirming a path past the gate.

## User Setup Required

None for this plan — entirely autonomous, read-only HTTP via Patchright, no credentials, no external service config.

**For 01-08, however:** revive plan 01-03 (IPRoyal trial registration) FIRST. Cannot run a meaningful Tier-2.5 / Tier-3 100-fetch experiment without proxy.

## Authentication Gates

None encountered.

## Next Phase Readiness

- **Plan 01-03 (IPRoyal) — REVIVE REQUIRED:** STATE.md deferred 01-03 with "if ≥98/100 + challenge<10% — proxy not needed". Empirical 0/7 invalidates the deferral. Recommend executing 01-03 BEFORE 01-08.
- **Plan 01-08 (Patchright Tier-2 100-fetch from KZ-laptop) — RECONFIGURED INPUT:**
  - Baseline (no proxy) is **expected to fail** based on this plan's 0/7. Run anyway as the empirical confirmation step (D-13/D-14/D-15 require numbers, not just "failed").
  - Add Camoufox as parallel-track candidate to be tested alongside / immediately after Patchright (escalation reorder).
  - Consider 5-15 minute warmup pattern (idle browse static pages, scroll, etc.) before first product fetch.
  - Pre-flight: confirm sitemap.xml is still plain-deliverable (per 01-05 — should be unchanged, but defensive).
- **Plan 01-09 (EU/RU residential proxy 100-fetch) — REPRIORITIZED:**
  - Hetzner-EU baseline (Phase 7 prod-IP candidate) likely WORSE than KZ-residential — flagged in MEMO.
  - 01-09 should test BOTH: EU-IPRoyal (originally planned) AND KZ-IPRoyal (new candidate motivated by GroupIB local-whitelist hypothesis).
- **Plan 01-10 (Tier-3 escalation if 01-08/01-09 fail) — RECALIBRATED:**
  - Original plan: residential proxy as primary escalation. Now: Camoufox as primary escalation (different fingerprint surface), proxy as orthogonal axis.
- **Plan 01-11 (MEMO finalize) — input ready:** JSON-endpoint-hunt section already populated with explicit verdict + 5 Phase-3 implications. Section ready for cross-link from TL;DR.
- **Phase 3 parser implementation — STILL BLOCKED** on a successful goldapple HTML fetch in 01-08+. `__NEXT_DATA__` / JSON-LD presence on real product page is unverified.
- **Phase 7 (KZ-legal review + prod-IP-geo) — input bundle expanded:** the GroupIB/F.A.C.C.T. vendor finding adds a new Phase 7 risk item: managed-unblocker fallback economics if 01-08+01-10 also fail.

---

## Self-Check: PASSED

**Files created (verified to exist):**
- `.planning/spikes/01-goldapple/scripts/01-06-network-hunt.py` ✓
- `.planning/spikes/01-goldapple/sample-payloads/goldapple-network-trace.json` ✓
- `.planning/spikes/01-goldapple/sample-payloads/goldapple-network-trace.md` ✓
- `.planning/spikes/01-goldapple/sample-payloads/goldapple-product-html-1.html` ✓
- `.planning/spikes/01-goldapple/sample-payloads/goldapple-jsonld-sample.json` ✓
- `.planning/spikes/01-goldapple/MEMO.md` (modified) ✓

**Commits verified in `git log`:**
- `0439cb2` (Task 1 — Patchright network-trace hunt) ✓
- `42763ca` (Task 2 — trace findings + GroupIB identification) ✓
- `a22034a` (Task 3 — MEMO verdict) ✓

**Plan-level acceptance criteria:**
- `test -f sample-payloads/goldapple-network-trace.md` ✓
- `test -f sample-payloads/goldapple-jsonld-sample.json` ✓
- `grep -c "## Verdict" goldapple-network-trace.md` ≥ 1 (= 1) ✓
- `grep -c "XHR" goldapple-network-trace.md` ≥ 1 (= 2) ✓
- JSON-LD sample is valid JSON `[]` with explicit "D-14 ALERT" pointer in trace.md ✓
- No `_TBD_` in trace.md (`grep -c "_TBD_"` = 0) ✓
- `grep -c "## JSON-endpoint hunt verdict (D-09, D-10)"` MEMO.md ≥ 1 (= 1) ✓
- `grep "Verdict:"` MEMO.md ≥ 1 ✓
- `grep "goldapple-network-trace.md"` MEMO.md ≥ 1 (= 2) ✓
- `grep "Implications for Phase 3"` MEMO.md ≥ 2 (= 2) ✓

---

*Phase: 01-goldapple-reconnaissance-spike*
*Completed: 2026-05-06*
