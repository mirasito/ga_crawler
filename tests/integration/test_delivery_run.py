"""Wave 0 stub — integration tests for runners/delivery_run.py::run_delivery_phase.

Plan 06-04 (Wave 3) replaces this stub. Tests against real on-disk SQLite
(synthetic_delivered_run fixture) + mock aiogram Bot. Covers all 6 D-606
enum transitions, D-604 gate composition, D-605 invariant (xlsx persists
on Telegram failure), Pitfall 6 single patch_stats call.
"""
import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skip(reason="Plan 06-01 stub — implemented in Plan 06-04 Wave 3")
def test_placeholder_implemented_in_plan_06_04():
    pass
