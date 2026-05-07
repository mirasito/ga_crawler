"""NORM-01 — `YamlBrandAlias` loader (BrandAliasProtocol implementation).

Wave 2 / Plan 02-03 implements `src/ga_crawler/alias/yaml_loader.py::YamlBrandAlias`.
Uses `brand_alias_yaml_fixture` (a tmp materialized copy of the test seed
brand-aliases-fixture.yaml) and asserts:
  - `lookup("estee_lauder")` returns ["Estée Lauder", "Estee Lauder", "Эсте Лаудер"]
  - `lookup("unknown_brand")` returns []
  - read-once-at-init (not hot-reload) per D-207

Source: 02-RESEARCH.md §Validation Architecture row 12; 02-CONTEXT.md D-216.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 2 not implemented yet — Plan 02-03")


def test_placeholder():
    """Placeholder. Plan 02-03 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-03"
