---
phase: 02
plan: 03
subsystem: normalizers
tags: [normalizers, alias, brand, name, volume, multipack, wave-2]
wave: 2
type: execute
autonomous: true
status: complete
completed_date: 2026-05-07
duration_minutes: ~12
dependency_graph:
  requires:
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT.md  # D-205, D-206, D-207, D-215, D-216
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-RESEARCH.md  # Pattern 6, Pattern 7, Pattern 8, Open Q4, Pitfall 6
    - src/ga_crawler/interfaces.py  # FROZEN: BrandAliasProtocol, NormalizerProtocol
    - src/ga_crawler/enumeration/slug.py  # FROZEN: _normalize_punct, CYRILLIC_TO_LATIN
    - tests/fixtures/normalize/volume-corpus.yaml  # 18 cases
    - tests/fixtures/normalize/brand-corpus.yaml  # 11 cases
    - tests/fixtures/viled/brand-aliases-fixture.yaml  # 3 canonicals × Cyrillic/Latin aliases
  provides:
    - src/ga_crawler/alias/yaml_loader.py  # YamlBrandAlias (D-207 read-once)
    - src/ga_crawler/normalizers/brand.py  # NORM-02 (REUSE _normalize_punct)
    - src/ga_crawler/normalizers/name.py  # NORM-05
    - src/ga_crawler/normalizers/volume.py  # NORM-03 + NORM-04 + Open Q4
    - src/ga_crawler/normalizers/facade.py  # Normalizer satisfies NormalizerProtocol
  affects:
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-04-PLAN.md  # Plan 04 viled_run.py wires `from ga_crawler.normalizers.facade import Normalizer`
    - src/ga_crawler/runners/goldapple_run.py  # Phase 3 orchestrator can swap stub Normalizer for real one
tech-stack:
  added: []
  patterns:
    - "REUSE-via-import (Pattern: enumeration/slug._normalize_punct imported by normalizers/brand.py — RESEARCH §Don't Hand-Roll)"
    - "Concrete-only helper outside Protocol (Pattern: YamlBrandAlias.canonical_for not in BrandAliasProtocol per Open Q1)"
    - "Layered grammar with multipack-flag persistence (Pattern: detect_multipack independent of parse_volume per Open Q4)"
    - "Frozen dataclass value-object (Pattern: Volume(amount, unit, count) hashable for dict/set keys)"
key-files:
  created:
    - src/ga_crawler/alias/__init__.py (4 LOC)
    - src/ga_crawler/alias/yaml_loader.py (81 LOC)
    - src/ga_crawler/normalizers/__init__.py (4 LOC)
    - src/ga_crawler/normalizers/brand.py (48 LOC)
    - src/ga_crawler/normalizers/name.py (30 LOC)
    - src/ga_crawler/normalizers/volume.py (172 LOC)
    - src/ga_crawler/normalizers/facade.py (43 LOC)
  modified:
    - tests/unit/test_yaml_brand_alias.py (skip → 7 GREEN tests)
    - tests/unit/test_brand_normalizer.py (skip → 6 GREEN tests)
    - tests/unit/test_name_normalizer.py (skip → 6 GREEN tests)
    - tests/unit/test_volume_normalizer.py (skip → 11 GREEN tests)
