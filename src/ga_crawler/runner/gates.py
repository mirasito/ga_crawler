"""Phase 3 runner gates (D-308, D-309, D-310, D-312).

Three gates protect the run:
  1. Smoke probe (D-312) — runs BEFORE crawl. 3 known-good URLs must all
     return 200 + microdata-extractable price. If any fails → runs.status='failed'
     and the 4-hour crawl is aborted to avoid wasting time on broken fingerprint.
  2. Final M-gate (D-308/D-309) — runs AFTER crawl. goldapple_count must
     meet M=1000 (default; configurable). If not → runs.status='failed';
     pre-send sanity-gate (DELIVER-03) blocks business-chat delivery.
  3. Auto-suggest M (D-310) — emits operator-actionable suggestion when 4+
     weeks of history are available. NEVER auto-tunes; operator decides.

Source: 03-RESEARCH.md §"Code Examples" lines 904-955 (verbatim).
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any, Optional

import structlog

from ga_crawler.parsers.goldapple_microdata import has_microdata_price, parse_pdp

log = structlog.get_logger(__name__)


# 3 known-good Givenchy URLs from spike (A12: avoid spike row 0 = 7681000002 stale).
# Operator updates these via Phase 7 ops-playbook rotation procedure.
# Source: 03-RESEARCH.md §"Code Examples" lines 908-913 + A12 mitigation.
# Rotation 2026-05-11 (UAT Phase 3 Test 6): index 0
#   `7680100018-very-irresistible-givenchy` went stale (SKU removed → 30x to
#   home). Replaced with `19000488678-givenchy-irresistible` (current sitemap).
SMOKE_URLS: tuple[str, ...] = (
    "https://goldapple.kz/19000488678-givenchy-irresistible",
    "https://goldapple.kz/7681000001-givenchy-pour-homme-blue-label",
    "https://goldapple.kz/19000032744-givenchy-gentleman-reserve-privee-eau-de-parfum",
)


def load_smoke_urls_from_config(repo_root: Path) -> tuple[str, ...]:
    """Optional override: load smoke URLs from pyproject.toml [tool.ga_crawler.crawl.goldapple.smoke_urls]
    or from config/smoke_urls.txt (one URL per line). If neither exists, returns SMOKE_URLS default.

    This is the operator-facing rotation surface (RESEARCH §Q2 recommendation).
    """
    cfg_file = repo_root / "config" / "smoke_urls.txt"
    if cfg_file.exists():
        urls = tuple(
            ln.strip()
            for ln in cfg_file.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")
        )
        if urls:
            return urls

    # Fall back to pyproject.toml config (parsed by Wave 5 orchestrator; here we
    # accept the constant). Wave 5 may override by passing urls= kwarg directly.
    return SMOKE_URLS


def _camoufox_version_at_runtime() -> str:
    """Best-effort: read installed camoufox version via importlib.metadata.
    Fall back to "unknown" if the package is not installed.

    NOTE: `camoufox.__version__` is a submodule (not a string attribute) in
    the installed package, so `getattr(camoufox, "__version__", ...)` returns
    a module object. `importlib.metadata.version("camoufox")` is the canonical
    way to read the installed version string (PEP 566).
    """
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("camoufox")
        except PackageNotFoundError:
            return "unknown"
    except Exception:
        return "unknown"


async def smoke_probe(fetcher: Any, smoke_urls: tuple[str, ...] = SMOKE_URLS) -> dict:
    """D-312 pre-crawl probe.

    Args:
      fetcher: a GoldappleFetcher inside an active async-context (already booted)
      smoke_urls: optional override (defaults to SMOKE_URLS); 1-3 URLs

    Returns:
      {
        "pass": bool,
        "diagnostics": {
          "camoufox_version": str,
          "responses": [{"url", "status", "size", "title", "price_extracted"}, ...]
        }
      }

    Pass criteria (ALL must hold):
      - Every smoke URL: status == 200 (or 304)
      - Every smoke URL: rec.block is False
      - Every smoke URL: parse_pdp returns a non-None GoldappleRawProduct with current_price > 0

    Source: 03-RESEARCH.md §"Code Examples" lines 906-935 (verbatim).
    """
    results: list[dict] = []
    for url in smoke_urls:
        rec = await fetcher.fetch_one(fetcher._page, url)
        price_extracted = False
        html = rec.get("html") if isinstance(rec, dict) else None
        if html:
            product = parse_pdp(html, url)
            price_extracted = product is not None and product.current_price > 0
        results.append(
            {
                "url": url,
                "status": rec.get("status") if isinstance(rec, dict) else None,
                "size": rec.get("html_size") if isinstance(rec, dict) else None,
                "title": rec.get("title") if isinstance(rec, dict) else None,
                "block": rec.get("block", True) if isinstance(rec, dict) else True,
                "price_extracted": price_extracted,
            }
        )

    diagnostics = {
        "camoufox_version": _camoufox_version_at_runtime(),
        "responses": results,
    }
    passed = (
        all(r["price_extracted"] for r in results)
        and all((r["status"] in (200, 304) and not r["block"]) for r in results)
    )
    log.info(
        "smoke_probe_complete",
        passed=passed,
        url_count=len(results),
        camoufox_version=diagnostics["camoufox_version"],
    )
    return {"pass": passed, "diagnostics": diagnostics}


# ---- D-203 retailer-agnostic refactor (Phase 2 Plan 02-05) ----


def auto_suggest_threshold(
    history_counts: list[int],
    factor: float = 0.7,
    min_runs: int = 4,
) -> Optional[int]:
    """Retailer-agnostic auto-suggest. Returns int(factor × median(last min_runs counts)).

    Returns None if history < min_runs.

    NOTE on float arithmetic (STATE.md plan 03-05 lesson): `int(0.7 * value)` truncates
    toward 0 due to IEEE 754; documented behavior. Don't pre-compute test expectations.

    Source: 02-RESEARCH.md §"auto_suggest_threshold refactor" lines 980-998.
    Decision: D-203.
    """
    if len(history_counts) < min_runs:
        return None
    last = history_counts[-min_runs:]
    return int(factor * statistics.median(last))


def final_threshold_gate(count: int, threshold: int) -> bool:
    """Retailer-agnostic. count >= threshold → True (gate PASSES).

    Source: 02-RESEARCH.md §"final_threshold_gate refactor" lines 1004-1014.
    """
    return count >= threshold


# ---- D-218 parse-quality gate (Phase 2 Plan 02-05) ----


def parse_quality_gate(
    null_rate_required_fields: float,
    *,
    threshold: float = 0.05,
) -> bool:
    """D-218: returns True iff null_rate <= threshold (gate PASSES).

    null_rate_required_fields = (rows where name OR current_price OR url is NULL)
                              / total_count

    >5% null rate → run marked failed with reason='parse_quality_below_threshold'.
    Threshold inclusive (≤): exactly 5% passes; 5.01% fails.

    Source: 02-CONTEXT.md D-218; 02-RESEARCH.md §Pattern 1 PARSE-05.
    """
    return null_rate_required_fields <= threshold


# ---- Backward-compat shims (Phase 3 callers + Phase 2 viled-side seeds) ----


def final_m_gate(goldapple_count: int, M: int = 1000) -> bool:
    """D-308/D-309 final sanity gate (Phase 3 shim).

    Forwards to retailer-agnostic `final_threshold_gate(count, M)`.
    Kept so Phase 3 callers (orchestrator + tests) stay green after the
    D-203 refactor.

    Source: 03-RESEARCH.md §"Code Examples" lines 944-946.
    """
    return final_threshold_gate(goldapple_count, M)


def final_n_gate(viled_count: int, N: int = 100) -> bool:
    """Phase 2 viled-side sanity gate. Forwards to final_threshold_gate(count, N).

    Decision: D-201 seed N=100 — sized for the catalog/1310 scope after the
    week-1 enumerator returns ~120 page-1 SKUs from both catalogs combined.
    Operator updates via auto_suggest_threshold (D-203) from week 5.
    """
    return final_threshold_gate(viled_count, N)


def auto_suggest_m(history_counts: list[int]) -> Optional[int]:
    """D-310: returns suggested M after 4+ runs of history (Phase 3 shim).

    Forwards to `auto_suggest_threshold(history, factor=0.7, min_runs=4)`.
    Operator decides whether to update sanity_gate_m in pyproject.toml.
    NEVER auto-tunes (Pitfall: silent drift downward at gradual anti-bot regression).

    Source: 03-RESEARCH.md §"Code Examples" lines 948-954.
    """
    return auto_suggest_threshold(history_counts, factor=0.7, min_runs=4)


__all__ = [
    "SMOKE_URLS",
    "load_smoke_urls_from_config",
    "smoke_probe",
    "auto_suggest_threshold",
    "final_threshold_gate",
    "parse_quality_gate",
    "final_m_gate",
    "final_n_gate",
    "auto_suggest_m",
]
