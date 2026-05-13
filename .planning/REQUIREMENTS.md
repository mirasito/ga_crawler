# Requirements — Milestone v1.1

> **Milestone:** v1.1 Parser bug fixes + operator deploy unblock
> **Status:** Phase 8 complete (5/5 PARSE-FIX reqs Closed) — Phases 9-11 pending
> **Started:** 2026-05-13

## Milestone Goal

Починить три парсер-бага найденных в live-run #13 (2026-05-13), добавить live-HTML harness чтобы такой drift больше не пропускали, закрыть paperwork-debt из v1.0 audit и развернуть на production VPS чтобы первое воскресенье вернуло корректный отчёт.

## v1.1 Requirements

### Bucket A — Parser Bug Fixes (must-have) → Phase 8

- [x] **PARSE-FIX-01**: Goldapple parser извлекает `volume_raw` из structured PDP-блока (`78 ОБЪЁМ / МЛ`) с selectolax 0.4 Lexbor `:contains` selector; ≥90% non-null rate на не-volumeless категориях — completed Plan 08-02 (2026-05-13)
- [x] **PARSE-FIX-02**: Goldapple parser извлекает `brand` и `name` раздельно через h1 `.brand`/`.name` CSS-class spans (W0 pivot — `<meta itemprop="name">` premise invalidated per 08-01-SUMMARY); invariant canary `brand.lower() not in name.lower()` softened to log-only warning — completed Plan 08-03 (2026-05-13)
- [x] **PARSE-FIX-03**: Viled parser извлекает `volume_raw` из `props.pageProps.attributes[0].attributes[].name == "Размер"` JSON-поля; fallback на regex по `name` только если отсутствует — completed Plan 08-04 (2026-05-13)
- [x] **PARSE-FIX-04**: Sanity-gate null-rate fail: запуск с `goldapple_volume_norm` null rate >50% → run помечается `failed` с reason `parser_drift_null_volume_rate` — completed Plan 08-05 (2026-05-13)
- [x] **PARSE-FIX-05**: Smoke-probe URL rotation: `runner/gates.py:36` SMOKE_URLS включает по 1 URL каждой найденной shape variant (STEREOTYPE-style + Armani-style + Givenchy-baseline) — completed Plan 08-05 (2026-05-13)

### Bucket B — Live-HTML Harness (must-have B1-B3, B6; should-have B4-B5) → Phase 9

- [ ] **TEST-HARNESS-01**: syrupy 4.7 добавлен как dev-dependency; `HTMLSnapshotExtension(SingleFileSnapshotExtension)` с `file_extension="html"` и `WriteMode.TEXT`
- [ ] **TEST-HARNESS-02**: Captured HTML живёт в `tests/fixtures/<retailer>/_live-YYYY-MM-DD-<slug>.html` с sidecar JSON `{date, url, status, html_size, title, camoufox_version}`
- [ ] **TEST-HARNESS-03**: `tests/live/test_parser_drift.py` с `@pytest.mark.live` маркером — re-fetches SMOKE_URLs, runs parsers, asserts invariants. Опт-ин через `pytest -m live`
- [ ] **TEST-HARNESS-04** (P2 cheap-bundle): brand-coverage quota canary — `≥1 fixture per active brand` для брендов виденных в последние 4 weekly runs
- [ ] **TEST-HARNESS-05** (P2 cheap-bundle): `python -m ga_crawler capture-fixtures` CLI subcommand (6-й — обновляет Phase 7 source-locked canary)
- [ ] **TEST-HARNESS-06**: Pydantic validation at `SqliteSnapshotWriter` boundary — defense-in-depth: `RawProduct` model с `volume_raw: NonEmptyStr | None`, `brand: NonEmptyStr | None`, raise on write если schema violated

### Bucket C — Audit Paperwork Carryover (must-have) → Phase 10

- [ ] **AUDIT-DEBT-01**: `SECURITY.md` для Phase 2 (viled crawl + storage) — retroactive threat model + 6/6 mitigation evidence
- [ ] **AUDIT-DEBT-02**: `SECURITY.md` для Phase 4 (matcher) — retroactive threat model + mitigation evidence
- [ ] **AUDIT-DEBT-03**: `SECURITY.md` для Phase 6 (Telegram delivery) — retroactive threat model + mitigation evidence
- [ ] **AUDIT-DEBT-04**: `VALIDATION.md` для Phase 4 (matcher) — Nyquist coverage matrix против 465+ matcher тестов
- [ ] **AUDIT-DEBT-05**: Audit verdict flip — `milestones/v1.0-MILESTONE-AUDIT.md` обновлён `tech_debt` → `clean` после AUDIT-DEBT-01..04

### Bucket D — Operator Deploy на Yandex Cloud kz1 (must-have) → Phase 11

