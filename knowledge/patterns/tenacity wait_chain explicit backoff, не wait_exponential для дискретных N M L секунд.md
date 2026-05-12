---
tags: [pattern, retry, tenacity, telegram, async, gotcha]
date: 2026-05-12
status: live
---

# tenacity wait_chain explicit backoff, не wait_exponential для дискретных N/M/L секунд

Когда нужен retry с **конкретной последовательностью** wait-времен (например, «5 секунд, потом 15, потом 45»), `wait_exponential(multiplier=N, min=M, max=L)` — **неправильный инструмент**. Используй `wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45))`.

## Почему `wait_exponential` не даёт 5/15/45

`tenacity.wait_exponential(multiplier=5, min=5, max=45)` использует формулу `min(multiplier * 2^(attempt-1), max)` где attempt = 1, 2, 3, ...:

| attempt | формула           | результат         |
|---------|-------------------|-------------------|
| 1       | min(5×1, 45)      | **5**             |
| 2       | min(5×2, 45)      | **10**            |
| 3       | min(5×4, 45)      | **20**            |
| 4       | min(5×8=40, 45)   | 40                |

То есть последовательность **5/10/20/40**, не 5/15/45. Если нужны разрывы (5×3=15, не 5×2=10) — формула не сходится никакой комбинацией `multiplier`/`min`/`max`/`exp_base`.

## Правильный паттерн — `wait_chain`

```python
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_chain, wait_fixed

@retry(
    retry=retry_if_exception_type((TelegramNetworkError, TelegramServerError)),
    stop=stop_after_attempt(3),
    wait=wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45)),  # explicit 5/15/45
    reraise=True,
)
async def _do(): ...
```

`wait_chain` берёт wait-функцию по индексу попытки: первая retry-пауза = `wait_fixed(5)`, вторая = `wait_fixed(15)`, третья = `wait_fixed(45)`. Total budget = 5+15+45 = 65 секунд.

## Альтернатива — `wait_exponential(exp_base=3)`

`wait_exponential(multiplier=5, exp_base=3, min=5, max=45)`:

| attempt | формула              | результат |
|---------|----------------------|-----------|
| 1       | min(5×1, 45)         | 5         |
| 2       | min(5×3, 45)         | **15**    |
| 3       | min(5×9=45, 45)      | **45**    |

Работает, но **menos читабельно** чем `wait_chain` — оператор должен ментально пересчитать `5×3^n`. `wait_chain` декларативно показывает 5/15/45.

## Когда `wait_exponential` правильный выбор

Для **истинно exponential backoff** (без жёстких дискретных значений): retry-after с jitter, или scaling по сетевой latency:

```python
wait_exponential(multiplier=1, max=60)  # 1, 2, 4, 8, 16, 32, 60
wait_exponential_jitter(initial=1, max=60)  # +jitter, для thundering herd
```

## Where в кодовой базе

- **`src/ga_crawler/delivery/telegram_client.py`** — Phase 6 D-603 (Plan 06-03):
  ```python
  wait=wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45))
  ```
  Подкреплено structural canary `tests/test_telegram_client.py::test_no_wait_exponential_in_telegram_client` — grep returns 0.
- **`src/ga_crawler/fetchers/viled.py` (Plan 02-04)** — viled fetcher использует `wait_exponential` (приемлемо там, потому что fetcher retry — true exponential backoff на network jitter).

## RESEARCH origin

Caveat #2 из `.planning/phases/06-telegram-delivery/06-RESEARCH.md` §Library Verification. Plan-checker iteration 1 поймал что CONTEXT D-603 literally encoded `wait_exponential(multiplier=5, min=5, max=45)` с комментарием «5/15/45 backoff» — формула не сходится. Plan 06-06 surgical fix update CONTEXT.md D-603 на `wait_chain` + footnote.

## Когда применять (decision rule)

| Situation                                             | Pick                  |
|-------------------------------------------------------|-----------------------|
| Нужны конкретные N/M/L секунд (5/15/45, 1/2/10, etc.) | `wait_chain`          |
| Нужен true exponential `multiplier × base^n`          | `wait_exponential`    |
| Нужен exponential + jitter (network thundering)       | `wait_exponential_jitter` |
| Нужны разные wait для разных exception types          | `wait_combine`        |
