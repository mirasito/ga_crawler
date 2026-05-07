"""NORM-01 — `YamlBrandAlias` loader (BrandAliasProtocol implementation).

Wave 2 / Plan 02-03 ships `src/ga_crawler/alias/yaml_loader.py::YamlBrandAlias`.

Asserts:
  - `lookup("estee_lauder")` returns ["Estée Lauder", "Estee Lauder", "Эсте Лаудер"]
  - `lookup("unknown_brand")` returns ["unknown_brand"] (self-seed default per RESEARCH Pattern 8)
  - `canonical_for(_normalize_punct("Эсте Лаудер"))` returns "estee_lauder" (D-205, D-206)
  - missing YAML → empty loader (no crash)
  - read-once at __init__ (D-207)

Source: 02-RESEARCH.md §Validation Architecture row 12; 02-CONTEXT.md D-205, D-207, D-216.
"""
from pathlib import Path

import pytest

from ga_crawler.alias.yaml_loader import YamlBrandAlias
from ga_crawler.enumeration.slug import _normalize_punct


def test_lookup_returns_aliases(brand_alias_yaml_fixture):
    alias = YamlBrandAlias(brand_alias_yaml_fixture)
    aliases = alias.lookup("estee_lauder")
    assert "Estée Lauder" in aliases
    assert "Estee Lauder" in aliases
    assert "Эсте Лаудер" in aliases


def test_lookup_unknown_returns_self_seed(brand_alias_yaml_fixture):
    alias = YamlBrandAlias(brand_alias_yaml_fixture)
    assert alias.lookup("nonexistent_brand") == ["nonexistent_brand"]


def test_canonical_for_round_trip(brand_alias_yaml_fixture):
    alias = YamlBrandAlias(brand_alias_yaml_fixture)
    # Cyrillic alias → normalize via _normalize_punct → reverse-lookup → estee_lauder
    cyrillic_norm = _normalize_punct("Эсте Лаудер")
    assert alias.canonical_for(cyrillic_norm) == "estee_lauder"
    # Latin variant
    latin_norm = _normalize_punct("Estée Lauder")
    assert alias.canonical_for(latin_norm) == "estee_lauder"
    # Plain ASCII variant
    ascii_norm = _normalize_punct("Estee Lauder")
    assert alias.canonical_for(ascii_norm) == "estee_lauder"


def test_canonical_for_unknown_returns_none(brand_alias_yaml_fixture):
    alias = YamlBrandAlias(brand_alias_yaml_fixture)
    assert alias.canonical_for("totally-unknown") is None


def test_missing_yaml_yields_empty_loader(tmp_path):
    alias = YamlBrandAlias(tmp_path / "does-not-exist.yaml")
    assert alias.lookup("estee_lauder") == ["estee_lauder"]
    assert alias.canonical_for("estee-lauder") is None


def test_read_once_at_init(tmp_path):
    """D-207: read-once. File mutation post-init must NOT change behavior."""
    p = tmp_path / "aliases.yaml"
    p.write_text("brand_a:\n  - 'Brand A'\n", encoding="utf-8")
    alias = YamlBrandAlias(p)
    assert alias.lookup("brand_a") == ["Brand A"]
    # mutate file post-init
    p.write_text("brand_a:\n  - 'Mutated'\n", encoding="utf-8")
    # Lookup is cached in-memory — must not reflect disk change
    assert alias.lookup("brand_a") == ["Brand A"]


def test_givenchy_cyrillic_alias_round_trip(brand_alias_yaml_fixture):
    """Живанши (Cyrillic) → givenchy canonical, per D-206."""
    alias = YamlBrandAlias(brand_alias_yaml_fixture)
    assert alias.canonical_for(_normalize_punct("Живанши")) == "givenchy"
    assert alias.canonical_for(_normalize_punct("Givenchy")) == "givenchy"
