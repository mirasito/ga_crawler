"""Phase 3 orchestrator — run_goldapple_phase().

Composes:
  1. Sitemap enumeration (Wave 1) — curl_cffi -> slug->URLs map
  2. Brand intersection (Wave 1) — viled brands x aliases x sitemap -> matched_urls
  3. NORM-06 forward (Wave 4) — count of viled brands with zero matches -> stats
  4. Camoufox bootstrap (Wave 3) — fresh tmp profile per run (D-311)
  5. Smoke probe (Wave 4) — D-312 pre-crawl gate; abort on fail
  6. Run loop (Wave 3) — sequential fetch with rate-limit + per-SKU isolation
  7. Microdata parse (Wave 2) — priceType-aware extraction per record
  8. Phase 2 normalizer (Protocol) — brand/name/volume normalize
  9. Phase 2 SnapshotWriter (Protocol) — append-only INSERT to snapshots
  10. NORM-06 reverse (Wave 1) — week-over-week NEW slug diff
  11. Camoufox teardown (Wave 3) — always-cleanup in __aexit__
  12. Final M-gate (Wave 4) — D-308/D-309 catastrophic-failure detector
  13. Auto-suggest M (Wave 4) — D-310 4-week median x 0.7
  14. Atomic stats merge (Pitfall 6) — single patch_stats call at end

The single `runs` row is shared with Phase 2 viled. Phase 3 NEVER creates a
runs row — Phase 2 created it; Phase 3 only patches stats and (on failure)
calls run_writer.fail with reason. Status finalization (success/partial)
is owned by the higher-level orchestrator (Phase 2 + Phase 3 wrapper, future
Phase 7 work).

Source: 03-RESEARCH.md §"System Architecture Diagram" lines 145-241 (12-step flow).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import structlog

from ga_crawler.enumeration.goldapple_sitemap import (
    diff_new_slugs,
    fetch_sitemap_slugs,
    find_previous_slug_file,
    persist_sitemap_slugs,
)
from ga_crawler.fetchers.goldapple import GoldappleFetcher
from ga_crawler.interfaces import (
    BrandAliasProtocol,
    NormalizerProtocol,
    RunWriterProtocol,
    SnapshotWriterProtocol,
)
from ga_crawler.parsers.goldapple_microdata import detect_state, parse_pdp
from ga_crawler.runner.gates import (
    SMOKE_URLS,
    auto_suggest_m,
    final_m_gate,
    smoke_probe,
)
from ga_crawler.runner.stats import GoldappleStatsBuilder, compute_norm06_forward

log = structlog.get_logger(__name__)


@dataclass
class PhaseResult:
    """Outcome of run_goldapple_phase."""

    status: str  # "success" | "failed"
    goldapple_count: int = 0
    reason: Optional[str] = None
    stats_delta: dict = field(default_factory=dict)
    unmatched_viled_brands: list[str] = field(default_factory=list)
    new_goldapple_slugs: list[str] = field(default_factory=list)


async def run_goldapple_phase(
    run_id: int,
    viled_brands: list[str],
    repo_root: Path,
    brand_alias: BrandAliasProtocol,
    normalizer: NormalizerProtocol,
    snapshot_writer: SnapshotWriterProtocol,
    run_writer: RunWriterProtocol,
    *,
    headless: bool = True,
    M: int = 1000,
    smoke_urls: Optional[tuple[str, ...]] = None,
    fetcher_factory: Optional[Callable[..., Any]] = None,  # injection point for tests
    sitemap_fetcher: Optional[Callable[[], dict[str, list[str]]]] = None,  # injection for tests
) -> PhaseResult:
    """Run Phase 3 (Goldapple Crawl) end-to-end.

    Args:
        run_id: ROW id of the runs table (created by Phase 2 — Phase 3 only patches it)
        viled_brands: list of brand_norm strings from current run's viled snapshot
        repo_root: project root for week-over-week persistence ({root}/runs/{run_id}/...)
        brand_alias: Phase 2 BrandAliasProtocol instance
        normalizer: Phase 2 NormalizerProtocol instance
        snapshot_writer: Phase 2 SnapshotWriterProtocol instance
        run_writer: Phase 2 RunWriterProtocol instance
        headless: Camoufox headless flag (False for dev observation)
        M: sanity_gate_m threshold (D-308; default 1000)
        smoke_urls: override SMOKE_URLS (test injection)
        fetcher_factory: optional callable returning GoldappleFetcher-compat (test injection)
        sitemap_fetcher: optional callable returning slug-map (test injection)

    Returns:
        PhaseResult with status / count / reason / stats_delta / NORM-06 lists
    """
    started = time.perf_counter()
    builder = GoldappleStatsBuilder()
    smoke_urls_actual = smoke_urls or SMOKE_URLS

    # Step 1: Sitemap enumeration
    log.info("phase3_sitemap_fetch_start", run_id=run_id)
    if sitemap_fetcher is not None:
        slug_map = sitemap_fetcher()
    else:
        slug_map = fetch_sitemap_slugs()
    log.info("phase3_sitemap_fetched", run_id=run_id, slug_count=len(slug_map))

    # Step 2: Persist current week's slugs (D-307 reverse NORM-06 setup)
    persist_sitemap_slugs(set(slug_map.keys()), run_id=run_id, root=repo_root)

    # Step 3: Week-over-week NEW slug diff (D-307)
    prev_slug_file = find_previous_slug_file(repo_root, current_run_id=run_id)
    new_slugs = diff_new_slugs(set(slug_map.keys()), prev_slug_file)
    builder.set("unmatched_goldapple_slugs_new", len(new_slugs))

    # Step 4: Resolve aliases for each viled brand + intersect with sitemap
    aliases: dict[str, list[str]] = {b: brand_alias.lookup(b) for b in viled_brands}
    matched_urls, unmatched_count, unmatched_brands = compute_norm06_forward(
        viled_brands, aliases, slug_map
    )
    builder.set("unmatched_viled_brands", unmatched_count)
    log.info(
        "phase3_brand_intersect",
        run_id=run_id,
        viled_brand_count=len(viled_brands),
        matched_url_count=len(matched_urls),
        unmatched_brand_count=unmatched_count,
    )

    # Step 5-11: Camoufox boot -> smoke -> run_loop -> parse -> store -> teardown
    # Camoufox lifecycle is wrapped via async with; cleanup always runs (Pitfall 7).
    final_records: list = []
    smoke_passed = False
    smoke_diagnostics: dict = {}

    # fetcher_factory: callable(run_id, headless) -> async-context-manager fetcher.
    # Default = GoldappleFetcher class (its __init__ matches signature).
    factory = fetcher_factory if fetcher_factory is not None else GoldappleFetcher
    fetcher = factory(run_id=run_id, headless=headless)

    async with fetcher:
        # Step 6: Smoke probe (D-312)
        smoke_result = await smoke_probe(fetcher, smoke_urls=smoke_urls_actual)
        smoke_passed = smoke_result["pass"]
        smoke_diagnostics = smoke_result["diagnostics"]
        builder.set("smoke_pass", smoke_passed)
        if not smoke_passed:
            builder.set("smoke_diagnostics", smoke_diagnostics)
        builder.set(
            "camoufox_version",
            smoke_diagnostics.get("camoufox_version", "unknown"),
        )

        if not smoke_passed:
            log.error(
                "phase3_smoke_failed",
                run_id=run_id,
                diagnostics=smoke_diagnostics,
            )
            run_writer.fail(
                run_id, f"smoke_probe_failed: {smoke_diagnostics}"
            )
            run_writer.patch_stats(run_id, builder.delta)
            return PhaseResult(
                status="failed",
                reason="smoke_probe_failed",
                stats_delta=dict(builder.delta),
                unmatched_viled_brands=unmatched_brands,
                new_goldapple_slugs=new_slugs,
            )

        # Step 7: Run loop (sequential, rate-limited, per-SKU isolated)
        run_loop_stats: dict = {}
        records = await fetcher.run_loop(matched_urls, run_loop_stats)

        # Steps 8-9: Parse + normalize + collect for batched insert
        parse_failures = 0
        stale_count = 0
        gate_shell_count = run_loop_stats.get("gate_shell_count", 0)
        for rec in records:
            if rec.get("block"):
                # gate-shell already counted in run_loop_stats.gate_shell_count
                continue
            html = rec.get("html")
            url = rec.get("url", "")
            if not html:
                continue
            product = parse_pdp(html, url)
            if product is None:
                # parse_pdp returns None on stale-sku, gate-shell, missing required
                # fields, or PARSE-04 sanity-range violation. Use detect_state to
                # disambiguate stale vs parse-fail.
                title = rec.get("title", "") or ""
                state = detect_state(html, title)
                if state == "stale-sku":
                    stale_count += 1
                else:
                    parse_failures += 1
                continue
            # Normalize via Phase 2 protocols
            normalized = {
                "sku_id": product.sku_id,
                "url": product.url,
                "name": product.name,
                "brand": product.brand_raw,
                "brand_norm": normalizer.brand(product.brand_raw),
                "name_norm": normalizer.name(product.name),
                "current_price": product.current_price,
                "was_price": product.was_price,
                "currency": product.currency,
                "stock_state": product.availability,
                "volume_norm": normalizer.volume(product.raw_volume_text or ""),
                "raw_volume_text": product.raw_volume_text,
            }
            final_records.append(normalized)

        # Step 10: SnapshotWriter append (Phase 2 contract; append-only per DATA-03;
        # WAL per-run TX per DATA-04 owned by Phase 2 SnapshotWriter — Phase 3 inherits)
        if final_records:
            inserted = snapshot_writer.append(run_id, "goldapple", final_records)
            log.info("phase3_snapshots_written", run_id=run_id, inserted=inserted)

        # Bulk-import run_loop stats into namespaced builder
        builder.from_run_loop_stats(run_loop_stats)
        builder.set("stale_count", stale_count)
        builder.set("parse_failures", parse_failures)
        builder.set("gate_shell_count", gate_shell_count)

    # Step 11: Camoufox teardown happened on async with exit (profile dir cleaned)

    # Step 12: Final M-gate (D-308/D-309)
    goldapple_count = len(final_records)
    duration_seconds = int(time.perf_counter() - started)
    mean_fetch = (
        duration_seconds / max(1, goldapple_count) if goldapple_count > 0 else 0.0
    )
    builder.set("fetch_duration_seconds", duration_seconds)
    builder.set("mean_fetch_seconds", round(mean_fetch, 2))

    # Step 13: Auto-suggest M (D-310) — read prior history from run_writer
    try:
        prior_stats_history = _gather_prior_counts(run_writer, current_run_id=run_id)
    except Exception as e:  # noqa: BLE001
        log.warning("phase3_history_read_failed", error=str(e))
        prior_stats_history = []
    suggested = auto_suggest_m([*prior_stats_history, goldapple_count])
    if suggested is not None:
        builder.set("auto_suggest_m", suggested)
        log.info("phase3_auto_suggest_m", run_id=run_id, suggested=suggested)

    # Step 14: Atomic stats merge (Pitfall 6) — ONE patch_stats call
    run_writer.patch_stats(run_id, builder.delta)

    if not final_m_gate(goldapple_count, M=M):
        reason = f"goldapple_count {goldapple_count} < M={M}"
        log.error("phase3_final_gate_failed", run_id=run_id, reason=reason)
        run_writer.fail(run_id, reason)
        return PhaseResult(
            status="failed",
            goldapple_count=goldapple_count,
            reason=reason,
            stats_delta=dict(builder.delta),
            unmatched_viled_brands=unmatched_brands,
            new_goldapple_slugs=new_slugs,
        )

    log.info(
        "phase3_complete",
        run_id=run_id,
        count=goldapple_count,
        duration_s=duration_seconds,
    )
    return PhaseResult(
        status="success",
        goldapple_count=goldapple_count,
        stats_delta=dict(builder.delta),
        unmatched_viled_brands=unmatched_brands,
        new_goldapple_slugs=new_slugs,
    )


def _gather_prior_counts(run_writer: RunWriterProtocol, current_run_id: int) -> list[int]:
    """Read goldapple.fetch_count from prior runs for D-310 auto-suggest median.

    This is a thin wrapper. Phase 2's RunWriter implementation may expose a
    history-query method; for now we attempt run_writer.get_stats(prior_id)
    for the most recent IDs. If RunWriter doesn't yet support history reads,
    the result is an empty list and auto-suggest stays disabled.
    """
    counts: list[int] = []
    # Naive last-4 runs: try IDs current_run_id-1..current_run_id-4
    for prior in range(max(1, current_run_id - 4), current_run_id):
        try:
            stats = run_writer.get_stats(prior)
        except Exception:  # noqa: BLE001
            continue
        if not stats:
            continue
        # Look for goldapple.fetch_count first; fall back to "fetch_count" bare key
        c = stats.get("goldapple.fetch_count") or stats.get("fetch_count")
        if isinstance(c, int) and c > 0:
            counts.append(c)
    return counts


__all__ = ["PhaseResult", "run_goldapple_phase"]
