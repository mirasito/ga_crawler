# Phase 8: Parser Bug Fixes — Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 22 (5 production-touch + 6 new tests + 1 conftest extension + 4 spike artifacts + 1 skill + 1 pyproject + 4 doc-cascade)
**Analogs found:** 19 / 22 (3 spike artifacts copy from `.planning/spikes/01-goldapple/` mirror; doc cascade has structural-canary analog only)

---

## File Classification

| New/Modified File | Kind | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|------|-----------|----------------|---------------|
| `src/ga_crawler/parsers/goldapple_microdata.py` | Production (modify) | parser | transform (HTML→dict) | self (lines 254-267 `_extract_strikethrough` helper shape; lines 288-380 `parse_pdp` call-site) | exact (same file) |
| `src/ga_crawler/parsers/viled_nextdata.py` | Production (modify) | parser | transform (JSON→dict) | self (lines 86-111 `_map_stock_state` helper; lines 124-216 `parse_pdp` call-site at line 215) | exact (same file) |
| `src/ga_crawler/runner/gates.py` | Production (modify) | gate | pure-function predicate | self (lines 242-247 `final_threshold_gate`; lines 253-268 `parse_quality_gate`; lines 36-40 `SMOKE_URLS` constant) | exact (same file) |
| `src/ga_crawler/runner/stats.py` | Production (modify) | stats namespace | append-only tuple | self (lines 18-32 `GOLDAPPLE_STATS_KEYS`) | exact (same file) |
| `pyproject.toml` | Config (modify) | dep pin | n/a | self (line 23 selectolax pin) | exact (same file) |
| `tests/parsers/test_goldapple_volume_block.py` | Test (new) | parser test | request-response | `tests/unit/test_goldapple_microdata_parser.py` (lines 1-72 fixture-driven round-trip + synthetic HTML helper at lines 77-96) | exact (role + flow) |
| `tests/parsers/test_goldapple_brand_name.py` | Test (new) | parser test | request-response | `tests/unit/test_goldapple_microdata_parser.py` | exact |
| `tests/parsers/test_viled_volume_from_nextdata.py` | Test (new) | parser test | request-response | `tests/unit/test_viled_nextdata_parser.py` (lines 24-67 `_make_html_with_nextdata` + `_base_nextdata` synthetic builders) | exact |
| `tests/runner/test_parser_drift_gate.py` | Test (new) | gate test | pure predicate | `tests/unit/test_parse_quality_gate.py` (full file — boundary + threshold parametrize) | exact |
| `tests/integration/test_phase8_synthetic_regression.py` | Test (new) | orchestrator integration | DB-state assertion | `tests/integration/test_matcher_run.py` (lines 42-80 in-memory engine + run-writer + planting helpers) | role-match |
| `tests/runner/test_smoke_urls_rotation.py` | Test (new) | structural canary | constant assertion | `tests/unit/test_smoke_probe.py` (lines 13-27 `test_smoke_urls_constant_shape` + `test_smoke_urls_exclude_stale_row_0`) | exact |
| `tests/conftest.py` (extension) | Test infra (modify) | fixture loader | session-scoped read | self (lines 28-37 `goldapple_pdp_html`; lines 164-189 viled trio) | exact (same file) |
| `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` | Test fixture (new) | raw HTML | static | `tests/fixtures/goldapple/_debug-product-page.html` | exact placement |
| `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` | Test fixture (new) | raw HTML | static | same | exact |
| `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` | Test fixture (new) | raw HTML | static | `tests/fixtures/viled/viled-pdp-discounted.html` | exact placement |
| `.planning/spikes/v1.1-brand-name-shapes/MEMO.md` | Spike artifact (new) | decision memo | static | `.planning/spikes/01-goldapple/MEMO.md` (lines 1-40 frontmatter + TL;DR + Options-tested table) | role-match |
| `.planning/spikes/v1.1-brand-name-shapes/shape-table.md` | Spike artifact (new) | survey table | static | (no exact analog — table convention only); structurally similar to `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` evidence tables | no-analog (use RESEARCH.md template) |
| `.planning/spikes/v1.1-brand-name-shapes/pdp-NN-*.html` ×30 | Spike artifact (new) | raw captures | static | `.planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html` | exact |
| `scripts/capture_spike_pdps.py` (ad-hoc) | Spike script (new) | one-shot capture | streaming I/O | `src/ga_crawler/fetchers/goldapple.py` (entire `GoldappleFetcher` class — verbatim consumer, not a re-implementation) | role-match (verbatim reuse) |
| `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` | Skill (new) | reference index | static | `.claude/skills/spike-01-goldapple/SKILL.md` (full file) | exact |
| `.planning/REQUIREMENTS.md`, `PROJECT.md`, `ROADMAP.md`, `STATE.md` | Doc (modify) | doc cascade | static | self (each existing file) | no-analog (doc updates are file-specific) |

---

## Pattern Assignments

### `src/ga_crawler/parsers/goldapple_microdata.py` (parser, transform) — Plans 08-02 + 08-03

**Analog:** self, plus selectolax 0.4 Lexbor docs (RESEARCH.md §"selectolax 0.4 Lexbor")

**Existing module-level helper pattern** (lines 254-267, copy this shape for `_extract_volume_block`):
```python
def _extract_strikethrough(tree: HTMLParser) -> Optional[int]:
    """First StrikethroughPrice in priceSpecification -> was_price.

    Source: 03-RESEARCH.md §Pattern 4 lines 580-590 (verbatim).
    """
    for spec in tree.css('[itemprop="priceSpecification"]'):
        ptype = spec.css_first('link[itemprop="priceType"]')
        if ptype and "StrikethroughPrice" in (ptype.attributes.get("href", "") or ""):
            p = spec.css_first('meta[itemprop="price"]')
            if p:
                v = (p.attributes.get("content") or "").strip()
                if v.isdigit():
                    return int(v)
    return None
```

**NEW helper to insert near line 268** (after `_extract_strikethrough`, before `_extract_availability`) — per RESEARCH.md §"goldapple PDP shape" Bug #1:
```python
def _extract_volume_block(html: str) -> Optional[str]:
    """Extract goldapple PDP structured volume block (e.g. '78 ОБЪЁМ / МЛ').

    Uses selectolax 0.4 Lexbor backend (CONTEXT.md D-806 — Lexbor import is
    LOCAL to this helper). Returns the raw composed text the volume label is
    adjacent to, for downstream NORM-03 parse_volume to consume.

    Source: 08-RESEARCH.md §"selectolax 0.4 Lexbor".
    """
    from selectolax.lexbor import LexborHTMLParser  # local import per D-806

    tree = LexborHTMLParser(html)
    label_nodes = tree.css('div:lexbor-contains("ОБЪЁМ" i)')
    if not label_nodes:
        return None
    label = label_nodes[0]
    parent = label.parent
    if parent is None:
        return None
    for sibling in parent.iter():  # element-only, skips text nodes
        if sibling is label:
            continue
        text = (sibling.text(deep=False, strip=True) or "")
        if text and any(c.isdigit() for c in text):
            label_text = (label.text(deep=False, strip=True) or "ОБЪЁМ / МЛ")
            return f"{text} {label_text}"
    composed = (label.text(deep=True, strip=True) or "")
    if any(c.isdigit() for c in composed):
        return composed
    return None
```

