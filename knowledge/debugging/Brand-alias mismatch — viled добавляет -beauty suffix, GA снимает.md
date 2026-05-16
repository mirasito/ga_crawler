---
tags: [debugging, brand-alias, normalization, matcher]
date: 2026-05-16
---

# Brand-alias mismatch — viled добавляет `-beauty` suffix, GA снимает

## Симптом

run-19 v2 (после добавления 8 новых slug overrides) показал unexpectedly: brand_overlap_count остался 40 несмотря на то что GA-side получил 51 brand_norm. match.count даже **упал** с 3 831 (v1.5) до 3 409.

Per-brand inspection раскрыл что 8 «новых» брендов на GA-стороне имеют brand_norm БЕЗ суффикса (`gucci`, `carolina-herrera`, `kenzo`...), а viled — с суффиксом (`gucci-beauty`, `carolina-herrera-beauty`, `kenzo-beauty`...). Matcher SQL JOIN на `v.brand_norm = g.brand_norm` фейлится.

## Root cause

Slug-override в `data/ga_brand_slugs.yaml` решает **routing** — куда направить enumeration:

```yaml
gucci-beauty: gucci   # viled brand_norm → GA /brands/{slug}
```

Но это НЕ решает **post-enumeration normalization** — какой `brand_norm` записать в `snapshots.brand_norm`. Нормализатор смотрит на raw `brand` поле каждой стороны:
- viled returns `brand="Gucci Beauty"` → default normalize = `gucci-beauty`
- GA returns `brand="Gucci"` → default normalize = `gucci`

Без alias-entry в `config/brand-aliases.yaml` оба нормализатор-выхода различаются и matcher JOIN ничего не находит.

## Fix

`config/brand-aliases.yaml` уже имел паттерн через `armani_beauty`:

```yaml
armani_beauty:
  - "Armani Beauty"
  - "Giorgio Armani"
  - "Armani"
```

Canonical = viled-side form (с суффиксом). Aliases = все варианты GA-side spelling.

Добавили 8 таких блоков для проблемных брендов:

```yaml
carolina-herrera-beauty: [Carolina Herrera, Carolina Herrera Beauty, …]
gucci-beauty:            [Gucci, Gucci Beauty, …]
hugo-boss-beauty:        [Hugo Boss, Hugo Boss Beauty, …]
valentino-beauty:        [Valentino, Valentino Garavani, Valentino Beauty, …]
kenzo-beauty:            [Kenzo, Kenzo Beauty, …]
lanvin-beauty:           [Lanvin, Lanvin Beauty, …]
courreges-perfume:       [Courreges, COURREGES, Courreges Perfume, …]
dr-vranjes:              [Dr. Vranjes, Dr. Vranjes Firenze, …]   # GA добавляет "Firenze"
```

После next enum обе стороны нормализуются к canonical `carolina-herrera-beauty` (и т.д.) → SQL JOIN работает.

## Для уже-собранных snapshots — SQL UPDATE

Aliases читаются на **start** прогона (D-207) и применяются на write-time. Чтобы не ждать следующего enum, можно SQL UPDATE existing snapshots:

```sql
BEGIN;
UPDATE snapshots SET brand_norm='carolina-herrera-beauty'
  WHERE run_id=19 AND retailer='goldapple' AND brand_norm='carolina-herrera';
UPDATE snapshots SET brand_norm='gucci-beauty'
  WHERE run_id=19 AND retailer='goldapple' AND brand_norm='gucci';
-- ... etc
COMMIT;
```

После такого UPDATE + `matcher-run --run-id 19` — brand_overlap прыгает 40 → 48, matches +123.

## Как поймать раньше

- **При добавлении brand-slug override**: добавлять одновременно canonical brand-alias entry. Это два связанных артефакта; разрыв между ними — bug.
- **`gsd-add-test`-style canary** который для каждого override в `ga_brand_slugs.yaml` проверяет существование соответствующего alias-entry в `brand-aliases.yaml`. Mismatch → FAIL.
- **Норм06-review должен флагать brand_norm-overlap явно**: «48 viled brands resolved, 40 в SQL-overlap → 8 mismatch».

## Связано

- [[GA brands index — single XHR на front-api-brands возвращает все 1389 брендов]]
- [[Cards-list per-session burst limit — 3-4 страницы потом 403]]
