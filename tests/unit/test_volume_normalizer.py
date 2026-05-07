"""NORM-03, NORM-04 — volume parser + multipack-flag detection.

Wave 2 / Plan 02-03 implements `src/ga_crawler/normalizers/volume.py`:
regex tokenize → unit-table lookup (мл/ml/мilliliter→ml, oz/унция→oz, г/g→g,
шт/pcs→pcs) → multipack regex (`(\\d+)\\s*[xх×]\\s*(\\d+)`, `Set of (\\d+)`,
`(\\d+)\\s*шт`).

Drives via `volume_corpus_cases` fixture (parametrize over ≥15 cases from
tests/fixtures/normalize/volume-corpus.yaml).

Source: 02-RESEARCH.md §Validation Architecture rows 8-9 + Pattern 6;
02-CONTEXT.md D-215.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 2 not implemented yet — Plan 02-03")


def test_placeholder():
    """Placeholder. Plan 02-03 flips this from skip to GREEN, parametrizing
    over the volume_corpus_cases fixture."""
    assert False, "implement in Plan 02-03"