**Brand+name microdata read** (Plan 08-03) — existing brand pattern (lines 318-324) is the template; product-level name follows the same `meta[itemprop="name"]` shape, but rooted at the product `itemscope`:
```python
# EXISTING (keep verbatim — brand read works)
brand_raw = ""
brand_node = tree.css_first('[itemprop="brand"]')
if brand_node is not None:
    brand_meta = brand_node.css_first('meta[itemprop="name"]')
    if brand_meta is not None:
        brand_raw = (brand_meta.attributes.get("content") or "").strip()

# NEW (Plan 08-03) — product-level meta sibling, excluding brand's nested name
product_scope = None
if brand_node is not None:
    cursor = brand_node.parent
    while cursor is not None:
        if (cursor.attributes.get("itemscope") is not None
                and "Product" in (cursor.attributes.get("itemtype", "") or "")):
            product_scope = cursor
            break
        cursor = cursor.parent

name_meta = None
if product_scope is not None:
    for meta in product_scope.css('meta[itemprop="name"]'):
        # Skip the brand's nested name
        anc = meta.parent
        in_brand = False
        while anc is not None and anc != product_scope:
            if anc.attributes.get("itemprop") == "brand":
                in_brand = True
                break
            anc = anc.parent
        if not in_brand:
            name_meta = meta
            break

name = (name_meta.attributes.get("content").strip() if name_meta else "")
# Fallback (decide in Plan 08-03 after W0 spike data):
if not name:
    h1 = tree.css_first("h1")
    if h1 is not None:
        name = h1.text(strip=True)  # legacy path (concat risk)
```

**Call-site replacement at line 358-359** (Plan 08-02):
```python
# BEFORE (current, line 358-359):
# Volume passthrough - Phase 2 NORM-03 owns regex extraction
raw_volume_text = name or None

# AFTER:
# Volume extraction (PARSE-FIX-01) — try structured block first, fall back to name passthrough
raw_volume_text = _extract_volume_block(html) or name or None
```

**Invariant canary** (Plan 08-03 — per CONTEXT.md D-816, do NOT replace gate; insert after name extracted):
```python
# Per-SKU brand-canary invariant (D-816)
if brand_raw and name and brand_raw.lower() in name.lower():
    log.warning(
        "goldapple_brand_in_name_canary_violation",
        brand_raw=brand_raw, name=name, url=url,
    )
    # The canary logs only — gate at runner level enforces aggregate.
    # (Plan 08-03 may choose `return None` instead — decide per W0 evidence.)
```

---

### `src/ga_crawler/parsers/viled_nextdata.py` (parser, transform) — Plan 08-04

**Analog:** self (lines 86-111 `_map_stock_state` helper shape; line 215 callsite)

**Existing module-level helper pattern** (lines 86-111, copy this shape for `_extract_volume_from_nextdata`):
```python
def _map_stock_state(item: dict) -> str:
    """D-217 mapping; per 02-WAVE0-PROBE.md §A1 REVISED.

    Stock-state is derived from `item.count` (inventory int) and
    `item.purchaseType` (string enum):
      - count > 0 AND purchaseType == "ONLINE"   → IN_STOCK
      - count > 0 AND purchaseType == "PREORDER" → UNAVAILABLE
      - count == 0                                → OUT_OF_STOCK
      - count missing / non-int                  → UNKNOWN
    """
    count = item.get("count")
    purchase_type = item.get("purchaseType")
    if not isinstance(count, int):
        return "UNKNOWN"
    if count == 0:
        return "OUT_OF_STOCK"
    if purchase_type == "PREORDER":
        return "UNAVAILABLE"
    return "IN_STOCK"
```

**NEW helper to insert near line 111** (after `_map_stock_state`, before `_coerce_int`) — per RESEARCH.md §"viled NextData attributes":
```python
def _extract_volume_from_nextdata(a0: dict) -> Optional[str]:
    """Extract raw volume text from viled __NEXT_DATA__ price-variant attributes.

    Reads the nested descriptive-attributes array at:
        props.pageProps.attributes[0].attributes[]
    and returns the first entry whose name matches Размер / объем / объём
    (case-insensitive, whitespace-stripped).

    Returns the raw value (e.g. "50 мл", "S") or None when absent. The
    downstream NORM-03 normalizer (parse_volume) handles disambiguation
    of clothing sizes ("S" → None) vs volumes ("50 мл" → Volume(50,ml,1)).

    Source: 08-RESEARCH.md §"viled NextData attributes" (verified against
    all 3 in-repo fixtures: viled-pdp-407682, multipack, discounted).
    """
    descriptive = a0.get("attributes")
    if not isinstance(descriptive, list):
        return None
    for entry in descriptive:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip().lower()
        if name in ("размер", "объем", "объём"):
            value = entry.get("value")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None
```

**Call-site replacement at line 215** (Plan 08-04):
```python
# BEFORE (current, line 215):
raw_volume_text=name,  # NORM-03 extracts volume regex from full name

# AFTER:
raw_volume_text=_extract_volume_from_nextdata(a0) or name,  # PARSE-FIX-03
```

---

### `src/ga_crawler/runner/gates.py` (gate, pure-predicate) — Plan 08-05

**Analog:** self (lines 242-247 `final_threshold_gate`, lines 253-268 `parse_quality_gate` — both retailer-agnostic D-203 helpers)

**Existing D-203 helper pattern** (lines 253-268, copy this shape for `parser_drift_null_rate_gate`):
```python
def parse_quality_gate(
    null_rate_required_fields: float,
    *,
    threshold: float = 0.05,
) -> bool:
    """D-218: returns True iff null_rate <= threshold (gate PASSES).

    null_rate_required_fields = (rows where name OR current_price OR url is NULL)
                              / total_count

    >5% null rate → run marked failed with reason='parse_quality_below_threshold'.
    Threshold inclusive (≤): exactly 5% passes; 5.01% fails.

    Source: 02-CONTEXT.md D-218; 02-RESEARCH.md §Pattern 1 PARSE-05.
    """
    return null_rate_required_fields <= threshold
```

