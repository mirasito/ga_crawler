# Phase 3: Goldapple Crawl - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 3-Goldapple Crawl
**Areas discussed:** URL-pool: sitemap → Camoufox pipeline, Brand-alias coverage gaps, Sanity-gate threshold M, Camoufox profile lifecycle между weekly-runs

---

## URL-pool: sitemap → Camoufox pipeline

### Q: Откуда goldapple-craweler берёт список product URL на каждый weekly run?

| Option | Description | Selected |
|--------|-------------|----------|
| Sitemap-only (Recommended) | curl_cffi sitemap-index → slug→URLs map → пересечение с viled-brand-set через alias → fetch matched URLs через Camoufox. Спайк 01-05: 1,461 slugs / 100,779 URLs, sitemap plain-deliverable. ~$0/week proxy. Не ловит within-week SKU. | ✓ |
| Brand-facet rendering | Camoufox рендерит /brand/{slug} страницы, парсит карточки. +50 facet-fetches × 50-100KB. Ловит свежие SKU. Риск gate-shielded facet. | |
| Hybrid: sitemap + facet sanity-cross-check | Sitemap = primary, на 1-й facet-странице каждого бренда cross-check. +50 facet-probes, ~2-3 мин к runs. | |

**User's choice:** Sitemap-only (Recommended)
**Notes:** Соответствует hybrid-стратегии спайка (curl_cffi sitemap + Camoufox product render).

---

### Q: Каждый weekly run полный re-crawl всех матч-брендов, или incremental delta через sitemap `<lastmod>`?

| Option | Description | Selected |
|--------|-------------|----------|
| Полный re-crawl каждый раз (Recommended) | Все ~3,450 URL фетчатся заново. Цены меняются без обновления `<lastmod>`. Чистый weekly snapshot. Бюджет 4.4ч в плане. | ✓ |
| Incremental через `<lastmod>` | Только изменённые/новые URL. Экономит ~80% fetches. Риск: пропуск price-change без lastmod-обновления. | |
| Hybrid: полный re-crawl + lastmod как observability | Фетчим всё + логируем lastmod-delta в ops. Подготавливает v2 incremental. | |

**User's choice:** Полный re-crawl каждый раз (Recommended)
**Notes:** —

---

### Q: Спайк подтвердил: stale-SKU на goldapple = 200 + <30 KB + нет microdata. Где stale-rate проявляется для ops-review?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-run в logs + structured `runs.stats.stale_count` (Recommended) | Stale-SKU пропускается (CRAWL-03 isolation), counter в `runs` row + JSON-лог + view `v_stale_rate_per_run`. Без алертов. | ✓ |
| Logs + ops-Telegram alert если stale-rate >5% | + алерт по порогу спайк-рекомендации (5% = sitemap rot signal). | |
| Logs + Telegram + файл `reports/stale-urls-YYYY-WNN.txt` | + отдельный файл с URL'ами для sitemap-pruning. | |

**User's choice:** Per-run в logs + structured `runs.stats.stale_count` (Recommended)
**Notes:** —

---

## Brand-alias coverage gaps

### Q: Где живёт viled-brand → goldapple-slug mapping?

| Option | Description | Selected |
|--------|-------------|----------|
| Явный `goldapple_slugs: [...]` в alias YAML (Recommended) | Ручное курирование slug-списков на бренд. Высшая предсказуемость. Missing → skip + NORM-06. | |
| Slug-эвристика от brand_norm + aliases | Slug-fy aliases, exact-match против sitemap-slug пула. Без manual курации, но false-positive-риск. | ✓ |
| Runtime probe goldapple | 1,461 sample-fetches через Camoufox для брендов из microdata. ~1.6ч + сжигает anti-bot бюджет. | |

**User's choice:** Slug-эвристика от brand_norm + aliases
**Notes:** Предпочёл lower manual curation ценой false-positive-риска; компенсируется D-305 exact-match guard.

---

### Q: Goldapple-slug'и бывают Latin (`tom-ford`), Cyrillic (`эсте-лаудер`), или микс. Как slug-эвристика работает с этим?

| Option | Description | Selected |
|--------|-------------|----------|
| Bilingual slug-fy + exact match (Recommended) | Из каждой alias-строки оба варианта: ASCII-transliterated + Cyrillic-preserved. Exact match — no substring/prefix. NFKD + accent strip + lowercase + non-alphanum→hyphen. | ✓ |
| Latin-only slug-fy | Cyrillic→Latin transliterate. Cyrillic-only goldapple-slug'и недостижимы — разваливает эвристику обратно в ручной курат. | |
| Bilingual slug-fy + rapidfuzz top-K | + fuzzy fallback при exact-miss (top-3 >85). Вводит fuzzy-логику, которую PROJECT.md отложил в v2. | |

