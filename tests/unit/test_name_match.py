"""Unit tests for matcher v2 token-overlap name-side logic.

Pins the four match paths defined in ``ga_crawler.matcher.name_match``:
  - Path 2: strict-equality fallback when both Latin token sets are empty
  - Path 3: subset (either direction)
  - Path 4: discriminative-residual with brand-token + stopword strip
  - Reject path: competing distinguishing tokens on both sides

All test cases are sourced from real ground-truth pairs in the user's
228-row manual-match Sheet (.planning notes) and from run-18 false-positive
pairs that the v1 strict matcher would have surfaced under brand+volume
alone.
"""

from __future__ import annotations

import pytest

from ga_crawler.matcher.name_match import (
    brand_tokens,
    en_tokens,
    name_matches,
    slug_tokens,
)


# ---- Token helpers ----


def test_en_tokens_strips_short_and_lowercases() -> None:
    assert en_tokens("Парфюмерная вода Armani Code, 75 мл") == {"armani", "code"}


def test_en_tokens_empty_on_none_and_empty() -> None:
    assert en_tokens(None) == set()
    assert en_tokens("") == set()


def test_slug_tokens_extracts_kebab_segments() -> None:
    url = "https://goldapple.kz/19000126321-almost-lipstick"
    assert slug_tokens(url) == {"almost", "lipstick"}


def test_slug_tokens_empty_when_no_slug() -> None:
    # Synthetic-fixture URLs from unit tests don't have a goldapple slug.
    assert slug_tokens("https://goldapple.kz/G1") == set()
    assert slug_tokens(None) == set()


def test_brand_tokens_splits_multiword_brand_norm() -> None:
    assert brand_tokens("armani_beauty") == {"armani", "beauty"}
    assert brand_tokens("bobbi-brown") == {"bobbi", "brown"}
    assert brand_tokens("mac") == {"mac"}


# ---- Path 2: strict-equality fallback (synthetic fixtures) ----


def test_strict_equality_fallback_single_char_names() -> None:
    """Synthetic test data uses 1-char names that produce no Latin tokens.
    Fallback to byte-equality must accept these so unit-test fixtures still
    pin the SQL formula behavior.
    """
    assert name_matches(
        viled_name_norm="a",
        goldapple_url="https://goldapple.kz/G1",
        goldapple_name_norm="a",
        brand_norm="givenchy",
    )


def test_strict_equality_fallback_rejects_different_short_names() -> None:
    assert not name_matches(
        viled_name_norm="a",
        goldapple_url="https://goldapple.kz/G1",
        goldapple_name_norm="b",
        brand_norm="givenchy",
    )


# ---- Path 3: subset (either direction) ----


def test_subset_ga_slug_in_viled_name() -> None:
    """GT pair v=282355: slug 'almost-lipstick' ⊆ viled 'Almost Lipstick Black Honey'."""
    assert name_matches(
        viled_name_norm="помада блеск для губ almost lipstick оттенок black honey",
        goldapple_url="https://goldapple.kz/19000126321-almost-lipstick",
        goldapple_name_norm="almost lipstick",
        brand_norm="mac",
    )


def test_subset_viled_name_in_ga_slug() -> None:
    """GT pair v=239922: slug 'vitamin-enriched' ⊇ viled tokens.

    viled latin = {deluxe, vitamin, enriched}; GA slug = {vitamin, enriched}.
    GA ⊆ V, accept.
    """
    assert name_matches(
        viled_name_norm="база под макияж deluxe vitamin enriched 100 мл",
        goldapple_url="https://goldapple.kz/19000140361-vitamin-enriched",
        goldapple_name_norm="vitamin enriched",
        brand_norm="bobbi-brown",
    )


# ---- Path 4: discriminative-residual (stopword strip enables match) ----


def test_discriminative_strip_accepts_when_only_diff_is_stopword() -> None:
    """GT pair v=154810: slug 'ultra-facial-cleanser' vs viled 'ultra facial 150 мл'.

    Naive subset fails (cleanser missing from viled). After stripping the
    'cleanser' stopword and numeric tokens, both residuals = {ultra, facial}.
    """
    assert name_matches(
        viled_name_norm="гель для умывания для всех типов кожи ultra facial 150 мл",
        goldapple_url="https://goldapple.kz/15370700001-ultra-facial-cleanser",
        goldapple_name_norm="ultra facial cleanser",
        brand_norm="kiehls",
    )