**NEW helper to insert after line 268** (after `parse_quality_gate`, before backward-compat shims) — per RESEARCH.md §"PARSE-FIX-04 Null-Rate Gate":
```python
from dataclasses import dataclass  # add to imports at line ~17 if not present


@dataclass(frozen=True)
class ParserDriftGateResult:
    """Result of the PARSE-FIX-04 null-rate sanity gate.

    Fields:
      passed: True if both volume and brand null rates are at-or-below threshold.
      volume_null_rate: float in [0, 1].
      brand_null_rate:  float in [0, 1].
      failure_reason:   None if passed; otherwise one of:
        - "parser_drift_null_volume_rate"
        - "parser_drift_null_brand_rate"
    """
    passed: bool
    volume_null_rate: float
    brand_null_rate: float
    failure_reason: Optional[str]


def parser_drift_null_rate_gate(
    volume_null_rate: float,
    brand_null_rate: float,
    *,
    threshold: float = 0.5,
) -> ParserDriftGateResult:
    """D-815: PARSE-FIX-04 sanity gate for goldapple parser drift.

    Returns passed=False if EITHER volume_null_rate > threshold OR
    brand_null_rate > threshold. Picks failure_reason via priority:
    volume first (most-impactful for match-rate), brand second.

    Threshold semantics: STRICT GREATER-THAN (`> 0.5` fails, exactly 0.5 passes).

    Source: 08-CONTEXT.md D-813/D-814/D-815/D-816/D-817.
    """
    v_fail = volume_null_rate > threshold
    b_fail = brand_null_rate > threshold
    if v_fail:
        reason: Optional[str] = "parser_drift_null_volume_rate"
    elif b_fail:
        reason = "parser_drift_null_brand_rate"
    else:
        reason = None
    return ParserDriftGateResult(
        passed=(not v_fail and not b_fail),
        volume_null_rate=volume_null_rate,
        brand_null_rate=brand_null_rate,
        failure_reason=reason,
    )
```

**Add to `__all__` at line 308-318:**
```python
__all__ = [
    "SMOKE_URLS",
    "load_smoke_urls_from_config",
    "smoke_probe",
    "auto_suggest_threshold",
    "final_threshold_gate",
    "parse_quality_gate",
    "parser_drift_null_rate_gate",   # NEW
    "ParserDriftGateResult",         # NEW
    "final_m_gate",
    "final_n_gate",
    "auto_suggest_m",
]
```

**SMOKE_URLS rotation at lines 36-40** (Plan 08-05, per D-818 — exact URLs deferred to post-W0 spike output):
```python
# BEFORE (current, lines 36-40):
SMOKE_URLS: tuple[str, ...] = (
    "https://goldapple.kz/19000488678-givenchy-irresistible",
    "https://goldapple.kz/7681000001-givenchy-pour-homme-blue-label",
    "https://goldapple.kz/19000032744-givenchy-gentleman-reserve-privee-eau-de-parfum",
)

# AFTER (Plan 08-05, after W0 spike supplies real URLs):
# Rotation 2026-05-13 (v1.1 Phase 8 D-818): 1 URL per shape variant to
# catch the run-#13 parser-drift mode (single-shape Givenchy baseline
# masked STEREOTYPE/Armani breakage). URLs sourced from W0 shape-table.md.
SMOKE_URLS: tuple[str, ...] = (
    "https://goldapple.kz/<TODO-STEREOTYPE-FROM-SHAPE-TABLE>",       # STEREOTYPE-style
    "https://goldapple.kz/<TODO-ARMANI-FROM-SHAPE-TABLE>",           # Armani-style
    "https://goldapple.kz/19000488678-givenchy-irresistible",        # Givenchy-baseline (kept)
)
```

---

### `src/ga_crawler/runner/stats.py` (stats namespace, append-only) — Plan 08-05

**Analog:** self (lines 18-32 `GOLDAPPLE_STATS_KEYS`)

**Existing 13-key namespace** (lines 18-32):
```python
GOLDAPPLE_STATS_KEYS: tuple[str, ...] = (
    "goldapple.fetch_count",
    "goldapple.fetch_failures",
    "goldapple.gate_shell_count",
    "goldapple.stale_count",
    "goldapple.parse_failures",
    "goldapple.unmatched_viled_brands",
    "goldapple.unmatched_goldapple_slugs_new",
    "goldapple.smoke_pass",
    "goldapple.smoke_diagnostics",
    "goldapple.fetch_duration_seconds",
    "goldapple.mean_fetch_seconds",
    "goldapple.camoufox_version",
    "goldapple.auto_suggest_m",
)
```

**Extension** (Plan 08-05, add 3 keys — per RESEARCH.md §"New Stats Keys"):
```python
GOLDAPPLE_STATS_KEYS: tuple[str, ...] = (
    # ... existing 13 keys ...
    "goldapple.volume_null_rate",            # NEW PARSE-FIX-04 (float in [0,1])
    "goldapple.brand_null_rate",             # NEW PARSE-FIX-04 (float in [0,1])
    "goldapple.parser_drift_failure_reason", # NEW PARSE-FIX-04 (str or None)
)
```

**Coupled test update** — `tests/unit/test_stats_namespace.py:14-16` `test_namespace_has_13_keys` MUST flip to 16 and parametrize block at line 24-38 MUST gain 3 entries.

---

### `pyproject.toml` (dep pin, modify) — Plan 08-02 W1 first task

**Existing pin** (line 23):
```toml
"selectolax>=0.3,<0.4",
```

**Replacement** (per CONTEXT.md D-805):
```toml
"selectolax>=0.4.7,<0.5",
```

**Coupled command** (run after edit):
```bash
uv lock --upgrade-package selectolax && uv sync
```

---

### `tests/parsers/test_goldapple_volume_block.py` (test, new) — Plan 08-02 W1

**Analog:** `tests/unit/test_goldapple_microdata_parser.py` (full file shape)

**Imports + fixture-driven assertion pattern** (analog lines 1-29):
```python
"""Goldapple _extract_volume_block helper tests — PARSE-FIX-01.

RED → GREEN per Plan 08-02 strict TDD discipline (CONTEXT.md D-811).
Fixture-driven against tests/fixtures/goldapple/_live-2026-05-13-stereotype.html
which is committed in Plan 08-01 W0 spike output.
"""

from __future__ import annotations

import pytest

from ga_crawler.parsers.goldapple_microdata import (
    GoldappleRawProduct,
    _extract_volume_block,
    parse_pdp,
)

STEREOTYPE_URL = "https://goldapple.kz/<sago-url-from-shape-table>"


def test_extract_volume_block_on_live_stereotype(goldapple_pdp_html_live_stereotype: str) -> None:
    """STEREOTYPE PDP has the structured `[78] ОБЪЁМ / МЛ` flex-box block."""
    result = _extract_volume_block(goldapple_pdp_html_live_stereotype)
    assert result is not None
    assert any(c.isdigit() for c in result)
    assert "МЛ" in result.upper() or "мл" in result


def test_extract_volume_block_falls_back_on_givenchy_baseline(goldapple_pdp_html: str) -> None:
    """Givenchy fixture has NO separate volume block (embedded in title).
    `_extract_volume_block` returns None; caller's `or name` fallback covers it.
    """
    result = _extract_volume_block(goldapple_pdp_html)
    # Either None (no block) or contains digit + label — both acceptable.
    if result is not None:
        assert any(c.isdigit() for c in result)


def test_parse_pdp_yields_raw_volume_text_on_stereotype(goldapple_pdp_html_live_stereotype: str) -> None:
    """End-to-end: parse_pdp on STEREOTYPE fixture produces raw_volume_text
    that NORM-03 can downstream-parse into a non-None volume_norm."""
    product = parse_pdp(goldapple_pdp_html_live_stereotype, STEREOTYPE_URL)
    assert product is not None
    assert isinstance(product, GoldappleRawProduct)
    assert product.raw_volume_text is not None
    assert any(c.isdigit() for c in product.raw_volume_text)
```

