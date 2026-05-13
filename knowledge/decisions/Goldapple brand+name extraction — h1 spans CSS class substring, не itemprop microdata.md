---
tags: [decision, phase-8, goldapple, parser, microdata, h1-spans, w0-spike-finding]
date: 2026-05-14
decision-id: SPIKE-08-01
status: active
supersedes: Plan 08-03 PLAN.md tentative microdata-walk strategy
---

# Goldapple brand+name extraction — h1 spans CSS class substring, не itemprop microdata

Для PARSE-FIX-02 (Plan 08-03) реальная extraction strategy goldapple PDP brand+name — substring-match CSS classes `_ga-pdp-title__brand_*` и `_ga-pdp-title__name_*` внутри `<h1 class*="_ga-pdp-title__heading_">`. Plan 08-03 PLAN.md предполагал чтение через `<meta itemprop="name">` walk внутри `[itemprop="brand"]` Product itemscope — но **этих metatags на goldapple PDP нет** (0/30 sampled PDPs in W0 spike). v1.0 production parser `tree.css_first('[itemprop="brand"]')` matched FIRST related-product card в нижней части страницы (carousel "you may also like"), а не main product — coincidental cross-product contamination объясняет run #13 bugs "STEREOTYPEsago" / "Armaniarmani code".

Это **load-bearing pivot** — без коррекции Plan 08-03 ушёл бы в production с broken selector, и Bug #2 не был бы исправлен. W0 spike поймал ошибку через 30-PDP shape-sampling по CONTEXT.md D-804 protocol — это buck-stops-here precedent для overfitting prevention.

## Empirical evidence (W0 spike, 30 PDPs, 2026-05-14)

| Selector | Match rate | Notes |
|---|---|---|
| `<h1 class*="_ga-pdp-title__heading_">` | **30/30 (100%)** | universal product title container |
| `[class*="_ga-pdp-title__brand_"]` | **30/30 (100%)** | brand span inside h1; read `[content]` attr OR text |
| `[class*="_ga-pdp-title__name_"]` | **30/30 (100%)** | name span inside h1; read text |
| `<meta itemprop="name">` at product level | **0/30 (0%)** | ❌ does NOT exist on goldapple PDPs; the 2 `itemprop="name"` per page are breadcrumb + review-author + Organization metadata |
| `<span itemprop="brand">` at product level | **0/30 (0%)** | only inside related-product carousel cards |

## Why CSS hash suffix substring-match (не full string)

CSS class names are hashed by goldapple's build (e.g. `_ga-pdp-title__brand_1yrfv_339`). Hash suffix `_1yrfv_339` is build-specific and rotates on every deploy. The semantic prefix `_ga-pdp-title__brand_` is stable. Match by `class*=` (substring), not `class=` (full string).

## Implementation sketch для Plan 08-03

```python
from selectolax.parser import HTMLParser

H1_HEADING = 'h1[class*="_ga-pdp-title__heading_"]'
BRAND_SPAN = '[class*="_ga-pdp-title__brand_"]'
NAME_SPAN  = '[class*="_ga-pdp-title__name_"]'

def parse_pdp_brand_name(tree: HTMLParser) -> tuple[str, str]:
    h1 = tree.css_first(H1_HEADING)
    if h1 is None:
        return "", ""
    brand_node = h1.css_first(BRAND_SPAN)
    name_node  = h1.css_first(NAME_SPAN)
    brand = ""
    if brand_node is not None:
        brand = (brand_node.attributes.get("content") or "").strip()
        if not brand:
            brand = brand_node.text(strip=True)
    name = name_node.text(strip=True) if name_node is not None else ""
    return brand, name
```

## Why this naturally fixes Bug #1 + Bug #2

Bug #1 "STEREOTYPEsago" и Bug #2 "Armaniarmani code" были вызваны v1.0 parser'ом, который делал naive `h1.text(deep=True)` deep-concat ИЛИ матчился на bottom-of-page related-product cards. Реальный h1 — это `<h1>` с TWO separate child spans (`.brand` + `.name`) — extracting каждый ИНДИВИДУАЛЬНО гарантирует:
- No string concatenation (spans are physically separate DOM nodes)
- No cross-product contamination (we always read from THE main product's h1, not from a card carousel)

## `_strip_brand_prefix` fallback — NOT NEEDED

W0 evidence: 28/30 PDPs (93%) имеют clean `.brand` / `.name` separation. 2 exceptions:
- `Armani` + `armani code` — name starts with brand text (upstream redundancy)
- `Givenchy` + `GIVENCHY GENTLEMAN RESERVE PRIVEE` — name starts with brand UPPERCASE (upstream redundancy)

Это **upstream data quality issues** на стороне goldapple, не parser bugs. Stripping brand prefix from name изменил бы user-facing product name (потеряли бы информацию). Plan 08-03 should NOT implement `_strip_brand_prefix`.

## D-816 invariant canary — soften к log-only

`assert brand.lower() not in name.lower()` — fail-hard версия канарейки заблокировала бы run на 2/30 (7%) legitimate cases. Convert to structured log warning:

```python
if brand.lower() and brand.lower() in name.lower():
    log.warning(
        "brand_substring_in_name",
        brand=brand,
        name=name,
        url=url,
        note="upstream goldapple data redundancy, not parser bug",
    )
```

Per-SKU log entries surface regression patterns без блокирования gate'а. Cascade catches: gate (`parser_drift_null_*_rate`) ловит "all SKUs broken" mode, log warning ловит per-SKU outliers.

## Rejected alternatives

- **`<meta itemprop="name">` walk inside Product itemscope** (Plan 08-03 original) — 0/30 PDPs, silent-fail
- **`<h1>.text(deep=True)` concat** (v1.0 production) — produces "STEREOTYPEsago" / "Armaniarmani code" bugs
- **`<title>` tag parsing** — concat-noise ("Armani духи armani code  75 мл — купить в Алматы..."); useful fallback only
- **`<a href="/brands/<slug>">` slug extraction** — possible secondary brand identifier, but slug ≠ canonical display brand (e.g. "tom-ford" vs "Tom Ford"); h1 spans cleaner

## Connected

- [[viled volume — в attributes Размер JSON-поле, не в name]] (parallel decision для PARSE-FIX-03)
- [[viled Размер JSON path — nested attributes 0 attributes, не item attributes]] (parallel decision для viled JSON path)
- [[Goldapple PDP renders volume в structured flexbox blok, не в microdata]] (parallel decision для PARSE-FIX-01 volume)
- [[2026-05-14 — Phase 8 W0 spike done, microdata премиса invalidated — pivot к h1-spans extraction]] (session)
- `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` — system-discoverable index
- `.planning/spikes/v1.1-brand-name-shapes/MEMO.md` — full evidence memo
- `.planning/spikes/v1.1-brand-name-shapes/shape-table.md` — 30-row per-PDP survey
- `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` — Bug #1 evidence
- `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` — Bug #2 evidence
