# Phase 8 W0 Spike — Brand-Name-Volume Shape Findings

**Completed:** 2026-05-13
**Spike start:** 2026-05-13
**Spike end:** 2026-05-13 (single-session, ~60 min wall-clock)
**Fetched:** 30 PDPs across 5 stratification buckets via Camoufox 0.4.11 from KZ-laptop (operator location) + 1 viled PDP via curl_cffi
**See also:** [[shape-table]] (per-PDP detail) — [[../../skills/spike-findings-v1.1-brand-name-shapes/SKILL|SKILL]] (downstream agent index)

## TL;DR

> **The shape-sampling spike invalidated Plan 08-03's core premise.** Goldapple PDPs do NOT carry product-level `<meta itemprop="name">` microdata at all (0/30 PDPs) — the `itemprop="name"` occurrences (2 per page) are breadcrumb labels, review-author names, and footer Organization name. The actual product brand+name lives in **`<h1>` child spans with CSS classes `_ga-pdp-title__brand_*` and `_ga-pdp-title__name_*`**, both with **100% (30/30) coverage**. This *strengthens* Phase 8 outcomes because the two spans are physically separate DOM nodes — no concatenation bug can occur when each is extracted from its own span. The "STEREOTYPEsago" / "Armaniarmani code" bugs reported in live-run #13 are explained by the v1.0 parser doing a naive `h1.text()` deep-concat. The fix is extracting brand and name from their respective spans independently; **the `<meta itemprop="name">` walk proposed in Plan 08-03 must be abandoned**.
>
> Volume block extraction (Plan 08-02) is on track — 25/30 PDPs (83%) carry the `ОБЪЁМ / МЛ` flex-box structure targetable by `selectolax 0.4 Lexbor :lexbor-contains("ОБЪЁМ" i)`. The 5 missing PDPs are non-volumed products (eye creams, gels, packs) where NULL is legitimate.
>
> Decision: `_strip_brand_prefix` fallback is NOT NEEDED — the `.name` span never contains the `.brand` span text in 28/30 cases. The 2 exceptions (`armani code`, `GIVENCHY GENTLEMAN RESERVE PRIVEE`) are upstream data quality redundancies, not parser bugs. The D-816 invariant canary `brand.lower() not in name.lower()` should log a warning rather than fail-hard, because the data legitimately fails it for ~7% of SKUs.

## Buckets (5 × 6 stratification per D-801 — adapted to real goldapple.kz/KZ inventory)