---

### `tests/parsers/test_goldapple_brand_name.py` (test, new) — Plan 08-03 W1

**Analog:** `tests/unit/test_goldapple_microdata_parser.py` lines 20-61

**Invariant-canary + microdata-read pattern**:
```python
"""Goldapple brand+name microdata extraction tests — PARSE-FIX-02.

RED → GREEN per Plan 08-03 strict TDD. Fixture-driven against
_live-2026-05-13-stereotype.html and _live-2026-05-13-armani-code.html.
"""

from __future__ import annotations

import pytest

from ga_crawler.parsers.goldapple_microdata import GoldappleRawProduct, parse_pdp


def test_invariant_canary_armani(goldapple_pdp_html_live_armani: str) -> None:
    """Brand-canary: brand_raw.lower() MUST NOT be in name.lower() — protects
    against pre-v1.1 'Armaniarmani code' regression (CONTEXT.md D-816)."""
    p = parse_pdp(goldapple_pdp_html_live_armani, "https://goldapple.kz/<armani-code-url>")
    assert p is not None
    assert p.brand_raw.lower() not in p.name.lower(), (
        f"brand '{p.brand_raw}' contained in name '{p.name}' — parser regressed "
        f"to v1.0 <h1> concatenation"
    )


def test_stereotype_name_is_microdata_not_h1(goldapple_pdp_html_live_stereotype: str) -> None:
    """STEREOTYPE PDP: name must come from <meta itemprop="name"> ('sago'),
    NOT from <h1> ('STEREOTYPEsago')."""
    p = parse_pdp(goldapple_pdp_html_live_stereotype, "https://goldapple.kz/<sago-url>")
    assert p is not None
    assert p.name.lower() == "sago"
    assert "stereotype" not in p.name.lower()


def test_givenchy_baseline_still_parses(goldapple_pdp_html: str) -> None:
    """Backward-compat: existing Givenchy fixture (which doesn't exhibit concat)
    still yields a reasonable name. The microdata-primary path falls back to
    <h1> when <meta itemprop="name"> at product level is absent."""
    p = parse_pdp(goldapple_pdp_html, "https://goldapple.kz/7681000001-givenchy-pour-homme-blue-label")
    assert p is not None
    assert p.name  # non-empty
    assert "givenchy" not in p.name.lower()  # brand prefix removed or never present
```

---

### `tests/parsers/test_viled_volume_from_nextdata.py` (test, new) — Plan 08-04 W1

**Analog:** `tests/unit/test_viled_nextdata_parser.py` lines 24-100 (synthetic-builder pattern)

**Parametrize across 4 fixtures (clothing / multipack / discounted / live-contre-jour)**:
```python
"""viled _extract_volume_from_nextdata helper tests — PARSE-FIX-03.

RED → GREEN per Plan 08-04 strict TDD. Drives both the new helper directly
and the full parse_pdp roundtrip against all 3 existing + 1 live fixture.
"""

from __future__ import annotations

import json

import pytest

from ga_crawler.parsers.viled_nextdata import (
    _extract_volume_from_nextdata,
    _extract_next_data,
    ViledRawProduct,
    parse_pdp,
)


# Direct helper unit tests — synthetic dicts

def test_extract_volume_from_nextdata_beauty_50ml() -> None:
    a0 = {
        "price": 12345,
        "attributes": [
            {"name": "Размер", "value": "50 мл"},
        ],
    }
    assert _extract_volume_from_nextdata(a0) == "50 мл"


def test_extract_volume_from_nextdata_clothing_size() -> None:
    """Clothing 'S' is returned verbatim; NORM-03 disambiguates."""
    a0 = {"attributes": [{"name": "Размер", "value": "S"}]}
    assert _extract_volume_from_nextdata(a0) == "S"


def test_extract_volume_from_nextdata_no_size_attr() -> None:
    """No 'Размер' / 'Объём' entry → None (legitimate-absent per D-814)."""
    a0 = {"attributes": [{"name": "Цвет", "value": "Красный"}]}
    assert _extract_volume_from_nextdata(a0) is None


def test_extract_volume_from_nextdata_cyrillic_obyom() -> None:
    a0 = {"attributes": [{"name": "Объём", "value": "100мл"}]}
    assert _extract_volume_from_nextdata(a0) == "100мл"


def test_extract_volume_from_nextdata_empty_descriptive_list() -> None:
    a0 = {"attributes": []}
    assert _extract_volume_from_nextdata(a0) is None


def test_extract_volume_from_nextdata_missing_attributes_key() -> None:
    a0 = {"price": 100}
    assert _extract_volume_from_nextdata(a0) is None


# Round-trip tests via existing fixtures

def test_round_trip_discounted_beauty_yields_50ml(viled_pdp_discounted_html: str) -> None:
    p = parse_pdp(viled_pdp_discounted_html, "https://viled.kz/item/367251")
    assert p is not None
    assert p.raw_volume_text is not None
    assert "50" in p.raw_volume_text
    assert "мл" in p.raw_volume_text.lower()


def test_round_trip_clothing_yields_size_string(viled_pdp_html: str) -> None:
    """Clothing fixture yields 'S' (or whatever clothing-size string); NORM-03
    then maps to volume_norm=None."""
    p = parse_pdp(viled_pdp_html, "https://viled.kz/item/407682")
    assert p is not None
    # raw_volume_text is now extracted from Размер attr, NOT name — verify NOT == name
    assert p.raw_volume_text != p.name


def test_round_trip_contre_jour_yields_none_or_name(viled_pdp_html_live_contre_jour: str) -> None:
    """Frederic Malle Contre-Jour: 'Размер' attr likely absent → fallback to name (D-814 legitimate-None)."""
    p = parse_pdp(viled_pdp_html_live_contre_jour, "https://viled.kz/item/<contre-jour-id>")
    assert p is not None
    # raw_volume_text is either None or equals name (fallback) — both are acceptable;
    # NORM-03 returns volume_norm=None either way.
```

**MODIFY existing test** — `tests/unit/test_viled_nextdata_parser.py` (1 modification per CONTEXT.md D-812): any assertion of the form `assert p.raw_volume_text == p.name` (currently true everywhere) flips to `assert p.raw_volume_text in (p.name, extracted_from_attr)` — flexibility for both fallback and extraction paths.

---

### `tests/runner/test_parser_drift_gate.py` (test, new) — Plan 08-05 W2

