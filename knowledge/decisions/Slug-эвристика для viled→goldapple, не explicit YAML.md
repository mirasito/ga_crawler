---
tags: [decision, phase-3, brand-alias, normalization, trade-off]
date: 2026-05-06
phase: 3
decisions: [D-304, D-305]
---

# Slug-эвристика для viled→goldapple, не explicit YAML

Phase 3 определяет goldapple-slug-набор для каждого viled-бренда **через slug-эвристику** от `brand_norm + aliases`, **не** через явное поле `goldapple_slugs: [...]` в alias YAML. Trade-off принят явно: ниже manual курация ценой false-positive риска.

## Алгоритм

Из каждой alias-строки бренда (например `Estée Lauder`, `Эсте Лаудер`) slug-fier генерирует **два** варианта:

1. **ASCII**: NFKD + accent strip + Cyrillic→Latin transliterate + lowercase + non-alphanum → `-` + collapse multi-`-` → `estee-lauder`
2. **Cyrillic-preserved**: NFKD + lowercase + non-alphanum → `-` → `эсте-лаудер`

Каждый кандидат проверяется **exact-match** против goldapple sitemap-slug пула (1,461 slug). Никакого substring/prefix/fuzzy — это исключает «Tom Ford → tom-ford-beauty» false-positive.

## Trade-off (зафиксирован явно)

- **Плюс:** оператор не курирует goldapple-slug per-brand вручную в YAML. Меньше PR-шума.
- **Минус:** Cyrillic-only goldapple-slug, на которые ни одна viled-alias не slug-fy-ится → бренд недостижим. Mitigation: D-307 week-over-week NEW goldapple-slug diff в NORM-06 → operator увидит и добавит alias.
- **Минус:** false-positive при бренд-сходных именах. Mitigation: exact-match (не substring) убивает большинство.

## Почему **не** explicit `goldapple_slugs:`

Альтернатива — поле в alias YAML на бренд, ручная курация. Отвергнуто: пользователь предпочёл minimum-curation подход. Если эвристика покажет высокий false-positive-rate в реальных runs — **возврат к explicit подходу** документирован как deferred review trigger в 03-CONTEXT.md.

## Почему **не** rapidfuzz

Fuzzy slug-matching откладывается в v2 (REQ MATCH-V2-01). Strict-key-only — invariant v1.

## Связанные

- [[Strict-key матчинг вместо fuzzy в v1]] — родительский invariant
- [[Brand-alias YAML — это v1 deliverable, не v2]] — alias-YAML контракт
- [[Парсим viled целиком, goldapple только по пересекающимся брендам]] — высокоуровневое решение
- [[Sitemap-only URL pool для goldapple, без brand-facet rendering]] — pipeline upstream
- `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` §Brand-alias coverage — D-304, D-305
