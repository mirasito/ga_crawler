# Phase 8 W0 Shape-Sampling Survey — 30 goldapple PDPs

**Captured:** 2026-05-13 via `capture.py` (Camoufox 0.4.11, 30/30 HTTP 200, ~3 min)
**Extraction:** `_ga-pdp-title__brand_*` + `_ga-pdp-title__name_*` CSS-class spans inside `<h1>`
**See also:** [[MEMO]] (decisions + h1-spans pivot) — [[../../skills/spike-findings-v1.1-brand-name-shapes/SKILL|SKILL]] (downstream agent index)

## Per-PDP categorization (30 rows)

| # | File | Brand (h1 .brand) | Name (h1 .name) | Volume word? | Volume `/МЛ`? | Shape bucket |
|---|------|-------------------|-----------------|--------------|---------------|---------------|
| 01 | pdp-01-lux-creed-royal-water.html | Creed | Royal Water | Y | Y | mixed-case |
| 02 | pdp-02-lux-creed-carmina.html | Creed | CARMINA | N | N | stereotype-style |
| 03 | pdp-03-lux-creed-queen-of-silk.html | Creed | QUEEN OF SILK | Y | Y | stereotype-style |
| 04 | pdp-04-lux-creed-aventus-for-her.html | Creed | AVENTUS FOR HER | Y | Y | stereotype-style |
| 05 | pdp-05-lux-creed-aventus.html | Creed | AVENTUS | Y | Y | stereotype-style |
| 06 | pdp-06-lux-creed-millesime-imperial.html | Creed | MILLESIME IMPERIAL | N | N | stereotype-style |
| 07 | pdp-07-mass-armani-code.html | Armani | armani code | Y | Y | **armani-style** (Bug #2 source) |
| 08 | pdp-08-mass-armani-prive-orangerie-venise.html | Armani | Prive ORANGERIE VENISE | Y | Y | mixed-case |
| 09 | pdp-09-mass-givenchy-pour-homme-blue-label.html | Givenchy | POUR HOMME BLUE LABEL | Y | Y | stereotype-style |
| 10 | pdp-10-mass-givenchy-gentleman-reserve-privee-eau-de-parfum.html | Givenchy | GIVENCHY GENTLEMAN RESERVE PRIVEE | Y | Y | armani-style |
| 11 | pdp-11-mass-givenchy-pour-homme.html | Givenchy | POUR HOMME | Y | Y | stereotype-style |
| 12 | pdp-12-mass-givenchy-irresistible-nectar.html | Givenchy | Irresistible Nectar | Y | Y | mixed-case |
| 13 | pdp-13-niche-stereotype-flow.html | Stereotype | FLOW | Y | Y | stereotype-style |
| 14 | pdp-14-niche-stereotype-brace.html | Stereotype | BRACE | Y | Y | stereotype-style |
| 15 | pdp-15-niche-stereotype-unframe.html | Stereotype | UNFRAME | Y | Y | stereotype-style |
| 16 | pdp-16-niche-stereotype-sago.html | Stereotype | SAĜO | Y | Y | **stereotype-style** (Bug #1 source) |
| 17 | pdp-17-niche-sago.html | Stereotype | Sago | Y | Y | mixed-case |
| 18 | pdp-18-niche-byredo-alto-astral.html | Byredo | Alto Astral | Y | Y | mixed-case |
| 19 | pdp-19-ru-black-pearl.html | SAVON DE ROYAL | BLACK PEARL | Y | Y | stereotype-style |
| 20 | pdp-20-ru-black-pearl-eye-cream.html | 3W CLINIC | Black Pearl Eye Cream | Y | Y | stereotype-style |
| 21 | pdp-21-ru-black-pearl-gold-hydrogel-eye-patch.html | PETITFEE | Black Pearl & Gold Hydrogel Eye Patch | N | N | stereotype-style |
| 22 | pdp-22-ru-natura-siberica-total-renewal.html | Natura Siberica | Lab biome Total renewal | Y | Y | mixed-case |
| 23 | pdp-23-ru-natura-siberica-refresh-scalp.html | Natura Siberica | Lab biome Refresh scalp | N | N | mixed-case |
| 24 | pdp-24-ru-sibirskie-travy.html | Levrana | Сибирские травы | Y | Y | mixed-case |
| 25 | pdp-25-multi-maison-margiela-set-replica-jazz-club.html | MAISON MARGIELA | jazz club | N | N | stereotype-style |
| 26 | pdp-26-multi-maison-margiela-replica-ideal-one.html | MAISON MARGIELA | Replica Ideal One | Y | Y | stereotype-style |
| 27 | pdp-27-multi-calvin-klein-silky-coconut.html | Calvin Klein | Silky Coconut | Y | Y | mixed-case |
| 28 | pdp-28-multi-calvin-klein-nude-vanilla.html | Calvin Klein | Nude Vanilla | Y | Y | mixed-case |
| 29 | pdp-29-multi-calvin-klein-sheer-peach.html | Calvin Klein | Sheer Peach | Y | Y | mixed-case |
| 30 | pdp-30-multi-calvin-klein-cotton-musk.html | Calvin Klein | cotton musk | Y | Y | givenchy-baseline |

## Shape Buckets Identified

| Bucket | Count | Description | Bug source? |
|--------|-------|-------------|-------------|
| stereotype-style | 16 (53%) | brand title-case, name UPPERCASE (Creed → "AVENTUS"), OR brand UPPERCASE itself (MAISON MARGIELA) | Bug #1 (pdp-16) |
| mixed-case | 11 (37%) | brand and name both title-case or sentence-case | — |
| armani-style | 2 (7%) | brand string is substring of name ("Armani" in "armani code", "Givenchy" in "GIVENCHY GENTLEMAN...") | Bug #2 (pdp-07, pdp-10) |
| givenchy-baseline | 1 (3%) | brand title-case, name lowercase ("Calvin Klein" / "cotton musk") | — |

## Selector Validation

| Selector | Match rate | Notes |
|----------|------------|-------|
| `<h1 class*="_ga-pdp-title__heading_">` | **30/30 (100%)** | universal across all PDPs |
| `_ga-pdp-title__brand_*` (substring CSS class match) | **30/30 (100%)** | clean brand extraction via `[content]` attr OR text |
| `_ga-pdp-title__name_*` (substring CSS class match) | **30/30 (100%)** | clean name extraction via text content |
| `<meta itemprop="name">` at product level (Plan 08-03 premise) | **0/30 (0%)** | ❌ INVALIDATED — `itemprop="name"` occurrences are breadcrumb labels + review-author names + footer Organization name |
| ОБЪЁМ word literal | 25/30 (83%) | absent in 5 PDPs that have no MЛ-quantified volume (eye creams, gels, etc.) |
| `ОБЪЁМ / МЛ` flexbox structure | 25/30 (83%) | matches the volume block targeted by `:lexbor-contains("ОБЪЁМ" i)` per Plan 08-02 |

## Selected Fixture URLs for v1.1 Plans

| Fixture | Source PDP | Purpose |
|---------|------------|---------|
| `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` | pdp-16-niche-stereotype-sago.html → goldapple.kz/19000440474-stereotype-sago | Bug #1 evidence (brand=Stereotype, name=SAĜO, volume present) |
| `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` | pdp-07-mass-armani-code.html → goldapple.kz/19000195723-armani-code | Bug #2 evidence (brand=Armani, name="armani code" — substring redundancy) |
| `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` | viled-contre-jour-408872.html → viled.kz/item/408872 | Bug #3 evidence (Frederic Malle Contre-Jour beauty PDP, Размер attribute behavior) |

## SMOKE_URLs Rotation Slots (for Plan 08-05 PARSE-FIX-05)

| Slot | URL | Shape covered |
|------|-----|---------------|
| 1 — STEREOTYPE-style | `https://goldapple.kz/19000440474-stereotype-sago` | brand title-case + name UPPERCASE (incl. non-Latin SAĜO codepoint) |
| 2 — Armani-style | `https://goldapple.kz/19000195723-armani-code` | brand substring of name (Bug #2 canonical) |
| 3 — Givenchy baseline | `https://goldapple.kz/19000488678-givenchy-irresistible` (RETAINED from `runner/gates.py:34-35`) | mass-market reference, current good baseline |