**Analog:** `tests/unit/test_parse_quality_gate.py` (full file — boundary + threshold parametrize)

**Direct copy of analog shape** (analog has 8 tests; new file has ~10):
```python
"""PARSE-FIX-04 parser-drift null-rate gate tests.

Pure-function unit tests for `parser_drift_null_rate_gate`. Mirror shape of
tests/unit/test_parse_quality_gate.py — same boundary + threshold style.
"""

from __future__ import annotations

import pytest

from ga_crawler.runner.gates import parser_drift_null_rate_gate, ParserDriftGateResult


def test_both_rates_below_threshold_passes() -> None:
    r = parser_drift_null_rate_gate(volume_null_rate=0.1, brand_null_rate=0.05)
    assert r.passed
    assert r.failure_reason is None


def test_exactly_at_threshold_passes() -> None:
    """D-815: STRICT > threshold — exactly 0.5 PASSES."""
    r = parser_drift_null_rate_gate(volume_null_rate=0.5, brand_null_rate=0.5)
    assert r.passed


def test_volume_exceeds_threshold_fails() -> None:
    """Synthetic regression (Success Criteria #5): 60% null volume."""
    r = parser_drift_null_rate_gate(volume_null_rate=0.6, brand_null_rate=0.0)
    assert not r.passed
    assert r.failure_reason == "parser_drift_null_volume_rate"
    assert r.volume_null_rate == 0.6


def test_brand_exceeds_threshold_fails() -> None:
    r = parser_drift_null_rate_gate(volume_null_rate=0.0, brand_null_rate=0.7)
    assert not r.passed
    assert r.failure_reason == "parser_drift_null_brand_rate"


def test_both_exceed_volume_wins_priority() -> None:
    """D-815 priority: volume_null_rate wins when both exceed."""
    r = parser_drift_null_rate_gate(volume_null_rate=0.8, brand_null_rate=0.7)
    assert not r.passed
    assert r.failure_reason == "parser_drift_null_volume_rate"


def test_custom_threshold() -> None:
    r = parser_drift_null_rate_gate(volume_null_rate=0.3, brand_null_rate=0.0, threshold=0.2)
    assert not r.passed
    assert r.failure_reason == "parser_drift_null_volume_rate"


def test_zero_rates_passes() -> None:
    r = parser_drift_null_rate_gate(volume_null_rate=0.0, brand_null_rate=0.0)
    assert r.passed


def test_result_is_frozen_dataclass() -> None:
    r = parser_drift_null_rate_gate(0.0, 0.0)
    assert isinstance(r, ParserDriftGateResult)
    with pytest.raises(Exception):
        r.passed = False  # frozen
```

---

### `tests/integration/test_phase8_synthetic_regression.py` (test, new) — Plan 08-05 W2

**Analog:** `tests/integration/test_matcher_run.py` (lines 42-80 in-memory engine + run-writer setup) + `synthetic_report_run` fixture in `conftest.py:316-594` (snapshot planting pattern)

**Imports + in-memory engine setup pattern** (analog lines 42-58):
```python
"""Phase 8 PARSE-FIX-04 synthetic-regression integration test (Success Criteria #5).

Mirrors tests/integration/test_matcher_run.py engine/run setup style and uses
the same snapshot-planting shape as conftest.py `synthetic_report_run`.

Wires parser_drift_null_rate_gate into an in-memory pipeline: 10 goldapple
snapshots planted with 60% NULL volume_norm → orchestrator finalizes run with
status='failed' + parser_drift_failure_reason='parser_drift_null_volume_rate'.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text as _text

from ga_crawler.runner.gates import parser_drift_null_rate_gate
from ga_crawler.runner.stats import GoldappleStatsBuilder
from ga_crawler.storage.sqlite import (
    SqliteRunWriter,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)


@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "phase8_drift.db"
    init_db(db)
    return make_engine(db)


def _gold_snap(sku_id: str, *, volume_norm: str | None, brand: str = "Givenchy") -> dict:
    """Snapshot row builder mirroring conftest synthetic_report_run shape."""
    return dict(
        sku_id=sku_id,
        url=f"https://goldapple.kz/{sku_id}",
        name="Test Product",
        brand=brand,
        volume_raw="50 мл" if volume_norm else None,
        current_price=10000,
        was_price=None,
        currency="KZT",
        stock_state="IN_STOCK",
        brand_norm=brand.lower() if brand else None,
        name_norm="test product",
        volume_norm=volume_norm,
        multipack_flag=False,
        scraped_at=datetime(2026, 5, 13, 14, 0, 0, tzinfo=timezone.utc),
    )


def test_synthetic_60pct_null_volume_triggers_drift_gate(engine) -> None:
    """Plant 10 goldapple snapshots — 6 with volume_norm=NULL, 4 valid.
    Compute null_rate via SQL; assert gate fails with volume-reason."""
    rw = SqliteRunWriter(engine)
    sw = SqliteSnapshotWriter(engine, batch_size=20)
    run_id = rw.create()

    snaps = [
        _gold_snap(f"g-{i:02d}", volume_norm=None) for i in range(6)  # 6 nulls
    ] + [
        _gold_snap(f"g-{i:02d}", volume_norm="(50, ml, 1)") for i in range(6, 10)
    ]
    sw.append(run_id, "goldapple", snaps)

    # Compute null rates via SQL (mirrors RESEARCH.md §"Null-Rate Computation")
    with engine.begin() as conn:
        row = conn.execute(_text(
            "SELECT "
            "  AVG(CASE WHEN volume_norm IS NULL THEN 1.0 ELSE 0.0 END) AS v_null, "
            "  AVG(CASE WHEN brand IS NULL OR brand = '' THEN 1.0 ELSE 0.0 END) AS b_null "
            "FROM snapshots WHERE run_id = :rid AND retailer = 'goldapple'"
        ), {"rid": run_id}).first()
    volume_null_rate = float(row.v_null or 0.0)
    brand_null_rate = float(row.b_null or 0.0)

    drift = parser_drift_null_rate_gate(volume_null_rate, brand_null_rate, threshold=0.5)
    assert volume_null_rate == 0.6
    assert not drift.passed
    assert drift.failure_reason == "parser_drift_null_volume_rate"

    # Wire into stats + finalize (per RESEARCH.md §"Orchestrator Wiring")
    builder = GoldappleStatsBuilder()
    builder.set("volume_null_rate", drift.volume_null_rate)
    builder.set("brand_null_rate", drift.brand_null_rate)
    builder.set("parser_drift_failure_reason", drift.failure_reason)
    rw.patch_stats(run_id, builder.delta)
    rw.finalize(run_id, "failed", reason=drift.failure_reason)

    # Assert end-state: status=failed + reason in stats
    stats = rw.get_stats(run_id)
    assert stats["goldapple.parser_drift_failure_reason"] == "parser_drift_null_volume_rate"
    assert stats["goldapple.volume_null_rate"] == 0.6
```

---