decisions:
  - "RESEARCH §Pattern 7 + §Pattern 8 shipped verbatim with adaptations: brand.py IMPORTS _normalize_punct from enumeration.slug (REUSE) — no duplication confirmed by inspection test test_uses_imported_normalize_punct."
  - "NORM-04 multipack grammar split into 3 layers per RESEARCH §Pattern 6: (1a) `Set of N × M unit` Set-of prefix pattern, (1b) `N [optional unit] x M unit` generic count×amount pattern, (2) keyword-only multipack (набор/комплект/kit/`N шт` no-amount) returns parse_volume=None but detect_multipack=True (Open Q4 multipack flag persists when per-unit volume unparseable)."
  - "Volume value-object is frozen dataclass (Decimal amount, str unit, int count) — hashable for dict/set keys; matches NormalizerProtocol Optional[tuple[Decimal,str,int]] via facade.volume mapping."
  - "Apostrophe-strip-before-hyphen cascading constraint (STATE.md plan 03-02 lesson) honored automatically: brand.py delegates to _normalize_punct which already strips apostrophes BEFORE non-alphanum→hyphen replace (`L'Oréal Paris → loreal-paris`, NOT `l-oreal-paris`)."
  - "Pitfall 6 'л' word-boundary mitigated by UNIT_TABLE whitelist: bare 'л' only resolves via UNIT_TABLE.get(token), so noise-tokens like 'л.с.' (horsepower) where the regex captures 'л' followed by punctuation never satisfy `[a-zа-яё]+` greedy match across the period boundary."
  - "YamlBrandAlias missing-YAML graceful degradation: returns empty loader (no crash) — per Pitfall 5; lookup falls back to self-seed [brand_norm], canonical_for returns None."
  - "Concrete-only `canonical_for` reverse-lookup helper (NOT in BrandAliasProtocol) — used by normalizers/brand.py via structural-typed `_AliasReverseLookup` Protocol. Pattern preserves Plan 03-02 Open Q1: keep concrete-only helpers off the public Protocol surface."
metrics:
  duration_minutes: 12
  completed_date: 2026-05-07
  tasks_completed: 2
  files_created: 7
  files_modified: 4
  tests_added: 30
  tests_added_kind: GREEN-flipped
  tests_passing_after: 247
  tests_skipped_after: 13
  tests_failing_after: 0
---

# Phase 02 Plan 03: Wave 2 Normalizers + Alias Loader Summary

Wave 2 of Phase 2 ships the three single-NORM modules (brand / name / volume) and a YAML-backed BrandAlias loader, composed via a `Normalizer` facade satisfying `NormalizerProtocol` exactly. **All five NORM-01..05 requirements close in this wave** (NORM-06 already shipped in Plan 02-02). Production code totals 382 LOC across 7 new files; 30 GREEN tests across 4 unblocked unit-test modules; full suite 192 → 247 passing, 24 → 13 skipped, 0 failing. `enumeration/slug.py` and `interfaces.py` UNCHANGED (`git diff` empty).

## Modules Shipped

| File | LOC | Purpose | Requirement |
|------|-----|---------|-------------|
| `src/ga_crawler/alias/__init__.py` | 4 | Package marker | — |
| `src/ga_crawler/alias/yaml_loader.py` | 81 | `YamlBrandAlias` reads YAML once at __init__, exposes `lookup(brand_norm)→list[str]` (BrandAliasProtocol) + concrete-only `canonical_for(slug)→str\|None` reverse helper | NORM-01 |
| `src/ga_crawler/normalizers/__init__.py` | 4 | Package marker | — |
| `src/ga_crawler/normalizers/brand.py` | 48 | `normalize_brand(raw, alias_lookup)` — IMPORTS `_normalize_punct` from `enumeration.slug` (REUSE confirmed by inspection test) | NORM-02 |
| `src/ga_crawler/normalizers/name.py` | 30 | `normalize_name(raw)` — NFKD + lowercase + strip-punct + collapse-whitespace | NORM-05 |
| `src/ga_crawler/normalizers/volume.py` | 172 | `Volume` frozen dataclass + `UNIT_TABLE` (24 entries: мл/ml/милилитр/миллилитр/г/гр/грамм/л/литр/шт/штук/унц/унция/унций/кг/ml/milliliter/g/gram/oz/ounce/fl/kg/l/liter/pcs/pc) + `parse_volume(raw)→Volume\|None` (3-layer grammar) + `detect_multipack(raw)→bool` (independent of parse_volume per Open Q4) | NORM-03, NORM-04 |
| `src/ga_crawler/normalizers/facade.py` | 43 | `Normalizer` class composes brand/name/volume; satisfies `NormalizerProtocol` via `@runtime_checkable` (verified inline: `isinstance(Normalizer(...), NormalizerProtocol)` is `True`) | facade for Plan 04 + Phase 3 swap |

