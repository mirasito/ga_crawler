"""Shared pytest fixtures for Phase 3 (Goldapple Crawl) tests.

Loads spike sample-payloads as in-memory fixtures. Provides Phase 2 contract
mocks (BrandAlias, Normalizer, SnapshotWriter, RunWriter) for all unit and
mocked-integration tests. Tmp Camoufox profile dir factory for fetcher tests.

Fixture path conventions:
- HTML fixtures: tests/fixtures/goldapple/*.html (verbatim spike copies)
- Mock builders: returned via fixture functions, scope='function' (fresh per test)
- Tmp profile dirs: scope='function', auto-cleanup via tmp_path

Per 03-PATTERNS.md "Test files" table.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "goldapple"


# ---- HTML / sitemap fixtures ----

@pytest.fixture(scope="session")
def goldapple_pdp_html() -> str:
    """Real Givenchy PDP captured during spike 01-08 (~200 KB).

    Source: .planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html
    Used by parser tests to assert: top-level offer extraction, priceType filtering
    (StrikethroughPrice / ListPrice / Gold Card discrimination), brand microdata
    walk, availability schema.org URL → enum.
    """
    return (FIXTURES_DIR / "_debug-product-page.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def gate_shell_html() -> str:
    """GroupIB challenge shell sample (~18 KB).

    Source: .planning/spikes/01-goldapple/sample-payloads/goldapple-product-html-1.html
    Used by gate detection tests: title contains "checking device" + size < 30 KB.
    """
    return (FIXTURES_DIR / "gate-shell.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def stale_sku_html() -> str:
    """De-listed SKU pattern: 200 OK + ~9.5 KB + no microdata + title contains 'Loading'.

    Source: synthesized at Wave 0 to mimic spike result row 0 (per
    03-PATTERNS.md §"Test fixtures" — stale-sku-9.5kb.html "must be re-fetched
    or synthesized").
    """
    return (FIXTURES_DIR / "stale-sku-9.5kb.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def sitemap_xml() -> str:
    """Goldapple sub-sitemap excerpt (50 product URLs).

    Source: .planning/spikes/01-goldapple/sample-payloads/goldapple-sitemap-1-excerpt.xml
    Used by sitemap parser unit tests (regex extraction of <loc>...</loc>).
    """
    return (FIXTURES_DIR / "sitemap-1-excerpt.xml").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def tier2_results_json() -> dict:
    """Spike 01-08 empirical 100-fetch baseline (99/100 success, 0% gate-shell).

    Source: .planning/spikes/01-goldapple/sample-payloads/tier2-camoufox-kz-results.json
    Used by stale-SKU detection tests: row 0 = '7681000002-...' is the canonical
    stale-SKU case (status=200, html_size~9500, no microdata).
    """
    return json.loads((FIXTURES_DIR / "tier2-camoufox-kz-results.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def jsonld_blocks_anti_fixture() -> list:
    """Proof goldapple emits ONLY OfferShippingDetails JSON-LD (no Product schema).

    Source: .planning/spikes/01-goldapple/sample-payloads/_debug-jsonld-blocks.json
    Used by parser tests as anti-fixture: assert parser does NOT use JSON-LD path
    for goldapple (D-14 microdata-not-JSON-LD; PARSE-02 inverted for goldapple).
    """
    return json.loads((FIXTURES_DIR / "_debug-jsonld-blocks.json").read_text(encoding="utf-8"))


# ---- Phase 2 contract mocks ----

@pytest.fixture
def mock_brand_alias() -> MagicMock:
    """Mock BrandAliasProtocol. Default lookup returns the brand_norm itself as
    the only alias; tests override .lookup.return_value or .side_effect as needed.
    """
    mock = MagicMock()
    mock.lookup.side_effect = lambda b: [b]
    return mock


@pytest.fixture
def mock_normalizer() -> MagicMock:
    """Mock NormalizerProtocol. Default brand/name = lowercase + strip; volume = None."""
    mock = MagicMock()
    mock.brand.side_effect = lambda raw: raw.lower().strip()
    mock.name.side_effect = lambda raw: raw.lower().strip()
    mock.volume.return_value = None
    return mock


@pytest.fixture
def mock_snapshot_writer() -> MagicMock:
    """Mock SnapshotWriterProtocol. .append returns len(products); records calls
    via mock.append.call_args_list for assertion."""
    mock = MagicMock()
    mock.append.side_effect = lambda run_id, retailer, products: len(products)
    return mock


@pytest.fixture
def mock_run_writer() -> MagicMock:
    """Mock RunWriterProtocol. patch_stats accumulates into _stats dict;
    get_stats returns it; fail records reason."""
    mock = MagicMock()
    mock._stats = {}

    def _patch(run_id, delta):
        mock._stats.update(delta)

    def _get(run_id):
        return dict(mock._stats)

    mock.patch_stats.side_effect = _patch
    mock.get_stats.side_effect = _get
    return mock


# ---- Tmp profile dir for fetcher tests ----

@pytest.fixture
def tmp_camoufox_profile_dir(tmp_path: Path) -> Path:
    """Per-test Camoufox tmp profile dir under pytest's tmp_path.
    Auto-cleanup by pytest at end of test. Mirrors D-311 fresh-profile-per-run pattern."""
    p = tmp_path / "camoufox-profile"
    p.mkdir()
    return p


# ===== Phase 2 fixtures (D-222) =====
# Added Wave 0 of Phase 2. The 11 Phase 3 fixtures above remain untouched.
# Source: 02-CONTEXT.md D-222 + 02-PATTERNS.md §"Pattern: conftest fixture extension".

import yaml  # noqa: E402  -- import-after-block intentional for section grouping
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

VILED_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "viled"
NORMALIZE_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "normalize"


@pytest.fixture(scope="session")
def viled_pdp_html() -> str:
    """Canonical viled PDP HTML pinned Wave 0 (item/407682, Alice+Olivia "Кружевное боди").

    Source: tests/fixtures/viled/viled-pdp-407682.html captured 2026-05-07 via
    curl_cffi.requests.get(impersonate="chrome"); see 02-WAVE0-PROBE.md.

    Drives PARSE-01..04 happy-path tests for the viled __NEXT_DATA__ parser.
    """
    return (VILED_FIXTURES_DIR / "viled-pdp-407682.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def viled_pdp_discounted_html() -> str:
    """Discounted viled PDP HTML (item/367251, Frederic Malle perfume).

    attributes[0].price=356745 < attributes[0].realPrice=419700, enableDiscount=True.
    Drives PARSE-03 was_price assertion.
    """
    return (VILED_FIXTURES_DIR / "viled-pdp-discounted.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def viled_pdp_multipack_html() -> str:
    """Multipack viled PDP HTML (item/398309). Drives NORM-04 multipack-flag tests."""
    return (VILED_FIXTURES_DIR / "viled-pdp-multipack.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def viled_catalog_html() -> str:
    """Canonical viled catalog page-1 HTML (men/catalog/1310, ~238 KB, 60 items).

    Source: tests/fixtures/viled/viled-catalog-men-1310-page1.html.
    Drives CRAWL-01 catalog enumeration tests; pageProps.items.{content,total,
    totalPages,pageSize,pageNumber} per 02-WAVE0-PROBE.md A4.
    """
    return (VILED_FIXTURES_DIR / "viled-catalog-men-1310-page1.html").read_text(encoding="utf-8")


@pytest.fixture
def brand_alias_yaml_fixture(tmp_path: Path) -> Path:
    """Materialize tests/fixtures/viled/brand-aliases-fixture.yaml into tmp_path.

    Returns the tmp file path so YamlBrandAlias tests can point at a writable copy
    (allows mutation in tests without polluting the source fixture).
    Schema per 02-CONTEXT.md D-205.
    """
    src = (VILED_FIXTURES_DIR / "brand-aliases-fixture.yaml").read_text(encoding="utf-8")
    dst = tmp_path / "brand-aliases.yaml"
    dst.write_text(src, encoding="utf-8")
    return dst


@pytest.fixture
def in_memory_sqlite_session():
    """Yield a Session bound to an in-memory SQLite engine with foreign-keys
    PRAGMA applied. SQLModel tables are created if Wave 1's storage module is
    importable; otherwise a bare session yields (Wave 0 stubs that need this
    fixture must skip until Wave 1 lands).

    Source: 02-RESEARCH.md §Pattern 3 + §"Initializing the WAL session".
    """
    from sqlalchemy import event

    engine = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        # WAL is moot for :memory: but PRAGMA call is harmless and matches prod.
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # Tables are created lazily by Wave 1; Wave 0 stub yields a bare session.
    try:
        from ga_crawler.storage.sqlite import SQLModel as _SQL  # type: ignore[import-not-found]

        _SQL.metadata.create_all(engine)
    except ImportError:
        SQLModel.metadata.create_all(engine)  # empty metadata, no-op until Wave 1
    with Session(engine) as session:
        yield session


@pytest.fixture
def volume_corpus_cases() -> list[dict]:
    """Load tests/fixtures/normalize/volume-corpus.yaml.

    Returns list[dict] with keys input/expected_volume/expected_multipack.
    Source: 02-RESEARCH.md Open Q5 + Pattern 6.
    """
    raw = (NORMALIZE_FIXTURES_DIR / "volume-corpus.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(raw)["cases"]


@pytest.fixture
def brand_corpus_cases() -> list[dict]:
    """Load tests/fixtures/normalize/brand-corpus.yaml.

    Returns list[dict] with keys raw/expected_brand_norm/alias_present.
    """
    raw = (NORMALIZE_FIXTURES_DIR / "brand-corpus.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(raw)["cases"]
