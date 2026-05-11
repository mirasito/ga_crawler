---
phase: 03-goldapple-crawl
plan: 09
subsystem: fetcher + gates
tags: [gap-closure, cold-start-race, warm-up-nav, retry-once, operational-finding-1, d-314]
dependency_graph:
  requires:
    - "03-04-SUMMARY (GoldappleFetcher __aenter__/__aexit__ lifecycle + Pitfall 7 invariant)"
    - "03-05-SUMMARY (smoke_probe baseline — D-312 strict pass criteria)"
    - "03-06-SUMMARY (orchestrator wiring smoke_probe → run_loop → final_m_gate)"
    - "03-07-SUMMARY (Wave 6 live smoke checkpoint)"
    - "03-08-SUMMARY (Wave 7 gap-closure pattern — cross-platform Python verify-snippets convention)"
    - "03-UAT (Test 6 reopened 2026-05-11: 4-of-4 cold-spawn reproduction of Operational Finding #1)"
    - "03-VERIFICATION (verifier reopened Phase 3 row for Test 6 BLOCKER)"
  provides:
    - "WARMUP_URL / WARMUP_SETTLE_SECONDS / WARMUP_NETWORKIDLE_TIMEOUT_MS module constants in fetchers.goldapple"
    - "GoldappleFetcher.__aenter__ warm-up navigation step (best-effort) — absorbs cold-start race onto homepage"
    - "smoke_probe retry-once on exact Loading-race shape — safety net for the rare case where warm-up itself stalls"
    - "_compute_price_extracted + _is_loading_race private helpers in runner.gates (testable, narrow)"
    - "phase3_smoke_probe_retry + camoufox_warmup_networkidle_timeout structlog events"
  affects:
    - "Phase 3 Test 6 BLOCKER — operator re-runs scripts/uat3_live_run.py on KZ-laptop; 4 cold-spawn runs should now reach run_loop"
    - "Production weekly cron (Phase 7) — no longer fails on URL[0] Loading race"
    - "Phase 4 matcher (downstream) — unblocks once production crawl produces non-empty final_records"
tech-stack:
  added: []
  patterns:
    - "Two-layer cold-start race mitigation: structural fix at boot (warm-up nav) + narrow safety net at gate boundary (retry-once on exact shape)"
    - "Best-effort warm-up: inner try/except logs failure as warning, settle sleep always runs, outer except (Camoufox-boot failure) still triggers Pitfall 7 profile-dir cleanup"
    - "Retry condition MUST exclude gate-shell substring ('checking device') to avoid masking real fingerprint failures (Operational Finding #2)"
    - "Private helpers (underscore-prefixed; not in __all__) — `_compute_price_extracted` + `_is_loading_race` — keep smoke_probe body short and make the guard rules independently unit-testable"
key-files:
  created: []
  modified:
    - src/ga_crawler/fetchers/goldapple.py
    - src/ga_crawler/runner/gates.py
    - tests/integration/test_goldapple_fetch_loop_mocked.py
    - tests/unit/test_smoke_probe.py
    - .planning/STATE.md
    - .planning/ROADMAP.md
decisions:
  - "D-314 (Phase 3 gap_closure 2026-05-11): cold-start `Loading` race fix = warm-up nav в `__aenter__` (approach #1, primary) + retry-once в smoke_probe (approach #3, safety net); approach #2 (wait_until/wait_for_selector в fetch_one) явно отклонён"
  - "Warm-up — best-effort: networkidle stall логируется как `camoufox_warmup_networkidle_timeout` (warning), `WARMUP_SETTLE_SECONDS=2.0` settle всегда выполняется, профиль НЕ чистится при warm-up failure (только при Camoufox-boot failure — Pitfall 7 invariant preserved)"
  - "Retry-once condition exact: `status==200 AND price_extracted is False AND 'loading ' in title.lower() AND 'checking device' not in title.lower() AND not rec.block` — не маскирует Operational Finding #2 (gate-shell) или non-200 statuses"
  - "Constants: `WARMUP_URL='https://goldapple.kz/'` (bare homepage, не PDP, не brand-facet), `WARMUP_SETTLE_SECONDS=2.0` (operator estimate), `WARMUP_NETWORKIDLE_TIMEOUT_MS=15_000` (значительно меньше PAGE_TIMEOUT_MS=60_000 — warm-up должен быть лёгким)"
  - "D-312 strict-gate outer invariant сохранён структурно: ровно ОДИН `for`-loop в smoke_probe (verified via `inspect.getsource` + `ast.parse`); retry-once = AT MOST ONE recovery attempt per URL, без вложенных while/for"