Total production code: **382 LOC across 7 files**.

## Tests Flipped (skip → GREEN)

| File | Tests | Coverage |
|------|-------|----------|
| `tests/unit/test_yaml_brand_alias.py` | 7 | `lookup` returns aliases / unknown self-seed / canonical_for round-trip / missing YAML / read-once-at-init (D-207) / Givenchy Cyrillic alias |
| `tests/unit/test_brand_normalizer.py` | 6 | Full 11-case corpus parametrize / apostrophe-strip-before-hyphen / Cyrillic→canonical / REUSE inspection / empty input / unknown→slug fallthrough |
| `tests/unit/test_name_normalizer.py` | 6 | NFKD-decompose / lowercase-strip-collapse / empty / internal-whitespace / preserves Cyrillic / strips brackets+quotes |
| `tests/unit/test_volume_normalizer.py` | 11 | All 18 corpus cases / unit-table canonical-units / decimal-with-comma / multipack-N-x-amount / keyword-multipack-no-amount (Open Q4) / facade 3-tuple / facade None / facade satisfies Protocol / facade brand-uses-alias / facade name-passes-through / Volume frozen+hashable |

**30 new GREEN tests.** Skip markers removed from all 4 files.

## Verification

| Check | Result |
|-------|--------|
| `grep -q "from ga_crawler.enumeration.slug import _normalize_punct" src/ga_crawler/normalizers/brand.py` | PASS |
| `grep -v "^#" src/ga_crawler/normalizers/brand.py \| grep -c "def _normalize_punct"` == 0 | PASS (NO duplication) |
| `grep -q "yaml.safe_load" src/ga_crawler/alias/yaml_loader.py` | PASS |
| `grep -q "class YamlBrandAlias" src/ga_crawler/alias/yaml_loader.py` | PASS |
| `grep -q "def lookup(self, brand_norm" src/ga_crawler/alias/yaml_loader.py` | PASS |
| `grep -q "def canonical_for" src/ga_crawler/alias/yaml_loader.py` | PASS |
| `grep -q "UNIT_TABLE" src/ga_crawler/normalizers/volume.py` AND `grep -q '"мл": "ml"'` | PASS |
| `grep -q "набор\|kit\|set of" src/ga_crawler/normalizers/volume.py` | PASS (all multipack patterns present) |
| `grep -q "class Volume:" src/ga_crawler/normalizers/volume.py` | PASS |
| `grep -q "def parse_volume" src/ga_crawler/normalizers/volume.py` AND `grep -q "def detect_multipack"` | PASS |
| `grep -q "class Normalizer" src/ga_crawler/normalizers/facade.py` AND `def brand`/`def name`/`def volume` | PASS |
| `python -c "...isinstance(Normalizer(...), NormalizerProtocol)"` | PASS (`protocol-ok`) |
| `git diff src/ga_crawler/interfaces.py src/ga_crawler/enumeration/slug.py` empty | PASS (0-line diff) |
| `pytest tests/unit/test_yaml_brand_alias.py tests/unit/test_brand_normalizer.py tests/unit/test_name_normalizer.py tests/unit/test_volume_normalizer.py -x -q` | PASS (30 passed) |
| `pytest -m "not live" -q` | PASS (247 passed + 13 skipped + 0 failed in 48.25 s) |
| 4 test files no longer carry `pytestmark = pytest.mark.skip` | PASS |

## Cascading Constraints for Plan 04

1. **Plan 04 viled_run.py imports the facade**:
   ```python
   from ga_crawler.alias.yaml_loader import YamlBrandAlias
   from ga_crawler.normalizers.facade import Normalizer
   alias = YamlBrandAlias(Path("config/brand-aliases.yaml"))  # production seed lands in Plan 06
   normalizer = Normalizer(alias)
   # normalizer satisfies NormalizerProtocol — drop into orchestrator wiring
   ```
