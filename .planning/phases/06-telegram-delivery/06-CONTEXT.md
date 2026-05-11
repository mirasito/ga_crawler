# Phase 6: Telegram Delivery + Ops/Business Split - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 — **тонкий delivery-wrapper** над Phase 5: читает `runs.stats.report.{summary_text, xlsx_path, size_guard_passed}` + `runs.status` из БД и роутит результат в один из двух Telegram-чатов через `aiogram` SDK. Phase 6 **никогда не регенерирует** summary (D-514 source-of-truth cascade), **никогда не пересчитывает** KPI (D-405), **никогда не падает на отказе Telegram** (отчёт остаётся на диске + delivery_status=undelivered). Pre-send sanity-gate (DELIVER-03) композирует 4 проверки (`runs.status=='success'` / `xlsx_path` непустой / `size_guard_passed=true` / `summary_text` непустой) — первый fail определяет ops-only branch с причиной. ENV-конфиг (DELIVER-05): три обязательных переменных (`TG_BOT_TOKEN` + `TG_BUSINESS_CHAT_ID` + `TG_OPS_CHAT_ID`) через `python-dotenv`. Retry-policy (DELIVER-04): tenacity 3-retry с backoff 5/15/45s + явный respect `TelegramRetryAfter.retry_after`; total budget ≤ 75s + retry-after. Idempotency через `runs.stats.deliver.delivery_status` enum — `deliver-run --run-id N` повторно безопасен. Phase 6 **НЕ** меняет схему `runs`/`snapshots`/`matches`/`reporter`-модули (frozen Phase 2..5), **НЕ** деплоит cron (Phase 7), **НЕ** добавляет ничего, кроме `deliver.*` keys в `runs.stats`.

</domain>

<decisions>
## Implementation Decisions

### SDK + sync/async integration (DELIVER-01 + composition)

- **D-601:** **aiogram 3.27.x как Telegram SDK.** CLAUDE.md §Stack уже зафиксирован; aiogram v3 — async-native (consistent с goldapple async fetcher pattern), полный type-hinting, встроенная обработка `TelegramRetryAfter` exception с `.retry_after` атрибутом, FSInputFile для xlsx-вложений, `parse_mode=HTML` через `DefaultBotProperties`. Альтернативы отвергнуты: python-telegram-bot 22 (второй толстый dep вместо aiogram); raw httpx (теряем retry-after parsing + multipart manual + 30 LOC ergonomic loss). Pin: `aiogram>=3.27,<4.0` (v4.x пока preview).

- **D-602:** **Sync `runners/delivery_run.py` оборачивает `asyncio.run(_send_delivery(...))`** — mirror `main_run.py:224` goldapple pattern (`g_result = asyncio.run(run_goldapple_phase(...))`). Внутри `_send_delivery` создаётся `Bot(token, default=DefaultBotProperties(parse_mode="HTML"))` через `async with Bot(...) as bot:` (aiogram 3.x context manager закрывает session автоматически). Внешний sync интерфейс держит `main_run.run_weekly` единым sync-pipeline'ом и тестируемым через subprocess.

- **D-603:** **Retry policy — tenacity 3-retry с явным respect retry-after.** Каждая send-операция (`send_message` для caption/ops-alert + `send_document` для xlsx) wrapped в:
  ```python
  @retry(
      retry=retry_if_exception_type((TelegramNetworkError, TelegramServerError)),
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=5, min=5, max=45),  # 5/15/45 backoff
      reraise=True,
  )
  ```
  `TelegramRetryAfter` обрабатывается **отдельно** (не в `retry_if_exception_type`): catch → `await asyncio.sleep(exc.retry_after)` → retry counter увеличивается. Общий budget ≤ 75s (5+15+45+ramp) + max single retry-after wait (Telegram обычно ≤ 30s). После 3 retry → `TelegramNetworkError` пробрасывается наружу, `deliver-run` помечает `delivery_status=undelivered_telegram_unreachable`. Mirror viled fetcher tenacity pattern (Plan 02-04).

### Pre-send gate composition + run-status policy (DELIVER-03 + cascade)

- **D-604:** **Pre-send gate = композиция 4 проверок, first-fail-wins.** Реализация в `delivery/gate.py::evaluate_gate(engine, run_id) -> GateDecision`:
  1. `runs.status == 'success'` — REUSE `matcher.strict_key.read_run_status` (D-507/D-411 mirror). Fail-reason: `"upstream_status_{status}"` (e.g. `upstream_status_failed`, `upstream_status_running`).
  2. `runs.stats.report.xlsx_path` непустой — защита от Plan 05-05 caveat (no-reporter path default size_guard_passed=True misleads). Fail-reason: `"no_xlsx_in_stats"`.
  3. `runs.stats.report.size_guard_passed == True` (D-515 cascade — НЕ NEGOTIABLE). Fail-reason: `"xlsx_oversize"`.
  4. `runs.stats.report.summary_text` непустой. Fail-reason: `"empty_summary_text"`.

  `GateDecision` dataclass возвращает `route: Literal["business", "ops_only"]` + `gate_failed_check: str | None` + `gate_failure_reason: str | None`. Все 4 проверки независимы — функция short-circuits на первой fail. Результат → ветка `route_to_business` (полный flow) или `route_to_ops_only` (alert template).

