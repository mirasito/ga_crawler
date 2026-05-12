"""Wave 0 stub — structural canary: no Phase 5 imports in delivery/.

Plan 06-05 (Wave 4) replaces this stub. Greps src/ga_crawler/delivery/
for 'summary_builder' and 'excel_builder' imports → expects 0 matches
(D-514 source-of-truth invariant; delivery is thin wrapper, NEVER
re-generates summary or xlsx).
"""
import pytest


@pytest.mark.skip(reason="Plan 06-01 stub — implemented in Plan 06-05 Wave 4")
def test_placeholder_implemented_in_plan_06_05():
    pass