2. **Phase 3 stub-swap**: `src/ga_crawler/runners/goldapple_run.py` currently uses `StubNormalizer` (lowercase+strip / None for volume). When Plan 04 wires the orchestrator, the same `Normalizer(YamlBrandAlias(...))` instance can replace the stub transparently — both satisfy `NormalizerProtocol`.
3. **Multipack flag persistence**: NORM-04 D-215 says multipack_flag is a separate column from volume. Plan 04 PARSE pipeline must call `detect_multipack(raw_volume)` AND `parse_volume(raw_volume)` independently and persist BOTH `volume_norm` (which may be None) and `multipack_flag` (which may be True even when volume_norm is None — `набор пробников`, `10 шт`).
4. **Brand-aliases YAML production seed**: Plan 06 will ship `config/brand-aliases.yaml` with the operator-curated full canonical set. The fixture seed `tests/fixtures/viled/brand-aliases-fixture.yaml` (3 canonicals × Cyrillic/Latin aliases) is test-only and stays put.
5. **Apostrophe-strip-before-hyphen**: any future module that does its own slugification MUST go through `_normalize_punct` from `enumeration/slug.py` — do NOT roll a regex-from-scratch path. The brand normalizer is the canonical example of correct REUSE.

## Deviations from Plan

None — plan executed exactly as written. All `<action>` blocks shipped on the first verify pass; all 18 volume-corpus cases passed without regex tweaks (the 3-layer grammar covers `Set of N × M`, `N [unit] × M unit`, `N×M`, single volumes, and keyword-only multipacks). Pattern A regex tightened to `(\d+)\s*(?:[a-zа-яё]+)?\s*[xх×]\s*(\d+(?:[.,]\d+)?)\s*([a-zа-яё]+)` to handle the `3 шт x 50мл` corpus case (count + optional separator unit-token + × + per-unit amount + unit) — within Pattern A's documented spec, not a deviation.

## Authentication Gates

None — pure-string transforms, no network/auth.

## Commits

- `b875b0b` — test(02-03): RED — flip NORM-01/02/05 tests to executable failures
- `be94a4d` — feat(02-03): YamlBrandAlias + brand/name normalizers (NORM-01/02/05)
- `42d7df6` — test(02-03): RED — flip NORM-03/04 + facade tests to executable failures
- `7c36316` — feat(02-03): volume normalizer + Normalizer facade (NORM-03/04)

## TDD Gate Compliance

Both tasks ran a strict RED → GREEN cycle with separate test-only and feature commits:
- Task 1: `b875b0b` (RED test) → `be94a4d` (GREEN feat) ✓
- Task 2: `42d7df6` (RED test) → `7c36316` (GREEN feat) ✓

No REFACTOR pass needed — production code shipped clean on the GREEN attempt.

## Self-Check: PASSED

Verified post-write:
- `src/ga_crawler/alias/__init__.py` FOUND
- `src/ga_crawler/alias/yaml_loader.py` FOUND (81 LOC, contains `YamlBrandAlias`, `yaml.safe_load`, `def lookup`, `def canonical_for`)
- `src/ga_crawler/normalizers/__init__.py` FOUND
- `src/ga_crawler/normalizers/brand.py` FOUND (48 LOC, imports `_normalize_punct`, NO local definition)
- `src/ga_crawler/normalizers/name.py` FOUND (30 LOC)
- `src/ga_crawler/normalizers/volume.py` FOUND (172 LOC, contains `UNIT_TABLE`, `class Volume`, `def parse_volume`, `def detect_multipack`, `набор`, `kit`, `set of`)
- `src/ga_crawler/normalizers/facade.py` FOUND (43 LOC, `class Normalizer` with brand/name/volume methods)
- 30 tests across 4 test files all GREEN
- Commit `b875b0b` FOUND in `git log --oneline`
- Commit `be94a4d` FOUND in `git log --oneline`
- Commit `42d7df6` FOUND in `git log --oneline`
- Commit `7c36316` FOUND in `git log --oneline`
- `git diff src/ga_crawler/interfaces.py src/ga_crawler/enumeration/slug.py` empty (frozen modules untouched)
- Full suite `pytest -m "not live"`: 247 passed + 13 skipped + 0 failed