def test_discriminative_strip_accepts_with_brand_token_stripped() -> None:
    """Multi-word brand_norm tokens must not count as distinguishing.

    Mock case: brand='armani_beauty'. The shared 'armani' would otherwise
    be the only token bridging viled and GA — but it's the brand and gets
    stripped from the discriminative residual.
    """
    assert name_matches(
        viled_name_norm="парфюмерная вода armani code 75 мл",
        goldapple_url="https://goldapple.kz/7381300006-armani-code",
        goldapple_name_norm="armani code",
        brand_norm="armani_beauty",
    )


# ---- Reject path: competing distinguishing tokens ----


def test_rejects_different_perfume_variants_within_same_brand_and_volume() -> None:
    """Run-18 false-positive: 'Stronger With You Absolutely' vs '...Powerfully'.

    Both share {stronger, you} but their distinguishing tail tokens
    (absolutely vs powerfully) are non-stopword and non-overlapping → REJECT.
    """
    assert not name_matches(
        viled_name_norm="парфюмерная вода stronger with you absolutely",
        goldapple_url="https://goldapple.kz/19000493328-armani-stronger-with-you-powerfully",
        goldapple_name_norm="stronger with you powerfully",
        brand_norm="armani_beauty",
    )


def test_rejects_azzaro_chrome_aqua_vs_chrome_united() -> None:
    """Run-18 false-positive: 'Azzaro Chrome Aqua' vs 'Azzaro Chrome United'.

    After stripping brand 'azzaro' the residuals are {chrome, aqua} and
    {chrome, united} — both have a distinct discriminative token.
    """
    assert not name_matches(
        viled_name_norm="туалетная вода azzaro chrome aqua 100 мл",
        goldapple_url="https://goldapple.kz/19000274010-azzaro-chrome-united",
        goldapple_name_norm="azzaro chrome united",
        brand_norm="azzaro",
    )


def test_rejects_no_token_overlap() -> None:
    """No shared Latin tokens at all → REJECT (unless the strict-equality
    fallback applies, which it doesn't here)."""
    assert not name_matches(
        viled_name_norm="карандаш для губ оттенок pale mauve",
        goldapple_url="https://goldapple.kz/19000432737-lip-pencil",
        goldapple_name_norm="lip pencil",
        brand_norm="clinique",
    )


# ---- v2.6 false-positive defenses ----


def test_rejects_kilian_refill_variant() -> None:
    """Run-19 FP: viled `Good Girl Gone Bad By Kilian` (base) ↔ GA composed
    name `Рефил парфюмерной воды Kilian Paris Good Girl Gone Bad`.

    The slug `good-girl-gone-bad` IS shared (same product family) but the
    `refill` token in GA name marks a different SKU. VARIANT_MARKERS veto
    in Path 4 must reject.
    """
    assert not name_matches(
        viled_name_norm="парфюмерная вода good girl gone bad by kilian",
        goldapple_url="https://goldapple.kz/19000311845-good-girl-gone-bad",
        goldapple_name_norm="рефил парфюмерной воды kilian paris good girl gone bad refill",
        brand_norm="kilian_paris",
    )


def test_rejects_kilian_extreme_variant() -> None:
    """Run-19 FP: viled `Good Girl Gone Bad By Kilian` (base) ↔ GA
    `... Good Girl Gone Bad Extreme`. Same family, different SKU."""
    assert not name_matches(
        viled_name_norm="парфюмерная вода good girl gone bad by kilian",
        goldapple_url="https://goldapple.kz/19000311846-good-girl-gone-bad",
        goldapple_name_norm="парфюмерная вода kilian paris good girl gone bad extreme",
        brand_norm="kilian_paris",
    )


def test_rejects_all_about_clean_vs_all_about_eyes() -> None:
    """Run-19 FP: viled face-soap `All About Clean Oily Skin` ↔ GA
    `All About Eyes` eye-cream. Body-part `eyes` is discriminative (not in
    STOPWORDS) so Path-4 residual collapses to incompatible diffs."""
    assert not name_matches(
        viled_name_norm="жидкое мыло для лица all about clean oily skin travel format",
        goldapple_url="https://goldapple.kz/19000035814-all-about-eyes",
        goldapple_name_norm="клиник all about eyes",
        brand_norm="clinique",
    )


