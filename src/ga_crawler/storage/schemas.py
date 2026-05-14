"""Pydantic raw-product schemas — write-boundary validation at SqliteSnapshotWriter.append.

Phase 9 TEST-HARNESS-06 (D-903 + D-904):
  - GoldappleRawProduct (STRICT): volume_raw REQUIRED (NonEmptyStr).
    Evidence: goldapple beauty PDPs carry [...] ОБЪЁМ / МЛ block on 25/30
    spike-sampled pages (spike-findings-v1.1-brand-name-shapes/SKILL.md L39).
  - ViledRawProduct (RELAXED): volume_raw Optional[NonEmptyStr]=None.
    Evidence: Frederic Malle Contre-Jour, Creed Wild Vetiver legitimately
    lack `Размер` attribute (08-01-SUMMARY Bug #3 + BUG-FINDINGS.md).

Cascade position: this is *structural* drift detection (parser emits wrong
shape). Phase 8 PARSE-FIX-04 null-rate gate catches *content* drift (all
SKUs have NULL volume). Schema gate runs FIRST (structural before content).

Source anchors: 09-CONTEXT.md D-903/D-904; 09-RESEARCH.md §4 + §6.4.
"""

from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class RawProductBase(BaseModel):
    """Shared fields between goldapple/viled raw product dicts (post-dispatcher).

    ConfigDict(extra='ignore'): SqliteSnapshotWriter.append pre-filters payload
    via valid_fields set (sqlite.py:183), so anything Pydantic sees is already
    Snapshot-known. RESEARCH §7.4 — 'ignore' is safe given pre-filter contract.
    """

    model_config = ConfigDict(extra="ignore")

    sku_id: NonEmptyStr
    url: NonEmptyStr
    name: NonEmptyStr
    brand: NonEmptyStr
    current_price: int = Field(gt=0)  # KZT integer; gt=0 rejects 0/negative


class GoldappleRawProduct(RawProductBase):
    """STRICT: goldapple beauty PDPs always carry volume per shape-table.
    Null/empty volume_raw at append-time => parser drift, reject row + count
    toward 5% gate threshold (D-903)."""

    volume_raw: NonEmptyStr


class ViledRawProduct(RawProductBase):
    """RELAXED: Contre-Jour / Wild Vetiver legitimately lack `Размер` attr
    per 08-01-SUMMARY Bug #3 + BUG-FINDINGS.md. volume_raw=None must NOT
    false-positive reject (would burn ops with alert noise)."""

    volume_raw: Optional[NonEmptyStr] = None
