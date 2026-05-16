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
    # Product types — English. These categorize a SKU's form (cream / serum
    # / gel / etc.) and are systematically dropped on the viled side because
    # the Russian product-type prefix already conveys them. Safe to strip.
    "cream", "creme", "serum", "lotion", "toner", "cleanser", "wash", "gel",
    "milk", "foam", "mask", "oil", "water", "balm", "butter", "lipstick",
    "gloss", "lipglass", "liner", "pencil", "mascara", "foundation", "blush",
    "bronzer", "highlighter", "powder", "primer", "base", "concealer",
    "makeup", "treatment", "shampoo", "conditioner", "spray", "mist",
    "perfume", "parfum", "eau", "cologne", "fragrance", "deodorant",
    "antiperspirant", "moisturizer", "moisturizing", "moisturising",
    # Generic packaging / size markers — also systematically asymmetric.
    "set", "kit", "collection", "duo", "trio", "combo", "edition",
    "edp", "edt", "mini", "travel",
    # Generic descriptors with no product-distinguishing power.
    "spf", "men", "women", "homme", "femme", "pour", "jour", "nuit",
    "the", "with", "and", "for",
})

# Variant markers — words that distinguish DIFFERENT SKUs of the same
# product family. If they appear in the GA-side residual (g_disc) but
# NOT on the viled side, the pair is a Kilian "Good Girl Gone Bad" base
# vs "Good Girl Gone Bad Extreme/Refill" variant mismatch — reject.
#
# These MUST NOT be in STOPWORDS (stripping would let variants collapse
# onto the base SKU).
#
# Source: matcher-review-2026-05-15 run-19 false-positive audit.
VARIANT_MARKERS: frozenset[str] = frozenset({
    # English variant qualifiers
    "extreme", "intense", "intensely", "original", "classic", "signature",
    "oud", "fraiche", "sport", "drama", "prestige", "limited",
    "refill", "concentrate", "essence", "elixir",
    # Russian variant qualifiers (after _LATIN — empty; kept for documentation)
})


