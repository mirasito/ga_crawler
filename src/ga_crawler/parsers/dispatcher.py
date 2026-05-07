"""Per-retailer parser dispatcher — concrete ParseDispatcherProtocol impl.

Phase 3 registers `goldapple_microdata.parse_pdp` (FROZEN);
Phase 2 registers `viled_nextdata.parse_pdp` (NEW).

The Protocol-declared signature is `dispatch(retailer, html_or_data) ->
Optional[dict]`. Concrete impl additionally accepts `url` (kw-default "") so
the underlying parsers can recover sku_id from the URL when the inline payload
lacks it; the extra arg is ABI-compatible with the Protocol because
`runtime_checkable` Protocol checks only that the named methods exist.

Source: 02-PATTERNS.md lines 631-666; 02-CONTEXT.md D-213 per-retailer split.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Callable, Optional

from ga_crawler.parsers.goldapple_microdata import parse_pdp as parse_goldapple
from ga_crawler.parsers.viled_nextdata import parse_pdp as parse_viled


class ParseDispatcher:
    """Routes raw HTML / data to the right per-retailer parser.

    Returns the parsed product as a dict (so the orchestrator can pass it
    through NormalizerProtocol + SnapshotWriter without retailer-aware
    unwrapping). Conforms to interfaces.py ParseDispatcherProtocol.
    """

    # Class-level registry. Mutating via monkeypatch.setitem in tests is supported.
    _registry: dict[str, Callable[..., object]] = {
        "viled": parse_viled,
        "goldapple": parse_goldapple,
    }

    def dispatch(
        self,
        retailer: str,
        html_or_data: str,
        url: str = "",
    ) -> Optional[dict]:
        parser = self._registry.get(retailer)
        if parser is None:
            return None
        result = parser(html_or_data, url)
        if result is None:
            return None
        if is_dataclass(result):
            return asdict(result)
        if isinstance(result, dict):
            return result
        return None


__all__ = ["ParseDispatcher"]