- **D-605:** **Delivery failure НЕ flagipает `runs.status` на 'failed'.** ARCHITECTURE.md «reporter independent of delivery» extends: «delivery independent of run-correctness». Если Telegram unreachable → `runs.status` остаётся `success`, `runs.stats.deliver.delivery_status='undelivered_telegram_unreachable'`, xlsx на диске для manual recovery через `deliver-run --run-id N`. **Исключение:** uncaught exception внутри delivery (config error, programmer bug) → outer try/except в `main_run.run_weekly` (DATA-05 Plan 02-05 invariant) → `run_writer.fail(traceback)` → `runs.status='failed'`. То есть «нормальный Telegram outage» не fail, «программный bug в delivery» — fail. Phase 7 Healthchecks.io + dead-man's switch ловит cron-failure (когда runs.status='failed') И undelivered (когда runs.status='success' но delivery_status='undelivered_*' — через отдельный health-probe). Cascade в Phase 7.

### Idempotency + delivered-state persistence (DELIVER-04 recovery)

- **D-606:** **`runs.stats.deliver.delivery_status` enum — 6 значений, mirror D-514 7-key namespace discipline.** Полный enum (исчерпывающий, Pitfall 4 sentinel "" rejected):
  - `pending` — после `runs.create()`, до первой delivery попытки. Default value (НЕ "" sentinel) — Phase 6 явно патчит на старте `run_delivery_phase`.
  - `delivered_business` — успешный send в business chat (caption text + xlsx document); `business_message_id` + `business_document_message_id` запатчены.
  - `delivered_ops_only` — pre-send gate trip → alert в ops chat (НЕ в business); `ops_message_id` запатчен.
  - `undelivered_telegram_unreachable` — после 3 tenacity retry все попытки (любого chat) упали с `TelegramNetworkError`/`TelegramServerError`; xlsx на диске остаётся, manual recovery через `deliver-run --run-id N` (D-608).
  - `skipped_no_credentials` — критичная ENV-переменная отсутствует (`TG_BOT_TOKEN`); bot невозможно инициализировать; structured-log error + non-zero CLI exit. Phase 7 Healthchecks fail-ping ловит.
  - `skipped_already_delivered` — idempotency: `deliver-run --run-id N` для run где `delivery_status='delivered_business'`; no-op + log; `--force` flag overrides (D-608).

- **D-607:** **`deliver.*` stats namespace — 8 keys (mirror D-514 discipline + Pitfall 4 sentinels).** В `delivery/stats.py::DeliverStatsBuilder`:
  - `deliver.delivery_status` — str (enum D-606)
  - `deliver.route` — str: `"business" | "ops_only" | "skipped" | ""` (`""` sentinel = pre-Phase-6 runs)
  - `deliver.business_caption_message_id` — int (Telegram-returned `message_id`); `-1` sentinel когда не отправлялось
  - `deliver.business_document_message_id` — int; `-1` sentinel
  - `deliver.ops_message_id` — int; `-1` sentinel
  - `deliver.attempt_count` — int (incremented per send-call attempt, cumulative across retries)
  - `deliver.last_error` — str (short truncated error message, "" sentinel)
  - `deliver.delivered_at` — str (ISO 8601 UTC timestamp, "" sentinel)

  Все 8 keys пишутся через **single atomic `patch_stats`** call (Pitfall 6 invariant). На skip path тоже single call. Тесты canary: `test_delivery_stats_namespace_keys_count`, `test_namespace_disjoint_invariant` (viled ∩ goldapple ∩ match ∩ report ∩ deliver = ∅).

- **D-608:** **CLI `deliver-run --run-id N [--force] [--dry-run] [--db-path PATH] [--pyproject PATH]`** — mirror D-412/D-509 shape. Поведение по `delivery_status`:
  - `pending` → run full delivery
  - `delivered_business` → no-op + `skipped_no_op` log; `--force` overrides и пересылает (operator может re-validate доставку после Telegram restore)
  - `delivered_ops_only` → re-send to ops chat (ops chat — для debug/alerts, дубли допустимы)
  - `undelivered_telegram_unreachable` → re-attempt full delivery (это primary recovery scenario)
  - `skipped_no_credentials` → re-validate ENV, full delivery если ENV теперь present
  - `skipped_already_delivered` → idem `delivered_business` (no-op + `--force`)

  `--dry-run`: builds gate decision + builds caption/alert text + routing decision → prints to stdout, **НЕ** вызывает Telegram API. Phase 7 cron не использует `--dry-run`, но операторы могут тестировать. Mirror Phase 4 `matcher-run` + Phase 5 `report-run` argparse shape.

### Ops alert content + format + ENV-edge cases (DELIVER-02 + DELIVER-05)

- **D-609:** **`parse_mode=HTML` (не MarkdownV2).** MarkdownV2 требует escape 16 спецсимволов (`_*[]()~\`>#+-=|{}.!`) в динамических полях (run_id может быть OK, но `reason` строка / `error` traceback легко содержат backticks или dots). HTML — escape только `<>&` через `html.escape()`. Allowed tags в Telegram HTML mode: `<b>`, `<i>`, `<code>`, `<pre>`, `<a href>`. Бизнес-caption не требует форматирования (summary_text plain emoji), но `parse_mode=HTML` для бота единый, не switch per-message.

