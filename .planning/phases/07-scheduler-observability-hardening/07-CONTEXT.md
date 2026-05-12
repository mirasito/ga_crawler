# Phase 7: Scheduler + Observability Hardening - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 — **operations layer** над уже-готовым pipeline'ом Phase 2..6: добавляет (а) системный cron в `Asia/Almaty` с bash-wrapper `bin/weekly-run.sh`, который запускает `python -m ga_crawler weekly-run` раз в неделю в ночь воскресенья; (б) Healthchecks.io dead-man's-switch интеграцию через /start, /success, /fail пинги в том же wrapper; (в) дисковую ротацию JSON-логов structlog через logrotate(8); (г) operator-runnable `bin/test-failure-alert.sh` для SC#5 верификации end-to-end (ops alert + business chat silent + HC /fail + runs.status='failed'); (д) единый русскоязычный `README.md` с from-scratch VPS setup, runbook'ом и deliberate-failure процедурой.

**Phase 7 НЕ меняет:** схему БД (`runs`/`snapshots`/`matches`/`runs.stats.*` все frozen Phase 2..6); production pipeline (`runners/main_run.py`, `delivery/*`, `reporter/*`, `matcher/*` НЕ затрагиваются — только новые `bin/*.sh` + `README.md` + `/etc/cron.d/ga_crawler` + `/etc/logrotate.d/ga_crawler` файлы); CLI surface Phase 2..6 (5 субкоманд) — НЕ добавляется новых субкоманд; `_configure_logging()` в `cli.py` (JSONRenderer→stdout остаётся; wrapper редиректит stdout/stderr в datestamped log file). Phase 7 ships **ноль строк production Python**: всё это shell-scripts + конфиг-файлы + документация.

**Phase 7 НЕ деплоит:** Docker / Kubernetes / systemd timer (cron оставлен per STATE.md Accumulated Key Decisions); self-hosted Healthchecks (SaaS Healthchecks.io); managed unblocker / proxy (Tier 2 Camoufox direct locked Phase 1).

</domain>

<decisions>
## Implementation Decisions

### Healthchecks integration (SCHED-03)

- **D-701:** **Bash wrapper `bin/weekly-run.sh` владеет /start, /success, /fail пингами; НЕ Python.** Wrapper пингует `${HC_PING_URL}/start` ПЕРЕД exec `uv run python -m ga_crawler weekly-run`, затем `${HC_PING_URL}` на exit=0 (/success) или `${HC_PING_URL}/fail` с POST data `exit=$EXIT_CODE` на любом ненулевом exit. Hard-crash покрыт **структурно**: OOM-killer, segfault Camoufox subprocess, `kill -9` вручную, system reboot, disk-full crash — все приводят к exit≠0 (или processus не вернётся вообще → HC grace-period dead-man-switch ловит). D-606 enum mapping (`delivered_*` vs `undelivered_*`) **НЕ используется** для HC routing — Phase 6 CLI exits уже семантически правильные (0=delivered/skipped-idempotent, 2=undelivered, 3=skipped_no_credentials, 4=missing_HC_PING_URL fail-loud per D-703, 5=flock-double-run-refused per D-709), и любой non-zero exit → /fail-ping (`undelivered_telegram_unreachable` → exit=2 → /fail; `delivered_ops_only` → exit=0 → /success — корректно, alerting сработал именно как задумано). `runs.stats.deliver.delivery_status` остаётся в БД для ручной диагностики и для `deliver-run --run-id N` standalone recovery (Phase 6 D-608). Альтернативы отвергнуты: Python in-process пинги — hard-crash blind spot; hybrid (bash + Python) — два места для одной ответственности, лишний integration test surface.

- **D-702:** **Healthchecks.io SaaS free tier.** https://healthchecks.io — до 20 checks, email + Telegram + webhook integrations, нулевая операционная нагрузка. Setup: оператор создаёт один check в web UI (один на проект, не per-phase), берёт UUID, кладёт полный URL `https://hc-ping.com/<uuid>` в ENV `HC_PING_URL`, добавляет в `.env.example` шаблон. Self-hosted Healthchecks отвергнут: dead-man's-switch на том же VPS — SPOF (если хост упадёт, никто не узнает); требует второй VPS — расход×2 ради монитора weekly job. Simple-webhook-to-Telegram-ops без HC отвергнут: нет dead-man-switch'а, missed-run не алертит → SCHED-03 violation.

- **D-703:** **Grace period 2h в HC UI; fail-loud если `HC_PING_URL` missing.** Grace 2h выбран по верхней границе типичного weekly run + retry budget (Phase 3 spike: ~4-14h наблюдалось; weekly run у нас 2-4h без 7,697-SKU full pagination). Schedule в HC UI: weekly Sunday 23:00 Asia/Almaty → next-expected 7 дней ± 2h grace → alert via Telegram integration в ops chat ИЛИ email. Если `HC_PING_URL` отсутствует в ENV — bash wrapper **отказывается запускаться** (`exit 4` с `HC_PING_URL missing — refusing to run per D-703`) — fail-loud principle (CLAUDE.md «без mon не запускаем»). README документирует HC_PING_URL как required ENV.

### Log rotation (SCHED-04)

- **D-704:** **logrotate(8) — Linux idiomatic подход; structlog НЕ меняется.** `_configure_logging()` в `cli.py` остаётся как есть (JSONRenderer на stdout); `bin/weekly-run.sh` редиректит stdout+stderr через `>> "$LOG_FILE" 2>&1` где `LOG_FILE=/var/log/ga_crawler/weekly-run-$(date +%F).log` (datestamped — рутацию обеспечивает имя файла + logrotate). `/etc/logrotate.d/ga_crawler` ротирует weekly. Path `/var/log/ga_crawler/` создаётся через `useradd` + `install -d -o ga_crawler -g ga_crawler -m 0755 /var/log/ga_crawler` в README VPS-setup section. Альтернативы отвергнуты: Python RotatingFileHandler — Camoufox subprocess stdout/stderr не видны inside-process, и весь смысл единого log-file теряется; systemd-journald — SCHED-04 требует «`tail`/`grep` session» literal — это journalctl semantics, не tail (можно но эргономика хуже).