# Russian product-type buckets — viled uses one of these as the leading
# word(s) of name; GA's composed name (productType + brand + name) does
# the same. When the V and G first-Russian-words map to DIFFERENT buckets,
# the pair is a cross-category match (e.g. "Крем для рук Portrait of a
# Lady" vs "Парфюмерная вода Portrait of a Lady By Frederic Malle").
#
# Each entry maps a Cyrillic STEM (case-insensitive prefix-match) to a
# canonical bucket name. Lookup picks the first stem that the leading
# Cyrillic words start with.
#
# Source: matcher-review-2026-05-15 run-19 v2.7 FP audit — cross-category
# matches surfaced when volume-loose mode let hand creams pair with
# perfumes that share the marketing name.
_PRODUCT_TYPE_STEMS: tuple[tuple[str, str], ...] = (
    # ---- Compound stems (must come BEFORE their constituent singles so
    # the compound-priority pass in product_type_bucket finds them) ----
    ("крем-основа",  "foundation_base"),   # "Крем-основа для лица" — primer
    ("гель-крем",    "cream"),             # пре-existing compound

    # Fragrance family — IMPORTANT: stems must be precise enough NOT to
    # catch ADJECTIVE forms ("парфюмированное мыло" = perfumed SOAP, not
    # perfume). Use "парфюмерн-" not "парфюм-" because the adjective
    # "парфюмированн-" branches differently after "парфюм".
    # Sub-buckets (perfume_edt / perfume_edp / perfume_parfum / perfume_cologne)
    # are applied in product_type_bucket after this list resolves the base
    # to `perfume`. Operator review 2026-05-16 surfaced viled EDT × GA EDP /
    # GA Парфюм cross-concentration FPs that must be vetoed.
    ("парфюмерн",    "perfume"),    # парфюмерная вода / -ной / -ные
    ("туалетн",      "perfume"),    # туалетная вода (EDT)
    ("одеколон",     "perfume"),    # cologne
    ("духи",         "perfume"),    # Дух — extrait de parfum (highest concentration)
    # NOTE: removed "аромат" stem 2026-05-16 — overreached to "ароматическая
    # свеча" (candle) and "ароматизатор" (room freshener). Run-20 audit
    # confirmed no current viled/GA SKU uses "ароматическая вода" as a
    # leading product-type — "парфюмерная" / "туалетная" / "духи" cover the
    # actual fragrance vocabulary in stock.
    # Mascara MUST come before "маск" so "маскара" doesn't bucket as mask
    ("маскар",       "mascara"),    # маскара (transliteration form)
    ("туш",          "mascara"),    # тушь / туши (plural) / тушью
    # Skincare
    ("крем",         "cream"),
    ("сыворот",      "serum"),
    ("эмульси",      "lotion"),
    ("лосьон",       "lotion"),
    ("тоник",        "toner"),
    ("эссенци",      "essence"),
    ("маск",         "mask"),       # face mask, hair mask (ONLY after маскар)
    ("концентрат",   "serum"),
    ("масл",         "oil"),
    ("эликсир",      "elixir"),
    ("патч",         "patch"),
    ("флюид",        "fluid"),
    ("база",         "foundation_base"), # «База под макияж» — viled-style primer naming
    # Cleansing
    ("гел",          "gel"),         # гель / геля / гелем (Russian declension)
    ("пен",          "foam"),        # пенка / пенки / пенный / пенный
    ("мыл",          "soap"),
    ("молочк",       "milk"),
    ("мицелл",       "micellar"),
    ("скраб",        "scrub"),
    ("пилинг",       "peeling"),
    ("гомм",         "gommage"),
    # Hair
    ("шампунь",      "shampoo"),
    ("кондиционер",  "conditioner"),
    ("бальзам-конд", "conditioner"),
    ("спре",         "spray"),     # спрей / спреи (plural viled-style normalization)
    ("дымк",         "spray"),
    ("мист",         "spray"),     # мист для волос — hair mist, atomized like spray
    ("сыворотка-сп", "spray"),
    # Makeup
    ("помад",        "lipstick"),
    ("блеск",        "lipgloss"),
    ("карандаш",     "pencil"),
    ("подводк",      "liner"),
    ("консил",       "concealer"),
    ("палетк",       "palette"),    # палетка теней / палетка хайлайтеров (base bucket;
                                    # product_type_bucket sub-divides into
                                    # palette_eyeshadow / palette_corrector / etc.)
    ("тен",          "palette"),    # тени для век (same bucket as палетка — same product family)
    ("кисть",        "brush_tool"), # cosmetic brush (the tool) — NOT a beauty liquid
    ("очист",        "cleanser"),   # очищающее средство / средство для очистки
    ("тональн",      "foundation"),
    ("основ",        "foundation"),
    ("пудр",         "powder"),
    ("румян",        "blush"),
    ("хаила",        "highlighter"), # viled й→и normalizer turns "Хайлайтер" into
                                     # "хаилаитер"; stem must NOT contain й
    ("хайла",        "highlighter"), # GA / Cyrillic-strict normalizers may preserve й
    ("бронз",        "bronzer"),
    ("праймер",      "primer"),
    ("лаин",         "liner"),      # лайнер / лайнера (Russian declension)
    # Body / personal care
    ("дезодорант",   "deodorant"),
    ("антиперспир",  "deodorant"),
    ("свеч",         "candle"),     # свеча, свечи — NOT perfume even when ароматическая
    ("атомаизер",    "atomizer"),   # атомайзер — refillable spray bottle, not parfum
    ("футляр",       "case"),       # cosmetic case / cushion case — accessory, NOT a beauty liquid
    ("массаж",       "device"),     # массажер для лица — device, NOT a cream
    ("бальзам",      "balm"),       # generic — placed late
    # Sets / multipacks (caller separately filters multipack_flag, but
    # the leading word still appears in name)
    ("набор",        "set"),
    ("рефил",        "refill"),     # variant of base — VARIANT_MARKERS also caught
    ("рефилл",       "refill"),
)


