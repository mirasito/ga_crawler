# Phase 8: Parser Bug Fixes — Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Починить три парсер-бага из live-run #13 (2026-05-13) — goldapple `volume_raw/volume_norm` 88/88 NULL; goldapple `brand+name` concatenation (`Armaniarmani code`); viled `volume_raw` = full `name` string — так чтобы Excel перестал быть пустым.

Дополнительно: добавить null-rate sanity gate (PARSE-FIX-04), ротировать SMOKE_URLs по shape variants (PARSE-FIX-05). Перед любыми изменениями кода парсеров — обязательный shape-sampling sub-spike (30 живых goldapple PDP) чтобы избежать overfitting под единственный STEREOTYPE-скриншот.

**В scope (5 requirements):**
- PARSE-FIX-01 — goldapple volume via selectolax 0.4 Lexbor `:contains`
- PARSE-FIX-02 — goldapple brand+name via `<meta itemprop="name">` микроразметка + invariant `brand.lower() not in name.lower()`
- PARSE-FIX-03 — viled volume via `props.pageProps.attributes[].name == "Размер"` JSON
- PARSE-FIX-04 — sanity-gate null-rate: `goldapple.volume_norm` null rate >50% **или** `goldapple.brand` null rate >50% → run `failed`
- PARSE-FIX-05 — SMOKE_URLs ротация в `runner/gates.py:36` (1 URL на shape variant)

**Вне scope (передаётся в другие фазы):**
- Live-HTML syrupy harness — Phase 9 (TEST-HARNESS-01..06)
- `scripts/capture_fixtures.py` CLI subcommand — Phase 9 (TEST-HARNESS-05)
- Pydantic write-boundary validation — Phase 9 (TEST-HARNESS-06)
- Backfill runs 1-13 — out (forward-only, see ARCHITECTURE.md §C)

</domain>

<decisions>
## Implementation Decisions

### Pre-spike (mandatory W0 sub-spike)
- **D-801:** 30 живых goldapple PDP fetched через Camoufox 0.4.11, стратифицированы 5×6 (lux / mass-market / niche / RU-brands / multi-word brands)
- **D-802:** Output: `.planning/spikes/v1.1-brand-name-shapes/` со структурой:
  - `MEMO.md` — итог: список найденных shape buckets и какой структурный селектор работает для каждого
  - `shape-table.md` — табличный survey: 30 PDP × {brand_raw, brand_displayed_in_h1, name_raw, volume_block_present?, volume_label_text, shape_bucket}
  - `pdp-<NN>-<slug>.html` — 30 raw HTML файлов (опционально gzipped если суммарно >5 MB)
- **D-803:** Wrap-up в project-local skill `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` (по конвенции `spike-01-goldapple/`) — чтобы downstream agents (gsd-planner, gsd-executor) видели выводы spike'а через системный список skills
- **D-804:** Sub-spike блокирует любые правки в `parsers/goldapple_microdata.py` и `parsers/viled_nextdata.py` — это первый task Phase 8

### selectolax 0.3 → 0.4 migration scope
- **D-805:** Pin: `pyproject.toml` selectolax `>=0.4.7,<0.5`. Modest backend остаётся default; Lexbor — opt-in
- **D-806:** Lexbor import СТРОГО локальный в `_extract_volume_block(tree)`: `from selectolax.lexbor import LexborHTMLParser`. Существующие 60+ goldapple parser тестов и viled parser НЕ ТРОГАЕМ
- **D-807:** Blast radius = 1 функция. Если Lexbor backend сломает что-то в smoke против `_debug-product-page.html` существующего фикстура — fallback на ручной selector без `:contains` (Wave 0 spike покажет)

### Plan-wave structure (3 waves, strict TDD)
- **D-808:** **W0 (sequential, blocking):** Plan 08-01 — 30-PDP shape-sampling spike + skill wrap-up + 3 живых fixture-capture (`tests/fixtures/goldapple/_live-2026-05-13-stereotype.html`, `_live-2026-05-13-armani-code.html`, `tests/fixtures/viled/_live-2026-05-13-contre-jour.html`). Output gate: shape-table.md commitable + 3 fixtures committed + skill SKILL.md создан
- **D-809:** **W1 (parallel, 3 plans):** разные файлы, can run concurrent:
  - Plan 08-02 — PARSE-FIX-01 goldapple volume_raw via `_extract_volume_block` (selectolax 0.4 Lexbor)
  - Plan 08-03 — PARSE-FIX-02 goldapple brand+name via sibling `<meta itemprop="name">` reads + invariant canary test
  - Plan 08-04 — PARSE-FIX-03 viled volume_raw via `_extract_volume_from_nextdata(item)` reading `attributes[].name == "Размер"`
