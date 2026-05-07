"""Phase 2 storage layer.

Single-module impl per D-214: `sqlite.py` houses SQLModel tables (Run, Snapshot)
+ writers (SqliteRunWriter, SqliteSnapshotWriter) + engine factory + view bootstrap.
`norm06_writer.py` houses the markdown ledger writer (per D-208 / NORM-06).

Source: 02-RESEARCH.md §Pattern 3, §Pattern 4, §Pattern 5; 02-CONTEXT.md D-214.
"""