def _cyrillic_leading_words(text: str | None) -> list[str]:
    """Return up to 3 Cyrillic product-type words from the name, in
    first-appearance order — INCLUDING when Cyrillic words appear after
    a non-Cyrillic prefix.

    Historical name kept for backwards compatibility. Limited to 3 words
    because the BASE bucket is determined by the leading product-type
    noun ("крем", "помада", "парфюмерная") — a 3-word window catches
    that plus a refill-marker plus one safety word. For body-part
    sub-bucketing (which needs to find "для глаз" several words into the
    name), see `_all_cyrillic_words` instead.
    """
    if not text:
        return []
    out: list[str] = []
    for word in text.lower().split():
        if all(("а" <= ch <= "я") or ch == "ё" or ch == "-" for ch in word):
            if len(word) >= 3:
                out.append(word)
                if len(out) >= 3:
                    break
    return out


def _all_cyrillic_words(text: str | None) -> list[str]:
    """Return ALL Cyrillic words (len ≥3) from the name. Used by
    body-part sub-bucketing where the qualifier «глаз» / «лица» / «рук»
    may sit anywhere — including after «для области вокруг ...» (6th
    word) which the 3-word leading-scan would miss.
    """
    if not text:
        return []
    out: list[str] = []
    for word in text.lower().split():
        if all(("а" <= ch <= "я") or ch == "ё" or ch == "-" for ch in word):
            if len(word) >= 3:
                out.append(word)
    return out


def product_type_bucket(name: str | None) -> str | None:
    """Map a name's Cyrillic words to a product-type bucket.

    Returns None when no Cyrillic word matches any stem. Caller treats None
    as "no signal" (don't apply cross-category veto).

    Lookup is THREE-pass:

      1. **Priority overrides** — high-precedence qualifiers ("набор",
         "сет") fire regardless of where they sit. A "Парфюмерный набор" is
         a SET (bucketed `set`), not a perfume — even though "Парфюмерный"
         appears first and would otherwise match the perfume stem.

      2. **Refill strip** — a leading "Рефил"/"Рефилл" prefix is dropped so
         the meaningful product type behind it determines the bucket
         (perfume refill → perfume, shower-gel refill → gel, etc.).

      3. **Stem scan** — first Cyrillic word whose prefix matches any
         stem wins. After the base bucket is determined, sub-bucketing
         applies for `palette` (см. ниже) — different palette TYPES
         (eyeshadow vs corrector vs highlighter) should not match.
    """
    words = _cyrillic_leading_words(name)
    if not words:
        return None

    # ---- Pass 1: priority overrides (qualifier-anywhere wins) ----
    # "Парфюмерный набор Travel set" — leading "парфюмерный" would match
    # perfume stem; "набор" anywhere overrides to `set`.
    for word in words:
        if word.startswith("набор") or word.startswith("сет"):
            return "set"

    # ---- Pass 2: refill strip ----
    while words and (words[0].startswith("рефил")):
        words = words[1:]
    if not words:
        return None

    # ---- Pass 3: stem scan (compounds FIRST, then singles) ----
    # Compound stems (e.g. «крем-основа» → foundation_base) MUST be tested
    # before their constituent single words ("крем" → cream). Without
    # this ordering the single word matches first and the compound never
    # fires — pre-fix виled «База под макияж» × GA «Крем-основа для лица»
    # bucketed differently and missed the legitimate primer-vs-primer match.
    compounds = [f"{w1}-{w2}" for w1 in words for w2 in words if w1 != w2]
    candidates = compounds + list(words)
    base: str | None = None
    for word in candidates:
        for stem, bucket in _PRODUCT_TYPE_STEMS:
            if word.startswith(stem):
                base = bucket
                break
        if base is not None:
            break
    if base is None:
        return None

    # ---- Sub-bucketing — refine base into a more discriminative category ----
    # For body-part sub-bucketing we need ALL Cyrillic words, not just the
    # 3 leading ones — "крем основа для области вокруг ГЛАЗ" has the
    # qualifier in the 6th word position.
    all_words = _all_cyrillic_words(name)
    return _refine_sub_bucket(base, all_words)