def test_accepts_vitamin_enriched_subset() -> None:
    """Regression check: viled `Deluxe Vitamin Enriched` should still match
    GA `vitamin-enriched` slug (base moisturizer, same product family).
    Path-4 one-side-empty relaxation handles the `deluxe` extra on viled."""
    assert name_matches(
        viled_name_norm="база под макияж deluxe vitamin enriched",
        goldapple_url="https://goldapple.kz/19000140361-vitamin-enriched",
        goldapple_name_norm="bobbi brown vitamin enriched",
        brand_norm="bobbi-brown",
    )


def test_rejects_palette_vs_perfume_same_marketing_name() -> None:
    """Run-19 v3.1 FP postmortem (commit 937213d+): viled
    `Палетка теней Eye Color Quad оттенок Electric cherry` (Tom Ford
    eyeshadow palette) matched GA `Парфюмерная вода Tom Ford Electric
    Cherry` because both share the marketing-name "electric cherry" AND
    palette had no `volume_norm` (volume-loose JOIN permits NULL one side).

    Bucket veto must reject this pair: `палетка` → palette bucket,
    `парфюмерная` → perfume bucket, mismatch ⇒ no match."""
    assert not name_matches(
        viled_name_norm="палетка тенеи eye color quad оттенок electric cherry",
        goldapple_url="https://goldapple.kz/19000402298-electric-cherry-eau-de-parfum",
        goldapple_name_norm="парфюмерная вода tom ford electric cherry eau de parfum",
        brand_norm="tom_ford",
    )


def test_accepts_palette_vs_palette_same_product() -> None:
    """Companion to the FP-rejection test: when BOTH sides are palettes,
    bucket veto MUST NOT fire — `палетка` ↔ `палетка` is a same-bucket
    match and the Path-2 token logic should accept the pair."""
    assert name_matches(
        viled_name_norm="палетка тенеи eye color quad оттенок electric cherry",
        goldapple_url="https://goldapple.kz/19000196765-eye-color-quad",
        goldapple_name_norm="палетка тенеи tom ford eye color quad",
        brand_norm="tom_ford",
    )


def test_plural_spray_form_resolves_to_spray_bucket() -> None:
    """viled normalizer emits `спреи` (plural) for "Спрей для тела". The
    bucket stem `спре` covers both `спрей` (singular) and `спреи` (plural)
    so spray-vs-perfume pairs are still vetoed despite plural normalization."""
    from ga_crawler.matcher.name_match import product_type_bucket
    assert product_type_bucket("спреи для тела electric cherry") == "spray"
    assert product_type_bucket("спрей для волос") == "spray"


def test_palette_and_eyeshadow_both_map_to_palette_bucket() -> None:
    """`Тени для век` and `Палетка теней` are the same product family in
    practice — both must map to `palette` so viled "Тени для век" can
    match GA "Палетка теней" without the veto firing."""
    from ga_crawler.matcher.name_match import product_type_bucket
    assert product_type_bucket("палетка тенеи tom ford") == "palette"
    assert product_type_bucket("тени для век guerlain") == "palette"


def test_rejects_perfumed_soap_vs_perfume() -> None:
    """Run-20 v3.1 top-1 FP postmortem (commit f67db88+): viled
    «Парфюмированное мыло Creed Green Irish Tweed 150 гр» matched GA
    «Парфюмерная вода Creed Green Irish Tweed» because the OLD stem
    `парфюм` ate the adjective `парфюмированное` → bucket=perfume on
    both sides → no veto.

    Fix: stem narrowed to `парфюмерн` — adjective `парфюмированн-` no
    longer collides. Soap leading word `мыло` falls through to `мыл`
    stem → bucket=soap. soap × perfume ⇒ veto fires."""
    assert not name_matches(
        viled_name_norm="парфюмированное мыло green irish tweed 150 гр",
        goldapple_url="https://goldapple.kz/26542200005-green-irish-tweed",
        goldapple_name_norm="парфюмерная вода creed green irish tweed",
        brand_norm="creed",
    )


def test_rejects_shower_gel_refill_vs_perfume() -> None:
    """Run-20 same FP class: viled «Рефилл геля для душа Kilian Good
    Girl Gone Bad 250 мл» matched GA «Парфюмерная вода Kilian Good Girl
    Gone Bad». Old `гель` stem missed the genitive «геля» (after refill
    strip). Fix: stem shortened to `гел` covers all Russian declensions.

    After refill prefix strip, leading word becomes `геля` → matches
    `гел` stem → bucket=gel. gel × perfume ⇒ veto fires."""
    assert not name_matches(
        viled_name_norm="рефилл геля для душа good girl gone bad 250 мл",
        goldapple_url="https://goldapple.kz/19000311846-good-girl-gone-bad",
        goldapple_name_norm="парфюмерная вода kilian paris good girl gone bad",
        brand_norm="kilian_paris",
    )


