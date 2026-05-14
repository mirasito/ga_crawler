"""TH-03 helper: confirm pytest_addoption('--refresh-live') is wired."""
from __future__ import annotations

import subprocess
import sys


def test_refresh_live_flag_accepted() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--refresh-live", "--collect-only", "-q",
         "tests/test_snapshot_extension.py"],
        capture_output=True, text=True, timeout=60,
    )
    # exit 0 (collection ok) or 5 (no tests selected) both fine; what we need:
    # NOT exit 4 (usage error) and stderr must NOT contain "unrecognized argument"
    combined = (result.stdout + result.stderr).lower()
    assert "unrecognized arguments" not in combined
    assert "unknown option" not in combined
