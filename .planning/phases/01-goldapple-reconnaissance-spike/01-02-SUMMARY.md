---
phase: 01-goldapple-reconnaissance-spike
plan: 02
subsystem: dev-environment
tags: [spike, uv, python-3.12, patchright, curl_cffi, dependencies]
requires:
  - .gitignore (Plan 01-01) защищает .env.local + browser-state
provides:
  - uv-проект в repo root с Python 3.12 (pyproject.toml + uv.lock + .python-version)
  - 5 spike-зависимостей установлены и lockfile-pinned (curl_cffi 0.15.0, patchright 1.59.1, selectolax 0.3.34, structlog 25.5.0, python-dotenv 1.2.2)
  - Patchright Chromium 147.0.7727.15 (v1217) скачан в %USERPROFILE%\AppData\Local\ms-playwright\
  - SETUP-NOTES.md фиксирует версии + warning Phase 2 не делать `uv init` повторно
affects:
  - Plan 01-03 будет писать `.env.local` для IPRoyal-creds — `python-dotenv` уже установлен
  - Plans 01-04..01-07 (cheap recon) могут сразу использовать curl_cffi + selectolax
  - Plans 01-08..01-09 (Patchright Tier-2) могут сразу запускать headless Chromium
  - Phase 2 переиспользует тот же uv-проект (just `uv add` для production deps)
tech_stack:
  added:
    - "python: 3.12.13"
    - "patchright: 1.59.1 (Tier-2 anti-bot, drop-in для playwright)"
    - "curl_cffi: 0.15.0 (TLS-impersonation HTTP client)"
    - "selectolax: 0.3.34 (быстрый HTML-parser)"
    - "structlog: 25.5.0 (JSON-логи)"
    - "python-dotenv: 1.2.2 (.env.local loader)"
  patterns:
    - "uv-managed deps: один lockfile, hash-pinned, единая venv в .venv/ (gitignored)"
    - "Patchright browser binary живёт ВНЕ репо (~/.cache/ms-playwright или AppData\\Local\\ms-playwright) — не в git"
key_files:
  created:
    - pyproject.toml
    - uv.lock
    - .python-version
    - .planning/spikes/01-goldapple/SETUP-NOTES.md
  modified: []
decisions:
  - "uv-проект в repo ROOT, не в .planning/spikes/01-goldapple/ (D-16 артефакты в spike-каталоге, но env переиспользуется Phase 2+)"
  - "vanilla `playwright` пакет НЕ установлен (D-01: Tier 1 пропущен, сразу Tier 2 Patchright)"
  - "Не добавлены pandas/sqlmodel/aiogram/xlsxwriter — это Phase 2+ scope; Camoufox/Scrapling — Tier 4 (plan 01-10 conditional)"
metrics:
  duration: "~5 min"
  completed: "2026-05-05"
  tasks_total: 3
  tasks_completed: 3
  files_created: 4
---

# Phase 1 Plan 02: uv Project Init + Spike Dependencies Summary

**One-liner:** uv-проект инициализирован в repo root с Python 3.12; 5 spike-зависимостей (curl_cffi, patchright, selectolax, structlog, python-dotenv) установлены и lockfile-pinned; Patchright Chromium binary v1217 скачан, headless smoke-test проходит.

## What Was Built

Setup-план Wave 0: окружение готово для всей оставшейся фазы 1 + переиспользуется Phase 2.