# Body-part qualifier prefixes — used to split skincare/makeup family buckets
# into face/eye/hands/body/etc. variants so face cream ≠ eye cream.
_BODY_PART_STEMS: tuple[tuple[str, str], ...] = (
    ("глаз",     "eye"),       # для глаз / вокруг глаз
    ("век",      "eye"),       # для век (eyelids) — same sub-bucket as glaz
    ("ресниц",   "lashes"),    # для ресниц
    ("брове",    "brows"),     # бровей
    ("губ",      "lips"),      # губ / губная
    ("лиц",      "face"),      # для лица
    ("ног",      "feet"),      # для ног
    ("рук",      "hands"),     # для рук
    ("шеи",      "neck"),
    ("декольте", "decolletage"),
    ("тел",      "body"),      # для тела (placed last — generic)
)

# Skincare/makeup families that benefit from body-part sub-bucketing.
# Fragrance (perfume) gets its own sub-bucketing by concentration instead.
_BODY_PART_AWARE_BASES = frozenset({
    "cream", "serum", "oil", "lotion", "gel", "balm", "fluid",
    "mask", "essence", "elixir", "milk", "foam", "soap", "scrub",
    "patch", "toner", "cleanser", "spray", "mist", "foundation_base",
})

# Subset of body-part-aware bases that default to FACE when no explicit
# body-part word is present. Operator-confirmed semantic (2026-05-16):
# a generic "Антивозрастной крем" / "База под макияж" / "Крем-основа" is
# implicitly a face product — should NOT match an explicit eye-cream /
# body-lotion variant of the same brand+marketing line.
_DEFAULT_FACE_BASES = frozenset({
    "cream", "serum", "essence", "toner", "foundation_base",
})