def test_mascara_vs_face_mask_does_not_alias() -> None:
    """Distinct bucket: `маскара` (mascara transliteration) maps to
    mascara bucket, NOT mask. Without the `маскар` stem placed before
    `маск`, mascara collisions с face mask SKUs are theoretical FPs."""
    from ga_crawler.matcher.name_match import product_type_bucket
    assert product_type_bucket("маскара hypnose lancome") == "mascara"
    assert product_type_bucket("маска для лица la mer") == "mask"


def test_plural_mascara_form_maps_to_mascara_bucket() -> None:
    """`тушь` (singular) was the only mascara stem, missing plural
    `туши` and instrumental `тушью`. Stem shortened to `туш`."""
    from ga_crawler.matcher.name_match import product_type_bucket
    assert product_type_bucket("тушь для ресниц lancome") == "mascara"
    assert product_type_bucket("туши для ресниц estee lauder") == "mascara"


def test_candle_does_not_bucket_as_perfume() -> None:
    """`Ароматическая свеча Vanisia` had been bucketed as perfume via
    the old `аромат` stem (catch-too-broad for "ароматический…").
    Fix dropped `аромат` entirely (no fragrance SKUs use it as leading
    word in viled/GA inventory). New `свеч` stem catches candles."""
    from ga_crawler.matcher.name_match import product_type_bucket
    assert product_type_bucket("ароматическая свеча vanisia") == "candle"
    assert product_type_bucket("фарфоровая свеча vanisia 220 гр") == "candle"


def test_atomizer_is_not_perfume() -> None:
    """`Атомайзер Creed Pocket Leather` is an empty refillable bottle,
    not parfum. Bucket=atomizer ensures it never matches against GA
    perfume SKUs (which would produce nonsense price deltas)."""
    from ga_crawler.matcher.name_match import product_type_bucket
    assert product_type_bucket("атомаизер creed s pocket leather atomizers") == "atomizer"


def test_eyeliner_genitive_form_resolves() -> None:
    """`Водостойкий лайнер для глаз Lancome Idole Liner` viled
    normalizer emits `лаинер` (й → и). Stem `лаин` covers лайнер /
    лайнера / лайнером."""
    from ga_crawler.matcher.name_match import product_type_bucket
    assert product_type_bucket("лаинер для глаз lancome") == "liner"
    assert product_type_bucket("водостоикии лаинер для глаз lancome idole liner") == "liner"


def test_english_leading_name_resolves_cyrillic_product_type() -> None:
    """Run-21 v2 FP postmortem (commit 4569a4e+): viled
    «Teint Idole Ultra Wear пудра компактная для лица оттенок 04 Medium»
    matched GA «Рефил парфюмерной воды Lancome Idole» — same brand,
    common token "idole", and BOTH sides resolved to bucket=None
    because the old `_cyrillic_leading_words` stopped at the first
    non-Cyrillic word ("teint"), never reaching the actual product-type
    noun «пудра» that sits in the middle.

    Fix: scan all words, collect Cyrillic ones in order. Now "пудра"
    → powder bucket; GA's leading «рефил» strips to «парфюмерной»
    → perfume bucket; powder × perfume ⇒ veto fires."""
    assert not name_matches(
        viled_name_norm="teint idole ultra wear пудра компактная для лица оттенок 04 medium",
        goldapple_url="https://goldapple.kz/19000267094-idole",
        goldapple_name_norm="рефил парфюмернои воды lancome idole",
        brand_norm="lancome",
    )


def test_english_leading_cream_resolves_to_cream_bucket() -> None:
    """Companion regression: «Bobbi Brown Vitamin Enriched 50 мл крем»
    must produce bucket=cream (the «крем» word is reachable now). Same
    product on GA («крем для лица Vitamin Enriched») also = cream ⇒
    same bucket, veto does NOT fire (correct — let token logic decide)."""
    from ga_crawler.matcher.name_match import product_type_bucket
    assert product_type_bucket("bobbi brown vitamin enriched 50 мл крем") == "cream"
    assert product_type_bucket("teint idole ultra wear пудра компактная") == "powder"
