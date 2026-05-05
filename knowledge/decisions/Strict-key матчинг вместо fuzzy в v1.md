---
tags: [decision, matching, simplicity]
date: 2026-05-05
---

# Strict-key матчинг вместо fuzzy в v1

Точное совпадение нормализованного ключа `(brand_norm, name_norm, volume_norm)`. Никакого Levenshtein, token-set, или ML.

## Почему

- **Меньше false positives** — fuzzy матчинг неизбежно даёт кросс-объёмные ошибки (`30мл` vs `50мл` через token-set могут совпасть)
- **Проще диагностировать** — match/no-match бинарно, причину видно сразу
- **Покрытия достаточно** при качественной нормализации (60–80% expected coverage)
- **Нет ML-модели в проде** — нет дрифта, нет переобучений

## Условие триггера v2 (fuzzy)

Если match-rate стабильно ниже приемлемого после 4 недель — v2 fuzzy с очередью ручного review. См. `MATCH-V2-01` в REQUIREMENTS.md.

## Реальная подложка

Дoминирующий источник пропусков на этом рынке — не "слабый алгоритм матчинга", а Cyrillic↔Latin расхождение брендов. Решается **brand-alias таблицей**, а не fuzzy. См. [[Brand-alias YAML — это v1 deliverable, не v2]].

## Связанные

- [[Match-rate — KPI с первой недели]]
- [[Volume как value-object с multipack-флагом]]
- [[Match-rate резко упал — проверь brand-alias таблицу]]
