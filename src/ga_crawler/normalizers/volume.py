"""NORM-03 + NORM-04 volume normalizer — layered grammar.

Layered:
  1. detect_multipack(raw) → bool, INDEPENDENT of parsability (Open Q4)
  2. parse_volume(raw) → Volume or None:
     a. Multipack-with-amount patterns (`3 x 50 мл`, `3 шт x 50мл`,
        `Set of 3 × 50ml`) → Volume(amount, unit, N)
     b. Multipack-keyword-only (`набор`, `kit`, `комплект`, `N шт` without
        per-unit amount) → None (caller sets multipack_flag separately
        via detect_multipack)
     c. Single-volume regex → Volume(amount, unit, 1)
     d. None for unparseable

Source: 02-RESEARCH.md §Pattern 6.
Decisions: D-215 layered grammar; NORM-04 multipack_flag persists separately.
Pitfall 6: Russian 'л' standalone is risky → whitelist via UNIT_TABLE keys.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


UNIT_TABLE: dict[str, str] = {
    # Russian (lowercase, post-NFKD)
    "мл": "ml",
    "милилитр": "ml",
    "миллилитр": "ml",
    "г": "g",
    "гр": "g",
    "грамм": "g",
    "л": "l",
    "литр": "l",
    "шт": "pcs",
    "штук": "pcs",
    "унц": "oz",
    "унция": "oz",
    "унций": "oz",
    "кг": "kg",
    # English (lowercase)
    "ml": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "fl": "fl",  # combined "fl oz"
    "kg": "kg",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "pcs": "pcs",
    "pc": "pcs",
}

# Multipack patterns (in order; first hit wins for parse_volume).
#
# Pattern A — `(N) [unit-token] x (AMOUNT) UNIT` (e.g. `3 шт x 50мл`):
#   Count first, optional separator unit (e.g. шт/pcs), then × (or x or х),
#   then per-unit amount + UNIT.
_MULTIPACK_NUNIT_X_AMOUNT_RE = re.compile(
    r"(\d+)\s*(?:[a-zа-яё]+)?\s*[xх×]\s*(\d+(?:[.,]\d+)?)\s*([a-zа-яё]+)",
    re.IGNORECASE,
)

# Pattern B — `Set of N × AMOUNT UNIT` (English explicit-set prefix):
_MULTIPACK_SET_OF_RE = re.compile(
    r"set\s+of\s+(\d+)\s*[xх×]?\s*(\d+(?:[.,]\d+)?)\s*([a-zа-яё]+)",
    re.IGNORECASE,
)

# Keyword-only multipack patterns (no per-unit volume extractable):
_MULTIPACK_KEYWORD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bset\s+of\s+\d+", re.IGNORECASE),
    re.compile(r"\bnabor\b|\bнабор", re.IGNORECASE),
    re.compile(r"\bkit\b", re.IGNORECASE),
    re.compile(r"\bкомплект", re.IGNORECASE),
    re.compile(r"\d+\s*шт\b", re.IGNORECASE),  # "10 шт" without "x AMOUNT"
    re.compile(r"\d+\s*[xх×]\s*\d+", re.IGNORECASE),  # generic N x M
]

# Single volume: "(AMOUNT) (UNIT)" — applied AFTER multipack patterns failed.
_SINGLE_VOLUME_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*([a-zа-яё]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Volume:
    amount: Decimal
    unit: str
    count: int


def _to_decimal(s: str) -> Decimal:
    return Decimal(s.replace(",", "."))


def detect_multipack(raw: str) -> bool:
    """True if raw text contains multipack markers — independent of parse_volume.

    Open Q4: multipack_flag survives even when amount/unit unparseable
    (`набор пробников` → True; `10 шт` → True; `30 мл` → False).
    """
    if not raw:
        return False
    raw_lower = raw.lower()
    return any(p.search(raw_lower) for p in _MULTIPACK_KEYWORD_PATTERNS)


def parse_volume(raw: str) -> Optional[Volume]:
    """Returns Volume or None. See module docstring for layered semantics."""
    if not raw:
        return None
    raw_lower = raw.lower()

    # Layer 1a: `Set of N × AMOUNT UNIT` (must run before generic N×AMOUNT
    # so the "set of" prefix is consumed).
    m = _MULTIPACK_SET_OF_RE.search(raw_lower)
    if m:
        try:
            count = int(m.group(1))
            amount = _to_decimal(m.group(2))
            unit_raw = m.group(3)
            unit = UNIT_TABLE.get(unit_raw)
            if unit and amount > 0 and count > 0:
                return Volume(amount=amount, unit=unit, count=count)
        except (ValueError, ArithmeticError):
            pass

    # Layer 1b: `(N) [optional unit-token] [x] (AMOUNT) UNIT` patterns
    # (handles bare `3 x 50мл` AND `3 шт x 50мл`).
    m = _MULTIPACK_NUNIT_X_AMOUNT_RE.search(raw_lower)
    if m:
        try:
            count = int(m.group(1))
            amount = _to_decimal(m.group(2))
            unit_raw = m.group(3)
            unit = UNIT_TABLE.get(unit_raw)
            if unit and amount > 0 and count > 0:
                return Volume(amount=amount, unit=unit, count=count)
        except (ValueError, ArithmeticError):
            pass

    # Layer 2: keyword-only multipack — return None (caller uses detect_multipack).
    # Caller treats None+detect_multipack=True as "multipack with unknown per-unit volume".
    for p in _MULTIPACK_KEYWORD_PATTERNS:
        if p.search(raw_lower):
            return None

    # Layer 3: single volume regex — first occurrence with a known unit wins.
    for m in _SINGLE_VOLUME_RE.finditer(raw_lower):
        try:
            amount = _to_decimal(m.group(1))
            unit_raw = m.group(2)
            unit = UNIT_TABLE.get(unit_raw)
            if unit and amount > 0:
                return Volume(amount=amount, unit=unit, count=1)
        except (ValueError, ArithmeticError):
            continue

    return None


__all__ = ["Volume", "UNIT_TABLE", "parse_volume", "detect_multipack"]
