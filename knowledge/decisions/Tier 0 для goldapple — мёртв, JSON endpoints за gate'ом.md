---
tags: [decision, anti-bot, phase-1, tier-0, hybrid-stack]
date: 2026-05-06
---

# Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом

**Tier 0 (curl_cffi + JSON endpoint без browser) для goldapple PRODUCT DATA — не виабелен.** Все JSON endpoints живут за GroupIB gate'ом, который без browser fingerprint не пробить.

**Но:** Tier 0 для goldapple **ENUMERATION** (sitemap.xml) — жив. Это **гибридный стек**, не моно-tier.

## Hybrid Phase 3 stack

```
goldapple enumeration : curl_cffi + sitemap.xml      (Tier 0 ✓)
goldapple product render: Camoufox + JSON-LD parse    (Tier 2)
```

[[Camoufox а не Patchright — engine для goldapple]] делает product render возможным. Sitemap.xml exempt от gate — это даёт нам полный enumeration без browser overhead.

## Что искали (плана 01-06 D-09 deliverable)

| Endpoint type | Status |
|---|---|
| `__NEXT_DATA__` script-tag | ❌ Не найдено в challenge shell. Реальное приложение — НЕ Next.js (вероятно Magento PWA). 0/3 страниц после Camoufox-gate-clearance тоже без `__NEXT_DATA__`. |
| `/_next/data/*.json` | ❌ Никогда не вызывается (приложение не Next.js) |
| GraphQL endpoint (`/api/graphql`, `/graphql`) | ❌ Не наблюдался ни в challenge HTML, ни в network trace |
| `/rest/V1/*` Magento REST | ⚠️ Существует, но **robots.txt Disallow** (плана 01-04) — нельзя использовать |
| Открытые ajax routes | ❌ Все frontend-internal endpoints (`/web/api/v1/settings`, `/front/api/event`, etc.) гейтятся |
| **sitemap.xml** | **✓ Plain-deliverable через curl_cffi** (01-05). 112 317 URLs, 100 779 product, 1461 брендов |

## Почему это нормально (а не катастрофа)

Тип данных каждой задачи:

- **Enumeration (что crawl-ить):** sitemap.xml — gate-exempt — Tier 0 ✓
- **Product price/name/stock (что внутри):** только за gate'ом — Tier 2 (Camoufox) ✓

Это **рассчитано как hybrid с самого начала** — теперь подтверждено эмпирически.

## D-14 success criterion verifiable

Camoufox-spike подтвердил **JSON-LD на всех 3 product pages** (`<script type="application/ld+json">`). Schema.org `Product.offers.price` / `Product.offers.priceCurrency` — стандартные поля. Spike fetch-OK criterion D-14 (`HTTP 200 + product JSON-LD`) — работает.

**Phase 3 parser hint:** `selectolax` + `json.loads` на innerText `<script type="application/ld+json">`. Fallback если goldapple добавит non-standard расширения: Open Graph `og:price:amount` / `og:price:currency` meta tags.

## Что НЕ делаем (deferred / cancelled)

- ❌ Не пытаемся reverse-engineer GroupIB fingerprint, чтобы pass gate с curl_cffi (вне scope, anti-economical)
- ❌ Не используем `/rest/` Magento (robots-blocked — courtesy + risk)
- ❌ Не зацикливаемся на поиске hidden JSON endpoint (01-06 cleared the search; ничего не нашлось post-gate тоже — это Magento, не Next.js)

## Связанные

- [[Camoufox а не Patchright — engine для goldapple]] — engine для product render Tier 2
- [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]] — vendor lock на fingerprint-gate
- [[JSON-endpoint hunt — явный deliverable Phase 1]] — D-09, выполнено
- [[2026-05-06 — Camoufox побеждает GroupIB, Phase 1 re-route]] — session log
