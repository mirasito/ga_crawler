---
tags: [priorities, phase-3, plan-09, operator-uat, human-needed, next-up]
date: 2026-05-11
supersedes: "Текущие приоритеты — Phase 3 Finding 1 → plan-gaps"
---

# Текущие приоритеты — Phase 3 plan 09 shipped, ждём operator UAT

## Где мы

**Phase 3 plan 03-09 закрыт structurally 2026-05-11** (вторая половина дня). Cold-start `Loading` race гасится через warm-up navigation в `__aenter__` (Layer 1) + retry-once в `smoke_probe` (Layer 2). 8 atomic commits на `master`, +7 net tests (385 → 392 passed). Code review поймал 1 Critical (CR-01 — gate-shell marker не использовал канон `GATE_TITLE_MARKER`); зафиксировано тем же днём, commit `05b29a8`.

Verifier verdict: **`human_needed`**, score 5/5 must_haves verified структурно. Phase 3 не закрылась окончательно — ждём оператор live re-run.

## Что дальше — ОДНА команда

Operator (на KZ-laptop, cold Camoufox spawn):

```bash
uv run python scripts/uat3_live_run.py
```

Pass criterion (zelf-checking):
- 4 cold-spawn runs **все** достигают `run_loop` (а не упираются в smoke_probe)
- `.planning/runs/{N}/runs.json` каждого run содержит `camoufox_booted` event с `warmup_url` + `warmup_elapsed_ms` полями
- ни один URL[0] не возвращает `"Loading https://..."` title + price_extracted=false

### На PASS

```
/gsd-verify-work 3
```

→ оператор флипает Test 6 `result: pass`, убирает Gaps entry в `03-UAT.md`, frontmatter status: partial → complete. Phase 3 закрывается окончательно. Затем:

```
/clear
/gsd-discuss-phase 4
```

Phase 4 — **Matcher + Match-Rate KPI** (MATCH-01..04). Phase 2 storage и normalizers уже на месте, Phase 3 snapshots будут поступать с первой production cron.

### На FAIL

Capture новые run logs, файлинг `/gsd-verify-work 3` против обновлённого `03-UAT.md`. Verifier маршрутизирует на одно из:
- ещё один gap-closure plan (если новая failure shape) → `/gsd-plan-phase 3 --gaps`
- Phase 7 ops-playbook escalation (если это уже не Phase 3 code defect, а operational concern)

## Что НЕ делать сейчас

- **Не двигаться к Phase 4** до оператор-confirmation — Phase 3 в `human_needed`, не `passed`. Match-rate KPI без Phase 3 snapshots = 0 от недели 1.
- **Не закрывать 5 открытых Warning'ов в `03-REVIEW.md` параллельно** — они non-blocking; делаем одним отдельным циклом `/gsd-code-review 3 --fix` перед milestone close.
- **Не запускать ещё один live run в этой же session window** — F.A.C.C.T. transient gate (Finding #2) активируется на back-to-back cold-spawns; нужен ≥15 мин cooldown между UAT-попытками.
- **Не убирать `headless=False`** в `scripts/uat3_live_run.py` — Windows framebuffer crash остаётся (production VPS Linux не страдает).

## Open code-review findings (когда руки дойдут — не сегодня)

- **WR-01:** `asyncio.sleep(1.0)` в smoke_probe не injectable; тесты платят 1s wall-clock
- **WR-02:** `_compute_price_extracted` зовёт `parse_pdp` без try/except — schema drift = uncaught exception
- **WR-03:** нет post-retry event для outcome — slow regressions в retry helpfulness невидимы до полного fail
- **WR-04:** `WARMUP_SETTLE_SECONDS = 2.0` magic number без обоснования измерением
- **WR-05:** pre-existing `_make_retry_decorator` ImportError fallback (вне scope плана 03-09)
- IN-01..04 — nice-to-have (unused tuple element, dead price check, label drift, missing back-off assert)

Команда для закрытия: `/gsd-code-review 3 --fix` после оператор-pass. Это **должно быть отдельным циклом**, не смешиваться с Phase 4 planning.

## Что Phase 7 уже владеет (не наша забота сейчас)

- **Operational Finding #2** (back-to-back gate-shell после короткого cooldown) — production weekly cadence не увидит; backlog
- **Windows headless framebuffer crash** — local QA-only; production Linux unaffected

## Side-quest

- `docs/viled-anti-bot-recommendations.html` всё ещё untracked
- Untracked Obsidian-заметки накопились — сегодняшняя сессия добавила +3 файла (session note + этот файл + cold-start race resolution update). Закоммитим разом следующим `docs(99): save session`.

## Connections

- [[2026-05-11 — Phase 3 plan 03-09 ships, cold-start race закрыт structurally]] — session note сегодня (PM)
- [[Cold-start `Loading` race на первой навигации после Camoufox boot]] — root cause + Resolution section
- ~~[[Текущие приоритеты — Phase 3 Finding 1 → plan-gaps]]~~ — superseded (plan-gaps выполнен; теперь ждём operator UAT)
- [[.planning/phases/03-goldapple-crawl/03-UAT|03-UAT.md]] · [[.planning/phases/03-goldapple-crawl/03-VERIFICATION|03-VERIFICATION.md]] · [[.planning/phases/03-goldapple-crawl/03-REVIEW|03-REVIEW.md]]
- [[scripts/uat3_live_run|scripts/uat3_live_run.py]]
- [[.planning/PROJECT|PROJECT.md]] · [[.planning/ROADMAP|ROADMAP.md]] · [[.planning/STATE|STATE.md]]
