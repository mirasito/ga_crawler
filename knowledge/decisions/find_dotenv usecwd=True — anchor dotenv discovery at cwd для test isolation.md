---
tags: [decision, dotenv, cli, test-isolation, security, hotfix-43dbfd7]
date: 2026-05-14
status: locked
hotfix_commit: 43dbfd7
applies_to: src/ga_crawler/cli.py
---

# find_dotenv(usecwd=True) — anchor dotenv discovery at cwd для test isolation

## Решение

В `src/ga_crawler/cli.py::_cmd_deliver()`, dotenv loading должен **всегда** anchor поиск `.env` файла на `os.getcwd()`, не на `__file__`.

```python
from dotenv import find_dotenv, load_dotenv

dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path, override=False)
```

**Никогда** не вызывать `load_dotenv()` без явного path аргумента в CLI код.

## Почему

`python-dotenv`'s default `find_dotenv()` walks UP от **caller frame's `__file__`** location, не от `os.getcwd()`. Для CLI module под `src/ga_crawler/cli.py` walk-up **всегда** находит project root's `.env` независимо от того, где запущен subprocess.

Это вызывает **silent credential leakage** в subprocess-тестах:
- Тесты стрипают `TG_*` из subprocess `env=` через `_env_without_tg()` helper
- Subprocess Python after start вызывает `load_dotenv(override=False)`
- find_dotenv walks UP от cli.py → находит project root .env → re-загружает real credentials
- Test happy-path исполняется → fake-xlsx fixture отправляется в real Telegram

Подтверждённый incident (commit `43dbfd7`, 2026-05-14): 11+ test runs силentno доставили 35-байт fake-xlsx fixtures в operator's личный Telegram (chat_id=986299192) через `test_deliver_run_missing_token_exits_3` + `test_unicode_stdout_safe_on_windows`. См. [[fake-xlsx в личный Telegram — load_dotenv walks от file, не cwd]].

## Производственная семантика сохранена

Operator на VPS запускает: `cd /opt/ga_crawler && python -m ga_crawler deliver-run --run-id N`
- cwd = `/opt/ga_crawler` (project root)
- `find_dotenv(usecwd=True)` walks up от cwd → finds `/opt/ga_crawler/.env` сразу
- Identical behavior to pre-fix code path

Cron entry в `deploy/etc-cron-d-ga_crawler` уже использует `cd /opt/ga_crawler` (D-708) — `usecwd=True` change полностью совместим.

## Test semantics fixed

Subprocess-тесты с `cwd=tmp_path`:
- `tmp_path` = `C:\Users\...\AppData\Local\Temp\pytest-of-...\pytest-N\test-name\` (Windows) или `/tmp/pytest-of-USER/...` (Linux/macOS)
- Walk-up от tmp_path никогда не пересекает project tree
- Returns `""` → `load_dotenv` no-op → TG_BOT_TOKEN stays unset → exit code 3 как designed

## Альтернативы рассмотрены

| Подход | Vердикт |
|--------|---------|
| Explicit `Path(args.repo_root) / ".env"` | **Не выбран** — операторы могут запускать CLI без `--repo-root` (default Path('.') resolve). Усложняет CLI surface. |
| Gating via `GA_CRAWLER_ALLOW_DOTENV=1` env var | **Рассмотрен** — добавляет operator friction (нужно set explicit env var). Не выбран для v1.1 hotfix. Возможно для v2. |
| Mock `load_dotenv` в тестах через monkeypatch | **Не выбран** — subprocess tests не могут monkey-patch внутренности subprocess Python. Можно только через `env=` strip, что не помогает против re-load из disk. |
| Skip dotenv loading совсем, всегда use `os.environ` | **Не выбран** — operator UX страдает (must `export TG_BOT_TOKEN=...` каждый запуск). `.env` остаётся primary delivery channel для credentials. |

`find_dotenv(usecwd=True)` выбран как **минимальное вмешательство** — 1-line change, zero new operator-facing knobs, restores intended test isolation.

## Regression protection

`tests/integration/test_cli_deliver.py::test_cli_does_not_load_project_dotenv_when_cwd_outside_tree` (added in commit `43dbfd7`) pins behavior independently от `test_deliver_run_missing_token_exits_3`. Future refactor который удалит `usecwd=True` flag triggers test failure.

## Ограничения / known limits

- Если operator случайно запускает CLI **из** project tree но без `cd /opt/ga_crawler` ahead-of-time (e.g. `python /opt/ga_crawler/src/...`), find_dotenv может или не может найти `.env` depending on cwd. Это **отступление от pre-fix behavior** — previously всегда работало; теперь требует deliberate cwd.
  - Mitigation: cron entry already does `cd /opt/ga_crawler` (D-708). Operator manual runs documented in `deploy/README.md` always `cd` first. No production regression observed.

## Связанные

- [[fake-xlsx в личный Telegram — load_dotenv walks от file, не cwd]] (debugging note)
- [[«Pre-existing failures» annotation pattern — code smell, не closure]] (mislabeling lesson)
- `.planning/quick/20260514-cli-dotenv-leak/SUMMARY.md`
- commit `43dbfd7`: `fix(quick): cli.py dotenv discovery anchored at cwd, not __file__ (data egress hotfix)`
