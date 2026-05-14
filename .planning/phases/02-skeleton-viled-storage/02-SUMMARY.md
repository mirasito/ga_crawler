---
phase: 2
slug: project-skeleton-viled-crawl-storage
status: complete
completed: 2026-05-07
requirements-completed: [DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, CRAWL-01, CRAWL-03, CRAWL-04, CRAWL-05, CRAWL-06, PARSE-01, PARSE-02, PARSE-03, PARSE-04, PARSE-05, PARSE-06, NORM-01, NORM-02, NORM-03, NORM-04, NORM-05, NORM-06]
test-count-at-close: 250
reconstructed: 2026-05-14
---

# Phase 2 Summary — Project Skeleton: Viled Crawl + Storage

## Goal

Stand up the full project skeleton and ship the end-to-end viled.kz crawl + parse + normalize + store pipeline. This phase ships all shared infrastructure (storage, normalizers, brand-alias loader, gates) that Phase 3+ reuses.

## Files Changed

### Production code

- `src/ga_crawler/storage/sqlite.py` — SQLModel tables (`Run`, `Snapshot`), WAL PRAGMA event listener, `SqliteRunWriter` (lifecycle: `create` / `patch_stats` / `fail` / `finalize`), `SqliteSnapshotWriter` (per-batch INSERT-only), `v_current_snapshots` VIEW DDL. All SQL uses `text(":param")` + `params=` dict — no f-string or %-formatted SQL (T-02-01 bind-param mitigation).
- `src/ga_crawler/storage/norm06_writer.py` — `Norm06Writer.persist()` markdown ledger for NORM-06 brand-gap review.
- `src/ga_crawler/storage/schemas.py` — `ViledRawProduct`, `GoldappleRawProduct`, `RawProductBase` 9-field shapes.
- `src/ga_crawler/fetchers/viled.py` — `ViledFetcher` with `fetch_one_isolated` (per-SKU isolation CRAWL-03), tenacity-decorated `_fetch_html` (retry CRAWL-04), `run_loop` with `pause_seconds` sleep (CRAWL-06).
- `src/ga_crawler/parsers/viled_nextdata.py` — `parse_pdp` returning `ViledRawProduct`; `__NEXT_DATA__` JSON extraction; `_map_stock_state` (`StockState` enum PARSE-06); price sanity 100–1_000_000 ₸ (PARSE-04).
- `src/ga_crawler/parsers/dispatcher.py` — `ParseDispatcher` per-retailer routing.
- `src/ga_crawler/parsers/types.py` — `StockState` Literal enum.
- `src/ga_crawler/normalizers/brand.py` — `normalize_brand` (NFKD + accent strip + lowercase + alias lookup).
- `src/ga_crawler/normalizers/name.py` — `normalize_name` (NFKD + lowercase + strip non-word + collapse whitespace).
- `src/ga_crawler/normalizers/volume.py` — `Volume` frozen dataclass + `parse_volume` 3-layer grammar + `detect_multipack`.
- `src/ga_crawler/enumeration/viled_catalog.py` — `fetch_catalog_urls` walking `props.pageProps.items.*` SSR pagination.
- `src/ga_crawler/runner/gates.py` — `final_threshold_gate` + `parse_quality_gate` (D-203, D-218).
- `src/ga_crawler/runners/viled_run.py` — phase orchestrator; calls parse-quality gate FIRST (D-218), then sanity-N gate, then `run_writer.finalize`.
- `config/brand-aliases.yaml` — 58 canonical brands + 46 Cyrillic aliases production seed.
- `bin/backup.sh` — online `sqlite3 .backup` + 4-rotate retention (D-219).

## Threat Flags

- none — retroactive reconstruction
