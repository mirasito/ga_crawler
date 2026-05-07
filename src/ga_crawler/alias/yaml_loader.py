"""YAML-backed BrandAlias loader. Reads brand-aliases YAML once at __init__.

Source: 02-RESEARCH.md §Pattern 8.
Decisions: D-204 location config/, D-205 flat-dict schema {brand_norm: [aliases...]},
D-207 read-once at __init__, D-216 single-class implementation.

Concrete-only `canonical_for` (NOT in BrandAliasProtocol) per RESEARCH Open Q1
pattern — it is the reverse-lookup helper used by normalizers/brand.py to map
a raw brand string (after `_normalize_punct`) back to its canonical form.

Pitfall: pure-Latin brands without RU variants seed as one-element list when
present in YAML; absent brands fall back to self-seed [brand_norm] via lookup().
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from ga_crawler.enumeration.slug import _normalize_punct  # REUSE — do not duplicate


class YamlBrandAlias:
    """BrandAliasProtocol implementer.

    `lookup(brand_norm) -> list[str]` returns aliases for a canonical brand_norm
    (or [brand_norm] if unknown — self-seed default).

    `canonical_for(normalized_alias) -> str | None` (CONCRETE-ONLY, NOT in Protocol)
    is the reverse lookup used by `normalizers.brand.normalize_brand` to map a raw
    brand string (post `_normalize_punct`) back to its canonical form.

    D-207 read-once: YAML is loaded once in __init__ and cached as in-memory dicts.
    Subsequent file mutations on disk do NOT affect already-loaded lookups.
    """

    def __init__(self, yaml_path: Path | str):
        self._raw: dict[str, list[str]] = {}
        self._reverse: dict[str, str] = {}
        path = Path(yaml_path)
        if path.exists():
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content) or {}
            if isinstance(data, dict):
                self._raw = {
                    k: list(v) if v else []
                    for k, v in data.items()
                    if isinstance(k, str)
                }
                self._build_reverse()

    def _build_reverse(self) -> None:
        """Build `normalized_alias → canonical_key` map.

        Each alias is normalized via `_normalize_punct` so the lookup key is
        slug-form. The canonical key (top-level YAML key) is preserved
        verbatim so callers see the underscore-snake-case form (D-205).
        Canonical key itself maps to itself (after normalization) to handle
        the case where the canonical key matches the slugified raw input.
        """
        for canonical, aliases in self._raw.items():
            for a in aliases:
                self._reverse[_normalize_punct(a)] = canonical
            # canonical maps to itself (after normalization)
            self._reverse[_normalize_punct(canonical)] = canonical

    def lookup(self, brand_norm: str) -> list[str]:
        """Per BrandAliasProtocol. Returns aliases or [brand_norm] (self-seed)."""
        return list(self._raw.get(brand_norm, [brand_norm]))

    def canonical_for(self, normalized_alias: str) -> Optional[str]:
        """Concrete-only. Returns canonical brand_norm or None if unknown.

        Input is expected to already be slug-form (output of `_normalize_punct`).
        """
        return self._reverse.get(normalized_alias)


__all__ = ["YamlBrandAlias"]
