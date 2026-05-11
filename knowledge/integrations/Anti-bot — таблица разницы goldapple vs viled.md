---
tags: [integration, anti-bot, comparison, goldapple, viled, security]
date: 2026-05-06
source: Phase 1 spike empirical findings + Phase 3 production code
---

# Anti-bot — таблица разницы goldapple vs viled

Источник: Phase 1 spike (15/15 viled trivial vs 99/100 goldapple после Camoufox+KZ-IP) + Phase 3 production-код (192 теста). Цифры эмпирические, не теория.

## Главная таблица — слой за слоем

| # | Слой защиты | goldapple.kz | viled.kz | Чем мы это обходили (на goldapple) |
|---|---|---|---|---|
| 1 | **TLS / JA3 fingerprint** | ✅ Есть. Python `requests` (urllib3) → `HTTP 403` мгновенно. WAF читает TLS-handshake подпись. | ❌ Нет. Голый urllib3 → `HTTP 200`. Не проверяется. | `curl_cffi` с `impersonate="chrome"` (Chrome 136 TLS+JA3) |
| 2 | **HTTP/2 fingerprint (Akamai-style)** | ✅ Есть (входит в #1). Порядок HEADERS/SETTINGS frames проверяется. | ❌ Нет. | curl_cffi покрывает автоматически |
| 3 | **JS-rendering required** | ✅ Цена и часть полей появляются после выполнения клиентского JS. Statiс HTML — частичный. | ❌ Нет. Весь товарный JSON в `__NEXT_DATA__` block прямо в HTML. `curl + grep` достаёт всё. | Headless Chromium / Firefox |
| 4 | **Browser fingerprinting** (Canvas, WebGL, AudioContext, Fonts, Screen, Plugins) | ✅ Активный. ~100 отпечатков клиентского окружения отправляются на сервер. Vanilla Playwright детектируется по характерным паттернам Chromium-headless. Patchright тоже не прошёл. | ❌ Нет. | **Camoufox** — форк Firefox с C++-патчами на gecko-уровне. Spoof'ит каждый отпечаток. |
| 5 | **Cookie-fingerprint + behavioral** | ✅ Возвращающийся клиент с теми же cookies, но другим IP/UA → подозрение. Mouse-move / scroll patterns анализируются. | ❌ Нет cookies-сессии для anonymous traffic. | Fresh tmp-профиль на каждую SKU + `humanize=True` (mouse/scroll) |
| 6 | **Geo-IP проверка** | ✅ EU/US datacenter IP'ы получают усиленный challenge. KZ-residential проходит. RU-residential частично. | ❌ Нет. Любой IP → 200. | KZ-laptop direct + резерв IPRoyal KZ-residential ($2/нед) |
| 7 | **Rate-limit + soft-throttling** | ✅ >1 RPS с одного fingerprint → 429 / cool-down 5 мин. | ❌ Не наблюдается. 15 sequential GET без задержек → 15× 200 OK. | 3-5 сек random pause + tenacity exponential backoff с jitter |
| 8 | **JS challenge / CAPTCHA** | ✅ Включается на подозрительный трафик (interstitial). | ❌ Нет. | Camoufox решает passively (просто рендерит страницу) |
| 9 | **Gate-shell pattern** (HTTP 200 + 18KB заглушка вместо 403) | ✅ WAF не отдаёт 403, а возвращает 200 с пустой страницей `title="Gold Apple — checking device"` — наивные scrapers молча получают мусор. | ❌ Нет. | Three-axis state classifier (real-pdp / gate-shell / stale-sku) + smoke probe перед каждым crawl |
| 10 | **Anti-bot vendor / WAF** | ✅ **F.A.C.C.T.** (бывш. Group-IB Fraud Hunting Platform). Российский enterprise fraud-prevention. Benchmark'и Patchright против Cloudflare/DataDome не применимы — другая система. | ❌ Никакого WAF (ни Cloudflare, ни DataDome, ни F.A.C.C.T., ни Imperva, ни Akamai). | Только Camoufox + KZ-IP комбинация прошла |
| 11 | **CDN L7 защита** | ✅ Активна (vendor-specific). | ❌ Нет видимой CDN-защиты. | (см. #10) |
| 12 | **Behavioral analytics** (mouse, touch, scroll patterns) | ✅ Часть #4 + #5 vendor-стека. | ❌ Нет. | `humanize=True` в Camoufox — синтетические mouse/scroll события |
| 13 | **Authentication wall на товарных страницах** | ❌ Нет (товары публичны, что correct для retail). | ❌ Нет (correct). | n/a |
| 14 | **`robots.txt` агрессивный** | ⚠️ Базовый, не блокирует автоматизацию. | ⚠️ Базовый Next.js default. | n/a (мы соблюдаем robots.txt) |
| 15 | **Hot-link protection (фоторесурсы)** | ✅ Активна (CORS/Referer check). | ❌ Не наблюдалось. | Не использовали — фото нам не нужны |
| 16 | **Server-side data filtering** (что не отдавать клиенту вообще) | ✅ Цена / остатки приходят отдельным API-вызовом, не в начальном HTML. | ❌ **`__NEXT_DATA__` отдаёт весь объект**: бренд, цена, sku, остатки, описание, фото-URLs, иногда внутренние SKU-id'ы и складские метаданные. | Не нужно обходить — данные сами в HTML |
| 17 | **Per-product structural variance (защита от парсера)** | ⚠️ Не намеренно anti-bot, но: микроданные (price, brand, name) разбросаны по PDP в разной структуре по категориям/промо/Gold Card. Reverse-engineering — отдельная задача. | ❌ `__NEXT_DATA__` всегда одной структуры — Next.js generates it автоматически. | Парсер с 3-axis state, priceType discrimination, gold-card heuristic, longest-prefix bucket — 192 теста |

## Сводный итог

| Метрика | goldapple | viled |
|---|---|---|
| **Слоёв защиты** | 12 активных | 0 значимых |
| **Стек скрейпера** | Camoufox 135.0.1-beta.24 + KZ-IP + 3-5s pause + per-SKU profile + retry + smoke probe + state classifier + 192 теста на парсер | `curl_cffi + selectolax + json.loads(NEXT_DATA)` |
| **Размер скрейпера** | ~250 MB Camoufox binary + ~50 коммитов кода + 8 waves | ~10 строк Python |
| **Время разработки** | ~4 недели + 1 неделя research | ~10 минут |
| **Стоимость / неделя** | $0–2 (proxy резерв) + ~5.5 часов sequential crawl | ~$0 + минуты |
| **Успех (Phase 1 spike)** | 99/100 (после Camoufox win) | 15/15 (100%) |
| **Маневренность атакующего** | Низкая. Каждый Camoufox upgrade — риск регрессии. | Полная. Любой stack работает. |

## Где пробивается даже сейчас (Wave 6 ops findings)

Даже после всех 12 слоёв goldapple теряется в двух operational regime'ах:

1. **Rapid Camoufox cold-spawns с одной IP** (≥3 в 10 минут) → transient gate-shell. 60-сек cooldown снимает. Production weekly cron unaffected.
2. **Парсер обходов структурных edge case'ов** (gold-card heuristic + multi-bare-priceMeta) — Wave 6 поймал, Wave 7 закрыл. Это уже не anti-bot, а structural reverse-engineering.

## Что это значит для viled

См. [[../../docs/viled-anti-bot-recommendations.html]] (на диске, 38 KB):

- **T0** (гигиена `__NEXT_DATA__` + robots.txt): 1-2 дня, ~0₸ → закрывает строку #16 (главная утечка)
- **T1** (Cloudflare Free + Bot Fight Mode + rate-limit): 1 нед, $0-20/мес → закрывает строки #1, #2, #7, частично #3, #8, #9, #10
- **T2** (Cloudflare Pro + JS challenge + FingerprintJS): 1 мес, $200-500/мес → закрывает #4
- **T3** (DataDome / Imperva): $2-10K/мес → анти-anti-detect-browser tier
- **T4** (F.A.C.C.T. — то же что у goldapple): $10-30K/мес — overkill для viled на 2026

**Прагматика для viled:** T0+T1 за 2-3 недели и $0-20/мес закроет ~95% script-kiddies и automated competitor-tooling. T2+ только когда логи покажут устойчивые попытки обхода T1.

## Connections

- [[goldapple.kz — источник цен конкурента]]
- [[viled.kz — собственный каталог и источник пересекающихся брендов]]
- [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]]
- [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]]
- [[Anti-bot transient gate-shell на быстрых Camoufox cold-spawns]]
- [[Тиры anti-bot эскалации]]