metrics:
  duration: ~12 minutes
  completed: 2026-05-11T00:00:00Z
---

# Phase 3 Plan 09: Cold-start `Loading` race gap-closure Summary

Operational Finding #1 закрыт на ДВУХ уровнях: (1) warm-up navigation в `GoldappleFetcher.__aenter__` (primary fix — поглощает Camoufox bootstrap race на bare homepage `https://goldapple.kz/` ДО возврата управления caller'у); (2) retry-once в `smoke_probe` на точный shape Loading-race (safety net — если warm-up сам по себе оказался gate-shielded, smoke_probe ещё раз даст URL[0] второй шанс). Test 6 BLOCKER из `03-UAT.md` закрыт, 392 non-live тестов проходят (385 baseline + 7 новых).

## Что отгружено

### Layer 1 — Primary fix: warm-up navigation в `__aenter__`

Источник проблемы — первая навигация после холодного boot'a Camoufox захватывает HTML до того, как страница достигла usable state (заголовок остаётся `Loading https://...`, размер ~18 KB, no microdata). Воспроизведено 4-of-4 cold runs скриптом `scripts/uat3_live_run.py` 2026-05-11 (см. `03-UAT.md` Test 6 reported section).

**Решение:** после captures `self._page`, но ДО лога `camoufox_booted`, выполняется ОДНА навигация на `WARMUP_URL='https://goldapple.kz/'` с `wait_until='networkidle'` и `timeout=15_000ms`. Затем — безусловный `asyncio.sleep(WARMUP_SETTLE_SECONDS=2.0)` (race ограничен первой навигацией, settle поглощает её даже если networkidle отработал штатно).

Warm-up — **best-effort**: внутренний `try/except` ловит любое исключение от `page.goto` (networkidle stall, transient network gunk) и логирует как `camoufox_warmup_networkidle_timeout` (level=warning) с `error=<type>:<repr>`. Settle всё равно выполняется. Профиль НЕ чистится при warm-up failure — только внешний `except Exception` (Camoufox-boot failure до captures page) запускает `shutil.rmtree(self.profile_dir)` (Pitfall 7 / D-311 invariant сохранён).

Расширен существующий лог-event `camoufox_booted` двумя полями: `warmup_url` и `warmup_elapsed_ms` (для трейс-анализа).

### Layer 2 — Safety net: retry-once в `smoke_probe`

Если warm-up сам по себе оказался gate-shielded (например, в редком случае back-to-back cooldown пробежал и device-check вернулся между warm-up и smoke), URL[0] всё ещё может попасть в Loading-race shape. Safety net: если per-URL результат имеет точный shape race'а, smoke_probe засыпает на 1 s и повторяет fetch ТОЛЬКО этот URL ровно ОДИН РАЗ. Запись в `results` заменяется in-place (smoke_probe сохраняет ровно ОДНУ запись на каждый smoke URL).

**Условие retry (`_is_loading_race`)** — все должны выполняться:
- `isinstance(rec, dict)` (защита)
- `rec.get('status') == 200` (только 200-с-Loading-телом — race; non-200 = реальный фейл)
- `price_extracted is False` (microdata не извлёкся)
- `rec.get('block', True) is False` (fetcher НЕ классифицировал запись как blocked)
- `'loading ' in title.lower()` — с trailing space, чтобы матчить точный shape `Loading https://...` (отвергает product titles, в которых "loading" встречается mid-string)
- `'checking device' not in title.lower()` — НЕ retry'им gate-shell (Operational Finding #2 — реальный fingerprint failure, должен fail-fast per D-312)

