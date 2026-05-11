# Phase 6 Research: Telegram Delivery

**Researched:** 2026-05-12
**Domain:** Telegram Bot API delivery wrapper (aiogram 3.27.x async) над persisted Phase 5 артефактами
**Confidence:** HIGH — все 16 локированных decisions D-601..D-616 верифицированы против aiogram 3.27 official docs (Context7 `/websites/aiogram_dev_en_v3_27_0`) + Telegram Bot API spec + existing codebase patterns

## Summary

Phase 6 — тонкий delivery-wrapper над Phase 5. CONTEXT.md (16 decisions) исключительно детализирован: SDK выбран (aiogram 3.27.x, D-601), composition pattern зеркалит Plan 02-05 + Plan 05-05 (D-602/D-615), retry policy конкретна (D-603), pre-send gate композиция из 4 проверок (D-604), idempotency через 6-value enum (D-606), 8-key stats namespace (D-607), HTML parse_mode + один ops template (D-609/D-610), ENV asymmetric handling (D-611), module layout зафиксирован (D-613), pyproject namespace minimal (D-614). Research-задача — **верифицировать**, не выбирать.

**Все ключевые API CONTEXT.md подтверждены через Context7 docs аiogram v3.27.0** (Source ID `/websites/aiogram_dev_en_v3_27_0`):
- `Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))` — корректная конструкция [VERIFIED: aiogram docs/defaults]
- `async with Bot(...) as bot:` — официально поддерживаемый context manager с `auto_close=True` по умолчанию (gracefully closes aiohttp session + 250ms SSL drain) [VERIFIED: aiogram docs/_modules/aiogram/client/bot.html]
- `FSInputFile(path: str | Path, filename: str | None = None, chunk_size: int = 65536)` — принимает pathlib.Path [VERIFIED: aiogram docs/api/upload_file.html]
- `send_document` возвращает `Message` с `message_id: int`, caption 0-1024 chars после parse [VERIFIED: aiogram docs/api/methods/send_document.html]
- `TelegramRetryAfter.retry_after: int` — **СЕКУНДЫ** (не миллисекунды), `TelegramNetworkError` / `TelegramServerError` / `TelegramBadRequest` все наследуют `TelegramAPIError` [VERIFIED: aiogram docs/_modules/aiogram/exceptions.html]

**Primary recommendation:** Реализовать ровно как описано в CONTEXT.md D-601..D-616 без отклонений. Внести в план **6 уточнений**, перечисленных в §Library Verification (caveat for `TelegramBadRequest` не в retry-list, HTML-escape через stdlib `html.escape`, ParseMode enum vs raw string `"HTML"`, tenacity `multiplier=` точное поведение, FSInputFile auto-close behavior, `bot.session.close()` явный fallback на случай отказа `async with`).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ENV loading + bot token validation | CLI/orchestrator (sync) | — | `python-dotenv` + `os.getenv` — startup-only, не runtime |
| Pre-send gate (4-check composition) | DB read layer (sync) | — | Чистая функция от `runs.stats.*` + `runs.status` — no I/O outside SQLite |
| Caption / ops-alert builder | Pure transform (sync) | — | Reads строки, возвращает строки; никаких сайд-эффектов |
| Telegram API send (`send_message` / `send_document`) | Async network layer | tenacity retry | Только здесь aiohttp session; обернуто в `async with Bot()` |
| Stats patch (`deliver.*` namespace) | DB write layer (sync) | — | Single `patch_stats` call per invocation (Pitfall 6) — выполняется ПОСЛЕ async return |
| Sync→async glue | `runners/delivery_run.py` | `asyncio.run(_send_async(...))` | Mirror Plan 02-05 goldapple pattern; main_run остаётся single sync pipeline |
| Idempotency check (delivery_status enum dispatch) | CLI command (`deliver-run`) | — | Reads enum value, decides no-op / re-attempt — pure dispatch |

**Key boundary:** только `telegram_client.py` касается aiogram. `gate.py`/`message_builder.py`/`stats.py`/`config.py` — pure sync Python, тестируемы без aiogram mocks.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DELIVER-01 | Telegram-бот отправляет business-чат: текстовая сводка + xlsx-вложение через `send_document` | aiogram 3.27 `send_document(chat_id, document=FSInputFile(...), caption=..., parse_mode=...)` returns `Message` object — verified. Caption 0-1024 chars limit — verified. Если summary_text > 1024 — split на `send_message` + `send_document(caption="См. сводку выше")` per Claude's Discretion. |
| DELIVER-02 | Отдельный ops-чат получает уведомления о падениях, sanity-gate failures, отсутствующих ENV-переменных | aiogram 3.27 `send_message(chat_id, text, parse_mode=HTML)` — 4096 char limit (D-610 ops-alert truncate 3500 leaves headroom). One template c reason-field (D-610) — НЕ per-reason templates. HTML parse_mode (D-609) — verified ParseMode.HTML enum value. |
| DELIVER-03 | Pre-send sanity-gate — composes 4 independent checks (D-604), first-fail-wins | Gate = pure function `evaluate_gate(engine, run_id) -> GateDecision`. Reuses `matcher.strict_key.read_run_status` (D-411 helper). Reads `runs.stats.report.{xlsx_path, size_guard_passed, summary_text}` через existing `get_stats(run_id)` flat-dotted keys (Pitfall 6). |
| DELIVER-04 | Retry с учётом Telegram rate-limit (`retry-after`); если Telegram unreachable — отчёт на диске + marked undelivered | tenacity `retry_if_exception_type((TelegramNetworkError, TelegramServerError))` + `wait_exponential(multiplier=5, min=5, max=45)` + `stop_after_attempt(3)` (D-603). `TelegramRetryAfter` обработать **вне** tenacity loop (catch → `asyncio.sleep(exc.retry_after)` → re-call). Final failure → `delivery_status='undelivered_telegram_unreachable'` + xlsx на диске (D-605/D-606). |
| DELIVER-05 | ENV config — TG_BOT_TOKEN / TG_BUSINESS_CHAT_ID / TG_OPS_CHAT_ID; missing → ops alert или fail-loud crash | `python-dotenv` уже в deps (pyproject line 21). Asymmetric handling (D-611): TG_BOT_TOKEN missing → `skipped_no_credentials` + exit 3; chat_id missing → degrade per-route. `.env.example` коммитится (D-612). |

## Library Verification

Все API, на которые опирается CONTEXT.md, верифицированы против aiogram 3.27.0 official docs через Context7 (`/websites/aiogram_dev_en_v3_27_0`). Несоответствий с CONTEXT.md **не найдено**. Ниже — точные подтверждения + 6 нюансов, которые планер должен учесть.

### 1. `Bot` constructor + `DefaultBotProperties` (D-601, D-609)

```python
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

bot = Bot(
    token=token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
```

**Verified:**
- `DefaultBotProperties` принимает `parse_mode` (str | None), а также `disable_notification`, `protect_content`, `allow_sending_without_reply`, `link_preview_*`. [CITED: docs.aiogram.dev/en/v3.27.0/api/defaults.html]
- ParseMode enum: `ParseMode.HTML = "HTML"`, `ParseMode.MARKDOWN_V2 = "MarkdownV2"`. CONTEXT.md D-609 говорит `parse_mode = "HTML"` — обе формы работают (enum.value == "HTML"). **Рекомендация для плана:** использовать `ParseMode.HTML` enum (типобезопасно), не raw string.

