---
tags: [session, phase-8, wave-0, spike, parser-bugs, milestone-v1.1, microdata-pivot, gsd-execute-phase]
date: 2026-05-14
phase: 8
wave: 0
verdict: W0-shipped-pivot-found
session_type: execute-phase-w0
commits: 1
---

# 2026-05-14 — Phase 8 W0 spike done, microdata премиса invalidated — pivot к h1-spans extraction

`/gsd-execute-phase 8` запустилась в inline-checkpoint режиме (user choice — operator-action tasks решает Claude вместо ручной операторской курации). W0 (Plan 08-01) выполнен полностью inline за ~30 min wall-clock через auto-sample подход. Сначала курировано 30 PDP URLs через `curate_urls.py` против реального goldapple sitemap (52,051 unique slugs), потом `capture.py` отфетчил все 30 PDPs (30/30 HTTP 200, ~3 min via Camoufox). **Spike поймал load-bearing finding**: Plan 08-03 premise (читать product brand+name из `<meta itemprop="name">`) **полностью невалидна** — этих metatags на goldapple PDP **нет** (0/30 PDPs). Реальные spans `_ga-pdp-title__brand_*` + `_ga-pdp-title__name_*` внутри `<h1>` дают 100% (30/30) clean extraction.

## Pipeline execution

| Шаг | Артефакт | Размер / нюанс |
|---|---|---|
| 1. URL curation auto-sample | `.planning/spikes/v1.1-brand-name-shapes/curate_urls.py` + `sampled-urls.py.snippet` | 30 URLs стратифицированы по 5 buckets через slug-prefix keyword match против real sitemap; deterministic seed=20260513 |
| 2. Probe brands в sitemap | `brand-probe.txt` (50+ brand keyword checks) | Tom Ford, Jo Malone, Atelier, Chanel, YSL, Versace, Profumum, Le Labo, Maison Crivelli, Nasomatto не присутствуют в goldapple.kz/KZ — substitutes drawn from same shape category |
| 3. Live fetch 30 PDPs | `pdp-NN-*.html` × 30, ~6.8 MB total | Camoufox 0.4.11 + 3-5s rate-limit, 100% success, no GroupIB challenge encountered |
| 4. Viled Contre-Jour fetch | `viled-contre-jour-408872.html` | curl_cffi separately (item id traced via виled-catalog-women-1310-page1 fixture); confirmed `props.pageProps.attributes[0].attributes[]` contains Размер |
| 5. Shape inspection | `inspect_shapes.py` + `shape-survey.txt` | Initial walker using `<meta itemprop="name">` returned 0/30 — surprise |
| 6. Raw HTML verification | direct grep в pdp-07 + giв legitимный `_debug-product-page.html` analog | **Discovery:** product brand+name lives в `<h1>` child spans (CSS classes `_ga-pdp-title__brand_*` + `_ga-pdp-title__name_*`) — 30/30 (100%) coverage |
| 7. Pivot decision | MEMO.md + SKILL.md updated with h1-spans strategy | downstream W2 (Plan 08-03) executor will adapt via spike skill in registry |

## Critical findings (для downstream waves)

### 1. Microdata premise INVALID — pivot к h1-spans

Plan 08-03 specifies "Goldapple `name` extracted from product-level `<meta itemprop="name">` (sibling of `[itemprop="brand"]` inside Product itemscope)". Реальность 2026-05-14:

- **0/30 PDPs** имеют product-level `<meta itemprop="name">`. Все встреченные `itemprop="name"` (2 per page) — это breadcrumb labels, review-author names, footer Organization metadata
- **0/30 PDPs** имеют `<span itemprop="brand">` inside Product itemscope — only внутри related-product cards в нижней части page
- v1.0 production parser `tree.css_first('[itemprop="brand"]')` matched FIRST related-product card brand — coincidental cross-product contamination объясняет run #13 bugs

