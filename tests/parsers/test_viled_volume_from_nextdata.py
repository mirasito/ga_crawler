"""viled _extract_volume_from_nextdata helper tests — PARSE-FIX-03.

RED → GREEN per Plan 08-04 strict TDD. Drives both the new helper directly
and the full parse_pdp roundtrip against all 3 existing + 1 live fixture.

Source: 08-04-PLAN.md (Wave 1, Plan 08-04); 08-RESEARCH.md §"viled NextData
attributes"; 08-PATTERNS.md §"tests/parsers/test_viled_volume_from_nextdata.py".
"""

from __future__ import annotations

from ga_crawler.parsers.viled_nextdata import (
    _extract_volume_from_nextdata,  # NEW helper (Plan 08-04 GREEN step)
    ViledRawProduct,
    parse_pdp,
)


# ---------- Direct helper unit tests — synthetic dicts ----------


def test_extract_volume_from_nextdata_beauty_50ml() -> None:
    """Canonical beauty case: Размер attr carries '50 мл' verbatim."""
    a0 = {
        "price": 12345,
        "attributes": [
            {"name": "Размер", "value": "50 мл"},
        ],
    }
    assert _extract_volume_from_nextdata(a0) == "50 мл"


def test_extract_volume_from_nextdata_clothing_size() -> None:
    """Clothing 'S' is returned verbatim; NORM-03 disambiguates downstream."""
    a0 = {"attributes": [{"name": "Размер", "value": "S"}]}
    assert _extract_volume_from_nextdata(a0) == "S"


def test_extract_volume_from_nextdata_no_size_attr() -> None:
    """No 'Размер' / 'Объём' entry → None (legitimate-absent per D-814)."""
    a0 = {"attributes": [{"name": "Цвет", "value": "Красный"}]}
    assert _extract_volume_from_nextdata(a0) is None


def test_extract_volume_from_nextdata_cyrillic_obyom() -> None:
    """Cyrillic 'Объём' (with Ё) variant — Russian word for 'volume'."""
    a0 = {"attributes": [{"name": "Объём", "value": "100мл"}]}
    assert _extract_volume_from_nextdata(a0) == "100мл"


def test_extract_volume_from_nextdata_cyrillic_obyem_no_yo() -> None:
    """Cyrillic 'Объем' (without Ё, common alternate spelling) variant."""
    a0 = {"attributes": [{"name": "Объем", "value": "75 мл"}]}
    assert _extract_volume_from_nextdata(a0) == "75 мл"


def test_extract_volume_from_nextdata_empty_descriptive_list() -> None:
    """Empty attributes list → None (no entries to match)."""
    a0 = {"attributes": []}
    assert _extract_volume_from_nextdata(a0) is None


def test_extract_volume_from_nextdata_missing_attributes_key() -> None:
    """No 'attributes' key on a0 → None (guarded by isinstance check)."""
    a0 = {"price": 100}
    assert _extract_volume_from_nextdata(a0) is None


def test_extract_volume_from_nextdata_malformed_entry_skipped() -> None:
    """Non-dict entries are silently skipped (T-08-13 mitigation)."""
    a0 = {
        "attributes": [
            "not-a-dict",
            None,
            {"name": "Размер", "value": "30 мл"},
        ]
    }
    assert _extract_volume_from_nextdata(a0) == "30 мл"


def test_extract_volume_from_nextdata_value_whitespace_stripped() -> None:
    """Surrounding whitespace stripped from extracted value."""
    a0 = {"attributes": [{"name": "Размер", "value": "  50 мл  "}]}
    assert _extract_volume_from_nextdata(a0) == "50 мл"


def test_extract_volume_from_nextdata_empty_value_returns_none() -> None:
    """Empty-string value (whitespace-only) treated as absent → None."""
    a0 = {"attributes": [{"name": "Размер", "value": "   "}]}
    assert _extract_volume_from_nextdata(a0) is None


# ---------- Round-trip tests via existing fixtures ----------


def test_round_trip_discounted_beauty_yields_50ml(viled_pdp_discounted_html: str) -> None:
    """Frederic Malle 50 мл beauty fixture: Размер attr emits '50 мл' verbatim."""
    p = parse_pdp(viled_pdp_discounted_html, "https://viled.kz/item/367251")
    assert p is not None
    assert isinstance(p, ViledRawProduct)
    assert p.raw_volume_text is not None
    assert "50" in p.raw_volume_text
    assert "мл" in p.raw_volume_text.lower()
    # No longer the full name string — discrete volume read from Размер.
    assert p.raw_volume_text != p.name


def test_round_trip_clothing_yields_size_string(viled_pdp_html: str) -> None:
    """Clothing fixture (item/407682) yields 'S' (or whatever clothing-size string);
    NORM-03 downstream maps to volume_norm=None per Pitfall 4 disambiguation."""
    p = parse_pdp(viled_pdp_html, "https://viled.kz/item/407682")
    assert p is not None
    # raw_volume_text is now extracted from Размер attr, NOT name — verify NOT == name.
    assert p.raw_volume_text != p.name
    # And it's some non-empty short string (clothing-size shape).
    assert p.raw_volume_text is not None
    assert len(p.raw_volume_text) <= 10  # clothing sizes are short ('S', 'M', '38', etc)


def test_round_trip_multipack_yields_multi_volume(viled_pdp_multipack_html: str) -> None:
    """Multipack beauty SKU: Размер attr carries something like '200мл + 200мл + 250мл'.

    Either a '+' separator OR multiple 'мл' tokens proves multi-volume extraction
    (rather than the previous fallback to full name string).
    """
    p = parse_pdp(viled_pdp_multipack_html, "https://viled.kz/item/multipack")
    assert p is not None
    assert p.raw_volume_text is not None
    assert "+" in p.raw_volume_text or p.raw_volume_text.lower().count("мл") >= 2, (
        f"multipack raw_volume_text {p.raw_volume_text!r} does not look multi-volume"
    )


def test_round_trip_contre_jour_yields_none_or_name(
    viled_pdp_html_live_contre_jour: str,
) -> None:
    """Frederic Malle / Contre-Jour live PDP (Bug #3 evidence): 'Размер' attr may be
    absent → fallback to name (D-814 legitimate-None case per CONTEXT.md).

    Acceptable outcomes:
      (a) raw_volume_text is None — pure fallback would never produce None per
          current code (always `or name`), so this branch is theoretical;
      (b) raw_volume_text == p.name — fallback path engaged (Размер absent);
      (c) raw_volume_text is some discrete value extracted from Размер.

    NORM-03 returns volume_norm=None in (a) and (b) — both consistent with D-814.
    """
    p = parse_pdp(viled_pdp_html_live_contre_jour, "https://viled.kz/item/408872")
    assert p is not None
    # Either fallback path (raw_volume_text == name) OR discrete extraction —
    # both are acceptable; the spike SUGGESTS attr is present but value may be None.
    # Document the outcome via assertion: the helper either extracted something
    # short (volume-shape) OR fell back to the full name string.
    assert p.raw_volume_text is not None  # 'or name' fallback guarantees non-None
    # If extracted (not fallback), should be a short volume-shape string.
    if p.raw_volume_text != p.name:
        assert len(p.raw_volume_text) < len(p.name), (
            f"extracted raw_volume_text {p.raw_volume_text!r} should be shorter "
            f"than full name {p.name!r}"
        )