- **D-810:** **W2 (sequential):** Plan 08-05 — PARSE-FIX-04 null-rate gate + PARSE-FIX-05 SMOKE_URLs rotation + doc cascade (REQUIREMENTS.md/PROJECT.md/ROADMAP.md/STATE.md)
- **D-811:** Strict TDD per fix: RED test против `_live-2026-05-13-*.html` fixture ДО touching production code, GREEN после. Commit пара RED + GREEN атомарно per плану
- **D-812:** Test count delta: 803 → ~818 (+15: ~10 goldapple parser, ~5 viled parser, plus PARSE-FIX-04 gate test + PARSE-FIX-05 SMOKE rotation smoke). 1 modification к existing viled test (`raw_volume_text == name` flips to "extracted when available, else None")

### PARSE-FIX-04 null-rate gate
- **D-813:** Threshold: **50% absolute** (просто, объяснимо, легко покрывается synthetic-regression тестом per Success Criteria #5)
- **D-814:** Retailer scope: **goldapple-only**. Viled НЕ включаем — там volume может легитимно отсутствовать (Frederic Malle Contre-Jour, Creed Wild Vetiver per BUG-FINDINGS.md)
- **D-815:** Field scope: **volume_norm + brand** оба gated. Gate срабатывает если ЛЮБОЕ из условий:
  - `null_rate(goldapple.volume_norm) > 0.5` → reason `parser_drift_null_volume_rate`
  - `null_rate(goldapple.brand) > 0.5` → reason `parser_drift_null_brand_rate`
- **D-816:** Brand-canary `assert brand.lower() not in name.lower()` остаётся отдельным per-SKU invariant — НЕ заменяется gate'ом. Cascade catches: gate ловит "all SKUs broken" mode, invariant ловит per-SKU regression
- **D-817:** Gate position в pipeline: после persist + parse-quality gate, ДО matcher (`runner/gates.py` join point — same shape as existing `final_threshold_gate`). Cite Plan 02-05 D-203 retailer-agnostic helpers shape

### PARSE-FIX-05 SMOKE_URLs rotation
- **D-818:** Current 3× Givenchy URLs ротируются в:
  1. **STEREOTYPE-style** URL (brand-uppercase-prefix-in-h1) — конкретный URL выбирается из shape-table.md spike output
  2. **Armani-style** URL (brand-duplicated-into-name `Armaniarmani code`) — конкретный URL из shape-table.md
  3. **Givenchy-baseline** URL — оставляем `19000488678-givenchy-irresistible` как known-good baseline (rotation 2026-05-11 per `gates.py:34-35`)
- **D-819:** Final URL slot selection deferred to Plan 08-05 (после W0 spike даёт shape-table)

### Claude's Discretion
- Внутренняя структура `_extract_volume_block(tree)` helper: точный CSS-селектор путь после Lexbor `:lexbor-contains("ОБЪЁМ" i)` — определяется на основе live HTML spike output, не угадываем заранее
- Brand-prefix fallback (`_strip_brand_prefix(name, brand)`): включать или нет — решается по shape-table data. Если `<meta itemprop="name">` присутствует >95% PDP → fallback не нужен. Если <95% → добавляем strip-prefix helper. Решает Plan 08-03 на основе W0 evidence
- Точный JSON path для viled `attributes[].name == "Размер"`: подтверждается Wave-0 mini-probe против живой beauty PDP в Plan 08-01 (clothing fixture `viled-pdp-407682.html` уже подтверждает shape, но beauty PDP path verification нужен)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.1 milestone artefacts
- `.planning/PROJECT.md` — Project description, Active requirements list, v1.1 milestone goal
- `.planning/REQUIREMENTS.md` — Полный v1.1 reqs roster + per-phase mapping. PARSE-FIX-01..05 определены тут verbatim
- `.planning/ROADMAP.md` §"Phase 8: Parser Bug Fixes" — phase Goal + Success Criteria #1-5 + Pitfall mitigation note
- `.planning/STATE.md` — текущее состояние milestone v1.1 (planning, 0/4 phases complete)
- `.planning/MILESTONES.md` § v1.0 — historical context (run #13 evidence, MILESTONE-AUDIT verdict `tech_debt`)

### Research (v1.1 SUMMARY + 4 dimensions)
- `.planning/research/SUMMARY.md` — Executive summary, convergent recommendations across 4 dimensions
- `.planning/research/STACK.md` — selectolax 0.4 Lexbor backend evidence + pin guidance + rejected alternatives (lxml, parsel, Patchright revisit)
- `.planning/research/FEATURES.md` — Feature decomposition into Buckets A-D, P1/P2 split, anti-feature list
- `.planning/research/ARCHITECTURE.md` §A (parser-fix integration pattern: file-line table for Bugs #1-#3, Option 3 dual-fixture strategy) — **load-bearing for Phase 8 implementation**
- `.planning/research/ARCHITECTURE.md` §C (downstream impact: forward-only no-backfill)
- `.planning/research/PITFALLS.md` § Pitfall 1 (parser-fix overfitting — sample-first protocol) + § Pitfall 2 (cassette staleness — feeds Phase 9 but informs Phase 8 fixture-capture mindset)
- `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` — **evidence document**: 3 bug reports + DB samples + live PDP screenshot description STEREOTYPE/sago

### v1.0 production parser code (touched by Phase 8)
- `src/ga_crawler/parsers/goldapple_microdata.py` — current parser (lines 319-332 brand/name, line 358 volume passthrough)
- `src/ga_crawler/parsers/viled_nextdata.py` — current parser (line 215 `raw_volume_text=name` aliasing)
- `src/ga_crawler/parsers/dispatcher.py:51` — dispatcher dict shape (unchanged by Phase 8 — additive only)
- `src/ga_crawler/runner/gates.py:34-36` — SMOKE_URLS constant + `load_smoke_urls_from_config` operator-rotation surface
- `src/ga_crawler/runner/gates.py` — pattern for D-203 retailer-agnostic gate helpers (PARSE-FIX-04 follows same shape)
- `src/ga_crawler/runner/stats.py` — `VILED_STATS_KEYS` pattern (PARSE-FIX-04 stat keys follow same shape for atomic persist)

### v1.0 spike conventions (reuse for Phase 8 W0)
- `.planning/spikes/01-goldapple/MEMO.md` — pattern для spike memo (used by spike-01-goldapple skill)
- `.claude/skills/spike-01-goldapple/SKILL.md` — pattern для wrap-up project skill (Phase 8 W0 mirrors this shape)
- `.planning/phases/07-scheduler/07-CONTEXT.md` (если существует) — reference for Phase-7 ops conventions
- `tests/conftest.py:23-37` — fixture-loading pattern для adding `_live-2026-05-13-*.html`

### Tooling / libraries
- selectolax 0.4 Lexbor docs: `https://selectolax.readthedocs.io/en/latest/lexbor.html` (per STACK.md §"selectolax")
- Camoufox 0.4.11 LOCKED per Phase 3 D-313 (smoke probe `camoufox_version_expected` invariant)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/ga_crawler/fetchers/goldapple.py:GoldappleFetcher` — Camoufox-direct fetcher уже работает; W0 spike использует verbatim для capture 30 PDP
- `src/ga_crawler/runner/gates.py` D-203 helpers (`auto_suggest_threshold`, `final_threshold_gate`, `parse_quality_gate`) — pattern для PARSE-FIX-04 null-rate gate
- `tests/conftest.py:23-37` `goldapple_pdp_html` fixture loader — 6-line extension добавит `goldapple_pdp_html_live_v2` для STEREOTYPE/Armani fixtures
- `tests/fixtures/goldapple/_debug-product-page.html` (Givenchy baseline) — НЕ ТРОГАЕМ, остаётся как backward-compat fixture для 60+ существующих тестов
- `tests/fixtures/viled/viled-pdp-407682.html` (clothing) — подтверждает `attributes[].name == "Размер"` shape для PARSE-FIX-03
- `pyproject.toml:51-53` pytest markers `live` + `integration` — `live` существует, но не используется; Phase 8 не подключает (Phase 9 формализует), но в spike capture можно использовать как mental anchor

### Established Patterns
- Pipe-and-filter monolith: `fetchers → parsers → normalizers → storage → matcher → reporter → delivery` — Phase 8 трогает ТОЛЬКО parsers/, internal contracts preserved
- Append-only fixtures: `tests/fixtures/<retailer>/` сгруппированы по retailer (НЕ по date) → новые `_live-2026-05-13-*.html` идут туда, НЕ в `tests/fixtures/live/` (нарушит convention)
- `MainRunResult` D-616 stat fields: PARSE-FIX-04 добавит 2 поля shape `goldapple_volume_null_rate: float`, `goldapple_brand_null_rate: float` + reason string в `runs.stats` (single atomic `patch_stats` per Phase 2 D-211)
- TDD discipline (per Phase 2-7 plans): RED commit (тест добавлен, fails) → GREEN commit (production код) → атомарные pairs
- Sub-spike convention: `.planning/spikes/NN-name/{MEMO.md, README.md, raw artefacts}` + wrap-up в project-local skill `.claude/skills/spike-findings-<slug>/SKILL.md` — Phase 1 paradigm

### Integration Points
- `parsers/dispatcher.py:51` `asdict(GoldappleRawProduct)` → unchanged dict shape (additive `raw_volume_text` already exists at field-level)
- `normalizers/volume.py:118 parse_volume` → автоматически отработает на extracted `volume_raw` text (`75 ОБЪЁМ / МЛ` или `78 мл` парсится 24-entry UNIT_TABLE)
- `matcher/strict_key.py:58` D-402 SQL JOIN `volume_norm IS NOT NULL` filter → как только parser отдаёт правильный volume, matcher автоматически начнёт находить пары (no matcher change needed)
- `reporter/queries.py` `per_sku_deltas` + `assortment_gaps` → пустые сейчас, populated автоматически как только matches table наполняется
- `delivery/telegram_client` → uchanged, шлёт уже непустой xlsx как только reporter возвращает data

</code_context>

<specifics>
## Specific Ideas

- **Brand-prefix dedupe ситуация:** evidence `Armaniarmani code` — это НЕ "Armani Armani Code" с пробелом, это slug-concatenation в SSR template. Goldapple emits `<meta itemprop="name" content="armani code">` отдельно. Решение per ARCHITECTURE.md §A: читать `<meta itemprop="name">` внутри product `itemscope`, НЕ `<h1>` text. Fallback `_strip_brand_prefix(name, brand)` — только если microdata пустой.
- **STEREOTYPE evidence:** brand `STEREOTYPE` (uppercase), SKU slug `sago`, нишевая парфюмерия. Live PDP screenshot 2026-05-13 user-provided. Volume block: `[78]  ОБЪЁМ / МЛ` flex-box of `<div>`s без `itemprop="size"`.
- **Contre-Jour evidence:** viled SKU `Frederic Malle / Парфюмерная вода Contre-Jour` без volume в title → `volume_norm = NULL` сейчас. Phase 8 fix: попытаться из `attributes[].name == "Размер"`, accept None если действительно отсутствует.
- **Synthetic-regression test (Success Criteria #5):** Plan 08-05 включает unit test который инжектит mocked snapshot batch с 60% null volume_norm → asserts `run.status == "failed"`, `run.stats.failure_reason == "parser_drift_null_volume_rate"`.

</specifics>

<deferred>
## Deferred Ideas

- **Backfill runs 1-13** — out (forward-only per ARCHITECTURE.md §C; HTML gone, matcher idempotent, auto-suggest 4-week median rolls garbage out by run #17). One-line annotation в `MILESTONES.md` достаточно.
- **scripts/capture_fixtures.py CLI subcommand** — Phase 9 (TEST-HARNESS-05) формализует. Phase 8 W0 захватывает 3 fixtures ad-hoc через ручной Camoufox run.
- **syrupy 4.7 HTML snapshot harness** — Phase 9 (TEST-HARNESS-01..03).
- **Pydantic `RawProduct` write-boundary validation** — Phase 9 (TEST-HARNESS-06).
- **Brand-coverage quota canary** — Phase 9 P2 cheap-bundle (TEST-HARNESS-04).
- **Match-rate floor alert** (упомянутый в SUMMARY.md как "A5") — не в v1.1 reqs roster; defer как v2 backlog item если operator пожалуется на silent low-match-rate runs после Phase 11 deploy.
- **viled volume null-rate gate** — Phase 8 сознательно gold-only (legitimate Nones у viled). Если post-deploy evidence покажет что и viled нужен gate — добавим в v1.2.

</deferred>

---

*Phase: 8-Parser Bug Fixes*
*Context gathered: 2026-05-13*
