---
phase: 09-live-html-harness
plan: 02a
type: execute
wave: 1
depends_on:
  - "09-01"
files_modified:
  - tests/live/__init__.py
  - tests/live/test_parser_drift.py
  - tests/test_snapshot_soundness.py
autonomous: true
requirements:
  - TEST-HARNESS-03
tags:
  - testing
  - snapshot
  - live
  - drift
  - parser
  - python
must_haves:
  truths:
    - "`pytest -m live` (cassette-replay default) parses the 3 Phase 8 fixtures and asserts brand+name+volume_raw + brand-not-in-name invariants"
    - "`pytest -m live --refresh-live` re-fetches via Camoufox (goldapple) / curl_cffi (viled) and diffs against syrupy snapshot AFTER normalize_for_snapshot strip"
    - "Missing-snapshot fails CI loudly (negative test in tests/test_snapshot_soundness.py) — confirms syrupy default fail-on-missing behavior (T-09-SOUND)"
    - "All tests in tests/live/test_parser_drift.py carry @pytest.mark.live (module-level pytestmark) — opt-in only"
    - "Cassette-replay mode does NOT hit network (no Camoufox launch, no curl_cffi outbound)"
  artifacts:
    - path: "tests/live/__init__.py"
      provides: "Package marker so tests/live is importable"
    - path: "tests/live/test_parser_drift.py"
      provides: "3 live-drift tests (stereotype, armani-code, viled-contre-jour); two-mode (cassette default + --refresh-live)"
      contains: "pytestmark = pytest.mark.live"
    - path: "tests/test_snapshot_soundness.py"
      provides: "Negative test: missing snapshot fails CI loudly (T-09-SOUND)"
  key_links:
    - from: "tests/live/test_parser_drift.py"
      to: "tests/fixtures/goldapple/_live-2026-05-13-stereotype.html"
      via: "Path.read_text in cassette-replay mode"
      pattern: "_live-2026-05-13-stereotype"
    - from: "tests/live/test_parser_drift.py"
      to: "tests/fixtures/goldapple/_live-2026-05-13-armani-code.html"
      via: "Path.read_text in cassette-replay mode"
      pattern: "_live-2026-05-13-armani-code"
    - from: "tests/live/test_parser_drift.py"
      to: "tests/fixtures/viled/_live-2026-05-13-contre-jour.html"
      via: "Path.read_text in cassette-replay mode"
      pattern: "_live-2026-05-13-contre-jour"
    - from: "tests/live/test_parser_drift.py"
      to: "src/ga_crawler/parsers/goldapple_microdata.py parse_pdp"
      via: "import + call in cassette-replay branch"
      pattern: "from ga_crawler.parsers.goldapple_microdata import parse_pdp"
    - from: "tests/live/test_parser_drift.py"
      to: "src/ga_crawler/parsers/viled_nextdata.py parse_pdp"
      via: "import + call in viled branch"
      pattern: "from ga_crawler.parsers.viled_nextdata import parse_pdp"
    - from: "tests/live/test_parser_drift.py refresh_live branch"
      to: "tests/_html_normalize.py normalize_for_snapshot"
      via: "syrupy diff after normalize"
      pattern: "normalize_for_snapshot"
---

<objective>
Phase 9 Wave 1 (parallel-A) — ship `tests/live/test_parser_drift.py` two-mode harness that retroactively locks the Phase 8 parser fixes against drift. Three tests (stereotype, armani-code, viled contre-jour) replay the 3 Phase 8 W0 fixtures from `_live-2026-05-13-*.html`. The harness has two modes:

1. **Default `pytest -m live`** (cassette-replay): reads frozen fixture from disk → parses via `parse_pdp` → asserts brand/name/volume_raw/brand-not-in-name invariants. ~10s, no network.
2. **`pytest -m live --refresh-live`** (operator path): re-fetches via Camoufox (goldapple) / curl_cffi (viled) → normalizes HTML → `assert normalized_html == html_snapshot` (syrupy diff). With `--snapshot-update`, regenerates fixture.

