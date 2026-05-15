---
tags: [decision, testing, live-harness, operator-runbook, cron-isolation, v1-1, phase-9]
date: 2026-05-14
phase: 9-contexted
status: locked
---

# `pytest -m live` — operator-only opt-in, документируется в README §8

## Утверждение

Phase 9 TEST-HARNESS-03 live-drift test ships как **operator-only opt-in**. weekly-run.sh **не меняется**. Cron **не запускает** `pytest -m live`. Документация — новый README §8 «Live HTML harness» с операторским runbook'ом.

Operator решает когда запустить:
- Pre-deploy (after pulling new parser fixes)
- Post-suspected-drift (operator замечает empty Excel или low match_count в weekly run)
- Quarterly/monthly maintenance refresh

Drift failures emit `.planning/research/parser-drift-YYYY-MM-DD.md` (diagnostic markdown с per-fixture per-assertion verdict + suggested next steps).

## Reasoning

### 1. ARCH Open Q2 рекомендует manual для v1.1

`.planning/research/ARCHITECTURE.md` §B Open Question 2: *"Live-test CI integration — pytest -m live manual ops-runbook OR scheduled? (Recommend: manual for v1.1; auto-schedule deferred to v1.2)"*. Это explicit рекомендация research-фазы; не было обоснования отклоняться от неё.

V1.2 reconsider если operator usage pattern эмпирически покажет что manual discipline проседает (например, operator забывает запускать pre-deploy → drift просыпается в production).

### 2. PITFALLS #2 риски привязки к weekly cron

`.planning/research/PITFALLS.md` §2 «Live-HTML cassettes captured once and never refreshed → harness goes stale» — argues FOR weekly auto-refresh job. Но детально читая:

- *"a separate cron entry (or GitHub Action with VPS secret)"* — `separate`, not coupled to weekly-run.sh
- *"Run cassette refresh from a separate working tree (`/opt/ga_crawler-test/`) or as a non-cron operator-initiated task"* — explicit recommendation против co-scheduling with weekly-run

Phase 9 v1.1 = operator-initiated; Phase 11 doesn't add cron entry; v1.2 reconsider separate cron entry.

### 3. weekly-run.sh blast radius

weekly-run.sh — это **production critical path** (Phase 7 D-709 9 invariants). Добавление `pytest -m live` шага раздувает blast radius:

- Camoufox 30+ sec launch latency (per-fixture × 3 fixtures = 90+ sec)
- Risk: Camoufox installation drift между production VPS и dev → live test passes locally fails on VPS
- Cron mailbox shows failure → operator alert burst для **test infrastructure** issues, not production data issues
- Phase 11 first cron tick — фокусируется на main path, не test instrumentation