### `tests/runner/test_smoke_urls_rotation.py` (test, new — structural canary) — Plan 08-05 W2

**Analog:** `tests/unit/test_smoke_probe.py` lines 13-27 (existing structural canary)

**Existing analog pattern** (verbatim copy + extend):
```python
def test_smoke_urls_constant_shape() -> None:
    """3 hardcoded Givenchy URLs; all match PRODUCT_URL_RE."""
    assert isinstance(SMOKE_URLS, tuple)
    assert len(SMOKE_URLS) == 3
    for url in SMOKE_URLS:
        assert PRODUCT_URL_RE.match(url) is not None, f"smoke URL {url!r} fails whitelist regex"


def test_smoke_urls_exclude_stale_row_0() -> None:
    """A12 mitigation: spike row 0 (URL contains 7681000002) is stale; must NOT be in SMOKE_URLS."""
    for url in SMOKE_URLS:
        assert "7681000002" not in url, ...
```

**NEW file content**:
```python
"""PARSE-FIX-05 SMOKE_URLs rotation canary (D-818).

After Phase 8, SMOKE_URLS must rotate to 1-URL-per-shape-variant to catch
single-shape-blindness that masked run #13 parser drift. Specific URLs are
sourced from W0 spike shape-table.md (Plan 08-01 output).
"""

from __future__ import annotations

from ga_crawler.enumeration.goldapple_sitemap import PRODUCT_URL_RE
from ga_crawler.runner.gates import SMOKE_URLS


def test_smoke_urls_length_three() -> None:
    assert isinstance(SMOKE_URLS, tuple)
    assert len(SMOKE_URLS) == 3


def test_smoke_urls_all_whitelist_regex_match() -> None:
    for url in SMOKE_URLS:
        assert PRODUCT_URL_RE.match(url) is not None, f"smoke URL {url!r} fails whitelist regex"


def test_smoke_urls_givenchy_baseline_retained() -> None:
    """Givenchy-baseline `19000488678-givenchy-irresistible` is the known-good
    anchor (rotation 2026-05-11). Phase 8 keeps it as one of the 3 slots (D-818)."""
    assert any("19000488678-givenchy-irresistible" in u for u in SMOKE_URLS)


def test_smoke_urls_have_shape_variety() -> None:
    """Distinct slugs — protects against accidental triple-copy of Givenchy baseline."""
    slugs = [u.rsplit("/", 1)[-1] for u in SMOKE_URLS]
    assert len(set(slugs)) == 3, f"SMOKE_URLS must have 3 distinct slugs; got {slugs}"
```

---

### `tests/conftest.py` (modify, append fixtures) — Plan 08-01 W0

**Analog:** self (lines 28-37 `goldapple_pdp_html`; lines 164-189 viled trio)

**Existing fixture-loader pattern** (lines 28-37):
```python
@pytest.fixture(scope="session")
def goldapple_pdp_html() -> str:
    """Real Givenchy PDP captured during spike 01-08 (~200 KB).

    Source: .planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html
    Used by parser tests to assert: top-level offer extraction, priceType filtering
    (StrikethroughPrice / ListPrice / Gold Card discrimination), brand microdata
    walk, availability schema.org URL → enum.
    """
    return (FIXTURES_DIR / "_debug-product-page.html").read_text(encoding="utf-8")
```

**NEW fixtures to append** — insert after line 91 (`jsonld_blocks_anti_fixture`) and after line 189 (`viled_pdp_multipack_html`):
```python
# After line 91 — goldapple v1.1 live fixtures
@pytest.fixture(scope="session")
def goldapple_pdp_html_live_stereotype() -> str:
    """STEREOTYPE/sago live PDP captured 2026-05-13 (Bug #1 + Bug #2 evidence).

    Brand <meta itemprop="name"> content="STEREOTYPE "; product
    <meta itemprop="name"> content="sago"; <h1> text "STEREOTYPEsago" (concat).
    Volume block [75] ОБЪЁМ / МЛ in flex-box of <div>s without itemprop="size".
    Source: Plan 08-01 W0 spike capture (.planning/spikes/v1.1-brand-name-shapes/).
    """
    return (FIXTURES_DIR / "_live-2026-05-13-stereotype.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def goldapple_pdp_html_live_armani() -> str:
    """Armani code live PDP captured 2026-05-13 (Bug #2 evidence).

    Brand "Armani"; product "armani code"; <h1> "Armaniarmani code" (concat lowercase).
    Source: Plan 08-01 W0 spike capture.
    """
    return (FIXTURES_DIR / "_live-2026-05-13-armani-code.html").read_text(encoding="utf-8")


# After line 189 — viled v1.1 live fixture
@pytest.fixture(scope="session")
def viled_pdp_html_live_contre_jour() -> str:
    """Frederic Malle Contre-Jour live PDP captured 2026-05-13 (Bug #3 evidence).

    Tests the legitimate-None case for D-814: `Размер` likely absent on this SKU.
    Source: Plan 08-01 W0 spike capture.
    """
    return (VILED_FIXTURES_DIR / "_live-2026-05-13-contre-jour.html").read_text(encoding="utf-8")
```

---

### `tests/fixtures/goldapple/_live-2026-05-13-*.html` + `tests/fixtures/viled/_live-2026-05-13-*.html` (raw HTML, new) — Plan 08-01 W0

**Analog:** `tests/fixtures/goldapple/_debug-product-page.html` (existing Givenchy baseline) + `tests/fixtures/viled/viled-pdp-discounted.html` (existing Frederic Malle beauty PDP)

**Placement rules** (per CONTEXT.md "Established Patterns" line 132):
- Goldapple PDPs → `tests/fixtures/goldapple/` (retailer-grouped, NOT date-grouped)
- viled PDPs → `tests/fixtures/viled/`
- Naming: `_live-YYYY-MM-DD-<slug>.html` (leading underscore matches `_debug-*.html` convention for live/captured fixtures)

**Hygiene:** Operator visually inspects each captured HTML before commit — no `cf_clearance=`, no session tokens, no PII (per RESEARCH.md §Security V12).

---

### `.planning/spikes/v1.1-brand-name-shapes/MEMO.md` (spike artifact, new) — Plan 08-01 W0

**Analog:** `.planning/spikes/01-goldapple/MEMO.md` (full file)

**Existing top-frontmatter + TL;DR + Options-tested shape** (analog lines 1-31):
```markdown
# Spike 01: Goldapple Anti-Bot Decision Memo

**Sign-off:** 2026-05-06 — mirdbek@gmail.com (operator) — APPROVED
**Spike start:** 2026-05-05 (plan 01-01 commit `6ed12da`)
**Spike end:** 2026-05-06 (plan 01-08 sign-off this commit)
**Duration:** 2 days (timebox 1 week per D-02 — well under)

## TL;DR

> [verdict + chosen tier/engine/proxy]

## Problem

[1-paragraph problem statement]

## Options tested

| Tier | Engine | Proxy | Geo (IP) | Result | Notes |
|------|--------|-------|----------|--------|-------|
| 2 | ... | ... | ... | ... | ... |
```

