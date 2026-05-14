"""HTMLSnapshotExtension — Phase 9 TEST-HARNESS-01 (D-901).

Single-file syrupy extension for .html snapshots in TEXT mode.
7-LOC body; verbatim from Context7 /syrupy-project/syrupy llms.txt
§"Create Custom Raw Binary Snapshot Extension" pattern, swapped to TEXT.
"""

from __future__ import annotations

from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode


class HTMLSnapshotExtension(SingleFileSnapshotExtension):
    """One .html file per snapshot, text mode (not binary)."""

    _file_extension = "html"
    _write_mode = WriteMode.TEXT