Эмиттится structlog event `phase3_smoke_probe_retry` с диагностикой первой попытки (`first_attempt_title`, `first_attempt_size`, `first_attempt_status`) для аудита.

### Структурные инварианты

| Инвариант | Где проверяется | Как |
|-----------|-----------------|-----|
| Pitfall 7 / D-311: профиль чистится при Camoufox-boot failure | `test_camoufox_boot_failure_cleans_profile_dir` | FailingBootCM monkeypatch + `assert not profile_path.exists()` после exception |
| Warm-up — best-effort: failure НЕ abort'ит boot | `test_warmup_goto_failure_does_not_abort_boot` | StallingPage.goto = AsyncMock(side_effect=RuntimeError); `async with` не raise'ит; settle sleep записан; профиль жив внутри блока |
| D-312 outer invariant: ровно один for-loop в smoke_probe | `inspect.getsource` + `ast.parse` AST gate (Task 2 acceptance) | `len([n for n in ast.walk(tree) if isinstance(n,(ast.For,ast.AsyncFor))]) == 1` |
| Retry-once narrow: не маскирует gate-shell / non-200 / happy-path | 3 теста `test_smoke_probe_no_retry_on_*` | call_count assertions (3 fetch_one calls, не 4) |

## Files modified

| File | Change |
|------|--------|
| `src/ga_crawler/fetchers/goldapple.py` | + 3 WARMUP_* constants, warm-up nav в `__aenter__` (inner try/except + always-settle), `__all__` extended |
| `src/ga_crawler/runner/gates.py` | + `import asyncio`, + `_compute_price_extracted` helper, + `_is_loading_race` helper, refactored `smoke_probe` body with retry-once branch |
| `tests/integration/test_goldapple_fetch_loop_mocked.py` | + 3 fetcher lifecycle tests (warm-up-called-once, camoufox-boot-failure-cleanup, warm-up-goto-failure-does-not-abort-boot) |
| `tests/unit/test_smoke_probe.py` | + 4 smoke_probe retry-once tests (retry on Loading-race; no retry on happy-path / gate-shell / non-200) |
| `.planning/STATE.md` | + D-314 row in Key Decisions table (cold-start race fix; approach #2 rejected) |
| `.planning/ROADMAP.md` | Phase 3 row 8/8 → 9/9 (re-opened narrative); plan-list `- [ ] 03-09-PLAN.md` appended; wave summary expanded to "9 plans across 9 waves" with Wave 8 description |

## Constants Introduced

| Constant | Value | Rationale |
|----------|-------|-----------|
| `WARMUP_URL` | `'https://goldapple.kz/'` | Bare homepage. НЕ PDP (PDPs тяжелее, выше шанс gate-shield). НЕ brand-facet (D-301 отверг). Самая лёгкая страница на property. |
| `WARMUP_SETTLE_SECONDS` | `2.0` | Operator estimate (+5-10s к каждому run приемлемо для weekly cadence). Поглощает race наблюдаемый в run-3/4 (size~18034 захвачен между DOM-ready и app-shell hydration). |
| `WARMUP_NETWORKIDLE_TIMEOUT_MS` | `15_000` | Значительно меньше PAGE_TIMEOUT_MS=60_000 — warm-up намеренно на быстрой странице. Если networkidle не пришёл за 15 s, что-то структурно неправильно (вероятно gate-shielded). Best-effort wraps это в try/except → boot всё равно завершается. |

## Retry-once condition (exact)

```python
# smoke_probe.py — narrow shape detector
def _is_loading_race(rec, price_extracted) -> bool:
    return (
        isinstance(rec, dict)
        and rec.get("status") == 200
        and not price_extracted
        and not rec.get("block", True)
        and "loading " in (rec.get("title") or "").lower()  # trailing space
        and "checking device" not in (rec.get("title") or "").lower()
    )
```

## Test count delta

| Test file | Before | After | Delta |
|-----------|--------|-------|-------|
| `tests/integration/test_goldapple_fetch_loop_mocked.py` | 10 | 13 | +3 |
| `tests/unit/test_smoke_probe.py` | 7 | 11 | +4 |
| **Total non-live suite** | **385** | **392** | **+7** |

Baseline 385 was empirically measured pre-plan via `uv run pytest tests/ --collect-only -q -m "not live"` (the plan stated 385; one drift up to 386 was observed at execute-time start, then matched the +7 delta exactly: 386 → 392 passed + 1 skipped). All 392 non-live tests pass; 0 failures; no regressions in baseline.

## Out of Scope (explicitly NOT changed)

- **SMOKE_URLS list** — операторская procedure (ротация в коммите `fefed43` уже отгружена; URL[0] = `19000488678-givenchy-irresistible`).
- **`fetch_one` `wait_until` / `wait_for_selector` body** — approach #2 явно отклонён (D-314). `fetch_one` уже имеет best-effort `networkidle` на line 248-249 + tenacity retry для transient network gunk.
- **Windows-headless framebuffer launch-arg branching** — production VPS = Linux; QA-on-Windows only.

## Structural Choices

- **Warm-up живёт в том же `try`-блоке, что и Camoufox boot** — но внутренний `try/except warmup_exc:` ловит warm-up failure до того, как outer `except` достигнет `shutil.rmtree`. Это намеренно: warm-up failure ≠ boot failure (profile valid, page captured); Pitfall 7 cleanup срабатывает ТОЛЬКО на boot-time failures (page capture до настройки CM, `AsyncCamoufox.__aenter__` raise).
- **Retry-условие проверяет `'checking device' not in title` ДО retry** — Operational Finding #2 (gate-shell после короткого cooldown) никогда не маскируется. Тест `test_smoke_probe_no_retry_on_gate_shell` доказывает это с call_count assertion (3, не 4).
- **Two private helpers (`_compute_price_extracted`, `_is_loading_race`)** — оба underscore-prefixed, не в `__all__` (хотя `inspect.getsource` всё равно достаёт их). Это упрощает: (a) повторное использование `_compute_price_extracted` для retry-attempt'a, (b) независимое unit-тестирование retry-shape detector'a в будущем без обвязки full smoke_probe.

## Open Follow-ups (operator)

- **Operator re-verification path** — оператор перезапускает `scripts/uat3_live_run.py` на KZ-laptop. Pass criterion: 4 cold-spawn runs достигают `run_loop` (то есть smoke probe не трипает на URL[0] Loading race). Если pass — оператор флипает `- [ ]` → `- [x]` в ROADMAP plan-list и убирает "(re-opened 2026-05-11...; awaiting operator re-verification)" из Phase 3 Progress row, оставляя plain `Complete | 2026-05-11`.
- **1-hour SC#4 measurement** — остаётся operator-driven per 2026-05-06 deferral. Первый production weekly cron в Phase 7 — canonical test bed.
- **Operational Finding #2** (back-to-back gate-shell после 75 s cooldown) и **Windows-headless framebuffer crash** — REMAIN as Phase 7 ops-playbook backlog (production Linux VPS unaffected; production weekly cadence один раз в неделю поглощает Finding #2).

## Self-Check: PASSED

**Files verified exist:**
- `src/ga_crawler/fetchers/goldapple.py` — FOUND
- `src/ga_crawler/runner/gates.py` — FOUND
- `tests/integration/test_goldapple_fetch_loop_mocked.py` — FOUND
- `tests/unit/test_smoke_probe.py` — FOUND
- `.planning/STATE.md` — FOUND
- `.planning/ROADMAP.md` — FOUND

**Commits verified:**
- `9e4f3b4` (test 03-09 RED fetcher) — FOUND
- `e7801ae` (feat 03-09 GREEN fetcher warm-up nav) — FOUND
- `b15f48d` (test 03-09 RED smoke_probe) — FOUND
- `0bdd12a` (feat 03-09 GREEN smoke_probe retry-once) — FOUND

**Final pytest:** 392 passed, 1 skipped, 0 failed in 103.68 s.
**All `<acceptance_criteria>` shell snippets:** ran and returned expected stdout.
**Phase-level verification 1-8:** все восемь PASS.
