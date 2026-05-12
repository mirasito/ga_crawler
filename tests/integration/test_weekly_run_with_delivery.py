"""Wave 0 stub — E2E tests: main_run.run_weekly amended with delivery step.

Plan 06-05 (Wave 4) replaces this stub. Tests SC#1 (business route happy path)
+ SC#2 (deliberate-failure → ops-only route) end-to-end through run_weekly.
Uses mock Bot; real on-disk SQLite; verifies MainRunResult D-616 fields
(delivery_status, delivery_route) populated correctly.
"""
import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skip(reason="Plan 06-01 stub — implemented in Plan 06-05 Wave 4")
def test_placeholder_implemented_in_plan_06_05():
    pass