Also ship a negative test (`tests/test_snapshot_soundness.py`) confirming syrupy's missing-snapshot fails-loud default (T-09-SOUND).

Purpose: this is the "would have caught run #13" headline test. If a future goldapple/viled HTML shape drifts so the parser regresses (e.g. brand merges into name, volume_raw nulls), pytest fails loudly. Locks Phase 8 D-805/D-806/D-807 fixes retroactively.

Output:
- `tests/live/__init__.py` (package marker)
- `tests/live/test_parser_drift.py` (3 drift tests, two-mode)
- `tests/test_snapshot_soundness.py` (negative test: missing snapshot raises)

Parallel-safe with 09-02b (TH-06 Pydantic) — disjoint files: 09-02a touches `tests/live/` + `tests/test_snapshot_soundness.py`; 09-02b touches `src/ga_crawler/storage/`, `tests/storage/`, `tests/integration/`, `tests/runner/`. Zero file overlap.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/09-live-html-harness/09-CONTEXT.md
@.planning/phases/09-live-html-harness/09-RESEARCH.md
@.planning/phases/09-live-html-harness/09-VALIDATION.md
@.planning/phases/09-live-html-harness/09-PATTERNS.md
@.planning/phases/09-live-html-harness/09-01-PLAN.md
@.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md
@tests/conftest.py
@tests/unit/test_goldapple_microdata_parser.py
@src/ga_crawler/parsers/goldapple_microdata.py
@src/ga_crawler/parsers/viled_nextdata.py
@src/ga_crawler/fetchers/goldapple.py
@src/ga_crawler/fetchers/viled.py

<interfaces>
<!-- Parser API consumed by drift tests (verbatim from Phase 8 fixed parsers) -->

From `src/ga_crawler/parsers/goldapple_microdata.py` (Phase 8 D-805/D-806):
```python
from dataclasses import dataclass

@dataclass
class GoldappleRawProduct:
    sku_id: str
    url: str
    name: str
    brand_raw: str            # h1 .brand text (Phase 8 fix)
    current_price: int
    was_price: int | None
    currency: str
    availability: str
    raw_volume_text: str | None  # Phase 8 PARSE-FIX-01 selectolax 0.4 Lexbor ОБЪЁМ extraction
    # ... + other fields

def parse_pdp(html: str, url: str) -> GoldappleRawProduct | None:
    ...
```

From `src/ga_crawler/parsers/viled_nextdata.py` (Phase 8 PARSE-FIX-03):
```python
def parse_pdp(html: str, url: str) -> ViledRawProduct | None:
    """Returns ViledRawProduct with volume_raw extracted from
    props.pageProps.attributes[0].attributes[].name == "Размер" (D-814).
    Contre-Jour legitimately returns volume_raw=None."""
    ...
```

From `src/ga_crawler/fetchers/goldapple.py` (existing Camoufox-direct fetcher):
```python
class GoldappleFetcher:
    async def __aenter__(self) -> "GoldappleFetcher": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...
    _page: Any   # playwright Page instance

    async def fetch_one(self, page, url: str) -> dict:
        """Returns {'html': str, 'status': int, 'title': str, ...}."""
```

From `src/ga_crawler/fetchers/viled.py` (existing curl_cffi fetcher):
```python
class ViledFetcher:
    def fetch_one(self, url: str) -> dict:
        """Sync curl_cffi fetch. Returns {'html': str, 'status': int, ...}."""
```

From `tests/conftest.py` (after 09-01 lands):
```python
def pytest_addoption(parser): ...
@pytest.fixture
def refresh_live(request) -> bool: ...
@pytest.fixture
def html_snapshot(snapshot): ...  # syrupy wrapper, HTMLSnapshotExtension
```

From `tests/_html_normalize.py` (from 09-01):
```python
def normalize_for_snapshot(html: str) -> str: ...
```
</interfaces>

