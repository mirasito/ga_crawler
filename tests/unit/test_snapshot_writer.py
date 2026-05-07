"""DATA-03 — `SnapshotWriter.append` append-only invariant.

Wave 1 / Plan 02-02 implements `SnapshotWriter` over the Snapshot SQLModel
table. Asserts:
  - INSERT-only path; UPDATEs raise / are absent
  - composite UNIQUE (run_id, retailer, sku_id) prevents intra-run duplicates
  - returns count of rows inserted (per SnapshotWriterProtocol)

Source: 02-RESEARCH.md §Validation Architecture row 3; 02-CONTEXT.md D-213.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 1 not implemented yet — Plan 02-02")


def test_placeholder():
    """Placeholder. Plan 02-02 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-02"
