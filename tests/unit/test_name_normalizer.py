"""NORM-05 — product-name normalizer (lowercase + punctuation strip + collapse spaces).

Wave 2 / Plan 02-03 ships `src/ga_crawler/normalizers/name.py`.

Pipeline: lowercase → NFKD-decompose → strip combining marks → strip non-word
non-space chars → collapse whitespace. Distinct from `_normalize_punct`
(slug.py) which produces hyphenated form; name_norm preserves spaces for
word-level matching.

Source: 02-RESEARCH.md §Validation Architecture row 11; §Pattern 7.
"""
from ga_crawler.normalizers.name import normalize_name


def test_lowercase_strip_collapse():
    assert normalize_name("Eau de Parfum  -  Givenchy!!") == "eau de parfum givenchy"


def test_nfkd_decompose():
    assert normalize_name("Crème Brûlée") == "creme brulee"


def test_empty_input():
    assert normalize_name("") == ""


def test_collapses_internal_whitespace():
    assert normalize_name("a   b\tc\nd") == "a b c d"


def test_preserves_cyrillic():
    # NFKD doesn't transliterate Cyrillic; just lower + collapse
    assert normalize_name("Кружевное Боди") == "кружевное боди"


def test_strips_brackets_and_quotes():
    assert normalize_name("Eau «de» (parfum)") == "eau de parfum"
