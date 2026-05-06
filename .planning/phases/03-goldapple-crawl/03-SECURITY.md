---
phase: 3
slug: goldapple-crawl
status: verified
threats_open: 0
threats_total: 35
threats_closed: 35
asvs_level: not_configured
block_on: high
created: 2026-05-06
verified: 2026-05-06
---

# Phase 3 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail. Verified against goldapple.kz crawler implementation (`src/ga_crawler/`) on 2026-05-06.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| `pyproject.toml` ↔ `uv.lock` | Dependency integrity — uv.lock pins hashes; tampering elsewhere fails `uv sync --check` | dependency manifests |
| Python imports ↔ Phase 2 modules | Protocol contracts in `interfaces.py` — runtime drift catches at integration (Wave 5) | Protocol contracts (BrandAlias / Normalizer / SnapshotWriter / RunWriter) |
| `curl_cffi` → goldapple sitemap | Untrusted XML response — must validate URL shape before using | sitemap XML |
| Filesystem (`{root}/runs/{run_id}/`) → diff logic | `run_id` is integer; path traversal blocked by Path object construction | sitemap-slugs.txt files |
| Camoufox HTML response → `parse_pdp` | Untrusted user-controlled HTML; selectolax is safe walker (no JS exec) | product PDP HTML |
| `selectolax` → product extraction | Library does not execute JavaScript or fetch external resources | parsed Node tree |
| Camoufox process → goldapple.kz | Tier 2 anti-bot path; spike validated 99/100 | live HTTP traffic |
| Tmp filesystem (profile dir) → process | Profile dir under restrictive `0700` perms (mkdtemp default); contains cookies/fingerprint state | session cookies, browser fingerprint |
| Smoke probe → goldapple | Pre-crawl gate; failure prevents 4-hour run on broken fingerprint | gate decision |
| Stats builder → `runs.stats` DB column | Only `goldapple.*` namespace allowed; `StatsNamespaceError` prevents accidental clobber of `viled.*` keys | stats delta dict |
| CLI argparse → user input | `--viled-brands` parsed by `,` split; `--run-id` is `int` | operator parameters |
| Stub storage → filesystem | Stubs use Path joins; `run_id` is int, no shell interpolation | snapshot/runs JSONL |
| KZ-laptop (operator) → goldapple.kz live | Spike validated 99/100 success at this exact configuration | live production crawl |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-03-01-01 | Tampering | `pyproject.toml` dep pin | mitigate | Exact pin `camoufox[geoip]==0.4.11` per D-313; `uv.lock` integrity hashes verified by `uv sync` | closed |
| T-03-01-02 | Tampering | Camoufox supply-chain | mitigate | D-313 exact pin + coryking fork backup documented in pyproject + manual upgrade workflow with smoke-test gate | closed |
| T-03-01-03 | Tampering | Test fixture file integrity | accept | Read-only spike artifacts under git; tampering leaves git-diff trail | closed |
| T-03-01-04 | Information Disclosure | PII in test fixtures | mitigate | `parse_pdp` ignores `[itemprop="author"]`/review nodes; fixtures are public-only data | closed |
| T-03-02-04 | Tampering | Sitemap-poisoning (attacker-controlled `<loc>` redirect) | mitigate | `PRODUCT_URL_RE` whitelist `^https://goldapple\.kz/(\d+)-[a-z0-9а-я-]+$` rejects non-conforming URLs at intake | closed |
| T-03-02-05 | Tampering | Path traversal via `run_id` | mitigate | `int(run_id)` parse with ValueError skip; pathlib `Path` interpolation safe | closed |
| T-03-02-09 | Denial of Service | Sitemap fetch hangs / 5xx flood | mitigate | tenacity `stop_after_attempt(3)` + `wait_exponential_jitter(initial=2, max=30)` + `SITEMAP_TIMEOUT_S=30` | closed |
| T-03-02-04b | Information Disclosure | Sitemap response logged | accept | Public XML; no PII; structured logging emits only URL + status | closed |
| T-03-03-09 | Tampering | XSS / CSV-injection in product name | mitigate (CSV deferred to Phase 5) | selectolax safe walker; raw text passthrough; CSV escaping = Phase 5 REPORT-* family | closed |
| T-03-03-09b | Tampering | Path traversal via SKU id | mitigate | `sku_id` from microdata or URL slug numeric prefix; no FS use in parser | closed |
| T-03-03-09c | Information Disclosure | PII in scraped HTML | mitigate | Parser extracts only product fields; `[itemprop="author"]`/reviews never accessed | closed |
| T-03-03-02 | Spoofing | Gold Card price treated as public (Pitfall 2) | mitigate | `_extract_top_level_offer` 3-filter: priceSpec subtree, priceType sibling, "при авторизации" ancestor | closed |
| T-03-03-02b | Spoofing | StrikethroughPrice treated as current | mitigate | `_has_excluded_priceType_sibling` rejects; `_extract_strikethrough` captures separately | closed |
| T-03-04-07 | Information Disclosure | Camoufox profile leakage | mitigate | D-311 fresh profile per run via `mkdtemp(prefix="camoufox-run-{run_id}-")`; always-cleanup in `__aexit__` | closed |
| T-03-04-07b | Information Disclosure | Profile dir cleanup race | mitigate | mkdtemp 0700 perms; cron user-isolated; Pitfall 7 always-cleanup | closed |
| T-03-04-09 | Denial of Service | Camoufox C++ binary crash → zombie | mitigate | try/finally `__aexit__` always runs; Phase 7 adds `timeout` cron wrapper | closed |
| T-03-04-09b | Denial of Service | Excessive request rate | mitigate | `random.uniform(3, 5)` + concurrency=1 + tenacity `wait_exponential_jitter` | closed |
| T-03-04-11 | Denial of Service | Per-SKU isolation cascade | mitigate | CRAWL-03 `fetch_one_isolated` try/except + counter; never bubbles | closed |
| T-03-04-08 | Tampering | Camoufox supply-chain (duplicate) | mitigate (deferred to Wave 0) | Inherits T-03-01-02 closure | closed |
| T-03-04-13 | Information Disclosure | structlog logs Cookie/Authorization headers | mitigate | `log.error("fetch_failed", url=..., error=str(e), error_type=...)` only; never log raw response/headers | closed |
| T-03-05-01 | Denial of Service | Smoke-bypass → 4h broken-fingerprint run | mitigate | `smoke_probe` is hard gate; orchestrator MUST call before `run_loop` and abort on `not pass` | closed |
| T-03-05-02 | Denial of Service | Smoke probe URLs go stale | accept (with hook) | A8 quarterly rotation in Phase 7 ops-playbook; `smoke_urls=` override accepted | closed |
| T-03-05-06 | Tampering | Stats namespace contention (clobber `viled.*`) | mitigate | `StatsNamespaceError` raised on any non-`goldapple.*` key | closed |
| T-03-05-11 | Business Logic | M=1000 too low | accept | D-308 explicit choice; D-310 auto-suggest after 4 weeks for data-driven update | closed |
| T-03-05-11b | Business Logic | Auto-suggest M emits inappropriate value | mitigate | `auto_suggest_m` returns None for <4 runs; only suggests, never auto-applies | closed |
| T-03-06-09 | Denial of Service | runs row contention | mitigate | DATA-05: never creates a runs row, only `patch_stats`; atomic merge | closed |
| T-03-06-09b | Denial of Service | Profile dir leak on smoke fail | mitigate | smoke fail explicitly calls `run_writer.fail` + `patch_stats`; `__aexit__` runs even on early return | closed |
| T-03-06-11 | Business Logic | Auto-suggest before 4+ runs | mitigate | None for <4 runs; only added to delta if not None | closed |
| T-03-06-12 | Information Disclosure | `.planning/runs/` committed accidentally | mitigate | `.gitignore` line 50: `.planning/runs/` (verified) | closed |
| T-03-06-13 | Tampering | Phase 2 protocol drift | mitigate (deferred) | Wave 0 froze Protocols; Phase 2 reviewer cross-checks at Phase 2 implementation | closed |
| T-03-06-09c | Denial of Service | Per-SKU isolation cascade (inherited) | mitigate | Inherits T-03-04-11 closure | closed |
| T-03-07-02 | Denial of Service | Anti-bot regression / `gate_shell_count > 5%` | mitigate | Live smoke is the gate; checklist marks BLOCKED-FINGERPRINT-REGRESSION; Phase 7 reactivates IPRoyal trial (D-08) | closed |
| T-03-07-08 | Tampering | Camoufox version drift between Wave 0 pin and live runtime | mitigate | Step 3 verifies `goldapple.camoufox_version == 135.0.1.beta24`; advisory: stats records wrapper version (`0.4.11`) — Firefox build transitively pinned via wrapper | closed |
| T-03-07-09 | Denial of Service | Sustained 429/503 from goldapple | accept (with mitigation) | Rate-limit + concurrency=1 + tenacity in place; operator marks BLOCKED-RATE-LIMIT | closed |
| T-03-07-12 | Information Disclosure | Operator commits live snapshot data | mitigate | `.gitignore` line 50: `.planning/runs/` (T-03-06-12) | closed |
| T-03-07-07 | Information Disclosure | Profile dir lingers with cookie state | mitigate | `__aexit__` cleanup; live-smoke-checklist Step 5 verified 0 lingering dirs | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-03-01 | T-03-01-03 | Test fixtures are read-only spike artifacts under git; tampering leaves git-diff trail; low value target | gsd-planner (plan 03-01) | 2026-05-06 |
| AR-03-02 | T-03-02-04b | Sitemap response is public XML; no PII; structured logging emits only URL + status, never body | gsd-planner (plan 03-02) | 2026-05-06 |
| AR-03-03 | T-03-05-02 | Smoke URLs may go stale; quarterly rotation in Phase 7 ops-playbook + operator override surface (`smoke_urls=`) | gsd-planner (plan 03-05) | 2026-05-06 |
| AR-03-04 | T-03-05-11 | M=1000 catastrophic-failure gate (~30% of spike estimate); D-310 operator-confirmed auto-suggest after 4 weeks; not auto-tuned | gsd-planner (plan 03-05) | 2026-05-06 |
| AR-03-05 | T-03-07-09 | Sustained 429/503 from goldapple; existing rate-limit + concurrency=1 + tenacity is the mitigation; operator BLOCKED-RATE-LIMIT escalation in checklist | gsd-planner (plan 03-07) | 2026-05-06 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-06 | 35 | 35 | 0 | gsd-security-auditor (sonnet) — State B (built from PLAN threat models + SUMMARY evidence + impl grep) |

### 2026-05-06 Audit Notes

- Verified read-only against `src/ga_crawler/`, `tests/`, `pyproject.toml`, `.gitignore`
- `.gitignore:50` confirmed contains `.planning/runs/` (closes T-03-06-12 + T-03-07-12)
- All `mitigate` threats have file:line evidence in source
- All `accept` threats have rationale documented in originating PLAN.md
- All `mitigate (deferred)` threats confirm deferred target (Wave 0 / Phase 2 / Phase 5 / Phase 7) — no orphans
- Live operator validation (run-43, 2026-05-06) per `03-VERIFICATION.md` confirms profile-dir cleanup and structured logging hygiene
- One advisory caveat (NOT a gap): T-03-07-08 records Camoufox Python-wrapper version (`0.4.11`) into stats rather than the embedded Firefox build (`135.0.1.beta24`). Transitively safe due to exact wrapper pin in `pyproject.toml:15`. Optional enhancement: extend `_camoufox_version_at_runtime` to expose Firefox build for explicit assertion against `camoufox_version_expected = "135.0.1.beta24"`. Tracked as enhancement, not security gap.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-06
