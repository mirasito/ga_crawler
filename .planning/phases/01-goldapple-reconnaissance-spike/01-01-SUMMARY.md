---
phase: 01-goldapple-reconnaissance-spike
plan: 01
subsystem: spike-skeleton
tags: [spike, scaffolding, throwaway, goldapple]
requires: []
provides:
  - .planning/spikes/01-goldapple/ tracked в git
  - skeleton-файлы (README, MEMO, notebook.py, notebook-viled.py, tos-audit.md, sample-payloads/)
  - .gitignore защищает .env.local + spike browser-state + *.db
affects: []
tech_stack:
  added: []
  patterns: []
key_files:
  created:
    - .planning/spikes/01-goldapple/README.md
    - .planning/spikes/01-goldapple/MEMO.md
    - .planning/spikes/01-goldapple/notebook.py
    - .planning/spikes/01-goldapple/notebook-viled.py
    - .planning/spikes/01-goldapple/tos-audit.md
    - .planning/spikes/01-goldapple/sample-payloads/.gitkeep
    - .gitignore
  modified: []
decisions:
  - "Throwaway-граница зафиксирована в README: ничего из spike-каталога не импортируется в Phase 2 src/"
metrics:
  duration: "~3 min"
  completed: "2026-05-05"
  tasks_total: 3
  tasks_completed: 3
  files_created: 7
---

# Phase 1 Plan 01: Spike Skeleton Summary

**One-liner:** Throwaway-каркас спайка `.planning/spikes/01-goldapple/` со stub-файлами под каждый последующий план + `.gitignore` для секретов.

## What Was Built

Полностью скелетный план: ни строчки production-кода, только структура для последующих планов 01-02..01-12.

- **`README.md`** — фиксирует throwaway-scope (D-16): Phase 2 НЕ импортирует ничего из этого каталога; навигационная таблица артефактов с пометкой какой план каждый файл заполняет; ссылка на 16 D-XX-решений в `01-CONTEXT.md`; setup-нота про uv в repo-root.
- **`MEMO.md`** — decision-memo template со всеми обязательными секциями: TL;DR (chosen tier / engine / proxy / prod-IP), Problem, Options tested, Chosen с двумя 100-fetch-результатами (KZ-laptop + EU-proxy per D-05/D-06), JSON-endpoint hunt verdict (D-09/D-10), page-volume estimate (RECON-03), viled feasibility (RECON-02), robots/ToS summary (RECON-04), Next-step impact (Phase 3 stack + Phase 7 hosting), Open risks, Challenge-rate appendix (D-15).
- **`notebook.py`** — header-only Python script для Patchright 100-fetch эксперимента; в docstring ссылки на D-04 (warm context, slow rate), D-13 (≥95/100 threshold), D-14 (HTTP 200 + JSON-LD), D-03 (stop-rule); тело — `raise NotImplementedError("Filled by plan 01-08")`.
- **`notebook-viled.py`** — header-only для curl_cffi viled feasibility check; ссылки на RECON-02 и side-deliverables (timing, JSON-LD, pagination, robots/UA strictness).
- **`tos-audit.md`** — robots/ToS audit skeleton с симметричными секциями для viled.kz и goldapple.kz; rate-limit placeholders (заполняет 01-04); KZ-legal review явно DEFERRED to Phase 7.
- **`sample-payloads/.gitkeep`** — пустая директория попадает в git, чтобы 01-05/01-06 могли складывать sample HTML/JSON/network-trace без `mkdir`.
- **`.gitignore`** — protects `.env`, `.env.local`, `.env.*.local` (D-08: IPRoyal credentials trial из 01-03), spike browser-state/ + .cache/ (D-04: persistent context cookies), `*.db` (Phase 2 SQLite превентивно), стандартные Python/OS/IDE-игноры.

## Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1 | spike directory + README + sample-payloads/.gitkeep | `c2da755` |
| 2 | MEMO/notebook/notebook-viled/tos-audit stubs | `02e8cf5` |
| 3 | .gitignore covering secrets + spike artifacts | `8a2d5c5` |

## Acceptance Criteria

Все criteria из 3 задач прошли (7/7 файлов, все обязательные anchor-строки присутствуют):

- ✓ `Throwaway scope` / `D-01` / `D-16` в README (3/3)
- ✓ `Chosen tier:` в MEMO.md
- ✓ `viled.kz rate-limit:` + `goldapple.kz rate-limit:` в tos-audit.md
- ✓ `NotImplementedError` в обоих notebook'ах
- ✓ `.env.local` + `.planning/spikes/01-goldapple/browser-state/` + `*.db` в `.gitignore`

## Deviations from Plan

None — план исполнен точно как написано.

Замечания:
- `.planning/spikes/01-goldapple/` уже существовал как пустой каталог, файлы внутри не было. Создал недостающие файлы без перезаписи существующих (по плану — idempotent create).
- `.gitignore` не существовал в repo-root; создан с нуля по plan-template, не было необходимости в idempotent merge.
- На Windows ожидаемо появились git warnings `LF will be replaced by CRLF` — это не ошибки, just `core.autocrlf=true` поведение, файлы коммитятся корректно с LF в репо.
- Out-of-scope изменения, оставленные нетронутыми (не относятся к этому плану): unstaged `CLAUDE.md` modification, untracked `.obsidian/` directory.

## Authentication Gates

Не применимо — план не делает сетевых запросов.

## Threat Flags

Не нашёл новых поверхностей вне `<threat_model>` плана. Существующая T-01-01-01 (информация раскрыта через `.env.local` commit) митигирована через `.gitignore` (Task 3).

## Self-Check: PASSED

Verified via filesystem + git-log:
- FOUND: `.planning/spikes/01-goldapple/README.md`
- FOUND: `.planning/spikes/01-goldapple/MEMO.md`
- FOUND: `.planning/spikes/01-goldapple/notebook.py`
- FOUND: `.planning/spikes/01-goldapple/notebook-viled.py`
- FOUND: `.planning/spikes/01-goldapple/tos-audit.md`
- FOUND: `.planning/spikes/01-goldapple/sample-payloads/.gitkeep`
- FOUND: `.gitignore`
- FOUND: commit `c2da755` (Task 1)
- FOUND: commit `02e8cf5` (Task 2)
- FOUND: commit `8a2d5c5` (Task 3)
