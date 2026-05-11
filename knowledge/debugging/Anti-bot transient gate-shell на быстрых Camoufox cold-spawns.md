---
tags: [debugging, anti-bot, camoufox, ops, phase-7-backlog, gate-shell, goldapple]
date: 2026-05-06
severity: ops-only
production_impact: none
---

# Anti-bot transient gate-shell на быстрых Camoufox cold-spawns

## Симптом

Smoke probe возвращает `passed: false` на всех 3 SMOKE_URLS одновременно. В diagnostics:

```json
{
  "url": "https://goldapple.kz/...",
  "status": 200,
  "size": 18057,
  "title": "Gold Apple — checking device",
  "block": true,
  "price_extracted": false
}
```

Все 3 URL дают **HTTP 200 + ~18 KB body + title "Gold Apple ... checking device"** — гейт-shell pattern. Goldapple anti-bot (F.A.C.C.T.) не отдаёт 403, а возвращает 200 с заглушкой «checking device». State classifier'ом помечается как `gate-shell`, `block=true`.

## Когда воспроизводится

Wave 6 live-smoke, 2026-05-06: после 3 cold-spawn'ов Camoufox в течение ~10 минут с одного KZ-IP — третий и далее запуски попадают в transient gate. Pattern наблюдался дважды:
1. После 2 успешных smoke probe + 1 fail (smoke probe внутри orchestrator), **всего 3 cold-spawn за ~10 мин**.
2. После повторного smoke probe + run-43 orchestrator smoke (warm-up), **всего 2 cold-spawn за ~3 мин**.

**Обновление 2026-05-11 (UAT Phase 3 Test 6 re-attempt):** 75-сек cooldown также **недостаточен** для надёжного снятия gate в плотной дебаг-сессии. Run-5 (75 сек после run-4) попал в gate-shell на все 3 URL. Новая нижняя граница безопасного cooldown в debug-сессии — **≥15 мин**, а не 60 сек как предполагалось раньше. 60-сек цифра остаётся валидной как **минимум** при условии "не больше 2 cold-spawn'ов в окно", но при 3+ spawn'ах нужны кратно более длинные паузы или fresh fingerprint.

**Не воспроизводится** при:
- 60-сек cooldown между **первыми двумя** cold-spawn'ами с одной IP → второй probe обычно нормален. На третьем за окно ~5 мин — гарантированно gate.
- ≥15-мин cooldown между cold-spawn'ами в debug-сессии — empirically clean.
- Production cron-cadence (1 run/нед, 3-5s rate-limit на product fetch) — здесь cold-spawn'ов вообще нет внутри одного run'а, и 7-дневный gap между weekly run'ами далеко за пределами F.A.C.C.T. rate-окна.

## Root cause (гипотеза)

F.A.C.C.T. fingerprint engine следит за частотой **новых** browser fingerprint'ов с одной IP. Каждый Camoufox cold-spawn даёт фресный fingerprint (D-311 mandates fresh tmp profile per run). 3 fresh fingerprint'а за 10 минут с одной IP triggers heuristic «automated rotation» → temporary block (`gate-shell` соответствует Cloudflare Bot Fight pattern, но F.A.C.C.T. может это imitate).

Не browser-fingerprint regression: тот же Camoufox 0.4.11, тот же KZ-IP, те же 3 SMOKE_URLS — после 60-сек cooldown работает нормально. Это **rate-based**, не fingerprint-based.

## Production impact

**Никакого.** Production weekly cron делает:
- 1 run / неделя
- 1 cold-spawn Camoufox в начале run'а
- 1 smoke probe с этого spawn'а
- ~5.5 часа sequential fetches с rate-limit 3-5 сек (тот же fingerprint, не cold-spawn)

Это **далеко** ниже rate, который triggers transient gate. Phase 1 spike прошёл 100 sequential fetches без gate-shell на той же конфигурации.

Transient gate triggers только на **manual debugging/testing**, когда developer прогоняет несколько smoke probe подряд.

## Workaround / mitigation

**Для debugging session:**

```bash
# После каждого smoke probe / orchestrator run:
echo "60s cooldown..." && sleep 60
# Затем следующий запуск
```

Эмпирически 60 сек снимает gate. 30 сек — недостаточно. 5 минут — гарантированно.

**Для CI / automated tests:**

Не запускать live smoke probe чаще раз в 5 минут. Mocked tests (`tests/unit/`, `tests/integration/`) используют fixtures, не trigger'ят live network.

**Для production monitoring:**

Если weekly cron production run возвращает `gate-shell_count / fetch_count > 5%` устойчиво (несколько недель подряд), это **уже не transient** — это либо real anti-bot regression, либо что-то изменилось в F.A.C.C.T. tier. Тогда эскалация до Tier 3 (residential proxy KZ) per spike MEMO.

## Phase 7 ops-playbook backlog

1. Cron alert if `goldapple.gate_shell_count / fetch_count > 5%` (sustained)
2. Documentation для operator: «Если debugging — пауза ≥60 сек между smoke probe runs»
3. Orchestrator smoke probe нуждается в warm-up wait после Camoufox boot (URL[0] caught mid-load в run-43 — это другой тип гонки, см. Finding #6 в Wave 6 SUMMARY)

## Related findings

Wave 6 live-smoke также поймал:
- **Finding #1 (parser):** Парсер микроданных fail на bonus-button «при авторизации» (FIXED inline, commit `277a40a`) — отдельный класс, parser bug, не anti-bot.
- **Finding #6 (sub-finding в Phase 7 backlog):** Orchestrator smoke probe ловит URL[0] в `Loading` state мгновенно после Camoufox boot — race condition warm-up. Это другой класс ошибки, не gate-shell — нужен `await page.wait_for_load_state` перед probe'ом или 1-2 сек warm-up wait. **Обновление 2026-05-11:** воспроизведено 4 из 4 раз на cold-start; повышено из ops-backlog в Phase 3 production-blocking defect — отдельная debugging note [[Cold-start `Loading` race на первой навигации после Camoufox boot]].

## Connections

- [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]]
- [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]] — production-baseline rate (1/нед) ниже trigger threshold
- [[2026-05-06 — Phase 3 closed через Wave 6 live-smoke + Wave 7 gap-closure]]
- D-311 fresh profile lifecycle — corollary: fresh fingerprint per cold-spawn делает rapid cold-spawns детектируемыми

## Файлы для проверки

- `src/ga_crawler/runner/gates.py` — `smoke_probe()` (D-312 fail-fast logic)
- `src/ga_crawler/parsers/goldapple_microdata.py` — `detect_state()` (gate-shell classification: title contains "checking" + size < 30000)
- `tests/fixtures/goldapple/gate-shell.html` — fixture для тестирования gate-shell detection
