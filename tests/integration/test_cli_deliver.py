"""Wave 0 stub — subprocess CLI tests for `python -m ga_crawler deliver-run`.

Plan 06-04 (Wave 3) replaces this stub. Tests --run-id N + --force + --dry-run
+ idempotency dispatch (D-608) + ENV-missing exit codes (3 for no_credentials,
2 for undelivered, 0 for delivered).
"""
import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skip(reason="Plan 06-01 stub — implemented in Plan 06-04 Wave 3")
def test_placeholder_implemented_in_plan_06_04():
    pass
