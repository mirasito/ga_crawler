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