**New selectors:**
```python
H1_HEADING_RE = re.compile(r'<h1[^>]*_ga-pdp-title__heading_[^>]*>(.{0,2000}?)</h1>', re.DOTALL)
BRAND_SPAN_RE = re.compile(r'class="[^"]*_ga-pdp-title__brand_[^"]*"[^>]*content="([^"]*)"')
NAME_SPAN_RE  = re.compile(r'class="[^"]*_ga-pdp-title__name_[^"]*"[^>]*>([^<]*)<')
```
CSS hash suffix (`_1yrfv_339`) build-specific → substring-match (`class*=` в CSS, regex в Python).

### 2. `_strip_brand_prefix` fallback NOT NEEDED

28/30 (93%) PDPs имеют clean `.brand` / `.name` separation. 2 exceptions — `Armani` + `armani code`, `Givenchy` + `GIVENCHY GENTLEMAN RESERVE PRIVEE` — это upstream data redundancy на стороне goldapple, не parser bug. Stripping изменил бы user-facing product name.

### 3. D-816 invariant canary — SOFTEN to log-only

`brand.lower() not in name.lower()` фейлит legitimately на 2/30 (7%). Если оставить fail-hard, gate будет блокировать runs на upstream data quality issues, которые мы не контролируем. Конвертировать в structured log warning.

### 4. Shape histogram (для context)

| Bucket | Count | Description | Bug source |
|---|---|---|---|
| stereotype-style | 16 (53%) | Brand title-case, name UPPERCASE (Creed/AVENTUS); или brand UPPERCASE (MAISON MARGIELA) | Bug #1 (pdp-16) |
| mixed-case | 11 (37%) | Brand + name Title-Case / Sentence case | — |
| armani-style | 2 (7%) | Brand string substring of name | Bug #2 (pdp-07) |
| givenchy-baseline | 1 (3%) | Brand title-case + name lowercase (Calvin Klein / cotton musk) | — |

### 5. Volume block coverage

25/30 (83%) PDPs имеют `ОБЪЁМ / МЛ` flex-box → `selectolax 0.4 Lexbor :lexbor-contains` сработает. 5 PDPs без блока (eye creams, gels, patches) — legitimate None, helper returning None для них корректно.

### 6. SMOKE_URLs rotation finalized

