---
tags: [debugging, dotenv, telegram, cli, data-egress, hotfix-43dbfd7, security]
date: 2026-05-14
severity: high
hotfix_commit: 43dbfd7
---

# fake-xlsx в личный Telegram — load_dotenv walks от __file__, не cwd

## Симптом

- Operator получает в личный Telegram файлы `2026-W19.xlsx`, `2026-W19 (2).xlsx` … `2026-W19 (N).xlsx`
- Все файлы **не открываются**: `OfficeImportErrorDomain Error 912` на macOS / `файл повреждён` на Windows
- Размер всех файлов идентичен: **35 байт**
- `head -c 35 file.xlsx` показывает literal: `PK\x03\x04fake-xlsx-content-for-cli-tests`
- Файлы приходят с **operator's собственного бота** (тот же `TG_BOT_TOKEN`, что в `.env`)
- Количество растёт после каждого `uv run pytest` запуска

## Причина

`src/ga_crawler/cli.py` вызывал `load_dotenv(override=False)` без явного path аргумента. `python-dotenv`'s `find_dotenv()` defaults к walk-up от **caller's `__file__`** (т.е. `src/ga_crawler/cli.py`), НЕ от `os.getcwd()`.

Так как `cli.py` живёт под `src/ga_crawler/`, walk-up **всегда** находит project root's `.env` независимо от того, где запущен subprocess.

Subprocess-тесты `test_cli_deliver.py`:
- Стрипали `TG_*` из subprocess `env=` через `_env_without_tg()` helper
- Ожидали exit code 3 (skipped_no_credentials)

Но subprocess Python после старта:
1. Импортировал `cli.py`
2. `_cmd_deliver()` вызывал `load_dotenv(override=False)`
3. find_dotenv walked UP от cli.py → нашёл project root's `.env`
4. **Реальный `TG_BOT_TOKEN` + `TG_BUSINESS_CHAT_ID=986299192` загружались**
5. Delivery happy path исполнялся
6. Test fixture (`tmp_path/reports/2026-W19.xlsx` = 35-байт `PK\x03\x04fake-xlsx-content-for-cli-tests`) отправлялся через `send_document` в operator's личный Telegram

Результат: каждый запуск 2 тестов = 2 новых файла в чате. ≥11 deliveries confirmed.

Mislabeled в `08-01-SUMMARY.md:36` как "pre-existing test failures (test_cli_deliver.py x2 — confirmed pre-existing via git stash test against HEAD baseline)" — git-stash baseline confirmed что тесты fail на HEAD, но **не объяснил WHY**. Тесты были active egress channel, не benign.

## Что делать

### Срочно

1. Закомментировать `TG_BOT_TOKEN` в `.env` (или переименовать `.env` → `.env.disabled`) ДО запуска любых тестов
2. ИЛИ применить hotfix: `find_dotenv(usecwd=True)` (см. ниже)

### Hotfix (commit 43dbfd7)

```python
# src/ga_crawler/cli.py
from dotenv import find_dotenv, load_dotenv  # was: just load_dotenv

dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path, override=False)
```

`find_dotenv(usecwd=True)` anchors search at `os.getcwd()`:
- Subprocess test cwd=`tmp_path` → walks up tmp tree → нет `.env` → returns `""` → `load_dotenv` no-op
- Production operator `cd /opt/ga_crawler && python -m ga_crawler ...` → cwd=project root → `.env` found

### Regression canary

`tests/integration/test_cli_deliver.py::test_cli_does_not_load_project_dotenv_when_cwd_outside_tree` pins behavior — running CLI с `cwd=tmp_path` + stripped TG_* → exit 3 + `delivery_status=skipped_no_credentials` + message IDs sentinel-only.

## Превентивно

1. **Never use `load_dotenv()` без явного path в CLI кода.** Always `find_dotenv(usecwd=True)` или explicit `Path(args.repo_root) / ".env"`.
2. **"Pre-existing failures" annotations нужны written root-cause.** Если не можешь объяснить WHY теcт fails одним предложением — он не triaged. См. [[«Pre-existing failures» annotation pattern — code smell, не closure]].
3. **Subprocess tests с TG_* / любыми credentials в env должны pre-flight verify** что .env не достижим из cwd через `find_dotenv(usecwd=True)` returning `""`.
4. Рассмотри gating: `load_dotenv` только когда явный operator flag (`GA_CRAWLER_ALLOW_DOTENV=1`), никогда автоматически.

## Impact (этот инцидент)

- **Leaked content:** 11+ × 35 bytes = ~385 bytes of `PK\x03\x04fake-xlsx-content-for-cli-tests` literal
- **Customer data:** **0 байт** (test fixture only, no DB snapshots / SKU prices / matches)
- **Credentials:** не утекли (TG_BOT_TOKEN остался в .env; only file-upload API exercised)
- **Recipient:** operator's personal Telegram, **не shared business chat**
- **Time to discovery:** ~1 day (Phase 8 W0 spike сделан 2026-05-13; user заметил 2026-05-14)

## Связанные

- [[2026-05-14 — Phase 8 W1 GREEN shipped + cli.py dotenv-leak hotfix closes data egress]]
- [[find_dotenv usecwd=True — anchor dotenv discovery at cwd для test isolation]]
- [[«Pre-existing failures» annotation pattern — code smell, не closure]]
- `.planning/quick/20260514-cli-dotenv-leak/SUMMARY.md`
