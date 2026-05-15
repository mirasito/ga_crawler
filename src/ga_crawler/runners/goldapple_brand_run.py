"""Goldapple Phase-3 runner — brand-page (cards-list) discovery path.

Alternative to ``runners/goldapple_run.py`` (sitemap-based PDP fetch loop).
This runner uses the ``ga_crawler.enumeration.goldapple_brand`` enumerator,
which captures the SPA's own ``/front/api/catalog/cards-list`` XHR JSON
during a brand-page scroll session — no PDP fetches needed, since each
cards-list response carries everything we'd otherwise scrape from the PDP:
``itemId``, ``brand``, ``productType`` (Russian!), ``name`` (English),
``attributes.units`` (volume + unit), ``price.actual`` (current),
``price.old`` (was), ``inStock`` (availability), and PDP URL.

Why a separate module instead of refactoring ``run_goldapple_phase``:
  * Keeps existing sitemap-based unit/integration tests untouched.
  * Smaller surface area: skip smoke probe, PDP fetch loop, parser, and the
    NORM-06 sitemap-slug diff (the latter is replaced by per-brand counts).
  * Cleaner failure mode: a single bad brand-slug doesn't poison the whole
    run; ``unmatched_viled_brands`` collects them.

Stats compatibility (Pitfall 6):
  We populate the same ``goldapple.*`` keys the legacy path uses, setting
  the PDP-loop-specific counters (gate_shell_count, stale_count,
  parse_failures) to 0 so the runs.stats schema is consistent across both
  discovery modes. Stats schema is owned by ``runner.stats.GOLDAPPLE_STATS_KEYS``.

Source: matcher-review-2026-05-15 brand-page architecture decision
(commits 7f396fd, 4a1e2de, 895c5ef); enumerator probe sequence in
``inbox/ga_brand_xhr/``, ``inbox/ga_cards_api/``.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import structlog
import yaml

from ga_crawler.enumeration.goldapple_brand import (
    BrandEnumerationResult,
    enumerate_brand,
)
from ga_crawler.fetchers.goldapple import GoldappleFetcher
from ga_crawler.interfaces import (
    BrandAliasProtocol,
    NormalizerProtocol,
    RunWriterProtocol,
    SnapshotWriterProtocol,
)
from ga_crawler.normalizers.volume import detect_multipack, serialize_volume_norm
from ga_crawler.runner.gates import final_threshold_gate as _final_n_gate  # noqa: F401
from ga_crawler.runner.gates import auto_suggest_threshold
from ga_crawler.runner.stats import GoldappleStatsBuilder

log = structlog.get_logger(__name__)


# ---- Configuration ----

DEFAULT_SLUG_ALIASES_PATH = Path("data/ga_brand_slugs.yaml")


@dataclass
class PhaseResult:
    """Outcome of run_goldapple_brand_phase. Mirrors the sitemap runner's
    PhaseResult shape so the orchestrator in ``main_run.py`` doesn't care
    which discovery path produced the result."""

    status: str  # "success" | "failed"
    goldapple_count: int = 0
    reason: Optional[str] = None
    stats_delta: dict = field(default_factory=dict)
    unmatched_viled_brands: list[str] = field(default_factory=list)
    new_goldapple_slugs: list[str] = field(default_factory=list)


# ---- Brand-slug resolution ----


def _default_kebab(brand_norm: str) -> str:
    """Default rule when no override is provided: kebab(brand_norm)."""
    return re.sub(r"[_\s]+", "-", (brand_norm or "").lower()).strip("-")


def load_slug_overrides(path: Path | str = DEFAULT_SLUG_ALIASES_PATH) -> dict[str, str]:
    """Read ``data/ga_brand_slugs.yaml`` overrides. Missing file → empty dict."""
    p = Path(path)
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return dict(data.get("overrides") or {})


def resolve_brand_slug(brand_norm: str, overrides: dict[str, str]) -> str:
    """``brand_norm`` → GA URL slug. Overrides win; default = kebab."""
    return overrides.get(brand_norm) or _default_kebab(brand_norm)


# ---- Card → snapshot-record conversion ----


def _record_from_raw(rp: Any, normalizer: NormalizerProtocol) -> dict:
    """Compose a snapshot-writer-ready dict from a GoldappleRawProduct.

    Uses the existing Phase-2 normalizer (brand alias, name normalize,
    volume parse + canonical serialize) so storage layer assumptions
    (volume_norm format, brand_norm case) are identical to the
    sitemap-based path.
    """
    return {
        "sku_id": rp.sku_id,
        "url": rp.url,
        "name": rp.name,
        "brand": rp.brand_raw,
        "brand_norm": normalizer.brand(rp.brand_raw),
        "name_norm": normalizer.name(rp.name),
        "volume_raw": rp.raw_volume_text,
        "volume_norm": serialize_volume_norm(
            normalizer.volume(rp.raw_volume_text or rp.name)
        ),
        "multipack_flag": detect_multipack(rp.name),
        "parse_error_flag": False,
        "current_price": rp.current_price,
        "was_price": rp.was_price,
        "currency": rp.currency,
        "stock_state": "IN_STOCK" if rp.availability == "InStock" else "OUT_OF_STOCK",
    }


# ---- Stats helpers (D-310 auto-suggest mirror) ----


def _gather_prior_counts(run_writer: RunWriterProtocol, current_run_id: int) -> list[int]:
    """Read ``goldapple.fetch_count`` from prior runs for D-310 median.
    Best-effort — any read error is skipped silently."""
    counts: list[int] = []
    for prior in range(max(1, current_run_id - 4), current_run_id):
        try:
            stats = run_writer.get_stats(prior)
        except Exception:  # noqa: BLE001
            continue
        if not stats:
            continue
        c = stats.get("goldapple.fetch_count") or stats.get("fetch_count")
        if isinstance(c, int) and c > 0:
            counts.append(c)
    return counts


# ---- Main entry point ----


async def run_goldapple_brand_phase(
    run_id: int,
    viled_brands: list[str],
    repo_root: Path,
    brand_alias: BrandAliasProtocol,  # accepted for signature parity, unused here
    normalizer: NormalizerProtocol,
    snapshot_writer: SnapshotWriterProtocol,
    run_writer: RunWriterProtocol,
    *,
    headless: bool = True,
    M: int = 1000,
    fetcher_factory: Optional[Callable[..., Any]] = None,
    slug_overrides_path: Path | str = DEFAULT_SLUG_ALIASES_PATH,
    inter_brand_pause_seconds: float = 2.0,
) -> PhaseResult:
    """Run Phase 3 in brand-page discovery mode.

    Steps (mirrors the sitemap runner's stage numbering where it makes
    sense; PDP-fetch steps are replaced with brand enumeration):

      1. Load slug overrides.
      2. Resolve every viled brand_norm → GA slug.
      3. Boot Camoufox via ``GoldappleFetcher`` (one session for all brands).
      4. Per brand: ``enumerate_brand`` (scroll + cards-list capture).
      5. Convert cards → normalized snapshot records.
      6. Snapshot writer batch INSERT.
      7. Compose ``GoldappleStatsBuilder.delta`` (legacy PDP counters set to 0).
      8. Atomic single-call ``run_writer.patch_stats``.
      9. Apply M-gate (D-308); fail run if below threshold.

    Returns a ``PhaseResult`` shaped identically to the sitemap runner.
    """
    started = time.perf_counter()
    builder = GoldappleStatsBuilder()

    # ---- Step 1: slug overrides ----
    overrides = load_slug_overrides(slug_overrides_path)
    log.info(
        "phase3_brand_overrides_loaded",
        run_id=run_id,
        override_count=len(overrides),
    )

    # ---- Step 2: brand_norm → slug map ----
    brand_to_slug: dict[str, str] = {
        b: resolve_brand_slug(b, overrides) for b in viled_brands
    }
    if not brand_to_slug:
        log.warning("phase3_no_viled_brands", run_id=run_id)
        builder.set("fetch_count", 0)
        builder.set("fetch_failures", 0)
        builder.set("gate_shell_count", 0)
        builder.set("stale_count", 0)
        builder.set("parse_failures", 0)
        builder.set("unmatched_viled_brands", 0)
        builder.set("unmatched_goldapple_slugs_new", 0)
        builder.set("smoke_pass", True)
        builder.set("fetch_duration_seconds", 0)
        builder.set("mean_fetch_seconds", 0.0)
        builder.set("camoufox_version", "unknown")
        builder.set("volume_null_rate", 0.0)
        builder.set("brand_null_rate", 0.0)
        builder.set("parser_drift_failure_reason", "")
        run_writer.patch_stats(run_id, builder.delta)
        run_writer.fail(run_id, "no_viled_brands_to_enumerate")
        return PhaseResult(status="failed", reason="no_viled_brands", stats_delta=dict(builder.delta))

    # ---- Step 3-4: Camoufox session + brand enumeration ----
    factory = fetcher_factory if fetcher_factory is not None else GoldappleFetcher
    enum_results: list[BrandEnumerationResult] = []
    fetcher = factory(run_id=run_id, headless=headless)
    async with fetcher:
        # Treat first brand-page render as the implicit smoke probe — if it
        # fails we'll surface goldapple_count=0 and the M-gate trips.
        # Detailed smoke instrumentation can be added later if needed.
        slugs = list(brand_to_slug.items())
        for i, (brand_norm, slug) in enumerate(slugs):
            log.info("phase3_enum_brand_start", run_id=run_id, brand_norm=brand_norm, slug=slug)
            try:
                result = await enumerate_brand(fetcher, slug)
            except Exception as e:  # noqa: BLE001
                log.error("phase3_enum_brand_failed",
                          run_id=run_id, brand_norm=brand_norm, slug=slug, error=str(e))
                result = BrandEnumerationResult(
                    slug=slug, product_count_badge=None, cards_collected=0,
                    raw_products=[], cards_list_calls=0, error=str(e),
                )
            enum_results.append(result)
            if i + 1 < len(slugs):
                await asyncio.sleep(inter_brand_pause_seconds)

    # ---- Step 5: cards → normalized records ----
    final_records: list[dict] = []
    unmatched_brands: list[str] = []
    for (brand_norm, _slug), res in zip(brand_to_slug.items(), enum_results):
        if not res.raw_products:
            unmatched_brands.append(brand_norm)
            continue
        for rp in res.raw_products:
            final_records.append(_record_from_raw(rp, normalizer))

    # ---- Step 6: batch INSERT ----
    if final_records:
        inserted = snapshot_writer.append(run_id, "goldapple", final_records)
        log.info("phase3_brand_snapshots_written", run_id=run_id, inserted=inserted)
    goldapple_count = len(final_records)

    # ---- Step 7: compose stats (legacy schema-locked keys) ----
    # PDP-loop counters set to 0 — there is no PDP fetch in this path.
    duration_seconds = int(time.perf_counter() - started)
    mean_fetch = (
        duration_seconds / max(1, len(enum_results)) if enum_results else 0.0
    )
    builder.set("fetch_count", goldapple_count)
    builder.set("fetch_failures", sum(1 for r in enum_results if r.error))
    builder.set("gate_shell_count", 0)
    builder.set("stale_count", 0)
    builder.set("parse_failures", 0)
    builder.set("unmatched_viled_brands", len(unmatched_brands))
    builder.set("unmatched_goldapple_slugs_new", 0)
    builder.set("smoke_pass", True)
    builder.set("fetch_duration_seconds", duration_seconds)
    builder.set("mean_fetch_seconds", round(mean_fetch, 2))
    builder.set("camoufox_version", "via-fetcher-session")
    # Quality metrics: null-rate for volume / brand among enumerated records.
    if goldapple_count > 0:
        vol_null = sum(1 for r in final_records if r.get("volume_norm") is None)
        brand_null = sum(1 for r in final_records if not r.get("brand_norm"))
        builder.set("volume_null_rate", round(vol_null / goldapple_count, 4))
        builder.set("brand_null_rate", round(brand_null / goldapple_count, 4))
    else:
        builder.set("volume_null_rate", 0.0)
        builder.set("brand_null_rate", 0.0)
    builder.set("parser_drift_failure_reason", "")  # not applicable in brand-mode

    # Auto-suggest M from history (best-effort).
    try:
        prior = _gather_prior_counts(run_writer, current_run_id=run_id)
    except Exception as e:  # noqa: BLE001
        log.warning("phase3_history_read_failed", error=str(e))
        prior = []
    suggested = auto_suggest_threshold([*prior, goldapple_count])
    if suggested is not None:
        builder.set("auto_suggest_m", suggested)
        log.info("phase3_auto_suggest_m", run_id=run_id, suggested=suggested)

    # ---- Step 8: single atomic patch_stats ----
    run_writer.patch_stats(run_id, builder.delta)

    # ---- Step 9: M-gate ----
    if goldapple_count < M:
        reason = f"goldapple_count {goldapple_count} < M={M}"
        log.error("phase3_brand_m_gate_failed", run_id=run_id, reason=reason)
        run_writer.fail(run_id, reason)
        return PhaseResult(
            status="failed",
            goldapple_count=goldapple_count,
            reason=reason,
            stats_delta=dict(builder.delta),
            unmatched_viled_brands=unmatched_brands,
            new_goldapple_slugs=[],
        )

    log.info(
        "phase3_brand_complete",
        run_id=run_id,
        count=goldapple_count,
        unmatched_brands=len(unmatched_brands),
        duration_s=duration_seconds,
    )
    return PhaseResult(
        status="success",
        goldapple_count=goldapple_count,
        stats_delta=dict(builder.delta),
        unmatched_viled_brands=unmatched_brands,
        new_goldapple_slugs=[],
    )


__all__ = [
    "DEFAULT_SLUG_ALIASES_PATH",
    "PhaseResult",
    "load_slug_overrides",
    "resolve_brand_slug",
    "run_goldapple_brand_phase",
]
