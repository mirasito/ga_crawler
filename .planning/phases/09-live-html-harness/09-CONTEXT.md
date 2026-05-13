# Phase 9: Live-HTML Harness — Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Закрепить ретроактивно Phase 8 parser-фиксы тестовой инфраструктурой, ловящей fixture-vs-live drift, чтобы такой gap как run #13 (frozen Givenchy fixtures прошли green, а STEREOTYPE/Armani/Contre-Jour shapes выдали 88/88 NULL volume в проде) выдавал loud test failure а не silent empty Excel.

**В scope (6 requirements — TEST-HARNESS-01..06):**
- TEST-HARNESS-01 — syrupy 4.7 dev-dependency + `HTMLSnapshotExtension(SingleFileSnapshotExtension)` с `file_extension="html"`, `WriteMode.TEXT`
- TEST-HARNESS-02 — captured HTML в `tests/fixtures/<retailer>/_live-YYYY-MM-DD-<slug>.html` с sidecar JSON `{date, url, status, html_size, title, camoufox_version}`; PII canary (no `cf_clearance=`, `bot\d+:`, UUID hc-ping paths); 50 MB size budget
- TEST-HARNESS-03 — `tests/live/test_parser_drift.py` с `@pytest.mark.live` маркером; opt-in через `pytest -m live`; default cassette-replay, `--refresh-live` flag для re-fetch
- TEST-HARNESS-04 (P2 cheap-bundle) — brand-coverage quota canary: `≥1 fixture per active brand` для брендов виденных в последние 4 weekly runs
- TEST-HARNESS-05 (P2 cheap-bundle) — `python -m ga_crawler capture-fixtures` CLI subcommand
- TEST-HARNESS-06 — Pydantic `RawProduct` validation at `SqliteSnapshotWriter.persist` boundary

**P2 bundle gate:** TEST-HARNESS-04 + TEST-HARNESS-05 включаем в Phase 9 если суммарный elapsed на W0+W1 < 8h (per D-902). Иначе — 09-03 = defer-to-v1.2 doc cascade.