- [ ] **DEPLOY-01**: Yandex Cloud kz1 VPS provisioned (Ubuntu 24.04, 2 vCPU/4GB/30GB SSD, KZ-region IP, SSH ключ загружен)
- [ ] **DEPLOY-02**: `bin/setup-vps.sh` — idempotent thin wrapper над README §2 шагами 1-7; structural canary test `tests/test_phase07_setup_vps_shape.py`
- [ ] **DEPLOY-03**: `load_dotenv(verbose=True)` at `src/ga_crawler/__main__.py` entrypoint — fixes D-705 recurrence из run #13 (`delivery_status=skipped_no_credentials` несмотря на наличие `.env`)
- [ ] **DEPLOY-04**: README §2 step 1.5: `sudo timedatectl set-timezone Asia/Almaty` (Pitfall #7 mitigation для Yandex Cloud KZ default Moscow TZ)
- [ ] **DEPLOY-05**: Pre-deploy Camoufox×Yandex compatibility smoke probe — verify Camoufox 0.4.11 launches на Yandex Cloud Ubuntu 24.04 BEFORE cron handoff
- [ ] **DEPLOY-06**: Egress connectivity smoke — `curl -I` to api.telegram.org, hc-ping.com, goldapple.kz, viled.kz from Yandex Cloud KZ instance (KZ→external network проверка)
- [ ] **DEPLOY-07**: First production Sunday cron tick — 2026-05-XX 23:00 Almaty → Telegram доставка xlsx с `match_count > 0` в business chat
- [ ] **DEPLOY-08**: `/gsd-verify-work 7` resume — 4 blocked UAT items в `07-HUMAN-UAT.md` flips to `pass` (SC#1 cron timing, SC#5 deliberate-failure end-to-end, smoke gate, HC.io↔Telegram integration)

## Future Requirements (deferred)

Из v1.0 STATE.md Deferred Items — переносятся в v1.2 или v2.0:

- [Deferred] viled SSR pagination — page-1 limitation 82 SKU
- [Deferred] Docker image (INFRA-V2-04 / D-710) — Camoufox Firefox 135 vs Playwright image incompatibility
- [Deferred] Camoufox+EU smoke from Hetzner (D-08 IPRoyal trial revival если KZ-IP regresses)
- [Deferred] KZ-legal / ToS review (30 min with lawyer)

## Out of Scope (v1.1)

Эти возможности явно НЕ входят в v1.1 — defer на v2.0+:

- **Fuzzy matching** — strict-key `brand+name+volume` остаётся; fuzzy откладывается до доказательства low-coverage в проде
- **Web dashboard / UI** — Telegram + Excel закрывают потребность
- **Real-time / daily monitoring** — еженедельной частоты достаточно
- **Парсинг других маркетплейсов** — фокус на goldapple.kz vs viled.kz
- **Картинки / описания товаров** — не нужны для ценового сравнения
- **Postgres миграция** — SQLite справляется; триггер migration пока не сработал
- **Полный парсинг goldapple (все бренды)** — только brand-intersect остаётся
- **Gold Card / залогиненные цены** — риск блокировки аккаунта, не справедливое сравнение
- **ML / image scraping** — out of domain

## Traceability

| Phase | REQ-IDs | Count | Status |
|-------|---------|-------|--------|
| Phase 8 — Parser Bug Fixes | PARSE-FIX-01, PARSE-FIX-02, PARSE-FIX-03, PARSE-FIX-04, PARSE-FIX-05 | 5 | Complete (2026-05-13) |
| Phase 9 — Live-HTML Harness | TEST-HARNESS-01, TEST-HARNESS-02, TEST-HARNESS-03, TEST-HARNESS-04, TEST-HARNESS-05, TEST-HARNESS-06 | 6 | Pending |
| Phase 10 — Audit Paperwork Carryover | AUDIT-DEBT-01, AUDIT-DEBT-02, AUDIT-DEBT-03, AUDIT-DEBT-04, AUDIT-DEBT-05 | 5 | Pending |
| Phase 11 — Operator Deploy на Yandex Cloud kz1 | DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05, DEPLOY-06, DEPLOY-07, DEPLOY-08 | 8 | Pending |
| **Total** | — | **24/24** | All v1.1 reqs mapped 1:1; 5/24 Complete |

### Per-Requirement Mapping

| Requirement | Phase | Status |
|-------------|-------|--------|
| PARSE-FIX-01 | Phase 8 | Complete |
| PARSE-FIX-02 | Phase 8 | Complete |
| PARSE-FIX-03 | Phase 8 | Complete |
| PARSE-FIX-04 | Phase 8 | Complete |
| PARSE-FIX-05 | Phase 8 | Complete |
| TEST-HARNESS-01 | Phase 9 | Pending |
| TEST-HARNESS-02 | Phase 9 | Pending |
| TEST-HARNESS-03 | Phase 9 | Pending |
| TEST-HARNESS-04 | Phase 9 | Pending (P2 cheap-bundle — bundle if quick, else defer to v1.2) |
| TEST-HARNESS-05 | Phase 9 | Pending (P2 cheap-bundle — bundle if quick, else defer to v1.2) |
| TEST-HARNESS-06 | Phase 9 | Pending |
| AUDIT-DEBT-01 | Phase 10 | Pending |
| AUDIT-DEBT-02 | Phase 10 | Pending |
| AUDIT-DEBT-03 | Phase 10 | Pending |
| AUDIT-DEBT-04 | Phase 10 | Pending |
| AUDIT-DEBT-05 | Phase 10 | Pending |
| DEPLOY-01 | Phase 11 | Pending |
| DEPLOY-02 | Phase 11 | Pending |
| DEPLOY-03 | Phase 11 | Pending |
| DEPLOY-04 | Phase 11 | Pending |
| DEPLOY-05 | Phase 11 | Pending |
| DEPLOY-06 | Phase 11 | Pending |
| DEPLOY-07 | Phase 11 | Pending |
| DEPLOY-08 | Phase 11 | Pending |

**Coverage:** 24/24 v1.1 requirements mapped to exactly one phase. No orphans, no duplicates. 5/24 Complete (Phase 8 closed); 19/24 Pending (Phases 9-11).

---
*Last updated: 2026-05-13 — Phase 8 closed via Plan 08-05 doc cascade (5/5 PARSE-FIX reqs Complete); Phases 9-11 remain Pending. Previously: traceability filled by `gsd-roadmapper` after v1.1 roadmap approval.*