| Slot | URL | Why |
|---|---|---|
| 1 | `goldapple.kz/19000440474-stereotype-sago` | STEREOTYPE-style canonical (Bug #1 source) |
| 2 | `goldapple.kz/19000195723-armani-code` | Armani-style canonical (Bug #2 source) |
| 3 | `goldapple.kz/19000488678-givenchy-irresistible` | Givenchy baseline (RETAINED from `runner/gates.py:34-35`) |

## Spike outputs committed

```
9c70513 feat(08-01): W0 shape-sampling spike — invalidates Plan 08-03 microdata premise
```

48 files / 4040 insertions:
- `.planning/spikes/v1.1-brand-name-shapes/` — MEMO + shape-table + 30 PDPs + viled Contre-Jour + 6 scratch helpers
- `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` — system-discoverable index (загружается gsd-executor agents через registry)
- `tests/fixtures/goldapple/_live-2026-05-13-{stereotype,armani-code}.html` — Bug #1+#2 evidence
- `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` — Bug #3 evidence
- `tests/conftest.py` — 3 new session-scoped fixture loaders
- `.planning/phases/08-parser-bug-fixes/08-01-SUMMARY.md`

Test suite: 801 passed / 1 skipped / 2 pre-existing failures (`test_cli_deliver.py` x2; verified via git stash → master HEAD baseline).

## Deviations from Plan 08-01

| # | Deviation | Justification |
|---|-----------|---------------|
| 1 | Task 1 operator URL curation → auto-sample via `curate_urls.py` | User approved at execute-phase start ("Auto-sample from sitemap.xml (Recommended)") |
| 2 | Task 3 operator shape-table fill → programmatic `inspect_shapes.py` + visual one-pass review | Generates same 30-row × 6-column survey deterministically |
| 3 | Bucket substitutions от D-801 spec (Tom Ford / Jo Malone / etc.) | Brands not present в goldapple.kz/KZ sitemap (verified via `probe_brands.py`); substitutes drawn from same shape category |
| 4 | Plan 08-03 microdata premise invalidated | Pivot к h1-spans documented в MEMO + SKILL; downstream executor adapts |
| 5 | PII canary regex flagged Nuxt buildId UUID + `Cookie:true` i18n config | False positives; actual cookies/session-tokens/auth absent — documented в commit msg |

## What's next

User interrupted mid-W1 со словами «сохранить сессию». На момент interrupt оба subagent'а (08-02 + 08-04) уже запустились параллельно и landed RED commits (`9df9c55` + `214e8ee`). 08-04 GREEN полностью имплементирован в working tree (helper + parse_pdp wiring + __all__ export + D-812 test flip) но НЕ committed. 08-02 GREEN частично — selectolax pin bumped + uv.lock regen committed only via working-tree mutation, helper code еще не написан.

Task state на момент save:
- ✅ W0 (Plan 08-01) — committed 9c70513
- 🟡 W1 (Plans 08-02 + 08-04) — оба RED committed; 08-04 GREEN ready (uncommitted), 08-02 GREEN partial (selectolax bumped, helper not yet)
- ⏸ W2 (Plan 08-03) — sequenced после 08-02 GREEN merges; will need h1-spans pivot per SKILL.md
- ⏸ W3 (Plan 08-05) — depends on W1+W2; doc cascade close-out
- ⏸ Phase 8 verification + STATE.md update

**Recovery paths next session:**

1. `/gsd-execute-phase 8 --wave 1` — re-spawns both gsd-executor agents; они увидят landed RED commits + partial GREEN state и завершат atomically
2. Manual finish: implement `_extract_volume_block` in `src/ga_crawler/parsers/goldapple_microdata.py` (see SKILL.md ОБЪЁМ/МЛ flex-box selector), commit GREEN, then resume W2+W3 via `/gsd-execute-phase 8 --wave 2`
3. Discard partial: `git checkout pyproject.toml uv.lock src/ga_crawler/parsers/viled_nextdata.py tests/unit/test_viled_nextdata_parser.py` + `git revert 9df9c55 214e8ee` → clean state, restart W1 from scratch

`/gsd-execute-phase 8 --wave 1` recommended — наименьший cognitive load, subagents picky up state correctly.

## Key learnings для будущих фаз

- **Sample-first protocol catches load-bearing premise errors** перед coding. Pitfall 1 (parser-fix overfitting) был mitigated structurally — без 30-PDP sample, Plan 08-03 ушёл бы в production с broken selector
- **Downstream executor adaptation через project-local skills works** — Plan 08-03 PLAN.md остаётся as-written, но executor агент читает SKILL.md и понимает strategy pivot; CONTEXT.md "Claude's Discretion" блок explicit разрешает это
- **Auto-sample with deterministic seed beats manual curation** для shape-sampling задач — `curate_urls.py` deterministic (seed=20260513) + reusable + auditable; manual operator curation добавляет ~60 min wall-time без качественного advantage
- **PII canary regex `[a-f0-9]{8}-[a-f0-9]{4}-...` too broad** — публичные buildIds + asset hashes flag false-positive; tighten by context-exclusion (`buildId` / `_nuxt` / `buildAssetsDir` near match)

---

[[2026-05-13 — Phase 8 plan ready (5 plans, 4 waves) — wave restructure caught real file-overlap]] (previous session)
[[Goldapple brand+name extraction — h1 spans CSS class substring, не itemprop microdata]] (decision born this session)
[[Текущие приоритеты — Phase 8 W0 done, Wave 1-3 next]] (next focus)
