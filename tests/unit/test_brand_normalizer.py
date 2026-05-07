"""NORM-02 — brand normalizer (lowercase + accent-strip + alias resolution).

Wave 2 / Plan 02-03 implements `src/ga_crawler/normalizers/brand.py`. Each
input flows: lowercase → unicodedata.normalize('NFKD') accent-strip → slugify
→ YamlBrandAlias.lookup() reverse-resolution (Cyrillic alias → canonical).

Drives via `brand_corpus_cases` fixture (parametrize over ≥10 cases including
Cyrillic Эсте Лаудер ↔ Latin Estée Lauder ↔ ASCII estee_lauder).

Source: 02-RESEARCH.md §Validation Architecture row 10; 02-CONTEXT.md D-205.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 2 not implemented yet — Plan 02-03")


def test_placeholder():
    """Placeholder. Plan 02-03 flips this from skip to GREEN, parametrizing
    over the brand_corpus_cases fixture."""
    assert False, "implement in Plan 02-03"
