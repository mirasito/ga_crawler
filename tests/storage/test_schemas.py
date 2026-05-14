"""TH-06a + TH-06b — per-retailer Pydantic schemas (D-904 strict/relaxed split).

Goldapple beauty PDPs have volume on 25/30 = 83% of shape-table samples
(spike-findings-v1.1-brand-name-shapes/SKILL.md L39). Strict justified.

Viled Frederic Malle Contre-Jour and Creed Wild Vetiver legitimately lack
`Размер` attribute (08-01-SUMMARY Bug #3 + BUG-FINDINGS.md). Relaxed required.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ga_crawler.storage.schemas import GoldappleRawProduct, ViledRawProduct


_VALID_PAYLOAD: dict = {
    "sku_id": "19000440474",
    "url": "https://goldapple.kz/19000440474-stereotype-sago",
    "name": "SAĜO",
    "brand": "Stereotype",
    "current_price": 50000,
    "volume_raw": "75 мл",
}


def test_goldapple_strict_accepts_valid() -> None:
    p = GoldappleRawProduct.model_validate(_VALID_PAYLOAD)
    assert p.volume_raw == "75 мл"
    assert p.brand == "Stereotype"


def test_goldapple_strict_rejects_empty_volume() -> None:
    bad = dict(_VALID_PAYLOAD)
    bad["volume_raw"] = ""
    with pytest.raises(ValidationError) as exc:
        GoldappleRawProduct.model_validate(bad)
    assert any(err["type"] == "string_too_short" for err in exc.value.errors())


def test_goldapple_strict_rejects_missing_volume() -> None:
    bad = dict(_VALID_PAYLOAD)
    del bad["volume_raw"]
    with pytest.raises(ValidationError):
        GoldappleRawProduct.model_validate(bad)


def test_viled_relaxed_accepts_none_volume() -> None:
    """D-904 evidence: Frederic Malle Contre-Jour legitimately lacks `Размер`."""
    payload = dict(_VALID_PAYLOAD)
    payload["volume_raw"] = None
    p = ViledRawProduct.model_validate(payload)
    assert p.volume_raw is None


def test_viled_relaxed_accepts_missing_volume() -> None:
    payload = dict(_VALID_PAYLOAD)
    del payload["volume_raw"]
    p = ViledRawProduct.model_validate(payload)
    assert p.volume_raw is None


def test_both_reject_zero_price() -> None:
    for cls in (GoldappleRawProduct, ViledRawProduct):
        bad = dict(_VALID_PAYLOAD)
        bad["current_price"] = 0
        with pytest.raises(ValidationError):
            cls.model_validate(bad)


def test_both_reject_negative_price() -> None:
    for cls in (GoldappleRawProduct, ViledRawProduct):
        bad = dict(_VALID_PAYLOAD)
        bad["current_price"] = -1
        with pytest.raises(ValidationError):
            cls.model_validate(bad)


def test_both_reject_empty_brand() -> None:
    for cls in (GoldappleRawProduct, ViledRawProduct):
        bad = dict(_VALID_PAYLOAD)
        bad["brand"] = ""
        with pytest.raises(ValidationError):
            cls.model_validate(bad)


def test_both_reject_empty_name() -> None:
    for cls in (GoldappleRawProduct, ViledRawProduct):
        bad = dict(_VALID_PAYLOAD)
        bad["name"] = ""
        with pytest.raises(ValidationError):
            cls.model_validate(bad)


def test_both_reject_empty_sku_id() -> None:
    for cls in (GoldappleRawProduct, ViledRawProduct):
        bad = dict(_VALID_PAYLOAD)
        bad["sku_id"] = ""
        with pytest.raises(ValidationError):
            cls.model_validate(bad)


def test_both_reject_empty_url() -> None:
    for cls in (GoldappleRawProduct, ViledRawProduct):
        bad = dict(_VALID_PAYLOAD)
        bad["url"] = ""
        with pytest.raises(ValidationError):
            cls.model_validate(bad)


def test_extra_keys_ignored() -> None:
    """ConfigDict(extra='ignore') lets unknown keys pass — writer pre-filters anyway."""
    payload = dict(_VALID_PAYLOAD)
    payload["completely_unknown_field"] = "ignored_value"
    p = GoldappleRawProduct.model_validate(payload)
    assert not hasattr(p, "completely_unknown_field")
