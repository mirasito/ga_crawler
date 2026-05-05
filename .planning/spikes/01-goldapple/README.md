# Spike 01: Goldapple Reconnaissance

**Status:** Active (1-week timebox per D-02)
**Output:** Signed-off `MEMO.md` + reproducible `notebook.py`

## Throwaway scope

Этот каталог — источник правды для Phase 1 спайка и **только** для него.

- Ни один файл отсюда не импортируется в `src/` или production-код Phase 2+.
- Phase 2 начинается с чистого листа; все findings переезжают через `MEMO.md` (decision memo) и project-local skill, упакованный `/gsd-spike --wrap-up`.
- Notebook — `.py` script (D-default per CONTEXT.md), не `.ipynb`. Print'ы вместо output-cells, чище diffs.

## Artifacts

| File | Purpose | Filled by plan |
|------|---------|----------------|
| `MEMO.md` | Decision memo: chosen tier, browser engine, proxy provider, prod-IP recommendation | 01-11 |
| `notebook.py` | Patchright 100-fetch experiment (Tier 2/3 measurement) | 01-08, 01-09, conditionally 01-10 |
| `notebook-viled.py` | curl_cffi feasibility check для viled.kz (≥10 fetches) | 01-07 |
| `tos-audit.md` | robots.txt + ToS findings + committed rate-limits для обоих сайтов | 01-04 |
| `sample-payloads/` | Образцы HTML/JSON/network-trace, challenge-страницы, error-варианты | 01-05, 01-06, по ходу |

## Locked decisions reference

Все 16 D-XX-решений зафиксированы в `../phases/01-goldapple-reconnaissance-spike/01-CONTEXT.md`. **Любое отклонение — ошибка плана, а не решения исполнителя.**

Ключевые:
- **D-01:** Стартуем с Tier 2 (Patchright). Tier 1 (vanilla) скипаем.
- **D-02:** Hard timebox = 1 week. Если стабильный tier ≤3 не достигнут — вердикт "Tier 4 / managed unblocker".
- **D-03:** Stop-rule = 5 подряд блоков (403/429) или первая Cloudflare/DataDome challenge без auto-resolve → tier failed.
- **D-04:** Persistent (warm) browser context, slow rate (3–5s pause), cookies live across fetches.
- **D-12:** 100-fetch эксперимент = 3–5 брендов из пересечения с viled top-10.
- **D-13:** Threshold = ≥95/100 успехов с разрешёнными 5xx/timeout-ретраями.
- **D-14:** Успешный fetch = HTTP 200 + product JSON-LD в `<script type="application/ld+json">`.
- **D-16:** На завершении спайка — `/gsd-spike --wrap-up` + копия MEMO.md в Obsidian `knowledge/decisions/`.

## Setup notes

`uv` проект инициализируется в **корне репозитория** (`pyproject.toml` в repo root) — Phase 2 переиспользует тот же uv project. См. plan 01-02. Не делайте `uv init` повторно в Phase 2.

`.env.local` (IPRoyal credentials) лежит в repo root, в git **не** коммитится (см. `.gitignore`).
