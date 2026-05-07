"""DATA-05 — `RunWriter.create / patch_stats / get_stats / fail` lifecycle.

Wave 1 / Plan 02-02 implements `src/ga_crawler/storage/sqlite.py::RunWriter`
satisfying RunWriterProtocol. patch_stats uses raw SQL `json_patch(stats, ?)`
for atomic merge (Pitfall 6) so concurrent viled+goldapple writers do not
clobber each other's namespace keys.

Source: 02-RESEARCH.md §Validation Architecture row 2; interfaces.py.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 1 not implemented yet — Plan 02-02")


def test_placeholder():
    """Placeholder. Plan 02-02 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-02"
