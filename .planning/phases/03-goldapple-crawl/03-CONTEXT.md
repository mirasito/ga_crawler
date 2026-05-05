# Phase 3: Goldapple Crawl - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 пишет goldapple snapshots в ту же таблицу `snapshots`, что и Phase 2 viled — на той же планке качества (per-SKU isolation, retry/backoff с jitter, sanity-gate, parse-quality invariants). Бренд-пул goldapple фильтруется по тому, что есть в текущем viled-снимке (CRAWL-02). Phase 3 переиспользует Phase 2 модули парсера/нормализатора (per-retailer dispatch: microdata для goldapple, `__NEXT_DATA__` для viled). Anti-bot стек **залочен** Phase 1 спайком: Camoufox v135.0.1-beta.24 (Firefox + C++ fingerprint spoof), KZ-laptop direct, без proxy, 99/100 на 100-fetch run. Phase 3 не строит схему БД, не пишет matcher, не делает отчёт — это последующие фазы.

</domain>

<decisions>
## Implementation Decisions

### URL-pool: sitemap → Camoufox pipeline

- **D-301:** **Sitemap-only** URL-pool. curl_cffi (Tier 0) фетчит goldapple sitemap-index → парсит 3 sub-sitemap → строит `slug → [URLs]` map → пересекает с матч-брендами через slug-эвристику → передаёт matched URLs в Camoufox-fetch-loop. Не используем brand-facet rendering (избыточные fetches, риск gate-shielded facet) и не делаем sanity-cross-check каждую неделю. Спайк 01-05 эмпирически: 1,461 brand slugs / 100,779 product URLs / sitemap plain-deliverable / ~$0/week proxy. Свежие SKU попадают в snapshot со следующей неделей (≤7 дней лаг).
- **D-302:** **Полный re-crawl** каждую неделю. Не используем sitemap `<lastmod>` для incremental — цены меняются БЕЗ обновления URL-`<lastmod>` (sitemap отслеживает URL-события, не price-content), incremental-режим оставит stale prices в weekly snapshot. Бюджет уже посчитан спайком: ~3,450 fetches × 3-5с = ~4.4ч sequential.
- **D-303:** **Stale-SKU surfacing minimally**: при detection «200 + <30KB + нет microdata» (spike 01-08 pattern для де-листов) Phase 3 пропускает SKU (CRAWL-03 per-SKU isolation), пишет counter в `runs.stats.stale_count` и в structured JSON-лог. Отдельный SQL-view `v_stale_rate_per_run` для ручного слежения. **Нет** ops-Telegram алерта и **нет** отдельного `reports/stale-urls-*.txt` файла. Не создаём шум — оператор смотрит при необходимости.

### Brand-alias coverage

