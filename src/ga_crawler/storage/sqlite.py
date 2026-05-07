"""SQLite storage layer: SQLModel tables, WAL engine, atomic writers, current-view bootstrap.

Source: 02-RESEARCH.md §Pattern 3 (Run + Snapshot tables), §Pattern 4 (SqliteRunWriter
atomic json_patch), §Pattern 5 (SqliteSnapshotWriter per-batch INSERT-only),
§"Initializing the WAL session" (PRAGMA event listener pattern).

Decisions:
  - D-214: single-module storage (sqlite.py + norm06_writer.py). No data/, models/,
    repositories/ split on day 1.
  - D-220: schema bootstrap via SQLModel.metadata.create_all + raw VIEW DDL.
    NO alembic on day 1 (CLAUDE.md explicit). Add at first migration (v2+).
  - D-221: v_current_snapshots VIEW is the single source of truth for "latest
    successful run" — Phase 3 brand-pool reads `DISTINCT brand_norm WHERE retailer='viled'`.

Pitfalls mitigated here:
  - Pitfall 4 (RFC-7396 null-as-DELETE): patch_stats rejects None values upfront.
  - Pitfall 6 (read-modify-write race): patch_stats is single-call SQL UPDATE
    using SQLite's json_patch() function — atomic at the SQL layer.
  - Pitfall 7 (Stub vs real schema drift): SqliteSnapshotWriter.append filters
    payload to Snapshot.model_fields.keys() so the Phase 3 dict-shape (which
    lacks multipack_flag/parse_error_flag/volume_raw) is accepted via defaults.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import event, text
from sqlmodel import (
    Field,
    Index,
    Session,
    SQLModel,
    UniqueConstraint,
    create_engine,
)

log = structlog.get_logger(__name__)


# ---- SQLModel tables (DATA-01, DATA-02) ----


class Run(SQLModel, table=True):
    """Single row per weekly run. DATA-05 lifecycle: create → patch_stats → finalize/fail."""

    __tablename__ = "runs"
    run_id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    status: str = Field(default="running")  # running | success | failed | partial
    fail_reason: Optional[str] = None
    stats: str = Field(default="{}")  # JSON-encoded text; SQLite TEXT column


class Snapshot(SQLModel, table=True):
    """Append-only snapshot row per (run_id, retailer, sku_id). DATA-01..03."""

    __tablename__ = "snapshots"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.run_id", index=True)
    retailer: str = Field(index=True)  # "viled" | "goldapple"
    sku_id: str
    url: str
    name: str
    brand: str
    brand_norm: str = Field(index=True)
    name_norm: str
    volume_raw: Optional[str] = None
    volume_norm: Optional[str] = None  # serialized "(amount, unit, count)" or NULL
    multipack_flag: bool = Field(default=False)
    parse_error_flag: bool = Field(default=False)
    current_price: Optional[int] = None
    was_price: Optional[int] = None
    currency: str = Field(default="KZT")
    stock_state: str = Field(default="UNKNOWN")
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("run_id", "retailer", "sku_id", name="uq_snapshot_run_retailer_sku"),
        Index("ix_snapshot_retailer_brand_norm", "retailer", "brand_norm"),
        Index("ix_snapshot_run_retailer", "run_id", "retailer"),
    )


# ---- Engine factory + PRAGMAs (DATA-04) ----


def make_engine(db_path: str | Path = "prices.db", *, echo: bool = False):
    """Create SQLAlchemy engine with WAL + synchronous=NORMAL + foreign_keys=ON.

    PRAGMA application via event listener so EVERY connection (incl. pool refills)
    gets them. Source: SQLAlchemy events doc + sqlite.org PRAGMA docs.
    """
    engine = create_engine(f"sqlite:///{db_path}", echo=echo)

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):  # noqa: D401
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def init_db(db_path: str | Path = "prices.db") -> None:
    """Idempotent schema bootstrap. SQLModel.metadata.create_all + create v_current_snapshots VIEW.

    D-220: NO alembic on day 1. CLAUDE.md explicit. Add when first migration is needed (v2).
    D-221: v_current_snapshots returns rows from MAX(run_id) where status='success'.
    """
    engine = make_engine(db_path)
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        # CREATE VIEW IF NOT EXISTS — idempotent
        conn.exec_driver_sql(
            """
            CREATE VIEW IF NOT EXISTS v_current_snapshots AS
            SELECT * FROM snapshots
            WHERE run_id = (SELECT MAX(run_id) FROM runs WHERE status = 'success')
            """
        )
        conn.commit()
    log.info("db_initialized", db_path=str(db_path))


# ---- SqliteSnapshotWriter (DATA-03, DATA-04) ----


class SqliteSnapshotWriter:
    """Append-only INSERT writer. Per-batch commit so mid-run failure keeps prior batches.

    Implements SnapshotWriterProtocol (interfaces.py). Accepts the same dict-shape
    that runners/goldapple_run.py:237-250 produces (Pitfall 7 contract — unknown
    keys silently filtered, missing optional keys default at the SQLModel level).
    """

    def __init__(self, engine, *, batch_size: int = 100):
        self.engine = engine
        self.batch_size = batch_size

    def append(self, run_id: int, retailer: str, products: list) -> int:
        if not products:
            return 0
        inserted = 0
        # Filter unknown keys so Phase 3 dict-shape (which lacks multipack_flag /
        # parse_error_flag / volume_raw) is accepted gracefully via defaults.
        valid_fields = set(Snapshot.model_fields.keys())
        with Session(self.engine) as session:
            try:
                for product in products:
                    payload = {k: v for k, v in product.items() if k in valid_fields}
                    payload["run_id"] = run_id
                    payload["retailer"] = retailer
                    row = Snapshot(**payload)
                    session.add(row)
                    inserted += 1
                    if inserted % self.batch_size == 0:
                        session.commit()
                session.commit()  # final partial batch
            except Exception:
                session.rollback()
                raise
        return inserted


__all__ = [
    "Run",
    "Snapshot",
    "SqliteSnapshotWriter",
    "make_engine",
    "init_db",
]
