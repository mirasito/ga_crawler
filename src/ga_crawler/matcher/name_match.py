"""Token-based name match logic for the Phase 4 matcher (v2).

Why this exists
---------------
v1 of the matcher required ``name_norm = name_norm`` SQL equality between
viled and goldapple snapshots. On run-18 production data this produced 0
matches across 144 comparable GA SKUs and 3807 viled SKUs, because:

  * viled name = ``[RU product type] [EN marketing core] [, объём][, оттенок]``
    e.g. ``'Парфюмерная вода Armani Code, 75 мл'``
  * goldapple name = ``[EN marketing core]`` only
    e.g. ``'CODE'`` (sometimes shorter than the EN slug in the URL)
  * the two normalized strings can NEVER be byte-equal.

Ground-truth analysis on 228 manually-paired SKUs (.planning/.../inbox/
manual_matches_v2.csv) shows the GA URL slug is consistently the canonical
EN marketing name in kebab-case (e.g. ``almost-lipstick``,
``smokey-eye-mascara``), and the viled name contains the same English
core embedded in a longer Russian-descriptive string. Token-overlap with a
small stopword list captures 150/202 = 74% of ground-truth pairs vs 0 strict.

Strategy v2 (precision-first)
-----------------------------
Given a (viled, goldapple) candidate pair already pre-filtered by
``brand_norm`` and ``volume_norm`` equality in SQL:

  1. **Latin token extraction**
     ``v_tok = en_tokens(viled.name_norm)`` — lowercase Latin words ≥3 chars.
     ``g_tok = slug_tokens(goldapple.url)`` falling back to
     ``en_tokens(goldapple.name_norm)`` when the URL has no slug.

  2. **Strict-equality fallback** (preserves synthetic-fixture behavior in
     unit tests where ``name_norm`` is a single char and both Latin token
     sets are empty): if ``v_tok`` and ``g_tok`` are both empty AND viled
     and goldapple ``name_norm`` are byte-equal, ACCEPT.

  3. **Subset path**: if ``g_tok ⊆ v_tok`` or ``v_tok ⊆ g_tok``, ACCEPT.
     Catches `almost-lipstick` ⊆ `almost black honey lipstick`.

  4. **Discriminative-residual path**: strip brand tokens and product-type
     stopwords from both sides → ``v_disc`` and ``g_disc``. ACCEPT only
     when they intersect AND one side's residual is a subset of the other
     (i.e. the only difference is shade words or product-type suffixes,
     never two competing distinguishing tokens like
     ``aqua`` vs ``united`` on Azzaro Chrome).

  5. Otherwise REJECT.

Stopwords list is intentionally small and conservative — only true
product-type words and category descriptors that systematically appear in
GA slugs but not in viled name_norm (or vice versa).

Source: matcher-review-2026-05-15 evidence-backed analysis on user's
228-pair ground-truth dataset; brand+volume gate is enforced upstream by
SQL JOIN so this module only does name-side disambiguation.
"""

from __future__ import annotations

import re


# Latin tokens, length ≥3, lowercase. Numbers allowed (preserves shade codes
# like "1n2" if they happen to overlap on both sides, harmlessly).
_LATIN = re.compile(r"[a-z0-9]{3,}")

# GA URL slug pattern (numeric SKU prefix + kebab-case slug).
_SLUG_FROM_URL = re.compile(r"goldapple\.kz/\d+-([a-z0-9\-]+)")

# Stopword list — product-type words + non-discriminative descriptors that
# systematically diverge between viled (Russian prefix) and goldapple
# (English marketing tail).  Keep this list SMALL and conservative; over-
# stripping causes false matches (e.g. "stronger with you absolutely" vs
# "stronger with you powerfully" collapse to the same residual if "with"
# and "you" are stripped — they are NOT stopwords for that reason).
STOPWORDS: frozenset[str] = frozenset({
    # Product types — English
    "cream", "creme", "serum", "lotion", "toner", "cleanser", "wash", "gel",
    "milk", "foam", "mask", "oil", "water", "balm", "butter", "lipstick",
    "gloss", "lipglass", "liner", "pencil", "mascara", "foundation", "blush",
    "bronzer", "highlighter", "powder", "primer", "base", "concealer",
    "makeup", "treatment", "shampoo", "conditioner", "spray", "mist",
    "perfume", "parfum", "eau", "cologne", "fragrance", "deodorant",
    "antiperspirant", "moisturizer", "moisturizing", "moisturising",
    # Generic packaging / variant words
    "set", "kit", "collection", "duo", "trio", "combo", "refill", "edition",
    "limited", "edp", "edt", "mini", "travel",
    # Generic body-part / area markers — non-discriminative when present on
    # only one side (e.g. GA slug "lip-pencil" vs viled "Карандаш для губ").
    "face", "body", "hand", "foot", "eyes", "lips", "hair", "skin",
    # Generic descriptors
    "spf", "men", "women", "homme", "femme", "pour", "jour", "nuit",
    "the", "with", "and", "for",
})


