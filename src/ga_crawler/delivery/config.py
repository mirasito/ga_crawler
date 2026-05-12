"""Phase 6 delivery configuration — runtime constants + ENV credentials.

Two separate dataclasses (D-611 + D-614 + RESEARCH caveat #4):
  DeliverConfig    — from ``pyproject.toml [tool.ga_crawler.deliver]``
  DeliverEnvConfig — from ``os.environ`` ``TG_*`` (pure ``os.getenv``
                     reads; dotenv-loading is the CLI entrypoint's job,
                     never this module's — keeps test runs from picking
                     up a real on-disk env file).

Source anchors: 06-CONTEXT.md D-611 + D-614; 06-RESEARCH.md caveat #4;
06-PATTERNS.md "src/ga_crawler/delivery/config.py" section.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class DeliverConfig:
    """Operator-tunable runtime constants. Defaults mirror pyproject.toml.

    Per D-614. Defaults are kept in sync with ``[tool.ga_crawler.deliver]``
    so that ``DeliverConfig()`` in a test yields the same values as
    ``DeliverConfig.from_pyproject()`` against the production toml.
    """

    retry_max_attempts: int = 3
    retry_backoff_min_seconds: int = 5
    retry_backoff_max_seconds: int = 45
    ops_message_truncate_chars: int = 3500
    business_caption_max_chars: int = 1024
    parse_mode: str = "HTML"

    @classmethod
    def from_pyproject(cls, pyproject_path: Path | str = "pyproject.toml") -> "DeliverConfig":
        """Read ``[tool.ga_crawler.deliver]`` from the given pyproject.toml.

        Missing keys (or a missing file) fall back to the dataclass defaults
        — mirror of ``ReportConfig.from_pyproject``.
        """
        path = Path(pyproject_path)
        if not path.exists():
            return cls()
        with path.open("rb") as f:
            data = tomllib.load(f)
        deliver = (
            data.get("tool", {})
            .get("ga_crawler", {})
            .get("deliver", {})
        )
        return cls(
            retry_max_attempts=int(deliver.get("retry_max_attempts", cls.retry_max_attempts)),
            retry_backoff_min_seconds=int(
                deliver.get("retry_backoff_min_seconds", cls.retry_backoff_min_seconds)
            ),
            retry_backoff_max_seconds=int(
                deliver.get("retry_backoff_max_seconds", cls.retry_backoff_max_seconds)
            ),
            ops_message_truncate_chars=int(
                deliver.get("ops_message_truncate_chars", cls.ops_message_truncate_chars)
            ),
            business_caption_max_chars=int(
                deliver.get("business_caption_max_chars", cls.business_caption_max_chars)
            ),
            parse_mode=str(deliver.get("parse_mode", cls.parse_mode)),
        )


@dataclass(frozen=True)
class DeliverEnvConfig:
    """ENV-loaded credentials (separated — secrets NEVER in git).

    Per D-611 (asymmetric handling: ``bot_token`` required, ``chat_ids``
    degradable) + RESEARCH caveat #4: this module performs only pure
    ``os.getenv`` reads; dotenv-loading is the CLI entrypoint's
    responsibility so test runs never accidentally read a real on-disk
    env file.

    Empty-string env vars are normalised to ``None`` so that downstream
    asymmetric handling (D-611) sees a clean ``is None`` check rather
    than having to also test ``== ""``.
    """

    bot_token: Optional[str]
    business_chat_id: Optional[str]
    ops_chat_id: Optional[str]

    @classmethod
    def from_env(cls) -> "DeliverEnvConfig":
        """Read TG_* from ``os.environ`` via ``os.getenv``; no dotenv side-effects."""
        return cls(
            bot_token=os.getenv("TG_BOT_TOKEN") or None,
            business_chat_id=os.getenv("TG_BUSINESS_CHAT_ID") or None,
            ops_chat_id=os.getenv("TG_OPS_CHAT_ID") or None,
        )


__all__ = ["DeliverConfig", "DeliverEnvConfig"]
