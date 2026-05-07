"""NORM-06 review queue writer — markdown ledger per run.

Source: 02-CONTEXT.md D-208 (markdown table schema), D-211 (Phase 2 owns write-path,
not Phase 3 stub). Mirrors role of `enumeration/goldapple_sitemap.py:persist_sitemap_slugs`
(file-I/O per run-dir).

Schema (D-208):

    # NORM-06 Review Queue — Run {run_id} ({YYYY-MM-DD})

    | brand_or_slug | source              | run_id | status  |
    |---------------|---------------------|--------|---------|
    | jo_malone     | viled-unmatched     | 44     | pending |
    | tom-ford-...  | goldapple-new-slug  | 44     | pending |

Source enum: viled-unmatched | goldapple-new-slug
Status default: pending; operator edits to aliased | skip | reviewed.

D-209 operator workflow: operator hand-edits the markdown status column then commits;
git history is the audit trail. No automated review pipeline on v1 (D-210).
D-220: NO DB-table backup on v1 — markdown + git suffice.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)


class Norm06Writer:
    """Markdown ledger writer for NORM-06 review queue.

    File-based ledger (D-210: NO DB-table backup on v1; git history is audit trail).
    """

    def __init__(self, repo_root: Path | str = "."):
        self.repo_root = Path(repo_root)

    def persist(
        self,
        run_id: int,
        viled_unmatched: list[str],
        goldapple_new_slugs: list[str],
    ) -> Path:
        """Render markdown to .planning/runs/{run_id}/norm06-review.md.

        Always writes the header even if both lists are empty (creates the audit
        artifact for the run regardless).
        """
        out_dir = self.repo_root / ".planning" / "runs" / str(run_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "norm06-review.md"

        today = date.today().isoformat()
        lines = [
            f"# NORM-06 Review Queue — Run {run_id} ({today})",
            "",
            "Operator workflow (D-209): edit the `status` column to one of "
            "`aliased` / `skip` / `reviewed` and commit. Git history is the audit "
            "trail (no DB-table backup on v1 per D-210).",
            "",
            "| brand_or_slug | source | run_id | status |",
            "|---------------|--------|--------|--------|",
        ]
        for brand in viled_unmatched:
            lines.append(f"| {brand} | viled-unmatched | {run_id} | pending |")
        for slug in goldapple_new_slugs:
            lines.append(f"| {slug} | goldapple-new-slug | {run_id} | pending |")

        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log.info(
            "norm06_persisted",
            run_id=run_id,
            out_path=str(out_path),
            viled_unmatched_count=len(viled_unmatched),
            goldapple_new_slugs_count=len(goldapple_new_slugs),
        )
        return out_path


__all__ = ["Norm06Writer"]