### 2. `async with Bot(...) as bot:` — auto-close session (D-602)

```python
async with Bot(token=..., default=DefaultBotProperties(parse_mode=ParseMode.HTML)) as bot:
    await bot.send_message(...)
    await bot.send_document(...)
# Session closed automatically: aiohttp ClientSession.close() + asyncio.sleep(0.25) for SSL graceful shutdown
```

**Verified:**
- Bot реализует `__aenter__` / `__aexit__`. Параметр `auto_close=True` по умолчанию — отключаемо если нужен manual control. [CITED: docs.aiogram.dev/en/v3.27.0/_modules/aiogram/client/bot.html]
- Внутри `AiohttpSession.close()` явно ждёт 250 ms для graceful SSL shutdown (избегает RuntimeWarning о незакрытом transport). [CITED: docs.aiogram.dev/en/v3.27.0/_modules/aiogram/client/session/aiohttp.html]
- **Fallback nuance:** если `async with` не используется (e.g., custom orchestrator), нужно явно `await bot.session.close()` в `finally:`. CONTEXT.md D-602 уже выбрал async-with — план должен **запретить** конструкции `bot = Bot(...)` без `async with`. Test canary: `grep -r "Bot(token" src/ga_crawler/delivery/` — каждое использование должно быть внутри `async with`.

### 3. `FSInputFile` (D-601)

```python
from aiogram.types import FSInputFile
from pathlib import Path

doc = FSInputFile(Path(repo_root) / xlsx_path, filename="weekly-report-2026-W19.xlsx")
```

**Verified:**
- Signature: `FSInputFile(path: str | Path, filename: str | None = None, chunk_size: int = 65536)`. Accepts both `str` и `pathlib.Path`. [CITED: docs.aiogram.dev/en/v3.27.0/api/upload_file.html]
- **filename parameter important:** by default aiogram parses filename из path (e.g., `2026-W19.xlsx`). Если хотим business-friendly name (`weekly-report-2026-W19.xlsx` для команды viled.kz) — передать `filename=` явно. **План должен решить:** использовать дефолт (filename из xlsx_path) или явно прокидывать `weekly-report-{iso_week}.xlsx`. Рекомендация: использовать дефолт — Phase 5 D-512 уже даёт ISO-week filename `2026-W19.xlsx` который читабелен.
- **File handle lifecycle:** `FSInputFile` использует `aiofiles.open()` внутри multipart upload и закрывает дескриптор после загрузки. Никаких file-handle leaks при условии корректного `async with Bot()` shutdown. [VERIFIED: aiogram session.close docs]

### 4. `send_document` / `send_message` return types + caption limits (D-601, D-610)

```python
msg: Message = await bot.send_document(
    chat_id=business_chat_id,
    document=FSInputFile(xlsx_path),
    caption=summary_text,  # 0-1024 chars after entities parsing
    parse_mode=ParseMode.HTML,  # inherited from DefaultBotProperties; explicit OK
)
caption_message_id = msg.message_id  # int
```

**Verified:**
- `send_document` returns `Message` object with `message_id: int` field. CONTEXT.md Claude's Discretion `business_caption_message_id` + `business_document_message_id` — корректное использование. [CITED: docs.aiogram.dev/en/v3.27.0/api/methods/send_document.html]
- `caption` lengths: **0-1024 characters after entities parsing** для всех media методов (document, voice, photo, video). [VERIFIED: aiogram docs multiple sources]
- `send_message` (для caption split-path и ops alerts): **0-4096 characters**. CONTEXT.md D-610 ops-template truncates traceback до 3500 chars — корректный запас (HTML tags overhead ≈ 400-500 chars max в template).

### 5. Exception hierarchy (D-603)

Hierarchy verified из `aiogram.exceptions` module:

```
TelegramAPIError                          # base; .method, .message attributes
├── TelegramRetryAfter                    # .retry_after: int (SECONDS, not ms)
├── TelegramMigrateToChat                 # .migrate_to_chat_id
├── TelegramBadRequest                    # 400; chat_id wrong, parse_mode error, etc.
├── TelegramNotFound                      # 404; entity missing
├── TelegramUnauthorizedError             # 401; bot token invalid
├── TelegramForbiddenError                # 403; bot kicked from chat
├── TelegramConflictError                 # bot token in use elsewhere
├── TelegramServerError                   # 5xx
└── TelegramNetworkError                  # transport-level failures
```

[CITED: docs.aiogram.dev/en/v3.27.0/_modules/aiogram/exceptions.html, docs.aiogram.dev/en/v3.27.0/dispatcher/errors.html]

**Retry classification для D-603:**

| Exception | Retry? | Action |
|-----------|--------|--------|
| `TelegramNetworkError` | YES (tenacity) | Transient transport failure |
| `TelegramServerError` (5xx) | YES (tenacity) | Telegram backend issue |
| `TelegramRetryAfter` | OUTSIDE tenacity | Honor `.retry_after` via `asyncio.sleep` then re-call |
| `TelegramBadRequest` | **NO** | Programmer error (e.g., bad chat_id format, oversized caption) — fail fast → ops alert with reason |
| `TelegramUnauthorizedError` | **NO** | Bot token revoked — `delivery_status='skipped_no_credentials'` + exit 3 |
| `TelegramForbiddenError` | **NO** | Bot removed from chat or no permission — log + `delivery_status='undelivered_telegram_unreachable'` + structlog `delivery_chat_forbidden` |
| `TelegramNotFound` | **NO** | Chat не существует (wrong chat_id в ENV) — log + `delivery_status='undelivered_telegram_unreachable'` |
| `TelegramConflictError` | **NO** | Bot конфликтует (другой polling) — fail fast (хотя в нашем pure-send-only сценарии это маловероятно) |

