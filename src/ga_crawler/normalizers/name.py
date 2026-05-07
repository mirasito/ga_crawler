"""NORM-05 name normalizer.

Lower + NFKD + strip combining marks + strip non-word/non-space + collapse-whitespace.
Distinct from `_normalize_punct` (slug.py) which produces hyphenated form;
name_norm preserves spaces for word-level matching.

Source: 02-RESEARCH.md §Pattern 7.
"""

from __future__ import annotations

import re
import unicodedata

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_name(raw: str) -> str:
    """NORM-05: lowercase + NFKD-decompose + strip combining + strip punct + collapse ws."""
    if not raw:
        return ""
    s = unicodedata.normalize("NFKD", raw.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


__all__ = ["normalize_name"]
