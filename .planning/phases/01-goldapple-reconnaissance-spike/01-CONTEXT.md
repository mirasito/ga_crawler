# Phase 1: Goldapple Reconnaissance Spike - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Timeboxed (1 неделя) reconnaissance-спайк, единственная цель которого — резолвнуть anti-bot-неизвестность goldapple.kz и подписать decision memo, выбирающий tier (0/1/2/3/4), proxy-провайдера и browser-engine для Phase 3. Производит throwaway-код, notebook с 100+ sequential successful goldapple-fetch'ами, robots/ToS-аудит обоих сайтов и эмпирическую оценку объёма страниц для типичного бренда. **Не** производит production-код, схемы БД, парсеры, общие модули — всё это начинается в Phase 2. Phase 3 stack-выбор гейтится подписью этого memo.

</domain>

<decisions>
## Implementation Decisions

### Tier Escalation & Timebox

- **D-01:** Стартуем сразу с **Tier 2 (Patchright)**. Vanilla Playwright (Tier 1) скипаем — research/PITFALLS и research/STACK сходятся на том, что vanilla в 2026 детектится Cloudflare/DataDome сразу; тратить день на ожидаемо-проваленный Tier 1 не имеет смысла. Если Patchright проходит — фиксируем Tier 2 без proxy. Если фейлит — эскалация до Tier 3 (+residential proxy).
- **D-02:** Жёсткий **timebox = 1 неделя** на весь спайк. После этого срока, если не достигнут стабильный tier ≤3, вердикт = «Tier 4 / managed unblocker (ZenRows/Bright Data) — экономика проекта меняется, идём пересматривать PROJECT.md».
- **D-03:** Stop-rule между tier'ами: **5 подряд блоков (403/429) или первая Cloudflare interstitial / DataDome captcha → tier failed, эскалация**. Не тратим попытки на очевидный фейл.
- **D-04:** Cookie/session reuse в эксперименте = **persistent context (warm)**. Один Playwright browser context на всю серию, cookies живут между fetch'ами, slow rate (пауза 3–5 секунд между запросами). Это тот же режим, что планируется в Phase 3-проде, поэтому спайк меряет реалистичный, а не worst-case tier.

### Spike Location & IP Geo

- **D-05:** Методология = **multi-geo**. Меряем Patchright с двух геолокаций для сравнения: (1) лэптоп пользователя (KZ-IP, Asia/Almaty) и (2) один residential proxy (RU или EU, провайдер из D-08). Memo содержит **два числа** (например, «KZ-laptop: 98/100 без challenge, EU-proxy: 84/100, 6 challenges»). Это снимает неопределённость «а что если IP-гео меняет ответ».
- **D-06:** Baseline IP = **лэптоп пользователя (KZ-IP, Windows 11)**. Бесплатно, быстрый setup, KZ-гео потенциально выгодно для goldapple.kz как KZ-домена. Это **не** тот IP, что будет в проде (Hetzner EU), и memo обязан это явно зафиксировать.
- **D-07:** Production-IP-гео для Phase 7 = **TBD; решается результатом спайка**. Кандидаты: Hetzner EU IP (research/STACK базовый), Hetzner EU + KZ/RU residential proxy (если EU-IP бьётся), full residential pool (Tier 3+). Memo обязан выдать однозначный вердикт по prod-гео.
- **D-08:** Proxy trial readiness — **регистрируем trial-аккаунт IPRoyal или Decodo до старта Tier 2-теста**, чтобы при фейле Tier 2 сразу эскалировать без потери дня на onboarding/KYC. Один провайдер, не оба. Выбор: IPRoyal предпочтительнее (KZ residential pool сильнее по 2026 reviews из research/STACK), Decodo — fallback если у IPRoyal плохо с KZ-гео.

### JSON-Endpoint Hunt