**Вне scope (передаётся в другие фазы или v1.2):**
- Auto-scheduled live-drift cron (weekly refresh job + ops-chat diff) — v1.2 (если operator request'нет после Phase 11 production observations); v1.1 = operator-only opt-in (D-905)
- GitHub Action CI integration для live tests — v1.2 (нужен self-hosted runner для Camoufox+KZ-IP)
- Backfill runs 1-13 — out (forward-only per ARCHITECTURE.md §C; зафиксировано в Phase 8 CONTEXT.md)
- Parser source changes — Phase 8 уже закрыт; Phase 9 только тестирует
- Telegram delivery / cron / VPS provisioning — Phase 11

</domain>

<decisions>
## Implementation Decisions

### Plan-wave structure
- **D-901:** **3-plan wave structure** (3 plans, P2 GO/NO-GO checkpoint after W1):
  - **09-01 (W0 sequential, must-have):** TEST-HARNESS-01 + TEST-HARNESS-02 — syrupy 4.7 install (`uv add --dev "syrupy>=4.7,<5.0"`); `HTMLSnapshotExtension` в `tests/conftest.py` (или dedicated `tests/_snapshot_extension.py` если conftest разрастается); fixture-path convention canary; sidecar JSON helper (`tests/_fixture_metadata.py`); PII canary `_assert_fixture_clean(path)` функция (regex + size); pytest `live_fixtures` collection fixture
  - **09-02 (W1 parallel-safe, 2 plans):** разные файлы, can run concurrent:
    - TEST-HARNESS-03 — `tests/live/test_parser_drift.py` ретроактивно подключает 3 Phase 8 fixtures (`_live-2026-05-13-stereotype.html`, `_live-2026-05-13-armani-code.html`, `tests/fixtures/viled/_live-2026-05-13-contre-jour.html`); two-mode (cassette-replay default + `--refresh-live` flag); assertions: brand+volume_raw+name non-empty, brand not in name lowercase, current_price > 0
    - TEST-HARNESS-06 — Pydantic `GoldappleRawProduct` + `ViledRawProduct` schemas + integration в `SqliteSnapshotWriter.persist` (storage module border)
  - **09-03 (W2 sequential, conditional):** TEST-HARNESS-04 + TEST-HARNESS-05 P2 bundle ИЛИ defer-to-v1.2 doc cascade (REQUIREMENTS.md / STATE.md / ROADMAP.md)
- **D-902:** **P2 GO/NO-GO criterion = time-budget < 8h elapsed W0+W1.** Измеряется по git commit timestamps первого RED commit'а 09-01 → последний GREEN commit 09-02. ≥8h → 09-03 пишет defer-to-v1.2 doc cascade (TEST-HARNESS-04/05 status → `Deferred to v1.2`; REQUIREMENTS.md per-req mapping обновляется). User может ручным override переопределить решение в любую сторону через CONTEXT-PATCH или явный invocation argument.

### Pydantic write-boundary semantics (TEST-HARNESS-06)
- **D-903:** **Validation boundary = `SqliteSnapshotWriter.persist`** (storage module border, per REQUIREMENTS.md verbatim). Pydantic `ValidationError` raise'ится per-SKU; writer ловит и инкрементирует новый `runs.stats` key `schema_rejected_count`. **Threshold gate:** `rejected_rate = schema_rejected_count / total_attempted_persist > 0.05` (5%) → run помечается `failed` с reason `schema_validation_rejected_rate`. Gate position: после `SqliteSnapshotWriter.persist` complete, ДО PARSE-FIX-04 null-rate gate (cascade — schema-violation проявляется раньше null-rate-violation). Ортогонально PARSE-FIX-04: тот ловит "все SKU имеют null volume" mode; этот ловит "schema контракт сломался" mode.
- **D-904:** **Per-retailer schema** (relaxed/strict split per fixture evidence):
  - `GoldappleRawProduct` (strict): `brand: NonEmptyStr` REQUIRED, `volume_raw: NonEmptyStr` REQUIRED, `name: NonEmptyStr` REQUIRED, `current_price: Decimal` > 0 REQUIRED, `sku_id: NonEmptyStr` REQUIRED. Volume legitimately всегда есть на goldapple beauty PDP (per shape-table.md spike output).
  - `ViledRawProduct` (relaxed): `brand: NonEmptyStr` REQUIRED, `name: NonEmptyStr` REQUIRED, `current_price: Decimal` > 0 REQUIRED, `sku_id: NonEmptyStr` REQUIRED, `volume_raw: NonEmptyStr | None` (legitimate Nones: Frederic Malle Contre-Jour, Creed Wild Vetiver per BUG-FINDINGS.md).
  - Base class `RawProductBase` со shared полями; per-retailer subclass'ы переопределяют только `volume_raw` тип. Файл: `src/ga_crawler/storage/schemas.py` (новый) или extend существующий `storage/types.py` если он есть. Planner выбирает по фактической shape storage модуля.

### Live-drift test integration (TEST-HARNESS-03)
- **D-905:** **Operator-only opt-in, NO cron wiring.** ARCH Open Q2 рекомендует manual для v1.1 — следуем. weekly-run.sh **не меняется**. Новый README §8 «Live HTML harness» документирует когда запускать (pre-deploy, post-suspected-drift, по запросу operator), как читать вывод, что делать с drift output. Drift failures пишут `.planning/research/parser-drift-YYYY-MM-DD.md` per ARCH §B спецификации (diagnostic markdown с per-fixture per-assertion verdict + suggested next steps).
- **D-906:** **Two-mode harness** (cassette-replay default + explicit refresh):
  - **Default `pytest -m live`** (быстро, deterministic, no network): читает frozen `_live-2026-05-13-*.html` fixtures + runs `parse_pdp` + asserts invariants. Это unit-test parser против captured live HTML.
  - **`pytest -m live --refresh-live`** (operator path): re-fetch SMOKE_URLs через Camoufox 0.4.11 → `assert html == html_snapshot` (syrupy) → если drift есть, **syrupy fails missing-snapshot soundness rule** + пишет diagnostic markdown. С `--snapshot-update` дополнительно перезаписывает fixture + регенерирует sidecar JSON.
  - **Stale fixture warning:** sidecar `date` > 30 дней → pytest warning (не fail). Operator решает refresh.

### PII canary + 50 MB size budget enforcement (TEST-HARNESS-02)
- **D-907:** **Two enforcement points в pytest** (plain `pytest`, runs in default CI, not `-m live`):
  - **Fixture loader integration:** `tests/conftest.py` extends `goldapple_pdp_html` / `viled_pdp_html` fixture loaders так чтобы любой `_live-*.html` file path проходил через `_assert_fixture_clean(path)` ДО возврата content. Грязный fixture → `pytest.fail()` на load, любой unit-тест который пытается его использовать падает.
  - **Standalone canary test:** `tests/test_live_fixtures_pii_canary.py` итерирует `glob("tests/fixtures/*/[!_]*.html") + glob("tests/fixtures/*/_live-*.html")`, regex-scan'ит на `cf_clearance=`, `bot\d+:`, UUID hc-ping paths (`/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`), assert filesize < 50 MB per файл AND aggregate sum < 200 MB. Этот тест собирается **default pytest invocation** — любой dev/CI ловит до merge.
  - **Capture-fixtures CLI scrub-on-write (если P2 GO):** TH-05 CLI вызывает `_scrub_html(content)` функцию перед записью на disk (удаляет cookie headers, `bot\d+` tokens, UUID hc-ping paths). Дублирующий barrier; pytest canary остаётся как safety net для manual-dropped fixtures.

### Claude's Discretion
- Точное имя файла для `HTMLSnapshotExtension` class location — `tests/conftest.py` если class < 30 LOC, иначе `tests/_snapshot_extension.py`. Planner выбирает.
- Точное имя файла для Pydantic schemas — `src/ga_crawler/storage/schemas.py` (новый) ИЛИ extend `storage/types.py` если он существует — `gsd-planner` инспектирует storage module и выбирает.
- Sidecar JSON helper — отдельный модуль `tests/_fixture_metadata.py` ИЛИ inline в conftest. Решается planner'ом по фактическому LOC count.
- Точная регулярка для UUID hc-ping detection — стандартная UUID v4 `[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}`; уточняется planner'ом если evidence показывает hc-ping UUIDs не v4.
- `parser-drift-YYYY-MM-DD.md` template shape — следует Phase 1 spike memo convention.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.1 milestone artefacts
- `.planning/PROJECT.md` — Active requirements list (TEST-FIX line 34); v1.1 milestone goal + Phase status block
- `.planning/REQUIREMENTS.md` lines 21-28 — TEST-HARNESS-01..06 verbatim; P2 cheap-bundle annotation (lines 94-95)
- `.planning/ROADMAP.md` §"Phase 9: Live-HTML Harness" (lines 78-89) — Goal + 5 Success Criteria + Pitfall mitigation notes
- `.planning/STATE.md` — milestone v1.1 status, locked decisions block (syrupy 4.7 added as dev-only; B4/B5 = P2 cheap-bundle inside Phase 9 try-same-milestone-else-defer)
- `.planning/MILESTONES.md` § v1.0 — historical context (run #13 evidence, audit verdict tech_debt)

### Research (v1.1)
- `.planning/research/SUMMARY.md` — executive summary, convergent recommendations across 4 dimensions
- `.planning/research/STACK.md` §B (lines 85-119) — syrupy `SingleFileSnapshotExtension` pattern verbatim; missing-snapshot soundness rule; pytest-recording / VCR.py rejected; code example
- `.planning/research/STACK.md` §"What NOT to Use" (line 200) — pytest-recording bypasses curl_cffi+Camoufox; do not adopt
- `.planning/research/ARCHITECTURE.md` §B (lines 80-117) — **harness placement and contract: file paths, sidecar JSON shape, drift test responsibilities, capture-fixtures CLI shape** — load-bearing for Phase 9 implementation
- `.planning/research/ARCHITECTURE.md` §C (lines 120-143) — forward-only no-backfill; Phase 9 inherits same constraint
- `.planning/research/ARCHITECTURE.md` §E (line 198) — build-order rationale: parser-fix SECOND-from-bottom, harness "locks in parser-fix retroactively"
- `.planning/research/PITFALLS.md` §1 (parser-fix overfitting) — Phase 8 closed but informs which fixture brand-shape canary catches
- `.planning/research/PITFALLS.md` §2 (cassette staleness) — Phase 9 explicit target; informs D-906 stale-fixture warning + D-905 operator-only opt-in choice
- `.planning/research/PITFALLS.md` §4 (flake hides drift) — `@pytest.mark.flaky` ban canary applies to `tests/live/` (NOT yet wired; v1.2 could add grep canary)
- `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` — Phase 8 evidence document; informs which SKU shapes Phase 9 harness must lock retroactively

### Phase 8 artefacts (predecessor — Phase 9 binds Phase 8 fixtures retroactively)
- `.planning/phases/08-parser-bug-fixes/08-CONTEXT.md` — Phase 8 implementation decisions; especially D-808/D-809/D-810/D-811 (TDD discipline + fixture path conventions)
- `.planning/phases/08-parser-bug-fixes/08-01-SUMMARY.md` — W0 spike summary; references shape-table.md + 30 raw PDP files
- `.planning/spikes/v1.1-brand-name-shapes/MEMO.md` — shape buckets evidence + brand-shape canary inputs for TEST-HARNESS-04
- `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` — wrap-up skill; visible to gsd-planner/gsd-executor as project-local skill

### v1.0 production code (Phase 9 wires tests against — does NOT modify)
- `src/ga_crawler/parsers/goldapple_microdata.py` — fixed parser (Phase 8 PARSE-FIX-01..02 landed)
- `src/ga_crawler/parsers/viled_nextdata.py` — fixed parser (Phase 8 PARSE-FIX-03 landed)
- `src/ga_crawler/parsers/dispatcher.py:51` — `asdict(GoldappleRawProduct)` dispatcher shape (Pydantic schema mirrors this — additive)
- `src/ga_crawler/storage/` (whole module) — `SqliteSnapshotWriter.persist` boundary; planner inspects to confirm exact file/class shape for D-903 wire-in
- `src/ga_crawler/runner/gates.py:34-36` SMOKE_URLS — TEST-HARNESS-03 uses as source-of-truth для URL list; gates pattern (D-203 retailer-agnostic helpers) для schema-rejected-rate gate
- `src/ga_crawler/runner/stats.py` — `VILED_STATS_KEYS` pattern; новый `schema_rejected_count` ключ следует тому же atomic patch_stats shape
- `src/ga_crawler/fetchers/goldapple.py:GoldappleFetcher` — Camoufox-direct fetcher; capture-fixtures CLI (TH-05) и `--refresh-live` flag (TH-03) переиспользуют verbatim
- `src/ga_crawler/fetchers/viled.py:ViledFetcher` — curl_cffi fetcher; capture-fixtures CLI вызывает для viled URLs

### Live fixtures (Phase 8 W0 output — Phase 9 binds retroactively)
- `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` — STEREOTYPE-shape PDP (brand uppercase, structured volume block)
- `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` — Armani-shape PDP (brand-duplicated-into-name slug)
- `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` — Frederic Malle Contre-Jour (legitimate None volume — viled-relaxed schema evidence)
- `tests/fixtures/goldapple/_debug-product-page.html` — Givenchy baseline (Phase 2 era); НЕ ТРОГАЕМ; остаётся для 60+ existing parser tests
- `tests/conftest.py:23-37` — existing fixture loader pattern; extends для PII canary integration

### Tooling / libraries
- syrupy docs: `https://github.com/syrupy-project/syrupy` (Context7 ID `/syrupy-project/syrupy`); `SingleFileSnapshotExtension` + `WriteMode.TEXT` + missing-snapshot soundness rule
- syrupy via Simon Willison TIL: `https://til.simonwillison.net/pytest/syrupy` — idiomatic patterns
- Pydantic 2 docs (already in stack): `https://docs.pydantic.dev/latest/` — `ValidationError`, custom validators, `model_validator(mode="after")` для cross-field rules
- `pyproject.toml [tool.pytest.ini_options].markers` — `live` маркер уже declared (Phase 7); Phase 9 наконец wire'ит его up

### Hazards / project memory (relevant)
- `hazard_dotenv_walks_from_file` — capture-fixtures CLI (if P2 GO) запускается standalone и нуждается в Camoufox env config; use `find_dotenv(usecwd=True)` not bare `load_dotenv()`
- `hazard_worktree_uses_stale_origin_master` — если используется worktree-isolation для parallel W1 plans (09-02 dual), planner коммитит W0 09-01 на master ДО spawn'а 09-02 agents

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py:23-37` `goldapple_pdp_html` fixture loader — base pattern для `_assert_fixture_clean(path)` integration (D-907)
- `src/ga_crawler/fetchers/goldapple.py:GoldappleFetcher` + `fetchers/viled.py:ViledFetcher` — reused verbatim для `--refresh-live` mode (D-906) и capture-fixtures CLI (TH-05 если P2 GO)
- `src/ga_crawler/runner/gates.py` D-203 retailer-agnostic helpers (`auto_suggest_threshold`, `final_threshold_gate`, `parse_quality_gate`) — pattern для `schema_rejected_rate_gate` (D-903)
- `src/ga_crawler/runner/gates.py:34-36` `SMOKE_URLS` constant — source-of-truth для drift test URL list (TH-03); Phase 8 D-818 уже ротировал на 3 shape-variant URLs
- `src/ga_crawler/runner/stats.py` `VILED_STATS_KEYS` 9-tuple — pattern для добавления `schema_rejected_count` key (atomic patch_stats per Phase 2 D-211)
- `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` + `_live-2026-05-13-armani-code.html` + `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` — Phase 8 W0 живые fixtures; TH-03 retroactively wraps в syrupy `assert html == html_snapshot`
- `pyproject.toml [tool.pytest.ini_options].markers` `live` marker — declared в Phase 7, unused; Phase 9 finally wires up (per ARCH §B)
- `.planning/spikes/v1.1-brand-name-shapes/MEMO.md` shape-table — TH-04 brand-coverage canary читает active brand list отсюда

### Established Patterns
- **Pipe-and-filter monolith** (parser → normalizer → storage → matcher → reporter → delivery): Phase 9 трогает ТОЛЬКО storage boundary (Pydantic schema injection at `SqliteSnapshotWriter.persist`); contracts upstream/downstream preserved
- **Append-only retailer-grouped fixtures** (`tests/fixtures/<retailer>/`, НЕ `tests/fixtures/live/`): per ARCHITECTURE.md §B and Phase 8 D-811 — `_live-*.html` filenames carry temporal info; директория остаётся retailer-grouped
- **Atomic stats patch** (Phase 2 D-211, Phase 6 D-616 MainRunResult): `schema_rejected_count` + `schema_rejected_rate` — single atomic `patch_stats` after SqliteSnapshotWriter.persist completes
- **TDD discipline RED+GREEN атомарные commit pairs** (Phase 8 D-811): тест против `_live-*.html` ДО production code; per-plan атомарные commits
- **Sub-spike-and-wrap-up-skill convention** (Phase 1 + Phase 8): уже два прецедента; Phase 9 не нуждается в новом spike (артефакты Phase 8 evidence-sufficient)
- **Plan-wave parallelization** (Phase 8 W1 = 3 parallel plans on different files): Phase 9 09-02 W1 = 2 parallel plans (TH-03 пишет в `tests/live/`, TH-06 пишет в `src/ga_crawler/storage/`)
- **Operator-runbook RU-primary README sections** (Phase 7 §3 + Phase 8 deferred): новый README §8 «Live HTML harness» follows same RU-primary patterns

### Integration Points
- `parsers/dispatcher.py:51` `asdict(GoldappleRawProduct)` dispatcher dict shape → Pydantic schemas зеркалят это dict shape (additive, no change to dispatcher)
- `storage/SqliteSnapshotWriter.persist` (точное имя метода планнер уточнит при инспекции) → injection point для `RawProduct.model_validate(row)` ДО SQL INSERT
- `runner/gates.py` → `schema_rejected_rate_gate` ставится ПОСЛЕ `persist` complete, ДО `null_rate_gate` (D-815/D-817 Phase 8) — cascade catches schema-violation раньше null-rate
- `runner/stats.py` → новые keys: `schema_rejected_count: int`, `schema_rejected_rate: float`, `schema_rejected_reasons: list[dict]` (per-SKU diagnostic для drift output)
- `tests/conftest.py` `goldapple_pdp_html` / `viled_pdp_html` loaders → wrapped через `_assert_fixture_clean(path)` (D-907 fixture-loader integration)
- `pyproject.toml [dependency-groups].dev` → новая зависимость `syrupy>=4.7,<5.0`
- README §8 (new) — operator runbook для `pytest -m live` и `pytest -m live --refresh-live`

</code_context>

<specifics>
## Specific Ideas

- **Two-mode drift test default = cassette-replay:** мотивация — operator должен иметь возможность запустить `pytest -m live` за секунды без Camoufox launch overhead для quick pre-deploy sanity check. `--refresh-live` flag = explicit operator decision когда тратить 30+s на actual live re-fetch.
- **`schema_rejected_rate > 5%` threshold:** аналог PARSE-FIX-04's 50% absolute null-rate — но 5% потому что schema violations это **structural** drift (parser выдаёт wrong shape), а null-rate ловит **content** drift (parser выдаёт NULL fields). Schema violations должны быть rare-or-zero в нормальном run; 5% = catch-early threshold.
- **Per-retailer Pydantic schema split (D-904) evidence:** viled run #13 BUG-FINDINGS показал что Contre-Jour и Wild Vetiver легитимно не имеют volume в `attributes[].name == "Размер"` JSON. Strict NonEmptyStr для viled volume_raw → false-positive rejections + run-fail на legitimate data → ops alert burst. Per-retailer split = correctness, не over-engineering.
- **PII canary fail-stack:** при detect cf_clearance / bot token / UUID hc-ping path в fixture, pytest fails с **path к фикстуре + matched substring** (НЕ полный content) — operator знает что почистить без leak of accidentally-captured secret в pytest stdout.
- **Stale fixture warning threshold 30 days:** соответствует «if fixture older than monthly cron interval — refresh suspected». Phase 11 weekly cron + Phase 9 operator-monthly-refresh assumption.

</specifics>

<deferred>
## Deferred Ideas

- **Auto-scheduled live-drift cron** (weekly refresh job + ops-chat diff alert per PITFALLS #2) — v1.2 if operator request'нет после Phase 11 production observations. Phase 9 v1.1 ships operator-only opt-in (D-905) чтобы избежать extending cron blast radius до production stability.
- **GitHub Action CI live-tests workflow** — v1.2; нужен self-hosted runner (Camoufox + KZ-IP requirement). Sceptical premise: GHA EU-IP runners ломают geo-fakes Phase 7 setup.
- **`@pytest.mark.flaky` ban grep canary** (per PITFALLS #4) — v1.2; не нужен пока в `tests/live/` нет ни одного flake-decorated test'а. Premature enforcement.
- **`parser-drift-YYYY-MM-DD.md` auto-classifier** (LLM-driven diff categorizer) — v2 / out of v1.1 scope. v1.1 = plain markdown diagnostic, operator читает.
- **Match-rate floor alert** (упомянутый в SUMMARY.md как "A5") — не в v1.1 reqs roster; defer как v2 backlog item если operator пожалуется на silent low-match-rate runs после Phase 11 deploy. Same deferred line as Phase 8 CONTEXT.md.
- **viled volume null-rate gate** (companion к Phase 8 PARSE-FIX-04 для viled) — оставляем deferred per Phase 8 CONTEXT.md `<deferred>`. v1.2 если post-deploy evidence покажет необходимость.
- **Cassette refresh cron entry** (separate from weekly-run.sh, e.g. Saturday 20:00 Almaty) — D-905 rejected for v1.1; reconsider в v1.2 если operator monthly-refresh discipline проседает.

</deferred>

---

*Phase: 9-Live-HTML Harness*
*Context gathered: 2026-05-14*
