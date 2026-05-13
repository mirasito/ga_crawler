# Phase 8: Parser Bug Fixes — Research

**Researched:** 2026-05-13
**Domain:** Python HTML/JSON parser surgery — selectolax 0.4 Lexbor backend, viled `__NEXT_DATA__` JSON traversal, parser-drift null-rate gate
**Confidence:** HIGH (selectolax 0.4 Lexbor API verified via Context7 `/websites/selectolax_readthedocs_io_en`; viled `attributes` JSON path empirically traced against all 3 in-repo fixtures; gate-insertion pattern grounded in direct read of `runner/gates.py` D-203 helpers)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Pre-spike (mandatory W0 sub-spike)**
- **D-801:** 30 живых goldapple PDP fetched через Camoufox 0.4.11, стратифицированы 5×6 (lux / mass-market / niche / RU-brands / multi-word brands).
- **D-802:** Output `.planning/spikes/v1.1-brand-name-shapes/` — `MEMO.md` (итог), `shape-table.md` (30 PDP × {brand_raw, brand_displayed_in_h1, name_raw, volume_block_present?, volume_label_text, shape_bucket}), `pdp-<NN>-<slug>.html` (30 raw HTML, опционально gzipped если >5 MB).
- **D-803:** Wrap-up в `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` (по конвенции `spike-01-goldapple/`).
- **D-804:** Sub-spike блокирует любые правки в `parsers/goldapple_microdata.py` и `parsers/viled_nextdata.py` — first task Phase 8.

**selectolax 0.3 → 0.4 migration scope**
- **D-805:** Pin `pyproject.toml` selectolax `>=0.4.7,<0.5`. Modest backend остаётся default; Lexbor — opt-in.
- **D-806:** Lexbor import СТРОГО локальный в `_extract_volume_block(tree)`: `from selectolax.lexbor import LexborHTMLParser`. Существующие 60+ goldapple parser тестов и viled parser НЕ ТРОГАЕМ.
- **D-807:** Blast radius = 1 функция. Если Lexbor backend сломает что-то в smoke против `_debug-product-page.html` — fallback на ручной selector без `:contains`.

**Plan-wave structure (3 waves, strict TDD)**
- **D-808:** W0 sequential — Plan 08-01 spike + skill + 3 fixtures. Gate: shape-table.md + 3 fixtures + SKILL.md committed.
- **D-809:** W1 parallel (3 plans, different files) — Plan 08-02 (PARSE-FIX-01 goldapple volume via `_extract_volume_block`); Plan 08-03 (PARSE-FIX-02 brand+name via `<meta itemprop="name">` + invariant canary); Plan 08-04 (PARSE-FIX-03 viled volume via `_extract_volume_from_nextdata`).
- **D-810:** W2 sequential — Plan 08-05 PARSE-FIX-04 null-rate gate + PARSE-FIX-05 SMOKE_URLs rotation + doc cascade.
- **D-811:** Strict TDD per fix: RED test против `_live-2026-05-13-*.html` fixture ДО touching production, GREEN после. Commit пара RED+GREEN атомарно.
- **D-812:** Test count delta: 803 → ~818 (+15: ~10 goldapple parser, ~5 viled parser, +1 gate test, +1 SMOKE rotation smoke; 1 modification к existing viled `raw_volume_text == name` test).

