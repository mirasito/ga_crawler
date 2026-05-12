"""Plan 06-05 (Wave 4) — structural canary: D-514 inverted invariant.

Phase 6 delivery is a thin wrapper. NEVER re-generates summary_text or xlsx;
consumes them verbatim from ``runs.stats.report.*`` (D-514 source-of-truth).

Test fails the build if anyone adds Phase 5 builder imports to delivery/.
Also pins ancillary isolation invariants (aiogram only in telegram_client.py;
load_dotenv ONLY in cli.py per RESEARCH caveat #4).
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_DIR = REPO_ROOT / "src" / "ga_crawler" / "delivery"
FORBIDDEN_IMPORTS = (
    "summary_builder",
    "excel_builder",
    "reporter.queries",
    "reporter.archive",
)


@pytest.fixture
def delivery_source_text() -> str:
    """Combined text of every ``src/ga_crawler/delivery/*.py`` module."""
    files = list(DELIVERY_DIR.glob("*.py"))
    assert len(files) >= 4, (
        f"expected >=4 delivery/*.py files, got {len(files)}: "
        f"{[p.name for p in files]}"
    )
    return "\n".join(f.read_text(encoding="utf-8") for f in files)


def test_no_summary_builder_import_in_delivery(delivery_source_text):
    """D-514 inverted invariant: delivery/ MUST NOT import Phase 5 builders.

    Phase 6 is a thin wrapper that consumes ``runs.stats.report.*`` verbatim.
    Any fork of Phase 5's summary/xlsx generation would create source-of-truth
    drift and break the D-514 contract.
    """
    for forbidden in FORBIDDEN_IMPORTS:
        assert forbidden not in delivery_source_text, (
            f"delivery/ imports '{forbidden}' -- violates D-514 inverted invariant "
            "(Phase 6 must consume reporter output verbatim, NEVER re-generate)"
        )


def test_delivery_package_has_expected_modules():
    """Wave 1+2+3 must ship: __init__, config, stats, message_builder, gate, telegram_client."""
    files = sorted(p.name for p in DELIVERY_DIR.glob("*.py"))
    expected = {
        "__init__.py",
        "config.py",
        "gate.py",
        "message_builder.py",
        "stats.py",
        "telegram_client.py",
    }
    missing = expected - set(files)
    assert not missing, f"missing modules: {missing}; have: {files}"


def test_aiogram_imports_only_in_telegram_client():
    """Pitfall B isolation: ONLY ``telegram_client.py`` touches aiogram.

    aiogram pulls in aiohttp / asyncio runtime side-effects; isolating it
    keeps the rest of the package pure-Python and easy to unit-test.

    Scope: import statements only. Mere mentions of "aiogram" in comments
    or docstrings (e.g. "stdlib over aiogram.html") are allowed.
    """
    for p in DELIVERY_DIR.glob("*.py"):
        if p.name in ("telegram_client.py", "__init__.py"):
            continue
        text = p.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.lstrip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            # Strip inline comments so a trailing `# RESEARCH caveat ... aiogram.html`
            # on an unrelated import is not flagged.
            code_part = line.split("#", 1)[0]
            assert "aiogram" not in code_part, (
                f"{p.name}: aiogram import detected -- isolation violation "
                "(only telegram_client.py may import aiogram). "
                f"Offending line: {line!r}"
            )


def test_load_dotenv_not_in_delivery_module():
    """RESEARCH caveat #4: ``load_dotenv`` ONLY in ``cli.py::_cmd_deliver``.

    Importing load_dotenv inside library code is a configuration-coupling
    smell: when run_weekly composes delivery, env is already loaded by the
    caller (cli.py weekly-run handler), and a second load_dotenv would
    re-read .env after subprocess monkeypatching took effect, breaking
    tests that override env vars via monkeypatch.setenv.
    """
    for p in DELIVERY_DIR.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        assert "load_dotenv" not in text, (
            f"{p.name} contains load_dotenv -- must ONLY appear in cli.py "
            "(RESEARCH caveat #4)"
        )
