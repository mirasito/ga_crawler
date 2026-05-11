---
tags: [decision, phase-3, norm-06, d-305, brand-intersect, gap-closure]
date: 2026-05-06
supersedes: D-305 в исходной формулировке («exact match исключает Tom Ford → tom-ford-beauty false-positive»)
status: locked
---

# Brand-intersect через longest-prefix-in-whitelist, не exact-match

## Контекст

D-305 в первой формулировке предписывал «exact match только (не substring, не prefix, не fuzzy)». Это работало в test-fixture'ах Wave 2 (03-02), где sitemap-словарь конструировался руками с brand-only ключами. На production sitemap'е (45,490 product-slug'ов формы `7681000001-givenchy-pour-homme-blue-label`) exact-match `dict.get('givenchy')` всегда возвращает None — потому что ключи — full product-slug'и, а не brand-aliases. Wave 6 live-smoke (run-42) поймал это: `unmatched_viled_brands=2` для обоих brand'ов из 2-х. Phase 4 matcher без fix получил бы пустой goldapple snapshot.

## Решение

`fetch_sitemap_slugs()` дополнительно эмитит **brand-token bucket** через helper `index_by_brand_token(slug_map, known_brand_tokens) → dict[brand_token, list[url]]`. `intersect_brand_pool` принимает `brand_bucket` и делает по-прежнему **exact-match** через `dict.get(brand_slug)` — но теперь против brand-token-keyed bucket'а, не product-slug-keyed dict'а.

**Алгоритм `index_by_brand_token` (longest-prefix-in-whitelist, Path A Option 4):**

Для каждого product-slug — strip leading numeric prefix, split по `-`, перебрать candidate-prefix'ы depth 3 → 2 → 1 (longest-first), и **первый** который ∈ `known_brand_tokens` забирает URL в свой bucket. Если ни один не в whitelist — URL drop'ается (orphan; viled не несёт этот бренд).

`known_brand_tokens` — set'е, который orchestrator precompute'ит из `slug_fy_bilingual` всех aliases всех viled brand'ов **до** вызова `index_by_brand_token`.

```python
# Pseudocode
def index_by_brand_token(slug_map, known_brand_tokens):
    bucket = {}
    for product_slug, urls in slug_map.items():
        remainder = strip_numeric_prefix(product_slug)
        tokens = remainder.split("-")
        for k in range(min(3, len(tokens)), 0, -1):
            candidate = "-".join(tokens[:k])
            if candidate in known_brand_tokens:
                bucket.setdefault(candidate, []).extend(urls)
                break  # ONLY add to longest-match bucket
    return bucket
```

## Что это даёт vs наивная версия

| Кейс | Наивный depth-emit-all (отвергнуто) | Longest-prefix-in-whitelist (принято) |
|---|---|---|
| `givenchy-pour-homme-blue-label`, viled = `Givenchy` (token=`givenchy`) | URL → bucket['givenchy'] (OK) | URL → bucket['givenchy'] (OK) |
| `tom-ford-beauty-eye-cream`, viled = только `Tom Ford` (token=`tom-ford`) | URL → bucket['tom-ford'] **И** bucket['tom-ford-beauty'] → contamination Tom Ford с Beauty SKUs | depth-3 `tom-ford-beauty` нет в whitelist → fallback depth-2 `tom-ford` ∈ whitelist → URL → bucket['tom-ford'] (operator-default, ожидаемо) |
| `tom-ford-beauty-eye-cream`, viled = `Tom Ford` + `Tom Ford Beauty` (оба в whitelist) | URL в обоих bucket'ах | depth-3 `tom-ford-beauty` ∈ whitelist → URL → ровно bucket['tom-ford-beauty'], bucket['tom-ford'] **не получает** этот URL (операторская дисамбигуация работает) |
| `jo-malone-london-cologne`, viled = `Jo Malone London` (token=`jo-malone-london`) | URL в bucket['jo'], bucket['jo-malone'], bucket['jo-malone-london'] → шум | depth-3 `jo-malone-london` ∈ whitelist → URL → bucket['jo-malone-london'] |
| `unknown-brand-product`, ни одного prefix не в whitelist | URL во всех trash bucket'ах | URL drop'ается (correct: viled не несёт этот бренд) |

## D-305 / Pitfall 3 защита

Сохранена **структурно**, не интерпретативно:

- Substring match'ей нет (`startswith`/`contains`/`find` не используются — есть AST/inspect.getsource grep gate в тестах).
- Cross-contamination между brand-extension семьями невозможна, если оператор объявил все семьи в `viled_brands` (longest-prefix selection даёт каждому URL ровно один bucket).
- Если оператор объявил только parent ('Tom Ford' без 'Tom Ford Beauty'), beauty-SKU падает в parent bucket — это **операторский opt-in**, не automatic, и явно задокументировано в CONTEXT.md.

## Operator opt-in disambiguation

Если оператор хочет различать parent brand и его brand-extension family:
1. Добавить parent (`Tom Ford`) в viled_brands list.
2. Добавить extension (`Tom Ford Beauty`) отдельной строкой в viled_brands list.
3. Longest-prefix selection ставит beauty-SKU в bucket['tom-ford-beauty'], parent-SKU в bucket['tom-ford'], **без overlap**.

Если оператор хочет считать всю семью одним брендом — оставить только parent. Beauty-SKU попадут в parent bucket по depth-2 fallback. Это намеренное поведение.

## Тестовое покрытие

- `tests/unit/test_brand_token_index.py` (7 тестов, новый файл): `test_brand_token_index_tom_ford_does_not_contaminate_tom_ford_beauty` — структурный гарант
- `tests/unit/test_intersect_brand_pool.py` (расширен): `test_intersect_against_real_sitemap_shape` (6 sub-tests против realistic 45K-style sitemap), `test_intersect_no_substring_lookup_in_function_body` (inspect.getsource grep gate), AST param-rename gate
- `tests/integration/test_run_e2e_with_phase2_mocks.py`: `test_e2e_brand_intersect_against_realistic_sitemap_shape` — `unmatched_viled_brands == 0` для givenchy + jo_malone_london + tom_ford

192/192 тестов зелёные после landing fix'а.

## Live verification

run-43 (operator KZ-laptop, 2026-05-06): `unmatched_viled_brands` упал 2 → 1. `givenchy` сматчился (был unmatched в run-42). `jo_malone_london` остался unmatched отдельно — separate ops-investigation (либо brand отсутствует в KZ goldapple sitemap, либо token shape mismatch).

## Connections

- [[2026-05-06 — Phase 3 closed через Wave 6 live-smoke + Wave 7 gap-closure]]
- [[Парсим viled целиком, goldapple только по пересекающимся брендам]] — depends on this
- [[Slug-эвристика для viled→goldapple, не explicit YAML]] — extended (slug-эвристика теперь bucket-keyed)
- D-306 NORM-06 forward direction — consumes `compute_norm06_forward(viled_brands, aliases, brand_bucket)` (signature shape change)

## Файлы

- `src/ga_crawler/enumeration/goldapple_sitemap.py` — `index_by_brand_token`, `BRAND_TOKEN_MAX_DEPTH=3`
- `src/ga_crawler/enumeration/slug.py` — refactored `intersect_brand_pool(viled_brands, aliases, brand_bucket)`
- `src/ga_crawler/runner/stats.py` — `compute_norm06_forward(viled_brands, aliases, brand_bucket)` param rename
- `src/ga_crawler/runners/goldapple_run.py` — Step 3.5 precompute `known_brand_tokens` whitelist
- `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` — D-305 refined wording (commit `c662d72`)
