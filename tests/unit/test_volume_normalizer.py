"""NORM-03 + NORM-04 + Open Q4 verification driven by volume-corpus.yaml.

Wave 2 / Plan 02-03 ships `src/ga_crawler/normalizers/volume.py`:
  - regex tokenize → unit-table lookup
    (мл/ml/милиlitr→ml, oz/унция→oz, г/g→g, шт/pcs→pcs, л/l→l, кг/kg→kg)
  - multipack regex (`(\\d+)\\s*[xх×]\\s*(\\d+)`, `Set of (\\d+)`,
    `(\\d+)\\s*шт`, `набор`/`комплект`/`kit`)
  - Open Q4: detect_multipack INDEPENDENT of parse_volume — multipack flag
    persists even when per-unit volume is unparseable.

Drives via `volume_corpus_cases` fixture (parametrize over 18 cases from
tests/fixtures/normalize/volume-corpus.yaml).

Source: 02-RESEARCH.md §Validation Architecture rows 8-9 + Pattern 6;
02-CONTEXT.md D-215.
"""
from decimal import Decimal

from ga_crawler.alias.yaml_loader import YamlBrandAlias
from ga_crawler.interfaces import NormalizerProtocol
from ga_crawler.normalizers.facade import Normalizer
from ga_crawler.normalizers.volume import (
    UNIT_TABLE,
    Volume,
    detect_multipack,
    parse_volume,
)


def _to_volume_or_none(spec):
    if spec is None:
        return None
    return Volume(amount=Decimal(spec[0]), unit=spec[1], count=int(spec[2]))


def test_corpus_parametrized(volume_corpus_cases):
    """ROADMAP success: documented test suite of real strings — all 18 corpus cases."""
    for case in volume_corpus_cases:
        actual = parse_volume(case["input"])
        expected = _to_volume_or_none(case["expected_volume"])
        assert actual == expected, (
            f"parse_volume({case['input']!r}): got {actual!r}, expected {expected!r}"
        )
        assert detect_multipack(case["input"]) == case["expected_multipack"], (
            f"detect_multipack({case['input']!r}): got {detect_multipack(case['input'])}, "
            f"expected {case['expected_multipack']}"
        )


def test_unit_table_canonical_units():
    canonical = set(UNIT_TABLE.values())
    assert canonical <= {"ml", "g", "oz", "l", "pcs", "kg", "fl"}


def test_decimal_with_comma():
    """RESEARCH Pattern 6: comma-decimal (`1,5 л`) normalizes to dot-decimal Decimal."""
    v = parse_volume("1,5 л")
    assert v == Volume(Decimal("1.5"), "l", 1)


def test_multipack_n_x_amount():
    """`3 x 50 мл` → Volume(50, ml, 3)."""
    v = parse_volume("3 x 50 мл")
    assert v == Volume(Decimal("50"), "ml", 3)
    assert detect_multipack("3 x 50 мл") is True


def test_keyword_multipack_no_amount():
    """Open Q4: parse_volume returns None but detect_multipack returns True."""
    assert parse_volume("набор пробников") is None
    assert detect_multipack("набор пробников") is True


def test_facade_volume_returns_3tuple(brand_alias_yaml_fixture):
    """NormalizerProtocol shape: Optional[tuple[Decimal, str, int]]."""
    n = Normalizer(YamlBrandAlias(brand_alias_yaml_fixture))
    result = n.volume("30 мл")
    assert result is not None
    amount, unit, count = result
    assert amount == Decimal("30")
    assert unit == "ml"
    assert count == 1


def test_facade_volume_none_for_unparseable(brand_alias_yaml_fixture):
    n = Normalizer(YamlBrandAlias(brand_alias_yaml_fixture))
    assert n.volume("Кружевное боди") is None


def test_facade_satisfies_protocol(brand_alias_yaml_fixture):
    """interfaces.py NormalizerProtocol is @runtime_checkable."""
    n = Normalizer(YamlBrandAlias(brand_alias_yaml_fixture))
    assert isinstance(n, NormalizerProtocol)


def test_facade_brand_uses_alias(brand_alias_yaml_fixture):
    n = Normalizer(YamlBrandAlias(brand_alias_yaml_fixture))
    assert n.brand("Estée Lauder") == "estee_lauder"
    assert n.brand("Эсте Лаудер") == "estee_lauder"
    assert n.brand("Tom Ford") == "tom-ford"  # not in alias → slug-form fallthrough


def test_facade_name_passes_through(brand_alias_yaml_fixture):
    n = Normalizer(YamlBrandAlias(brand_alias_yaml_fixture))
    assert n.name("Crème Brûlée") == "creme brulee"


def test_volume_dataclass_frozen():
    """Volume is hashable (frozen dataclass) → can live in dict/set keys."""
    v1 = Volume(Decimal("30"), "ml", 1)
    v2 = Volume(Decimal("30"), "ml", 1)
    assert v1 == v2
    assert hash(v1) == hash(v2)