- **D-610:** **Один ops-template с reason-field, НЕ per-reason templates** (DRY). Скелет в `delivery/message_builder.py::build_ops_alert`:
  ```html
  🚨 <b>Weekly run #{run_id}</b> — {reason_short}

  <i>Run started:</i> {started_at_almaty}
  <i>Run status:</i> <code>{runs.status}</code>
  <i>Gate failure:</i> <code>{gate_failed_check}</code>

  <i>Snapshot stats:</i>
    viled: {viled_count} • goldapple: {goldapple_count}
    matches: {match_count} ({match_rate}%)
  {if size_guard_failed:}
    xlsx size: {xlsx_size_mb} MB (limit: {size_limit_mb} MB)
  {endif}

  {if error_short:}<i>Error:</i> <pre>{error_truncated_3500}</pre>{endif}

  <i>Manual recovery:</i> <code>python -m ga_crawler deliver-run --run-id {run_id}</code>
  ```
  `error_truncated_3500` — truncate traceback до 3500 chars (Telegram 4096-char message limit minus HTML tags overhead). `reason_short` derived from `gate_failed_check` per dict mapping (e.g., `"upstream_status_failed"` → `"upstream pipeline failed"`, `"xlsx_oversize"` → `"xlsx too large for Telegram"`, `"empty_summary_text"` → `"missing report summary"`). Один template covers все 4 gate-fail причины + delivery-exception-fallback.

- **D-611:** **ENV-loading через `python-dotenv` (уже в deps) + `os.getenv`.** В `delivery/config.py::DeliverConfig.from_env`:
  - `TG_BOT_TOKEN` — required. Отсутствует → `delivery_status=skipped_no_credentials` + structlog error + CLI exit code 3. **Без TG_BOT_TOKEN ни одной alert не отправить** (CLAUDE.md «fail-loud crash logged to disk»).
  - `TG_BUSINESS_CHAT_ID` — required для business route. Отсутствует но `TG_OPS_CHAT_ID` present И gate-decision route был бы `business` → ops alert «config error: TG_BUSINESS_CHAT_ID missing for run #N» + `delivery_status=delivered_ops_only` + `gate_failure_reason='missing_env_TG_BUSINESS_CHAT_ID'`. Если gate уже route=ops_only — продолжаем нормально.
  - `TG_OPS_CHAT_ID` — required для ops route. Отсутствует но `TG_BUSINESS_CHAT_ID` present И gate-decision route=business → log warning + продолжаем business-only (ops alerts невозможны, но business send безопасен). Если gate route=ops_only → `delivery_status=skipped_no_credentials` + log + CLI exit code 3.

  **Validation order:** parse ENV → validate TG_BOT_TOKEN required → gate-decision → validate route-specific chat_id presence. Phase 7 README документирует все 3 ENV как required для production cron.

- **D-612:** **`.env.example` коммитится; `.env` в `.gitignore`.** Mirror Phase 1 spike `.env.local` pattern (но spike .gitignore — отдельный). Phase 6 ships `.env.example` в repo root:
  ```env
  # Telegram delivery (Phase 6 — DELIVER-05)
  TG_BOT_TOKEN=
  TG_BUSINESS_CHAT_ID=
  TG_OPS_CHAT_ID=
  ```
  `.gitignore` дополняется `.env` (если ещё не было — проверить в Plan 06-XX Wave 0). Документация в README (Phase 7 SCHED-05) объясняет создание бота через @BotFather + получение chat_id через @userinfobot.

### Module structure + composition + pyproject namespace

- **D-613:** **Module layout — `delivery/` package + `runners/delivery_run.py`.** Mirror D-413/D-513:
  ```
  src/ga_crawler/
    delivery/
      __init__.py
      config.py          # DeliverConfig.from_env + .from_pyproject (D-611 + D-614)
      telegram_client.py # aiogram Bot wrapper + tenacity retry policy (D-601 + D-603)
      message_builder.py # build_ops_alert (D-610) + business_caption = report.summary_text verbatim (D-514)
      gate.py            # PreSendGate.evaluate_gate (D-604) returning GateDecision
      stats.py           # DeliverStatsBuilder (D-607) mirror ReportStatsBuilder
    runners/
      delivery_run.py    # sync orchestrator: ENV-validate → gate → asyncio.run(send) → patch_stats (D-602 + D-606)
      main_run.py        # AMEND: add run_delivery_phase step after reporter step (D-615)
  ```
  Phase 5 reporter package НЕ затрагивается. `runner/stats.py::StatsNamespaceError` reused. `matcher.strict_key.read_run_status` reused в `delivery/gate.py` (D-604 step 1).

- **D-614:** **`[tool.ga_crawler.deliver]` pyproject namespace — minimal:**
  ```toml
  [tool.ga_crawler.deliver]
  retry_max_attempts = 3                # D-603 tenacity stop_after_attempt
  retry_backoff_min_seconds = 5         # D-603 wait_exponential min
  retry_backoff_max_seconds = 45        # D-603 wait_exponential max
  ops_message_truncate_chars = 3500     # D-610 traceback truncation (safe under 4096 TG limit)
  business_caption_max_chars = 1024     # Telegram document caption hard-limit
  parse_mode = "HTML"                   # D-609
  ```
  `DeliverConfig.from_pyproject` loader mirrors `ReportConfig.from_pyproject` (Plan 05-01). ENV vars (D-611) loaded separately в `.from_env` — НЕ через pyproject (секреты НЕ в git).

- **D-615:** **`main_run.run_weekly` composition — delivery step ПОСЛЕ reporter step, ПЕРЕД final finalize.** Pipeline:
  ```
  runs.create()
    → run_viled_phase()
    → run_goldapple_phase()
    → Norm06Writer.persist()
    → run_writer.finalize('success')       # pre-finalize per Plan 04-05
    → run_matcher_phase()                  # D-411 skip-protocol inside
    → run_reporter_phase()                 # D-507 skip-protocol inside
    → run_delivery_phase()                 # NEW — D-604 gate inside; D-605 never-fails-run
    → run_writer.finalize('success')       # idempotent re-finalize per Plan 04-05
  ```
  Explicit gate в `main_run` mirror Plan 05-05 pattern: `if r_result.status == "success" and r_result.xlsx_path:` → run_delivery_phase. Если reporter был skipped (no xlsx) → delivery тоже skip (нечего слать); patch `deliver.delivery_status='skipped_no_xlsx'` + `route="skipped"`. Pre-init outcome vars (`delivery_status`/`route`/...) выше try block для всех failure-return paths.