Per Phase 8 lesson [[Code review ловит deploy-blocking defects невидимые plan-checker'у — uv PATH, useradd -m collision, sudo без sudoers]] — production cron path должен иметь МИНИМАЛЬНЫЙ surface area для unknowns. Test execution в cron path = unknown surface area.

### 4. GitHub Action wouldn't help для KZ-IP scenario

Альтернатива — GHA scheduled workflow. Но Camoufox + KZ-IP requirement (Phase 1 spike MEMO: geoip=true + Tier-2 Camoufox без proxy) делает GHA вариант неработоспособным:

- Default GHA EU-IP runner → geo-fake не соответствует production VPS geo (Phase 7 setup ломается)
- Self-hosted runner на VPS → тот же VPS что и production → нет дополнительной isolation
- Self-hosted runner на separate KZ machine → infrastructure overhead для v1.1 (нет такого machine)

V1.2 reconsider self-hosted GHA runner если operator team grows и manual discipline проседает.

### 5. README §8 — operator-runbook home

Phase 7 D-707 уже locked decision: «README 10 sections RU primary EN code — single file для operator-is-developer team». Phase 9 продолжает этот pattern, добавляя §8 «Live HTML harness» с:

- Quick reference table: когда запускать (pre-deploy, post-drift-suspicion, monthly maintenance)
- Commands: `uv run pytest -m live` (cassette-replay mode) и `uv run pytest -m live --refresh-live` (Camoufox re-fetch mode)
- Output interpretation: что значит `parser-drift-YYYY-MM-DD.md`, как читать per-fixture verdict
- Troubleshooting: stale fixture warning (>30 дней), как scrub'нуть accidentally-leaked credentials, как commit'ить refresh'нутые fixtures
- Pitfalls: НЕ запускать с production `.env` (TG_BOT_TOKEN leak risk если capture-fixtures CLI ширлокует HTML)

## Implication

- `bin/weekly-run.sh` — НЕ меняется (Phase 7 D-709 9 invariants preserved)
- `.github/workflows/` — НЕ создаётся live-tests workflow (deferred to v1.2)
- `crontab` (production VPS) — НЕ добавляется entry для `pytest -m live` (deferred to v1.2)
- `README.md` §8 (new) — `## 8. Live HTML harness — operator manual runbook` с командами + drift output interpretation
- `tests/live/test_parser_drift.py` — pytest live-marked test, default skipped (`pytest -m "not live"` уже the default), opt-in через `-m live`
- Drift output spec — `parser-drift-YYYY-MM-DD.md` template следует Phase 1 spike memo convention (per-fixture verdict block + suggested-next-steps tail)

## Failure mode handling

Когда `pytest -m live` fails (либо cassette-replay assert либо `--refresh-live` syrupy diff):

1. Test prints fixture path + assertion failure + diagnostic to stderr
2. `parser-drift-YYYY-MM-DD.md` написан в `.planning/research/` с структурой:
   ```
   # Parser drift report — YYYY-MM-DD
   ## Failing fixtures
   - tests/fixtures/goldapple/_live-2026-05-13-stereotype.html: brand assertion failed (got "STEREOTYPE sago", expected non-empty after h1 .brand extraction)
   ## Suggested next steps
   - Compare against last working sidecar JSON
   - Re-fetch fixture via --refresh-live to see if live shape changed
   - If shape changed, open Phase 12 (or future fix-phase) with parser update
   ```
3. Operator решает: refresh fixture (drift confirmed → file fix-phase) или ignore (transient anti-bot challenge → wait + retry)

## Alternative considered

- **Auto-attached к weekly cron как 7-й шаг с diff-to-ops** — REJECTED. Расширяет cron blast radius; Camoufox 30s+ flakes положат weekly-run; ops alert fatigue для test infrastructure
- **Separate cron entry (Saturday 20:00 Almaty) + Telegram ops alert** — REJECTED для v1.1. Phase 11 еще не лёг; operator-level concern; PITFALLS warns про cron-cross-contamination требующий dedicated lock + log; premature complexity
- **GitHub Action weekly** — REJECTED. Camoufox + KZ-IP делает self-hosted runner на VPS (= нет isolation) или EU-IP geo-fake ломает Phase 7 setup. Не сработает технически

## Related

- [[Bash wrapper владеет Healthchecks pings, не Python — hard-crash coverage critical]] (D-701 — почему weekly-run.sh keeps minimal surface area)
- [[README 10 sections RU primary EN code — single file для operator-is-developer team]] (D-707 — operator runbook pattern; Phase 9 §8 follows)
- [[Code review ловит deploy-blocking defects невидимые plan-checker'у — uv PATH, useradd -m collision, sudo без sudoers]] (boomerang lesson — production cron path должен иметь минимальный surface area)
- [[Pydantic RawProduct validation at SqliteSnapshotWriter — 5 percent reject-rate gate orthogonal to PARSE-FIX-04]] (D-903 — что **уже** покрывает defense-in-depth в weekly-run path)
- `.planning/research/ARCHITECTURE.md` §B Open Q2 — verbatim рекомендация manual
- `.planning/research/PITFALLS.md` §2 — cassette staleness analysis
- `.planning/phases/09-live-html-harness/09-CONTEXT.md` — D-905 + D-906 verbatim