- **D-705:** **Weekly rotation, keep=13 (3 месяца истории), gzip compress.** `/etc/logrotate.d/ga_crawler`:
  ```
  /var/log/ga_crawler/*.log {
      weekly
      rotate 13
      compress
      delaycompress
      missingok
      notifempty
      create 0644 ga_crawler ga_crawler
  }
  ```
  3 месяца — баланс между диагностической ёмкостью (можно вернуться к 12 недельным runs) и SSD space (Hetzner CX22 40GB; ~5MB/run gzipped × 13 = ~65MB total — negligible). `structlog` event payload «run_id» bound в `main_run.py` уже (Phase 4..6 pattern — `log.bind(run_id=run_id)`); grep-friendly через `grep '"run_id":"42"' /var/log/ga_crawler/*.log.gz`.

### Deliberate-failure test (SC#5)

- **D-706:** **`bin/test-failure-alert.sh` orchestrates end-to-end SC#5 verification ~2-3 минуты runtime.** Sequence:
  1. `bin/weekly-run.sh --viled-only --sanity-gate-n 999999` — viled-only crawl (~2 min, 120 SKUs) с D-218 sanity-N gate forced fail (count=120 < 999999) → `run_writer.fail(reason='sanity_gate_n_failed:120<999999')` → `runs.status='failed'`. Wrapper пингует HC /fail на exit=2. Этот шаг тестирует SCHED-03 (HC /fail dead-man's-switch) end-to-end.
  2. Extract `run_id` из последней строки `tail -1 /var/log/ga_crawler/weekly-run-$(date +%F).log | jq -r .run_id` (или из stdout-захваченного `MainRunResult.run_id` json).
  3. `python -m ga_crawler deliver-run --run-id $RID` (НЕ через wrapper — отдельный invocation, чтобы не повторно пинговать HC; Phase 6 D-608 standalone). Delivery_run.evaluate_gate (D-604) trip на step 1 — `read_run_status(rid)='failed'` → `gate_failed_check='upstream_status_failed'` → route=`ops_only` → `build_ops_alert(reason='upstream pipeline failed', runs.status='failed', ...)` → send to ops chat (parse_mode=HTML per D-609; html.escape per Pitfall A). Этот шаг тестирует DELIVER-02 (ops chat receives alert) + DELIVER-03 (pre-send gate routing).
  4. Echo checklist для оператора: «Проверь: (a) ops chat URL — должен быть alert message с reason `upstream pipeline failed` для run #$RID; (b) business chat URL — должен быть тихий, ни одного нового message; (c) HC dashboard URL — должен показать /start + /fail pings; (d) DB: `sqlite3 prices.db 'SELECT run_id, status, reason FROM runs WHERE run_id=$RID'` → `failed | sanity_gate_n_failed:120<999999`; (e) `runs.stats.deliver.delivery_status` через `sqlite3 prices.db 'SELECT json_extract(stats, "$.deliver.delivery_status") FROM runs WHERE run_id=$RID'` → `delivered_ops_only`.»
  5. NO cleanup — failed run остаётся в БД как evidence; `bin/test-failure-alert.sh` идемпотентен (можно запускать многократно, каждый раз создаётся новая `runs` row с новым `run_id`).

  **Reuses existing CLI surface only:** `--viled-only` (Plan 02-05 D-212), `--sanity-gate-n` (Plan 04-05), `deliver-run --run-id N` (Phase 6 D-608). НИ ОДНОЙ новой Python LOC. Альтернативы отвергнуты: `--simulate-failure` production flag — добавляет testing-only code path в production binary, риск accidental enable; synthetic-run+deliver-run (skip полный crawl) — не покрывает viled fetcher path и HC wrapper integration, оставляет blind spot.

### README scope + structure (SCHED-05)

- **D-707:** **Единый `README.md` at repo root, RU primary, 10 sections.** Структура (порядок mandatory):
  1. **Что это** — 5-line summary из PROJECT.md (core value + delivery contract).
  2. **VPS setup from-scratch** — Ubuntu 24.04 LTS (Hetzner CX22 EU), `apt install` deps (curl, sqlite3, logrotate, cron уже есть), `useradd -r -m -d /opt/ga_crawler ga_crawler` system user, `curl -LsSf https://astral.sh/uv/install.sh | sh` (как `ga_crawler`), `git clone … /opt/ga_crawler`, `cd /opt/ga_crawler && uv sync`, `uv run playwright install firefox` (Camoufox использует Firefox; Plan 03-01 уже Camoufox-via-uv проверил), `install -d -o ga_crawler -g ga_crawler /var/log/ga_crawler && chmod 0755 /var/log/ga_crawler`, root-owned `/etc/cron.d/ga_crawler` + `/etc/logrotate.d/ga_crawler`. Раздел заканчивается smoke test — `sudo -u ga_crawler bin/weekly-run.sh --viled-only --sanity-gate-n 1` (mini-run должен пройти zelyono).
  3. **ENV vars** — таблица `TG_BOT_TOKEN` / `TG_BUSINESS_CHAT_ID` / `TG_OPS_CHAT_ID` / `HC_PING_URL` + опциональные overrides (`SANITY_GATE_N` / `SANITY_GATE_M` / `SANITY_GATE_P` через CLI flags) + ссылка на `.env.example`.
  4. **Cron entry** — `/etc/cron.d/ga_crawler` content verbatim (CRON_TZ + weekly-run row + backup row); SCHED-02 invariant пояснён («без CRON_TZ system cron в UTC → Almaty Sunday 23:00 = UTC Sunday 18:00 = операторская ошибка»).
  5. **Healthchecks.io setup** — пошагово: создать аккаунт, создать check named «ga_crawler weekly», скопировать ping URL, в Settings → Schedule выбрать «Cron» schedule type, ввести `0 23 * * 0` + timezone Asia/Almaty, grace period 2h, добавить Telegram integration (рекомендуется) ИЛИ email, скопировать URL в `.env` как `HC_PING_URL=https://hc-ping.com/<uuid>`.
  6. **Telegram bot setup** — пошагово: `/newbot` через @BotFather → token; добавить bot в business и ops чаты как admin (`/setjoingroups Enable`, опционально `/setprivacy Disable`); получить chat_id через @userinfobot или forward + getUpdates; вставить в `.env`.
  7. **Deliberate-failure test** — `sudo -u ga_crawler bin/test-failure-alert.sh` + ожидаемый result + verification checklist (D-706 шаг 4). Раздел заканчивается «If any step fails — see Troubleshooting».
  8. **Operations runbook** — рецепты на типичные incidents:
     - `undelivered_telegram_unreachable` → `sudo -u ga_crawler /opt/ga_crawler/.venv/bin/python -m ga_crawler deliver-run --run-id N`
     - reporter bug found, нужно перегенерировать xlsx → `report-run --run-id N`
     - matcher bug found, нужно re-match → `matcher-run --run-id N --sanity-gate-p P`
     - backups location `/opt/ga_crawler/backups/*.db` (Plan 02-06 4-rotate retention); recovery → stop cron, `sqlite3 prices.db ".restore '/opt/ga_crawler/backups/latest.db'"`
     - проверить статус последнего run → `sqlite3 /opt/ga_crawler/prices.db 'SELECT run_id, status, reason, started_at FROM runs ORDER BY run_id DESC LIMIT 5'`
  9. **Логи** — location (`/var/log/ga_crawler/weekly-run-YYYY-MM-DD.log[.gz]`), rotation policy (D-705), grep examples:
     - последний run, все events → `tail -f /var/log/ga_crawler/weekly-run-$(date +%F).log | jq .`
     - все ошибки последнего run → `grep '"level":"error"' /var/log/ga_crawler/weekly-run-$(date +%F).log | jq .`
     - history по run_id → `zgrep '"run_id":"42"' /var/log/ga_crawler/*.log.gz | jq .`
  10. **Dev setup** — короткий блок (5 строк): `git clone … && cd ga_crawler && uv sync && uv run pytest` + ссылка на `CLAUDE.md` для архитектурных деталей.

  **Single file, не split в OPERATOR.md + DEVELOPER.md** — small team (PROJECT.md «внутренний инструмент одной команды»), operator IS developer initially; split добавляет «куда смотреть?» friction. Language **RU primary** — PROJECT.md «команда полностью русскоязычная»; технические термины (cron, ENV, exit code, ping) и code blocks английские, prose русский.

### VPS layout + wrapper script

- **D-708:** **`/opt/ga_crawler` + system user `ga_crawler` + `/etc/cron.d/ga_crawler`.** Path `/opt/ga_crawler` — Linux FHS «add-on application software» (vs `/srv` который для service data), уже зафиксировано в CLAUDE.md §Deployment. System user via `useradd -r -m -d /opt/ga_crawler ga_crawler` (`-r` system user, `-m` create home dir = `/opt/ga_crawler`, никакого shell не нужно — кронит cron). Cron entry в `/etc/cron.d/ga_crawler` (root-owned, root-edited, user column) предпочтительней `crontab -u ga_crawler -e` (per-user): (a) ops visibility — `cat /etc/cron.d/*` показывает все scheduled tasks; (b) git-checkin'able — файл коммитится в repo как `deploy/cron.d-ga_crawler` template; (c) `CRON_TZ` блок применяется ко всем строкам в одном файле — нельзя в user crontab. Cron content:
  ```
  CRON_TZ=Asia/Almaty
  MAILTO=""
  0 23 * * 0 ga_crawler /opt/ga_crawler/bin/weekly-run.sh
  0 1 * * *  ga_crawler /opt/ga_crawler/bin/backup.sh
  ```
  Sunday 23:00 Almaty (UTC+5) = Sunday 18:00 UTC → отчёт в business chat утром понедельника Almaty (cron starts 23:00 + ~3-4h run + delivery → 02:00-03:00 Monday Almaty; team reads Monday 09:00). `MAILTO=""` отключает cron email (HC уже покрывает alerting). `bin/backup.sh` уже работает (Plan 02-06 4-rotate retention).

- **D-709:** **`bin/weekly-run.sh` — rigid contract; реализация в Phase 7 planner.** Required shape:
  ```bash
  #!/bin/bash
  set -euo pipefail
  cd /opt/ga_crawler

  # ENV loading (RESEARCH caveat #4 bypass — bash wrapper is the env-loading
  # authority for cron context; python-dotenv остаётся только в cli.py::_cmd_deliver
  # для local-dev manual invocation per Phase 6 RESEARCH caveat #4 структурный canary).
  set -a
  source .env
  set +a

  # D-703 fail-loud: no HC, no run
  : "${HC_PING_URL:?HC_PING_URL missing — refusing to run per D-703}"

  # Single-writer flock guard (defense vs double-run from manual + cron overlap)
  exec 9>/var/lock/ga_crawler-weekly.lock
  flock -n 9 || { echo "Another weekly-run holds the lock — refusing" >&2; exit 5; }

  LOG_DIR=/var/log/ga_crawler
  LOG_FILE="$LOG_DIR/weekly-run-$(date +%F).log"

  # D-701 /start ping (fail-soft — HC outage не должен блочить production run)
  curl -fsS -m 10 --retry 3 "${HC_PING_URL}/start" > /dev/null || true

  set +e
  uv run python -m ga_crawler weekly-run "$@" >> "$LOG_FILE" 2>&1
  EXIT=$?
  set -e

  # D-701 success/fail ping
  if [[ $EXIT -eq 0 ]]; then
    curl -fsS -m 10 --retry 3 "${HC_PING_URL}" > /dev/null || true
  else
    curl -fsS -m 10 --retry 3 --data-raw "exit=$EXIT" "${HC_PING_URL}/fail" > /dev/null || true
  fi

  exit $EXIT
  ```
  Key invariants для планнера:
  - `set -euo pipefail` обязателен — undefined var = exit (поймает опечатку в ENV name).
  - `set -a; source .env; set +a` exports все vars в child env (auto-export mode); идиоматично для cron-wrapper.
  - `flock -n 9` non-blocking — если уже-running weekly-run держит lock, новый запуск **отказывается** (exit 5), НЕ ждёт.
  - HC pings обёрнуты в `|| true` — HC.io outage НЕ должна маскировать реальный exit code или блокировать exec; HC service-level reliability ≪ нашего production reliability requirement.
  - `--data-raw "exit=$EXIT"` на /fail-ping — Healthchecks.io индексирует это в "Last Failure" payload, ops видит exit code сразу в alert.
  - `"$@"` pass-through — `bin/test-failure-alert.sh` передаёт `--viled-only --sanity-gate-n 999999`; cron entry passes ничего.

- **D-710:** **Docker — defer to v2 (out of scope Phase 7).** Камуфокс требует Firefox 135.0.1-beta.24 (Plan 03-01 D-313 exact pin); `mcr.microsoft.com/playwright/python:v1.57.0-noble` ships Chromium, не Firefox-Camoufox forge. Custom Docker image = отдельная работа (build pipeline + base image + Camoufox install + uv + bind-mount volumes для DB+reports+logs) — Phase 8+ если ever. Native install on Ubuntu 24.04 (D-708) — proven path через Phase 1 spike + STATE.md Phase 7 hosting recommendation. Tracked в v2 backlog: `INFRA-V2-04: Docker image для reproducible redeploys`.

### Claude's Discretion

- **Cron MAILTO empty string** (D-708) — не string null, не unset; пустая строка явно отключает cron email reports. Без этого cron посылает stdout/stderr на root@localhost (даже если уже редиректнуто в LOG_FILE wrapper'ом, любой `set -x` debug на ранней стадии before redirect забьёт mailbox).
- **Lock file path `/var/lock/ga_crawler-weekly.lock`** (D-709) — Linux FHS для lock files; tmpfs обычно (clean reboot = lock release auto). Permissions создаются автоматически root первый раз; группа ga_crawler нужна → wrapper использует `exec 9>>${path}` который создаёт файл owned by current user (ga_crawler) если не существует, ИЛИ открывает append если существует. Идеомпотентно.
- **`set -a; source .env`** (D-709) — bypass Phase 6 D-611 «python-dotenv only in cli.py» invariant. Структурный canary в Phase 6 проверяет источник Python модулей; bash скрипт — другой language, инвариант не нарушается. README §3 эксплицитно: «.env loading: в production через bash wrapper для cron context; в development через python-dotenv в `cli.py::_cmd_deliver` (manual invocations)».
- **`uv run python -m ga_crawler weekly-run`** (D-709) — `uv run` гарантирует resolve venv + entry-point из `pyproject.toml`. Альтернатива (`/opt/ga_crawler/.venv/bin/python -m ga_crawler`) хрупче — если venv pruned, `uv run` восстановит. На VPS uv cached package data — overhead `uv run` ничтожен.
- **Healthchecks.io check name + slug** (D-702) — название «ga_crawler weekly» в UI; slug автогенерирован. Ping URL — `https://hc-ping.com/<uuid>` (НЕ slug-based — slug может конфликтовать в shared workspace). README §5 явно про UUID.
- **Backup cron — отдельная строка в /etc/cron.d/ga_crawler** (D-708) — Plan 02-06 `bin/backup.sh` уже работает; Phase 7 НЕ переписывает, только добавляет cron schedule. Daily 01:00 — после weekly-run (Sunday 23:00-03:00) + до next day workload.
- **README structure RU primary, code блоки EN** (D-707) — операторы читают prose, копипастят code. Команды/flag-имена/ENV-имена не локализуются.
- **`bin/test-failure-alert.sh` — НЕ ставится в cron** (D-706) — manually invoked operator tool; cron schedule не нужен; README документирует «run after deploy or after major code change».
- **Cron file lives in repo as deploy template** (D-708) — `deploy/cron.d-ga_crawler` или `deploy/etc-cron-d-ga_crawler` (Phase 7 planner picks path); README §4 ссылается на `cp deploy/… /etc/cron.d/ga_crawler`. То же для `deploy/etc-logrotate-d-ga_crawler` (D-704/D-705).
- **No new pyproject.toml namespace** — Phase 7 не добавляет `[tool.ga_crawler.schedule]` секцию: все decisions zaшиты в shell scripts + cron + logrotate configs (config-as-code в deploy/), НЕ в Python config (нет Python code в Phase 7).
- **No new `runs.stats.*` namespace** — Phase 7 не добавляет `schedule.*` keys в `runs.stats`. Stats namespace остаётся 5-way disjoint (`viled / goldapple / match / report / deliver`); HC ping outcomes живут в HC dashboard, не в БД (это monitoring data, не business data).
- **structlog binding не изменяется** — wrapper не пытается вставить `cron_pid` или `wrapper_version` в log events; Phase 4..6 уже binds `run_id` в `main_run.py` — этого достаточно для grep'абельности. Phase 7 planner ДОЛЖЕН проверить структурно (тест-канарейка): `_configure_logging()` source-diff пустой между Phase 6 и Phase 7 commits.
- **Exit code 4 reserved for HC_PING_URL missing** (D-703); exit code 5 reserved for flock-double-run-refused (D-709). README §3 ENV table документирует обе.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — core value (weekly viled vs goldapple для commercial team); §Hosting «решение в research-фазе на основе требований к прокси и времени запуска (ожидаемо VPS + cron)» — Phase 7 закрывает; §Frequency «раз в неделю» — Phase 7 кодирует cron schedule.
- `.planning/REQUIREMENTS.md` §"Schedule & Ops" (SCHED-01..05 pending — все 5 закрываются Phase 7); §Deliver DELIVER-02 (ops chat alerts pattern — Phase 7 D-706 deliberate-failure verifies); §Data DATA-06 (Plan 02-06 backup cron — Phase 7 D-708 adds row в `/etc/cron.d/ga_crawler` рядом с weekly-run).
- `.planning/ROADMAP.md` §"Phase 7: Scheduler + Observability Hardening" — phase goal + 5 success criteria (SC#1..5).

### Prior phase context (decisions cascade)
- `.planning/phases/06-telegram-delivery/06-CONTEXT.md` — **D-605** (delivery_status decoupled от runs.status — Phase 7 HC pings consume Phase 6 CLI exit codes, не enum directly per D-701); **D-606** (6-value delivery_status enum — Phase 7 DOES NOT new-ping per enum, exit-code based per D-701); **D-608** (`deliver-run --run-id N` standalone — Phase 7 D-706 reuses в deliberate-failure script); **D-611** (asymmetric ENV handling: TG_BOT_TOKEN fail-loud, chat_ids degradable — Phase 7 README §3 документирует); RESEARCH caveat #4 (`load_dotenv` ONLY in `cli.py::_cmd_deliver` — Phase 7 D-709 НЕ нарушает: bash wrapper, не Python).
- `.planning/phases/05-reporter-excel-summary/05-CONTEXT.md` — **D-509** (`report-run --run-id N` — Phase 7 README §8 operations runbook); **D-515** (size-guard flag-only — Phase 7 не добавляет нового handling, recovery через delivery layer existing).
- `.planning/phases/04-matcher-match-rate-kpi/04-CONTEXT.md` — **D-412** (`matcher-run --run-id N` — Phase 7 README §8 operations runbook).
- `.planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT.md` — **D-218** (parse-quality + sanity-N gate sequencing — Phase 7 D-706 использует D-218 sanity-N fail mechanism через `--sanity-gate-n 999999`); **D-219** (backup script — Phase 7 D-708 добавляет cron строку).
- `.planning/phases/01-goldapple-reconnaissance-spike/MEMO.md` — Phase 1 spike close-out: Tier 2 Camoufox direct, NO proxy, KZ-laptop validated; Phase 7 hosting recommendation = **Hetzner CX22 EU** (см. STATE.md note line 157).

### Research foundation
- `CLAUDE.md` §"Scheduling: cron vs APScheduler vs Celery vs Prefect" — **system cron locked** (Phase 7 inherits); §"Deployment / Hosting" — Hetzner CX22 + Ubuntu 24.04 LTS Falkenstein/Helsinki (EU); §"Docker?" — «Optional, recommended» — Phase 7 D-710 **defers to v2** для Camoufox-Firefox incompatibility с official Playwright image.
- `.planning/research/ARCHITECTURE.md` — «reporter independent of delivery» extended to «delivery independent of run-correctness» (Phase 6 D-605) — Phase 7 inherits inverted ещё раз: «monitoring independent of business logic» (HC pings — wrapper-level, не Python).
- `.planning/research/PITFALLS.md` — Phase 7 не добавляет новых Pitfalls; cron/logrotate/HC.io — well-trodden Linux ops territory.

### Frozen infrastructure (Phase 7 inputs — READ-ONLY)
- `src/ga_crawler/cli.py` — current 5 субкоманд (`goldapple-smoke`, `weekly-run`, `matcher-run`, `report-run`, `deliver-run`); `_configure_logging()` JSONRenderer→stdout (Phase 7 НЕ меняет; wrapper редиректит). Структурный canary: `git diff src/ga_crawler/cli.py` ПУСТОЙ между Phase 6 head и Phase 7 close-out commits.
- `src/ga_crawler/runners/main_run.py` — `run_weekly()` orchestrator (Phase 2..6 frozen). Phase 7 НЕ меняет; wrapper вызывает через `uv run python -m ga_crawler weekly-run`. Структурный canary: `git diff src/ga_crawler/runners/main_run.py` ПУСТОЙ.
- `bin/backup.sh` — Plan 02-06 frozen; Phase 7 D-708 добавляет cron row рядом, не меняет скрипт.
- `pyproject.toml` — Phase 7 НЕ добавляет dependencies (curl уже на любой Ubuntu; flock(1) уже в util-linux; logrotate уже в base). НЕ добавляет `[tool.ga_crawler.schedule]` namespace (Phase 7 = shell + конфиг-файлы, не Python).

### Test infrastructure (inherited)
- `tests/integration/test_weekly_run_with_delivery.py` — Phase 6 E2E; Phase 7 НЕ дополняет (Phase 7 — ops-layer, не code-layer). Регрессионный invariant: эти тесты должны GREEN остаться после Phase 7 (структурный canary через CI).
- `tests/integration/test_cli_deliver.py` — Phase 6 D-608 deliver-run; Phase 7 `bin/test-failure-alert.sh` reuses в production без unit-test surface.

### Project conventions
- `CLAUDE.md` §"Deployment / Hosting" — Hetzner CX22, Ubuntu 24.04, `useradd -r`, `/opt/<app>` convention, cron over systemd-timer baseline; Phase 7 D-708 follows verbatim.
- `CLAUDE.md` §"Conventions" — пустой («not yet established»); Phase 7 не вводит новых code conventions (всё в shell + docs).

### Project state & accumulated decisions
- `.planning/STATE.md` §"Accumulated Key Decisions":
  - line 138: «System cron with `CRON_TZ=Asia/Almaty`; no APScheduler/Celery/Prefect» — Phase 7 D-708 implements.
  - line 157: «Phase 7 hosting recommendation = Hetzner CX22 EU + smoke gate» — Phase 7 inherits, README §2 документирует.
  - line 184: «cron entry `0 1 * * * /opt/ga_crawler/bin/backup.sh` (daily 01:00 KZ after weekly Sunday batch)» — Phase 7 D-708 adds.
  - line 195: «D-605 Phase 7 Healthchecks SCHED-03 SHALL probe `deliver.delivery_status` (NOT `runs.status`)» — Phase 7 D-701 **partial override**: HC routing на CLI exit code (который сам derived from `delivery_status` enum в Phase 6 CLI handler), а НЕ direct JSON read. Effective семантика та же (`undelivered_*` → exit 2 → /fail; `delivered_*` → exit 0 → /success), но monitoring уровень — wrapper, не Python (hard-crash coverage critical).
  - line 196: «D-606 enum→ping mapping» — Phase 7 D-701 inherits per CLI exit code mapping (Phase 6 `cli.py::_cmd_deliver` уже выдаёт exit codes 0/2/3 per enum).
  - line 207: «[Phase 7 backlog] Camoufox+EU smoke fetch» — opens на Phase 7 ops; Phase 7 D-707 README §2 smoke test row («`bin/weekly-run.sh --viled-only --sanity-gate-n 1`») partially покрывает («mini-run green = setup green»); full goldapple+Camoufox+EU smoke остаётся отдельной operator task (running `goldapple-smoke` через wrapper после deploy).
  - line 208: «[Phase 7 backlog] KZ-legal review» — orthogonal, Phase 7 не блокирует, остаётся в backlog.

### External / vendor docs
- Healthchecks.io API — `https://healthchecks.io/docs/http_api/` — `/start` / `/fail` / `/{uuid}` endpoints; UUID-based pings; cron schedule + timezone config; integrations (Telegram, email, webhook, etc.).
- Healthchecks.io free tier limits — `https://healthchecks.io/pricing/` — 20 checks, 2 team members, email + Telegram integrations. Достаточно для проекта.
- logrotate(8) man page — `https://linux.die.net/man/8/logrotate` — directives `weekly`, `rotate`, `compress`, `delaycompress`, `missingok`, `notifempty`, `create`.
- Linux cron(8) + crontab(5) — `CRON_TZ`, `MAILTO`, user column в `/etc/cron.d/*`.
- flock(1) — `man flock` — `-n` non-blocking semantics.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`bin/backup.sh`** (Plan 02-06) — pattern для bash scripts в этом проекте; xargs `-d '\n'` Windows quirk handled. Phase 7 `bin/weekly-run.sh` + `bin/test-failure-alert.sh` mirror conventions (shebang `#!/bin/bash`, `set -euo pipefail`, cd to `/opt/ga_crawler`, `uv run` invocation).
- **`src/ga_crawler/cli.py::_configure_logging`** — JSONRenderer→stdout pipeline (Phase 2..6 stable). Phase 7 НЕ меняет; structlog binding `run_id` в `main_run.py` (Phase 4..6) уже grep-friendly.
- **`src/ga_crawler/cli.py::_cmd_weekly` exit codes** — Phase 6 D-616 + Phase 5 D-509 + Phase 4 D-412 уже выдают 0/2 codes; Phase 6 D-608 deliver-run extends с 3 (no creds). Phase 7 wrapper read exit codes verbatim. Структурный canary: `grep -n 'return [0-9]' src/ga_crawler/cli.py` — все ветки exit code-mapped.
- **`runs.stats.deliver.delivery_status`** (Phase 6 D-606 8-value enum) — Phase 7 D-706 `bin/test-failure-alert.sh` verification checklist citation в README §7.
- **`python-dotenv>=1.0,<2.0`** — уже в deps (pyproject.toml); Phase 7 НЕ trogает в Python (CLI Phase 6 RESEARCH caveat #4 invariant preserved); bash wrapper использует `set -a; source .env; set +a` вместо.
- **`uv run python -m ga_crawler weekly-run`** invocation — стандарт проекта (Phase 2..6 README references). Phase 7 wrapper наследует.

### Established Patterns
- **bash script convention** (Plan 02-06): `#!/bin/bash`, `set -euo pipefail`, error redirection через `>&2`, error message в stderr перед exit code. Phase 7 wrapper + test-failure-alert script наследуют.
- **Cron entry в `/etc/cron.d/<name>` с user column** (D-708) — Linux idiomatic; пользователь явно указан в строке, в отличие от user-crontab.
- **`/var/log/<app>/` + logrotate(8)**: стандарт Linux; Phase 7 первый раз вводит в проекте, README §9 документирует.
- **Append-only `runs` row через `run_writer.fail()`** (Plan 02-05 DATA-05): Phase 7 D-706 deliberate-failure test orchestrates через D-218 sanity-N gate fail (existing path), НЕ через новый failure-injection mechanism.
- **`deliver-run --run-id N` idempotent re-routing** (Phase 6 D-608) — Phase 7 D-706 invokes на failed run → D-604 gate trip → ops_only route; pattern уже test-covered в Phase 6 (`test_d605_*`).

### Integration Points
- **Input ← cron** (`/etc/cron.d/ga_crawler`): Sunday 23:00 Almaty → `ga_crawler` user → `bin/weekly-run.sh`.
- **Input ← ENV** (`.env` loaded by wrapper): `TG_BOT_TOKEN` + `TG_BUSINESS_CHAT_ID` + `TG_OPS_CHAT_ID` (Phase 6 DELIVER-05) + `HC_PING_URL` (Phase 7 NEW).
- **Input ← CLI args** (pass-through `"$@"`): `--viled-only` + `--sanity-gate-n N` для deliberate-failure test (D-706).
- **Output → Healthchecks.io REST**: GET/POST на `${HC_PING_URL}/{start,,fail}` per D-701; ops alerts via HC's Telegram/email integration.
- **Output → `/var/log/ga_crawler/weekly-run-YYYY-MM-DD.log`**: stdout+stderr (structlog JSON + Camoufox subprocess output + any incidental prints). Read via `tail` / `grep` / `jq`.
- **Output → logrotate(8) cycle**: weekly rotate, keep 13, compress; `/var/log/ga_crawler/*.log.gz` archive.
- **Output → cron exit code → wrapper exit code → HC ping path**: `0` → /success; `2` → /fail (undelivered); `3` → /fail (no creds); `4` → /fail (HC missing); `5` → /fail (lock); any non-zero → /fail.
- **Output → DB**: НЕТ изменений в `runs`/`snapshots`/`matches` через Phase 7 code path (Phase 7 не пишет в БД напрямую — только Python production code via `weekly-run` поддерживает Phase 2..6 invariants).

### Open dependencies
- **Hetzner CX22 VPS** — operator provisioning task (out of Python code scope). README §2 документирует from-scratch setup commands.
- **Healthchecks.io account + check + ping URL** — operator setup task; README §5 пошагово.
- **Telegram bot uniqueness** — Phase 6 setup retained; README §6 для freshness review.
- **DNS / firewall** — Telegram Bot API HTTPS outbound (port 443) + Healthchecks.io HTTPS outbound (port 443) + Camoufox HTTPS to goldapple/viled (443) + uv install + apt update. Default Hetzner egress permits all; README §2 noted.
- Phase 6 fully shipped — Phase 7 unblocked. Phase 5 + Phase 6 stats + 5-way namespace disjoint preserved (Phase 7 НЕ добавляет 6th namespace).

</code_context>

<specifics>
## Specific Ideas

- **«Phase 7 — ноль строк production Python»** — все decisions ложатся в shell scripts + cron + logrotate configs + Markdown docs. Структурный test canary в Phase 7 planner: `git diff src/ga_crawler/ -- ':!*.md'` пустой между Phase 6 head и Phase 7 close-out commits (production code untouched).
- **«Wrapper владеет HC pings, не Python»** (D-701) — hard-crash coverage — главный driver. OOM-killer на Hetzner CX22 (4GB RAM, Camoufox + Chromium-equivalent processes ~1.5GB peak) — realistic failure mode; Python в этом момент уже мёртв, send-pingов не будет. Bash wrapper после `set +e` всегда доходит до cleanup.
- **«Fail-loud при missing HC_PING_URL»** (D-703) — CLAUDE.md «without mon we don't run» principle. Phase 6 D-611 fail-loud для TG_BOT_TOKEN — same pattern. README §3 marks HC_PING_URL как required (не optional).
- **«Cron file как deployment artifact в repo»** (D-708) — `deploy/etc-cron-d-ga_crawler` config-as-code; README §4 `sudo cp deploy/etc-cron-d-ga_crawler /etc/cron.d/ga_crawler && sudo chmod 0644 /etc/cron.d/ga_crawler && sudo systemctl reload cron` (Ubuntu 24.04 uses `cron` not `cronie`).
- **«Deliberate-failure через existing CLI flags, не новый production code path»** (D-706) — `--sanity-gate-n 999999` уже работает (Plan 04-05 + Plan 02-05); `deliver-run --run-id N` уже работает (Phase 6 D-608); test script — orchestration над existing surface. NO new flags, NO production-binary testing-mode toggles. Структурный canary: `grep -n 'simulate\|fail.mode' src/ga_crawler/` после Phase 7 commit — пусто.
- **«Single README, RU primary, code blocks EN»** (D-707) — operator team RU-speaking per PROJECT.md; технические термины (cron, ENV, exit code) и commands не локализуются (потеряется grep-ability в bug reports).
- **«Lock file под `/var/lock/`»** (D-709) — Linux FHS standard, tmpfs cleanup на reboot, никаких manual cleanup hooks не нужно. flock(1) handles concurrent invocations через kernel-level advisory lock.
- **«Daily backup рядом с weekly run в том же cron file»** (D-708) — Plan 02-06 backup.sh wasn't given a cron schedule (только сам скрипт); Phase 7 first time wires cron schedule. README §4 cron content прямо включает обе строки.
- **«No new pyproject namespace, no new stats namespace»** — Phase 7 не добавляет `[tool.ga_crawler.schedule]` и не добавляет `schedule.*` keys в `runs.stats`. 5-way namespace disjoint invariant (Phase 6 D-607 canary `test_five_way_namespaces_disjoint`) preserved.

</specifics>

<deferred>
## Deferred Ideas

- **Docker image для reproducible redeploys** — v2 backlog `INFRA-V2-04`. Камуфокс Firefox 135-pinned требует custom base image; не покрывается `mcr.microsoft.com/playwright/python:v1.57.0-noble` который Chromium-based. Native install на Ubuntu 24.04 (D-708) proven через Phase 1 spike.
- **Self-hosted Healthchecks** — отвергнуто Phase 7 D-702: SPOF risk (мониторинг на том же VPS что и мониторируемое); требует 2-й VPS — расход x2 ради weekly job. Может вернуться к рассмотрению если SaaS HC.io станет paid-only OR если проект масштабируется до 10+ scheduled jobs (тогда self-hosted self-pays).
- **systemd timer вместо cron** — отвергнуто per STATE.md «Accumulated Key Decisions» line 138 + Phase 7 D-708 (cron одной строкой proven; systemd timer = .service + .timer + journalctl tooling = больше moving parts ради того же weekly schedule).
- **Python in-process HC pings** — отвергнуто Phase 7 D-701: hard-crash coverage критичен (Camoufox + 4GB RAM + Firefox subprocess OOM scenarios — realistic). Hybrid (bash+Python) — overengineering для weekly job.
- **Per-step / per-phase HC pings** (отдельные UUIDs для viled / goldapple / matcher / reporter / deliver) — отвергнуто: один weekly run = один deliveryable unit; дробление monitoring на phase boundaries добавляет 4 HC checks + 4 routing rules в HC UI + 4 alerting channels — высокая cognitive load ради marginal observability gain. Phase-level errors уже видны в JSON logs (`grep '"phase":"goldapple"' weekly-run-…log`) + run_id traceability в БД.
- **Multi-region failover / hot-standby VPS** — out of scope v1; стоимость+сложность не оправдывают для weekly batch job; «если упадёт — следующая неделя» acceptable.
- **Prometheus / Grafana / Loki / etc. observability stack** — out of scope v1; structlog JSON + logrotate + HC.io dashboard покрывают «is it alive? did it succeed?»; advanced metrics (latency p99, brand-by-brand coverage trends) — v2 если pricing team запросит.
- **Cron retry on failure** — отвергнуто: weekly cron failure → ops alert → operator runs `deliver-run --run-id N` (recovery) ИЛИ ждёт следующую неделю. Auto-retry — может маскировать transient issue который заслуживает investigation.
- **`weekly-run --dry-run`** — отвергнуто: Phase 6 D-608 уже имеет `deliver-run --dry-run`; weekly-run dry-run = «4h crawl без commit в БД» = wastes anti-bot budget без значительной value; vendor-stress concern. Не нужно.
- **Mailing list / email alerts** — Phase 6 ops chat покрывает + HC.io Telegram integration; email — duplicate notification channel, без value.
- **APScheduler 4 fallback** — отвергнуто: STATE.md decision locked; не пересматривается без strong reason (e.g., если cron schedule reliability ухудшится — но за 50 лет cron ни разу не подводил эту problem class).
- **Auto-deployment / CI-driven VPS update** — out of scope v1; manual `git pull && uv sync` достаточно для weekly batch job; deploy frequency низкая (раз в несколько недель/месяцев); CI/CD pipeline — Phase 8+ territory если ever.
- **Log shipping в central log aggregator (Loki, ELK, Datadog)** — out of scope v1; single-VPS + grep — оператор может login + tail в любой момент; central log = paid SaaS overhead.
- **HC.io paid tier для >20 checks** — не нужен; один project = один check.
- **Backup off-site replication (rclone к S3 / B2 / etc.)** — out of scope v1 (DATA-06 4-rotate local достаточно для weekly snapshot recovery); off-site = disaster recovery (VPS provider dies), v2 territory.
- **Custom Healthchecks alert template** — HC.io defaults достаточно (subject + ping URL + last log); no custom template нужен для weekly cron.
- **`bin/test-failure-alert.sh --auto-verify`** (программный assertion вместо checklist) — рассматривался; отвергнут: ops chat + business chat checks требуют человеческого глаза («есть ли там сообщение?») via Telegram client; HC dashboard check тоже UI-based. Manual checklist (D-706 шаг 4) — pragmatic.

### Reviewed Todos (not folded)
- `gsd-sdk` not available in environment (как и в Phase 2..6); `todo.match-phase` step skipped silently per workflow universal rule.
- `[Phase 7 backlog] Camoufox+EU smoke fetch before locking Hetzner hosting` (STATE.md line 207) — НЕ folded в Phase 7 scope: D-707 README §2 mini-smoke `--viled-only --sanity-gate-n 1` purpose-covers setup-green check; full Camoufox+goldapple+EU smoke — отдельная operator task **после** Phase 7 deploy (`sudo -u ga_crawler /opt/ga_crawler/.venv/bin/python -m ga_crawler goldapple-smoke`). Backlog item closes когда оператор отчитается «smoke green».
- `[Phase 7 backlog] KZ-legal review for ToS compliance` (STATE.md line 208) — НЕ folded: orthogonal к scheduler/observability; legal review — отдельная задача с привлечением юриста; bundle (tos-audit.md + viled-privacy.txt + robots.txt snapshots + GroupIB flag) уже собран в Phase 1; остаётся в backlog до operator-triggered milestone.
- `[Phase 3/7 ops backlog] viled catalog pagination beyond page 1` (STATE.md line 202-203) — НЕ folded: касается viled crawl coverage (full 7,697-SKU corpus), не scheduler. Текущий v1 limit 120 SKUs > D-201 N=100 floor. Phase 7 deploy не блокируется; closes when ops budget allows separately.

</deferred>

---

*Phase: 7-scheduler-observability-hardening*
*Context gathered: 2026-05-12*
*Decisions: D-701..D-710 (10 decisions). 4 areas discussed; user-confirmed: HC bash-wrapper (D-701), HC.io SaaS free (D-702), grace 2h + fail-loud (D-703), logrotate weekly keep 13 (D-704/D-705), `bin/test-failure-alert.sh` orchestrator (D-706); autonomous calls made for README scope (D-707), VPS layout (D-708), wrapper script contract (D-709), Docker defer (D-710) — per user «work without stopping» instruction.*

## Action Items for Other Documents

The following changes propagate to other artifacts at next opportunity:

- **`.env.example`**: add `HC_PING_URL=` placeholder (Phase 7 NEW; existing 3 TG_* vars from Phase 6 stay) — surface at Plan 07-XX Wave 0. **[DONE Plan 07-02 Task 3]** — `.env.example` MODIFIED (+6 lines: blank + 3 comment + blank + HC_PING_URL=); 14 lines total, 452 bytes; canary `test_phase07_env_example_shape.py::test_env_example_has_hc_ping_url_line` GREEN.
- **`pyproject.toml`**: NO changes (no new deps, no new namespace) — Phase 7 = shell + configs + docs only. **[DONE — verified by tests/test_phase07_structural_canaries.py::test_pyproject_no_new_namespace_phase7 + zero diff in pyproject between Phase 6 close-out and Phase 7 close-out]**.
- **`.planning/REQUIREMENTS.md` SCHED-01..05**: annotate с per-plan citation (D-701..D-710 decision IDs) at Phase 7 close-out — mirror Plan 05-06 / Plan 06-06 doc cascade pattern. **[DONE Plan 07-05 Task 1]** — 5 `- [x] **SCHED-0N**` rows with per-plan citations (07-02 / 07-03 / 07-04) + decision IDs (D-701..D-710); Traceability table rows updated Pending → Done; Coverage block 42/48 → 47/48; Phase 7 footer line appended.
- **`.planning/STATE.md`**: add to "Accumulated Key Decisions":
  - «D-701 Phase 7 — HC pings live в bash wrapper, не Python (hard-crash coverage). CLI exit codes уже семантически правильные через Phase 6 D-606 enum→exit-code mapping. Структурный canary: `git diff src/ga_crawler/cli.py` empty Phase 6→Phase 7.» **[DONE Plan 07-05 Task 2]**
  - «D-708 Phase 7 — `/etc/cron.d/ga_crawler` (root-edited, user column) preferred над user-crontab для ops visibility + git-trackability. Repo template at `deploy/etc-cron-d-ga_crawler`.» **[DONE Plan 07-05 Task 2]**
  - «D-709 Phase 7 — flock(1) advisory lock в `/var/lock/ga_crawler-weekly.lock` предотвращает double-run от cron+manual overlap. Exit code 5 reserved.» **[DONE Plan 07-05 Task 2]**
  - «D-710 Phase 7 — Docker defer to v2 (INFRA-V2-04). Camoufox Firefox 135-pinned не совместим с `mcr.microsoft.com/playwright/python:v1.57.0-noble` (Chromium-based); custom image — separate effort.» **[DONE Plan 07-05 Task 2]**
  - surface at Phase 7 close-out (Plan 07-XX final wave doc cascade). **[DONE Plan 07-05 Task 2]** — 4 D-7xx rows appended to §Accumulated Key Decisions; Plan Execution Metrics extended with 5 rows 07-01..07-05; Current Position rewritten to Phase 7 COMPLETE.
- **`.planning/REQUIREMENTS.md` v2 Infrastructure**: add `INFRA-V2-04: Docker image для reproducible redeploys` — surface at Phase 7 close-out per D-710. **[DONE Plan 07-05 Task 1]** — INFRA-V2-04 added to v2 Infrastructure backlog with rationale (Camoufox Firefox 135-pinned vs Chromium-based Playwright image; custom base image required).
- **`README.md`** (new file at repo root, primary deliverable Phase 7 SCHED-05): 10-section structure per D-707; written в final Phase 7 wave. **[DONE Plan 07-04]** — 232 lines, 10 H2 sections in D-707 verbatim order; canary `tests/test_phase07_readme_structure.py::test_readme_h2_order_matches_d707` GREEN.
- **`deploy/etc-cron-d-ga_crawler`** (new file in repo): cron config-as-code per D-708 — surface at Plan 07-XX Wave N (planner places). **[DONE Plan 07-02 Task 1]** — 24 lines, 1065 bytes; CRON_TZ=Asia/Almaty + MAILTO="" + weekly-run row + daily backup row; Pitfall #1 filename (no dot, no extension).
- **`deploy/etc-logrotate-d-ga_crawler`** (new file in repo): logrotate config-as-code per D-704/D-705 — surface at Plan 07-XX Wave N. **[DONE Plan 07-02 Task 2]** — 28 lines, 1067 bytes; 7 directives (weekly + rotate 13 + compress + delaycompress + missingok + notifempty + create 0644 ga_crawler ga_crawler).
- **`bin/weekly-run.sh`** (new file): D-709 contract — surface at Plan 07-XX Wave N. **[DONE Plan 07-03 Task 1]** — 77 lines, mode 100755; 7 responsibilities in strict order per D-709 verbatim; shebang reconciled to #!/usr/bin/env bash per project convention.
- **`bin/test-failure-alert.sh`** (new file): D-706 orchestrator — surface at Plan 07-XX Wave N. **[DONE Plan 07-03 Task 2]** — 57 lines, mode 100755; verbatim 5-step recipe per D-706; reuses existing CLI surface only (zero new Python LOC).
- **`.gitignore`**: verify `/var/log/` not relevant (logs выкладываются на VPS, не in-repo); если кто-то будет local-symlink-ить `var/log/` для dev — добавить exclude. Plan 07-XX Wave 0 audit. **[DONE Plan 07-01 audit]** — `.gitignore` audit confirmed no `/var/log/` symlink usage in dev workflows; no edit needed. Logs land on VPS only; never enter repo.