def en_tokens(text: str | None) -> set[str]:
    """Latin tokens length ≥3 from a string (lowercased)."""
    if not text:
        return set()
    return set(_LATIN.findall(text.lower()))


def slug_tokens(ga_url: str | None) -> set[str]:
    """Latin tokens length ≥3 from the goldapple URL slug (kebab segment).

    Returns an empty set when the URL has no slug (e.g. synthetic-fixture URLs
    like ``https://goldapple.kz/G1``) — caller falls back to GA ``name_norm``.
    """
    if not ga_url:
        return set()
    m = _SLUG_FROM_URL.search(ga_url.lower())
    if not m:
        return set()
    slug = m.group(1).rstrip("/")
    return {t for t in slug.split("-") if len(t) >= 3 and t.isalnum()}


def brand_tokens(brand_norm: str | None) -> set[str]:
    """Tokens that make up a multi-word brand_norm (e.g. ``armani_beauty``
    → ``{armani, beauty}``).  Stripped from the discriminative-residual
    calculation so the brand word itself doesn't count as a distinguishing
    token (it's already pinned by the SQL JOIN's brand_norm equality).
    """
    if not brand_norm:
        return set()
    return {t for t in re.split(r"[-_\s]+", brand_norm.lower()) if len(t) >= 3}


def _discriminative(tokens: set[str], brand: str | None) -> set[str]:
    """Tokens minus stopwords, brand-tokens, and pure-digit tokens.

    These are the tokens that actually distinguish one SKU from another
    within the (brand, volume) pre-filter — e.g. for Azzaro Chrome Aqua vs
    Azzaro Chrome United, after stripping ``azzaro`` (brand) and ``chrome``
    (kept as discriminative), the residuals are ``{aqua}`` and ``{united}``.
    """
    btok = brand_tokens(brand)
    out = set()
    for t in tokens:
        if t in STOPWORDS:
            continue
        if t in btok:
            continue
        if t.isdigit():
            continue
        out.add(t)
    return out


def name_matches(
    *,
    viled_name_norm: str | None,
    goldapple_url: str | None,
    goldapple_name_norm: str | None,
    brand_norm: str | None,
) -> bool:
    """Return True iff the (viled, goldapple) pair matches by name-side rules.

    Pre-conditions enforced by the caller:
      * brand_norm equal on both sides (SQL JOIN)
      * volume_norm equal AND non-null on both sides (SQL JOIN + filter)
      * multipack_flag = 0 on both sides
      * stock_state != 'DELISTED' on both sides
      * current_price NOT NULL on both sides

    See module docstring for the full v2 strategy.
    """
    v_tok = en_tokens(viled_name_norm)
    g_tok = slug_tokens(goldapple_url) or en_tokens(goldapple_name_norm)

    # Path 2: strict-equality fallback for synthetic / single-char names.
    if not v_tok and not g_tok:
        return (viled_name_norm or "") == (goldapple_name_norm or "")

    # Need at least one shared Latin token to even consider a match.
    inter = v_tok & g_tok
    if not inter:
        return False

    # Path 3: subset (either direction).
    if g_tok and g_tok.issubset(v_tok):
        return True
    if v_tok and v_tok.issubset(g_tok):
        return True

    # Path 4: discriminative-residual.  Both sides must share at least one
    # discriminative token, AND their residuals must be subset-compatible
    # (one side has no extras that contradict the other).
    v_disc = _discriminative(v_tok, brand_norm)
    g_disc = _discriminative(g_tok, brand_norm)
    if not (v_disc & g_disc):
        return False
    v_only = v_disc - g_disc
    g_only = g_disc - v_disc
    # Reject "Azzaro Chrome Aqua" vs "Azzaro Chrome United" — both
    # residuals have a distinct discriminative token the other lacks.
    if v_only and g_only:
        return False
    return True


__all__ = [
    "STOPWORDS",
    "brand_tokens",
    "en_tokens",
    "name_matches",
    "slug_tokens",
]
