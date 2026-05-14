"""TH-06c — SqliteSnapshotWriter.append integration with Pydantic write-boundary.

D-903: per-row schema_cls.model_validate(payload) inside the existing
append() loop. ValidationError -> row SKIPPED, reason captured into
writer._last_rejected_reasons (truncated at 50; no `input` key per
RESEARCH §7.2 PII landmine).

Cascade position: structural drift caught here BEFORE Phase 8 PARSE-FIX-04
null-rate gate (content drift).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest
from sqlmodel import Session, select

from ga_crawler.storage.sqlite import (
    Snapshot,
    SqliteRunWriter,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)


def _setup(tmp_path: Path):
    db = tmp_path / "test.db"
    init_db(db)
    return make_engine(db)


def _row(
    sku_id: str,
    name: str = "X",
    brand: str = "TestBrand",
    price: int = 1000,
    volume_raw: Optional[str] = "75 мл",
    **extras,
) -> dict:
    return {
        "sku_id": sku_id,
        "url": f"https://example.com/{sku_id}",
        "name": name,
        "brand": brand,
        "brand_norm": brand.lower(),
        "name_norm": name.lower(),
        "current_price": price,
        "volume_raw": volume_raw,
        "currency": "KZT",
        "stock_state": "IN_STOCK",
        **extras,
    }


def _row_no_volume_key(sku_id: str, **kw) -> dict:
    r = _row(sku_id, **kw)
    del r["volume_raw"]
    return r


def test_writer_validates_goldapple_strictly(tmp_path: Path) -> None:
    """3 products: valid, empty-volume, missing-volume -> 1 INSERTed; 2 rejected."""
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    products = [
        _row("100", name="Valid", volume_raw="75 мл"),
        _row("200", name="Empty", volume_raw=""),       # rejected
        _row_no_volume_key("300", name="Missing"),       # rejected
    ]
    n = writer.append(run_id=rid, retailer="goldapple", products=products)
    assert n == 1
    assert len(writer._last_rejected_reasons) == 2
    assert {r["sku_id"] for r in writer._last_rejected_reasons} == {"200", "300"}
    with Session(engine) as s:
        rows = list(s.exec(select(Snapshot)))
    assert len(rows) == 1
    assert rows[0].sku_id == "100"


def test_writer_relaxes_viled_volume_none(tmp_path: Path) -> None:
    """D-904 viled-relaxed: volume_raw=None must NOT reject."""
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    products = [_row("v-contre-jour", name="Contre-Jour", volume_raw=None)]
    n = writer.append(run_id=rid, retailer="viled", products=products)
    assert n == 1
    assert writer._last_rejected_reasons == []


def test_writer_no_input_key_in_rejected_reasons(tmp_path: Path) -> None:
    """RESEARCH §7.2: e.errors() default emits 'input' (PII surface).
    Projection must yield ONLY {'loc', 'type'} per error."""
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    bad = _row("sensitive", name="potentially-secret-data", volume_raw="")
    writer.append(run_id=rid, retailer="goldapple", products=[bad])
    assert len(writer._last_rejected_reasons) == 1
    reason = writer._last_rejected_reasons[0]
    assert reason["sku_id"] == "sensitive"
    assert isinstance(reason["errors"], list)
    for err in reason["errors"]:
        assert "input" not in err, f"PII landmine: 'input' leaked into rejected_reasons: {err}"
        assert set(err.keys()) == {"loc", "type"}


def test_writer_truncates_at_50_rejected(tmp_path: Path) -> None:
    """Memory bound: _last_rejected_reasons capped at 50 entries (RESEARCH §4.2)."""
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    # 100 invalid rows (all volume_raw="")
    products = [_row(str(i), name=f"S{i}", volume_raw="") for i in range(100)]
    writer.append(run_id=rid, retailer="goldapple", products=products)
    assert len(writer._last_rejected_reasons) == 50


def test_writer_unknown_retailer_skips_validation(tmp_path: Path) -> None:
    """Backward compat: unknown retailer = no schema_cls => no validation.
    Phase 2/3 don't break."""
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    # Note: schema would reject volume_raw="", but retailer="test" has no
    # entry in _SCHEMA_BY_RETAILER, so validation skipped.
    products = [_row("999", volume_raw="")]
    n = writer.append(run_id=rid, retailer="test", products=products)
    assert n == 1
    assert writer._last_rejected_reasons == []


def test_writer_baseline_appends_valid_rows(tmp_path: Path) -> None:
    """Regression guard: pre-existing valid-row INSERT still works post-wire-up."""
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    products = [
        _row("100", name="A", volume_raw="50 мл"),
        _row("200", name="B", volume_raw="100 мл"),
    ]
    n = writer.append(run_id=rid, retailer="goldapple", products=products)
    assert n == 2
    with Session(engine) as s:
        rows = list(s.exec(select(Snapshot)))
    assert len(rows) == 2