- **D-304:** **Slug-эвристика** от `brand_norm + aliases` (НЕ explicit `goldapple_slugs:` в YAML, НЕ runtime probe). Phase 3 берёт каждую alias-строку viled-бренда (например `Estée Lauder`, `Эсте Лаудер`), slug-fy-ит её, проверяет exact-match против sitemap-slug пула. Совместимо с тем, что Phase 2 alias-YAML сидится viled-side вариантами; goldapple-side вариантов в YAML на старте может НЕ быть. **Trade-off принят явно:** ниже manual curation, но возможны false-positives и пропуски Cyrillic-only goldapple-slug, на которые ни одна viled-alias не slug-fy-ится.
- **D-305:** **Bilingual slug-fy + exact match**. Slug-fier из каждой alias-строки производит ДВА варианта slug: ASCII (после NFKD + accent strip + transliterate Cyrillic→Latin) И Cyrillic-preserved. Алгоритм: lowercase → non-alphanum → `-` → collapse multi-`-`. Match только exact (не substring, не prefix, не fuzzy) — исключает «Tom Ford» → «tom-ford-beauty» false-positive. Rapidfuzz/fuzzy откладывается в v2 (REQ MATCH-V2-01).
- **D-306:** **Skip + log в NORM-06** для viled-брендов с нулём slug-матчей. Бренд просто пропущен из weekly run, имя пишется в NORM-06 review-очередь (по REQUIREMENTS NORM-06) + counter `runs.stats.unmatched_viled_brands`. **Нет** ops-Telegram per-brand алертов (шумно), **нет** pre-flight coverage-gate (риск ложных abort'ов первые недели). Оператор ревьюит NORM-06 еженедельно, добавляет alias в YAML или признаёт «goldapple не несёт бренд».
- **D-307:** **Week-over-week NEW goldapple-slug diff** для NORM-06 reverse-direction (REQUIREMENTS NORM-06: «бренды на goldapple, не найденные в alias-таблице»). Каждый run сохраняет sitemap-slug snapshot на диск; в начале next run diff-им с предыдущим, **новые** slug'и (обычно единицы/десятки) идут в NORM-06 review-очередь. Не дамп всех 1,400+ unmatched каждую неделю (избыточно: большинство — российские бренды viled никогда не возьмёт).

### Sanity-gate threshold M

- **D-308:** **`M = 1000` static absolute** в config (`config/sanity.toml` или `[tool.ga_crawler.sanity]` в pyproject.toml — конкретное место выберет планер). ~30% от спайк-оценки 3,450/week = catastrophic-failure detector. Не lowing complexity dynamic-формулами на v1.
- **D-309:** **Run-to-completion + final M-gate** (нет mid-run circuit-breaker). Phase 3 фетчит все ~3,450 URLs (CRAWL-03 per-SKU isolation абсорбирует индивидуальные failures), в конце проверяет `goldapple_count > 1000`. Если нет → `runs.status='failed'`, отчёт НЕ уходит в business-чат (DELIVER-03 / spec-lock #3), ops-чат получает алерт. **Не** имплементим sliding-window gate-shell-rate-detector и **не** D-03-style «5 consecutive shells abort» — в healthy state (gate-shell rate ~0% per spike) circuit-breaker не нужен; в broken state final-gate всё равно срабатывает.
- **D-310:** **Auto-suggest M в ops-чат после 4 недель**. На 5-й неделе и далее run отправляет ops-Telegram сообщение `new M-rec: 0.7 × 4-week-median goldapple_count = X` после каждого успешного run. Оператор сам решает поднимать M или нет (PR в config). НЕ auto-tune (предотвращает silent drift вниз при постепенной anti-bot регрессии).

### Camoufox profile lifecycle

- **D-311:** **Fresh profile dir каждый weekly run**. Cron создаёт tmp profile-dir (е.g. `/tmp/camoufox-{run_id}/`), Camoufox бутится на нём с конфигом `geoip=True, locale=['ru-RU','kk-KZ','en-US'], humanize=True, persistent_context=True` (per-run persistent для cookies WITHIN run, но profile dir сносится после run). Обоснование: спайк 01-08 валидировал 99/100 на ХОЛОДНОМ старте — warm-cookies между weeks недоказаны и риск fingerprint drift / cookie expiry / profile bloat. +30с boot warmup на каждый run приемлем.
- **D-312:** **Smoke probe ПЕРЕД crawl-фазой, integrated в weekly run**. После Camoufox-boot на fresh profile, до full crawl, Phase 3 пробует 1-3 known-good URLs (хардкодятся в config; обновляются operator'ом если стейл). Pass-критерий: все probe-URLs возвращают 200 + microdata-price extracted. Fail → `runs.status='failed'`, ops-Telegram с диагностикой (Camoufox version, response-bytes, gate-shell title), 4ч беспоsлезных fetches не тратятся. Spike-skill «weekly Camoufox-vs-goldapple smoke» удовлетворяется этим integrated-механизмом — отдельный midweek cron не нужен.
- **D-313:** **Pin exact Camoufox version** = `camoufox==135.0.1.beta24` (или эквивалентная PyPI-версия) в `uv.lock`. coryking/camoufox fork как backup в случае upstream stalls (spike-skill maintenance note). Manual upgrade workflow: оператор в dev gо запускает goldapple-smoke на новой версии → если pass → PR в lock-файл. Защищает: spike-validation остаётся правдивой (fingerprint hash меняется на каждом patch — Camoufox-spoof on C++ level).

### Claude's Discretion

- **Конкретное место config-файла** для `M`, `smoke_urls`, rate-limit constants — `pyproject.toml [tool.ga_crawler]` vs dedicated `config/sanity.toml` vs `.env` — оставлено планеру. Default predict: `pyproject.toml [tool.ga_crawler.crawl.goldapple]` для consistency со стэком.
- **Имя tmp-каталога** для Camoufox profile (`/tmp/camoufox-{run_id}/` vs `<repo>/tmp/...`) — implementation детaль планера.
- **Структура `runs.stats` JSON-блока** (точные ключи `stale_count`, `unmatched_viled_brands`, `unmatched_goldapple_slugs_new`, `gate_shell_count`) — оставлено планеру; должно быть consistent с Phase 2 viled-side `runs.stats` schema.
- **Smoke probe URL pool curation workflow** — kак оператор обновляет `smoke_urls` если они стэйлятся (3-URL ротация, manual review каждые N недель) — оставлено Phase 7 ops-playbook.
- **Камоufox profile dir cleanup strategy on FAIL** — всегда удалять vs preserve last failure для forensics — оставлено планеру; default: всегда удалять (disk-cost > debug-utility для v1).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — core value, scope, constraints, key decisions
- `.planning/REQUIREMENTS.md` §Crawl (CRAWL-02), §Norm (NORM-06), §Data (DATA-03/04 immutable, WAL), §Parse (PARSE-01..PARSE-06 переиспользуются для goldapple через retailer dispatch)
- `.planning/ROADMAP.md` §"Phase 3: Goldapple Crawl" — phase goal, success criteria 1-5

### Spike findings (LOCKED — Phase 3 stack constraints)
- `.planning/spikes/01-goldapple/MEMO.md` — signed-off decision memo (2026-05-06): Tier 2 = Camoufox v135.0.1-beta.24 direct, no proxy, 99/100 success, 0% gate-shell rate, NOT FRAGILE per D-15
- `.claude/skills/spike-01-goldapple/SKILL.md` — Phase 3 entry-point reference: rate-limits, parser strategy (microdata НЕ JSON-LD), Camoufox config, ops monitoring playbook
- `.planning/spikes/01-goldapple/notebook.py` — 100-fetch reference implementation (Camoufox bootstrap, gate detection, microdata extraction)
- `.planning/spikes/01-goldapple/sample-payloads/tier2-camoufox-kz-results.json` — empirical baseline (99/100, per-URL timings, response-bytes distribution)
- `.planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html` — реальный goldapple PDP HTML для парсер-калибровки
- `.planning/spikes/01-goldapple/sample-payloads/_debug-jsonld-blocks.json` — proof goldapple emits ТОЛЬКО `OfferShippingDetails` JSON-LD (no Product schema → must use microdata)

### Phase 1 spike context
- `.planning/phases/01-goldapple-reconnaissance-spike/01-CONTEXT.md` — D-01..D-16 spike-decisions; D-04 persistent-context, D-14 microdata not JSON-LD, D-15 fragility-line 20% gate-shell

### Research foundation
- `.planning/research/SUMMARY.md` — общая стратегия (modular monolith, snapshot-table integration backbone)
- `.planning/research/STACK.md` §Anti-Bot Strategy, §Tier 2 Patchright/Camoufox — superseded by spike-MEMO в части tier choice
- `.planning/research/PITFALLS.md` — anti-bot 2026 mechanics, что НЕ работает (cloudscraper, vanilla Selenium, requests + headers)
- `.planning/research/ARCHITECTURE.md` §"Major components", §"snapshots-table integration" — модульный монолит, append-only

### Project state & shared infra
- `.planning/STATE.md` — accumulated key-decisions table (line 53-86); updated 2026-05-06 with Phase 1 closure
- CLAUDE.md (project root) §Technology Stack, §Anti-Bot Strategy — рекомендованные версии библиотек

### Out-of-tree (Obsidian vault)
- `knowledge/decisions/Goldapple — Tier 2 Camoufox без proxy, 99 из 100.md` — Obsidian-vault sign-off note (mirror MEMO.md)

### Phase 2 dependency (will be filled when Phase 2 ships)
- `.planning/phases/02-*/02-CONTEXT.md` — Phase 2 viled crawler + storage decisions (NOT YET WRITTEN; Phase 3 plan will reference как соблюдает Phase 2 patterns: alias-YAML format, snapshot-schema, retailer dispatch). Если planner запускается до Phase 2 discuss/plan — flag как gap.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`spike-01-goldapple/notebook.py`** — Camoufox bootstrap pattern, gate-detection logic (title check для shell-vs-real-HTML), microdata extraction via `selectolax tree.css('meta[itemprop="price"]')`. Phase 3 production реализация может прямо переиспользовать эти примитивы (но не файл — он throwaway по D-16). Refactor в `ga_crawler.fetchers.goldapple.Camoufox*` модули.
- **`spike-01-goldapple/_fetch_goldapple_sitemap.py`** (если существует, см. plan 01-05 артефакты) — curl_cffi sitemap fetch pattern; brand-slug extraction from URL. Phase 3 production: rewrite в `ga_crawler.enumeration.goldapple.SitemapEnumerator`.
- **viled-side modules from Phase 2** (НЕ ЕЩЁ существуют) — `ga_crawler.parsers.shared`, `ga_crawler.normalizers.brand`, `ga_crawler.normalizers.volume`, `ga_crawler.alias.BrandAlias`, `ga_crawler.storage.SnapshotWriter`. Phase 3 ВЫЗЫВАЕТ через retailer dispatch (`ParseDispatcher.dispatch(retailer="goldapple", html_or_data) → goldapple-microdata-parser`).

### Established Patterns
- **Per-retailer parser dispatch** (Phase 2 architecture): `ParseDispatcher` switches на retailer-id; goldapple → microdata extraction, viled → `__NEXT_DATA__` extraction. Phase 3 регистрирует goldapple-handler.
- **Append-only snapshot writes** (DATA-03): keyed by `(run_id, retailer, sku_id)`; Phase 3 пишет с `retailer='goldapple'`. Никогда не UPDATE — только INSERT.
- **`runs` row lifecycle** (DATA-05): start → in-progress → final status update в ВСЕХ code paths. Phase 3 продлевает существующий `runs` row (не создаёт новый — viled и goldapple — ОДИН run).
- **Spike rate-limit pattern**: `random.uniform(3, 5)` between fetches на goldapple; `random.uniform(2, 2)` (фактически просто `2`) на viled; concurrency=1. Хранится в config.
- **Stealth UA strategy** (Phase 1 D-04): не self-identification (`ViledPriceMonitor/1.0`-style banned). Camoufox использует встроенный realistic Firefox UA + spoof.

### Integration Points
- **Input ← Phase 2 storage:** Phase 3 читает `v_current_snapshots WHERE retailer='viled' AND run_id=:current` чтобы получить viled-brand-set.
- **Input ← Phase 2 alias-YAML:** Phase 3 читает `<viled-seeded brand-alias YAML>` через `BrandAlias.lookup(brand_norm)` для получения alias-строк.
- **Input ← Phase 2 normalizer:** для каждого goldapple-PDP вызывает `Normalize.brand`, `Normalize.name`, `Normalize.volume` (REQ NORM-02..NORM-05).
- **Output → snapshots table:** INSERT с retailer='goldapple' и all required fields (PARSE-01).
- **Output → NORM-06 файл/таблица:** week-over-week diff goldapple-slug NEW + viled-side missing-brand list.
- **Output → runs.stats JSON-блок:** stale_count, unmatched_viled_brands, unmatched_goldapple_slugs_new, gate_shell_count, smoke_pass.
- **Output → Phase 4 matcher:** matches' input — viled-snapshots ∩ goldapple-snapshots по `(brand_norm, name_norm, volume_norm)` strict-key.
- **Output → Phase 6 delivery:** `runs.status` (success/failed) — пре-send sanity-gate.

### Open dependency on Phase 2
Phase 2 не запущена ещё. Planner должен либо:
1. Дождаться Phase 2 (recommended sequencing per ROADMAP — Phase 3 depends on Phase 2);
2. **Или** plan Phase 3 параллельно, считая Phase 2 модули контрактами (см. STATE.md «Phase 2 and Phase 3 are independent — order is operator preference»). Если параллельно — planner ставит integration-tests на mocked Phase 2 интерфейсы, real integration в финальной волне.

</code_context>

<specifics>
## Specific Ideas

- **«Не дамп всех 1,400+ unmatched goldapple-slugs»** — D-307 явно: low signal-to-noise. Только новые week-over-week.
- **«4ч беспоsлезных fetches не тратятся»** — D-312 smoke-probe цель: предотвратить 4-часовой run на сломанном fingerprint после Camoufox upgrade.
- **«Auto-tune опасно»** — D-310: silent drift вниз M-порога при постепенной anti-bot регрессии = sanity-gate теряет смысл. Только auto-SUGGEST, всегда с manual-confirm.
- **«Phase 3 stack-выбор гейтится подписью спайк-MEMO»** (унаследовано из 01-CONTEXT) — выполнено: MEMO signed off 2026-05-06, stack locked.

</specifics>

<deferred>
## Deferred Ideas

- **Pre-flight coverage gate (<60% viled-брендов с goldapple-match → abort run)** — отвергнуто на v1 (D-306) из-за риска ложных abort первые недели; пересмотр после 8 недель history.
- **Mid-run circuit-breaker по rolling gate-shell-rate** — отвергнуто на v1 (D-309); spike-D-15 fragility line 20% не достигается в healthy state. Пересмотр если post-launch появятся реальные anti-bot regressions.
- **Auto-tune sanity-gate threshold M** — навсегда отвергнуто (D-310 contra). Auto-suggest подходит вместо.
- **Persistent profile dir между weekly runs (warm cookies)** — отвергнуто на v1 (D-311) из-за рисков fingerprint drift / cookie expiry. Пересмотр если smoke-probe + fresh-profile стабильно работает 12+ недель и появится reason для warm.
- **Adaptive profile lifecycle (persist + wipe on detect)** — отвергнуто (D-311) как переосложнение для v1.
- **Brand-facet rendering как primary URL-pool источник** — отвергнуто (D-301): sitemap уже plain-deliverable, brand-facet добавляет ~50 facet-renders в Camoufox + риск gate-shielded facet pages.
- **Hybrid sitemap + facet sanity-cross-check каждую неделю** — отвергнуто (D-301): добавляет 50 fetches/run, на v1 утилита ниже стоимости.
- **Incremental delta через sitemap `<lastmod>`** — отвергнуто на v1 (D-302): sitemap-`<lastmod>` не отслеживает price-change. Возможный пересмотр в v2 если bandwidth budget станет жёстким.
- **Rapidfuzz fuzzy slug-matching** — отвергнуто (D-305 contra), v2 territory (REQ MATCH-V2-01).
- **Explicit `goldapple_slugs:` field в alias YAML** — рассмотрено и отвергнуто (D-304): пользователь предпочёл slug-эвристику с trade-off. Если эвристика покажет высокий false-positive-rate — пересмотр.
- **Ops-Telegram alert per missing brand** — отвергнуто (D-306): шум. Только agg counter в `runs.stats`.
- **Файл `reports/stale-urls-YYYY-WNN.txt`** — отвергнуто (D-303): low utility unless планируем sitemap-overrides.
- **Separate midweek cron для smoke probe** — отвергнуто (D-312): integrated подход покрывает.
- **Latest stable Camoufox без pin** — отвергнуто (D-313 contra): фейл случится в воскресенье ночью.

### Reviewed Todos (not folded)
Не было — todos не сравнивались (gsd-tools todo match-phase 3 = todo_count=0).

</deferred>

---

*Phase: 3-Goldapple Crawl*
*Context gathered: 2026-05-06*
