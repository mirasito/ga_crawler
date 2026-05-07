"""Normalizer facade — composes brand/name/volume + holds YamlBrandAlias ref.

Implements NormalizerProtocol exactly (interfaces.py FROZEN).

Source: 02-CONTEXT.md D-215 facade; 02-PATTERNS.md "facade composes".
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from ga_crawler.alias.yaml_loader import YamlBrandAlias
from ga_crawler.normalizers.brand import normalize_brand
from ga_crawler.normalizers.name import normalize_name
from ga_crawler.normalizers.volume import parse_volume


class Normalizer:
    """Concrete NormalizerProtocol implementer.

    Composes the three single-NORM functions. `volume` returns the protocol's
    `Optional[tuple[Decimal, str, int]]` shape; `Volume.amount/unit/count`
    fields map to tuple positions 0/1/2.
    """

    def __init__(self, alias: YamlBrandAlias):
        self._alias = alias

    def brand(self, raw: str) -> str:
        return normalize_brand(raw, self._alias)

    def name(self, raw: str) -> str:
        return normalize_name(raw)

    def volume(self, raw: str) -> Optional[tuple[Decimal, str, int]]:
        v = parse_volume(raw)
        if v is None:
            return None
        return (v.amount, v.unit, v.count)


__all__ = ["Normalizer"]
