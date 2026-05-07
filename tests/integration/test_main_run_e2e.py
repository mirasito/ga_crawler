"""Full weekly run: viled phase → goldapple phase → both retailers' snapshots in one DB.

Wave 5 / Plan 02-06 wires `runners/main_run.py` composing:
  1. Viled phase (curl_cffi Tier 0 — Plan 02-04..05)
  2. Goldapple phase (Camoufox Tier 2 — already shipped Phase 3 Wave 5)

Asserts:
  - single `runs` row, both viled.* AND goldapple.* keys merged into stats
    (Pitfall 6: atomic patch_stats no clobber)
  - `snapshots` table has rows for both retailers, both visible via
    v_current_snapshots after run.status='success'
  - failure of either phase yields run.status='failed' but other phase's
    snapshots still persist (audit trail)

Source: 02-RESEARCH.md §Validation Architecture row 23.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 5 not implemented yet — Plan 02-06")


def test_placeholder():
    """Placeholder. Plan 02-06 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-06"