<exact_urls_per_phase_8_smoke_rotation>
Per `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` L57-61:
- STEREOTYPE: https://goldapple.kz/19000440474-stereotype-sago
- Armani Code: https://goldapple.kz/19000195723-armani-code
- Viled Contre-Jour: https://viled.kz/item/408872
</exact_urls_per_phase_8_smoke_rotation>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Ship tests/live/__init__.py + tests/live/test_parser_drift.py with 3 cassette-replay drift tests (RED-first)</name>
  <files>
    tests/live/__init__.py,
    tests/live/test_parser_drift.py
  </files>
  <read_first>
    - 09-RESEARCH.md §5.1 (pytest -m live collection semantics — pytestmark module-level marker)
    - 09-RESEARCH.md §5.2 (refresh_live fixture branch — verbatim test skeleton)
    - 09-PATTERNS.md lines 706-792 (tests/live/test_parser_drift.py analog + cross-references)
    - 09-CONTEXT.md D-906 (two-mode harness contract)
    - 09-CONTEXT.md D-905 (operator-only opt-in; NO cron wiring)
    - .claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md L19-22 (h1 .brand/.name selectors), L39-40 (D-816 invariant SOFTENED — log-only)
    - src/ga_crawler/parsers/goldapple_microdata.py (verify GoldappleRawProduct field names: `brand_raw`, `raw_volume_text`)
    - src/ga_crawler/parsers/viled_nextdata.py (verify ViledRawProduct field names)
    - tests/unit/test_goldapple_microdata_parser.py:1-60 (parse-and-assert shape analog)
  </read_first>
  <behavior>
    - Test 1 (`test_goldapple_stereotype_cassette`): Cassette-replay parses `_live-2026-05-13-stereotype.html`; asserts product not None, brand="Stereotype", name="SAĜO", volume_raw non-empty, current_price > 0
    - Test 2 (`test_goldapple_armani_code_cassette`): Cassette-replay parses `_live-2026-05-13-armani-code.html`; asserts product not None, brand="Armani", name="armani code", current_price > 0. Brand IS substring of name (Bug #2 evidence) — invariant `brand.lower() not in name.lower()` is INTENTIONALLY SOFTENED per SKILL.md L40 + Phase 8 D-816 (log-only canary, NOT hard assert)
    - Test 3 (`test_viled_contre_jour_cassette`): Cassette-replay parses `_live-2026-05-13-contre-jour.html`; asserts product not None, brand non-empty, name non-empty, current_price > 0. volume_raw legitimately may be None (D-904 viled-relaxed evidence)
    - Module marker: `pytestmark = pytest.mark.live` so all tests are deselected by default `pytest -x -m "not live"`
    - Cassette-replay mode does NOT touch network: tests with `refresh_live=False` complete without GoldappleFetcher/ViledFetcher instantiation
  </behavior>
  <action>
    **First — verify exact parser API names by reading the source files.**

    1. Read `src/ga_crawler/parsers/goldapple_microdata.py` lines 1-80 to confirm: (a) function is `parse_pdp(html: str, url: str)`, (b) returned dataclass field names are `brand_raw`, `name`, `raw_volume_text`, `current_price`. If field names differ, use the ACTUAL names found in source (do NOT invent).
    2. Read `src/ga_crawler/parsers/viled_nextdata.py` lines 1-80 to confirm equivalent for viled side. Note expected field names for `ViledRawProduct`.

    **RED step — write the test file before any production-code consumer changes.**

    3. Create `tests/live/__init__.py` (empty file with single docstring):
    ```python
    """Phase 9 live-drift tests. Opt-in via `pytest -m live`. D-905 operator-only."""
    ```

    4. Create `tests/live/test_parser_drift.py` (cassette-replay branch only in this task; --refresh-live branch in Task 2):
    ```python
    """TH-03 live parser-drift harness — cassette-replay mode.

    Two modes documented per D-906 (--refresh-live branch in Task 2):
      - default `pytest -m live`: cassette-replay against 3 Phase 8 fixtures
      - `pytest -m live --refresh-live`: Camoufox/curl_cffi re-fetch + syrupy diff

    Retroactively locks Phase 8 parser fixes (PARSE-FIX-01..03) — if goldapple
    HTML shape drifts so brand merges back into name, or volume_raw nulls
    return, these tests fail loud (the "would have caught run #13" guarantee).

    D-905: operator-only opt-in; NO cron wiring; weekly-run.sh unchanged.
    """

    from __future__ import annotations

    from pathlib import Path

    import pytest

    from ga_crawler.parsers.goldapple_microdata import parse_pdp as parse_goldapple
    from ga_crawler.parsers.viled_nextdata import parse_pdp as parse_viled

    pytestmark = pytest.mark.live  # RESEARCH §5.1 — applies to ALL tests in module

    _FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
    _GA_FIXTURES = _FIXTURES / "goldapple"
    _VL_FIXTURES = _FIXTURES / "viled"


    # ---- Goldapple STEREOTYPE drift test (Bug #1 retroactive lock) ----

    def test_goldapple_stereotype_cassette(refresh_live: bool) -> None:
        """STEREOTYPE / SAĜO PDP — Bug #1 evidence; volume present, distinct brand+name."""
        if refresh_live:
            pytest.skip("--refresh-live mode handled in test_*_refresh tests (Task 2)")
        url = "https://goldapple.kz/19000440474-stereotype-sago"
        html = (_GA_FIXTURES / "_live-2026-05-13-stereotype.html").read_text("utf-8")
        product = parse_goldapple(html, url)
        assert product is not None, "STEREOTYPE PDP must parse non-None"
        assert product.brand_raw, "brand_raw must be non-empty (Phase 8 D-806 h1 .brand fix)"
        assert product.name, "name must be non-empty (Phase 8 D-806 h1 .name fix)"
        assert product.raw_volume_text, "raw_volume_text must be non-empty (Phase 8 PARSE-FIX-01)"
        assert product.current_price > 0
        assert product.brand_raw.strip().lower() not in product.name.strip().lower(), (
            "Bug #1 lock — STEREOTYPE brand must NOT be substring of name "
            "(invariant holds for stereotype-style PDPs; softened to log-only "
            "for armani-style — see test_goldapple_armani_code_cassette)"
        )


    # ---- Goldapple Armani Code drift test (Bug #2 retroactive lock; SOFTENED invariant) ----

    def test_goldapple_armani_code_cassette(refresh_live: bool) -> None:
        """Armani Code PDP — brand is legitimate substring of name (upstream data
        redundancy). SKILL.md L40 + Phase 8 D-816: brand-in-name invariant
        SOFTENED to log-only canary; NO hard assert here."""
        if refresh_live:
            pytest.skip("--refresh-live mode handled in test_*_refresh tests (Task 2)")
        url = "https://goldapple.kz/19000195723-armani-code"
        html = (_GA_FIXTURES / "_live-2026-05-13-armani-code.html").read_text("utf-8")
        product = parse_goldapple(html, url)
        assert product is not None, "armani-code PDP must parse non-None"
        assert product.brand_raw, "brand_raw must be non-empty (Phase 8 D-806)"
        assert product.name, "name must be non-empty (Phase 8 D-806)"
        assert product.current_price > 0
        # raw_volume_text: armani-code DOES have volume block per SKILL.md (Armani 75 мл)
        assert product.raw_volume_text, "raw_volume_text must be non-empty"
        # NOTE: brand_raw.lower() IS substring of name.lower() — this is the
        # canonical Bug #2 case; D-816 SOFTENED the invariant. No hard assert
        # against substring here (would block runs on legitimate data per SKILL).


    # ---- Viled Contre-Jour drift test (Bug #3 — legitimate-None volume_raw) ----

    def test_viled_contre_jour_cassette(refresh_live: bool) -> None:
        """Frederic Malle Contre-Jour PDP — D-904 viled-relaxed evidence:
        `Размер` attribute legitimately absent => volume_raw=None must NOT fail."""
        if refresh_live:
            pytest.skip("--refresh-live mode handled in test_*_refresh tests (Task 2)")
        url = "https://viled.kz/item/408872"
        html = (_VL_FIXTURES / "_live-2026-05-13-contre-jour.html").read_text("utf-8")
        product = parse_viled(html, url)
        assert product is not None, "Contre-Jour PDP must parse non-None"
        assert product.brand_raw or getattr(product, "brand", None), "brand must be non-empty"
        assert product.name, "name must be non-empty"
        assert product.current_price > 0
        # volume_raw legitimately None per D-814/D-904 viled-relaxed; no assertion
        # against non-empty. Just confirm parser does NOT raise on None.
    ```

    **NOTE:** When reading Step 1, confirm `ViledRawProduct` field name for brand (likely `brand_raw` mirroring goldapple, but may be `brand`). Use the ACTUAL field name. The `or getattr` line above is defensive.

    5. Run `uv run pytest tests/live/test_parser_drift.py -m live -x` — MUST initially fail RED if any field name is wrong; iterate field-name corrections only (not assertion logic).
    6. Once field names correct, GREEN. Commit: `feat(09-02a): tests/live/test_parser_drift.py cassette-replay mode (TH-03a, D-906)`.
    7. Run `uv run pytest -x -m "not live"` — confirm baseline NOT affected (these tests deselected).
    8. Run `uv run pytest -x -m live` — confirm all 3 tests green in cassette mode.
  </action>
  <verify>
    <automated>uv run pytest -m live tests/live/test_parser_drift.py -x</automated>
  </verify>
  <done>
    - `tests/live/__init__.py` exists
    - `tests/live/test_parser_drift.py` exists with `pytestmark = pytest.mark.live`
    - 3 cassette-replay tests green (stereotype, armani-code, viled-contre-jour)
    - `pytest -x -m "not live"` baseline unchanged
    - `pytest -m live` runs 3 tests green in <15s (no network)
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add --refresh-live branch to drift tests (Camoufox + curl_cffi re-fetch + syrupy diff)</name>
  <files>
    tests/live/test_parser_drift.py
  </files>
  <read_first>
    - 09-RESEARCH.md §5.2 (refresh_live fixture branch — verbatim skeleton)
    - 09-RESEARCH.md §7.1 (normalize_for_snapshot landmine — apply BEFORE syrupy diff)
    - 09-CONTEXT.md D-906 (two-mode contract — --refresh-live + --snapshot-update operator combo)
    - 09-PATTERNS.md lines 706-792 (refresh_live branch detail per fixture)
    - src/ga_crawler/fetchers/goldapple.py (GoldappleFetcher async context manager + fetch_one)
    - src/ga_crawler/fetchers/viled.py (ViledFetcher sync fetch_one)
    - tests/_html_normalize.py (normalize_for_snapshot from 09-01)
  </read_first>
  <behavior>
    - `pytest -m live --refresh-live` triggers the refresh branch in all 3 tests
    - The refresh branch uses `GoldappleFetcher` (async) for goldapple, `ViledFetcher` (sync) for viled — verbatim, no new fetcher code
    - The refresh branch applies `normalize_for_snapshot(html)` BEFORE comparing to syrupy `html_snapshot`
    - With `--refresh-live --snapshot-update`, syrupy creates the snapshot file fresh on first run; subsequent runs diff against it
    - The refresh branch is EXPLICITLY GUARDED by `if refresh_live:` — default invocation (`pytest -m live` without flag) does NOT execute fetcher code path
  </behavior>
  <action>
    1. Edit `tests/live/test_parser_drift.py`. Replace the three `pytest.skip("--refresh-live mode handled...")` stubs with actual refresh-mode logic.

    For **`test_goldapple_stereotype_cassette`** — RENAME to `test_goldapple_stereotype_drift` (drop `_cassette` suffix since now handles both modes) and replace body:
    ```python
    @pytest.mark.asyncio
    async def test_goldapple_stereotype_drift(refresh_live: bool, html_snapshot) -> None:
        """STEREOTYPE / SAĜO PDP. Two-mode (D-906)."""
        url = "https://goldapple.kz/19000440474-stereotype-sago"
        fixture_path = _GA_FIXTURES / "_live-2026-05-13-stereotype.html"

        if refresh_live:
            from ga_crawler.fetchers.goldapple import GoldappleFetcher
            from tests._html_normalize import normalize_for_snapshot

            async with GoldappleFetcher(run_id=-1, headless=True) as fetcher:
                rec = await fetcher.fetch_one(fetcher._page, url)
            normalized = normalize_for_snapshot(rec["html"])
            # Syrupy default behavior: missing snapshot fails (T-09-SOUND);
            # `--snapshot-update` regenerates. RESEARCH §3.2.
            assert normalized == html_snapshot
            # After refresh round-trip succeeds (or --snapshot-update),
            # we still parse from disk fixture to assert invariants below:
            html = fixture_path.read_text("utf-8")
        else:
            html = fixture_path.read_text("utf-8")

        product = parse_goldapple(html, url)
        assert product is not None
        assert product.brand_raw
        assert product.name
        assert product.raw_volume_text  # PARSE-FIX-01 lock
        assert product.current_price > 0
        assert product.brand_raw.strip().lower() not in product.name.strip().lower()
    ```

    Apply analogous transformation to `test_goldapple_armani_code_drift` (drop the brand-not-in-name assertion per SKILL.md D-816 softening; otherwise identical pattern with `https://goldapple.kz/19000195723-armani-code` + `_live-2026-05-13-armani-code.html`).

    For `test_viled_contre_jour_drift`:
    ```python
    def test_viled_contre_jour_drift(refresh_live: bool, html_snapshot) -> None:
        """Frederic Malle Contre-Jour PDP. Two-mode (D-906)."""
        url = "https://viled.kz/item/408872"
        fixture_path = _VL_FIXTURES / "_live-2026-05-13-contre-jour.html"

        if refresh_live:
            from ga_crawler.fetchers.viled import ViledFetcher
            from tests._html_normalize import normalize_for_snapshot

            rec = ViledFetcher().fetch_one(url)
            normalized = normalize_for_snapshot(rec["html"])
            assert normalized == html_snapshot
            html = fixture_path.read_text("utf-8")
        else:
            html = fixture_path.read_text("utf-8")

        product = parse_viled(html, url)
        assert product is not None
        # ... (rest same as Task 1 body) ...
    ```

    **CRITICAL — DO NOT actually execute --refresh-live in this task.** Verifying the cassette-replay branch is sufficient for CI green; the refresh branch is operator-only (D-905) and would require Camoufox + KZ-IP + ~30s wallclock per test. The task's automated verify is `pytest -m live -x` (default mode), which exercises the `else:` branch.

    2. Run `uv run pytest -m live tests/live/test_parser_drift.py -x` — MUST stay green (cassette-replay branch unchanged in semantics).
    3. (Manual operator verification, OUT OF SCOPE for this task) Operator may later run `uv run pytest -m live --refresh-live --snapshot-update tests/live/test_parser_drift.py -x` to bootstrap snapshots — outside automated CI.
    4. Commit: `feat(09-02a): TH-03b refresh-live branch via Camoufox/curl_cffi + normalize (D-906)`.
  </action>
  <verify>
    <automated>uv run pytest -m live tests/live/test_parser_drift.py -x</automated>
  </verify>
  <done>
    - 3 drift tests carry both cassette-replay and --refresh-live code paths
    - Cassette-replay still green
    - `if refresh_live:` branch references `GoldappleFetcher` / `ViledFetcher` / `normalize_for_snapshot` correctly (grep canary)
    - No regression in `pytest -x -m "not live"` baseline
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Ship tests/test_snapshot_soundness.py — missing-snapshot fails loudly (T-09-SOUND)</name>
  <files>
    tests/test_snapshot_soundness.py
  </files>
  <read_first>
    - 09-RESEARCH.md §3.2 (missing-snapshot is FAILURE by default in syrupy 4.x; no --strict flag)
    - 09-VALIDATION.md row TH-03c (negative test specification)
    - 09-PATTERNS.md lines 441-466 (test_snapshot_soundness.py analog)
    - 09-CONTEXT.md D-906 (soundness rule expectation)
  </read_first>
  <behavior>
    - Test 1: When syrupy is asked to compare against a snapshot that does NOT exist on disk, the assertion FAILS (raises AssertionError or `pytest.fail`) — NOT silently passes
    - Test 2: The test does NOT depend on Camoufox or `--refresh-live`; it constructs a synthetic syrupy assertion against a guaranteed-missing snapshot name
  </behavior>
  <action>
    1. Create `tests/test_snapshot_soundness.py`. The challenge: syrupy auto-creates snapshots on `--snapshot-update`, so we need a deterministic way to assert that a missing snapshot causes a failure.

    Approach: Use a unique snapshot name (UUID-based) that we GUARANTEE does not exist on disk; assert against the `html_snapshot` fixture; capture the resulting failure via a subprocess `pytest` invocation OR a `try/except` against syrupy's internal exception.

    Simplest approach — subprocess invocation (proves CI-level behavior):
    ```python
    """TH-03c — syrupy missing-snapshot fails CI loudly (T-09-SOUND).

    D-906 soundness rule: `assert actual == snapshot` MUST fail if snapshot file
    is absent, not silently pass. This negative test confirms the regression
    does NOT silently succeed.

    Implementation: spawn a child pytest invocation that targets a deliberately-
    missing snapshot name. Assert non-zero exit + assertion failure in output.
    """

    from __future__ import annotations

    import subprocess
    import sys
    import textwrap
    from pathlib import Path


    _CHILD_TEST = textwrap.dedent('''
        from __future__ import annotations
        import pytest
        from tests._snapshot_extension import HTMLSnapshotExtension

        @pytest.fixture
        def html_snapshot_local(snapshot):
            return snapshot.with_defaults(extension_class=HTMLSnapshotExtension)

        def test_missing_snapshot_fails(html_snapshot_local):
            """Snapshot with this unique name must NOT exist on disk — must fail."""
            assert "<html>deliberately-missing-snapshot-marker</html>" == html_snapshot_local
    ''')


    def test_syrupy_default_fails_on_missing_snapshot(tmp_path: Path) -> None:
        """Spawn subprocess pytest against a missing-snapshot test; assert exit !=0."""
        # Write the child test file into tmp_path so we don't pollute the repo
        # and so its snapshot dir is guaranteed empty.
        child_dir = tmp_path / "soundness_probe"
        child_dir.mkdir()
        (child_dir / "conftest.py").write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(Path.cwd()).encode('unicode_escape').decode()!r})\n",
            encoding="utf-8",
        )
        (child_dir / "test_missing_snapshot.py").write_text(_CHILD_TEST, encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-x", "-q", str(child_dir / "test_missing_snapshot.py")],
            capture_output=True, text=True, timeout=60,
            cwd=str(Path.cwd()),
        )
        # Default syrupy behavior must FAIL on missing snapshot.
        # Acceptable exit codes: 1 (test failed) or 2 (error). NOT 0 (silent pass).
        assert result.returncode != 0, (
            f"syrupy missing-snapshot did NOT fail (exit=0). "
            f"This breaks the T-09-SOUND soundness guarantee.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        # Confirm output mentions a missing or unused snapshot to make the
        # cause unambiguous (defends against accidental exit-1 from import errors).
        joined = (result.stdout + result.stderr).lower()
        # syrupy reports vary by version; accept any of these substrings.
        ok = (
            "snapshot does not exist" in joined
            or "no snapshot" in joined
            or "snapshot is missing" in joined
            or "assertionerror" in joined
        )
        assert ok, (
            f"subprocess failed but reason unclear (not a missing-snapshot signal):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    ```

    2. Run `uv run pytest tests/test_snapshot_soundness.py -x` — MUST pass: parent test passes because child test FAILS as expected.
    3. Commit: `test(09-02a): TH-03c missing-snapshot soundness negative test (T-09-SOUND)`.
    4. Run `uv run pytest -x -m "not live"` to confirm baseline + new soundness test all green.
  </action>
  <verify>
    <automated>uv run pytest tests/test_snapshot_soundness.py -x</automated>
  </verify>
  <done>
    - `tests/test_snapshot_soundness.py` exists
    - Subprocess approach proves syrupy fail-on-missing default
    - Parent test PASSES (child fails as expected)
    - No regression in default suite
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| frozen fixture → parser runtime | Cassette-replay assumes the fixture content matches a known-good shape |
| live re-fetch (Camoufox/curl_cffi) → syrupy diff | Live HTML carries rotating tokens; bytewise diff falsely positives without normalize |
| syrupy missing-snapshot path | Risk of silent skip = drift never caught |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-09-SOUND | Repudiation | syrupy missing-snapshot default | mitigate | `tests/test_snapshot_soundness.py` subprocess-spawns a child pytest with a deliberately-missing snapshot and asserts non-zero exit — proves CI-level fail-loud behavior every default suite run |
| T-09-DRIFT | False-positive drift | syrupy `assert html == html_snapshot` after live re-fetch | mitigate | `tests/_html_normalize.py:normalize_for_snapshot` (from 09-01) strips csrf-token, cf_clearance echoes, CSS build-hash, `__NEXT_DATA__.buildId` BEFORE syrupy diff. Refresh branch in all 3 drift tests imports + applies it |
| T-09-PII | Information disclosure | new `_live-*.html` fixtures captured via `--refresh-live --snapshot-update` | accept (mitigated upstream in 09-01) | 09-01's `_assert_fixture_clean` runs on every fixture load (including refreshed ones); standalone canary catches secret-laden commits before merge |
</threat_model>

<verification>
- `uv run pytest -m live tests/live/test_parser_drift.py -x` — 3 drift tests green in cassette mode
- `uv run pytest -x -m "not live"` — baseline still green (drift tests deselected by marker)
- `uv run pytest tests/test_snapshot_soundness.py -x` — soundness negative test green
- `grep -c "pytest.mark.live" tests/live/test_parser_drift.py` — at least 1 (module-level `pytestmark`)
- `grep -c "if refresh_live:" tests/live/test_parser_drift.py` — exactly 3 (one per drift test)
- `grep -c "normalize_for_snapshot" tests/live/test_parser_drift.py` — at least 3 (one import + 3 calls, or 3 inline imports — count flexible)
- `grep "from ga_crawler.fetchers" tests/live/test_parser_drift.py` — present (GoldappleFetcher + ViledFetcher imports in refresh branch)
</verification>

<success_criteria>
- `tests/live/__init__.py` exists (package marker)
- `tests/live/test_parser_drift.py` exists with 3 drift tests carrying `pytestmark = pytest.mark.live`
- Each drift test has `if refresh_live:` branch using fetcher + `normalize_for_snapshot` + syrupy `html_snapshot`; `else:` branch reads frozen fixture
- Cassette-replay tests pass against Phase 8 `_live-2026-05-13-*.html` fixtures
- `tests/test_snapshot_soundness.py` exists with subprocess proof of fail-on-missing default — TEST-HARNESS-03c, T-09-SOUND
- Phase 8 D-816 invariant softening respected: armani-code test does NOT hard-assert `brand not in name` (log-only canary)
- D-905 operator-only opt-in respected: no cron/CI wiring of `--refresh-live`
- Atomic RED/GREEN commit pairs (D-811 inheritance)
- `uv run pytest -x -m "not live"` GREEN with 09-01 + 09-02a (no live tests in default run)
- `uv run pytest -m live` GREEN (3 drift tests in cassette-replay; ~10s)
</success_criteria>

<output>
After completion, create `.planning/phases/09-live-html-harness/09-02a-SUMMARY.md` per `summary.md` template:
- Wave executed: 1 (parallel-A; depends_on [09-01])
- Requirements closed: TEST-HARNESS-03 (a, b wiring, c soundness)
- Files created: 3 (tests/live/__init__.py, tests/live/test_parser_drift.py, tests/test_snapshot_soundness.py)
- Files modified: 0 (production code untouched — testing-only plan)
- Time-stamp last GREEN commit (anchor for 09-03's D-902 P2 GO/NO-GO 8h gate measurement)
- Note: `--refresh-live` branch coded but NOT exercised in CI (operator-only per D-905); operator runbook in 09-03 README §8 will document the manual flow
</output>
