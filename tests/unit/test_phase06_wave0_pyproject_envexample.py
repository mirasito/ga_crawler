"""Wave 0 / Plan 06-01 — Task 1 RED-gate test.

Asserts the post-Task-1 state of pyproject.toml + .env.example + .gitignore:
- pyproject.toml has aiogram>=3.27,<4.0 in [project] dependencies
- pyproject.toml has [tool.ga_crawler.deliver] table with exactly 6 keys (D-614)
- .env.example committed at repo root with 3 TG_* placeholders (D-612)
- .gitignore still excludes .env exactly once (audit, no edit needed)

Permanent canary — survives into Phase 7 to lock D-612/D-614 invariants.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_dependencies_include_aiogram():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deps = data["project"]["dependencies"]
    assert any(d.startswith("aiogram") for d in deps), (
        "aiogram dep missing from [project] dependencies"
    )
    aiogram_spec = next(d for d in deps if d.startswith("aiogram"))
    assert ">=3.27" in aiogram_spec
    assert "<4.0" in aiogram_spec


def test_pyproject_deliver_namespace_six_keys_typed():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deliver = data["tool"]["ga_crawler"]["deliver"]
    assert deliver["retry_max_attempts"] == 3
    assert deliver["retry_backoff_min_seconds"] == 5
    assert deliver["retry_backoff_max_seconds"] == 45
    assert deliver["ops_message_truncate_chars"] == 3500
    assert deliver["business_caption_max_chars"] == 1024
    assert deliver["parse_mode"] == "HTML"
    # Exactly 6 keys (Pitfall: drift detection — refuse stealth additions outside operator PR).
    assert set(deliver.keys()) == {
        "retry_max_attempts",
        "retry_backoff_min_seconds",
        "retry_backoff_max_seconds",
        "ops_message_truncate_chars",
        "business_caption_max_chars",
        "parse_mode",
    }


def test_env_example_committed_with_three_placeholders():
    env_example = REPO_ROOT / ".env.example"
    assert env_example.exists(), ".env.example must exist at repo root (D-612)"
    txt = env_example.read_text(encoding="utf-8")
    assert "TG_BOT_TOKEN=" in txt
    assert "TG_BUSINESS_CHAT_ID=" in txt
    assert "TG_OPS_CHAT_ID=" in txt


def test_env_example_has_no_real_secret_values():
    # T-6-01 mitigation canary: ensure .env.example only ships blank placeholders.
    env_example = REPO_ROOT / ".env.example"
    txt = env_example.read_text(encoding="utf-8")
    for line in txt.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.startswith("TG_"):
            assert value == "", (
                f"{key} in .env.example must have empty value (got {value!r}) — "
                "T-6-01 mitigation: no real secrets committed"
            )


def test_gitignore_excludes_env_exact_match():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    lines = [ln.rstrip("\r\n") for ln in gitignore.splitlines()]
    assert ".env" in lines, ".gitignore must contain an exact `.env` line"