**PARSE-FIX-04 null-rate gate**
- **D-813:** Threshold 50% absolute (объяснимо, покрывается synthetic-regression тестом per Success Criteria #5).
- **D-814:** Retailer scope goldapple-only. Viled НЕ включаем (legitimate Nones — Frederic Malle Contre-Jour, Creed Wild Vetiver).
- **D-815:** Field scope volume_norm + brand оба gated. Gate срабатывает если ЛЮБОЕ из:
  - `null_rate(goldapple.volume_norm) > 0.5` → reason `parser_drift_null_volume_rate`
  - `null_rate(goldapple.brand) > 0.5` → reason `parser_drift_null_brand_rate`
- **D-816:** Brand-canary `assert brand.lower() not in name.lower()` остаётся отдельным per-SKU invariant — НЕ заменяется gate'ом. Gate ловит "all SKUs broken" mode, invariant ловит per-SKU regression.
- **D-817:** Gate position: после persist + parse-quality gate, ДО matcher (same shape as `final_threshold_gate` per D-203 retailer-agnostic helpers).

**PARSE-FIX-05 SMOKE_URLs rotation**
- **D-818:** Current 3× Givenchy URLs ротируются в:
  1. STEREOTYPE-style (brand-uppercase-prefix-in-h1) — URL из shape-table.md.
  2. Armani-style (brand-duplicated-into-name) — URL из shape-table.md.
  3. Givenchy-baseline `19000488678-givenchy-irresistible` — оставляем как known-good baseline.
- **D-819:** Final URL slot selection deferred to Plan 08-05 (после W0 spike даёт shape-table).

### Claude's Discretion

- **Внутренняя структура `_extract_volume_block(tree)`** — точный CSS-селектор путь после Lexbor `:lexbor-contains("ОБЪЁМ" i)` — определяется на основе live HTML spike output, не угадываем заранее.
- **Brand-prefix fallback `_strip_brand_prefix(name, brand)`** — включать или нет, решается по shape-table data. Если `<meta itemprop="name">` присутствует >95% PDP → fallback не нужен. Если <95% → добавляем strip-prefix helper. Решает Plan 08-03 на основе W0 evidence.
- **Точный JSON path для viled `attributes[].name == "Размер"`** — подтверждается Wave-0 mini-probe против живой beauty PDP в Plan 08-01 (clothing fixture уже подтверждает shape, но beauty PDP path verification нужен). **Research-time finding:** path empirically traced — see §"viled NextData attributes" below.

### Deferred Ideas (OUT OF SCOPE)

- Live-HTML syrupy harness — Phase 9 (TEST-HARNESS-01..06).
- `scripts/capture_fixtures.py` CLI subcommand — Phase 9 (TEST-HARNESS-05).
- Pydantic write-boundary validation — Phase 9 (TEST-HARNESS-06).
- Backfill runs 1-13 — out (forward-only per ARCHITECTURE.md §C).
- viled volume null-rate gate — gold-only (legitimate Nones at viled). Re-evaluate в v1.2 если post-deploy evidence пожалуется.
- Brand-coverage quota canary — Phase 9 P2 cheap-bundle (TEST-HARNESS-04).
- Match-rate floor alert (упомянутый в SUMMARY.md как "A5") — defer v2.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PARSE-FIX-01 | Goldapple parser извлекает `volume_raw` из structured PDP-блока (`78 ОБЪЁМ / МЛ`) через selectolax 0.4 Lexbor `:contains` selector; ≥90% non-null rate на не-volumeless категориях | §"selectolax 0.4 Lexbor" provides verified `:lexbor-contains("ОБЪЁМ" i)` primitive + sibling-walk pattern; §"goldapple PDP shape" gives concrete extraction algorithm |
| PARSE-FIX-02 | Goldapple parser извлекает `brand` и `name` раздельно через `<meta itemprop="name">` микроразметку; invariant canary `brand.lower() not in name.lower()` проходит | §"goldapple PDP shape" maps current code line 327-332 (`<h1>` verbatim read) to the structured replacement (product-level `<meta itemprop="name">` adjacent to `[itemprop="brand"]`); existing `_debug-product-page.html` Givenchy fixture confirms shape |
| PARSE-FIX-03 | Viled parser извлекает `volume_raw` из `props.pageProps.attributes[].name == "Размер"` JSON-поля; fallback на regex по `name` только если отсутствует | §"viled NextData attributes" provides **exact** path `props.pageProps.attributes[0].attributes[]` (nested, NOT what STACK.md tentatively suggested) — verified against all 3 in-repo fixtures (407682, multipack, discounted) |
| PARSE-FIX-04 | Sanity-gate null-rate: `goldapple_volume_norm` null rate >50% **или** `goldapple.brand` null rate >50% → run `failed` с reason `parser_drift_null_volume_rate` / `parser_drift_null_brand_rate` | §"PARSE-FIX-04 null-rate gate" details insertion point (between parse-quality and matcher), 3 new stats keys, and synthetic-regression test recipe |
| PARSE-FIX-05 | Smoke-probe URL rotation в `runner/gates.py:36` SMOKE_URLS — 1 URL на shape variant (STEREOTYPE + Armani + Givenchy-baseline) | §"PARSE-FIX-05 SMOKE_URLs rotation" + selection deferred to Plan 08-05 post-W0 |

</phase_requirements>

## Executive Summary

Phase 8 is a **narrow, evidence-driven parser surgery** — three concurrent parser fixes (W1 parallel) preceded by a mandatory 30-PDP shape-sampling sub-spike (W0 sequential) and followed by a defensive gate + smoke-URL rotation (W2 sequential). All major risk areas have research-grade answers in this document:

- **selectolax 0.4 Lexbor backend** is the right primitive for goldapple volume extraction. Context7 confirms `:lexbor-contains("text" i)` pseudo-class is exposed via `tree.css(...)` on `LexborHTMLParser`, sibling traversal via `node.next` / `node.parent.iter()` is identical to Modest, and **Modest is now flagged DEPRECATED upstream** — Lexbor is the future-proof path. Pin `selectolax>=0.4.7,<0.5` is validated against PyPI (current latest 0.4.8). Modest backend remains importable so existing 60+ goldapple parser tests stay green untouched (D-806).
- **viled `Размер` JSON path was misidentified in research SUMMARY.md / STACK.md.** Empirical trace against all 3 in-repo viled fixtures (`viled-pdp-407682.html`, `viled-pdp-multipack.html`, `viled-pdp-discounted.html`) shows the descriptive-attributes array lives at **`props.pageProps.attributes[0].attributes[]`** (nested inside the price-variant), NOT at `props.pageProps.item.attributes[]` (which is `None`/absent). This is load-bearing for Plan 08-04 — write the helper against the verified path, not the speculative one.
- **Clothing-vs-beauty disambiguation is required.** The same `Размер` attribute returns `"S"`/`"L"` (clothing size, viled-pdp-407682) versus `"50 мл"`/`"200мл + 200мл + 250мл"` (volume, discounted/multipack). The helper MUST run the extracted value through the existing `normalizers/volume.py:118 parse_volume` and treat `None` as "не volume" — never as a parse failure.
- **PARSE-FIX-04 gate insertion** follows the D-203 retailer-agnostic helper pattern in `runner/gates.py` (`final_threshold_gate`, `parse_quality_gate`). The new `parser_drift_null_rate_gate(null_rate_volume, null_rate_brand, *, threshold=0.5)` sits between persist + parse-quality and matcher in the pipeline, emits 3 new stats fields (`goldapple.volume_null_rate`, `goldapple.brand_null_rate`, `failure_reason`), and is testable in pure isolation with a synthetic dict.

**Primary recommendation:** Execute W0 spike with a tight 60-90 minute Camoufox capture script (30 PDPs at the LOCKED Phase 3 rate-limit of 3-5 s random uniform sequential, so ~90 s warm-up + 30 × 4 s ≈ 3 minutes wall-clock fetch, plus 5-10 min skim of shape-table writing). All three parser fixes (Plans 08-02/03/04) then proceed in parallel against the 3 committed `_live-2026-05-13-*.html` fixtures with strict RED → GREEN TDD discipline.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTML parsing (goldapple PDP volume block) | `parsers/goldapple_microdata.py` | — | Single-file responsibility; new `_extract_volume_block(tree)` helper at module level; Lexbor backend opt-in per D-806 |
| HTML parsing (goldapple brand+name microdata read) | `parsers/goldapple_microdata.py` | — | Same file; new sibling `<meta itemprop="name">` read inside product `itemscope` |
| JSON parsing (viled `Размер` extraction) | `parsers/viled_nextdata.py` | — | Single-file responsibility; new `_extract_volume_from_nextdata(a0)` helper; no library change |
| Pipeline gate (null-rate sanity) | `runner/gates.py` | `runner/stats.py` (3 new stats keys via `GoldappleStatsBuilder`) | Follows D-203 retailer-agnostic helper shape; gate is pure function `(null_rate_v, null_rate_b, *, threshold) -> (passed, reason)` |
| Smoke URL rotation | `runner/gates.py` constant `SMOKE_URLS` | — | Operator-facing constant per D-203; rotation per D-818 |
| Shape-sampling capture (W0) | `scripts/spike_v11_capture.py` (NEW, ad-hoc, not committed long-term) | `fetchers/goldapple.GoldappleFetcher` (verbatim reuse) | Wraps existing fetcher; ad-hoc per CONTEXT.md "no `scripts/capture_fixtures.py` until Phase 9" |
| Fixture loading (3 new live fixtures) | `tests/conftest.py:23-37` | — | 6-line extension per CONTEXT.md "Reusable Assets" |

---

## selectolax 0.4 Lexbor — Usage Patterns, Exact Imports, Gotchas

> **Source:** Context7 `/websites/selectolax_readthedocs_io_en` (HIGH confidence, fetched 2026-05-13).
> **Version verification:** [PyPI](https://pypi.org/project/selectolax/) — latest **0.4.8** (May 2026). Pin `>=0.4.7,<0.5` per CONTEXT.md D-805 is current and valid.

### Imports & Instantiation

The Lexbor backend lives in a **separate submodule**, NOT in `selectolax.parser`. Existing Modest imports are preserved verbatim — Lexbor is strictly additive.

```python
# Existing Modest backend (parsers/goldapple_microdata.py:32 — UNCHANGED per D-806)
from selectolax.parser import HTMLParser, Node

# NEW Lexbor import — STRICTLY LOCAL to _extract_volume_block(tree) helper per D-806
from selectolax.lexbor import LexborHTMLParser
```

**Constructor signature** (Context7-verified):

```python
LexborHTMLParser(
    html: str | bytes,
    is_fragment: bool = False,
    fragment_tag: str = 'div',
    fragment_namespace: str = 'html',
)
```

⚠️ **Difference from `HTMLParser`:** Lexbor's constructor does NOT accept `detect_encoding=`, `use_meta_tags=`, or `decode_errors=` — those parameters are Modest-specific. For Phase 8's purpose this is fine; live PDP HTML comes from Camoufox as `str` (already decoded), so encoding negotiation isn't needed.

**Recommended pattern** for the volume-block helper:

```python
def _extract_volume_block(html: str) -> Optional[str]:
    """Extract '78 ОБЪЁМ / МЛ' style structured volume block from goldapple PDP HTML.

    Uses selectolax 0.4 Lexbor backend for :lexbor-contains() case-insensitive
    pseudo-selector. Falls back to None if the label is absent OR the sibling
    walk fails to land on a numeric leaf.

    Returns the raw volume text (e.g. '78 мл' or '78 ОБЪЁМ / МЛ') for downstream
    NORM-03 parse_volume to consume. Returns None on extraction failure — caller
    treats None as "volume legitimately absent" (e.g. spray-mist categories) and
    continues, since PARSE-FIX-04 null-rate gate handles aggregate drift.
    """
    tree = LexborHTMLParser(html)
    # Step 1: find any <div> whose text contains "ОБЪЁМ" case-insensitively.
    # :lexbor-contains() is the only contains pseudo-class in selectolax — there
    # is NO :contains() in either Modest or Lexbor (jQuery extension, NOT W3C).
    label_nodes = tree.css('div:lexbor-contains("ОБЪЁМ" i)')
    if not label_nodes:
        return None
    # Step 2: walk to sibling holding numeric value.
    # Strategy depends on observed flex-box DOM — finalize after W0 shape-table.
    # Hypothesis: <div>78</div><div>ОБЪЁМ / МЛ</div> as siblings under a parent.
    label = label_nodes[0]
    parent = label.parent
    if parent is None:
        return None
    for sibling in parent.iter():
        if sibling is label:
            continue
        text = (sibling.text(deep=False, strip=True) or "")
        # Heuristic: numeric content (matches "78", "75.5", "100 мл") — caller
        # passes through parse_volume which is forgiving of trailing labels.
        if text and any(c.isdigit() for c in text):
            return text
    return None
```

### `:lexbor-contains` Pseudo-Class — Authoritative Reference

Per Context7 (`https://selectolax.readthedocs.io/en/latest/examples.html`):

```python
html = '<div><p>hello </p><p id="main">lexbor is AwesOme</p></div>'
parser = LexborHTMLParser(html)

# Case-insensitive search (flag: trailing " i" — note the SPACE before i)
results_ci = parser.css('p:lexbor-contains("awesome" i)')  # → 1 match

# Case-sensitive search (default, no flag)
results_cs = parser.css('p:lexbor-contains("AwesOme")')    # → 1 match
results_miss = parser.css('p:lexbor-contains("awesome")')  # → 0 matches
```

**Gotchas:**
1. **The case-insensitive flag is `" i"` with a leading space.** `:lexbor-contains("ОБЪЁМ"i)` (no space) is undefined behavior — always write `:lexbor-contains("ОБЪЁМ" i)`.
2. **Russian uppercase normalization.** The literal "ОБЪЁМ" (with capital Ё U+0401, NOT capital Е U+0415) is what goldapple emits per `v1.1-PARSER-BUG-FINDINGS.md` line 22. Case-insensitive matching with `:lexbor-contains("ОБЪЁМ" i)` is the safe writing — but the W0 spike MUST confirm Ё vs Е in the live HTML (Unicode normalization variations are real).
3. **NO `:contains()` in selectolax.** Both Modest and Lexbor only expose `:lexbor-contains()`. The jQuery-style `:contains()` is unsupported. Don't write it — silent zero-match.
4. **`text_contains` is a Selector method, not a Node method.** `LexborSelector.text_contains(text, deep=True, separator='', strip=False)` filters an existing selection. Use it AFTER `tree.css(...)`, not as a tree-level call.

### Sibling Traversal API (identical for Modest + Lexbor)

Verified Context7:

| API | Behavior | Phase 8 use |
|-----|----------|-------------|
| `node.parent` | Returns parent `LexborNode` or `None` | Walk up from label to flex-box parent |
| `node.next` | **Next sibling node** — includes text nodes (whitespace) between elements per docs example | Sibling traversal; may need `.next.next` to skip text |
| `node.prev` | Previous sibling node — same caveat | Pre-label numeric check |
| `node.iter(include_text=False, skip_empty=False)` | Iterates direct children of node, element-only by default | Recommended — element-only iteration skips whitespace text nodes |

⚠️ **`node.next` returns text nodes.** Per the Context7 navigation example: "We need to call it twice, because there are text nodes (spaces and new lines) between elements." For flexbox `<div>78</div><div>ОБЪЁМ / МЛ</div>` rendering, prefer `parent.iter()` (element-only) over manual `.next` chaining.

### Performance Characteristics — Modest vs Lexbor

- Lexbor is documented upstream as **the preferred backend** and Modest is now flagged **deprecated** in current selectolax docs ([selectolax.parser docs](https://selectolax.readthedocs.io/en/latest/parser.html): *"This backend is deprecated. Please use lexbor backend instead."*). [VERIFIED: Context7 fetch 2026-05-13]
- Lexbor is faster on benchmarks (Cython binding around a C HTML5 parser written for performance). For a single-PDP parse this is irrelevant (sub-millisecond either way); the architectural argument is forward-compatibility, not speed.
- Per CONTEXT.md D-806/D-807: **Modest backend stays default in goldapple_microdata.py module-level code.** Lexbor is invoked ONLY inside `_extract_volume_block(html)` (which receives the raw HTML string, not the already-parsed `tree`). This isolates blast radius to one function.

### Memoization

A fresh `LexborHTMLParser` instance per PDP is fine — parser instantiation is ~µs for typical HTML. Do NOT cache a parser instance across calls in a long-running process; the parser holds a reference to a C-level document tree that gets destroyed when the parser is GC'd. The `_extract_volume_block` helper should always instantiate locally.

### Version Pin Justification (`>=0.4.7,<0.5`)

| Version | Released | Notes |
|---------|----------|-------|
| 0.4.0 | Earlier 2025 | First Lexbor-stable release |
| 0.4.7 | ~Q1 2026 | Stabilization release; pin lower bound |
| 0.4.8 | May 2026 | Current latest; bug fixes only |

Upper bound `<0.5` prevents accidental adoption of an as-yet-unreleased 0.5.x which may break API. `>=0.4.7` excludes early 0.4.x that may have had Lexbor wrinkles. [CITED: pypi.org/project/selectolax/]

---

## goldapple PDP Shape — Microdata + Volume Block Extraction Strategy

### Bug #2 (Brand+Name Concatenation) — Direct `<meta itemprop="name">` Read

**Current behavior** (`parsers/goldapple_microdata.py` lines 326-332):

```python
# Name: <h1>; fallback to <title> stripped of " — купить ..."
name = ""
h1 = tree.css_first("h1")
if h1 is not None:
    name = h1.text(strip=True)   # ← reads "STEREOTYPEsago" or "Armaniarmani code" verbatim
if not name and title:
    name = title.split(" — купить", 1)[0].strip()
```

**Root cause** (from `v1.1-PARSER-BUG-FINDINGS.md` + ARCHITECTURE.md §A): The `<h1>` text is the rendered display form — for STEREOTYPE/Armani PDPs it concatenates the brand-as-prefix with the product name in mixed casing (CSS `text-transform: uppercase` on the brand span is visually rendered but the underlying text is the brand string concatenated with the product name in source).

**Recommended fix** (per ARCHITECTURE.md §A + STACK.md A1 line 73-83):

The goldapple PDP emits structured microdata for both brand and product name. The brand is already read correctly at lines 319-324:

```python
brand_raw = ""
brand_node = tree.css_first('[itemprop="brand"]')
if brand_node is not None:
    brand_meta = brand_node.css_first('meta[itemprop="name"]')
    if brand_meta is not None:
        brand_raw = (brand_meta.attributes.get("content") or "").strip()
```

The product-level name lives in a **sibling `<meta itemprop="name">` adjacent to the `[itemprop="brand"]` span**, inside the product `itemscope`. Existing fixture `tests/fixtures/goldapple/_debug-product-page.html` (Givenchy baseline) confirms this shape per STACK.md §A1:

```html
<span itemprop="brand" itemtype="https://schema.org/Brand" itemscope>
  <meta itemprop="name" content="Givenchy ">
</span>
...
<meta itemprop="name" content="Pour Homme">  <!-- product-level — NEW path for v1.1 -->
```

**New extraction strategy:**

```python
# Step 1: locate the product itemscope (the parent of the brand microdata)
product_scope = None
if brand_node is not None:
    cursor = brand_node.parent
    while cursor is not None:
        if cursor.attributes.get("itemscope") is not None and "Product" in (cursor.attributes.get("itemtype", "") or ""):
            product_scope = cursor
            break
        cursor = cursor.parent

# Step 2: within product_scope, find the meta[itemprop="name"] that is NOT inside [itemprop="brand"]
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

# Step 3: extract product name from meta content
name = (name_meta.attributes.get("content").strip() if name_meta else "")

# Fallback chain (per CONTEXT.md "Claude's Discretion" — decided in Plan 08-03 after W0 evidence):
# - If <meta itemprop="name"> missing from spike PDPs >5% of the time → add _strip_brand_prefix(h1_text, brand) helper
# - Otherwise omit fallback (microdata-primary, fail-loud on absence)
```

**Invariant canary** (PARSE-FIX-02 acceptance per CONTEXT.md):

```python
# Per-SKU invariant (D-816 — NOT replaced by gate, both protect different drift modes)
assert brand_raw.lower() not in name.lower(), (
    f"brand '{brand_raw}' is contained in name '{name}' — "
    f"parser regression to pre-v1.1 concatenation"
)
```

### Bug #1 (Volume Block) — `:lexbor-contains` + Sibling Walk

**Current behavior** (`parsers/goldapple_microdata.py` line 358-359):

```python
# Volume passthrough - Phase 2 NORM-03 owns regex extraction
raw_volume_text = name or None  # ← garbage; name has no volume on STEREOTYPE
```

**Live HTML evidence** (`v1.1-PARSER-BUG-FINDINGS.md` line 22):

```
[78]  ОБЪЁМ / МЛ
```

Rendered as a flexbox of `<div>` siblings without `itemprop="size"`. Hypothesized DOM (must confirm via W0 spike):

```html
<div class="some-flex-box-class">
  <div>78</div>
  <div>ОБЪЁМ / МЛ</div>
</div>
```

**Recommended fix** (NEW helper `_extract_volume_block(html)` at module level, inserted near line 254 next to `_extract_strikethrough`):

```python
def _extract_volume_block(html: str) -> Optional[str]:
    """Extract goldapple PDP structured volume block (e.g. '78 ОБЪЁМ / МЛ').

    Uses selectolax 0.4 Lexbor backend (CONTEXT.md D-806 — Lexbor import is
    LOCAL to this helper). Returns the raw composed text the volume label is
    adjacent to, for downstream NORM-03 parse_volume to consume.

    Returns None when:
      - the "ОБЪЁМ" label is not found (volumeless category or shape variant
        not covered by current spike)
      - no numeric sibling/parent is found near the label

    Caller treats None as legitimate-absent (volume normalizer returns None,
    matcher skips per D-402 volume_norm IS NOT NULL filter, PARSE-FIX-04 gate
    handles aggregate drift via null-rate threshold).
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

    # Strategy A: sibling-walk for numeric content
    for sibling in parent.iter():  # element-only, skips text nodes
        if sibling is label:
            continue
        text = (sibling.text(deep=False, strip=True) or "")
        if text and any(c.isdigit() for c in text):
            # Compose "78" + " " + "ОБЪЁМ / МЛ" → "78 ОБЪЁМ / МЛ" for normalizer
            label_text = (label.text(deep=False, strip=True) or "ОБЪЁМ / МЛ")
            return f"{text} {label_text}"

    # Strategy B: label.text(deep=True) — falls back to single-flat-text case
    # (some shape variants may render "78 ОБЪЁМ / МЛ" inside the SAME div).
    composed = (label.text(deep=True, strip=True) or "")
    if any(c.isdigit() for c in composed):
        return composed

    return None
```

**Callsite** (`parse_pdp`, replace line 358-359):

```python
# Volume extraction (PARSE-FIX-01) — try structured block first, fall back to name passthrough
# (preserves backward compat for fixtures where volume IS embedded in title).
raw_volume_text = _extract_volume_block(html) or name or None
```

**Decision deferred to spike output:** the exact CSS selector inside `_extract_volume_block` may need tightening (e.g. `div.volume-block:lexbor-contains(...)` if the spike reveals goldapple uses a known class on the parent). The W0 30-PDP capture must inspect 3-5 PDPs visually and document the volume-block DOM in `shape-table.md`.

### STEREOTYPE vs Armani vs Givenchy — Three Shape Variants

| Shape | Brand source | Name source | Volume block | Test fixture (post-W0) |
|-------|-------------|-------------|--------------|------------------------|
| **Givenchy baseline** (existing) | `<meta itemprop="name">` in `[itemprop="brand"]` → `"Givenchy "` | `<h1>` ≈ `"Pour Homme"` (no concatenation) | Embedded in name string (`"Givenchy Pour Homme 100 мл"`) | `_debug-product-page.html` (UNCHANGED) |
| **STEREOTYPE** (sago) | `<meta itemprop="name">` → `"STEREOTYPE"` (uppercase) | `<h1>` ≈ `"STEREOTYPEsago"` (concat) | Separate `78 ОБЪЁМ / МЛ` block | `_live-2026-05-13-stereotype.html` (NEW) |
| **Armani code** | `<meta itemprop="name">` → `"Armani"` | `<h1>` ≈ `"Armaniarmani code"` (concat lowercase) | Separate `78 ОБЪЁМ / МЛ` block | `_live-2026-05-13-armani-code.html` (NEW) |

**The fix works across all three because:**
1. Microdata `<meta itemprop="name">` for brand AND product-level is present in all three (verified Givenchy; STEREOTYPE/Armani must be confirmed in W0).
2. Volume block is structurally identical across STEREOTYPE/Armani (both are non-Givenchy 2026 PDPs); Givenchy fixture's title-embedded volume is preserved by the `_extract_volume_block(...) or name or None` fallback chain.

---

## viled NextData attributes — JSON Path + Helper Integration

### **EMPIRICAL FINDING — supersedes STACK.md tentative guidance**

> [VERIFIED: traced against all 3 in-repo viled fixtures 2026-05-13]
>
> The descriptive-attributes array carrying `Размер` is **nested** at:
>
> **`props.pageProps.attributes[0].attributes[]`**
>
> NOT at `props.pageProps.item.attributes[]` (which is `None` on all 3 fixtures) and NOT at `props.pageProps.attributes[]` (which is the price-variant array, not descriptive).

### Empirical Evidence

Traced via direct JSON walk of all 3 in-repo viled fixtures (2026-05-13):

| Fixture | `pp.attributes[0]` keys | Nested `attributes[]` length | `Размер` value |
|---------|------------------------|------------------------------|------------------|
| `viled-pdp-407682.html` (clothing) | `['id','price','realPrice','currency','itemImages','enableDiscount','attributes','article','namePlates']` | 6 | `"S"` (clothing size — NOT volume) |
| `viled-pdp-multipack.html` (beauty multipack) | same shape | 4 | `"200мл + 200мл + 250мл"` |
| `viled-pdp-discounted.html` (Frederic Malle beauty) | same shape | 4 | `"50 мл"` |

**This is the existing viled `pageProps.attributes[0]` (`a0` in current code line 155)** — the same dict already used for `current_price = a0.get("price")`. The descriptive attributes array is a **field inside `a0` itself**, not a sibling. The current parser ignores it entirely.

### Recommended Helper

```python
def _extract_volume_from_nextdata(a0: dict) -> Optional[str]:
    """Extract raw volume text from viled __NEXT_DATA__ price-variant attributes.

    Reads the nested descriptive-attributes array at:
        props.pageProps.attributes[0].attributes[]
    and returns the first entry whose name matches Размер / объем / объём
    (case-insensitive, whitespace-stripped).

    Returns:
      str — raw value as emitted by viled (e.g. "50 мл", "200мл + 200мл + 250мл",
            "S", "L"). The downstream NORM-03 normalizer is forgiving — it returns
            None for non-volume strings (e.g. "S", "L" clothing sizes), so the
            caller treats this helper's output as "best-effort raw volume text"
            and lets parse_volume do the validation.
      None — when the nested descriptive attributes are missing OR no entry with
             a recognized name is found.

    Disambiguation strategy (clothing vs beauty):
      We do NOT branch on category here. The value is passed verbatim to
      parse_volume which handles "50 мл" → Volume(50, ml, 1) and "S" → None.
      This keeps the helper simple and the disambiguation in one place
      (normalizers/volume.py), matching v1.0 modularity discipline.
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

### Callsite Integration

Replace line 215 in `parsers/viled_nextdata.py`:

```python
# Before (line 215 — PARSE-FIX-03 target):
raw_volume_text=name,  # NORM-03 extracts volume regex from full name

# After:
raw_volume_text=_extract_volume_from_nextdata(a0) or name,  # PARSE-FIX-03
```

The `or name` chain preserves the v1.0 fallback (regex on full name) for SKUs where viled doesn't emit `Размер` — which is the "legitimate None" case per CONTEXT.md D-814 (Frederic Malle Contre-Jour: no `Размер` attribute → fallback to name → regex fails → `volume_norm = NULL`).

### Test Impact (per CONTEXT.md D-812)

- 1 modification to existing viled parser test: `raw_volume_text == name` → "extracted when available, else name"
- ~5 new viled parser tests:
  - Beauty PDP with `Размер: 50 мл` → `raw_volume_text == "50 мл"`
  - Multipack PDP with `Размер: 200мл + 200мл + 250мл` → `raw_volume_text == "200мл + 200мл + 250мл"`
  - Clothing PDP with `Размер: S` → `raw_volume_text == "S"` (NORM-03 then returns `volume_norm=None`)
  - PDP with no `Размер` attribute → `raw_volume_text == name` (fallback)
  - PDP with `Объём: 100мл` (Cyrillic variant) → `raw_volume_text == "100мл"`

### Wave-0 Mini-Probe Recommendation

Per CONTEXT.md "Claude's Discretion": the beauty-PDP verification is **redundant** — all 3 in-repo fixtures already confirm the shape including the discounted Frederic Malle beauty fixture. The 30-min Wave-0 probe should still happen against ONE live beauty PDP (e.g. Contre-Jour from the bug-findings doc) but its sole purpose is "capture `tests/fixtures/viled/_live-2026-05-13-contre-jour.html`", not path verification.

---

## PARSE-FIX-04 Null-Rate Gate — Insertion Point, Stat Keys, Synthetic Test

### Insertion Point

Per CONTEXT.md D-817: the gate sits between **parse-quality** and **matcher** in the pipeline. Concrete codepath:

```
fetchers.GoldappleFetcher.run_loop
  → snapshot persistence (storage/sqlite.SqliteSnapshotWriter.append)
  → runner.gates.parse_quality_gate(null_rate)           ← existing D-218
  → runner.gates.parser_drift_null_rate_gate(...)        ← NEW (PARSE-FIX-04)
  → matcher.strict_key.run_matcher()                     ← existing D-402
```

The current parse-quality gate (`runner/gates.py:253-268`) checks that `null_rate(name OR current_price OR url)` ≤ 5% — a "required-fields" gate. The new gate is **content-quality** (volume + brand should be non-null at the aggregate level), strictly downstream.

### Recommended Helper Shape (matches D-203 retailer-agnostic shape)

```python
# In runner/gates.py, inserted after parse_quality_gate (around line 268)

@dataclass(frozen=True)
class ParserDriftGateResult:
    """Result of the PARSE-FIX-04 null-rate sanity gate.

    Fields:
      passed: True if both volume and brand null rates are at-or-below threshold.
      volume_null_rate: float in [0, 1]; computed by caller via SQL or in-memory.
      brand_null_rate:  float in [0, 1]; same.
      failure_reason:   None if passed; otherwise one of:
        - "parser_drift_null_volume_rate"
        - "parser_drift_null_brand_rate"
        - "parser_drift_null_both_rate"  (both exceeded — pick most-broken first)
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
    Matches D-218 `<=` convention for parse_quality_gate boundary inclusivity.

    Source: 08-CONTEXT.md D-813/D-814/D-815/D-816/D-817.
    """
    v_fail = volume_null_rate > threshold
    b_fail = brand_null_rate > threshold
    if v_fail and b_fail:
        reason = "parser_drift_null_volume_rate"  # volume wins priority per D-815
    elif v_fail:
        reason = "parser_drift_null_volume_rate"
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

### Null-Rate Computation (SQL Query Recommendation)

After snapshot persistence, the orchestrator computes the two null rates with a single round-trip:

```sql
SELECT
  AVG(CASE WHEN volume_norm IS NULL THEN 1.0 ELSE 0.0 END) AS volume_null_rate,
  AVG(CASE WHEN brand     IS NULL OR brand = '' THEN 1.0 ELSE 0.0 END) AS brand_null_rate
FROM snapshots
WHERE run_id = :run_id AND retailer = 'goldapple';
```

Both rates are `float` in `[0, 1]`. If `goldapple.fetch_count == 0` the query returns NULL for both rates — the orchestrator should treat this as "gate not applicable, skip" (defensive: avoid false-failing when the entire goldapple crawl was skipped).

### New Stats Keys (extend `GOLDAPPLE_STATS_KEYS` in `runner/stats.py`)

Per CONTEXT.md "Established Patterns": atomic `patch_stats` via `GoldappleStatsBuilder`. Add 3 keys to the existing `GOLDAPPLE_STATS_KEYS` tuple (line 18-32):

```python
GOLDAPPLE_STATS_KEYS: tuple[str, ...] = (
    # ... existing 13 keys ...
    "goldapple.volume_null_rate",       # NEW (PARSE-FIX-04) — float in [0, 1]
    "goldapple.brand_null_rate",        # NEW (PARSE-FIX-04) — float in [0, 1]
    "goldapple.parser_drift_failure_reason",  # NEW (PARSE-FIX-04) — str or None
)
```

Note: `failure_reason` could alternatively live in the top-level `runs.stats` (e.g. `run.stats.failure_reason`) since it's run-level not goldapple-namespaced. Recommend keeping it in `goldapple.*` for atomic-merge safety — `parser_drift_*` is a goldapple-specific concern per D-814.

### Orchestrator Wiring (pseudo-code for Plan 08-05)

```python
# After all retailer fetchers complete, after snapshot persistence + parse_quality_gate:
volume_null_rate, brand_null_rate = compute_goldapple_null_rates(engine, run_id)

drift_result = parser_drift_null_rate_gate(
    volume_null_rate=volume_null_rate,
    brand_null_rate=brand_null_rate,
    threshold=0.5,
)

builder = GoldappleStatsBuilder()
builder.set("volume_null_rate", drift_result.volume_null_rate)
builder.set("brand_null_rate",  drift_result.brand_null_rate)
builder.set("parser_drift_failure_reason", drift_result.failure_reason)
run_writer.patch_stats(run_id, builder.delta)

if not drift_result.passed:
    log.error(
        "phase8_parser_drift_gate_failed",
        run_id=run_id,
        volume_null_rate=drift_result.volume_null_rate,
        brand_null_rate=drift_result.brand_null_rate,
        reason=drift_result.failure_reason,
    )
    run_writer.finalize(run_id, "failed", reason=drift_result.failure_reason)
    return  # abort before matcher
```

### Synthetic Regression Test (Success Criteria #5)

```python
# tests/runner/test_parser_drift_gate.py
import pytest
from ga_crawler.runner.gates import parser_drift_null_rate_gate


class TestParserDriftNullRateGate:

    def test_both_rates_below_threshold_passes(self):
        result = parser_drift_null_rate_gate(
            volume_null_rate=0.1, brand_null_rate=0.05
        )
        assert result.passed
        assert result.failure_reason is None

    def test_exactly_at_threshold_passes(self):
        # D-815: STRICT > threshold (50% absolute) — exactly 0.5 PASSES
        result = parser_drift_null_rate_gate(
            volume_null_rate=0.5, brand_null_rate=0.5
        )
        assert result.passed

    def test_volume_exceeds_threshold_fails_with_volume_reason(self):
        # Synthetic regression: 60% null volume (Success Criteria #5)
        result = parser_drift_null_rate_gate(
            volume_null_rate=0.6, brand_null_rate=0.0
        )
        assert not result.passed
        assert result.failure_reason == "parser_drift_null_volume_rate"
        assert result.volume_null_rate == 0.6

    def test_brand_exceeds_threshold_fails_with_brand_reason(self):
        result = parser_drift_null_rate_gate(
            volume_null_rate=0.0, brand_null_rate=0.7
        )
        assert not result.passed
        assert result.failure_reason == "parser_drift_null_brand_rate"

    def test_both_exceed_volume_wins_priority(self):
        # D-815 priority: volume first
        result = parser_drift_null_rate_gate(
            volume_null_rate=0.8, brand_null_rate=0.7
        )
        assert not result.passed
        assert result.failure_reason == "parser_drift_null_volume_rate"

    def test_custom_threshold(self):
        result = parser_drift_null_rate_gate(
            volume_null_rate=0.3, brand_null_rate=0.0, threshold=0.2
        )
        assert not result.passed
        assert result.failure_reason == "parser_drift_null_volume_rate"
```

Integration-level test (against in-memory SQLite, mirrors `synthetic_report_run` fixture pattern in `conftest.py`):

```python
def test_phase8_gate_fails_synthetic_regression_run(in_memory_sqlite_session):
    """Success Criteria #5 — synthetic snapshot batch with 60% null volume
    triggers run.status=failed with reason=parser_drift_null_volume_rate.
    """
    # Plant 10 goldapple snapshots: 6 with volume_norm=NULL, 4 with valid volume
    # ... (mirror `synthetic_report_run` planting shape)
    # Run the gate via orchestrator wiring
    # Assert: run row has status='failed', stats.parser_drift_failure_reason==expected
```

---

## W0 Sub-Spike Protocol — Camoufox Capture Script + Stratification + Output

### Capture Script Outline

Per CONTEXT.md "Code Context — Reusable Assets": **`src/ga_crawler/fetchers/goldapple.GoldappleFetcher` is verbatim reused** — the W0 spike does NOT add new fetcher infrastructure (that's Phase 9 TEST-HARNESS-05).

Recommended ad-hoc script (NOT committed long-term; lives in `.planning/spikes/v1.1-brand-name-shapes/capture.py` alongside the artifacts, OR in `scripts/` if convention preferred — operator's call per CONTEXT.md):

```python
# .planning/spikes/v1.1-brand-name-shapes/capture.py
# Ad-hoc 30-PDP capture for Phase 8 W0 shape-sampling spike (D-801..D-804).
# Phase 9 (TEST-HARNESS-05) will formalize this as `python -m ga_crawler capture-fixtures`.

import asyncio
from pathlib import Path
from ga_crawler.fetchers.goldapple import GoldappleFetcher

# Stratified 5x6 = 30 URLs across 5 categories × 6 brands per CONTEXT.md D-801.
# Operator curates list before run; URLs sourced from goldapple sitemap or
# manual catalog browse. Document each in shape-table.md with its bucket label.
URLS: list[tuple[str, str]] = [
    # (slug-tag-for-filename, full-URL)
    # bucket 1: lux (e.g. Tom Ford, Creed, Frederic Malle, Maison Margiela, Chanel, Dior)
    ("lux-tomford-noir",      "https://goldapple.kz/..."),
    # ... 5 more
    # bucket 2: mass-market (Givenchy, YSL, Versace, Calvin Klein, Hugo Boss, Armani)
    # ... 6
    # bucket 3: niche (STEREOTYPE, Byredo, Le Labo, Maison Crivelli, Profumum Roma, Memo)
    # ... 6
    # bucket 4: RU-brands (Натура Сибирика, Чистая Линия, Black Pearl, Лошадиная Сила, Невская Косметика, Сибирские Травы)
    # ... 6
    # bucket 5: multi-word brands (Tom Ford, Jo Malone, Atelier Cologne, Maison Margiela, By Kilian, Diptyque)
    # ... 6
]
assert len(URLS) == 30, f"expected 30, got {len(URLS)}"

OUTPUT_DIR = Path(__file__).parent

async def main():
    fetcher = GoldappleFetcher.from_config()  # uses pyproject.toml [tool.ga_crawler.crawl.goldapple]
    async with fetcher:
        for i, (slug, url) in enumerate(URLS, start=1):
            print(f"[{i:02d}/30] fetching {slug}: {url}")
            rec = await fetcher.fetch_one(fetcher._page, url)
            html = rec.get("html") or ""
            status = rec.get("status")
            size = len(html)
            print(f"  → status={status} size={size}")
            if html:
                out = OUTPUT_DIR / f"pdp-{i:02d}-{slug}.html"
                out.write_text(html, encoding="utf-8")
                print(f"  → saved {out.name}")
            # Camoufox rate-limit per spike-01-goldapple/SKILL.md: 3-5s random uniform.
            # Already enforced by GoldappleFetcher.fetch_one() per Phase 3 D-307.

if __name__ == "__main__":
    asyncio.run(main())
```

**Wall-clock budget:** 30 URLs × 4s avg = 120s fetch + ~30s Camoufox warm-up = ~3 min raw fetch. Plus 10-15 min for the operator to skim each HTML, fill `shape-table.md`, and write `MEMO.md` conclusions. Total W0 spike budget: **30-60 minutes wall-clock**.

### Stratification Rationale (D-801)

| Bucket | Why include | Risk if missing |
|--------|-------------|-----------------|
| Lux | High-margin SKUs; STEREOTYPE-style brand UI common | Miss the uppercase-brand concatenation shape |
| Mass-market | Largest viled overlap; matcher coverage critical | Miss the Armani-lowercase-concat shape |
| Niche | Slug-style names; tests `_extract_volume_block` brittleness | Overfit to Givenchy baseline |
| RU-brands | Cyrillic-uppercase brand text; tests Lexbor case-insensitive | Miss "НАТУРА СИБИРИКА" Cyrillic concat case |
| Multi-word brands | Brand prefix has spaces; tests `_strip_brand_prefix` if needed | Miss "Tom Fordtom ford noir" multi-word concat |

### Output Format

Per CONTEXT.md D-802, the spike directory contents:

```
.planning/spikes/v1.1-brand-name-shapes/
├── MEMO.md              ← 1-page summary: which shape buckets exist, which selector works
├── shape-table.md       ← 30 PDP × 6 columns survey table (template below)
├── capture.py           ← (optional) ad-hoc capture script
└── pdp-NN-slug.html     ← 30 raw HTML files (gzip if total >5 MB)
```

**`shape-table.md` template:**

```markdown
# Phase 8 W0 Shape-Sampling Survey — 30 goldapple PDPs (2026-05-13)

| # | Bucket | Brand (raw `<meta>`) | Brand (rendered `<h1>`) | Name (raw `<meta>`) | `<h1>` text | Volume block present? | Volume label text | Shape bucket |
|---|--------|---------------------|------------------------|---------------------|-------------|----------------------|---------------------|----------------|
| 01 | lux | `Tom Ford ` | `TOM FORD` | `Noir Extreme` | `TOM FORDnoir extreme` | ✅ | `78 ОБЪЁМ / МЛ` | STEREOTYPE-style |
| 02 | mass-market | `Armani ` | `Armani` | `armani code` | `Armaniarmani code` | ✅ | `100 ОБЪЁМ / МЛ` | Armani-style |
| 03 | niche | `STEREOTYPE ` | `STEREOTYPE` | `sago` | `STEREOTYPEsago` | ✅ | `75 ОБЪЁМ / МЛ` | STEREOTYPE-style |
| ... | | | | | | | |
| 30 | | | | | | | |

## Shape Buckets Identified

- **Givenchy-baseline** (N=X): `<h1>` is clean product name; volume embedded in title. EXISTING fixture covers.
- **STEREOTYPE-style** (N=X): brand uppercased+prefixed in `<h1>`; volume in separate block. NEW Plan 08-02/03 target.
- **Armani-style** (N=X): brand lowercased+prefixed in `<h1>`; volume in separate block. NEW.
- **(Discovered)** (N=X): ... — flag any new shape variant for plan re-scoping.

## Selector Validation

- `tree.css('div:lexbor-contains("ОБЪЁМ" i)')` matches: X/30 PDPs.
- `<meta itemprop="name">` (product-level, sibling of `[itemprop="brand"]`) present in: X/30 PDPs.
- Brand-prefix fallback needed? (per D-806 "<95% threshold"): Y/N.

## Selected Fixture URLs for v1.1 Plans

- `_live-2026-05-13-stereotype.html` ← PDP #03 (STEREOTYPE/sago) — Bug #1 + #2 evidence
- `_live-2026-05-13-armani-code.html` ← PDP #02 (Armani/code) — Bug #2 evidence
- SMOKE_URLs rotation slot 1 (STEREOTYPE-style): PDP #XX URL
- SMOKE_URLs rotation slot 2 (Armani-style): PDP #YY URL
```

**`MEMO.md` template:**

```markdown
# Phase 8 W0 Spike — Brand-Name-Volume Shape Findings

**Completed:** 2026-05-13
**Fetched:** 30 PDPs across 5 stratification buckets via Camoufox 0.4.11 from <location>
**Conclusion:** {summary — selector validated / fallback needed / new shape discovered}

## What works

- `:lexbor-contains("ОБЪЁМ" i)` matched volume label in X/30 PDPs (Y%) — covers {buckets}.
- `<meta itemprop="name">` at product level present in X/30 PDPs (Y%) — Plan 08-03 can rely on microdata-primary.

## What doesn't

- {edge cases — e.g. "PDP #17 has volume in JSON data attribute, not flexbox — flag for v1.2"}

## Decisions

- `_extract_volume_block` parent-iter strategy: confirmed.
- `_strip_brand_prefix` fallback: {needed / not needed} based on {X/30} `<meta>` coverage.

## Open issues

- (none / list)

## Handoff

- See `shape-table.md` for per-PDP detail.
- 3 fixtures committed: stereotype.html, armani-code.html, contre-jour.html (viled).
- Skill wrap-up: `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md`
```

### Project-Local Skill Wrap-Up (D-803)

Mirror `.claude/skills/spike-01-goldapple/SKILL.md` shape. Template:

```markdown
---
name: spike-findings-v1.1-brand-name-shapes
description: Phase 8 W0 spike findings — goldapple PDP brand/name/volume shape buckets. Use when planning Phase 8 W1 plans (08-02/03), Phase 9 brand-coverage canary, or any future parser-drift investigation.
---

# Spike v1.1 brand-name-shapes (Reference Skill)

**Source memo:** [[.planning/spikes/v1.1-brand-name-shapes/MEMO]]
**Survey table:** [[.planning/spikes/v1.1-brand-name-shapes/shape-table]]
**Spike completed:** 2026-05-13
**Phase 8 W0 status:** DONE

## What was decided

{summary — same as MEMO.md "Conclusion"}

## Shape buckets identified

| Bucket | Frequency in 30-PDP sample | Selector / extraction strategy |
|--------|---------------------------|--------------------------------|
| Givenchy-baseline | X/30 | volume embedded in name; existing parser path |
| STEREOTYPE-style | X/30 | `<meta itemprop="name">` for both brand + name; `:lexbor-contains("ОБЪЁМ" i)` for volume |
| Armani-style | X/30 | same as STEREOTYPE |
| (discovered) | X/30 | {note} |

## Operational constants

- `<meta itemprop="name">` coverage: Y%. Above 95% threshold → `_strip_brand_prefix` fallback NOT NEEDED.
- `:lexbor-contains("ОБЪЁМ" i)` match rate: Y%.

## When to consult this skill

- `/gsd-plan-phase 8` — for plans 08-02 (volume), 08-03 (brand+name), 08-04 (viled volume)
- `/gsd-discuss-phase 9` — for TEST-HARNESS-04 brand-coverage canary (which brands to enforce)
- Any "did v1.1 W0 cover bucket X?" question

## Critical files

- [[.planning/spikes/v1.1-brand-name-shapes/MEMO]]
- [[.planning/spikes/v1.1-brand-name-shapes/shape-table]]
- [[tests/fixtures/goldapple/_live-2026-05-13-stereotype.html]]
- [[tests/fixtures/goldapple/_live-2026-05-13-armani-code.html]]
- [[tests/fixtures/viled/_live-2026-05-13-contre-jour.html]]
```

---

## Fixture-Capture Pattern — conftest.py Extension Recipe

Per CONTEXT.md "Reusable Assets" lines 124-128 and "Established Patterns" lines 132 — append-only, retailer-grouped, NOT `tests/fixtures/live/`.

### File Placement

```
tests/fixtures/goldapple/
├── _debug-product-page.html              ← EXISTING Givenchy baseline (UNTOUCHED)
├── gate-shell.html                       ← EXISTING (UNTOUCHED)
├── stale-sku-9.5kb.html                  ← EXISTING (UNTOUCHED)
├── _live-2026-05-13-stereotype.html      ← NEW Bug #1 + #2 evidence
└── _live-2026-05-13-armani-code.html     ← NEW Bug #2 evidence

tests/fixtures/viled/
├── viled-pdp-407682.html                 ← EXISTING clothing (UNTOUCHED)
├── viled-pdp-discounted.html             ← EXISTING Frederic Malle 50ml beauty
├── viled-pdp-multipack.html              ← EXISTING beauty (UNTOUCHED)
├── viled-catalog-men-1310-page1.html     ← EXISTING (UNTOUCHED)
├── viled-catalog-women-1310-page1.html   ← EXISTING (UNTOUCHED)
└── _live-2026-05-13-contre-jour.html     ← NEW Bug #3 evidence
```

### `conftest.py` Extension (6 lines, per CONTEXT.md line 125)

Append after line 91 `jsonld_blocks_anti_fixture` fixture, BEFORE line 93 `# ---- Phase 2 contract mocks ----` section:

```python
# ---- Phase 8 (v1.1) live PDP fixtures (D-822 append-only pattern) ----

@pytest.fixture(scope="session")
def goldapple_pdp_html_live_stereotype() -> str:
    """STEREOTYPE/sago live PDP captured 2026-05-13 (Bug #1 + Bug #2 evidence).

    Brand `<meta itemprop="name">` content="STEREOTYPE "; product `<meta itemprop="name">`
    content="sago"; `<h1>` text "STEREOTYPEsago" (concat). Volume block `[75] ОБЪЁМ / МЛ`
    in flex-box of <div>s without itemprop="size".
    Source: .planning/spikes/v1.1-brand-name-shapes/pdp-NN-stereotype-sago.html.
    """
    return (FIXTURES_DIR / "_live-2026-05-13-stereotype.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def goldapple_pdp_html_live_armani() -> str:
    """Armani code live PDP captured 2026-05-13 (Bug #2 evidence).

    Brand "Armani"; product "armani code"; `<h1>` text "Armaniarmani code" (concat lowercase).
    Source: .planning/spikes/v1.1-brand-name-shapes/pdp-NN-armani-code.html.
    """
    return (FIXTURES_DIR / "_live-2026-05-13-armani-code.html").read_text(encoding="utf-8")
```

And after line 189 `viled_pdp_multipack_html`:

```python
@pytest.fixture(scope="session")
def viled_pdp_html_live_contre_jour() -> str:
    """Frederic Malle Contre-Jour live PDP captured 2026-05-13 (Bug #3 evidence).

    name `Парфюмерная вода Contre-Jour` (no volume in title). Verify whether
    Размер attribute is present in pp.attributes[0].attributes[] (likely absent
    for this SKU — that's the "legitimate None" case for D-814).
    Source: .planning/spikes/v1.1-brand-name-shapes/viled-contre-jour.html.
    """
    return (VILED_FIXTURES_DIR / "_live-2026-05-13-contre-jour.html").read_text(encoding="utf-8")
```

**Total lines added:** 6 fixture declarations (with docstrings ≈ 25 LOC).

### Fixture Size & Repo Hygiene

- Goldapple PDPs are ~200-300 KB each (per existing `_debug-product-page.html` size); 2 new × 300 KB = ~600 KB.
- Viled PDPs are ~100-150 KB each; 1 new × 150 KB = ~150 KB.
- Total Phase 8 fixture commit: ~750 KB raw HTML. Well under any reasonable repo bloat threshold; no gzip needed (Phase 9 will introduce the >5MB-gzip threshold as TEST-HARNESS-02 sidecar metadata).

---

## Validation Architecture

> **Nyquist rationale:** Phase 8 has 5 specific behavioral requirements (PARSE-FIX-01..05). For each, the test surface must (a) be runnable in ≤30s for per-task commits, (b) target the actual production code path (no synthetic stubs that bypass parser logic), and (c) sample sufficient shape variants to prove the fix generalizes beyond a single fixture (the v1.0 audit gap that masked run #13).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio ≥0.24 (existing, LOCKED) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` (lines 51-53 markers `live`, `integration`) |
| Quick run command | `uv run pytest tests/parsers tests/runner/test_parser_drift_gate.py -x` |
| Full suite command | `uv run pytest -m "not live" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PARSE-FIX-01 | `_extract_volume_block(html)` returns non-None for `_live-2026-05-13-stereotype.html` with text containing digit + Russian volume label | unit | `uv run pytest tests/parsers/test_goldapple_volume_block.py -x` | ❌ Wave 0 (Plan 08-02 W1) |
| PARSE-FIX-01 | `parse_pdp(stereotype_html)` yields `GoldappleRawProduct` with `raw_volume_text` containing digit + "МЛ" / "мл" | unit | same file | ❌ Wave 0 |
| PARSE-FIX-01 | parametrized: ≥3 fixtures (Givenchy baseline + STEREOTYPE + Armani) all yield non-None `volume_norm` after running through `normalizers/volume.parse_volume` | unit (parametrize) | same file | ❌ Wave 0 |
| PARSE-FIX-02 | `parse_pdp(armani_html).brand_raw.lower() not in parse_pdp(armani_html).name.lower()` invariant canary | unit | `uv run pytest tests/parsers/test_goldapple_brand_name.py::test_invariant_canary -x` | ❌ Wave 0 (Plan 08-03 W1) |
| PARSE-FIX-02 | `parse_pdp(stereotype_html).name == "sago"` (microdata read, NOT `<h1>` concat) | unit | same file | ❌ Wave 0 |
| PARSE-FIX-02 | `parse_pdp(givenchy_html).name == "Pour Homme"` (backward-compat: existing fixture still parses correctly) | unit | same file | ❌ Wave 0 |
| PARSE-FIX-03 | `_extract_volume_from_nextdata({...})` returns "50 мл" for discounted-beauty fixture | unit | `uv run pytest tests/parsers/test_viled_volume_from_nextdata.py -x` | ❌ Wave 0 (Plan 08-04 W1) |
| PARSE-FIX-03 | parametrized: 4 fixtures (407682 clothing → "S", multipack → "200мл+...", discounted → "50 мл", contre-jour live → None) | unit (parametrize) | same file | ❌ Wave 0 |
| PARSE-FIX-03 | `parse_pdp(viled_discounted_html).raw_volume_text == "50 мл"` (not the full name) — flips the existing test | unit (modify existing) | `uv run pytest tests/parsers/test_viled_nextdata.py -x` | ✅ exists (modify 1 assertion) |
| PARSE-FIX-04 | `parser_drift_null_rate_gate(0.6, 0.0)` returns `passed=False, reason="parser_drift_null_volume_rate"` | unit | `uv run pytest tests/runner/test_parser_drift_gate.py -x` | ❌ Wave 0 (Plan 08-05 W2) |
| PARSE-FIX-04 | parametrized: 6 boundary cases (both pass / volume-fails / brand-fails / both-fail / exactly-at-threshold / custom-threshold) | unit (parametrize) | same file | ❌ Wave 0 |
| PARSE-FIX-04 | Synthetic regression: in-memory SQLite with 60% NULL `volume_norm` snapshots → orchestrator finalizes run with `status="failed"` and `stats.parser_drift_failure_reason="parser_drift_null_volume_rate"` (Success Criteria #5) | integration | `uv run pytest tests/integration/test_phase8_synthetic_regression.py -x` | ❌ Wave 0 (Plan 08-05 W2) |
| PARSE-FIX-05 | `SMOKE_URLS` constant in `runner/gates.py` has length 3, contains a STEREOTYPE-style URL, an Armani-style URL, and the Givenchy-baseline URL `19000488678-givenchy-irresistible` | unit (structural canary) | `uv run pytest tests/runner/test_smoke_urls_rotation.py -x` | ❌ Wave 0 (Plan 08-05 W2) |
| **Aggregate** | All 803 existing tests stay green; ~818 total after Phase 8 lands | regression | `uv run pytest -m "not live" -q` | n/a |

### Sampling Sufficiency (Nyquist coverage rationale)

For each parser fix, the test set must oversample the shape diversity revealed by the W0 spike. Sufficiency rule of thumb:

- **PARSE-FIX-01 volume:** ≥3 fixtures covering Givenchy-baseline (volume-in-title), STEREOTYPE-style (separate-block, uppercase), Armani-style (separate-block, mixed-case). If W0 reveals a 4th shape bucket, add a 4th fixture.
- **PARSE-FIX-02 brand+name:** ≥3 fixtures covering the same buckets. Invariant canary `brand.lower() not in name.lower()` must hold across all of them and across the existing 60+ Givenchy tests.
- **PARSE-FIX-03 viled volume:** ≥4 fixtures — 3 existing (clothing "S", multipack "200мл+...", beauty "50 мл") + 1 live Contre-Jour (no `Размер`). Disambiguation rule (clothing "S" → `volume_norm=None`) is verified by passing through real `parse_volume` not a mock.
- **PARSE-FIX-04 null-rate gate:** ≥6 unit-test boundary cases (both-pass, volume-fail, brand-fail, both-fail, exactly-at-threshold, custom-threshold) + 1 integration test injecting 60% null volumes against in-memory SQLite. Sufficient to prove the gate handles all branches AND wires correctly to `runs.stats` + `runs.status`.
- **PARSE-FIX-05 smoke rotation:** 1 structural canary asserting `SMOKE_URLS` shape. Real-world validation is the next live run (out-of-scope for Phase 8 acceptance; covered by Phase 11 cron tick).

### Sampling Rate

- **Per task commit:** `uv run pytest tests/parsers tests/runner -x` (~10-15s) — runs only Phase 8-touched test modules.
- **Per wave merge:** `uv run pytest -m "not live" -q` (~803 → 818 tests, ~60-90s baseline) — full suite green.
- **Phase gate (before `/gsd-verify-work 8`):** full suite + manual visual inspection of `tests/fixtures/goldapple/_live-2026-05-13-*.html` to confirm fixtures are real HTML (not Camoufox error pages).

### Wave 0 Gaps

- [ ] `tests/parsers/test_goldapple_volume_block.py` — covers PARSE-FIX-01 (Plan 08-02 W1)
- [ ] `tests/parsers/test_goldapple_brand_name.py` — covers PARSE-FIX-02 (Plan 08-03 W1)
- [ ] `tests/parsers/test_viled_volume_from_nextdata.py` — covers PARSE-FIX-03 (Plan 08-04 W1)
- [ ] `tests/runner/test_parser_drift_gate.py` — covers PARSE-FIX-04 unit (Plan 08-05 W2)
- [ ] `tests/integration/test_phase8_synthetic_regression.py` — covers PARSE-FIX-04 SC#5 integration (Plan 08-05 W2)
- [ ] `tests/runner/test_smoke_urls_rotation.py` — covers PARSE-FIX-05 (Plan 08-05 W2)
- [ ] `tests/conftest.py` — append 3 new fixture loaders (Plan 08-01 W0)
- [ ] `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` — committed (Plan 08-01 W0)
- [ ] `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` — committed (Plan 08-01 W0)
- [ ] `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` — committed (Plan 08-01 W0)

**Framework install:** None — pytest 8.x and pytest-asyncio ≥0.24 already in `pyproject.toml [dependency-groups].dev`.

**selectolax upgrade:** `uv lock --upgrade-package selectolax && uv sync` after bumping `pyproject.toml [project].dependencies` to `selectolax>=0.4.7,<0.5`. This is a separate first-step in Plan 08-02 W1 (selectolax bump RED test → bump → GREEN).

---

## Security Domain

> Phase 8 modifies HTML/JSON parsing logic and adds a stats-gate. No new auth surface, no new network egress, no new file write boundary. Most ASVS controls are not applicable.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | (no auth changes) |
| V3 Session Management | no | (no session state) |
| V4 Access Control | no | (no privilege boundary changes) |
| V5 Input Validation | **yes** | `parse_volume` / `parse_brand` normalizers (existing) handle malicious/malformed HTML strings — selectolax parser is robust against XSS injection at parse time (no eval). New `_extract_volume_block` and `_extract_volume_from_nextdata` operate on already-parsed nodes/dicts. |
| V6 Cryptography | no | (no crypto operations) |
| V7 Error Handling and Logging | **yes** | New stats keys `goldapple.volume_null_rate`, `goldapple.brand_null_rate`, `goldapple.parser_drift_failure_reason` are written to `runs.stats` via existing atomic `patch_stats` (`GoldappleStatsBuilder`) — no log injection risk. Logging via `structlog` (existing pattern). |
| V12 Files and Resources | **yes** | 3 new HTML fixtures committed to repo (`tests/fixtures/<retailer>/_live-2026-05-13-*.html`). Operator must verify no PII or session tokens in captured HTML before commit (anti-Pitfall #3 from research SUMMARY.md). |

### Known Threat Patterns for HTML Parser Code

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed HTML triggering parser crash | Denial of Service | selectolax Lexbor is robust; wrap helper calls in try/except returning `None` on `Exception`. Existing v1.0 parsers already do this implicitly via guard clauses. |
| Selector injection (CSS string concatenation) | Tampering | All CSS selectors in `_extract_volume_block` are HARDCODED string literals (`'div:lexbor-contains("ОБЪЁМ" i)'`) — no user input flows into selectors. NOT a risk. |
| PII / session tokens leaking into committed fixtures | Information Disclosure | Pre-commit visual review of 3 new `_live-*.html` files. Phase 9 (TEST-HARNESS-02) will formalize a `gitleaks` + canary scan for `cf_clearance=`, `bot\d+:`, UUID-shaped hc-ping paths. Phase 8 informally requires the operator to skim. |
| Stats key explosion via dynamic keys | Tampering | `GOLDAPPLE_STATS_KEYS` tuple in `runner/stats.py` is frozen; `GoldappleStatsBuilder._resolve` raises `StatsNamespaceError` on unknown keys. Adding 3 new keys is a controlled, code-reviewed change. |
| Gate-bypass via numeric coercion bugs | Tampering | `parser_drift_null_rate_gate` takes `float` inputs; the SQL `AVG(CASE WHEN ... THEN 1.0 ELSE 0.0)` produces a guaranteed-numeric result. Edge case: empty `snapshots` table → SQL returns NULL → orchestrator must handle (recommend: treat as "gate not applicable, skip" rather than 0.0 which would silently pass). |

---

## Pitfalls and Landmines

### Pitfall 1: `:contains` syntax confusion

`:contains()` is jQuery, NOT W3C CSS. selectolax (both Modest and Lexbor) only supports `:lexbor-contains()`. Writing `:contains("ОБЪЁМ")` returns zero matches silently — there is NO selector parse error. Always use the `:lexbor-contains` prefix and the case-insensitive `" i"` flag with a leading space.

**Warning sign:** Plan 08-02 RED test returns "no match" when the live HTML clearly contains the label. Check the selector string first.

### Pitfall 2: Ё vs Е Unicode normalization

Russian text `ОБЪЁМ` uses uppercase Ё (U+0401), but some content management systems normalize it to Е (U+0415). If goldapple's PDP source uses Е instead of Ё, `:lexbor-contains("ОБЪЁМ" i)` returns zero matches even with the `i` flag — case-insensitivity does NOT apply to Е↔Ё distinction.

**Prevention:** W0 spike output must include the exact byte sequence of the volume label from one captured HTML. If the live PDP uses Е, the selector becomes `:lexbor-contains("ОБЪЕМ" i)` — OR use two `tree.css(...)` calls and `or` the results.

**Warning sign:** Spike PDP capture works (HTML file has visible "ОБЪЁМ" text) but `_extract_volume_block` returns None. Hex-dump the label region.

### Pitfall 3: Cyrillic-uppercase brand in `<meta itemprop="name">`

Goldapple renders `STEREOTYPE` in the `<meta itemprop="name" content="STEREOTYPE ">` as Latin uppercase, but the `<h1>` may emit a CSS-transformed version of a different underlying string. For Russian brands (e.g. НАТУРА СИБИРИКА), the `<meta>` content may itself be the Cyrillic uppercase form. The invariant canary `brand.lower() not in name.lower()` requires `.lower()` to handle Cyrillic correctly — Python's `str.lower()` DOES handle Cyrillic correctly per Unicode standard, so this is fine. Test it.

**Prevention:** Plan 08-03 includes one parametrized test with a Cyrillic-brand fixture if W0 spike captures one (RU-brands bucket per D-801). If no RU-brand surfaces in W0, defer to v1.2.

### Pitfall 4: viled `Размер` ambiguity (clothing "S" vs beauty "50 мл")

The same `Размер` attribute name carries clothing size (`"S"`, `"L"`) OR volume (`"50 мл"`). Disambiguation is delegated to `normalizers/volume.parse_volume` per existing v1.0 contract — it returns `None` for non-volume strings. The new `_extract_volume_from_nextdata` helper does NOT branch on category; it just returns whatever `Размер` carries verbatim.

**Why this is safe:** Phase 4 matcher SQL filter `volume_norm IS NOT NULL` already excludes clothing SKUs from the strict-key join. Viled clothing flowed through v1.0 already and was correctly excluded by null volume_norm. We're not regressing.

**Warning sign:** Plan 08-04 test for clothing fixture asserts `volume_norm == None` after parse pipeline, not after `_extract_volume_from_nextdata`. Both should be tested.

### Pitfall 5: selectolax 0.4 vs 0.3 constructor compatibility

`LexborHTMLParser(html)` does NOT accept `detect_encoding=` or `use_meta_tags=`. If existing code somewhere passes these to a Lexbor parser (it doesn't, per current `parsers/goldapple_microdata.py:32` import), `TypeError` raises. The proposed strict-local Lexbor import inside `_extract_volume_block` avoids this entirely — but if some future plan moves Lexbor to module-level, audit constructor calls.

**Warning sign:** `uv sync` after upgrade succeeds but `pytest` immediately fails with `TypeError: __init__() got unexpected keyword argument 'detect_encoding'`. Look for misplaced `LexborHTMLParser(html, detect_encoding=...)` calls.

### Pitfall 6: PARSE-FIX-04 false-positive on empty crawl

If goldapple crawl completely fails (`fetch_count == 0`), the null-rate SQL query returns NULL (no rows to average). Orchestrator must guard:

```python
if goldapple_fetch_count == 0:
    log.warning("phase8_drift_gate_skipped_no_snapshots", run_id=run_id)
    # Skip gate; let existing parse_quality_gate / final_threshold_gate
    # handle the "zero crawl" failure mode (they already do per D-218/D-203).
    return
```

**Warning sign:** Synthetic-regression test for "zero goldapple snapshots" asserts gate raises or skips, not "passes with rate=0".

### Pitfall 7: Fixture commit safety (HTML may contain captured cookies)

Camoufox session cookies, `cf_clearance` tokens, and UUID-shaped IDs may leak into captured HTML if the PDP body renders them server-side (rare but possible). Plan 08-01 RED-gate before fixture commit: operator runs `git diff --staged` and visually scans for `cf_clearance=`, `bot\d+:`, hex UUIDs, JWT tokens. Phase 9 TEST-HARNESS-02 will formalize a `gitleaks` precommit; Phase 8 relies on operator discipline.

**Warning sign:** Any `[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}` substring in a `_live-*.html` diff.

### Pitfall 8: Lexbor `tree.css()` returns LexborNode, not Node

`selectolax.parser.Node` and `selectolax.lexbor.LexborNode` are SEPARATE classes. Their APIs are similar but not identical (e.g. `.parser` attribute name differs in some versions). Helpers operating on Lexbor nodes must use `LexborNode` type hints or duck-type. Mixing parsers (e.g. passing a `LexborNode` to a function expecting `selectolax.parser.Node`) raises at attribute access.

**Prevention:** `_extract_volume_block` operates entirely within Lexbor namespace — accepts raw `html: str`, instantiates `LexborHTMLParser` locally, returns `Optional[str]`. No node objects cross the helper boundary.

### Pitfall 9: Existing 803 tests use Modest backend; bump must not break them

Bumping `selectolax>=0.4.7,<0.5` activates the upstream deprecation warning for `HTMLParser` (Modest). Pytest may capture this as test-output noise. If `[tool.pytest.ini_options]` enables `filterwarnings = ["error"]`, the bump breaks existing tests.

**Check before bump:** `grep "filterwarnings" pyproject.toml` — confirm no `error` mode. v1.0 uses warning-mode default (no filterwarnings configured), so this is fine, but verify before Plan 08-02 RED step.

### Pitfall 10: Spike output fidelity loss if rushed

The W0 spike's value is the shape-table — NOT the raw HTML. If the operator captures 30 HTMLs but does not fill `shape-table.md` carefully, Plan 08-02/03 implementers can't tell which DOM shape they're targeting. Per CONTEXT.md D-808 the output gate is: shape-table.md commitable + 3 fixtures committed + SKILL.md created. Enforce this gate in Plan 08-01 verification.

---

## Sources

### Primary (HIGH confidence)

- **Context7 `/websites/selectolax_readthedocs_io_en`** — fetched 2026-05-13. Topics: `LexborHTMLParser` constructor, `:lexbor-contains("text" i)` pseudo-class (case-insensitive flag syntax, MUST include leading space), `LexborSelector.text_contains(text, deep=True, separator='', strip=False)`, `LexborNode.parent` / `.next` / `.prev` / `.iter(include_text, skip_empty)` traversal API, Modest backend marked DEPRECATED upstream
- **In-repo empirical trace (this research session)** — verified `props.pageProps.attributes[0].attributes[]` is the descriptive-attributes path for viled `Размер` across all 3 in-repo fixtures (`viled-pdp-407682.html`, `viled-pdp-multipack.html`, `viled-pdp-discounted.html`); confirmed `props.pageProps.item.attributes` is `None` on all 3
- **In-repo code reads** — `src/ga_crawler/parsers/goldapple_microdata.py` lines 319-375 (current brand/name/volume extraction code); `src/ga_crawler/parsers/viled_nextdata.py` lines 124-216 (current viled NEXT_DATA flow); `src/ga_crawler/runner/gates.py` lines 218-268 (D-203 gate-helper pattern); `src/ga_crawler/runner/stats.py` lines 18-32, 45-108 (`GoldappleStatsBuilder` + atomic patch_stats); `tests/conftest.py` lines 23-37, 165-200 (fixture loading pattern); `tests/fixtures/goldapple/_debug-product-page.html` (Givenchy baseline microdata shape)
- **CONTEXT.md** — Phase 8 decisions D-801..D-819, deferrals, claude's-discretion items
- **`.planning/research/v1.1-PARSER-BUG-FINDINGS.md`** — DB samples from run #13, live PDP screenshot description (STEREOTYPE/sago + Armani/code)

### Secondary (MEDIUM confidence)

- **PyPI** [selectolax](https://pypi.org/project/selectolax/) — latest 0.4.8 (May 2026 per WebFetch); confirms `>=0.4.7,<0.5` pin range
- **selectolax docs** [parser module](https://selectolax.readthedocs.io/en/latest/parser.html), [lexbor backend](https://selectolax.readthedocs.io/en/latest/lexbor.html), [examples](https://selectolax.readthedocs.io/en/latest/examples.html) — sibling-navigation patterns + `:lexbor-contains` syntax (confirmed via Context7)
- **`.planning/research/SUMMARY.md` § Key Findings** — v1.1 milestone context (Pitfalls 1-5 explicit list, build order rationale, locked decisions)
- **`.planning/research/STACK.md` § A/C** — selectolax 0.4 rationale + viled `attributes` shape (note: this research session's empirical trace SUPERSEDES STACK.md tentative path guidance — see §"viled NextData attributes")
- **`.planning/research/ARCHITECTURE.md` §A** — file-line integration points for Bugs #1/#2/#3 + Option 3 dual-fixture strategy

### Tertiary (LOW confidence — flagged for W0 validation)

- **STEREOTYPE/Armani microdata coverage hypothesis** — that goldapple emits `<meta itemprop="name">` at product level for ALL PDPs (not just Givenchy). Confirmed only against `_debug-product-page.html` Givenchy fixture. **W0 spike MUST validate** against ≥20 of 30 captured PDPs before Plan 08-03 commits to microdata-primary path.
- **Volume-block DOM hypothesis** — that the flexbox shape is `<div>78</div><div>ОБЪЁМ / МЛ</div>` siblings. Inferred from `v1.1-PARSER-BUG-FINDINGS.md` line 22 plus general goldapple UI rendering. **W0 spike MUST validate** by visual DOM inspection in DevTools or via direct HTML grep on captured fixtures.
- **Ё vs Е encoding in live HTML** — assumed Ё (U+0401) per `BUG-FINDINGS.md` literal `ОБЪЁМ`. Live HTML may differ — W0 must hex-dump one label.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Goldapple emits `<meta itemprop="name">` at product level on ≥95% of PDPs | goldapple PDP Shape | If <95% — `_strip_brand_prefix` fallback required, Plan 08-03 expands |
| A2 | Volume block DOM is `<div>78</div><div>ОБЪЁМ / МЛ</div>` siblings under a common parent | goldapple PDP Shape | If different (e.g. `<span>78</span>` siblings in same `<div>`) — `parent.iter()` strategy stays valid; only the tag in `tree.css('div:lexbor-contains(...)')` changes |
| A3 | Goldapple uses Ё (U+0401), not Е (U+0415), in "ОБЪЁМ" label | selectolax 0.4 Lexbor | Selector must handle both; trivial code-level fix once W0 reveals the byte |
| A4 | viled `Размер` attribute always lives at `pp.attributes[0].attributes[]` (not `[1]` or higher) | viled NextData attributes | Multi-variant PDPs may put `Размер` in another slot — helper should iterate all `pp.attributes[]` if W0 reveals this |
| A5 | `parser_drift_null_rate_gate` with `>` (strict) at 0.5 threshold is the intended semantics | PARSE-FIX-04 | If `>=` was intended — D-815 says "> 0.5", matches recommendation |
| A6 | `runs.stats` JSON column supports adding 3 new keys without migration | PARSE-FIX-04 | Schema is JSON, additive — no migration needed; SQLite `json_patch` handles |

**Mitigation:** All 6 assumptions are resolved at W0 spike (A1/A2/A3/A4) or at first integration test (A5/A6). None block Plan 08-01 W0 from starting.

## Open Questions (RESOLVED)

1. **`_strip_brand_prefix` fallback ship in Plan 08-03?**
   - What we know: existing Givenchy fixture has clean `<meta itemprop="name">` for both brand AND product.
   - What's unclear: do STEREOTYPE/Armani PDPs also have product-level microdata, or do they fall back to `<h1>` text?
   - **RESOLVED:** Decision deferred to Plan 08-03 execution-time, gated on W0 shape-table evidence. If `shape-table.md` shows microdata coverage ≥95% across the 30 PDPs → omit fallback (microdata-primary path only). If coverage <95% → add `_strip_brand_prefix(name, brand)` helper that strips `^{brand}` case-insensitively, with a unit test for STEREOTYPE/Armani. Plan 08-03 Task 2 enforces this branch logic explicitly (read MEMO.md → branch).

2. **viled descriptive-attributes iteration cover all `pp.attributes[*]`, not just `[0]`?**
   - What we know: existing v1.0 code only reads `pp.attributes[0]` (single price variant per D-217 Pitfall 2 "beauty SKUs typically have ≤1 size variant").
   - What's unclear: multi-variant SKUs may put `Размер` in `[1]` or higher.
   - **RESOLVED:** Single-variant `[0]` only for v1.1 (mirrors existing v1.0 contract — Phase 4 matcher `volume_norm IS NOT NULL` filter already excludes nulls from join, so missing multi-variant volumes degrade gracefully). Multi-variant `[*]` deferred to v1.2 if Phase 9 brand-coverage canary surfaces misses. Plan 08-04 codifies single-variant path.

3. **`parser_drift_failure_reason` location in `runs.stats`?**
   - What we know: D-816 says `failure_reason` is run-level.
   - What's unclear: `goldapple.parser_drift_failure_reason` (namespaced) vs top-level `failure_reason`.
   - **RESOLVED:** Namespaced `goldapple.parser_drift_failure_reason` per D-815 (gate is goldapple-only). Atomic-merge safety preserved through `GoldappleStatsBuilder`. Top-level `runs.status='failed'` signals at run-level; the namespaced reason key identifies the specific drift mode (volume vs brand). Plan 08-05 enforces this naming.

## Environment Availability

> Phase 8 is a code+test change; no new environmental dependencies beyond the selectolax upgrade. The Camoufox W0 fetch reuses the LOCKED Phase 3 stack.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| selectolax | All parser code | ✓ (current pin `>=0.3,<0.4`) | 0.3.x | UPGRADE to `>=0.4.7,<0.5` (Plan 08-02 first step) |
| Camoufox 0.4.11 | W0 spike capture | ✓ (Phase 3 LOCKED) | 0.4.11 | None — LOCKED per D-313 |
| pytest 8.x | All tests | ✓ | 8.x | n/a |
| pytest-asyncio ≥0.24 | Live-marker async tests (deferred Phase 9; not needed in Phase 8) | ✓ | ≥0.24 | n/a |
| SQLite (in-memory) | PARSE-FIX-04 integration test | ✓ (stdlib) | bundled | n/a |
| Network access to goldapple.kz | W0 spike (30 PDPs) | depends on operator location | n/a | Operator runs from Camoufox-tested geography per spike-01-goldapple/SKILL.md |

**No missing dependencies.** Upgrade `selectolax` is the only mutation; it lands as part of Plan 08-02 W1.

## Metadata

**Confidence breakdown:**
- Standard stack (selectolax 0.4 Lexbor): HIGH — verified Context7 + PyPI version, Modest deprecation confirmed
- viled JSON path: HIGH — empirical trace against 3 in-repo fixtures
- Goldapple PDP shape (STEREOTYPE/Armani specifics): MEDIUM — inferred from BUG-FINDINGS.md description + ARCHITECTURE.md §A; W0 spike MUST validate before Plan 08-02/03 commit
- PARSE-FIX-04 gate insertion: HIGH — pattern direct-copied from existing D-203 helpers
- Synthetic regression test pattern: HIGH — mirrors `synthetic_report_run` fixture shape
- W0 spike script: MEDIUM — ad-hoc reuse of `GoldappleFetcher`; precise URL curation deferred to operator

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (30 days — stable selectolax + viled NEXT_DATA shape; revisit if selectolax 0.5 or new viled UI rolls in this window)

---

## RESEARCH COMPLETE

- selectolax 0.4 Lexbor backend `:lexbor-contains("ОБЪЁМ" i)` is the verified primitive for goldapple volume extraction; case-insensitive flag MUST include the leading space; Modest backend is deprecated upstream but the v1.1 pin keeps it as default to protect 60+ existing tests.
- viled `Размер` attribute lives at **`props.pageProps.attributes[0].attributes[]`** (nested, NOT `pp.item.attributes[]` as STACK.md tentatively suggested) — empirically verified against all 3 in-repo viled fixtures; clothing-vs-beauty disambiguation is handled by the existing `parse_volume` normalizer, not by the new helper.
- PARSE-FIX-04 null-rate gate plugs into the D-203 retailer-agnostic gate-helper shape (between parse-quality and matcher), adds 3 new stats keys (`goldapple.volume_null_rate`, `goldapple.brand_null_rate`, `goldapple.parser_drift_failure_reason`), and is testable in pure isolation plus one in-memory-SQLite synthetic-regression integration test for Success Criteria #5.
- W0 sub-spike protocol concrete: ~3 min Camoufox fetch + 15 min shape-table fill, gated on `shape-table.md` + 3 `_live-2026-05-13-*.html` fixtures committed + `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` written before any Plan 08-02/03/04 RED test is allowed to land.
- ~15-test delta to suite (803 → ~818) covering parametrized fixtures across Givenchy-baseline + STEREOTYPE + Armani (goldapple) and clothing + beauty + multipack + Contre-Jour (viled), plus 6 gate boundary cases and 1 synthetic-regression integration test — all under 30s per-task quick run, full suite under 90s.
