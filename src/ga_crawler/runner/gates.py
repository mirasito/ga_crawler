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
SMOKE_URLS: tuple[str, ...] = (
    "https://goldapple.kz/7680100018-very-irresistible-givenchy",
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


def final_m_gate(goldapple_count: int, M: int = 1000) -> bool:
    """D-308/D-309 final sanity gate. Returns True iff goldapple_count >= M.

    Caller (Wave 5 orchestrator):
      if not final_m_gate(stats["goldapple.fetch_count"], M=config["sanity_gate_m"]):
          run_writer.fail(run_id, reason=f"goldapple_count {n} < M={M}")

    Source: 03-RESEARCH.md §"Code Examples" lines 944-946.
    """
    return goldapple_count >= M


def auto_suggest_m(history_counts: list[int]) -> Optional[int]:
    """D-310: returns suggested M after 4+ runs of history.

    Formula: int(0.7 × median(last_4_run_counts))
    Less than 4 runs → returns None (operator gets no suggestion yet).

    Operator decides whether to update sanity_gate_m in pyproject.toml.
    NEVER auto-tunes (Pitfall: silent drift downward at gradual anti-bot regression).

    Source: 03-RESEARCH.md §"Code Examples" lines 948-954.
    """
    if len(history_counts) < 4:
        return None
    last_4 = history_counts[-4:]
    median = statistics.median(last_4)
    return int(0.7 * median)


__all__ = [
    "SMOKE_URLS",
    "load_smoke_urls_from_config",
    "smoke_probe",
    "final_m_gate",
    "auto_suggest_m",
]
