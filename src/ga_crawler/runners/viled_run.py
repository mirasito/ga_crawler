"""Phase 2 viled orchestrator — `run_viled_phase()`.

Mirror of `runners/goldapple_run.py` with the Camoufox/anti-bot stack
stripped (viled is Tier 0 — plain curl_cffi). Sync-inside (D-225). Composes
Plan 02-02 storage, Plan 02-03 normalizers, Plan 02-04 fetcher / parser /
catalog enumerator into the 8-step viled pipeline:

  1. Catalog enumeration   — fetch_catalog_urls(both endpoints)
  2. Run loop              — ViledFetcher.run_loop with 2 s pacing + per-SKU isolation
  3. Parse                 — ParseDispatcher.dispatch("viled", html, url)
  4. Normalize             — Normalizer.brand / .name / .volume + detect_multipack
  5. Persist               — SnapshotWriter.append(retailer="viled", ...)
  6. Parse-quality gate    — D-218 (run FIRST) — null_rate <= 5%
  7. Sanity-N gate         — D-201 / CRAWL-05 (run SECOND) — count >= N
  8. Atomic stats merge    — single run_writer.patch_stats call (Pitfall 6)

The single `runs` row is shared with Phase 3 goldapple. Phase 2 viled writes
ONLY viled.* keys (Pitfall 6); the orchestrator (`runners/main_run.py`)
owns row creation + finalize.

Source: 02-RESEARCH.md §System Architecture Diagram lines 186-242;
        02-PATTERNS.md §"viled_run analog" lines 275-348;
        02-CONTEXT.md D-218 sequential gates, D-225 sync-inside.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import structlog

from ga_crawler.config import ViledConfig
from ga_crawler.enumeration.viled_catalog import fetch_catalog_urls as _default_fetch_catalog
from ga_crawler.fetchers.viled import ViledFetcher
from ga_crawler.interfaces import (
    BrandAliasProtocol,
    NormalizerProtocol,
    RunWriterProtocol,
    SnapshotWriterProtocol,
)
from ga_crawler.normalizers.volume import detect_multipack
from ga_crawler.parsers.dispatcher import ParseDispatcher
from ga_crawler.runner.gates import (
    auto_suggest_threshold,
    final_threshold_gate,
    parse_quality_gate,
)
from ga_crawler.runner.stats import ViledStatsBuilder

log = structlog.get_logger(__name__)


@dataclass
class ViledPhaseResult:
    """Outcome of run_viled_phase."""

    status: str  # "success" | "failed"
    viled_count: int = 0
    reason: Optional[str] = None
    stats_delta: dict = field(default_factory=dict)


# ---- Helpers ----


def _compute_null_rate(records: list[dict]) -> float:
    """D-218 null-rate calculation.

    Counts rows where `name`, `current_price`, OR `url` is None / falsy.
    Returns 0.0 when records is empty (no data → no quality assertion;
    sanity-N gate downstream catches "no data").
    """
    if not records:
        return 0.0
    null_count = 0
    for r in records:
        if not r.get("name") or r.get("current_price") is None or not r.get("url"):
            null_count += 1
    return null_count / len(records)


def _normalize_record(parsed: dict, normalizer: NormalizerProtocol) -> dict:
    """Build the SnapshotWriter dict shape (extends Phase 3 shape with v_curr fields).

    Mirrors `runners/goldapple_run.py:237-250` but adds:
      - `multipack_flag` via `detect_multipack(name)` (NORM-04, D-215)
      - `volume_raw` passthrough (raw text the regex was applied to)
      - `parse_error_flag=False` (parse already succeeded by definition)

    The volume serializer matches NormalizerProtocol's
    `Optional[tuple[Decimal, str, int]]` return shape — stringify to a
    canonical `"(amount, unit, count)"` form for the snapshot column
    (the SQLModel `volume_norm` field is `Optional[str]`).
    """
    raw_volume_text = parsed.get("raw_volume_text") or parsed.get("name") or ""
    name_raw = parsed.get("name", "")
    brand_raw = parsed.get("brand_raw", "")

    volume_norm_tuple = normalizer.volume(raw_volume_text)
    volume_norm: Optional[str] = (
        str(volume_norm_tuple) if volume_norm_tuple is not None else None
    )

    multipack_flag = detect_multipack(raw_volume_text)

    return {
        "sku_id": str(parsed.get("sku_id", "")),
        "url": parsed.get("url", ""),
        "name": name_raw,
        "brand": brand_raw,
        "brand_norm": normalizer.brand(brand_raw),
        "name_norm": normalizer.name(name_raw),
        "current_price": parsed.get("current_price"),
        "was_price": parsed.get("was_price"),
        "currency": parsed.get("currency", "KZT"),
        "stock_state": parsed.get("availability", "UNKNOWN"),
        "volume_raw": raw_volume_text,
        "volume_norm": volume_norm,
        "multipack_flag": multipack_flag,
        "parse_error_flag": False,
    }


def _gather_prior_counts(
    run_writer: RunWriterProtocol, current_run_id: int, *, lookback: int = 4
) -> list[int]:
    """Read viled.fetch_count from prior runs for D-203 auto-suggest median.

    Mirrors goldapple_run._gather_prior_counts but reads viled.* keys.
    Best-effort — any error returns [].
    """
    counts: list[int] = []
    for prior in range(max(1, current_run_id - lookback), current_run_id):
        try:
            stats = run_writer.get_stats(prior)
        except Exception:  # noqa: BLE001
            continue
        if not stats:
            continue
        c = stats.get("viled.fetch_count") or stats.get("fetch_count")
        if isinstance(c, int) and c > 0:
            counts.append(c)
    return counts


# ---- Main entry point ----


def run_viled_phase(
    *,
    run_id: int,
    config: ViledConfig,
    brand_alias: BrandAliasProtocol,
    normalizer: NormalizerProtocol,
    snapshot_writer: SnapshotWriterProtocol,
    run_writer: RunWriterProtocol,
    dispatcher: Optional[ParseDispatcher] = None,
    fetcher: Optional[Any] = None,
    fetch_catalog: Optional[Callable[..., list[str]]] = None,
) -> ViledPhaseResult:
    """Execute the full Phase 2 viled pipeline.

    Args:
        run_id:           runs row id (already created by main_run.py)
        config:           ViledConfig (from pyproject.toml or override)
        brand_alias:      Plan 02-03 YamlBrandAlias instance
        normalizer:       Plan 02-03 Normalizer instance
        snapshot_writer:  Plan 02-02 SqliteSnapshotWriter instance
        run_writer:       Plan 02-02 SqliteRunWriter instance
        dispatcher:       optional ParseDispatcher (test injection)
        fetcher:          optional ViledFetcher-compatible (test injection)
        fetch_catalog:    optional fetch_catalog_urls (test injection)

    Returns:
        ViledPhaseResult with status / viled_count / reason / stats_delta.
    """
    started = time.perf_counter()
    builder = ViledStatsBuilder()

    # Default-construct the injectable dependencies so the orchestrator works
    # without explicit wiring.
    if dispatcher is None:
        dispatcher = ParseDispatcher()
    if fetcher is None:
        fetcher = ViledFetcher(run_id=run_id, pause_seconds=config.pause_seconds)
    if fetch_catalog is None:
        fetch_catalog = _default_fetch_catalog

    # Step 1: Catalog enumeration over both endpoints (men/women).
    all_urls: list[str] = []
    for catalog_base in config.catalog_urls:
        try:
            urls = fetch_catalog(catalog_base, pause_seconds=config.pause_seconds)
        except Exception as e:  # noqa: BLE001
            log.error(
                "viled_catalog_enum_failed",
                catalog_base=catalog_base,
                error=str(e),
            )
            continue
        log.info(
            "viled_catalog_enumerated",
            catalog_base=catalog_base,
            url_count=len(urls),
        )
        all_urls.extend(urls)

    # Dedup while preserving order (men + women catalogs may overlap).
    seen: set[str] = set()
    deduped_urls: list[str] = []
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            deduped_urls.append(u)

    log.info("viled_total_urls", run_id=run_id, count=len(deduped_urls))

    # Step 2: Run loop (2 s pacing + per-SKU isolation).
    run_loop_stats: dict[str, Any] = {}
    fetched_records = fetcher.run_loop(deduped_urls, run_loop_stats, sleep_fn=time.sleep)
    builder.set("fetch_count", run_loop_stats.get("fetch_count", 0))
    builder.set("fetch_failures", run_loop_stats.get("fetch_failures", 0))

    # Steps 3+4: Parse + normalize.
    snapshot_rows: list[dict] = []
    parse_failures = 0
    for rec in fetched_records:
        html = rec.get("html") or ""
        url = rec.get("url", "")
        if not html:
            parse_failures += 1
            continue
        parsed = dispatcher.dispatch("viled", html, url)
        if parsed is None:
            parse_failures += 1
            continue
        try:
            row = _normalize_record(parsed, normalizer)
        except Exception as e:  # noqa: BLE001
            log.error("viled_normalize_failed", url=url, error=str(e))
            parse_failures += 1
            continue
        snapshot_rows.append(row)
    builder.set("parse_failures", parse_failures)

    # Step 5: Persist (per-batch commit semantics owned by SqliteSnapshotWriter).
    inserted = 0
    if snapshot_rows:
        inserted = snapshot_writer.append(run_id, "viled", snapshot_rows)
        log.info("viled_snapshots_persisted", run_id=run_id, inserted=inserted)

    # Stats decoration (duration / mean fetch).
    elapsed = time.perf_counter() - started
    fetch_count = run_loop_stats.get("fetch_count", 0)
    builder.set("fetch_duration_seconds", round(elapsed, 2))
    if fetch_count > 0:
        builder.set("mean_fetch_seconds", round(elapsed / fetch_count, 3))
    else:
        builder.set("mean_fetch_seconds", 0.0)

    # Step 6: Parse-quality gate (D-218 — runs FIRST).
    null_rate = _compute_null_rate(snapshot_rows)
    builder.set("null_rate_required_fields", round(null_rate, 4))
    parse_quality_pass = parse_quality_gate(null_rate)
    builder.set("parse_quality_pass", 1 if parse_quality_pass else 0)
    if not parse_quality_pass:
        reason = (
            f"parse_quality_below_threshold (null_rate={null_rate:.4f} > 0.05)"
        )
        log.error("viled_parse_quality_failed", run_id=run_id, reason=reason)
        run_writer.fail(run_id, reason)
        run_writer.patch_stats(run_id, dict(builder.delta))
        return ViledPhaseResult(
            status="failed",
            viled_count=inserted,
            reason=reason,
            stats_delta=dict(builder.delta),
        )

    # Step 7: Sanity-N gate (D-201 / CRAWL-05 — runs SECOND).
    sanity_pass = final_threshold_gate(inserted, config.sanity_gate_n)
    builder.set("sanity_gate_n_pass", 1 if sanity_pass else 0)

    # Step 7c: Auto-suggest N (informational; D-203 — must run BEFORE single
    # patch_stats so the value is part of the atomic merge).
    history = _gather_prior_counts(run_writer, run_id)
    suggested = auto_suggest_threshold(
        history,
        factor=config.n_auto_suggest_factor,
        min_runs=config.n_auto_suggest_after_runs,
    )
    if suggested is not None:
        builder.set("auto_suggest_n", suggested)
        log.info("viled_auto_suggest_n", run_id=run_id, suggested=suggested)

    if not sanity_pass:
        reason = (
            f"sanity_gate_n_failed: viled_count {inserted} < N={config.sanity_gate_n}"
        )
        log.error("viled_sanity_gate_failed", run_id=run_id, reason=reason)
        run_writer.fail(run_id, reason)
        run_writer.patch_stats(run_id, dict(builder.delta))
        return ViledPhaseResult(
            status="failed",
            viled_count=inserted,
            reason=reason,
            stats_delta=dict(builder.delta),
        )

    # Step 8: Atomic stats merge (Pitfall 6) — SINGLE patch_stats on success path.
    run_writer.patch_stats(run_id, dict(builder.delta))

    log.info(
        "viled_phase_complete",
        run_id=run_id,
        viled_count=inserted,
        duration_s=round(elapsed, 2),
    )
    return ViledPhaseResult(
        status="success",
        viled_count=inserted,
        stats_delta=dict(builder.delta),
    )


__all__ = ["ViledPhaseResult", "run_viled_phase"]
