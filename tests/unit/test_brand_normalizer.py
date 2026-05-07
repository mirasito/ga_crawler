"""NORM-02 — brand normalizer (lowercase + accent-strip + alias resolution).

Wave 2 / Plan 02-03 ships `src/ga_crawler/normalizers/brand.py`. Each input
flows: `_normalize_punct(raw)` (slug-form) → alias_lookup.canonical_for(slug)
→ canonical brand_norm if known, else fall through to slug-form.

Drives via `brand_corpus_cases` fixture (parametrize over ≥10 cases including
Cyrillic Эсте Лаудер ↔ Latin Estée Lauder ↔ canonical estee_lauder).

Source: 02-RESEARCH.md §Validation Architecture row 10; §Pattern 7;
02-CONTEXT.md D-205.
"""
import inspect

from ga_crawler.alias.yaml_loader import YamlBrandAlias
from ga_crawler.normalizers import brand as brand_module
from ga_crawler.normalizers.brand import normalize_brand


def _alias_factory(brand_alias_yaml_fixture):
    return YamlBrandAlias(brand_alias_yaml_fixture)


def test_corpus_resolution(brand_corpus_cases, brand_alias_yaml_fixture):
    """Drives the full ≥10-case corpus from tests/fixtures/normalize/brand-corpus.yaml."""
    alias = _alias_factory(brand_alias_yaml_fixture)
    for case in brand_corpus_cases:
        actual = normalize_brand(case["raw"], alias)
        assert actual == case["expected_brand_norm"], (
            f"{case['raw']!r} → {actual!r}, expected {case['expected_brand_norm']!r}"
        )


def test_apostrophe_strip_before_hyphen(brand_alias_yaml_fixture):
    """STATE.md plan 03-02 lesson: `L'Oréal Paris → loreal-paris` not `l-oreal-paris`."""
    alias = _alias_factory(brand_alias_yaml_fixture)
    assert normalize_brand("L'Oréal Paris", alias) == "loreal-paris"


def test_cyrillic_to_canonical(brand_alias_yaml_fixture):
    """NORM-01: Cyrillic alias resolves to canonical (D-206)."""
    alias = _alias_factory(brand_alias_yaml_fixture)
    assert normalize_brand("Эсте Лаудер", alias) == "estee_lauder"
    assert normalize_brand("Живанши", alias) == "givenchy"
    assert normalize_brand("Шанель", alias) == "chanel"


def test_uses_imported_normalize_punct():
    """REUSE: brand.py must IMPORT _normalize_punct, not duplicate it."""
    src = inspect.getsource(brand_module)
    assert "from ga_crawler.enumeration.slug import _normalize_punct" in src
    # No duplicated definition: brand.py must NOT define its own _normalize_punct
    assert "def _normalize_punct" not in src


def test_empty_brand_returns_empty(brand_alias_yaml_fixture):
    alias = _alias_factory(brand_alias_yaml_fixture)
    assert normalize_brand("", alias) == ""


def test_unknown_brand_falls_through_to_slug(brand_alias_yaml_fixture):
    """No alias entry → return _normalize_punct(raw)."""
    alias = _alias_factory(brand_alias_yaml_fixture)
    assert normalize_brand("Tom Ford", alias) == "tom-ford"
    assert normalize_brand("Frédéric Malle", alias) == "frederic-malle"
