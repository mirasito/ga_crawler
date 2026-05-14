---
phase: 2
slug: project-skeleton-viled-crawl-storage
audited: 2026-05-14
asvs_level: 1
threats_open: 0
threats_closed: 3
threats_total: 3
block_on: open
---

# Phase 2 Security Audit — Project Skeleton: Viled Crawl + Storage

Retroactive audit executed 2026-05-14. Phase shipped 2026-05-07. All mitigations verified against production code; no implementation changes made (read-only audit per role constraint).

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-02-01 | Injection / SQL layer | mitigate | CLOSED | `src/ga_crawler/storage/sqlite.py:279-321` — all three `SqliteRunWriter` mutating methods (`patch_stats`, `fail`, `finalize`) use `text(":param")` + `params=` dict exclusively. Zero f-string or %-formatted SQL found in storage module (grep for `f".*UPDATE\|f".*INSERT\|%.*SELECT` returns no matches). |
| T-02-02 | Tampering / untrusted HTML | accept | CLOSED | Accepted risk; no sandbox required for public product catalog parsing. Risk bounded by three layered controls: (a) per-SKU isolation via `fetch_one_isolated` in `src/ga_crawler/fetchers/viled.py:119-141` (CRAWL-03) — one bad product does not abort the run; (b) sanity-N gate `final_threshold_gate` in `src/ga_crawler/runner/gates.py:256-261` (D-203) catches wholesale parse failures; (c) parse-quality gate `parse_quality_gate` in `src/ga_crawler/runner/gates.py:267-282` (D-218) — aborts run if >5% required fields null. |
| T-02-03 | Information Disclosure / .env | mitigate | CLOSED | Three sub-controls all verified: (1) `find_dotenv(usecwd=True)` + `load_dotenv()` present ONLY in `src/ga_crawler/cli.py:287-289` (`_cmd_deliver` handler); structural canary `test_load_dotenv_only_in_cli` in `tests/test_phase07_structural_canaries.py:122-134` enforces uniqueness across all `src/` modules. (2) `.env` gitignored at `.gitignore:25` (`# Secrets (D-08)`). (3) `.env.example` committed with placeholder values only (all values empty strings). (4) README.md §2 step 7 (line 51) documents `chmod 0600 .env` as mandatory operator step with inline comment `# T-07-08 mitigation`. |

## Accepted Risks Log

### T-02-02 — Tampering via untrusted HTML deserialization

**Rationale:** `selectolax` / `__NEXT_DATA__` JSON deserialization operates on public product catalog HTML from viled.kz. The threat surface is limited: input is HTML fetched by the operator's own process from a known-good retailer domain; there is no user-controlled input path. Full sandboxing (e.g., subprocess isolation) would add significant complexity with negligible security gain given the domain.

**Residual risk:** A maliciously crafted or compromised viled.kz response could trigger unexpected parse behavior. Bounded by: CRAWL-03 per-SKU isolation (blast radius = one SKU), PARSE-05 parse-quality gate (detects wholesale corruption), and CRAWL-05 sanity-N gate (detects catalog-level failure).

**Owner:** Engineering. No further action required for v1.

## Unregistered Flags

SUMMARY.md `## Threat Flags` section states: `none — retroactive reconstruction`. No unregistered attack surface to record.

## Audit Notes

- T-02-03 `find_dotenv(usecwd=True)` anchor was introduced as a hotfix (commit `43dbfd7`) after a real Telegram data egress incident during subprocess tests. The pattern is load-bearing — default `find_dotenv()` walks from `__file__` and always locates the project `.env` regardless of test working directory. The `usecwd=True` form anchors discovery to `os.getcwd()`, making tmp-cwd subprocess tests credential-free.
- The structural canary (`test_load_dotenv_only_in_cli`) is present in three test files providing overlapping coverage: `tests/test_phase07_structural_canaries.py`, `tests/test_delivery_source_lock.py`, and `tests/integration/test_cli_deliver.py`.
- No ESCALATE conditions found. All declared mitigations are present in the cited locations.
