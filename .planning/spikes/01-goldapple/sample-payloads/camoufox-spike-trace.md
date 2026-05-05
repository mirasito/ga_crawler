# Camoufox Spike Trace (sibling experiment to 01-06)

**Investigation date:** 2026-05-06
**Operator:** mirdbek@gmail.com
**Method:** Camoufox v135.0.1-beta.24 (daijro upstream, not coryking fork — daijro still publishes new builds against Firefox 135 as of 2025-Q4; verify maintenance status before Phase 3 production lock-in). Persistent context, KZ-laptop direct, no proxy. `geoip=True`, `locale=['ru-RU','kk-KZ','en-US']`, `humanize=True`. 3 URLs at 3-5s rate-limit.
**Script:** `.planning/spikes/01-goldapple/scripts/01-06b-camoufox-spike.py`
**Trace data:** `.planning/spikes/01-goldapple/sample-payloads/camoufox-spike-trace.json` (688 response events).

## Hypothesis tested

01-06 found goldapple uses **GroupIB / F.A.C.C.T.** anti-bot. Patchright + KZ-laptop = 0/7 gate-pass; the 403 was fingerprint-based, not rate-based. Hypothesis: a different fingerprint surface (Firefox via Camoufox) defeats the gate from the same KZ-laptop IP, no proxy required.

## Result: HYPOTHESIS CONFIRMED

| URL | gate pass | size (bytes) | wait_ms for clearance | JSON-LD | __NEXT_DATA__ |
|-----|:---------:|-------------:|----------------------:|:-------:|:-------------:|
| `/` (home) | ✓ | 724,342 | 0 | ✓ | ✗ |
| `/brands/tom-ford` | ✓ | 376,159 | 0 | ✓ | ✗ |
| `/19000032744-givenchy-gentleman-reserve-privee-eau-de-parfum` | ✓ | 200,040 | 0 | ✓ | ✗ |

**3/3 pages passed instantly** (`wait_ms=0` — title cleared on first poll, no challenge shell rendered). HTML sizes 200KB–724KB are real Next.js app payloads, NOT the 18KB GUN challenge shell.

## Gate API verdict

| Status | Count | Notes |
|-------:|------:|-------|
| 200 | 665 | All normal Next.js asset/API responses |
| 202 | 16 | APM telemetry (same as 01-06; not blocking) |
| 206 | 6 | Range requests (large assets) |
| 302 | 1 | Redirect (likely locale handshake) |
| **403** | **0** | **Gate never denied us.** Compare 01-06: 24/24 gate-403. |

The GroupIB `/web/api/v1/settings` gate cleared on first call. Camoufox's default Firefox fingerprint (with `geoip=True` for KZ timezone/locale alignment + `humanize=True` for jitter) evidently presents a profile GroupIB classifies as legitimate.

## D-14 verifiability — CONFIRMED

D-14 defines "successful fetch" as `HTTP 200 + product JSON-LD found in <script type="application/ld+json">`. **3/3 pages had JSON-LD present.** The product page (`200,040 B`) has a parseable JSON-LD block — D-14 success function works for goldapple.

## __NEXT_DATA__ presence — confirmed absent

0/3 pages contain `__NEXT_DATA__` despite reaching the real app. This means goldapple is **NOT a Next.js application** at the rendering layer (or it uses a non-default Next.js build that strips the data blob server-side). Combined with the `/rest/` Magento robots-block from 01-04, goldapple is most likely a **Magento PWA** or custom React/Vue SPA backed by a Magento backend — JSON-LD becomes the canonical product-data extraction surface.

**Phase 3 parser hint:** parse JSON-LD directly via `selectolax` + `json.loads` of the `<script type="application/ld+json">` content; `Product.offers.price` and `Product.offers.priceCurrency` are the standard fields per Schema.org Product spec. Fallback for non-standard goldapple extensions: parse Open Graph `og:price:amount` / `og:price:currency` meta tags.

## Implications for Phase 1 plan tree

| Plan | Original purpose | New status |
|------|------------------|-----------|
| 01-03 (IPRoyal trial) | Pre-register proxy before Tier-2 test, in case fingerprint-only fails | **NOT NEEDED.** Camoufox + KZ-laptop direct passes the gate. Skip; record decision in MEMO. |
| 01-08 (Patchright Tier-2 100-fetch KZ-laptop) | Validate Patchright Tier 2 on 100 URLs | **REWRITE around Camoufox.** Patchright is empirically broken for goldapple (01-06: 0/7). New 01-08: Camoufox 100-fetch KZ-laptop, same D-13/D-14/D-15 success criteria, same persistent-context discipline (D-04). |
| 01-09 (Patchright Tier-2 + EU residential proxy) | Multi-geo comparison (D-05) | **OPTIONAL / SKIP.** Multi-geo data point's value-of-information drops when fingerprint alone solves the gate. May still want a small proxy comparison run for Phase 7 prod-IP question, but defer until 01-08-camoufox passes ≥95/100. |
| 01-10 (Tier 3 conditional escalation) | If 01-08/01-09 fail | **SKIP.** Triggered only by Tier-2 failure; Tier 2 (now Camoufox) on track to pass. |

## Implications for Phase 3 stack

- **Browser engine:** Camoufox (Firefox-based) — NOT Patchright. Material correction to research/STACK.md.
- **Proxy budget:** $0 baseline (Tier 2 with Camoufox alone). Reserve $5-10/month as contingency only if Camoufox fingerprint drift breaks the gate later.
- **Hosting (Phase 7):** EU Hetzner baseline now LESS risky than 01-06 implied — if fingerprint is the dominant factor (not IP-geo), Hetzner-EU may pass on Camoufox alone too. Verify with one Camoufox fetch through any EU proxy before locking in. If KZ residential is still required, IPRoyal trial reactivates as Phase 7 task.
- **Maintenance risk:** daijro/camoufox is the upstream we used. CLAUDE.md flagged it as unmaintained-as-of-2025; the v135.0.1-beta.24 release (current) is fresher than that flag suggests, but Phase 3 should add a periodic check ("does Camoufox still pass goldapple?") to the operational playbook.

## Re-run

```powershell
cd C:\Users\gstorepc\projects\ga_crawler
$env:PYTHONIOENCODING = "utf-8"
uv run python .planning/spikes/01-goldapple/scripts/01-06b-camoufox-spike.py
```

Expected wall-clock: ~30 sec (3 URLs × 5s rate-limit + 0 gate-wait). Browser state at `.planning/spikes/01-goldapple/.camoufox-state/` (gitignored).

---

*Spike completed by gsd-executor side-experiment on 2026-05-06; result reorganizes plans 01-08/01-09/01-10 and the entire Phase 3 browser-engine decision.*