def _refine_sub_bucket(base: str, words: list[str]) -> str:
    """Apply category-specific sub-bucketing to a base bucket.

    - Palette → eyeshadow / corrector / highlighter / blush / bronzer
    - Perfume → parfum / edp / edt / cologne (by concentration stem)
    - Skincare/makeup with body-part qualifier → cream_face / serum_eye / …
    """
    # Palette family
    if base == "palette":
        for word in words:
            if word.startswith("коррекц"):
                return "palette_corrector"
            if word.startswith("тен"):
                return "palette_eyeshadow"
            if word.startswith("хаила") or word.startswith("хайла"):
                return "palette_highlighter"
            if word.startswith("румян"):
                return "palette_blush"
            if word.startswith("брон") or word.startswith("бронз"):
                return "palette_bronzer"
        return base

    # Fragrance concentration
    if base == "perfume":
        # Walk words and pick the FIRST concentration marker. Stems are
        # checked in priority order: «духи» > «парфюмерн» > «туалетн» >
        # «одеколон» so a mixed name like «Парфюмерная вода-спрей»
        # collapses to EDP (not cologne).
        for word in words:
            if word.startswith("духи"):
                return "perfume_parfum"
            if word.startswith("парфюмерн"):
                return "perfume_edp"
            if word.startswith("туалетн"):
                return "perfume_edt"
            if word.startswith("одеколон"):
                return "perfume_cologne"
        return base

    # Body-part sub-bucketing for skincare/makeup
    if base in _BODY_PART_AWARE_BASES:
        for word in words:
            for stem, suffix in _BODY_PART_STEMS:
                if word.startswith(stem):
                    return f"{base}_{suffix}"
        # No explicit body part — apply "default face" for skincare/primer
        # bases (cream, serum, toner, foundation_base, etc.). This ensures
        # bare «Крем X» is treated as a face cream and does NOT match an
        # explicit «Крем для глаз X» variant of the same line.
        if base in _DEFAULT_FACE_BASES:
            return f"{base}_face"
        return base

    return base


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
    # Cross-category veto: viled and GA names start with a Russian
    # product-type word ("Крем для рук" / "Парфюмерная вода" / etc.).
    # If both sides resolve to a known bucket AND the buckets differ,
    # the pair is a hand-cream vs perfume style cross-category match —
    # reject before anything else. When either side has no Cyrillic
    # prefix (or the prefix doesn't map to a known bucket), this veto
    # silently does not apply.
    v_bucket = product_type_bucket(viled_name_norm)
    g_bucket = product_type_bucket(goldapple_name_norm)
    if v_bucket and g_bucket and v_bucket != g_bucket:
        return False

    v_tok = en_tokens(viled_name_norm)
    # GA-side token set is the UNION of slug + name_norm tokens.
    #
    # The URL slug is the canonical short marketing form (e.g.
    # ``good-girl-gone-bad``). The name_norm carries the variant qualifier
    # the slug drops (``Refil``, ``Extreme``, ``Eye Base``, ``Eau Fraiche``,
    # ``Eye Treatment``). Using the union catches both:
    #   * the legitimate `code` slug ⊆ `armani code` viled match (slug-only
    #     tokens suffice)
    #   * the false `good-girl-gone-bad` ↔ `good-girl-gone-bad-extreme`
    #     variant mismatch — Refill / Extreme appears in name_norm even
    #     when both share the slug; that distinct discriminative token
    #     forces Path-4 rejection.
    g_tok = slug_tokens(goldapple_url) | en_tokens(goldapple_name_norm)

    # Path 2: strict-equality fallback for synthetic / single-char names.
    if not v_tok and not g_tok:
        return (viled_name_norm or "") == (goldapple_name_norm or "")

    # Need at least one shared Latin token to even consider a match.
    inter = v_tok & g_tok
    if not inter:
        return False

    # Path 3: GA-side ⊆ viled-side (one direction only).
    #
    # Bidirectional Path 3 was too loose: it accepted viled-base SKUs
    # against GA-variant slugs (e.g. ``Hypnose`` ⊊ ``hypnose-drama``).
    # The natural asymmetry is that viled names are LONGER (Russian
    # product-type prefix + brand redundancy + size suffix) and GA
    # marketing slugs are SHORTER. So if the GA token set IS a subset of
    # viled's, that's the legitimate "slug fits inside viled" case.
    if g_tok and g_tok.issubset(v_tok):
        return True

    # Path 4: discriminative residual with variant-marker veto.
    #
    # Build residuals after stripping brand tokens + product-type
    # stopwords + numeric tokens. Accept when:
    #   * residuals share at least one discriminative token, AND
    #   * at least one side has NO leftover discriminative tokens
    #     (the other's extras are shade words, descriptive adjectives,
    #     or other non-variant info that viled simply omits), AND
    #   * the residual extras don't contain a VARIANT_MARKER — those
    #     mean different SKUs (Kilian "Good Girl Gone Bad" base vs
    #     "Good Girl Gone Bad Extreme/Refill") and must reject.
    v_disc = _discriminative(v_tok, brand_norm)
    g_disc = _discriminative(g_tok, brand_norm)
    if not (v_disc & g_disc):
        return False
    v_only = v_disc - g_disc
    g_only = g_disc - v_disc
    # Variant veto — if EITHER side's residual contains a variant marker
    # AND the other side lacks it, the pair is a different SKU. Reject.
    if (v_only & VARIANT_MARKERS) or (g_only & VARIANT_MARKERS):
        return False
    # Standard relaxation: accept if at least one side has no excess
    # discriminative tokens. Both sides non-empty → competing
    # distinguishers (Azzaro Chrome Aqua vs Chrome United) → reject.
    if v_only and g_only:
        return False
    return True


__all__ = [
    "STOPWORDS",
    "VARIANT_MARKERS",
    "brand_tokens",
    "en_tokens",
    "name_matches",
    "product_type_bucket",
    "slug_tokens",
]