**NEW MEMO.md skeleton** (per RESEARCH.md §"W0 Sub-Spike Protocol" template at line 833-863):
```markdown
# Phase 8 W0 Spike — Brand-Name-Volume Shape Findings

**Completed:** 2026-05-13
**Spike start:** 2026-05-13
**Spike end:** 2026-05-13 (single-session, ~60-90 min wall-clock per RESEARCH §W0 budget)
**Fetched:** 30 PDPs across 5 stratification buckets via Camoufox 0.4.11 from KZ-laptop

## TL;DR

> [verdict — selector validated / fallback needed / new shape discovered]
> [selectolax 0.4 Lexbor `:lexbor-contains("ОБЪЁМ" i)` match rate]
> [microdata <meta itemprop="name"> coverage rate]
> [decision: fallback _strip_brand_prefix needed Y/N]

## Buckets (5 × 6 stratification per D-801)

| Bucket | URLs sampled | Lex-contains-match rate | Microdata-name presence | Shape variant |
|--------|--------------|------------------------|--------------------------|---------------|
| Lux | 6 | x/6 | y/6 | ... |
| Mass-market | 6 | ... | ... | ... |
| Niche | 6 | ... | ... | ... |
| RU-brands | 6 | ... | ... | ... |
| Multi-word brands | 6 | ... | ... | ... |

## What works

- ... (paste selector evidence)

## What doesn't

- ... (edge cases to defer to v1.2)

## Decisions

- `_extract_volume_block` parent-iter strategy: {confirmed/refined}
- `_strip_brand_prefix` fallback: {needed/not needed} based on {X/30} microdata coverage
- Final SMOKE_URLs rotation selection (Plan 08-05): {STEREOTYPE URL} + {Armani URL} + Givenchy-baseline

## Handoff

- See `shape-table.md` for per-PDP detail (30 rows × 8 columns)
- 3 fixtures committed:
  - `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` (Bug #1+#2 evidence)
  - `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` (Bug #2 evidence)
  - `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` (Bug #3 evidence)
- Skill wrap-up: `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md`
```

---

### `.planning/spikes/v1.1-brand-name-shapes/shape-table.md` (spike survey, new) — Plan 08-01 W0

**Analog:** No exact in-repo analog. Use template from RESEARCH.md lines 798-829 verbatim (8-column survey table).

---

### `scripts/capture_spike_pdps.py` (ad-hoc capture, new) — Plan 08-01 W0

**Analog:** `src/ga_crawler/fetchers/goldapple.GoldappleFetcher` (lines 1-60+ — verbatim reuse as async-context-manager)

**Existing fetcher consumer pattern** (analog: `tests/integration/test_run_e2e_with_phase2_mocks.py:28-60`):
```python
async with fetcher:
    rec = await fetcher.fetch_one(fetcher._page, url)
```

**NEW capture script** (per RESEARCH.md §"W0 Sub-Spike Protocol" template at lines 722-771):
```python
"""Ad-hoc 30-PDP capture for Phase 8 W0 shape-sampling spike (D-801..D-804).

NOT a long-term committed CLI surface — Phase 9 (TEST-HARNESS-05) formalizes this
as `python -m ga_crawler capture-fixtures`. For Phase 8, this script is a
one-shot helper used to populate .planning/spikes/v1.1-brand-name-shapes/.

Lives in `scripts/` (operator's call per CONTEXT.md "Reusable Assets"); may
alternatively be placed at `.planning/spikes/v1.1-brand-name-shapes/capture.py`.
"""
import asyncio
from pathlib import Path
from ga_crawler.fetchers.goldapple import GoldappleFetcher

# Stratified 5 × 6 = 30 URLs per CONTEXT.md D-801.
URLS: list[tuple[str, str]] = [
    # bucket 1: lux  (6 URLs)
    ("lux-tomford-noir",      "https://goldapple.kz/..."),
    # ... 24 more in 4 buckets ...
]
assert len(URLS) == 30

OUTPUT_DIR = Path(__file__).resolve().parent.parent / ".planning" / "spikes" / "v1.1-brand-name-shapes"

async def main():
    fetcher = GoldappleFetcher(run_id=0)
    async with fetcher:
        for i, (slug, url) in enumerate(URLS, start=1):
            rec = await fetcher.fetch_one(fetcher._page, url)
            html = rec.get("html") or ""
            if html:
                out = OUTPUT_DIR / f"pdp-{i:02d}-{slug}.html"
                out.write_text(html, encoding="utf-8")
            # Rate-limit per spike-01-goldapple/SKILL: 3-5s, enforced by fetch_one.

if __name__ == "__main__":
    asyncio.run(main())
```

---

### `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` (skill, new) — Plan 08-01 W0

**Analog:** `.claude/skills/spike-01-goldapple/SKILL.md` (full file — verbatim copy of structure)

**Existing skill frontmatter shape** (analog lines 1-22):
```markdown
---
name: spike-01-goldapple-anti-bot
description: Phase 1 spike findings for goldapple.kz anti-bot tier. Use when planning Phase 3 (Goldapple Crawl) or Phase 7 (hosting/prod-IP) to recall chosen tier, browser engine, proxy provider, microdata-not-JSON-LD parser strategy, and committed rate-limits.
---

# Spike 01: Goldapple Anti-Bot Findings (Reference Skill)

**Source memo:** [[.planning/spikes/01-goldapple/MEMO]] (repo-local, signed off 2026-05-06)
**Spike completed:** 2026-05-06
**Phase 1 status:** DONE
**Sign-off:** mirdbek@gmail.com (operator), APPROVED

## What was decided

[1-paragraph TL;DR]

| Field | Value |
|---|---|
| **Chosen tier** | 2 |
...

## Operational constants for Phase 3
...

## Stack constraints (do not deviate without re-spike)
...

## When to consult this skill
...

## Critical files (entry points)
...

## What was NOT decided here (defer to relevant phase)
...
```

**NEW skill skeleton** (per RESEARCH.md §"Project-Local Skill Wrap-Up" template at lines 869-899) — same H2 sections as analog, repopulated for shape-sampling context.

---

### Doc cascade (`.planning/REQUIREMENTS.md`, `PROJECT.md`, `ROADMAP.md`, `STATE.md`) — Plan 08-05 W2 tail

**Analog:** None (doc updates are file-specific). The pattern is "additive table-row edits" — find PARSE-FIX-01..05 lines in REQUIREMENTS.md and flip status checkbox; in ROADMAP.md, find "Phase 8" heading and mark complete; in STATE.md, update current-state pointer.

**Convention from prior phase doc cascades** (e.g. Phase 7 closed in commits `2747b69`, `0477cda`): single commit per file, message format `docs(NN): mark Phase N reqs complete` (replace `NN` with phase number).

---

## Shared Patterns

### Pattern 1: Module-level helper insertion shape