- **`pyproject.toml`** — single-package uv-проект `ga-crawler` 0.1.0, `requires-python = ">=3.12"`, 5 dep-строк с version-bound'ами из CLAUDE.md §Technology Stack (`curl_cffi>=0.15,<0.16`, `patchright>=1.55`, `selectolax>=0.3,<0.4`, `structlog>=25.0,<26.0`, `python-dotenv>=1.0,<2.0`).
- **`uv.lock`** — 55 KB lockfile, 16 packages resolved (5 direct + 11 transitive: cffi, certifi, greenlet, markdown-it-py, mdurl, pyee, pycparser, pygments, rich, typing-extensions). Hash-pinned, воспроизводимое окружение.
- **`.python-version`** — содержит `3.12`. uv-toolchain выбирает `CPython 3.12.13` для venv в `.venv/`.
- **Patchright Chromium binary** — `Chrome for Testing 147.0.7727.15 (v1217)` + `chrome-headless-shell` суммарно ~290 MB в `C:\Users\gstorepc\AppData\Local\ms-playwright\chromium-1217\` и `chromium_headless_shell-1217\`. Cache живёт ВНЕ репо (не в git).
- **`.planning/spikes/01-goldapple/SETUP-NOTES.md`** — записаны точные установленные версии (`Python 3.12.13`, `patchright 1.59.1`, `curl_cffi 0.15.0`, `selectolax 0.3.34`, `structlog 25.5.0`, `python-dotenv 1.2.2`), команды установки Chromium, smoke-test output (`TITLE: Example Domain`), explicit warning для Phase 2: «**НЕ** делать `uv init` повторно — обнулит lockfile-историю». Перечислены explicitly-excluded пакеты (vanilla playwright per D-01, pandas/sqlmodel/aiogram per Phase-2-scope, camoufox/scrapling per Tier-4-conditional).

## Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1 | uv installed (auto-skip in YOLO mode — `uv 0.11.7` already present) | (no commit — checkpoint) |
| 2 | uv init + Python 3.12 + 5 spike deps via single `uv add` | `d47b800` |
| 3 | Patchright Chromium install + SETUP-NOTES.md с реальными версиями + Phase-2 warning | `0b98407` |

## Acceptance Criteria

Все criteria из обеих auto-задач прошли:

**Task 2 (uv project init):**
- ✓ `pyproject.toml` exists
- ✓ `uv.lock` exists
- ✓ `.python-version` содержит `3.12`
- ✓ `pyproject.toml` содержит `patchright`, `curl-cffi`, `selectolax`, `structlog`, `python-dotenv` (все 5 grep-ов прошли ≥1)
- ✓ `uv run python -c "import patchright, curl_cffi, selectolax, structlog, dotenv; print('OK')"` → `OK` (exit 0)

**Task 3 (Chromium + SETUP-NOTES):**
- ✓ `uv run python -c "from patchright.sync_api import sync_playwright; ...; b.close(); p.stop()"` exit 0 (Chromium headless launches и закрывается)
- ✓ Smoke test против `https://example.com` вернул `TITLE: Example Domain`
- ✓ `.planning/spikes/01-goldapple/SETUP-NOTES.md` существует
- ✓ `grep -c "uv init"` ≥ 1 (warning для Phase 2 присутствует)
- ✓ `grep -c "Phase 2"` ≥ 1
- ✓ `grep -c "patchright"` ≥ 1
- ✓ `_TBD_` placeholders все заменены реальными значениями (grep `_TBD_` → 0 matches)

## Deviations from Plan

None — план исполнен точно как написано.

Замечания:
- Task 1 (checkpoint:human-verify «установить uv») auto-approved через `workflow.auto_advance: true` — `uv 0.11.7` уже был установлен на машине (verified `uv --version` perед стартом плана). Плановый resume-signal допускает это (`"skip" если уже установлен и проверено`).
- `uv init --no-readme --no-workspace .` создал `main.py` (default uv entry-point) — удалён согласно шагу 3 плана (спайк не нуждается в entry-point, скрипты живут в `.planning/spikes/01-goldapple/notebook*.py`).
- `patchright>=1.55` зарезолвилось в `1.59.1` (минорный апдейт от плана) — это в рамках version-bound'а из CLAUDE.md, не deviation.
- На Windows git warnings `LF will be replaced by CRLF` появились (как и в Plan 01-01) — не ошибки, `core.autocrlf=true` поведение.
- Out-of-scope, оставленные нетронутыми: unstaged `CLAUDE.md` modification, untracked `.obsidian/` directory (не относятся к этому плану — пользовательский Obsidian-vault content).

## Authentication Gates

Не применимо — план не делает аутентификированных сетевых запросов. Скачивания (PyPI для зависимостей, Microsoft Playwright CDN для Chromium) — public, без auth.

## Threat Flags

Не нашёл новых поверхностей вне `<threat_model>` плана.

- T-01-02-01 (Tampering — supply chain) **accepted** как и планировалось; mitigation через uv lockfile-hash-pinning (uv.lock содержит SHA-256 для каждого wheel).
- T-01-02-02 (Information Disclosure — secret в pyproject.toml) **mitigated**: проверено grep'ом — `pyproject.toml` не содержит токенов/ключей, только public dep-specs. Все creds откладываются в `.env.local` (Plan 01-03), gitignored.

## Self-Check: PASSED

Verified via filesystem + git-log + uv-runtime:

- FOUND: `pyproject.toml` (277 bytes)
- FOUND: `uv.lock` (55098 bytes)
- FOUND: `.python-version` (5 bytes, contains "3.12")
- FOUND: `.planning/spikes/01-goldapple/SETUP-NOTES.md`
- FOUND: commit `d47b800` (Task 2)
- FOUND: commit `0b98407` (Task 3)
- VERIFIED: `uv run python -c "import patchright, curl_cffi, selectolax, structlog, dotenv"` → OK
- VERIFIED: Patchright headless smoke-test против example.com → `TITLE: Example Domain`
- VERIFIED: `pyproject.toml` содержит все 5 deps (grep counts: patchright 1, curl-cffi 1, selectolax 1, structlog 1, python-dotenv 1)
- VERIFIED: SETUP-NOTES.md содержит `uv init` (1), `Phase 2` (3), `patchright` (5), no `_TBD_`
