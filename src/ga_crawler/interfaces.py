"""Phase 2 contract Protocols.

Phase 3 (Goldapple Crawl) is built against these interface contracts so it can
develop in parallel with Phase 2 (viled crawl + storage). Phase 2 modules MUST
conform to these signatures; if drift occurs at integration time (Wave 5), this
file is the single source of truth.

Source: 03-RESEARCH.md §Open Questions Q6 lines 1077-1094.
Origin: 03-CONTEXT.md "Open dependency on Phase 2" — parallel-plan-with-stubs.
Pitfall reference: 03-RESEARCH.md Pitfall 9 (contract drift) — mitigated by
freezing Protocols here at Wave 0 and asking Phase 2 plan reviewer to cross-check.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class BrandAliasProtocol(Protocol):
    """Phase 2 alias resolver. Maps a normalized brand to its alias strings.

    Example:
        lookup("estee_lauder") -> ["Estée Lauder", "Эсте Лаудер", "Estee Lauder"]
    """

    def lookup(self, brand_norm: str) -> list[str]: ...


@runtime_checkable
class NormalizerProtocol(Protocol):
    """Phase 2 normalizer. Per NORM-02/NORM-03/NORM-05.

    - brand: NFKD + accent strip + lowercase + alias lookup -> brand_norm
    - name: lowercase + punctuation strip + collapse whitespace -> name_norm
    - volume: Volume value-object (amount, unit, multipack); None if unparseable
    """

    def brand(self, raw: str) -> str: ...
    def name(self, raw: str) -> str: ...
    def volume(self, raw: str) -> Optional[tuple[Decimal, str, int]]: ...


@runtime_checkable
class SnapshotWriterProtocol(Protocol):
    """Phase 2 storage writer. Append-only per DATA-03.

    Returns the number of rows successfully inserted.
    Phase 3 calls with retailer='goldapple' on every successful parse.
    """

    def append(self, run_id: int, retailer: str, products: list) -> int: ...


@runtime_checkable
class RunWriterProtocol(Protocol):
    """Phase 2 runs row mutator. Per DATA-05 single-row-per-run + Pitfall 6 atomic merge.

    - patch_stats: atomic JSON-merge into runs.stats (uses SQLite json_patch).
      Phase 3 writes only goldapple.* keys; Phase 2 only viled.* keys.
    - get_stats: read current stats (used for D-310 4-week median fetch).
    - fail: marks runs.status='failed' with reason; idempotent.
    """

    def patch_stats(self, run_id: int, delta: dict) -> None: ...
    def get_stats(self, run_id: int) -> dict: ...
    def fail(self, run_id: int, reason: str) -> None: ...


@runtime_checkable
class ParseDispatcherProtocol(Protocol):
    """Phase 2 parser dispatcher. Per-retailer dispatch (microdata for goldapple,
    __NEXT_DATA__ for viled). Phase 3 registers goldapple_microdata.parse_pdp.

    Returns the parsed product dict, or None on parse failure / gate-shell / stale.
    """

    def dispatch(self, retailer: str, html_or_data: str) -> Optional[dict]: ...


class CrawlerProtocol(Protocol):
    """Phase 2 base.Crawler interface. Phase 3 GoldappleFetcher conforms.

    Sequential async context manager: __aenter__ boots browser, __aexit__ tears
    down + cleans up tmp profile. fetch_one(url) returns the spike-style dict
    with status, html_size, title, gate_cleared, html (if real-pdp), block,
    block_reason, error fields.
    """

    site: str

    async def __aenter__(self) -> "CrawlerProtocol": ...
    async def __aexit__(self, *exc) -> None: ...
    async def fetch_one(self, url: str) -> dict: ...


__all__ = [
    "BrandAliasProtocol",
    "NormalizerProtocol",
    "SnapshotWriterProtocol",
    "RunWriterProtocol",
    "ParseDispatcherProtocol",
    "CrawlerProtocol",
]
