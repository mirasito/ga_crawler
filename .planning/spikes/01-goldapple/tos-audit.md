# Spike 01: robots.txt + ToS Audit (RECON-04)

**Status:** COMPLETED — _2026-05-05_
**Operator:** mirdbek@gmail.com
**Scope:** self-review обоих сайтов (viled.kz и goldapple.kz). KZ-legal review (30 мин с юристом) — DEFERRED to Phase 7 per `01-CONTEXT.md` (deferred ideas).
**Method:** `curl_cffi` с `impersonate="chrome"` (per CLAUDE.md §Anti-Bot Strategy + PITFALLS.md Pitfall 1). Snapshot'ы сохранены в `sample-payloads/` для drift-baseline. Скрипты-выкачивалки (`_fetch_robots.py`, `_fetch_tos.py`, `_extract_viled_tos.py`, `_scan_tos.py`) оставлены для воспроизводимости.

---

## viled.kz

**robots.txt URL:** `https://viled.kz/robots.txt` (canonical — apex; `www.viled.kz/robots.txt` 301-редиректится на apex и отдаёт идентичный контент, поэтому `www`-snapshot не сохранён)
**Fetched:** 2026-05-05, snapshot in `sample-payloads/viled-kz-robots.txt` (508 байт)
**HTTP status:** 200 (Content-Type: `text/plain; charset=UTF-8`)

**User-agent sections seen:**
- `User-agent: *` (единственная секция; нет отдельных правил для Googlebot/Bingbot)

**Allowed paths (relevant to scraping):**
- Всё, что НЕ перечислено в Disallow (по дефолту robots.txt). Для нас критично: `/` (homepage), product pages, brand/category listings — все доступны.

**Disallowed paths (relevant to scraping):**
- `/*/*search?` — поиск (нерелевантно — мы не парсим search)
- `/*/wishlist`, `/*/cart/`, `/*/checkout/`, `/*/profile/`, `/*/auth/` — пользовательские/защищённые секции (нерелевантно)
- `/*/terms/`, `/*/embed`, `/*/rss` — служебные
- `/*page=1*` (все варианты) — стандартный SEO-приём (`?page=1` дублирует canonical-страницу без параметра)
- `/cn/` — устаревший раздел
- `*openstat=`, `/*srsltid*` — UTM-подобные параметры

**Crawl-delay directive:** **не задан** (отсутствует в robots.txt)

**Sitemap URLs (transferred to plan 01-05):**
- `https://viled.kz/sitemap.xml`