| Bucket | URLs sampled | h1 .brand extraction | h1 .name extraction | Lex-contains-match rate | Shape distribution |
|--------|--------------|----------------------|---------------------|-------------------------|---------------------|
| Lux (Creed ×6) | 6 | 6/6 | 6/6 | 4/6 (2 PDPs are eye-creams without ОБЪЁМ block) | 5× stereotype-style, 1× mixed-case |
| Mass-market (Armani ×2, Givenchy ×4) | 6 | 6/6 | 6/6 | 6/6 | 3× stereotype-style, 1× armani-style (Bug #2), 1× mixed-case, 1× armani-style |
| Niche (Stereotype ×4 incl. sago, Byredo) | 6 | 6/6 | 6/6 | 6/6 | 4× stereotype-style (Bug #1 evidence in pdp-16), 2× mixed-case |
| RU-brands (Black Pearl ×3, Natura Siberica ×2, Sibirskie Travy ×1) | 6 | 6/6 | 6/6 | 4/6 | 3× stereotype-style, 3× mixed-case |
| Multi-word (Maison Margiela ×2, Calvin Klein ×4) | 6 | 6/6 | 6/6 | 5/6 | 2× stereotype-style, 3× mixed-case, 1× givenchy-baseline |

**Substitutions from D-801 spec:** Tom Ford, Jo Malone, Atelier Cologne, Diptyque, Chanel, YSL, Versace, Profumum, Le Labo, Maison Crivelli, Nasomatto are NOT carried in goldapple.kz/KZ sitemap (verified via `probe_brands.py`). Substitutes chosen from same shape category — coverage of brand-display variance preserved (multi-word brand prefix tested via Maison Margiela + Calvin Klein; mass-market brand-name-substring tested via Armani-code).

**Cyrillic-uppercase RU brands** ("Натура Сибирика", "Чистая Линия", "Лошадиная Сила", "Невская Косметика", "Сибирские Травы") are NOT slug-prefixed in goldapple.kz/KZ — they're transliterated to Latin (`natura-siberica`) or carried under different umbrella brands (`black-pearl-eye-cream` is a 3W CLINIC SKU, not a "Black Pearl" brand SKU). The case-insensitive `:lexbor-contains` flag is therefore not stress-tested by RU brand names; the test still applies to the volume label "ОБЪЁМ" Ё/Е variants (one PDP shape uses Ё, the rest use Ё — Е variant not observed in this 30-PDP sample).

## What works

- **`<h1 class*="_ga-pdp-title__heading_">`** — 100% (30/30) presence as the main product title container.
- **Brand span CSS class `_ga-pdp-title__brand_*`** — substring-match yields brand cleanly:
  - Reading the `content="..."` attribute when present (most pages): preserves trailing whitespace exactly as authored (e.g. `"Givenchy "`)
  - Falling back to text content when `content` is absent
  - 100% (30/30) extraction success
- **Name span CSS class `_ga-pdp-title__name_*`** — 100% (30/30) extraction.
- **`<a class="...__brand_*" href="/brands/<slug>">`** — the brand link's slug is also reliable (could be used as a secondary brand identifier).
- **ОБЪЁМ + МЛ flex-box** — 25/30 PDPs (83%) have the structured volume row. The `:lexbor-contains` Lexbor selector is appropriate.
- **`<meta itemprop="sku">` inside Product itemscope** — 30/30 carries the numeric SKU id (verified in pdp-07-armani-code: `content="19000195723"`).

## What doesn't

- **`<meta itemprop="name">` at product level** — does NOT exist (0/30). Plan 08-03's microdata-walk approach is invalid. The `<span itemprop="brand">` walk in the existing v1.0 parser was matching against the bottom-of-page "you may also like" product CARDS (the carousel section that DOES carry `[itemprop="brand"]` per product card), not the main product. This is why v1.0 production parser silently took the FIRST card's brand+name — hence the cross-product contamination observed in run #13.
- **`<meta itemprop="brand">` at product level** — does NOT exist (0/30) either. The brand link `<a href="/brands/...">` inside h1 is the only product-level brand source.
- **Tom Ford / Jo Malone / Atelier Cologne / Chanel / YSL** — not in goldapple.kz/KZ catalog (matters for v1.2 if expanding bucket coverage).
- **`<title>` tag is unreliable for parsing** — it concatenates raw text (e.g. "Armani духи armani code  75 мл — купить в Алматы и Шымкенте"). Useful as last-resort fallback only.

## Decisions

### 1. Brand+name extraction strategy → `h1` child spans (PIVOT from microdata)

For Plan 08-03 (PARSE-FIX-02):

```python
H1_HEADING = 'h1[class*="_ga-pdp-title__heading_"]'
BRAND_SPAN = '[class*="_ga-pdp-title__brand_"]'  # substring CSS-class match
NAME_SPAN  = '[class*="_ga-pdp-title__name_"]'

h1 = tree.css_first(H1_HEADING)
brand_a = h1.css_first(BRAND_SPAN) if h1 else None
name_s  = h1.css_first(NAME_SPAN)  if h1 else None
brand = (brand_a.attributes.get("content") or brand_a.text(strip=True)) if brand_a else ""
name  = name_s.text(strip=True) if name_s else ""
```

The Plan 08-03 spec calls for `<meta itemprop="name">` walking under Product itemscope — that strategy is REJECTED here. The h1-spans strategy is empirically more reliable (100% vs 0%) and yields cleaner separation.

### 2. `_strip_brand_prefix` fallback — NOT NEEDED

The `.name` span text never contains the `.brand` text in 28/30 cases. The 2 exceptions are upstream redundancies; stripping would alter the user-facing product name. Decision per CONTEXT.md Claude's Discretion: **NOT NEEDED**.

### 3. Volume extraction strategy → `_extract_volume_block` via selectolax 0.4 Lexbor

Plan 08-02 strategy holds: `selectolax.lexbor.LexborHTMLParser.css('div:lexbor-contains("ОБЪЁМ" i)')` will hit the structured volume block on 25/30 PDPs. The 5 non-volumed PDPs (eye creams etc.) fall through to None, which is correct.

### 4. D-816 invariant canary — SOFTEN to log-only

`assert brand.lower() not in name.lower()` would fail-hard on legitimately redundant goldapple data (armani-code, gentlemen-reserve). Soften to a structured log warning so per-SKU regressions still get surfaced without failing the whole run.

### 5. SMOKE_URLs rotation (Plan 08-05 D-818) — slot selections finalized

| Slot | URL | Why |
|------|-----|-----|
| 1 | `https://goldapple.kz/19000440474-stereotype-sago` | STEREOTYPE-style canonical (Bug #1 source), brand "Stereotype" + name "SAĜO" with non-Latin codepoint stress |
| 2 | `https://goldapple.kz/19000195723-armani-code` | Armani-style canonical (Bug #2 source), brand substring of name |
| 3 | `https://goldapple.kz/19000488678-givenchy-irresistible` | Givenchy baseline (RETAINED from `runner/gates.py:34-35`) |

## Handoff

- See [[shape-table]] for per-PDP detail (30 rows × 6 columns)
- 3 fixtures committed:
  - `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` (Bug #1 evidence, 206 KB)
  - `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` (Bug #2 evidence, 204 KB)
  - `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` (Bug #3 evidence, 197 KB)
- 3 new session-scoped pytest fixtures in `tests/conftest.py`:
  - `goldapple_pdp_html_live_stereotype`
  - `goldapple_pdp_html_live_armani`
  - `viled_pdp_html_live_contre_jour`
- Skill wrap-up: [[../../skills/spike-findings-v1.1-brand-name-shapes/SKILL|spike-findings-v1.1-brand-name-shapes]]
- Scratch scripts (NOT a long-term CLI surface): `capture.py`, `sample_urls.py`, `curate_urls.py`, `probe_brands.py`, `inspect_shapes.py`, `fetch_contre_jour.py`. Retained in spike dir for re-run-ability; superseded by Phase 9 `capture-fixtures` CLI subcommand (TEST-HARNESS-05).
- 30 captured PDPs retained as `pdp-NN-<slug>.html` for future regression auditing (Plan 08-03 Wave 2 RED tests will load these for assertions; Phase 9 syrupy harness will fold them into the canonical fixture set).