**Source:** `src/ga_crawler/parsers/goldapple_microdata.py:254-267` (`_extract_strikethrough`); `src/ga_crawler/parsers/viled_nextdata.py:86-111` (`_map_stock_state`)
**Apply to:** `_extract_volume_block` (Plan 08-02), `_extract_volume_from_nextdata` (Plan 08-04)

Both new helpers follow:
1. Underscore-prefix (`_extract_*`) — module-private
2. Inputs are already-parsed nodes/dicts (NOT raw HTML strings — exception: `_extract_volume_block` takes html string per D-806 local-import isolation)
3. Returns `Optional[T]` — None on missing-data is a normal flow, never an exception
4. Docstring lists exact return contract ("returns None when ..."), cites source decision (e.g. `D-806`, `D-815`), and links 08-RESEARCH.md section
5. NO logging inside helper — logging happens at caller level

### Pattern 2: Stats namespace extension

**Source:** `src/ga_crawler/runner/stats.py:18-32` (`GOLDAPPLE_STATS_KEYS` tuple) + `tests/unit/test_stats_namespace.py:14-38` (length + parametrize canary)
**Apply to:** Plan 08-05 (3 new keys: `volume_null_rate`, `brand_null_rate`, `parser_drift_failure_reason`)

Add to tuple → update `test_namespace_has_13_keys` to 16 → add 3 entries to parametrize block. **Pitfall 6 atomic merge:** never persist new keys piecemeal — always via single `patch_stats(run_id, builder.delta)` call.

### Pattern 3: D-203 retailer-agnostic gate helper

**Source:** `src/ga_crawler/runner/gates.py:242-247` (`final_threshold_gate`); `:253-268` (`parse_quality_gate`)
**Apply to:** Plan 08-05 `parser_drift_null_rate_gate`

Pure-function predicate, retailer-agnostic, threshold-kwarg defaulted, return-type either `bool` OR a small `@dataclass(frozen=True)` Result class for multi-field returns. Inclusive-vs-exclusive threshold semantics MUST be in docstring (`>` vs `<=`).

### Pattern 4: TDD RED→GREEN atomic commits

**Source:** Established across Phases 2-7 (see plan files in `.planning/phases/02-*/` through `07-*/`)
**Apply to:** All Phase 8 plans

Per CONTEXT.md D-811: RED commit (test added against `_live-*.html` fixture, fails) → GREEN commit (production code, test passes). Commit pair is atomic per plan. No "test-and-impl in one commit" shortcuts.

### Pattern 5: Append-only `__all__` discipline

**Source:** `src/ga_crawler/runner/gates.py:308-318` (`__all__` list)
**Apply to:** Plans adding new public helpers (`parser_drift_null_rate_gate`, `ParserDriftGateResult`)

Add new names to `__all__` — never remove existing. Maintains import surface stability across phases.

### Pattern 6: Local-import isolation for opt-in backends

**Source:** None in-repo yet (new pattern for Phase 8)
**Apply to:** Plan 08-02 `_extract_volume_block` Lexbor backend

Per CONTEXT.md D-806: `from selectolax.lexbor import LexborHTMLParser` MUST be local to the helper function, NOT at module top. Reason: blast-radius isolation — existing 60+ goldapple parser tests use Modest via module-top `from selectolax.parser import HTMLParser` and must not be disturbed.

---

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| `.planning/spikes/v1.1-brand-name-shapes/shape-table.md` | survey table | No prior in-repo spike used a tabular shape-survey artifact — use RESEARCH.md §"W0 Sub-Spike Protocol" template (lines 798-829) verbatim |
| `.planning/REQUIREMENTS.md` / `PROJECT.md` / `ROADMAP.md` / `STATE.md` doc edits | doc cascade | Pure additive table-row / status-line edits; no code analog. Convention is "single commit per file" per recent history (commits `2747b69`, `0477cda`) |

---

## Metadata

**Analog search scope:**
- `src/ga_crawler/parsers/` (microdata + nextdata parsers — existing)
- `src/ga_crawler/runner/` (gates + stats — existing)
- `src/ga_crawler/fetchers/` (Camoufox consumer — existing)
- `tests/unit/` + `tests/integration/` (parser tests, gate tests, orchestrator tests)
- `tests/conftest.py` (fixture-loader patterns)
- `.planning/spikes/01-goldapple/` (spike conventions)
- `.claude/skills/spike-01-goldapple/` (skill conventions)
- `pyproject.toml` (dependency-pin shape)
- `.planning/phases/08-parser-bug-fixes/08-CONTEXT.md` + `08-RESEARCH.md` (source-of-truth)

**Files scanned:** 13 production .py + 8 test files + 1 conftest + 1 pyproject + 4 spike+skill artifacts = 27 files

**Pattern extraction date:** 2026-05-13

---

## PATTERN MAPPING COMPLETE

**Phase:** 8 — Parser Bug Fixes
**Files classified:** 22
**Analogs found:** 19 / 22

### Coverage
- Files with exact analog: 16 (parsers, gates, stats, tests, conftest, fixtures, spike MEMO/PDPs, skill, pyproject)
- Files with role-match analog: 3 (capture script reuses GoldappleFetcher; integration test reuses matcher_run setup; spike artifacts mirror Phase 1 spike conventions)
- Files with no analog: 3 (shape-table.md — RESEARCH template only; doc cascade — file-specific)

### Key Patterns Identified
- All new module-level helpers use the `_extract_*(input) -> Optional[T]` shape (mirror of existing `_extract_strikethrough` + `_map_stock_state`)
- New gate `parser_drift_null_rate_gate` mirrors `parse_quality_gate` D-203 retailer-agnostic pure-predicate shape; returns `@dataclass(frozen=True) ParserDriftGateResult` for 3-field result
- selectolax 0.4 Lexbor import is STRICTLY LOCAL to `_extract_volume_block` per D-806 — Modest stays default at module top; blast radius = 1 function
- viled NextData `Размер` path empirically traced to **nested** `props.pageProps.attributes[0].attributes[]` (NOT `props.pageProps.item.attributes[]` per STACK.md guess)
- Stats namespace extension follows append-only tuple discipline; coupled `test_stats_namespace.py` length canary MUST flip 13→16
- All new tests mirror RED→GREEN TDD discipline (CONTEXT.md D-811); fixture-driven against committed `_live-2026-05-13-*.html` from Plan 08-01 W0
- Spike artifacts (MEMO + shape-table + skill) mirror `.planning/spikes/01-goldapple/` + `.claude/skills/spike-01-goldapple/` shape verbatim

### File Created
`.planning/phases/08-parser-bug-fixes/08-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns (with line numbers + verbatim code excerpts) in plan-action blocks for Plans 08-01 (W0 spike), 08-02 (PARSE-FIX-01 volume), 08-03 (PARSE-FIX-02 brand+name), 08-04 (PARSE-FIX-03 viled volume), and 08-05 (PARSE-FIX-04 gate + PARSE-FIX-05 rotation + doc cascade).