**User's choice:** Bilingual slug-fy + exact match (Recommended)
**Notes:** —

---

### Q: viled бренд с нулём slug-матчей в goldapple sitemap (выпал из покрытия). Что делает Phase 3?

| Option | Description | Selected |
|--------|-------------|----------|
| Skip + log в NORM-06 weekly review-очередь (Recommended) | Бренд пропущен. Лог + counter `runs.stats.unmatched_viled_brands`. Оператор еженедельно ревьюит. | ✓ |
| Skip + ops-Telegram alert на каждый пропущенный бренд | + per-brand алерт. Шумно при alias-bootstrap. | |
| Pre-flight coverage gate: <60% viled-брендов = abort run | Pre-flight invariant. Сильный, но первые недели может ложно abort'ить. | |

**User's choice:** Skip + log в NORM-06 weekly review-очередь (Recommended)
**Notes:** —

---

### Q: REQ NORM-06: «бренды на goldapple, не найденные в alias-таблице». Как Phase 3 это ведёт (1,400+ unmatched slugs, большинство не интересны)?

| Option | Description | Selected |
|--------|-------------|----------|
| Лог только NEW goldapple-slug'ов (week-over-week diff) (Recommended) | Каждый run сохраняет sitemap-slug snapshot. Diff с прошлой неделей → новые в NORM-06. Низкий шум, высокая signal. | ✓ |
| Лог ВСЕХ unmatched goldapple-slug'ов каждую неделю | 1,400+ slug'ов в файл. Operator проигнорирует. NORM-06 буква, низкая utility. | |
| Не логируем goldapple-side вообще | Phase 3 видит только match-сторону. NORM-06 reinterpreted как viled-only. Нарушает букву NORM-06. | |

**User's choice:** Лог только NEW goldapple-slug'ов (week-over-week diff) (Recommended)
**Notes:** —

---

## Sanity-gate threshold M

### Q: Как вычисляется sanity-gate порог M для goldapple_count?

| Option | Description | Selected |
|--------|-------------|----------|
| Static absolute в config (M=1000) (Recommended) | Просто, предсказуемо. ~30% спайк-оценки 3,450. Ловит катастрофу, не ловит мягкую регрессию. Тюн после 4 недель. | ✓ |
| Static relative-to-viled («30% от viled-brand-filtered count») | M = 0.3 × sum(viled_skus_in_matched_brands). Связывает двух ритейлеров (риск ложных проходов при viled-shrink). | |
| Dynamic median-of-trailing-4-weeks + bootstrap floor | M = max(0.7 × trailing-4-week median, 500). Ловит -30% регрессию. Требует history. | |

**User's choice:** Static absolute в config (M=1000) (Recommended)
**Notes:** —

---

### Q: Mid-run при gate-shell-spike (anti-bot регрессия Camoufox или GroupIB ружьё), Phase 3 фетчает до конца или абортит?

| Option | Description | Selected |
|--------|-------------|----------|
| Run-to-completion + final M-gate (Recommended) | Все ~3,450 URLs (CRAWL-03 isolation), final goldapple_count > 1000. Предсказуемый wall-clock. | ✓ |
| Circuit-breaker: rolling gate-shell-rate > 20%/50-url окно → abort | Соответствует D-15 fragility-line. Экономит ~3-4ч беспоsлезных fetches. Sliding-window state. | |
| 5 consecutive gate-shells → abort (D-03 spike-style) | Mirror spike's stop-rule. Простой счётчик. Ложные abort'ы при 5 подряд stale-SKU. | |

**User's choice:** Run-to-completion + final M-gate (Recommended)
**Notes:** —

---

### Q: M=1000 это первая прикидка без history. Как M эволюционирует после 4-8 недель реальных runs?

| Option | Description | Selected |
|--------|-------------|----------|
| Оператор вручную переписывает M в config (Recommended) | Manual workflow. Operator → PR в config. Никакой авто-магии. | |
| Auto-suggest после 4 недель (рекомендация в ops-чат) | На 5-й неделе ops-алерт `new M-rec: 0.7 × 4-week median`. Operator решает принять. Полезно без silent drift. | ✓ |
| Auto-tune M автоматически | Система обновляет M по формуле. Опасно — silent drift вниз при постепенной anti-bot регрессии. | |

**User's choice:** Auto-suggest после 4 недель (рекомендация в ops-чат)
**Notes:** —

---

## Camoufox profile lifecycle между weekly-runs

### Q: Camoufox profile dir между воскресными cron-запусками?