- **D-09:** Активная охота за JSON-эндпоинтами — **явный deliverable спайка**. 30–60 минут в DevTools (Network tab) и `view-source:` на 5–10 product/category-страницах: ищем XHR/fetch к catalog API, `__NEXT_DATA__` script-tag, GraphQL endpoints, sitemap.xml. Дешёвая проверка с очень высоким upside — может сэкономить весь Tier 2+ stack.
- **D-10:** Если найдём рабочий JSON-эндпоинт без anti-bot — memo описывает **новый сценарий: Tier 0 (curl_cffi + JSON-эндпоинт)** как primary стратегию для Phase 3. Patchright становится резервом. Phase 3 stack радикально упрощается (нет Playwright, нет Camoufox, нет proxy) и экономика проекта улучшается.
- **D-11:** Page-volume estimate (RECON-03) = **sitemap.xml + pagination meta**. Сначала пробуем `goldapple.kz/sitemap.xml` (часто открыт без anti-bot), считаем product URLs per brand. Fallback: на 2–3 brand-listing страницах смотрим pagination-метку («Page 1 of N» / total count) и умножаем. Не делаем полный обход в спайке (это бюджет Phase 3).
- **D-12:** Бренды для 100-fetch эксперимента = **3–5 брендов из пересечения с viled top-10**. Это даёт Phase 3 предварительный сигнал по brand-list-структуре + проверяет, что выбранный tier работает на тех брендах, которые реально нужны бизнесу. Не «случайные 100 SKU из sitemap» (не привязано к viled-каталогу) и не «крупный + мелкий микс» (репрезентативность ниже). Список топ-10 берётся из viled.kz top-traffic брендов (ручной просмотр или manual sample, спайк не парсит viled пока).

### Success Criteria & Artifacts

- **D-13:** Threshold = **≥95/100 с разрешёнными 5xx/timeout-ретраями**. Это норма для реальных краулеров 2026 — не 100/100-strict (нереалистично) и не 100/100-with-budget (слишком мягко). <95% за 100 fetch'ей → tier failed, эскалация. Memo фиксирует точное число (98/100, 92/100, и т. д.).
- **D-14:** Определение «успешный fetch» = **HTML 200 + product JSON-LD найден в `<script type="application/ld+json">`**. Это прокси для «прод реально сможет парсить». Не «HTML 200 + нет captcha-page» (слишком мягко, парсер может упасть позже) и не «current_price извлечён» (выход за scope throwaway-спайка — это Phase 2/3 работа).
- **D-15:** Cloudflare interstitial / DataDome challenge, **auto-resolved браузером без человеческого вмешательства, считается проходом**. Но challenge-rate **обязательно логируется в memo** как отдельная метрика (например, «8/100 challenges, all auto-resolved, avg +2.3s»). Если challenge-rate >20%, tier помечается как «хрупкий» даже если технически прошёл — это сигнал, что в проде лучше Tier 3.
- **D-16:** Артефакты спайка живут в `.planning/spikes/01-goldapple/` (git-tracked, основной источник правды): `MEMO.md`, `notebook.ipynb` или `notebook.py`, `tos-audit.md`, `sample-payloads/`. Дополнительная копия `MEMO.md` дублируется в Obsidian-vault в `knowledge/decisions/` для поиска и cross-link'ования. На завершении спайка обязательно вызывается `/gsd-spike --wrap-up` чтобы упаковать findings в project-local skill, который Phase 3 discuss/plan смогут подгрузить.

### Claude's Discretion

Не оставленных.

### Не обсуждали явно (но повлияют на план):
- **Формат decision memo** — Claude использует короткий decision-memo template (problem / options tested / chosen tier+rationale / next-step impact / open risks), не freeform.
- **viled-проба (RECON-02)** — минимум ≥10 product fetches через `curl_cffi impersonate="chrome"`; Claude дополнительно фиксирует timing, JSON-LD presence, pagination shape, robots/UA-строгость как side-deliverable, чтобы Phase 2 шёл с горячими данными.
- **Notebook vs script** — Claude по умолчанию выбирает `.py` script (cleaner diffs, run-anywhere, никакой Jupyter-state), с `print(...)` вместо output-cells. `.ipynb` только если потребуется визуализация (не ожидается для recon-спайка).
- **KZ-legal review** — research/SUMMARY.md флагует «30-min KZ lawyer review before Phase 7». Спайк делает только self-review robots.txt + ToS обоих сайтов и фиксирует findings в `tos-audit.md`. Юридический ревью переносится в Phase 7 как отдельный TODO (не блокирует спайк).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — core value, constraints, out-of-scope, key decisions
- `.planning/REQUIREMENTS.md` §Reconnaissance (RECON-01..04) — locked v1 requirements for this phase
- `.planning/ROADMAP.md` §"Phase 1: Goldapple Reconnaissance Spike" — phase goal, dependencies, success criteria

