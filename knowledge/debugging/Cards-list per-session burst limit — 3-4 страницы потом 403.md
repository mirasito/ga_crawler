---
tags: [debugging, anti-bot, rate-limit, cards-list, retry-hardening]
date: 2026-05-16
---

# Cards-list per-session burst limit — 3-4 страницы потом 403

## Симптом

`enumerate_brand_via_api` для крупных брендов (badge ≥ 100, требует 5+ pages of pagination) **консистентно** ловит HTTP 403 на 4-й cards-list XHR в session. Pattern наблюдался на armani, bobbi-brown, mac, clarins, clinique, zielinski_rozen во всех трёх прогонах 2026-05-16.

run-19 v2 example для zielinski-rozen (badge=340, требует 17 pages):
```
page 1: OK     (200, 20 cards)
page 2: OK     (200, 20 cards)
page 3: OK     (200, 20 cards)
page 4: 403    ← burst limit triggered
```

## Root cause

Cards-list endpoint имеет **per-session burst rate-limit** ~3-4 requests за короткий промежуток. Cookies, fingerprint и IP не помогают — это per-session ceil, скорее всего sliding window типа «N запросов за M секунд».

Старый retry-код:
```python
consecutive_403 += 1
if consecutive_403 > 2: break   # ← бросал весь бренд
await page.wait_for_timeout(12_000)
result = await _fetch_page(page_num)
if result.get("status") == 403: break   # ← после single retry
```

Эффект: после 1 неудачной retry (всё ещё 403) бросал ВЕСЬ бренд. zielinski_rozen терял 14 unread страниц = ~280 SKU.

## Fix — 5 рычагов

1. **Base inter-page delay 2.8s → 4.0s.** Более conservative pacing подальше от threshold.

2. **Per-page retry 1 → 3 attempts с exponential backoff `[12s, 24s, 48s]`.** Иногда нужно подождать существенно дольше чем 12s чтобы rate-counter спал.

3. **Skip-page-on-403 instead of break-brand.** Это ключевое изменение. Логика: pageN failure не означает page(N+1) тоже failed — они отдельные cache-lookups server-side. После exhaust per-page retries — `continue` to next pageNumber вместо `break` from brand. Дополнительно `await wait_for_timeout(inter_page_delay_ms * 2)` для отдыха.

4. **Per-brand 403 budget = 12** (всего 403 across all pages). Защита от полностью заблоченного бренда — иначе indefinite retry loop.

5. **Anti-burst cooldown:** после `pages_per_burst=3` успешных pages — `await wait_for_timeout(20_000)` ПЕРЕД page 4. Empirically 403 ловится на 4-й request → cooldown ДО 4-го должен сбить rate-counter.

## Verified outcomes

После hardening + targeted recovery на run-19:

| Brand | До v3 | После v3.1 | badge | coverage |
|---|---:|---:|---:|---:|
| zielinski_rozen | 100 | 320 | 340 | 94% |
| MAC | 98 | 212 | 176 | 100%+ (multi-variant top-up) |
| clarins | 40 (scroll) | 248 | 248 | 100% |
| clinique | 40 (scroll) | 219 | 220 | 99.5% |
| bobbi-brown | 40 (scroll) | 155 | 115 | 100%+ |

## Wall-clock cost

Hardening добавляет:
- 4s × pages вместо 2.8s × pages → +1.2s × pages
- 20s burst-cooldown каждые 3 pages → ~5s × pages amortized
- 403 retries при срабатывании: 12+24=36s + page-skip = `<` 1 минута per brand

Net на 64 брендах: 55 мин → **87 мин** (+58%). Acceptable для weekly run, особенно с учётом что matches вырос +1500.

## Когда обратить внимание

- Если ловим `brand_enum_api_403_budget_exhausted` чаще одного раза на 64 брендов — bump `max_403_budget_per_brand` 12 → 16
- Если burst_cooldown_ms=20s не помогает (pages 4+ всё равно 403) — это significantly tighter rate-limit, нужно `pages_per_burst=2` + cooldown 30s
- При замедлении на ВСЕХ брендах (не только rate-limited) — мб anti-bot фингерпринтинг растёт, нужен residential proxy или Camoufox refresh per N brands

## Связано

- [[Brand-pages discovery через cards-list + product-card API]]
- [[GA brands index — single XHR на front-api-brands возвращает все 1389 брендов]]
- [[Brand-alias mismatch — viled добавляет -beauty suffix, GA снимает]]
