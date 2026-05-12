"""Wave 0 / Plan 07-01 — Phase 7 "zero production Python" structural canaries.

RED-gate stub: parts fail until Plan 07-05 close-out commit (or stay GREEN if Phase 6
state preserved — these are inverted invariants).

Covers:
  - Phase 7 ships zero production Python (no new src/ga_crawler/**/*.py from Phase 6 -> Phase 7)
  - 5-way runs.stats.* namespace disjoint preserved (no schedule.* keys)
  - pyproject.toml [tool.ga_crawler.*] namespace set unchanged (no new namespace)
  - No simulate-failure / fail.mode substrings in production source
  - load_dotenv only in cli.py (Phase 6 RESEARCH caveat #4 inherited)

Source: 07-CONTEXT.md Claude's Discretion lines 153-156; 07-PATTERNS.md §"test_phase07_structural_canaries.py".
"""

from __future__ import annotations

import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "ga_crawler"


# --- Canary 1: no simulate-failure / fail.mode in production source ---

def test_no_simulate_failure_substring_in_production():
    """Phase 7 specifics line 259: NO new flags / testing-mode toggles in production binary."""
    FORBIDDEN_SUBSTRINGS = ("simulate-failure", "simulate_failure", "fail.mode", "fail_mode")
    offenders = []
    for py_file in SRC_ROOT.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_SUBSTRINGS:
            if forbidden in text:
                offenders.append((py_file.relative_to(REPO_ROOT), forbidden))
    assert offenders == [], (
        f"production source contains forbidden testing-mode substrings — Phase 7 anti-pattern: {offenders}"
    )


# --- Canary 2: pyproject [tool.ga_crawler.*] namespaces unchanged ----

def test_pyproject_no_new_namespace_phase7():
    """Phase 7 adds NO new [tool.ga_crawler.*] section (CONTEXT.md Claude's Discretion line 153)."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    ga = data.get("tool", {}).get("ga_crawler", {})
    actual_keys = set(ga.keys())
    EXPECTED = {"crawl", "match", "report", "deliver"}
    extra = actual_keys - EXPECTED
    assert extra == set(), (
        f"Phase 7 must not add [tool.ga_crawler.*] namespaces; extra: {extra}"
    )
    crawl_keys = set(ga.get("crawl", {}).keys())
    assert crawl_keys == {"viled", "goldapple"}, (
        f"[tool.ga_crawler.crawl] subspaces must remain {{viled, goldapple}}; got {crawl_keys}"
    )


def test_pyproject_no_new_dependencies_phase7():
    """Phase 7 adds zero deps (CONTEXT.md Action Items line 307 + D-710)."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deps = set(data["project"]["dependencies"])
    expected_packages = {
        "aiogram", "camoufox[geoip]", "curl-cffi", "pandas", "patchright",
        "pydantic", "python-dotenv", "pyyaml", "selectolax", "sqlmodel",
        "structlog", "tenacity", "tzdata", "xlsxwriter",
    }
    actual_packages = set()
    for dep in deps:
        name = dep.split(";")[0].strip()
        for op in (">=", "<=", "==", "<", ">", "!="):
            name = name.split(op)[0].strip()
        actual_packages.add(name)
    extra = actual_packages - expected_packages
    assert extra == set(), (
        f"Phase 7 must not add new deps; extra: {extra}"
    )


# --- Canary 3: 5-way namespace disjoint preserved (no schedule.* key) ----

def test_five_way_stats_namespace_disjoint_preserved():
    """D-607 + Pitfall 7 inherited from Phase 6. Phase 7 adds NO 6th namespace
    (CONTEXT.md Claude's Discretion line 154 — no schedule.* in runs.stats).
    """
    from ga_crawler.delivery.stats import DELIVER_STATS_KEYS
    from ga_crawler.matcher.stats import MATCH_STATS_KEYS
    from ga_crawler.reporter.stats import REPORT_STATS_KEYS
    from ga_crawler.runner.stats import GOLDAPPLE_STATS_KEYS, VILED_STATS_KEYS

    sets = {
        "viled":     set(VILED_STATS_KEYS),
        "goldapple": set(GOLDAPPLE_STATS_KEYS),
        "match":     set(MATCH_STATS_KEYS),
        "report":    set(REPORT_STATS_KEYS),
        "deliver":   set(DELIVER_STATS_KEYS),
    }
    names = list(sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert sets[a].isdisjoint(sets[b]), (
                f"Phase 7 broke 5-way disjoint: {a} ∩ {b} = {sets[a] & sets[b]}"
            )


def test_no_schedule_stats_namespace_in_source():
    """CONTEXT.md Claude's Discretion line 154: Phase 7 must NOT add schedule.* keys."""
    offenders = []
    for py_file in SRC_ROOT.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for forbidden in ('"schedule.', "'schedule.", "stats[\"schedule.", "stats['schedule."):
            if forbidden in text:
                offenders.append((py_file.relative_to(REPO_ROOT), forbidden))
    assert offenders == [], (
        f"Phase 7 must not add schedule.* stats key; offenders: {offenders}"
    )


# --- Canary 4: load_dotenv only in cli.py (RESEARCH caveat #4) -----

def test_load_dotenv_only_in_cli_module():
    """RESEARCH caveat #4 inherited from Phase 6. Phase 7 bash wrapper handles env
    via 'set -a; source .env; set +a' — Python load_dotenv stays only in cli.py.
    """
    offenders = []
    for py_file in SRC_ROOT.rglob("*.py"):
        if py_file.name == "cli.py":
            continue
        text = py_file.read_text(encoding="utf-8")
        if "load_dotenv" in text:
            offenders.append(py_file.relative_to(REPO_ROOT))
    assert offenders == [], (
        f"load_dotenv must ONLY appear in cli.py (RESEARCH caveat #4); offenders: {offenders}"
    )


# --- Canary 5: CLI surface unchanged (5 subcommands, no Phase 7 additions) -

def test_cli_surface_remains_five_subcommands():
    """Phase 7 ships ZERO production Python — cli.py source unchanged from Phase 6."""
    cli_text = (SRC_ROOT / "cli.py").read_text(encoding="utf-8")
    for anchor in (
        "goldapple-smoke",
        "weekly-run",
        "matcher-run",
        "report-run",
        "deliver-run",
        "def _configure_logging",
    ):
        assert anchor in cli_text, (
            f"cli.py anchor {anchor!r} missing — Phase 7 must not change cli.py (CONTEXT.md line 183)"
        )


def test_main_run_orchestrator_unchanged_anchors():
    """runners/main_run.py source unchanged Phase 6 -> Phase 7 (CONTEXT.md line 184)."""
    main_run = SRC_ROOT / "runners" / "main_run.py"
    text = main_run.read_text(encoding="utf-8")
    for anchor in ("def run_weekly", "MainRunResult", "delivery_status", "delivery_route"):
        assert anchor in text, (
            f"runners/main_run.py anchor {anchor!r} missing — Phase 7 must not change main_run.py (CONTEXT.md line 184)"
        )