### Research foundation (LOCKED — все 4 файла обязательны для планера)
- `.planning/research/SUMMARY.md` — общая стратегия, executive summary, причина «спайк first»
- `.planning/research/STACK.md` — tier-лестница (0→1→2→3→4), proxy-провайдеры (IPRoyal/Decodo), Patchright/Camoufox-fork каноны, Hetzner CX22 EU как baseline хостинг
- `.planning/research/PITFALLS.md` — anti-bot-механика 2026, что НЕ работает (cloudscraper, vanilla Selenium, playwright-stealth v1, requests + headers)
- `.planning/research/ARCHITECTURE.md` — depend-order rationale (viled-first но spike-zero), модульный монолит, snapshot-таблица как integration backbone (для Phase 2+, но влияет на throwaway-границу спайка)
- `.planning/research/FEATURES.md` — feature taxonomy (фоновое чтение для понимания scope-границ)

### Project state
- `.planning/STATE.md` — текущая позиция, accumulated key decisions

### Project conventions
- `CLAUDE.md` (project root) §Technology Stack, §Anti-Bot Strategy — рекомендованные версии библиотек, escalation tiers со ссылками на источники

### Out-of-tree (Obsidian vault)
- `knowledge/decisions/` — copy цели MEMO.md после `/gsd-spike --wrap-up`
- `00-home/index.md` и `текущие приоритеты.md` — общая навигация (читаются в начале сессии по project-prompt)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
**Нет.** Фаза 1 — pre-code reconnaissance. Никаких production-модулей, скрипты — throwaway. После завершения спайка артефакты не импортируются Phase 2.

### Established Patterns
**Нет** (это первая фаза). Pattern-source для Phase 2+: `.planning/research/ARCHITECTURE.md` §Major components, §Project layout.

### Integration Points
- Output → **Phase 3 stack selection**: tier (D-01..D-04, D-07), proxy provider (D-08), browser engine (Patchright/Camoufox/Tier 0 curl_cffi).
- Output → **Phase 2 viled-крауль**: RECON-02 (curl_cffi feasibility), сторонние находки про viled (timing, JSON-LD, pagination — см. «Не обсуждали явно»).
- Output → **Phase 7 docs**: robots/ToS-audit, rate-limit constants.

</code_context>

<specifics>
## Specific Ideas

- **«5 подряд блоков»** как stop-rule: не «5 за всю сессию» — именно подряд. После любого успешного fetch'а счётчик блоков обнуляется. Чтобы случайные одиночные 429-ки от backend retry-able шумов не триггерили эскалацию.
- **Sitemap-first** для page-volume и product URL discovery: спайк обязан в первую очередь попробовать `goldapple.kz/sitemap.xml`, `goldapple.kz/sitemap_products.xml` и любые ссылки в `robots.txt`. Это часто открыто и обходит anti-bot полностью.
- **Challenge-rate как метрика**: даже при ≥95/100 успехе, если challenge-rate >20%, tier помечается «хрупким» в memo и рекомендуется Tier 3 в проде.

</specifics>

<deferred>
## Deferred Ideas

- **Полный детальный KZ-legal review (30 мин с юристом)** — research/SUMMARY рекомендует до Phase 7. Спайк делает только self-review. Перенесено в Phase 7 как TODO.
- **Camoufox / Scrapling StealthyFetcher тесты (Tier 4)** — только если Tier 2 + Tier 3 оба фейлят. Не входят в default-спайк-сценарий.
- **Бенчмарк нескольких proxy-провайдеров (IPRoyal vs Decodo vs Bright Data)** — в спайке выбираем один (IPRoyal), сравнение откладывается до момента, когда станет понятно «нужен ли вообще proxy».
- **Захват goldapple HTML-fixtures для unit-тестов парсера** — потенциально полезно, но это уже Phase 3 deliverable. Спайк сохраняет sample HTML только если попадается интересный кейс (challenge page, error variants), не как систематический dataset.
- **Match-rate baseline-симуляция на спайк-данных** — слишком рано, нет нормализатора. Это Phase 4 KPI.

### Reviewed Todos (not folded)

Не было — todos не сравнивались (нет todo-tracker'а инициализированного для этого проекта).

</deferred>

---

*Phase: 1-Goldapple Reconnaissance Spike*
*Context gathered: 2026-05-05*
