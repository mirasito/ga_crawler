# Spike 01: Setup Notes

**Setup completed:** 2026-05-05
**Operator:** mirdbek@gmail.com
**Baseline machine:** Windows 11 Pro (per D-06)

## uv project location

**Repo root:** `pyproject.toml` живёт здесь, не в `.planning/spikes/01-goldapple/`.

**Phase 2 instruction:** **НЕ делать `uv init` повторно.** Phase 2 переиспользует этот же uv-проект и просто добавит свои зависимости (`uv add pandas xlsxwriter sqlmodel aiogram`). Lockfile-история сохраняется. Повторный `uv init` обнулит `uv.lock` и потеряет pinned hashes для curl_cffi/patchright/selectolax — это сломает воспроизводимость.

## Installed versions

Точные версии из `uv pip list` сразу после `uv sync` + `uv add`:

- Python: **3.12.13**
- patchright: **1.59.1**
- curl_cffi (curl-cffi): **0.15.0**
- selectolax: **0.3.34**
- structlog: **25.5.0**
- python-dotenv: **1.2.2**

Транзитивные зависимости (cffi 2.0.0, certifi 2026.4.22, greenlet 3.5.0, pyee 13.0.1, typing-extensions 4.15.0, и др.) — см. `uv.lock`.

## Patchright Chromium binary

Установлен через `uv run patchright install chromium`.

**Cache location (Windows):** `C:\Users\gstorepc\AppData\Local\ms-playwright\chromium-1217\` (Chrome for Testing 147.0.7727.15) и `C:\Users\gstorepc\AppData\Local\ms-playwright\chromium_headless_shell-1217\` (~290 MB суммарно).

На Linux VPS (Phase 7) дополнительно потребуется `uv run patchright install-deps chromium` для системных deps (libnss, libgtk, libgconf, и т. п.).

## Smoke test (recorded)

Команда:

```bash
uv run python -c "from patchright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); page = b.new_page(); page.goto('https://example.com'); print('TITLE:', page.title()); b.close(); p.stop()"
```

Output: `TITLE: Example Domain`

Запуск headless Chromium прошёл без ошибок, страница example.com отрендерилась, title извлечён.

## Excluded (NOT installed in this spike)

- vanilla `playwright` — per D-01, Tier 1 (vanilla) skipped (детектится Cloudflare/DataDome в 2026)
- `camoufox`, `scrapling` — Tier 4, добавляются plan'ом 01-10 ТОЛЬКО если Tier 2+3 fail
- `pandas`, `xlsxwriter`, `sqlmodel`, `aiogram`, `alembic`, `APScheduler` — Phase 2+ scope
- `tenacity`, `pydantic` — пока не нужны для recon-спайка (добавятся в Phase 2 для production-ретраев)

## Next plans (Phase 1)

Этот setup разблокирует:
- 01-03: IPRoyal trial signup (D-08) — нужен `python-dotenv` для `.env.local`
- 01-04..01-07 (Wave 1): cheap recon — robots, sitemap, JSON-endpoint hunt (curl_cffi), viled feasibility (curl_cffi + selectolax)
- 01-08..01-09 (Wave 2): Patchright Tier-2 100-fetch эксперимент (KZ-laptop + EU-proxy)
