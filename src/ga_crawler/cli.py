"""Phase 3 CLI entry. Two subcommands:

  python -m ga_crawler goldapple-smoke
      One-off smoke probe against live goldapple. Prints diagnostics. No DB writes.

  python -m ga_crawler goldapple-run --run-id N --viled-brands a,b,c [--repo-root .]
      Full Phase 3 run with stub Phase 2 protocols.

Stub Phase 2 implementations satisfy interfaces.py Protocols and persist to
{repo_root}/.planning/runs/{run_id}/. They are intentionally minimal — once
Phase 2 ships, the orchestrator wires the real Phase 2 modules.

T-03-06-12 mitigation: stub-state files live under .planning/runs/, which
the project .gitignore should cover.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import structlog

from ga_crawler.fetchers.goldapple import GoldappleFetcher
from ga_crawler.runner.gates import smoke_probe

log = structlog.get_logger(__name__)


# ---- Stub Phase 2 protocol implementations ----


class StubBrandAlias:
    """Brand-alias stub: lookup returns [brand_norm]."""

    def lookup(self, brand_norm: str) -> list[str]:
        return [brand_norm]


class StubNormalizer:
    """No-op-ish normalizer: lowercase brand/name; volume always None."""

    def brand(self, raw: str) -> str:
        return raw.lower().strip()

    def name(self, raw: str) -> str:
        return raw.lower().strip()

    def volume(self, raw: str):
        return None


class StubSnapshotWriter:
    """Append-only JSONL writer to {root}/runs/{run_id}/snapshots.jsonl (DATA-03)."""

    def __init__(self, root: Path):
        self.root = root

    def append(self, run_id: int, retailer: str, products: list) -> int:
        out = self.root / f"runs/{run_id}/snapshots.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as f:
            for p in products:
                row = {**p, "retailer": retailer, "run_id": run_id}
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return len(products)


class StubRunWriter:
    """Stub RunWriter: persists JSON to {root}/runs/{run_id}/runs.json.

    patch_stats merges via dict.update (Pitfall 6 atomic-merge semantics —
    real Phase 2 uses SQLite json_patch which is functionally identical).
    """

    def __init__(self, root: Path):
        self.root = root

    def _path(self, run_id: int) -> Path:
        return self.root / f"runs/{run_id}/runs.json"

    def patch_stats(self, run_id: int, delta: dict) -> None:
        p = self._path(run_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if p.exists():
            existing = json.loads(p.read_text(encoding="utf-8"))
        stats = existing.get("stats", {})
        stats.update(delta)
        existing["stats"] = stats
        existing.setdefault("run_id", run_id)
        existing.setdefault("status", "running")
        p.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def get_stats(self, run_id: int) -> dict:
        p = self._path(run_id)
        if not p.exists():
            return {}
        return json.loads(p.read_text(encoding="utf-8")).get("stats", {})

    def fail(self, run_id: int, reason: str) -> None:
        p = self._path(run_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if p.exists():
            existing = json.loads(p.read_text(encoding="utf-8"))
        existing["status"] = "failed"
        existing["fail_reason"] = reason
        existing.setdefault("run_id", run_id)
        p.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )


# ---- CLI command handlers ----


async def _cmd_smoke(args) -> int:
    async with GoldappleFetcher(run_id=args.run_id, headless=args.headless) as fetcher:
        result = await smoke_probe(fetcher)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


async def _cmd_run(args) -> int:
    from ga_crawler.runners.goldapple_run import run_goldapple_phase

    repo_root = Path(args.repo_root).resolve()
    viled_brands = [b.strip() for b in args.viled_brands.split(",") if b.strip()]
    brand_alias = StubBrandAlias()
    normalizer = StubNormalizer()
    snapshot_writer = StubSnapshotWriter(repo_root / ".planning")
    run_writer = StubRunWriter(repo_root / ".planning")
    result = await run_goldapple_phase(
        run_id=args.run_id,
        viled_brands=viled_brands,
        repo_root=repo_root / ".planning",
        brand_alias=brand_alias,
        normalizer=normalizer,
        snapshot_writer=snapshot_writer,
        run_writer=run_writer,
        headless=args.headless,
        M=args.sanity_gate_m,
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "goldapple_count": result.goldapple_count,
                "reason": result.reason,
                "stats_delta_keys": sorted(result.stats_delta.keys()),
                "unmatched_viled_brands": result.unmatched_viled_brands,
                "new_goldapple_slugs_count": len(result.new_goldapple_slugs),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status == "success" else 2


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


def _parse_bool(v: str) -> bool:
    return str(v).strip().lower() not in ("false", "0", "no", "off")


def main(argv: Optional[list[str]] = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(
        prog="python -m ga_crawler", description="GA Crawler Phase 3 CLI"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    smoke = sub.add_parser(
        "goldapple-smoke",
        help="Run smoke probe (D-312) against live goldapple",
    )
    smoke.add_argument("--run-id", type=int, default=999)
    smoke.add_argument("--headless", type=_parse_bool, default=True)

    run = sub.add_parser(
        "goldapple-run",
        help="Full Phase 3 run with stub Phase 2 storage",
    )
    run.add_argument("--run-id", type=int, required=True)
    run.add_argument("--viled-brands", required=True)
    run.add_argument("--repo-root", default=".")
    run.add_argument("--sanity-gate-m", type=int, default=1000)
    run.add_argument("--headless", type=_parse_bool, default=True)

    args = parser.parse_args(argv)
    if args.cmd == "goldapple-smoke":
        return asyncio.run(_cmd_smoke(args))
    if args.cmd == "goldapple-run":
        return asyncio.run(_cmd_run(args))
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
