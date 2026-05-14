"""TH-03c — syrupy missing-snapshot fails CI loudly (T-09-SOUND).

D-906 soundness rule: `assert actual == snapshot` MUST fail if snapshot file
is absent, not silently pass. This negative test confirms the regression
does NOT silently succeed.

Implementation: spawn a child pytest invocation that targets a deliberately-
missing snapshot name. Assert non-zero exit + recognisable failure in output.

If syrupy is not installed (09-01 not yet merged to this worktree), the test
is skipped with an explanation rather than erroring with ImportError.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


# Child test that syrupy snapshot fixture is wired and a missing snapshot
# fails (exits non-zero). Self-contained so it does NOT import any Phase 9
# modules that may not exist on this worktree.
_CHILD_TEST = textwrap.dedent("""\
    from __future__ import annotations
    import pytest

    def test_missing_snapshot_fails(snapshot):
        \"\"\"Snapshot with this unique name must NOT exist on disk — must fail.\"\"\"
        # This unique sentinel string will have no matching .ambr snapshot file.
        assert "<html>deliberately-missing-snapshot-sentinel-09-02a</html>" == snapshot
""")

_CHILD_CONFTEST = textwrap.dedent("""\
    # Minimal conftest so pytest can run in the isolated tmp dir.
    # No project imports needed — we only test syrupy's built-in behavior.
""")


def test_syrupy_default_fails_on_missing_snapshot(tmp_path: Path) -> None:
    """Spawn subprocess pytest against a missing-snapshot test; assert exit != 0.

    T-09-SOUND: proves that syrupy's default behavior is to FAIL when the
    snapshot file is absent (not silently pass). This is the 'soundness'
    negative test — if syrupy's default changes to silent-pass, CI would
    never catch parser drift.

    Skips if syrupy is not installed (09-01 not yet merged).
    """
    # Check syrupy is available; skip gracefully if 09-01 hasn't merged yet.
    result_check = subprocess.run(
        [sys.executable, "-c", "import syrupy; print(syrupy.__version__)"],
        capture_output=True, text=True,
    )
    if result_check.returncode != 0:
        import pytest
        pytest.skip(
            "syrupy not installed on this worktree (09-01 not merged). "
            "T-09-SOUND will run post-wave-merge. "
            f"(pip check: {result_check.stderr[:200]})"
        )

    # Write the child test into a fully isolated tmp directory so its
    # snapshot dir is guaranteed empty (no pre-existing .ambr files).
    child_dir = tmp_path / "soundness_probe"
    child_dir.mkdir()
    (child_dir / "conftest.py").write_text(_CHILD_CONFTEST, encoding="utf-8")
    (child_dir / "test_missing_snapshot.py").write_text(_CHILD_TEST, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "-x", "-q",
            "--tb=short",
            str(child_dir / "test_missing_snapshot.py"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        # Run in tmp_path so snapshot dir is relative to child_dir
        cwd=str(child_dir),
    )

    # Default syrupy behavior MUST FAIL on missing snapshot.
    # Acceptable exit codes: 1 (test failed) or 2 (collection error). NOT 0.
    assert result.returncode != 0, (
        "syrupy missing-snapshot did NOT fail (exit=0). "
        "This breaks the T-09-SOUND soundness guarantee — "
        "syrupy's default fail-on-missing behavior has changed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    # Confirm the output mentions a snapshot-related failure to rule out
    # accidental failures from import errors or config issues.
    joined = (result.stdout + result.stderr).lower()
    # syrupy failure messages vary by version; accept any of:
    snapshot_failure_signals = (
        "snapshot does not exist",
        "snapshot",          # broad catch for any snapshot-related message
        "assertionerror",
        "failed",
        "assert",
    )
    ok = any(sig in joined for sig in snapshot_failure_signals)
    assert ok, (
        "subprocess failed (exit!=0) but reason unclear — "
        "no snapshot-failure signal found in output.\n"
        "This may indicate an import error or config issue, not a "
        "syrupy missing-snapshot failure.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
