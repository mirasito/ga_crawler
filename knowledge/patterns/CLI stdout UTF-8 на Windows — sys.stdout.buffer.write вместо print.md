---
tags: [pattern, cli, windows, unicode, cross-platform]
date: 2026-05-12
---

# CLI stdout UTF-8 на Windows — sys.stdout.buffer.write вместо print

## Проблема

`print(json.dumps(payload, ensure_ascii=False))` падает на Windows-консоли:

```
UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f4ca'
in position N: character maps to <undefined>
```

Причина: дефолтный stdout на Windows использует cp1252 locale codec, который не покрывает Cyrillic + emoji. `ensure_ascii=False` сохраняет Unicode, но печать в stdout проходит через encode → ломается.

## Решение

```python
import json
import sys

payload = {
    "summary_text": "📊 Неделя 2026-W19 — viled vs goldapple\n...",
    "xlsx_path": "reports/2026-W19.xlsx",
}
sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
sys.stdout.buffer.write(b"\n")
```

`sys.stdout.buffer` — это raw binary buffer; запись байтов обходит locale codec. UTF-8 явный, portable across Linux/macOS/Windows.

## Антипаттерн

```python
# плохо — ломается на Windows-консоли с Cyrillic+emoji
print(json.dumps(payload, ensure_ascii=False))

# плохо — теряет читаемость, не решает проблему для stderr/logs
print(json.dumps(payload, ensure_ascii=True))  # \uXXXX-эскейпы
```

Альтернативы хуже:
- `PYTHONIOENCODING=utf-8` env var — внешняя конфигурация, не self-contained
- `sys.stdout.reconfigure(encoding="utf-8")` — Python 3.7+, mutates global state mid-process, можно пропустить в CLI dispatch
- `chcp 65001` — требует от оператора, ломается в pipe-chain

`sys.stdout.buffer.write` — однострочная замена `print`, явная, ZERO state mutation.

## Когда применять

- CLI commands, которые выводят JSON с user-facing текстом (Russian, emoji, любой non-ASCII)
- Любой CLI handler, потенциально pipe-ed в файл или другую программу
- Любой код, тестируемый через `subprocess.run` в CI/test suite — Windows runners (GitHub Actions windows-latest) специально ловят эту ошибку

## Примеры в ga_crawler

- `src/ga_crawler/cli.py::_cmd_report` (Plan 05-05 Rule 1 fix) — выводит `MainRunResult`-подобный JSON с `summary_text` содержащим 📊📦🎯🆕💸🔝 emoji + Russian
- Любой будущий `delivery-run`-style CLI в Phase 6 должен следовать тому же pattern (Phase 6 будет выводить тот же `summary_text` для preview)

## Связанные

- [[Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text]]
- [[Стек — Python 3.12 + curl_cffi + Playwright + SQLite]]
- [[2026-05-12 — Phase 5 executed — reporter shipped через 6 waves]]