| Option | Description | Selected |
|--------|-------------|----------|
| Fresh profile dir каждый run (Recommended) | tmp profile, бутимся, после run сносится. Спайк 01-08 = 99/100 на ХОЛОДНОМ. +30с boot. Нет drift / cookie expiry. | ✓ |
| Persist profile dir между runs | `~/.cache/ga_crawler/camoufox-profile/`. Сохраняет cookies (gib-token). Риски: cookie expiry, fingerprint drift, profile bloat. Не валидирована спайком. | |
| Adaptive: persist + wipe on detect | Persist + smoke check + wipe при gate-shell в smoke. Лучшее из двух, больше логики. Никто не валидировал warm-savings. | |

**User's choice:** Fresh profile dir каждый run (Recommended)
**Notes:** —

---

### Q: Спайк-skill рекомендует weekly Camoufox-smoke. Где это живёт в Phase 3?

| Option | Description | Selected |
|--------|-------------|----------|
| Интегрирован в weekly run, ПЕРЕД crawl-фазой (Recommended) | 1-3 known-good URLs, проверка microdata. Pass → crawl. Fail → abort + ops-Telegram. Экономит 4ч fetches при сломанном fingerprint. | ✓ |
| Separate cron earlier in week (например Wed) → ops alert if shell-rate spikes | Wed cron 3-fetch smoke. Раннее предупреждение. Не блокирует weekly run. Больше cron-записей. | |
| Нет интегрированного smoke; per-SKU isolation разберётся | Сразу первый product URL. CRAWL-03 isolation + final M-gate всё равно поймает. Тратит 4ч на ничто. | |

**User's choice:** Интегрирован в weekly run, ПЕРЕД crawl-фазой (Recommended)
**Notes:** —

---

### Q: Camoufox version policy. Спайк-validated = v135.0.1-beta.24 (daijro upstream; coryking fork как backup).

| Option | Description | Selected |
|--------|-------------|----------|
| Pin точную версию (Recommended) | `camoufox==135.0.1.beta24` в uv.lock. Manual upgrade workflow: dev smoke → PR в lock-файл. Спайк-валидация остаётся правдивой. | ✓ |
| Pin major+minor (^135.0) | Auto-patch updates. Patch меняет fingerprint hash → gate может свалиться без предупреждения. | |
| Latest stable + integration smoke gate | Без pin, smoke-probe = gate. Фейл случится в воскресенье ночью. | |

**User's choice:** Pin точную версию (Recommended)
**Notes:** —

---

## Claude's Discretion

- Конкретное место config-файла для `M`, `smoke_urls`, rate-limit constants — `pyproject.toml` vs dedicated `config/sanity.toml` vs `.env`. Default predict: `pyproject.toml [tool.ga_crawler.crawl.goldapple]`.
- Имя tmp-каталога для Camoufox profile (`/tmp/camoufox-{run_id}/` vs `<repo>/tmp/...`).
- Структура `runs.stats` JSON-блока — точные ключи (`stale_count`, `unmatched_viled_brands`, `unmatched_goldapple_slugs_new`, `gate_shell_count`, `smoke_pass`).
- Smoke probe URL pool curation workflow — как оператор обновляет `smoke_urls` если стэйлятся (deferred Phase 7 ops-playbook).
- Camoufox profile dir cleanup strategy on FAIL — preserve last failure dir для forensics vs always delete. Default: always delete (disk-cost > debug-utility для v1).

## Deferred Ideas

- Pre-flight coverage gate (<60% viled-брендов с goldapple-match → abort run) — отвергнуто на v1 (D-306); пересмотр после 8 недель history
- Mid-run circuit-breaker по rolling gate-shell-rate — отвергнуто на v1 (D-309); пересмотр если post-launch появятся реальные anti-bot regressions
- Auto-tune sanity-gate threshold M — навсегда отвергнуто (D-310 contra)
- Persistent profile dir между weekly runs (warm cookies) — отвергнуто на v1 (D-311); пересмотр если smoke + fresh-profile стабильно работает 12+ недель
- Adaptive profile lifecycle (persist + wipe on detect) — отвергнуто на v1 (D-311) как переосложнение
- Brand-facet rendering как primary URL-pool — отвергнуто (D-301)
- Hybrid sitemap + facet sanity-cross-check каждую неделю — отвергнуто (D-301)
- Incremental delta через sitemap `<lastmod>` — отвергнуто на v1 (D-302); возможный пересмотр в v2
- Rapidfuzz fuzzy slug-matching — отвергнуто (D-305 contra), v2 territory (REQ MATCH-V2-01)
- Explicit `goldapple_slugs:` field в alias YAML — рассмотрено и отвергнуто (D-304); пересмотр если эвристика покажет высокий false-positive-rate
- Ops-Telegram alert per missing brand — отвергнуто (D-306)
- Файл `reports/stale-urls-YYYY-WNN.txt` — отвергнуто (D-303)
- Separate midweek cron для smoke probe — отвергнуто (D-312)
- Latest stable Camoufox без pin — отвергнуто (D-313 contra)
