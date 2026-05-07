"""NORM-02 brand normalizer.

NFKD + accent strip + lowercase + non-alphanum→hyphen (delegated to
`enumeration.slug._normalize_punct`) + alias_lookup reverse-resolve to
canonical brand_norm.

Source: 02-RESEARCH.md §Pattern 7.

Cascading constraints from STATE.md plan 03-02:
  - Apostrophe-strip MUST happen BEFORE non-alphanum→hyphen
    (`L'Oréal Paris → loreal-paris`, NOT `l-oreal-paris`).
    `_normalize_punct` already does this; do NOT re-implement.
  - Cyrillic-presence regex must use explicit-list `[а-яёәғқңөұүһі]`
    (handled in slug.py).
"""

from __future__ import annotations

from typing import Protocol

from ga_crawler.enumeration.slug import _normalize_punct  # REUSE — do not duplicate


class _AliasReverseLookup(Protocol):
    """Structural type for the reverse-lookup helper exposed by YamlBrandAlias."""

    def canonical_for(self, normalized_alias: str) -> str | None: ...


def normalize_brand(raw: str, alias_lookup: _AliasReverseLookup) -> str:
    """NORM-02. Returns canonical brand_norm.

    Step 1: `_normalize_punct(raw)` → slug-form (NFKD + accent + lower + apostrophe-strip + slug).
    Step 2: `alias_lookup.canonical_for(slug)` → canonical brand_norm if known.
    Step 3: Fall through to slug-form if alias unknown.

    Empty input returns "".
    """
    if not raw:
        return ""
    candidate = _normalize_punct(raw)
    if not candidate:
        return ""
    canonical = alias_lookup.canonical_for(candidate)
    return canonical if canonical is not None else candidate


__all__ = ["normalize_brand"]