**ToS URL:** **отсутствует как отдельная страница**.
- Перебрали 8 кандидатов (`/terms`, `/usloviya`, `/oferta`, `/publichnaya-oferta`, `/polzovatelskoe-soglashenie`, `/soglashenie`, `/privacy-policy`) — все отдают HTTP 404 (Next.js fallback page, 179 KB одинакового SPA-shell'а).
- Единственный реально работающий правовой документ — **Политика конфиденциальности** на `https://viled.kz/privacy` (HTTP 200, 216 KB Next.js-страница; контент embedded в `<script id="__NEXT_DATA__">` JSON-blob, успешно извлечён в `sample-payloads/viled-privacy.txt` через `_extract_viled_tos.py`).

**ToS findings (anti-scraping clauses):**
- **Anti-scraping clauses: НЕТ.** Privacy Policy viled.kz регулирует обработку **персональных данных пользователей** в соответствии с Законом РК 94-V от 2013-05-21 («О персональных данных и их защите»). Документ описывает: что такое cookies/IP/персональные данные, как viled их собирает, цели обработки, права субъекта, способы отзыва согласия.
- Документ **не упоминает**: scraping, crawling, robots, парсинг, автоматизированный доступ, конкурентную разведку, ограничения на использование публичных страниц третьими лицами.
- Слово «автоматизирован»/«автоматическ» встречается **только в контексте «без использования средств автоматизации» при обработке персональных данных пользователей** — то есть про сам viled, а не про внешних потребителей данных.
- Раздел 9 «Разрешение споров» — стандартный (KZ-юрисдикция, претензионный порядок).
- Нет публичной оферты / условий использования / пользовательского соглашения как отдельного документа.

**viled.kz rate-limit (committed): 2 секунды между fetch'ами (1 req / 2s, sequential)**

**Rationale:**
- robots.txt **не задаёт** Crawl-delay, поэтому опираемся на defaults.
- PITFALLS.md Pitfall 13: «viled.kz: smaller, less defended, but be polite. 1 req/sec is plenty. You're a guest, not a customer. (And: the team owns viled.kz — be extra polite to your own infrastructure.)»
- CLAUDE.md / PROJECT.md: viled.kz — это собственная инфраструктура клиентской команды. Ставим консервативный коэффициент 2× к минимуму Pitfall 13 (2s вместо 1s) — стоимость нулевая (раз в неделю, ~10k product-страниц × 2s = 5.5 часов, бюджет phase-2 это легко переваривает).
- Privacy Policy не накладывает явных ограничений по rate; default Pitfall 13.

---

## goldapple.kz

**robots.txt URL:** `https://goldapple.kz/robots.txt` (canonical apex)
**Fetched:** 2026-05-05, snapshot in `sample-payloads/goldapple-kz-robots.txt` (7303 байт)
**HTTP status:** 200 (Content-Type: `text/plain`) — **robots.txt отдаётся в обход JS-challenge**, в отличие от HTML-страниц (см. ToS findings ниже).

**User-agent sections seen:**
- `User-agent: *` — общие правила для всех ботов (≈100 строк Disallow + paginated/session-id блоки + Adult-only).
- `User-agent: Googlebot` — отдельный, более жёсткий блок: дополнительно `Disallow: /*?*` (запрет ВСЕХ get-параметров) + `Disallow: /*?locale=*` + повторение всех путей из секции `*`. Для нас это интересно как сигнал: «search-боты пускают только на чистые URL без параметров».
- **Чёрный список спецификованных user-agent'ов** (38 ботов, все с `Disallow: /`): SemrushBot, MJ12bot, BLEXBot, DotBot, MegaIndex, AhrefsBot не указан явно но семьи аналогичны; LinkpadBot, FlipboardProxy, aiHitBot, trovitBot, grapeshot, Detectify, Riddler, DISCo Pump, **Wget**, **HTTrack**, **libwww**, **Microsoft.URL.Control**, MSIECrawler, Xenu, larbin, ZyBORG, NPBot, WebReaper, Teleport, SiteSnagger, WebCopier, WebStripper, Offline Explorer, Fetch, Download Ninja, grub-client, ZyBORG, Zealbot, Zao, sitecheck.internetseer.com, UbiCrawler, NetinfoBot, Twiceler, psbot, seznambot, Riddler, DOC, linko.
- **Сильный сигнал для нашей UA-strategy:** competitive-intel боты (SemrushBot, MJ12bot, BLEXBot — стандартные SEO/конкурентного-анализа crawler'ы) явно нежеланны. Указывать `ViledPriceMonitor/1.0` как UA (как предлагает Pitfall 14 в варианте «честный UA») — НЕ подходит: первый же успешный fetch с таким UA будет зафиксирован и потенциально внесён в persistent ban-list. → **Phase 3 UA = realistic browser UA (impersonate=chrome)**, без self-identification, документировано как сознательный выбор stealth-варианта Pitfall 14.

**Allowed paths (relevant to scraping):**
- Product pages (`/product/...`), brand pages (`/brands/...`, `/brand/...` — точные маршруты определит plan 01-05 через sitemap), category pages (`/catalog/...` без `/product/view/`), homepage, sitemap. Пути НЕ перечисленные в Disallow — разрешены.

**Disallowed paths (relevant to scraping):**
- **Внутренние API**: `/rest/`, `/swagger/` — критично: означает, что доступ к JSON-эндпоинтам через `*/rest/V1/...` (Magento REST) **запрещён robots.txt'ом**. Для D-09 (JSON-endpoint hunt в plan 01-06) это влияет: если найдём REST-API в DevTools, использование будет ToS-нарушением robots.txt. **Альтернатива** — JSON-LD из HTML (D-14) разрешён по умолчанию.
- `/catalog/product_compare/`, `/catalog/category/view/`, `/catalog/product/view/`, `/catalogsearch/` — внутренние Magento dispatcher-URLs (legacy маршруты до rewrite'ов). Реальные SEO-URLs `/product/<slug>` обычно НЕ дублируют `view/`-paths.
- Admin/setup-инфраструктура: `/admin`, `/app/`, `/var/`, `/vendor/`, `/setup/`, `/composer.json`, `/composer.lock`, `/package.json` (вся стандартная Magento-tree).
- User-private: `/checkout/`, `/customer/`, `/wishlist/`, `/cards/...`, `/sales/order/`, `/sendfriend/`, `/private-sales`.
- Pagination/sort filter dupes: `/*?*product_list_mode=`, `/*?*product_list_order=`, `/*?*product_list_limit=`, `/*?*product_list_dir=`.
- Service: `/no-route`, `/service-unavailable`, `/enable-cookies`, `/all-products`, `/sertifikaty`, `/giftcardlp*`, `/kd*`, `/flacon/preview/*`.
- File-extension blocks: `/*.php$`, `/*.html`, `/*.pdf`, `/*.Sql$`, `/*.Tgz$` etc. — для нас **критично что `*.html` Disallow'ed для secondary processing**, но реальные продукт-URL'ы Magento-style обычно БЕЗ `.html`-суффикса (slug-based). Нужно валидировать в plan 01-05 на конкретных sitemap-URL'ах.
- Adult-content: `*adultonly-*`.

**Crawl-delay directive:** **не задан** (отсутствует в robots.txt) — это типично для Cloudflare/managed-prod-сайтов: rate-limiting реализован на уровне WAF, а не через robots.txt-полиси.

**Clean-param directives:** Множество (Yandex-style инструкции для нормализации URL — UTM-параметры, brand-/category-фильтры, sort-параметры). Для нас это означает что Yandex/Mail.ru-боты получают canonical-URL'ы; для нашего краулера несущественно (мы будем использовать sitemap-URL'ы напрямую).

**Sitemap URLs (transferred to plan 01-05):**
- `https://goldapple.kz/sitemap.xml` (один declared sitemap; внутри может быть sitemap-index с подkapt'ами `sitemap_products.xml` и т. п. — проверит plan 01-05).

**ToS URL:** **не получен через curl_cffi.** Перебрано 11 кандидатов (`/rules`, `/terms`, `/usloviya`, `/oferta`, `/publichnaya-oferta`, `/polzovatelskoe-soglashenie`, `/privacy`, `/privacy-policy`, `/confidentiality`, `/soglashenie`) — **все 11 отдают идентичный 18 912-байтный JS-challenge shell** с `<title>Gold Apple — checking device</title>` и `<noscript>` блоком «Oops! JavaScript is disabled in your browser. For proper website functioning, please enable JavaScript…». Включает скрипт `/_static/js/5ae5d1cd-7037-4ce7-9a67-dc2ed4d4e6ea.umd.min.js` (UUID-имя — характерный pattern для DataDome / custom device-fingerprint challenge'а). Один из shell'ов (`/rules`) сохранён в `sample-payloads/goldapple-rules.html` как evidence; остальные 10 не коммитятся (byte-identical копии — drift baseline избыточен).

**ToS findings (anti-scraping clauses):**
- **Текст ToS не получен в этой фазе** — все правовые страницы гейтятся за client-side JS challenge (см. выше). Это само по себе **значимая находка** и фиксируется как сигнал для plan 01-08 (Tier-2 100-fetch): если robots.txt отдаётся plain а **любая** HTML-страница (включая privacy/legal!) гейтится — anti-bot слой goldapple глобален и активен с первого hop'а. **НЕ эскалируем до Patchright для ToS** (per plan 01-04 guidance: «overkill для ToS»).
- ToS будет **повторно проверен после plan 01-08**, когда 100-fetch стабилизирует Patchright-сессию — тогда можно сделать дополнительный low-cost fetch правовых страниц через уже-warm-context. Если найдём явные anti-scraping clauses — эскалируем в MEMO «Open risks» и в Phase 7 KZ-legal review.
- **Косвенный сигнал в robots.txt**: блокировка SemrushBot/MJ12bot/BLEXBot/DotBot — это competitive-intel SEO-tools — означает, что goldapple **явно не хочет** автоматизированной конкурентной разведки. Это не ToS-clause, но moral/practical-сигнал per Pitfall 14.

**goldapple.kz rate-limit (committed): 3-5 секунд между fetch'ами (random uniform), sequential, concurrency = 1**

**Rationale:**
- D-04 (CONTEXT.md): «persistent context (warm), один Playwright browser context на всю серию, cookies живут между fetch'ами, slow rate (пауза 3–5 секунд между запросами)».
- PITFALLS.md Pitfall 13: «Concurrency: 1-3 max for goldapple. Random uniform 2-5 seconds. NOT a fixed delay (looks robotic).»
- Pitfall 1: agressive scraping вызывает Cloudflare/DataDome detection penalises bursts.
- robots.txt **не задаёт** Crawl-delay → опираемся на defaults и эмпирический эксперимент plan 01-08.
- Будет валидировано plan 01-08: если challenge-rate >20% при 3-5s — увеличить до 5-10s; если success-rate ≥98/100 при 3s — оставить как есть. **Эта 3-5s константа — стартовая точка эксперимента, не финальное продакшн-значение.**

---

## Summary

| Site | robots.txt status | Sitemap available | Crawl-delay | Bot-blocklist (UA) | ToS anti-scraping clause | Committed rate-limit |
|------|---|---|---|---|---|---|
| viled.kz | 200, 508 B | Y (`https://viled.kz/sitemap.xml`) | not set | none | none — only Privacy Policy (KZ Law 94-V personal data) | 2 s sequential |
| goldapple.kz | 200, 7303 B | Y (`https://goldapple.kz/sitemap.xml`, likely sitemap-index) | not set | **38 bots blocked**, incl. SemrushBot, MJ12bot, BLEXBot, DotBot, Wget, HTTrack | unknown — ToS pages JS-gated, deferred to post-01-08 re-fetch | 3–5 s random uniform, concurrency=1 |

## Key signals for downstream plans

1. **goldapple.kz anti-bot is global (not just product pages):** every HTML route (including legal/privacy pages) returns the same JS-challenge shell. robots.txt is the only plain-text resource confirmed. This **strengthens the case for D-01 (start at Tier 2 / Patchright)** and confirms vanilla Playwright will likely fail too.
2. **goldapple `/rest/` is robots-Disallowed:** Magento REST API is off-limits per robots.txt even if discoverable in DevTools. JSON-endpoint hunt (D-09, plan 01-06) must focus on alternatives — `__NEXT_DATA__`-style embedded JSON, JSON-LD in `<script type="application/ld+json">` (D-14), or non-`/rest/` ajax routes.
3. **goldapple competitive-intel UA strategy:** `Disallow: /` for SemrushBot/MJ12bot/BLEXBot means honest UA `ViledPriceMonitor/1.0` would flag us immediately. **Decision: realistic browser UA via `curl_cffi`/Patchright impersonation** (PITFALLS Pitfall 14 stealth-variant). Документировано в MEMO как сознательный выбор.
4. **viled.kz has no anti-scraping clause:** clean ground legally and morally. Polite 2-second rate is courtesy, not requirement.
5. **Both sites declare a sitemap** — primary enumeration path for plan 01-05 (page-volume estimate, D-11).

## Risks / Open items

- **KZ-legal review (30 min lawyer)** — Phase 7 TODO per CONTEXT.md (D-deferred). Сводка `tos-audit.md` + privacy policy snapshot (`viled-privacy.txt`) — input для review.
- **goldapple.kz ToS re-fetch after 01-08:** as soon as plan 01-08 confirms Patchright stability, перefetcher legal pages с warm-session и проверить anti-scraping clauses. Если clause найдена — `MEMO.md` «Open risks» + Phase 7 lawyer note.
- **ToS update monitoring:** не реализуется в спайке. MEMO «Open risks» зафиксирует что snapshot'ы — baseline на 2026-05-05; в Phase 7+ возможно периодическая proverka diff'а через простой curl_cffi GET + hash compare.
- **Если goldapple ToS прямо запрещает competitive-intel scraping** (которое мы и делаем) — это бизнес-решение клиента и не блокирует спайк (CONTEXT.md scope: self-review-only).
- **`*.html` Disallow в goldapple robots:** валидировать в 01-05 что реальные product-URL'ы slug-based без `.html`-суффикса (Magento default). Если product-URL'ы имеют `.html` — пересмотреть стратегию.

## Transferred to other plans

- **plan 01-05 (sitemap / page-volume):** sitemap URLs:
  - viled: `https://viled.kz/sitemap.xml`
  - goldapple: `https://goldapple.kz/sitemap.xml`
  - + `*.html` Disallow check (см. Open items)
- **plan 01-06 (DevTools / JSON-endpoint hunt):** `/rest/` is forbidden by robots.txt — focus on `__NEXT_DATA__` / JSON-LD / non-`/rest/` ajax routes. `viled.kz` использует `__NEXT_DATA__` (подтверждено для privacy page, вероятно тот же pattern для product pages).
- **plan 01-07 (viled curl_cffi):** rate-limit = **2 s sequential**, sitemap = `https://viled.kz/sitemap.xml`, Disallow-аккуратность нулевая (paths все разрешены).
- **plan 01-08 (Patchright 100-fetch goldapple):** rate-limit = **3-5 s random uniform, concurrency=1**, persistent-context (warm), cookies-reuse (D-04). Bot-blocklist в robots.txt обосновывает stealth-UA-strategy. Pre-flight: проверить что sitemap.xml тоже отдаётся plain (а не challenge'и) — если да, использовать как primary enumeration.
- **plan 01-11 (MEMO finalize):** этот audit-summary рефериться в section "Robots/ToS audit" + committed rate-limits становятся config-константами для Phase 3 fetch layer.
- **Phase 7 (KZ-legal review):** input bundle = этот файл + `viled-privacy.txt` + оба `*-robots.txt` snapshot'а + flag «goldapple ToS не получен в спайке, требуется browser-fetch».

---

*Audit completed by gsd-executor on 2026-05-05; snapshots committed for drift-baseline and reproducibility.*