**ВАЖНОЕ УТОЧНЕНИЕ К ПЛАНУ (caveat #1):** CONTEXT.md D-603 не упоминает `TelegramBadRequest` / `TelegramForbiddenError` / `TelegramNotFound`. План MUST добавить **fail-fast branch** для этих 3 классов исключений: они **должны** обходить tenacity (retry не поможет) и попадать в outer try/except который пишет `delivery_status='undelivered_telegram_unreachable'` + `deliver.last_error = f"{type(e).__name__}: {e.message}"`. Это **defensive completeness**, не новое решение — D-606 enum уже покрывает.

### 6. tenacity wait_exponential behavior (D-603)

CONTEXT.md D-603 говорит `wait_exponential(multiplier=5, min=5, max=45)`. Точное поведение tenacity:

```
wait_exponential(multiplier=5, min=5, max=45):
  attempt 1 fails → wait = min(max(2^1 * 5, 5), 45) = min(max(10, 5), 45) = 10
  attempt 2 fails → wait = min(max(2^2 * 5, 5), 45) = min(max(20, 5), 45) = 20
  attempt 3 fails → reraise (stop_after_attempt(3) triggered)
```

**ВАЖНОЕ УТОЧНЕНИЕ К ПЛАНУ (caveat #2):** CONTEXT.md D-603 говорит **«5/15/45 backoff»** в комментарии. Это **НЕ соответствует** `wait_exponential(multiplier=5, min=5, max=45)`. Реальный sequence будет **10 / 20 / (no third wait — stop)** или **5 / 15 / 45** если использовать `wait_fixed([5, 15, 45])` / custom wait function. Tenacity formula: `wait = min(max(multiplier * 2^(n-1), min), max)`. Для получения 5/15/45 нужно:
- Вариант A: `wait_fixed([5, 15, 45])` — но `wait_fixed` принимает один scalar, не list.
- Вариант B: `wait_chain(*[wait_fixed(s) for s in (5, 15, 45)])` — каноничный паттерн.
- Вариант C: `wait_exponential(multiplier=5, min=5, max=45, exp_base=3)` — `5 * 3^(n-1)` = 5/15/45. **Это, вероятно, то, что нужно.**
- Вариант D: принять что-то близкое — `wait_exponential(multiplier=2.5, min=5, max=45)` даёт ≈5/10/20, или просто `wait_exponential_jitter(initial=5, max=45)` (как в viled fetcher).

**Decision for planner:** план должен **либо** уточнить точную формулу (рекомендую `wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45))` — explicit и читаемо), **либо** принять `wait_exponential_jitter(initial=5, max=45)` (mirror viled fetcher паттерна — уже используется в проекте, см. `src/ga_crawler/fetchers/viled.py:88-90`). Total budget D-603 ≤ 75s остаётся в силе либо способом.

### 7. HTML escaping (D-609 Claude's Discretion)

Два варианта:

**Вариант A — stdlib (рекомендуется):**
```python
import html
escaped = html.escape(value, quote=False)  # escapes <, >, & ; keeps " and '
```
- Telegram HTML mode принимает: `<b>`, `<i>`, `<u>`, `<s>`, `<code>`, `<pre>`, `<a href="...">`, `<tg-spoiler>`, `<tg-emoji>`. [CITED: core.telegram.org/bots/api#html-style]
- Telegram эскейпит ровно `<`, `>`, `&`. `html.escape(v, quote=False)` точно матчит.

**Вариант B — aiogram helper:**
```python
from aiogram import html as ahtml
escaped = ahtml.quote(value)  # equivalent to html.escape with html.escape semantics
```
- aiogram доступен под `aiogram.html.quote` (alias для html.escape). [CITED: docs.aiogram.dev/en/v3.27.0/utils/formatting.html showing `html.quote(message.from_user.full_name)`]
- aiogram.utils.text_decorations имеет `html_decoration.quote()` (более низкоуровневый).

**ВАЖНОЕ УТОЧНЕНИЕ К ПЛАНУ (caveat #3):** Рекомендую stdlib `html.escape(value, quote=False)` — zero дополнительной dependency surface, поведение идентично. Aiogram-helper полезен если уже импортируем `from aiogram import html` — стилистически согласованно. План должен зафиксировать одну форму и проверить через `test_message_builder_escapes_html` canary (фикстура: `error = "<script>alert(1)</script>"` → ожидаем `&lt;script&gt;`).

### 8. python-dotenv usage (D-611)

```python
from dotenv import load_dotenv

# Option A — populate os.environ (default; affects child processes)
load_dotenv(dotenv_path=".env", override=False)
token = os.getenv("TG_BOT_TOKEN")

# Option B — read into dict without polluting os.environ (better for tests)
from dotenv import dotenv_values
values = dotenv_values(".env")
token = values.get("TG_BOT_TOKEN")
```

**ВАЖНОЕ УТОЧНЕНИЕ К ПЛАНУ (caveat #4):** CONTEXT.md D-611 + Claude's Discretion «Test secrets» говорит «Real `.env` не загружается в test path — `python-dotenv` вызывается только из `cli.py::_cmd_deliver` startup». Рекомендация:
- В `cli.py::_cmd_deliver` (startup-only): `load_dotenv(override=False)` — НЕ overwrite existing env (CI/cron may set them directly).
- В `delivery/config.py::DeliverConfig.from_env`: читать **только** через `os.getenv` (так тесты могут `monkeypatch.setenv("TG_BOT_TOKEN", "...")` без файла).
- `load_dotenv()` НЕ вызывать в `from_env` — это разделение позволяет CLI решать "когда читать .env", а тесты иметь полный контроль.

Этот паттерн зеркалит Phase 1 spike `01-08` `.env.local` — uvicorn-стиль.

### 9. Telegram Bot API hard limits (D-610 truncation, REPORT-06 cascade)

[CITED: core.telegram.org/bots/api]

| Limit | Value | Phase 6 Impact |
|-------|-------|---------------|
| `sendDocument` file size | 50 MB (standard Bot API) | Phase 5 D-515 size_guard at 45 MB (5 MB safety) — already enforced |
| `sendMessage` text length | 4096 chars | D-610 truncates traceback to 3500 — leaves ~600 char headroom for HTML tags |
| `sendDocument` caption | 1024 chars | Split-path triggered if `summary_text > 1024` per Claude's Discretion |
| Rate limit per chat | 1 msg/sec same chat | One run = ≤3 sends (caption + document business OR alert ops) — well under |
| Rate limit global | 30 msgs/sec different chats | Weekly cron = ~2 calls/min — trivial |
| Rate limit bulk | 20 msgs/min sustained | Same — well under |
| `retry_after` precision | Seconds (integer) | `TelegramRetryAfter.retry_after: int` — pass directly to `asyncio.sleep` |

**Validation:** все CONTEXT.md лимиты (D-610 truncate=3500, D-614 ops_message_truncate_chars=3500, business_caption_max_chars=1024) корректны.

### 10. asyncio.run() consistency with existing main_run (D-602)

`runners/main_run.py:224` уже использует `asyncio.run(run_goldapple_phase(...))`. Phase 6 D-615 добавляет `run_delivery_phase()` после reporter. Внутри `run_delivery_phase`:

```python
def run_delivery_phase(run_id: int, ...) -> DeliveryPhaseResult:
    # ... sync setup: load config, read stats, evaluate gate, build messages ...
    result = asyncio.run(_send_delivery_async(bot_token, route, ...))  # NEW nested asyncio.run
    # ... sync teardown: patch_stats single call ...
    return DeliveryPhaseResult(...)
```

**ВАЖНОЕ УТОЧНЕНИЕ К ПЛАНУ (caveat #5):** `main_run.run_weekly` (sync) вызывает `asyncio.run(run_goldapple_phase(...))` (1-й event loop), затем после reporter step снова `asyncio.run(_send_delivery_async(...))` (2-й event loop). Это **корректно** — каждый `asyncio.run` создаёт и закрывает свой event loop. Они **не вложены** — выполняются sequentially. Pattern verified Plan 02-05 + соответствует CPython `asyncio.run` semantics. **План должен явно зафиксировать:** `run_delivery_phase` не должно быть async — это sync wrapper, как и `run_goldapple_phase` is async **внутри** одной фазы, но вызывается из sync main_run через `asyncio.run`. Symmetry preserved.

### 11. tenacity wrapping для async functions (D-603)

```python
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_chain, wait_fixed

@retry(
    retry=retry_if_exception_type((TelegramNetworkError, TelegramServerError)),
    stop=stop_after_attempt(3),
    wait=wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45)),
    reraise=True,
)
async def _send_with_retry(bot, chat_id, ...):
    return await bot.send_message(chat_id, ...)
```

**Verified:** tenacity 9.x корректно работает с `async def` — `@retry` декоратор внутренне detect coroutine functions и применяет async wrapper. [CITED: tenacity docs (existing project usage in `src/ga_crawler/fetchers/viled.py` and Phase 3 goldapple fetcher)]

Wrapping `TelegramRetryAfter` outside tenacity (как D-603 говорит):

```python
async def _send_one(bot, chat_id, ...):
    retry_after_attempts = 0
    while retry_after_attempts < 3:  # limit total retry-after loops
        try:
            return await _send_with_retry(bot, chat_id, ...)  # tenacity inside
        except TelegramRetryAfter as e:
            log.warning("telegram_retry_after", chat_id=chat_id, seconds=e.retry_after)
            await asyncio.sleep(e.retry_after)
            retry_after_attempts += 1
    raise TelegramRetryAfter(...)  # exhausted
```

**План должен:** реализовать это в `delivery/telegram_client.py::send_with_policy(bot, chat_id, action_fn, ...)` — generic wrapper, не дублировать в send_message + send_document.

## Integration Patterns

### Pattern 1: Bot lifecycle (single context manager per delivery_run invocation)

```python
async def _send_delivery_async(token, ops_chat_id, business_chat_id, ...):
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    async with bot:
        # All sends happen here. Single session reused across send_message + send_document.
        if route == "business":
            caption_msg = await send_with_policy(bot, business_chat_id, action="send_message", text=summary)
            doc_msg = await send_with_policy(bot, business_chat_id, action="send_document", doc=FSInputFile(xlsx))
            return DeliveryResult(business_caption_msg_id=caption_msg.message_id, ...)
        else:
            ops_msg = await send_with_policy(bot, ops_chat_id, action="send_message", text=ops_alert)
            return DeliveryResult(ops_message_id=ops_msg.message_id, ...)
    # async with exit → bot.session.close() → 250ms SSL drain
```

Reused aiohttp ClientSession across 2 sends per business route → 1 TCP handshake вместо 2 → ~50ms экономия (не критично, но архитектурно правильно). Mirror Phase 3 goldapple fetcher persistent_context паттерна.

### Pattern 2: Stats single-call atomic patch (D-607 + Pitfall 6)

```python
def run_delivery_phase(run_id, engine, run_writer, config) -> DeliveryPhaseResult:
    builder = DeliverStatsBuilder()
    # Pre-init ALL 8 keys to sentinels (Pitfall 4: never write null sentinels for missing data)
    builder.set("delivery_status", "pending")
    builder.set("route", "")
    builder.set("business_caption_message_id", -1)
    builder.set("business_document_message_id", -1)
    builder.set("ops_message_id", -1)
    builder.set("attempt_count", 0)
    builder.set("last_error", "")
    builder.set("delivered_at", "")

    try:
        decision = evaluate_gate(engine, run_id)
        # ... run async delivery, mutate builder ...
        builder.set("delivery_status", final_enum_value)
        builder.set("route", decision.route)
        # ... fill message_ids, attempt_count, delivered_at ...
    except Exception as e:
        builder.set("delivery_status", "undelivered_telegram_unreachable")
        builder.set("last_error", _truncate(repr(e), 500))

    # SINGLE atomic patch_stats call — Pitfall 6 invariant
    run_writer.patch_stats(run_id, builder.delta)
    return DeliveryPhaseResult(...)
```

Mirror Plan 04-04 / Plan 05-04 паттерна. Test canary `test_delivery_single_patch_call`: spy на `run_writer.patch_stats` → assert call_count == 1 (skip-path тоже).

### Pattern 3: Gate composition (D-604)

```python
@dataclass(frozen=True)
class GateDecision:
    route: Literal["business", "ops_only"]
    gate_failed_check: str | None  # None when route=business
    gate_failure_reason: str | None  # human-readable

def evaluate_gate(engine, run_id: int) -> GateDecision:
    # Check 1: runs.status
    status = read_run_status(engine, run_id)  # REUSE from matcher.strict_key
    if status != "success":
        return GateDecision(route="ops_only", gate_failed_check="run_status",
                            gate_failure_reason=f"upstream_status_{status}")
    # Check 2: xlsx_path exists in stats
    stats = engine_get_stats(engine, run_id)  # via SqliteRunWriter.get_stats(run_id)
    if not stats.get("report.xlsx_path"):
        return GateDecision(route="ops_only", gate_failed_check="xlsx_path",
                            gate_failure_reason="no_xlsx_in_stats")
    # Check 3: size_guard_passed
    if not stats.get("report.size_guard_passed", False):
        return GateDecision(route="ops_only", gate_failed_check="size_guard",
                            gate_failure_reason="xlsx_oversize")
    # Check 4: summary_text non-empty
    if not stats.get("report.summary_text", "").strip():
        return GateDecision(route="ops_only", gate_failed_check="summary_text",
                            gate_failure_reason="empty_summary_text")
    return GateDecision(route="business", gate_failed_check=None, gate_failure_reason=None)
```

**Test pattern:** 5 fixtures (1 pass + 4 fail-one-each). Verify short-circuit ordering: fail-1 must NOT compute fail-2 etc.

### Pattern 4: HTML escape in ops alert (D-610)

```python
import html as stdlib_html

def build_ops_alert(run_id, reason_short, started_at_almaty, run_status,
                    gate_failed_check, viled_count, goldapple_count, match_count,
                    match_rate, size_guard_failed, xlsx_size_mb, size_limit_mb,
                    error_short) -> str:
    parts = [
        f"🚨 <b>Weekly run #{run_id}</b> — {stdlib_html.escape(reason_short, quote=False)}",
        "",
        f"<i>Run started:</i> {stdlib_html.escape(started_at_almaty, quote=False)}",
        f"<i>Run status:</i> <code>{stdlib_html.escape(run_status, quote=False)}</code>",
        f"<i>Gate failure:</i> <code>{stdlib_html.escape(gate_failed_check or '', quote=False)}</code>",
        "",
        "<i>Snapshot stats:</i>",
        f"  viled: {viled_count} • goldapple: {goldapple_count}",
        f"  matches: {match_count} ({match_rate}%)",
    ]
    if size_guard_failed:
        parts.append(f"  xlsx size: {xlsx_size_mb} MB (limit: {size_limit_mb} MB)")
    parts.append("")
    if error_short:
        truncated = error_short[:3500]
        parts.append(f"<i>Error:</i> <pre>{stdlib_html.escape(truncated, quote=False)}</pre>")
        parts.append("")
    parts.append(f"<i>Manual recovery:</i> <code>python -m ga_crawler deliver-run --run-id {run_id}</code>")
    return "\n".join(parts)
```

**Test corpus minimum:** `tests/fixtures/delivery/ops-alert-templates.txt` golden file with 5 cases:
1. `upstream_status_failed` (matcher gate-trip)
2. `xlsx_oversize` (REPORT-06 cascade)
3. `empty_summary_text` (reporter skip)
4. `no_xlsx_in_stats` (matcher skipped → no reporter)
5. Crash fallback (uncaught exception in delivery itself)

### Pattern 5: CLI subcommand (D-608, mirror D-509 reporter)

```python
# cli.py
def _cmd_deliver(args):
    load_dotenv(override=False)  # only here, not in tests
    db_path = args.db_path
    pyproject_path = args.pyproject

    config = DeliverConfig.from_pyproject(pyproject_path)
    env_config = DeliverConfig.from_env()  # separate API

    engine = make_engine(db_path)
    run_writer = SqliteRunWriter(engine)

    # Idempotency dispatch per D-608
    existing_status = read_delivery_status(engine, args.run_id)  # NEW helper
    if existing_status == "delivered_business" and not args.force:
        log.info("skipped_already_delivered", run_id=args.run_id)
        print(json.dumps({"status": "skipped_no_op", "delivery_status": existing_status}))
        return 0

    if args.dry_run:
        # Build decision + render messages → print JSON, NO Telegram call
        decision = evaluate_gate(engine, args.run_id)
        # ... render preview ...
        print(json.dumps({"route": decision.route, "gate_decision": ..., ...}))
        return 0

    result = run_delivery_phase(args.run_id, engine, run_writer, config, env_config)
    print(json.dumps({"delivery_status": result.delivery_status, "route": result.route, ...}))
    return _exit_code_for_status(result.delivery_status)  # 0/2/3
```

Mirror Plan 05-05 `_cmd_report` shape (uses Unicode stdout pattern `sys.stdout.buffer.write(payload.encode('utf-8'))` для emoji-safe output на Windows).

## Validation Architecture

> Nyquist gate enabled (`workflow.nyquist_validation: true` in `.planning/config.json`).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (existing) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing — `asyncio_mode = "auto"`) |
| Async support | pytest-asyncio 0.24.x (already in dev deps) |
| Mocking | pytest-mock 3.14.x (already in dev deps) — `mocker.patch.object(Bot, "send_message")` |
| Quick run command | `uv run pytest tests/test_delivery_*.py tests/test_gate.py tests/test_message_builder.py -x` |
| Full suite command | `uv run pytest -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Status |
|--------|----------|-----------|-------------------|------------|
| DELIVER-01 | Successful run → business chat gets caption + xlsx | integration | `uv run pytest tests/integration/test_delivery_run.py::test_business_route_full_send -x` | ❌ Wave 0 |
| DELIVER-01 | Caption > 1024 → split into send_message + send_document with "См. сводку выше" | unit | `uv run pytest tests/test_telegram_client.py::test_caption_split_when_too_long -x` | ❌ Wave 0 |
| DELIVER-02 | Failed run → ops chat gets alert with run_id + failed phase + error | integration | `uv run pytest tests/integration/test_delivery_run.py::test_ops_route_on_run_failure -x` | ❌ Wave 0 |
| DELIVER-02 | Deliberate-failure test (SC#2 explicit) — synthetic run with `runs.status='failed'` | integration | `uv run pytest tests/integration/test_delivery_run.py::test_deliberate_failure_to_ops_only -x` | ❌ Wave 0 |
| DELIVER-03 | Gate check #1: status != 'success' → ops_only | unit | `uv run pytest tests/test_gate.py::test_gate_fails_on_run_status -x` | ❌ Wave 0 |
| DELIVER-03 | Gate check #2: xlsx_path empty → ops_only | unit | `uv run pytest tests/test_gate.py::test_gate_fails_on_no_xlsx -x` | ❌ Wave 0 |
| DELIVER-03 | Gate check #3: size_guard_passed=False → ops_only | unit | `uv run pytest tests/test_gate.py::test_gate_fails_on_size_guard -x` | ❌ Wave 0 |
| DELIVER-03 | Gate check #4: summary_text empty → ops_only | unit | `uv run pytest tests/test_gate.py::test_gate_fails_on_empty_summary -x` | ❌ Wave 0 |
| DELIVER-03 | Gate short-circuits on first fail (check #1 fail does NOT evaluate #2/#3/#4) | unit | `uv run pytest tests/test_gate.py::test_gate_short_circuits -x` (spy on db reads) | ❌ Wave 0 |
| DELIVER-04 | TelegramNetworkError → tenacity 3-retry → `undelivered_telegram_unreachable` | unit | `uv run pytest tests/test_telegram_client.py::test_network_error_exhausts_retries -x` | ❌ Wave 0 |
| DELIVER-04 | TelegramServerError → tenacity retry → eventual success | unit | `uv run pytest tests/test_telegram_client.py::test_server_error_then_success -x` | ❌ Wave 0 |
| DELIVER-04 | TelegramRetryAfter → asyncio.sleep(retry_after) → re-attempt outside tenacity | unit | `uv run pytest tests/test_telegram_client.py::test_retry_after_honored -x` | ❌ Wave 0 |
| DELIVER-04 | TelegramBadRequest → NO retry → fail fast with last_error populated | unit | `uv run pytest tests/test_telegram_client.py::test_bad_request_no_retry -x` | ❌ Wave 0 |
| DELIVER-04 | Total retry budget ≤ 75s + max(retry_after) for one chat | unit | `uv run pytest tests/test_telegram_client.py::test_total_retry_budget_bounded -x` | ❌ Wave 0 |
| DELIVER-04 | xlsx remains on disk after Telegram unreachable | integration | `uv run pytest tests/integration/test_delivery_run.py::test_xlsx_persists_on_telegram_failure -x` | ❌ Wave 0 |
| DELIVER-05 | TG_BOT_TOKEN missing → `skipped_no_credentials` + exit code 3 | integration | `uv run pytest tests/integration/test_cli_deliver.py::test_missing_token_exits_3 -x` | ❌ Wave 0 |
| DELIVER-05 | TG_BUSINESS_CHAT_ID missing on business route → ops alert with `missing_env_*` | integration | `uv run pytest tests/integration/test_cli_deliver.py::test_missing_business_chat_falls_to_ops -x` | ❌ Wave 0 |
| DELIVER-05 | TG_OPS_CHAT_ID missing on ops route → exit code 3 | integration | `uv run pytest tests/integration/test_cli_deliver.py::test_missing_ops_chat_on_ops_route_exits_3 -x` | ❌ Wave 0 |
| Cross | Stats namespace 8-keys disjoint invariant (viled ∩ goldapple ∩ match ∩ report ∩ deliver = ∅) | unit | `uv run pytest tests/test_delivery_stats.py::test_namespace_disjoint_invariant_five_way -x` | ❌ Wave 0 |
| Cross | Single atomic patch_stats call per delivery_run invocation | integration | `uv run pytest tests/integration/test_delivery_run.py::test_single_patch_stats_call -x` (spy) | ❌ Wave 0 |
| Cross | Idempotency: re-running deliver-run on `delivered_business` → no-op + no Telegram calls | integration | `uv run pytest tests/integration/test_cli_deliver.py::test_idempotent_rerun_skipped -x` | ❌ Wave 0 |
| Cross | Idempotency: re-running with `--force` overrides | integration | `uv run pytest tests/integration/test_cli_deliver.py::test_force_overrides_idempotency -x` | ❌ Wave 0 |
| Cross | Bot session closed via `async with` (no `RuntimeWarning: Unclosed client session`) | unit | `uv run pytest tests/test_telegram_client.py::test_no_unclosed_session_warning -x` (pytest-recwarn) | ❌ Wave 0 |
| Cross | Path-traversal containment on xlsx_path before FSInputFile | unit | `uv run pytest tests/test_delivery_run.py::test_xlsx_path_must_be_within_repo -x` | ❌ Wave 0 |
| Cross | HTML escape in ops alert (run_id integer OK, but reason/error contain `<>&`) | unit | `uv run pytest tests/test_message_builder.py::test_html_escape_applied -x` | ❌ Wave 0 |
| Source-lock | `grep -r "summary_builder\|excel_builder" src/ga_crawler/delivery/` returns 0 (no re-generate) | unit | `uv run pytest tests/test_delivery_structural.py::test_no_summary_builder_imports -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_delivery_*.py tests/test_gate.py tests/test_message_builder.py tests/test_telegram_client.py -x` (~3-5 sec, all unit-level)
- **Per wave merge:** `uv run pytest tests/integration/test_delivery_run.py tests/integration/test_cli_deliver.py -x` (~15-20 sec)
- **Phase gate:** `uv run pytest -x` (full suite, currently ~5-10 sec wall — 381+ existing tests before Phase 6 additions)

### Wave 0 Gaps

All new test files require Wave 0 creation:

- [ ] `tests/test_delivery_structural.py` — package layout invariants (no summary_builder/excel_builder imports per D-601 + D-514 cascade)
- [ ] `tests/test_delivery_stats.py` — DeliverStatsBuilder 8-key namespace + 5-way disjoint canary
- [ ] `tests/test_gate.py` — evaluate_gate 4 short-circuit checks
- [ ] `tests/test_message_builder.py` — build_ops_alert golden-file + html.escape behavior
- [ ] `tests/test_telegram_client.py` — send_with_policy tenacity wrapping + TelegramRetryAfter loop + exception classification
- [ ] `tests/test_delivery_config.py` — DeliverConfig.from_env asymmetric handling + from_pyproject
- [ ] `tests/test_delivery_run.py` — synchronous orchestrator unit-level (mock Bot)
- [ ] `tests/integration/test_delivery_run.py` — real SQLite + mock Bot.send_*; assert `runs.stats.deliver.*` patched
- [ ] `tests/integration/test_cli_deliver.py` — subprocess invocations of `python -m ga_crawler deliver-run --run-id N [...]`
- [ ] `tests/conftest.py` — add 3 new fixtures: `mock_aiogram_bot` (stub Bot class returning Message with stub message_id), `mock_tg_env` (sets/unsets TG_* env vars via monkeypatch), `synthetic_delivered_run` (Run row + populated `runs.stats.report.*` for gate-pass + 4 gate-fail variants)
- [ ] `tests/fixtures/delivery/ops-alert-templates.txt` — golden file 5 ops-alert scenarios
- [ ] No framework install needed — pytest + pytest-asyncio + pytest-mock already in dev deps

### Coverage Gap Analysis

**Already covered upstream:**
- D-405 KPI verbatim — covered by Plan 04-03 `test_match_rate_formula_canary` (Phase 6 inherits via summary_text reuse, no new test)
- D-514 7-key report namespace — covered Plan 05-04 (Phase 6 reads keys, doesn't write)
- D-515 size_guard_passed flag — covered Plan 05-04 (Phase 6 gate-check #3 reads it)

**Phase 6 net new coverage:**
- Gate composition (4 independent checks + short-circuit ordering)
- Retry timing budget (≤75s upper bound assertion via `time.monotonic` measurement in test)
- Idempotency dispatch (6 enum values × 2 force-mode = 12 paths in CLI; cover all)
- Bot session lifecycle (no leaks)
- HTML escape (golden file + property test: any input → no broken HTML)
- ENV-edge cases (4 missing-env scenarios per D-611 asymmetric matrix)
- Atomic single patch_stats call (spy)
- Structural invariant (no Phase 5 imports in delivery/)

**No live integration tests** per Claude's Discretion: «production smoke = первый weekly cron-run (Phase 7)». Phase 6 mocks aiogram Bot.

## Pitfalls Beyond CONTEXT.md

CONTEXT.md уже цитирует Pitfall 4 (None-rejection sentinels) и Pitfall 6 (atomic patch_stats). Ниже — **новые** pitfalls, не покрытые CONTEXT.md, основанные на Context7 verification + general aiogram production experience:

### Pitfall A: `TelegramBadRequest` retry-classification missing

**What goes wrong:** CONTEXT.md D-603 указывает только `TelegramNetworkError` + `TelegramServerError` для tenacity retry-set. Если `chat_id` неправильный (опечатка в `TG_BUSINESS_CHAT_ID`), aiogram бросит `TelegramBadRequest` ("chat not found"). Tenacity НЕ перехватит → исключение пробросится → outer `try` пометит `undelivered_telegram_unreachable` — корректное поведение **только если** outer try catches **base `Exception` или `TelegramAPIError`**.

**Why it happens:** `retry_if_exception_type(...)` фильтрует — НЕперехваченные exceptions сразу проброшены. Без явного outer catch для `TelegramAPIError`, исключение всплывёт в `main_run.run_weekly`'s DATA-05 try/except → `runs.status='failed'`. Это противоречит D-605 «delivery failure НЕ flagipает runs.status на failed».

**How to avoid:**
- В `delivery_run.py` outer try/except должен ловить `TelegramAPIError` (base class) ИЛИ `Exception` явно.
- Status mapping:
  - `TelegramBadRequest` → `delivery_status='undelivered_telegram_unreachable'`, `last_error=str(e)`. НЕ propagate.
  - `TelegramForbiddenError` → same.
  - `TelegramNotFound` → same.
  - `TelegramUnauthorizedError` (bot token revoked mid-run) → same OR `skipped_no_credentials` (debatable; рекомендую `undelivered_telegram_unreachable` потому что ENV был valid на startup).
- Только **`Exception` без подкласса** (programmer bug — AttributeError, TypeError) → re-raise → DATA-05 catches → `runs.status='failed'`.

**Warning signs:** test `test_bad_request_no_retry` + `test_runs_status_unchanged_on_telegram_failure` обязательны.

### Pitfall B: aiogram `Bot` instantiation without `async with` leaks aiohttp session

**What goes wrong:** Direct `bot = Bot(token); await bot.send_message(...)` без `async with` или явного `await bot.session.close()` оставляет `aiohttp.ClientSession` открытым → `RuntimeWarning: Unclosed client session` на event loop teardown. В production cron это просто warning, но в pytest с `-W error` валит тесты, и в долгоживущих процессах накапливает TCP connections.

**Why it happens:** aiogram lazy-инициализирует `AiohttpSession` при первом запросе. Session не имеет `__del__` cleanup — Python GC не закроет aiohttp ClientSession автоматически.

**How to avoid:**
- **Только** `async with Bot(...) as bot:` в `_send_delivery_async`.
- Test canary `test_no_unclosed_session_warning`: использовать `pytest.warns()` с `recwarn` фикстурой → assert no `RuntimeWarning` after function exit.
- Structural canary: `grep -E "^\s*bot\s*=\s*Bot\(" src/ga_crawler/delivery/` без последующего `async with` — fail.

### Pitfall C: `Path` containment for FSInputFile (defense in depth)

**What goes wrong:** Phase 5 Plan 05-04 уже валидирует `xlsx_path.relative_to(repo_root.resolve())` на write-side. Phase 6 читает persisted `runs.stats.report.xlsx_path` and trusts it. Если БД повреждена / атакован, `xlsx_path` мог содержать `../../etc/passwd` или абсолютный путь вне repo_root. `FSInputFile` откроет любой путь — Telegram получит чувствительные данные.

**Why it happens:** xlsx_path хранится как строка в JSON column. Любой write в DB обходит Phase 5 валидацию. Defence-in-depth требует re-check на read-side.

**How to avoid:**
```python
def _resolve_xlsx_safely(xlsx_path: str, repo_root: Path) -> Path:
    candidate = (repo_root / xlsx_path).resolve()
    repo_resolved = repo_root.resolve()
    try:
        candidate.relative_to(repo_resolved)
    except ValueError:
        raise ValueError(f"xlsx_path escapes repo_root: {xlsx_path}")
    if not candidate.is_file():
        raise FileNotFoundError(f"xlsx_path does not exist: {candidate}")
    return candidate
```

**Test:** `test_xlsx_path_must_be_within_repo` — synthetic run с tampered `xlsx_path='../../etc/passwd'` → expect ValueError → `delivery_status='undelivered_telegram_unreachable'`, no FSInputFile creation.

### Pitfall D: `Message.message_id` уникален per-chat, не globally

**What goes wrong:** CONTEXT.md Claude's Discretion говорит «`business_message_id` semantics: `send_message` возвращает `Message` с `message_id`; запатчить как `business_caption_message_id` + `business_document_message_id`». Если оператор когда-нибудь будет искать сообщение по message_id (e.g., Phase 7 pin/unpin), он должен помнить что **message_id уникален только в пределах одного chat**. Phase 6 пишет 3 ID в stats (caption / document / ops), но без chat_id-pair → теряется контекст в чём искать.

**Why it happens:** Telegram message_id — incremental counter per-chat, не UUID. Без chat_id pair ID бесполезен для последующих API calls.

**How to avoid:**
- Документировать в D-616 / Plan 06-XX inline comment: «message_id are scoped per-chat; use TG_BUSINESS_CHAT_ID + business_caption_message_id для поиска».
- Опционально (планер может решить): добавить 2 keys в D-607: `deliver.business_chat_id` + `deliver.ops_chat_id` (int, sentinel -1). **Recommendation:** НЕ добавлять — это recoverable из ENV и `.env.example` уже коммитится. Just inline-document в `delivery/stats.py` docstring.

### Pitfall E: TimeZone for `started_at_almaty` в ops alert (D-610)

**What goes wrong:** CONTEXT.md D-610 template содержит `{started_at_almaty}`. `runs.started_at` хранится в UTC (DATA-05 convention). Если форматировать просто `runs.started_at.strftime(...)`, оператор увидит UTC time, не Almaty.

**Why it happens:** SQLite DATETIME column хранит timestamp как-есть; sqlmodel default использует `datetime.utcnow()`. Phase 5 D-512 уже использует `ZoneInfo("Asia/Almaty")` для ISO-week derivation — тот же tz должен применяться к ops alert.

**How to avoid:**
```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def _format_almaty(started_at_utc: datetime) -> str:
    if started_at_utc.tzinfo is None:
        started_at_utc = started_at_utc.replace(tzinfo=timezone.utc)
    almaty = started_at_utc.astimezone(ZoneInfo("Asia/Almaty"))
    return almaty.strftime("%Y-%m-%d %H:%M %Z")  # e.g., "2026-05-11 22:00 +05"
```

**Test:** `test_ops_alert_started_at_in_almaty` — fixture started_at_utc = `2026-05-11T17:00Z` → expect `"2026-05-11 22:00"` substring in alert text.

**Cross-reference:** Phase 5 `reporter/archive.py` already imports `from zoneinfo import ZoneInfo` for D-512. Phase 6 reuses same pattern — no new dependency.

### Pitfall F: Synthetic test run fixture must populate ALL stats keys

**What goes wrong:** Plan 05-04 `synthetic_report_run` fixture устанавливает `report.*` keys. Phase 6 reads `report.summary_text`, `report.xlsx_path`, `report.size_guard_passed`, AND `match.count`, `match.rate`, `viled.fetch_count`, `goldapple.fetch_count` (для ops-alert snapshot stats per D-610). Если synthetic fixture не покрывает все 7 ключей, тест провалится по `KeyError` или сгенерирует ops alert с `None` substituted.

**How to avoid:** `synthetic_delivered_run` fixture в `tests/conftest.py` должен быть **superset** of `synthetic_report_run`:
- report.* keys (7) — для gate
- match.* keys (count, rate) — для D-610 snapshot stats
- viled.* keys (fetch_count) — для D-610
- goldapple.* keys (fetch_count) — для D-610
- runs.status — для gate check #1
- runs.started_at — для D-610 timezone formatting

Document in fixture docstring: «Populates ALL stats namespaces needed for delivery gate + ops alert builder».

## Open Questions

1. **tenacity wait formula (5/15/45 vs reality of `wait_exponential(multiplier=5, min=5, max=45)`)**
   - What we know: CONTEXT.md D-603 documents 5/15/45 backoff intent.
   - What's unclear: precise tenacity invocation. `wait_exponential(multiplier=5, min=5, max=45)` gives 10/20/(stop), not 5/15/45.
   - Recommendation: план MUST pick one:
     - `wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45))` — explicit, predictable.
     - `wait_exponential(multiplier=5, min=5, max=45, exp_base=3)` — `5×3^(n-1)` = 5/15/45.
     - `wait_exponential_jitter(initial=5, max=45)` — mirror viled fetcher pattern (project precedent).
   - Я рекомендую **option 1 (wait_chain)** — explicit, тестируется по списку waits, читается без знания tenacity formula. Если планер выберет option 3 для consistency с viled fetcher — OK, но изменит D-603 «5/15/45» на «5/10/20/40 capped jittered».

2. **Telegram parse_mode preference: enum vs string**
   - What we know: aiogram accepts `parse_mode="HTML"` (string) OR `parse_mode=ParseMode.HTML` (enum). Both work — `ParseMode` is `str, Enum` subclass.
   - What's unclear: D-609 pinned `parse_mode = "HTML"` в pyproject.toml. Это string — корректно для TOML. Но в code предпочтительно `ParseMode.HTML` (type-safe, IDE autocomplete).
   - Recommendation: TOML keeps string `"HTML"` (D-614 как есть); `delivery/config.py` parses TOML string into `ParseMode(parse_mode_str)` enum at load time. Single mapping `_PARSE_MODE_MAP = {"HTML": ParseMode.HTML, "MarkdownV2": ParseMode.MARKDOWN_V2}` with KeyError fail-fast for invalid TOML config.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | runtime | ✓ | 3.12 (pyproject `requires-python`) | — |
| aiogram | DELIVER-01..04 | ✗ (NEW dep — Wave 0 adds) | target `>=3.27,<4.0` | None — fail-fast in Wave 0 if pin fails |
| python-dotenv | DELIVER-05 | ✓ | `>=1.0,<2.0` (pyproject:21) | — |
| tenacity | DELIVER-04 | ✓ | `>=9.0,<10.0` (pyproject:25) | — |
| structlog | logging | ✓ | `>=25.0,<26.0` (pyproject:24) | — |
| sqlmodel | DB access | ✓ | `>=0.0.24,<0.1` (pyproject:23) | — |
| pytest-asyncio | tests | ✓ | `>=0.24` (dev deps:33) | — |
| pytest-mock | tests | ✓ | `>=3.14` (dev deps:34) | — |
| zoneinfo | Pitfall E timezone | ✓ | stdlib (Python 3.9+); `tzdata` win32 backfill present (pyproject:26) | — |

**Missing dependencies with no fallback:** `aiogram>=3.27,<4.0` — must be added in Plan 06-XX Wave 0. Estimate: ~70 sub-deps (aiohttp + magic-filter + pydantic — pydantic уже есть, aiohttp новый).

**No managed services / external APIs required beyond Telegram itself** (which is the integration target, not a dev dependency).

## Project Constraints (from CLAUDE.md)

- **Tech stack — Python**: aiogram fits (async-native, modern Python). Verified §Telegram Delivery in CLAUDE.md locks aiogram 3.27.
- **Frequency — weekly**: one cron run per week → only ≤3 Telegram sends/week. Far below all rate limits.
- **Pricing source — only public**: irrelevant for delivery (Telegram is our channel, not target site).
- **Delivery channel — Telegram + Excel**: covered by D-601 + D-615.
- **Hosting — VPS + cron**: Phase 6 host-agnostic; Phase 7 owns deployment. Telegram Bot API works from any IP (no geographic restrictions for ru-locale/kz-locale chats).
- **No selenium / requests / cloudscraper**: not applicable (scraping ≠ delivery).
- **Forbidden patterns from CLAUDE.md "What NOT to Use":** None apply to Phase 6 — Telegram Bot API uses aiohttp (через aiogram), not requests. python-telegram-bot rejected per D-601.

## Sources

### Primary (HIGH confidence)
- **Context7 `/websites/aiogram_dev_en_v3_27_0`** — 9054 code snippets indexed. Topics fetched:
  - `Bot DefaultBotProperties send_document FSInputFile parse_mode HTML async context manager`
  - `TelegramRetryAfter TelegramNetworkError TelegramServerError TelegramBadRequest exceptions session close`
  - `FSInputFile path filename example send_document`
  - `html escape formatting utils markdown html_decoration quote sanitize parse mode HTML allowed tags`
  - `html.quote aiogram html utils escape send_message caption length 1024 4096`
- **`https://docs.aiogram.dev/en/v3.27.0/api/methods/send_document.html`** — sendDocument signature + return type + caption limits
- **`https://docs.aiogram.dev/en/v3.27.0/api/upload_file.html`** — FSInputFile signature (path: str | Path, filename optional, chunk_size default 65536)
- **`https://docs.aiogram.dev/en/v3.27.0/api/defaults.html`** — DefaultBotProperties full parameter list
- **`https://docs.aiogram.dev/en/v3.27.0/_modules/aiogram/exceptions.html`** — exception hierarchy (TelegramAPIError base + 8 subclasses)
- **`https://docs.aiogram.dev/en/v3.27.0/dispatcher/errors.html`** — error type taxonomy + retry guidance
- **`https://docs.aiogram.dev/en/v3.27.0/_modules/aiogram/client/bot.html`** — Bot async context manager `auto_close=True` semantics
- **`https://docs.aiogram.dev/en/v3.27.0/_modules/aiogram/client/session/aiohttp.html`** — AiohttpSession.close() 250ms SSL drain
- **`https://docs.aiogram.dev/en/v3.27.0/migration_2_to_3.html`** — v2→v3 exception remapping (`RetryAfter` → `TelegramRetryAfter`)
- **`https://docs.aiogram.dev/en/v3.27.0/utils/formatting.html`** — `html.quote(value)` aiogram-namespace helper
- **`https://docs.aiogram.dev/en/v3.27.0/_modules/aiogram/enums/parse_mode.html`** — ParseMode str-Enum (HTML/MARKDOWN/MARKDOWN_V2)
- **`https://core.telegram.org/bots/api#senddocument`** — official Telegram spec: 50 MB file limit, 1024 char caption
- **`https://core.telegram.org/bots/api#sendmessage`** — 4096 char text limit
- **`https://core.telegram.org/bots/api#html-style`** — allowed HTML tags in HTML parse_mode
- **CLAUDE.md §Telegram Delivery** — aiogram 3.27 locked, python-telegram-bot 22 rejected, raw httpx rejected

### Codebase pattern references (HIGH confidence)
- `src/ga_crawler/runners/main_run.py:224` — `asyncio.run(run_goldapple_phase(...))` sync→async glue pattern (Phase 6 D-602 mirrors)
- `src/ga_crawler/fetchers/viled.py:87-92` — tenacity `@retry` async pattern (existing project precedent for D-603)
- `src/ga_crawler/runner/stats.py:18-32` — GOLDAPPLE_STATS_KEYS namespace pattern (Phase 6 D-607 mirrors)
- `src/ga_crawler/reporter/config.py` — ReportConfig.from_pyproject pattern (Phase 6 D-614 DeliverConfig.from_pyproject mirrors)
- `src/ga_crawler/storage/sqlite.py::SqliteRunWriter.patch_stats` — atomic json_patch (Pitfall 6; Phase 6 D-607 single-call invariant)
- `src/ga_crawler/matcher/strict_key.py::read_run_status` — D-411 helper REUSED in delivery/gate.py (D-604 check #1)

### Project context (HIGH confidence)
- `.planning/phases/06-telegram-delivery/06-CONTEXT.md` — 16 locked decisions D-601..D-616 (source of truth — research does NOT relitigate)
- `.planning/phases/05-reporter-excel-summary/05-CONTEXT.md` — Phase 5 D-514 source-of-truth cascade, D-515 size-guard cascade
- `.planning/REQUIREMENTS.md` §Deliver — DELIVER-01..05 active; §Report REPORT-06 (D-515 size_guard_passed dependency)
- `.planning/ROADMAP.md` §Phase 6 — Goal + 4 success criteria
- `.planning/research/PITFALLS.md` — Pitfall 6 atomic patch_stats, Pitfall 4 sentinel discipline (CONTEXT.md already cites)

### Tertiary (consulted, no claims dependent)
- ctx7 CLI v0.10 — `npx ctx7 docs /websites/aiogram_dev_en_v3_27_0 "..."` — fallback for Context7 MCP unavailability in Bash agent environment per documentation_lookup contract

## Assumptions Log

All claims in this research are either **[VERIFIED]** via Context7 / source code grep / pyproject.toml inspection, or **[CITED]** with direct URLs to aiogram v3.27.0 docs. **No `[ASSUMED]` claims remain.**

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | (empty) | — | — |

**Implication for discuss-phase:** all critical knowledge for planning is verified — no additional user confirmation needed beyond the 6 plan-uncertainties surfaced as `caveat #1..#6` in §Library Verification. Those are not assumptions about facts; they are gaps in CONTEXT.md spec where the planner must make a small implementation choice.

## Metadata

**Confidence breakdown:**
- aiogram 3.27 API correctness: HIGH — every Bot/send_*/FSInputFile/exception claim cited to docs.aiogram.dev/en/v3.27.0/ paths.
- Composition pattern correctness: HIGH — direct mirror of in-tree patterns (Plan 02-05 `asyncio.run`, Plan 04-04 stats builder, Plan 05-04 `patch_stats` single-call, Plan 05-05 pre-finalize).
- Telegram Bot API limits: HIGH — sourced from core.telegram.org/bots/api spec.
- Retry policy specifics (D-603 wait formula): MEDIUM — CONTEXT.md says "5/15/45" but exact tenacity invocation is ambiguous; flagged as Open Question #1.
- HTML escape choice (stdlib vs aiogram.html): HIGH — both valid; recommendation made.
- New pitfalls (A-F) coverage: HIGH — each pitfall references explicit aiogram source code or Telegram spec.

**Research date:** 2026-05-12
**Valid until:** 2026-06-12 (30 days — aiogram 3.x is stable; Telegram Bot API changes are additive)

## RESEARCH COMPLETE
