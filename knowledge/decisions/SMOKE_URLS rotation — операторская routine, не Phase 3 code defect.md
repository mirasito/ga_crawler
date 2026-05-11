---
tags: [decision, smoke-urls, ops-routine, phase-3, phase-7, rotation]
date: 2026-05-11
type: operational-procedure
status: in-force
---

# SMOKE_URLS rotation — операторская routine, не Phase 3 code defect

## Решение

**SMOKE_URLS (3 hardcoded Givenchy URLs в `src/ga_crawler/runner/gates.py:32`) ротируется оператором как Phase 7 ops-playbook procedure** — не как Phase 3 fix-plan. Каждая ротация — отдельный atomic commit с тегом `ops(03)` (НЕ `feat`, НЕ `fix`), описывающий какой SKU протух и какой пришёл на замену.

## Контекст / почему

`SMOKE_URLS` — это **гипотеза о живости 3 конкретных Givenchy SKU**. Со временем SKU удаляются из ассортимента → URL'ы начинают 30x редиректить на homepage → smoke probe возвращает generic title size~9KB → smoke gate fails по причине, не связанной с anti-bot или code-level bug'ом. Это **data drift**, а не software defect.

Коммент прямо в коде (gates.py:29-30) обозначает это как операторскую процедуру:

```python
# 3 known-good Givenchy URLs from spike (A12: avoid spike row 0 = 7681000002 stale).
# Operator updates these via Phase 7 ops-playbook rotation procedure.
```

То есть **ещё на стадии spike 2026-05-06** команда явно проектировала SMOKE_URLS как rotation-friendly константу с человеческой responsibility за свежесть.

## Первая ротация — 2026-05-11

Phase 3 UAT Test 6 (re-opened 2026-05-11) обнаружил `SMOKE_URLS[0]` = `7680100018-very-irresistible-givenchy` протух:
- run-2: title "ЗОЛОТОЕ ЯБЛОКО — интернет-магазин..." size=9587 (30x to homepage)
- run-42 (2026-05-06): тот же pattern, size=9570

SKU был удалён из ассортимента в окне 2026-04 .. 2026-05. Заменено на `19000488678-givenchy-irresistible` — взят прямо из live 52,044-slug sitemap, гарантирующего наличие URL'а в текущем индексе.

Commit: `fefed43` ops(03): rotate SMOKE_URLS[0] — stale Givenchy SKU replaced

## Почему НЕ Phase 3 fix-plan

| Признак | SMOKE_URLS rotation | Phase 3 fix-plan материал |
|---|---|---|
| Источник проблемы | Data drift (товар удалён) | Code defect (race condition, неправильный wait, etc.) |
| Кто решает | Оператор (смотрит в sitemap, выбирает живой SKU) | Engineer (читает код, ищет root cause) |
| Что меняется | Литерал в `SMOKE_URLS` tuple | Логика fetch/parse/gate/orchestrator |
| Артефакт | Atomic commit `ops(03):` | PLAN.md → SUMMARY.md → execute |
| Тестирование | Re-run smoke probe вручную | Test suite в Phase 3 plan |
| Каденс | По мере drift'a (ad-hoc, раз в N месяцев) | Plan/execute cycle (одноразово) |

## Когда применять

**Применять rotation** если:
- Один из SMOKE_URLS возвращает status=200 + size<20KB + title `"ЗОЛОТОЕ ЯБЛОКО — интернет-магазин косметики и парфюмерии"` (= goldapple generic homepage)
- Прямой `curl -I {URL}` показывает 301/302 на корень goldapple.kz
- Другие 2 URL в SMOKE_URLS возвращаются нормально (size 200-500 KB, реальный product title) — изолирует проблему от anti-bot/race условий

**НЕ применять rotation** если:
- Все 3 URL вернули gate-shell (block=true, "checking device") — это [[Anti-bot transient gate-shell на быстрых Camoufox cold-spawns]], не data drift
- Только URL[0] failed с "Loading" prefix в title — это [[Cold-start `Loading` race на первой навигации после Camoufox boot]], code defect, требует fix-plan
- URL'ы возвращаются с реальными product titles но без `<meta itemprop="price">` — это [[Goldapple показывает Cloudflare-челлендж — эскалация tier]] или parser regression

## Процедура (Phase 7 ops-playbook canonical)

```bash
# 1. Запустить sitemap probe — взять live Givenchy URL'ы:
uv run python -c "
from ga_crawler.enumeration.goldapple_sitemap import fetch_sitemap_slugs
sm = fetch_sitemap_slugs()
for slug in sorted(s for s in sm if 'givenchy' in s)[:10]:
    print(f'{slug}: {sm[slug][0]}')
"

# 2. Выбрать 3 URL'а из разных SKU-семей (избегать too-similar; D-312 spike A12 rationale)

# 3. Curl-проверить каждый: status=200, title содержит "Givenchy", body ≥100 KB:
curl -sL https://goldapple.kz/{NEW_URL} | grep -oE '<title>[^<]+</title>' | head -1

# 4. Замена в src/ga_crawler/runner/gates.py:32 — обновить tuple

# 5. Update комментарий — добавить "Rotation YYYY-MM-DD: index N (old → new)"

# 6. Atomic commit:
#    git add src/ga_crawler/runner/gates.py
#    git commit -m "ops(03): rotate SMOKE_URLS[N] — {reason}"

# 7. Re-run smoke probe для verification:
#    uv run python -m ga_crawler goldapple-smoke
```

## Альтернативы рассмотренные

| Альтернатива | Почему отклонена |
|---|---|
| Загружать SMOKE_URLS из `config/smoke_urls.txt` (run-time config) | `load_smoke_urls_from_config()` уже существует (gates.py:39) как opt-in fallback. Но default остаётся hardcoded SMOKE_URLS — это сознательно: hardcoded гарантирует reproducibility test fixtures + spike A12 baseline. Config file дополняет, не заменяет. |
| Auto-rotate (cron job делает sitemap probe + обновляет SMOKE_URLS если найден stale) | Излишняя automation. Drift редкий (раз в месяцы). Operator-eye-on-glass дешевле + добавляет human review слой для catch других regression types. |
| Динамический выбор из текущего sitemap'а (каждый run sample'ит 3 свежих Givenchy URL'а) | Smoke probe **должна** быть stable baseline. Если URL'ы меняются каждый run, мы теряем сравнимость диагностики между runs. Defeats purpose. |

## Connections

- [[Anti-bot transient gate-shell на быстрых Camoufox cold-spawns]] — другой класс smoke probe failure, requires cooldown not rotation
- [[Cold-start `Loading` race на первой навигации после Camoufox boot]] — другой класс smoke probe failure, requires code fix not rotation
- [[Fresh Camoufox profile per run + integrated smoke probe]] — D-311 + D-312 контекст для smoke probe protocol
- [[2026-05-11 — Phase 3 UAT Test 6 re-opened, SMOKE_URLS rotation + cold-start race promoted]] — session где впервые применили процедуру

## Файлы

- `src/ga_crawler/runner/gates.py:32` — `SMOKE_URLS` constant
- `src/ga_crawler/runner/gates.py:39` — `load_smoke_urls_from_config()` opt-in override
- `config/smoke_urls.txt` (опциональный) — не создан, но supported
- Commit `fefed43` — первая ротация 2026-05-11