- **D-616:** **`MainRunResult` gets 2 new fields:** `delivery_status: str = "pending"` + `delivery_route: str = ""`. Phase 7 cron / Healthchecks integration читает эти поля через CLI stdout JSON для health-pings. Mirror Plan 05-05 D-514 field addition.

### Claude's Discretion

- **Business caption length handling:** Если `summary_text` > 1024 chars (Telegram caption limit) — split: send `send_message(business_chat, summary_text, parse_mode=None)` FIRST (4096 char limit, summary plain emoji ASCII fits легко), THEN `send_document(business_chat, FSInputFile(xlsx), caption="См. сводку выше")`. Plan checks summary_text length в `delivery_run.py` step 5. Edge case в production маловероятен (D-504 template + top-3 deltas ~500 chars typical), но защита от 50-brand summary в v2.
- **HTML escaping:** `html.escape(value)` для всех динамических полей в ops-alert template (run_id integer OK, но `reason` строка / `error` traceback легко содержит `<` `>` `&`). aiogram сам НЕ escape — обязанность сборщика.
- **Dry-run output format:** `{"route": "business", "gate_decision": "...", "business_caption": "<truncated>", "ops_alert": null}` JSON to stdout. Reuse Plan 05-05 Unicode-stdout pattern (`sys.stdout.buffer.write(payload.encode('utf-8'))`) для emoji-safe output на Windows.
- **`business_message_id` semantics:** `send_message` возвращает `Message` object с `message_id`; запатчить как `business_caption_message_id` (caption text message) + `business_document_message_id` (xlsx document message — отдельный Telegram message). Phase 7 cron может pin / unpin сообщения через эти ID если потребуется.
- **Mock Bot для тестов:** через `pytest-mock` мокать `aiogram.Bot.send_message` + `send_document` напрямую; respx НЕ подходит (aiogram использует internal aiohttp session, не httpx). E2E test через `delivery/telegram_client.py::send` с monkeypatched Bot class. Synthetic run fixture mirror Plan 05-04 `synthetic_report_run`.
- **Test secrets:** `tests/conftest.py` экспортирует `mock_tg_bot_token=os.environ.get("TG_BOT_TOKEN", "test-token-12345")` + `mock_tg_business_chat_id="-100000001"` + `mock_tg_ops_chat_id="-100000002"`. Real `.env` не загружается в test path — `python-dotenv` вызывается только из `cli.py::_cmd_deliver` startup.
- **Skip-no-xlsx semantics:** Если reporter ranen но gate-tripped (status not 'success'), `xlsx_path` всё равно может быть пустым (reporter skip-path D-507 пишет `xlsx_path=""`). Delivery gate check #2 `xlsx_path non-empty` поймает это → route=ops_only с reason `"no_xlsx_in_stats"`. Эквивалентно ops alert «upstream failed before reporter». Один path covers оба сценария.
- **Idempotent re-finalize after delivery:** delivery НЕ зовёт `run_writer.finalize()` — runs row уже success per Plan 04-05 pre-finalize. Outer `main_run.run_weekly` зовёт `finalize` повторно (no-op via `WHERE status='running'` guard).
- **No alembic migration:** Phase 6 не меняет схему `runs`/`snapshots`/`matches`. Только новый `deliver.*` namespace в `runs.stats` JSON column — append-only via `patch_stats`. D-220 invariant preserved.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — core value (weekly viled vs goldapple report для commercial team), §Delivery channel = Telegram + Excel
- `.planning/REQUIREMENTS.md` §Deliver (DELIVER-01..05 active), §Report (REPORT-06 D-515 cascade — `report.size_guard_passed` flag в `runs.stats` входит в pre-send gate)
- `.planning/ROADMAP.md` §"Phase 6: Telegram Delivery + Ops/Business Split" — phase goal + 4 success criteria (SC#1..4)

### Prior phase context (decisions cascade)
- `.planning/phases/05-reporter-excel-summary/05-CONTEXT.md` — Phase 5 frozen: **D-514 reporter source-of-truth for caption** (Phase 6 D-601 reads verbatim, no regenerate); **D-515 size-guard cascade** (Phase 6 D-604 gate check #3); D-507 status-gate skip-protocol (Phase 6 D-604 gate check #1 mirror); D-509 standalone CLI subcommand (Phase 6 D-608 mirror with `deliver-run`); D-513 reporter/ package split (Phase 6 D-613 mirrors with `delivery/`); D-514 stats namespace 7-key discipline (Phase 6 D-607 mirrors with `deliver.*` 8-key); D-516 pyproject namespace pattern (Phase 6 D-614 mirrors with `[tool.ga_crawler.deliver]`)
- `.planning/phases/04-matcher-match-rate-kpi/04-CONTEXT.md` — Phase 4 frozen: D-405 KPI formula frozen (Phase 6 cites `runs.stats.match.rate` через summary_text verbatim, no recompute); D-411 skip-protocol pattern + `read_run_status` helper (Phase 6 D-604 gate check #1 REUSES); D-412 standalone `matcher-run` CLI (Phase 6 D-608 mirror); D-413 matcher/ package split (Phase 6 D-613 mirrors); D-414 stats namespace (Phase 6 D-607 mirrors)
- `.planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT.md` — Phase 2 frozen: DATA-05 try/except outer wrapper (Phase 6 D-605 inherits — delivery exception → main_run.fail); Plan 02-04 tenacity 3-retry pattern (Phase 6 D-603 mirrors with TG-specific exception types); patch_stats atomic merge invariant Pitfall 6 (Phase 6 D-607 single-call patch); D-220 no-alembic (Phase 6 inherits — append-only `deliver.*` keys)
- `.planning/phases/01-goldapple-reconnaissance-spike/MEMO.md` — Phase 1 spike close-out: Tier 2 Camoufox + KZ-laptop locked. Phase 6 inherits **Hetzner CX22 EU + Camoufox** hosting recommendation from STATE.md Accumulated Key Decisions — Phase 7 ops territory; Phase 6 itself host-agnostic (Telegram Bot API доступен с любой IP).

### Research foundation
- `.planning/research/ARCHITECTURE.md` §"Key boundary principle" — Crawler/Parser/Normalizer/Matcher = pure pipelines; Storage/Reporter/Delivery = side-effects ONLY. Phase 6 = delivery side-effect layer. **«Reporter independent of delivery»** invariant (Phase 5 D-507/D-515 anchor) — Phase 6 inherits inverted: «Delivery never fails reporter's product» (xlsx persists на диске независимо от Telegram success/fail).
- `.planning/research/PITFALLS.md` — Pitfall 6 atomic `patch_stats` (D-607 reuses); Pitfall 4 None-rejection sentinels — `deliver.*` keys use `""` для str, `-1` для int sentinels.
- `.planning/research/STACK.md` (если есть) или CLAUDE.md §Telegram Delivery — **aiogram 3.27** locked, **python-telegram-bot 22 rejected**, raw httpx rejected.

### Frozen infrastructure (Phase 6 inputs — READ-ONLY)
- `src/ga_crawler/storage/sqlite.py` — `SqliteRunWriter.patch_stats(run_id, delta)` atomic json_patch (Phase 6 calls для `deliver.*` keys); `Run.stats` JSON column reads `runs.stats.report.{summary_text, xlsx_path, size_guard_passed}` + `runs.stats.match.*` через `get_stats(run_id)`.
- `src/ga_crawler/matcher/strict_key.py::read_run_status(engine, run_id)` — D-411 helper, **REUSED** в `delivery/gate.py::evaluate_gate` step 1 (D-604).
- `src/ga_crawler/reporter/archive.py` — Phase 5 frozen; Phase 6 reads `report.xlsx_path` из stats + opens via `FSInputFile(Path(repo_root) / xlsx_path)`. Path-traversal containment был валидирован в `reporter_run.py` Step 6 (Plan 05-04), Phase 6 наследует доверие (re-check защитный в `delivery_run.py` всё же — defense-in-depth).
- `src/ga_crawler/runner/stats.py::StatsNamespaceError` — Phase 6 `DeliverStatsBuilder` использует общий error class (Phase 4/5 pattern).
- `src/ga_crawler/runners/main_run.py` — current orchestrator (viled + goldapple + matcher + reporter); Phase 6 amend через `run_delivery_phase` после reporter per D-615. Pre-init pattern (Plan 05-05) extended с `delivery_status` + `delivery_route`.
- `src/ga_crawler/cli.py` — current 4 subcommands (`goldapple-smoke`, `weekly-run`, `matcher-run`, `report-run`); Phase 6 amends добавлением `deliver-run --run-id N` per D-608.
- `pyproject.toml` — current namespaces `[tool.ga_crawler.crawl.{retailer}]` + `[tool.ga_crawler.match]` + `[tool.ga_crawler.report]`; Phase 6 adds `[tool.ga_crawler.deliver]` per D-614. New dep: `aiogram>=3.27,<4.0`.

### Test infrastructure (inherited)
- `tests/conftest.py` — Phase 6 adds `synthetic_delivered_run` (Run с report.* stats populated для gate-pass + gate-fail сценариев) + `mock_aiogram_bot` (returns Message objects with stub message_id) + `mock_tg_env` (sets/unsets ENV vars per test).
- `tests/integration/` — pattern Plan 05-04: real on-disk SQLite + real `delivery_run.py` call + mock Bot.send_*; assert `runs.stats.deliver.*` keys patched correctly.

### Project conventions
- `CLAUDE.md` §Telegram Delivery — aiogram 3.27 locked; §Anti-Bot Strategy не применимо к Telegram Bot API (это own API, не scraping); §Environment Variables pattern (python-dotenv already in deps).

### Project state & accumulated decisions
- `.planning/STATE.md` §"Accumulated Key Decisions":
  - «Reporter is independent of delivery» (Phase 6 D-605 inherits inverted form: delivery_status decoupled от runs.status; delivery failure → runs.status='success' continues, ops alerts via Healthchecks Phase 7).
  - «Two Telegram chats (ops vs business)» (Phase 6 D-604 gate routes; D-606 enum reflects);
  - **D-514 reporter source-of-truth for Telegram caption** — Phase 6 D-601 verbatim consume; tests MUST canary «no Telegram bot module imports summary_builder» structurally.
  - **D-515 size-guard delivery cascade** — Phase 6 D-604 gate check #3; oversize → ops chat «manual delivery required».
  - **D-405 KPI verbatim** — Phase 6 inherits via summary_text content (reporter уже cite-ed); no separate KPI handling в delivery layer.
  - **Plan 02-05 DATA-05 lifecycle invariant** (Phase 6 D-605 follows: delivery exception within outer try/except → run_writer.fail; normal Telegram outage stays success).
  - **Plan 05-05 composition pattern** (Phase 6 D-615 mirrors: explicit gate above D-507/D-604, pre-init outcome vars, inside outer try).

### External / vendor docs
- aiogram 3.27 docs — `https://docs.aiogram.dev/en/v3.27.0/` — `Bot`, `DefaultBotProperties`, `FSInputFile`, `send_document(chat_id, document, caption, parse_mode)`, `TelegramRetryAfter`, `TelegramNetworkError`, `TelegramServerError`.
- Telegram Bot API — `https://core.telegram.org/bots/api` — `sendDocument` limits (50 MB Bot API), `sendMessage` (4096 chars), document caption (1024 chars), rate-limit (30 msg/sec global, 1 msg/sec per chat).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`storage/sqlite.py::SqliteRunWriter.patch_stats(run_id, delta)`** — atomic json_patch для `deliver.*` keys (Pitfall 6 invariant). Zero дополнительной работы.
- **`storage/sqlite.py::SqliteRunWriter.get_stats(run_id)`** — читает `runs.stats` JSON dict; Phase 6 reads `report.summary_text` + `report.xlsx_path` + `report.size_guard_passed` + `match.count` + `match.rate` через flat-dotted keys (Pitfall 6 invariant).
- **`matcher/strict_key.py::read_run_status(engine, run_id) -> str | None`** — D-411 helper; D-604 gate check #1 **REUSES** этот же function. Возвращает `'success' | 'failed' | 'running' | 'partial' | None`.
- **`runner/stats.py::StatsNamespaceError`** + 4 existing builders (`GoldappleStatsBuilder` / `ViledStatsBuilder` / `MatchStatsBuilder` / `ReportStatsBuilder`) — паттерн namespace-enforced. Phase 6 `DeliverStatsBuilder` mirrors с `deliver.` prefix (D-607).
- **`cli.py::_cmd_report` shape (Plan 05-05)** — argparse mirror для `deliver-run --run-id N` (D-608). Same `--db-path` / `--pyproject` flags; new `--force` + `--dry-run`.
- **`runners/main_run.run_weekly` composition pattern (Plan 05-05)** — pre-finalize-before-downstream-step pattern + explicit gate above D-507; pre-init outcome vars above try; Phase 6 D-615 mirrors с `delivery_status` + `delivery_route` MainRunResult fields.
- **`reporter/archive.py::write_atomic` precedent** — Phase 6 не пишет файлы, но если когда-нибудь delivery-receipt log нужен будет (Phase 7 territory), копировать паттерн.
- **`pyproject.toml [tool.ga_crawler.report]` config namespace** (Plan 05-01) — pattern для D-614 `[tool.ga_crawler.deliver]`. `ReportConfig.from_pyproject` exact shape для `DeliverConfig.from_pyproject`.
- **`python-dotenv>=1.0,<2.0`** — уже в deps (`pyproject.toml` line 21); Phase 6 D-611 reuses без upgrade.
- **`tenacity>=9.0,<10.0`** — уже в deps (line 22); Phase 6 D-603 reuses (same lib viled fetcher Plan 02-04 uses).
- **`structlog>=25.0,<26.0`** — уже в deps; Phase 6 events: `delivery_phase_start` / `delivery_gate_decision` / `telegram_send_attempt` / `telegram_retry_after` / `delivery_complete` / `delivery_undelivered`.

### Established Patterns
- **Per-domain split** (D-213 retailer-split + D-413 matcher-split + D-513 reporter-split) → Phase 6 mirrors с `delivery/` + `runners/delivery_run.py`. Симметрия 5-домен `{viled, goldapple, matcher, reporter, deliver}`.
- **Append-only `runs.stats` keys via patch_stats** (D-414/D-514): Phase 6 `deliver.*` keys append-only, single-call atomic. Pitfall 6 reused.
- **Stats namespace enforcement** (D-414/D-514): cross-namespace writes raise `StatsNamespaceError`. Tests canary `test_namespace_disjoint_invariant` extends с `deliver.*` (5-way disjoint).
- **CLI subcommands**: 4 existing `(goldapple-smoke, weekly-run, matcher-run, report-run)` → 5 with `deliver-run` (D-608).
- **DATA-05 try/except DATA-05 lifecycle** (Plan 02-05): `run_weekly` wraps body in try/except; delivery exception → `run_writer.fail()`. Plan 05-05 invariant preserved (Phase 6 = +1 step внутри того же try block).
- **Pre-init outcome vars** (Plan 05-05): MainRunResult.delivery_status default `"pending"`, delivery_route default `""` — failure-return paths emit valid result without 5-place edit.
- **`asyncio.run()` sync→async glue** (Plan 02-05 goldapple): `g_result = asyncio.run(run_goldapple_phase(...))` → Phase 6 `d_result = asyncio.run(_send_delivery_async(...))`. One nested event loop OK in sync orchestrator.
- **`from_pyproject` config loader** (Plan 04-01 + 05-01): `[tool.ga_crawler.deliver]` parsed once at startup, immutable per-run. `from_env` (D-611) separate API на тот же `DeliverConfig` class.
- **`from_env` ENV-loading pattern** — впервые в проекте, но trivial; mirror Phase 1 spike `01-08` `.env.local` load_dotenv() pattern.
- **Test mocks via tests/conftest.py** — Phase 4/5 paradigm extended: `mock_aiogram_bot` + `mock_tg_env` + `synthetic_delivered_run` fixtures.

### Integration Points
- **Input ← `runs` table**: `status` (D-604 gate check #1), `started_at` (D-610 ops-alert `started_at_almaty` formatted), `stats.report.*` (D-514 cascade), `stats.match.*` (D-405 verbatim via summary_text), `stats.viled.fetch_count` + `stats.goldapple.fetch_count` (D-610 ops-alert snapshot stats), `stats.deliver.*` (D-607 idempotency check).
- **Input ← `reports/YYYY-WNN.xlsx`** (via `runs.stats.report.xlsx_path`): open as `FSInputFile(repo_root / xlsx_path)` для `send_document`. Phase 6 НЕ генерирует path — читает persisted.
- **Input ← ENV variables**: `TG_BOT_TOKEN` + `TG_BUSINESS_CHAT_ID` + `TG_OPS_CHAT_ID` (D-611). Loaded ONCE per `deliver-run` invocation through `DeliverConfig.from_env`.
- **Input ← `pyproject.toml [tool.ga_crawler.deliver]`** (D-614 new namespace): retry config + truncate limits + parse_mode.
- **Output → Telegram Bot API**:
  - `sendMessage(business_chat_id, summary_text)` если `len(summary_text) > 1024` (Claude's Discretion split-edge)
  - `sendDocument(business_chat_id, FSInputFile(xlsx_path), caption=summary_text or "См. сводку выше")`
  - `sendMessage(ops_chat_id, ops_alert_html, parse_mode="HTML")`
- **Output → `runs.stats.deliver.*` keys** через `patch_stats` (D-607 8 keys): single atomic call per `delivery_run` invocation. Skip path тоже single call (sentinels filled).
- **Output → CLI exit codes**: 0 = `delivered_business` or `delivered_ops_only`; 2 = `undelivered_telegram_unreachable` (retryable manual recovery); 3 = `skipped_no_credentials` (config error, Phase 7 Healthchecks fail-ping).
- **Output → MainRunResult**: gains `delivery_status: str` + `delivery_route: str` fields (D-616).

### Open dependencies
- **`aiogram>=3.27,<4.0`** — НОВЫЙ dep, добавляется в Wave 0 Plan 06-XX. Не trivial: ~70 sub-deps (aiohttp + magic-filter + pydantic + etc.), но широко используется и стабилен.
- **Telegram bot setup** — operator action: создать bot через @BotFather, получить TOKEN, создать 2 чата, добавить bot, получить chat_id через @userinfobot. Phase 7 README документирует. Plan 06-XX Wave N может включать testing-bot setup для local dev.
- Phase 5 fully shipped (REPORT-01..06 closed; `report.*` 7-key namespace operational; xlsx archive working). Phase 6 unblocked.

</code_context>

<specifics>
## Specific Ideas

- **«Phase 6 — это thin wrapper, не second-source-of-truth»** (D-601 + D-514 cascade): caption = `runs.stats.report.summary_text` verbatim; KPI cited через что Phase 5 уже cited; xlsx-file from Phase 5 archive; gate logic composes Phase 4/5 helpers. Test canary: `grep -r "summary_builder" src/ga_crawler/delivery/` returns 0; same for `excel_builder`. Структурное недопускание drift.
- **«Delivery failure ≠ run failure»** (D-605): ARCHITECTURE.md «reporter independent of delivery» → расширено «delivery independent of run-status correctness». Telegram outage в воскресенье ночью → утром в понедельник оператор видит run.status=success в DB + delivery_status=undelivered в `runs.stats` + xlsx на диске → `deliver-run --run-id N` recovers. NO data loss, no manual DB intervention.
- **«One ops-template, reason-field, HTML escape»** (D-609 + D-610): DRY + safety. MarkdownV2 escape сложен; HTML — три символа (`<>&`) через `html.escape()`. Один template с placeholder для `{reason_short}` покрывает 4 gate-fail причины + exception fallback. Регрессионный тест источника templete-source-lock pattern (Plan 05-02 D-504).
- **«Idempotent CLI for recovery»** (D-608): operator scenario — Telegram outage в воскресенье 23:55 локально → cron job завершился с delivery_status=undelivered_telegram_unreachable → понедельник 09:00 оператор запускает `python -m ga_crawler deliver-run --run-id 42` → проверка enum → re-attempt → delivered_business → done. No DB surgery, no xlsx regen.
- **«ENV-fail-loud при TG_BOT_TOKEN missing, ENV-degrade при chat_id missing»** (D-611): asymmetric handling. Token = критичный (без него вообще ничего); chat_id = degradable (можно ops-only или business-only режим). Phase 7 Healthchecks ловит full-fail через exit code 3.
- **«5-domain symmetry: viled/goldapple/matcher/reporter/deliver»** (D-613): aiogram-package = пятая domain. После Phase 6 архитектура «full pipeline»: 5 domains + 1 composition (`main_run`). Phase 7 — operations layer (cron + healthchecks), не +1 domain.
- **«patch_stats single call invariant carries to Phase 6»** (D-607): все 8 `deliver.*` keys пишутся одним `patch_stats(run_id, full_delta_dict)`. Mirror D-514 7-key pattern. Hot-path test `test_delivery_single_patch_call` через MagicMock spy.

</specifics>

<deferred>
## Deferred Ideas

- **Email-channel доставки (PDF + xlsx)** — v2 (DELIVER-V2-01). Reporter уже produces xlsx; Phase 6 пишет в Telegram; новый channel = новый wrapper над тем же `runs.stats.report.*`. Не зависит от Phase 6 design — параллельно.
- **Webhook / Slack доставка** — v2. Same pattern: read from `runs.stats.report.*`, format-and-send. Phase 6 module `delivery/` уже сегрегирован, не блокирует.
- **`weekly-run --skip-delivery` flag** — отвергнуто в Phase 6 design: delivery — обязательная часть weekly pipeline (без неё нечего слать). Skip управляется через D-604 gate + D-606 `skipped_*` enum. Operator может `deliver-run --dry-run` для тестирования.
- **`weekly-run --delivery-only` flag** — отвергнуто: уже есть `deliver-run --run-id N` standalone (D-608). DRY.
- **Telegram bot self-hosted server (2 GB file limit)** — отвергнуто Phase 5 D-515 + Phase 6 D-604: oversize → ops alert manual delivery. Self-hosted server = новый infra-component (Phase 7+ territory если ever).
- **Pin / unpin Telegram messages** — out of scope; mod-action на бизнес-канале не требуется per PROJECT.md «pricing team просто смотрит еженедельные отчёты».
- **Telegram message threads / reply-to** — out of scope для v1; чаты простые group/channel.
- **Delivery audit log в отдельной таблице `deliveries`** — отвергнуто: `runs.stats.deliver.*` 8-key namespace + structlog JSON logs достаточно. Отдельная таблица = +ALTER TABLE = +alembic = +Phase complexity (D-220 invariant).
- **`deliver-run --re-summary` regenerate-then-send** — отвергнуто (D-514 invariant): summary frozen в reporter; если нужно re-summary → `report-run --run-id N` (Phase 5 D-509 уже idempotent) → `deliver-run --run-id N --force`.
- **Per-chat parse_mode override** — отвергнуто (D-609): один HTML mode для бота. Simplifies tests + template-source-lock.
- **Rich progress reporter в Telegram (status updates во время run)** — out of scope v1; weekly cron = batch job, progress не нужен (Phase 7 Healthchecks.io покрывает «alive» semantics).
- **Multi-language ops alerts (RU + EN)** — out of scope v1 per PROJECT.md «команда полностью русскоязычная»; ops alerts на русском.
- **Delivery scheduling / queuing (отдельный delivery time от run time)** — отвергнуто: cron-run + immediate delivery = simplest model; voraussetzt-задержку (e.g., рассылать утром в понедельник если cron упал ночью) реализована через cron-schedule Phase 7 (cron вечером воскресенье → результат утром понедельник через Almaty timezone).
- **Encryption / password-protected xlsx через Telegram** — out of scope; xlsx — внутренний инструмент команды viled.
- **Webhook listener mode (responding к /commands в Telegram)** — out of scope; Phase 6 = one-way send-only. Interactive bot = v2 effort.
- **Customizable summary template per-chat** — отвергнуто; D-504 single source-locked template для consistency.
- **A/B testing разных summary форматов** — out of scope; one canonical template per D-504.
- **Live integration tests против real Telegram test-bot** — отвергнуто Plan 06-XX (mirror Phase 4/5 no `-m live`): mock aiogram Bot достаточно; production smoke = первый weekly cron-run (Phase 7).

### Reviewed Todos (not folded)
`gsd-sdk query todo.match-phase 6` not available (gsd-sdk не установлен в среде); cross-reference step skipped silently per workflow.

</deferred>

---

*Phase: 6-telegram-delivery*
*Context gathered: 2026-05-12*
*Decisions: D-601..D-616 (16 decisions). 4 areas discussed; SDK + retry options confirmed by user; gate/idempotency/ops-alert auto-resolved per auto-mode following mirror-patterns from Phase 4/5 D-411/D-507/D-413/D-513/D-414/D-514 invariants.*

## Action Items for Other Documents

The following changes propagate to other artifacts at next opportunity:

- **`pyproject.toml`**: add `[tool.ga_crawler.deliver]` namespace per D-614 (retry_max_attempts + retry_backoff_min/max_seconds + ops_message_truncate_chars + business_caption_max_chars + parse_mode) + new dep `aiogram>=3.27,<4.0` — surface at Plan 06-XX Wave 0.
- **`.env.example`**: create at repo root with three `TG_*` placeholders per D-612 — surface at Plan 06-XX Wave 0.
- **`.gitignore`**: verify `.env` excluded (likely already via `.env.local` pattern from Phase 1; double-check at Plan 06-XX Wave 0).
- **`.planning/STATE.md`**: add to "Accumulated Key Decisions" — "Phase 6 delivery_status decoupled from runs.status (D-605): Telegram outage → runs.status='success' + delivery_status='undelivered_telegram_unreachable' + xlsx on disk for manual recovery via `deliver-run --run-id N`. Phase 7 Healthchecks integration ловит этот случай через `deliver.delivery_status` health-probe (НЕ через runs.status)." — surface at Phase 6 close-out (Plan 06-XX Wave 5 doc cascade).
- **`.planning/STATE.md`**: add — "Phase 6 D-606 delivery_status enum (6 values: pending / delivered_business / delivered_ops_only / undelivered_telegram_unreachable / skipped_no_credentials / skipped_already_delivered). Phase 7 cron monitoring SHALL ping Healthchecks on enum value; `delivered_business` and `delivered_ops_only` = healthy; others = unhealthy" — surface at Phase 6 close-out.
- **`.planning/REQUIREMENTS.md` DELIVER-01..05**: annotate с per-plan citation (D-601..D-616 decision IDs) at Phase 6 close-out — mirror Plan 05-06 doc cascade pattern.
- **`README.md`** (Phase 7 SCHED-05 deliverable): document создание Telegram bot через @BotFather + получение chat_id через @userinfobot + .env setup; deliberate-failure test procedure (drop bot token → cron → ops alert visible).
