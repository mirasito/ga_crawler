# Phase 7: Scheduler + Observability Hardening — Research

**Researched:** 2026-05-12
**Domain:** Linux ops (cron + Healthchecks.io + logrotate + flock + bash wrapper)
**Confidence:** HIGH (well-trodden territory; all decisions D-701..D-710 LOCKED in CONTEXT.md; research validates them)

## Summary

Phase 7 wires шесть артефактов (4 файла в `deploy/` + `bin/`, плюс `README.md`, плюс `.env.example` edit) над уже-shipped pipeline Phase 2..6 — ноль строк production Python. Все ключевые решения зафиксированы CONTEXT.md (D-701..D-710); цель этого research'а — **валидировать** локированные решения против актуальных upstream specs (HC.io ping API, logrotate(8), cron(8), flock(1)) и **surface PITFALLS** которые planner кодирует как guards/canaries.

Главные находки validation pass'а:
1. **Healthchecks.io ping URL format `https://hc-ping.com/<uuid>`** — корректно [VERIFIED: healthchecks.io/docs/http_api/]; `/start` + `/success` (bare UUID) + `/fail` endpoints семантика подтверждена; POST body up to 100 kB stored как diagnostic info [VERIFIED]; rate-limit 5 pings/min per check [VERIFIED]. Telegram integration через @my_hc_bot стандартный, требует invite-в-group + `/start@my_hc_bot` activation [VERIFIED: healthchecks.io/integrations/telegram/].
2. **`/etc/cron.d/` filename restriction:** имя файла НЕ должно содержать точек ИЛИ других неалфавитных символов кроме `_-`; иначе Vixie cron silently игнорирует файл [VERIFIED: manpages.ubuntu.com/jammy/man8/cron.8]. CONTEXT.md `deploy/etc-cron-d-ga_crawler` и target path `/etc/cron.d/ga_crawler` оба safe.
3. **`/var/lock` is symlink → `/run/lock` (tmpfs)** на Ubuntu 24.04 [VERIFIED: wiki.debian.org/ReleaseGoals/RunDirectory + lwn.net/Articles/436012]. Файл lock'а исчезает после reboot — **invariant: stale-lock-after-reboot НЕВОЗМОЖЕН**, никакой ручной cleanup не нужен. flock `-n` exit code = 1 на EWOULDBLOCK [VERIFIED: man7.org/linux/man-pages/man1/flock.1]; CONTEXT.md exit code 5 для double-run переопределяет default 1 через `flock -n 9 || { ... exit 5; }` idiom — корректно.
4. **`set -a; source .env; set +a` vs python-dotenv parser parity:** оба consume **K=V lines с одинаковой семантикой** для **простых quoted/unquoted values** (TG_BOT_TOKEN строка цифр+символов, HC_PING_URL URL, chat_id число) — поддерживаются обоими. Расхождение проявляется ТОЛЬКО на multiline values + `#` inside quoted strings (python-dotenv интерпретирует как comment даже в кавычках [CITED: dev.to/proteusiq]; bash сохраняет внутри одинарных/двойных кавычек). Phase 6 `.env.example` имеет только 3 простые vars (token + chat_id + chat_id); Phase 7 добавляет 1 (HC_PING_URL — URL без `#`). **Pitfall #4 risk: LOW.**
5. **Camoufox + cron context:** Camoufox 0.4.11 = Firefox 135.0.1-beta.24 (Plan 03-01 D-313 pin); Firefox storage пишет в `$XDG_CACHE_HOME` ИЛИ `$HOME/.cache/mozilla/...` [VERIFIED: bugzilla.mozilla.org/259356]. CONTEXT.md D-708 `useradd -r -m -d /opt/ga_crawler ga_crawler` создаёт $HOME для system user — Camoufox-cache safe в `/opt/ga_crawler/.cache/mozilla/...`. **Без `-m` flag** system user не имеет $HOME → Firefox stalls or crashes. Validation: README §2 setup row уже включает `-m`.
6. **logrotate weekly + delaycompress + missingok + notifempty + create combination is SAFE for первой запуск scenario** [VERIFIED: man7.org/linux/man-pages/man8/logrotate.8 via mirror]: первый run без существующего LOG_FILE → `missingok` пропускает rotate; первый run с empty 0-byte LOG_FILE → `notifempty` пропускает rotate; `create 0644 ga_crawler ga_crawler` создаёт новый LOG_FILE после rotation. **Pitfall #6: user `ga_crawler` MUST exist BEFORE первый logrotate run** (D-708 useradd happens in README §2 setup; if logrotate runs before user created → silent fail).

**Primary recommendation:** Planner может реализовать ровно по D-701..D-710 verbatim. Six pitfalls below — convert каждый в task-level guard или canary.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Cron trigger | OS / system cron | — | Linux idiomatic для weekly batch; CLAUDE.md §Scheduling LOCKED |
| Schedule + timezone enforcement | OS / `/etc/cron.d/*` `CRON_TZ` line | — | `CRON_TZ=Asia/Almaty` scope-limited to one file [VERIFIED: crontab(5)] |
| Single-writer mutual exclusion | OS / flock(1) advisory | bash wrapper opens FD 9 | Kernel-level lock; no cleanup needed (tmpfs `/run/lock`) |
| Dead-man's-switch monitoring | SaaS (Healthchecks.io free tier) | — | SPOF avoidance: self-hosted HC на том же VPS = no monitoring if VPS dies |
| HC ping orchestration | bash wrapper `bin/weekly-run.sh` | — | Hard-crash coverage (OOM, segfault, kill -9) — Python в этом моменте уже мёртв |
| ENV loading (production) | bash wrapper `set -a; source .env` | — | cron has no `.env` discovery; Python `load_dotenv` оставлен только для local-dev manual invocations per Phase 6 RESEARCH caveat #4 |
| Log rotation | OS / logrotate(8) `/etc/logrotate.d/` | — | Standard Linux; structlog JSONRenderer писать всё в stdout, wrapper редиректит, logrotate rotates |
| Log persistence | Disk `/var/log/ga_crawler/*.log[.gz]` | — | structlog Phase 4..6 already binds `run_id` — grep-friendly |
| Ops alert delivery | HC.io → Telegram integration (@my_hc_bot) | Email integration | Phase 7 не пишет new alert code; HC's built-in integrations |
| Operator runbook docs | `README.md` (single file, RU primary) | — | Small team, operator IS developer; split-doc adds friction |
| Deliberate-failure verification | `bin/test-failure-alert.sh` orchestrator | — | Reuses existing CLI surface (`--sanity-gate-n 999999` + `deliver-run`); no new production Python |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCHED-01 | Системный cron на VPS запускает `python -m ga_crawler` раз в неделю в ночь воскресенья (Asia/Almaty) | D-708 cron entry verbatim; D-709 wrapper invokes `uv run python -m ga_crawler weekly-run` |
| SCHED-02 | Cron-запись использует `CRON_TZ=Asia/Almaty` (нет drift из-за UTC server) | crontab(5) verified — `CRON_TZ` scope-limited to one /etc/cron.d/ file |
| SCHED-03 | Healthchecks.io dead-man's-switch получает start/success/fail-пинги | D-701 bash wrapper owns /start /success /fail; D-702 SaaS free tier; D-703 grace 2h + fail-loud если URL missing |
| SCHED-04 | Структурированные JSON-логи (structlog) на диск с ротацией; видно через `tail` / `grep` | D-704 wrapper редиректит stdout/stderr; D-705 logrotate weekly rotate 13 |
| SCHED-05 | Документация по setup: `README.md` с инструкцией установки на чистый VPS + deliberate-failure тест | D-706 `bin/test-failure-alert.sh`; D-707 10-section README structure RU primary |

## Standard Stack

### Core (already on Ubuntu 24.04 base; no installs needed)

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| **cron** (Vixie) | Ubuntu 24.04 default (`cron` package) | Weekly scheduler | CLAUDE.md §Scheduling LOCKED — "system cron over APScheduler/Celery/Prefect HIGH"; STATE.md line 138 |
| **logrotate(8)** | base | Log rotation weekly keep 13 | Linux idiomatic; D-704/D-705 |
| **flock(1)** | util-linux (base) | Advisory lock guard | Kernel-level mutex; CONTEXT.md D-709 |
| **curl** | base | HC.io ping HTTP client | bash wrapper line `curl -fsS -m 10 --retry 3 ...`; no new install |
| **bash** | base (`/bin/bash`) | wrapper script runtime | `bin/backup.sh` precedent (Plan 02-06) |
| **sqlite3** | base | runbook DB inspection | README §8 operations runbook `sqlite3 prices.db 'SELECT ...'` |

### SaaS

| Service | Tier | Purpose | Why |
|---------|------|---------|-----|
| **Healthchecks.io** | Free (up to 20 checks, 2 team members, Telegram + email integrations) | Dead-man's-switch + alert routing | D-702: SaaS избегает SPOF (self-hosted на том же VPS — circular monitoring); 20 checks ≫ нам нужен 1 |

### Hosting (inherited from CLAUDE.md §Deployment + STATE.md line 157)

| Component | Choice | Why |
|-----------|--------|-----|
| VPS provider | Hetzner CX22 EU (Falkenstein/Helsinki) | CLAUDE.md §Deployment LOCKED; €4.50–8/month; 2 vCPU + 4 GB RAM достаточно для Camoufox + Chromium peak ~1.5GB |
| OS | Ubuntu 24.04 LTS | CLAUDE.md §Deployment LOCKED; vixie cron + logrotate в base |
| Python toolchain | uv (Astral) installed via curl script | CLAUDE.md §Stack LOCKED; STATE.md line 160 `[build-system] hatchling` makes `uv sync` install package |
| Container | NO (D-710 defers Docker to v2) | Camoufox Firefox-pinned не совместим с `mcr.microsoft.com/playwright/python:v1.57.0-noble` (Chromium-based); custom image = INFRA-V2-04 backlog |

### Installation

```bash
# README §2 — VPS setup verbatim (operator copies)
sudo apt update && sudo apt install -y curl sqlite3 logrotate cron git
sudo useradd -r -m -d /opt/ga_crawler -s /bin/bash ga_crawler
sudo -u ga_crawler bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -u ga_crawler git clone <repo> /opt/ga_crawler
cd /opt/ga_crawler && sudo -u ga_crawler uv sync
sudo -u ga_crawler uv run playwright install firefox  # Camoufox Firefox 135
sudo install -d -o ga_crawler -g ga_crawler -m 0755 /var/log/ga_crawler
sudo cp deploy/etc-cron-d-ga_crawler /etc/cron.d/ga_crawler
sudo chmod 0644 /etc/cron.d/ga_crawler
sudo chown root:root /etc/cron.d/ga_crawler
sudo cp deploy/etc-logrotate-d-ga_crawler /etc/logrotate.d/ga_crawler
sudo chmod 0644 /etc/logrotate.d/ga_crawler
sudo chown root:root /etc/logrotate.d/ga_crawler
sudo systemctl reload cron
```

**Version verification (no new versioned deps in Phase 7):**
- Phase 7 adds zero entries to `pyproject.toml` (verified — D-710 + CONTEXT.md §code_context line 308 "pyproject.toml: NO changes").
- `aiogram>=3.27,<4.0` (Phase 6, line 15 of `pyproject.toml`) — already shipped; Phase 7 wrapper не trogает.
- Cron + logrotate + flock are base OS — no version pin needed in repo.

## Architecture Patterns

### System Architecture Diagram

```
   ┌────────────────────────────┐
   │ Ubuntu 24.04 system cron    │  (Vixie, /etc/cron.d/ga_crawler)
   │  CRON_TZ=Asia/Almaty        │
   │  0 23 * * 0 ga_crawler …   │
   └────────────┬────────────────┘
                │ Sunday 23:00 Almaty (= UTC+5 = Sunday 18:00 UTC)
                ▼
   ┌────────────────────────────┐
   │ /opt/ga_crawler/bin/        │
   │  weekly-run.sh              │ (D-709 wrapper, bash + flock + curl)
   └──┬──────────┬───────────┬───┘
      │          │           │
      │          │ set -a    │  exec 9>/var/lock/ga_crawler-weekly.lock
      │          │ source .env  │  flock -n 9 || exit 5
      │          │ set +a    │
      │          │           │
      │          ▼           ▼
      │      ENV vars       LOG_FILE = /var/log/ga_crawler/weekly-run-YYYY-MM-DD.log
      │     (HC_PING_URL,   ────────────┐
      │      TG_BOT_TOKEN,                │ stdout+stderr append
      │      TG_*_CHAT_ID)                │
      │                                   │
      ▼                                   │
   curl ${HC_PING_URL}/start ─────────────┼──────► Healthchecks.io
                                          │           SaaS
      ▼                                   │            │ /fail or
   set +e                                 │            │ grace-expire
   uv run python -m ga_crawler weekly-run │            ▼
   ─── viled fetch                        │       Telegram integration
   ─── goldapple fetch (Camoufox)         │       (@my_hc_bot → ops chat)
   ─── matcher                            │
   ─── reporter (xlsx + summary)          │
   ─── delivery (aiogram → Telegram)      │ ─────► Telegram Bot API
       EXIT=$?                            │         (business chat = xlsx + caption,
   set -e                                 │          ops chat = alerts)
      │                                   │
      ▼                                   │
   if EXIT==0:                            │
      curl ${HC_PING_URL}            ─────┼──────► Healthchecks.io /success
   else:                                  │
      curl --data-raw "exit=$EXIT"        │
        ${HC_PING_URL}/fail          ─────┼──────► Healthchecks.io /fail
                                          │
      ▼                                   │
   exit $EXIT                             │
                                          │
   ─────────────────────────────          │
                                          ▼
   Daily 01:00 (separate cron row):  /var/log/ga_crawler/*.log
   /opt/ga_crawler/bin/backup.sh     ────►  logrotate(8) weekly rotate 13
   → backups/ (4-rotate retention)        (D-705; .log.gz archives)
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| Cron schedule | `deploy/etc-cron-d-ga_crawler` → `/etc/cron.d/ga_crawler` | Define `CRON_TZ=Asia/Almaty` + `MAILTO=""` + 2 rows (weekly-run Sunday 23:00, backup daily 01:00); root-owned; **filename has NO dots** (Pitfall #1) |
| Weekly wrapper | `bin/weekly-run.sh` | Own `.env` loading + HC pings + flock + log redirect + exit-code preservation per D-709 contract |
| Deliberate-failure orchestrator | `bin/test-failure-alert.sh` | Drive `--sanity-gate-n 999999` + extract run_id + invoke `deliver-run` + emit verification checklist per D-706 |
| Log rotation | `deploy/etc-logrotate-d-ga_crawler` → `/etc/logrotate.d/ga_crawler` | weekly + rotate 13 + compress + delaycompress + missingok + notifempty + create 0644 ga_crawler ga_crawler |
| ENV template | `.env.example` | Phase 6 3 vars + Phase 7 ADD `HC_PING_URL=` |
| Operator runbook | `README.md` | 10 sections RU primary per D-707 |

### Pattern 1: bash wrapper with fail-soft pings + fail-loud missing ENV (D-709)

**What:** Wrapper holds the responsibility hierarchy `lock > config > production exec > monitoring`.

**When to use:** Anytime production exec is wrapped by ops layer that needs hard-crash coverage (OOM, segfault, kill -9).

**Example:**
```bash
#!/bin/bash
# Source: CONTEXT.md D-709 (locked) + flock(1) Ubuntu manpage idiom
set -euo pipefail
cd /opt/ga_crawler

# 1) ENV load (bash side; Python side uses python-dotenv via cli.py per RESEARCH caveat #4)
set -a
source .env
set +a

# 2) fail-loud: HC_PING_URL required per D-703
: "${HC_PING_URL:?HC_PING_URL missing — refusing to run per D-703}"

# 3) single-writer flock guard (no-wait; cron + manual overlap → second exits)
exec 9>/var/lock/ga_crawler-weekly.lock
flock -n 9 || { echo "Another weekly-run holds the lock — refusing" >&2; exit 5; }

LOG_DIR=/var/log/ga_crawler
LOG_FILE="$LOG_DIR/weekly-run-$(date +%F).log"

# 4) /start ping (fail-soft — HC outage MUST NOT block production)
curl -fsS -m 10 --retry 3 "${HC_PING_URL}/start" > /dev/null || true

# 5) exec production; preserve exit code through set -e/+e dance
set +e
uv run python -m ga_crawler weekly-run "$@" >> "$LOG_FILE" 2>&1
EXIT=$?
set -e

# 6) success/fail ping (fail-soft)
if [[ $EXIT -eq 0 ]]; then
  curl -fsS -m 10 --retry 3 "${HC_PING_URL}" > /dev/null || true
else
  curl -fsS -m 10 --retry 3 --data-raw "exit=$EXIT" "${HC_PING_URL}/fail" > /dev/null || true
fi

exit $EXIT
```

**Why this shape:**
- `set -euo pipefail` catches typos in ENV names (`unbound variable`) before they cause silent failures
- `set -a` auto-exports vars during `source .env` — without it, vars are local to wrapper, not inherited by `uv run python -m ga_crawler`
- `flock -n 9` non-blocking: holder of lock keeps it; new invocation refuses (exit 5) — prevents cron+manual race
- `set +e ... $? ... set -e` preserves Python exit code through the success/fail-ping branch
- `|| true` on HC pings: HC outage MUST NOT mask production exit code or block ping (HC service-level reliability ≪ production reliability requirement)

### Pattern 2: `/etc/cron.d/` file with CRON_TZ + MAILTO + user column (D-708)

**What:** System cron entries declarable as repo artifact (config-as-code).

**When to use:** Anytime more than 1 cron row or non-UTC timezone OR ops visibility wanted.

**Example:**
```
# /etc/cron.d/ga_crawler  (root-owned, 0644, NO dot in filename)
# Source: CONTEXT.md D-708 (locked); crontab(5)
CRON_TZ=Asia/Almaty
MAILTO=""
0 23 * * 0 ga_crawler /opt/ga_crawler/bin/weekly-run.sh
0 1  * * * ga_crawler /opt/ga_crawler/bin/backup.sh
```

**Why this shape:**
- `CRON_TZ=Asia/Almaty` scope-limited to this file [VERIFIED: crontab(5)] — doesn't pollute global cron
- `MAILTO=""` empty string explicitly disables cron email (HC.io covers alerting; cron emails to root@localhost would silently pile up before redirect kicks in)
- User column `ga_crawler` per Vixie cron `/etc/cron.d/` format
- Filename `ga_crawler` (no dot, no other punctuation) — required per Vixie cron (Pitfall #1)

### Pattern 3: logrotate(8) config for daily-stamped logs (D-705)

**Example:**
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

**Why each directive:**
- `weekly`: rotate once per week (every Sunday by default; logrotate cron at `/etc/cron.daily/logrotate` decides timing per state file)
- `rotate 13`: keep 13 rotated archives → 3 months history
- `compress`: gzip rotated files (-> `.gz` archive)
- `delaycompress`: postpone gzip to next rotation cycle, so the most-recent rotated file stays uncompressed (one extra rotation in unrotated form — friendlier for "yesterday's run" diagnosis)
- `missingok`: don't error if `/var/log/ga_crawler/*.log` matches zero files (first run before any cron has fired)
- `notifempty`: don't rotate a 0-byte log (avoids rotating an empty placeholder)
- `create 0644 ga_crawler ga_crawler`: after rotation, create new empty file owned by `ga_crawler:ga_crawler` with mode 0644 — wrapper's `>>` append picks up the new file transparently

### Anti-Patterns to Avoid

- **Anti-pattern:** HC ping done from Python inside `weekly_run`. **Why bad:** Camoufox OOM kill on Hetzner 4 GB box → Python dead → no /fail ping → ops blind until 2 h grace expires. **Use instead:** bash wrapper owns pings (D-701).
- **Anti-pattern:** Per-step HC pings (separate UUIDs for viled / goldapple / matcher / reporter / deliver). **Why bad:** 5 checks in HC UI + 5 alert routes = cognitive load × 5 for marginal observability gain (phase-level errors already in structlog logs). **Use instead:** one check per project; phase-level inspection via `grep '"phase":"goldapple"' weekly-run-…log`.
- **Anti-pattern:** `crontab -u ga_crawler -e` (per-user crontab). **Why bad:** no `cat /etc/cron.d/*` visibility for ops; not git-trackable; cannot set `CRON_TZ` (env vars in user-crontab are deprecated/inconsistent across cron variants). **Use instead:** `/etc/cron.d/ga_crawler` (D-708).
- **Anti-pattern:** Filename `/etc/cron.d/ga_crawler.conf` or `.cron`. **Why bad:** Vixie cron silently ignores files with dots [VERIFIED: manpages.ubuntu.com/jammy/man8/cron.8]. **Use instead:** `ga_crawler` (no extension).
- **Anti-pattern:** Lock file in `/tmp/` or `/var/run/` (modern). **Why bad:** `/tmp` may be cleaned by tmpfiles.d; `/var/run` is symlink to `/run` (tmpfs) — works but `/var/lock` → `/run/lock` is the FHS-blessed location for lock files. **Use instead:** `/var/lock/ga_crawler-weekly.lock` (D-709).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dead-man's-switch / missed-run alerting | Custom Python timer + Telegram poll | Healthchecks.io free tier | SaaS отдельно от monitored host — no SPOF; grace + Telegram integration уже built |
| Log rotation | Python `RotatingFileHandler` in `_configure_logging()` | logrotate(8) | Camoufox subprocess stdout/stderr НЕ видны inside-process; single-file-truth теряется (D-704) |
| Cron-style scheduling | APScheduler 4 as daemon | system cron `/etc/cron.d/*` | 50-летняя надёжность; one weekly job = no need for in-process scheduler (STATE.md line 138) |
| Single-writer mutex | Bash pidfile + `kill -0 $PID` check + cleanup trap | flock(1) `-n 9` | Kernel-level advisory lock; tmpfs auto-cleanup at reboot; no stale-pid races |
| Telegram alert routing | Custom HC-to-Telegram bridge service | HC.io built-in Telegram integration (@my_hc_bot) | Zero code; UI-configured; battle-tested |
| `.env` parsing in bash | Manual `while read line; do export ...; done` | `set -a; source .env; set +a` | Idiomatic; matches python-dotenv on simple K=V (Pitfall #4) |

**Key insight:** Phase 7 is **integration of established Linux ops primitives** — no domain-specific custom solutions. Hand-rolling any of the above introduces edge cases (timezone drift, OOM blindness, lock cleanup, etc.) that the standard tools have already solved.

## Runtime State Inventory

> Phase 7 is **not** a rename/refactor phase — it adds new artifacts (`bin/weekly-run.sh`, `bin/test-failure-alert.sh`, `deploy/*`, `README.md`, `.env.example` edit, cron + logrotate configs) without modifying existing identifiers. This section is included for completeness per ops-layer convention since Phase 7 introduces **first-time** filesystem and OS state.

| Category | Items Created (first time) | Action Required |
|----------|---------------------------|------------------|
| Stored data | None — Phase 7 does NOT write to DB (only Python `weekly-run` writes, untouched) | None |
| Live service config | Healthchecks.io check (1 row); Telegram integration record (1 entry referencing @my_hc_bot in ops chat) | Operator one-time UI setup per README §5 |
| OS-registered state | `/etc/cron.d/ga_crawler` (2 rows: weekly-run + backup); `/etc/logrotate.d/ga_crawler`; `/var/log/ga_crawler/` directory; `/opt/ga_crawler/` source tree; `ga_crawler` system user; `/var/lock/ga_crawler-weekly.lock` (transient, tmpfs) | All registered via README §2 setup; no migration (greenfield) |
| Secrets/env vars | `.env` on VPS (NOT in git): `TG_BOT_TOKEN`, `TG_BUSINESS_CHAT_ID`, `TG_OPS_CHAT_ID`, **NEW** `HC_PING_URL` | Operator copies `.env.example` → `.env` and fills; README §3 documents |
| Build artifacts | None Phase-7-specific (Phase 7 adds zero deps; pyproject.toml unchanged); Camoufox Firefox binary already installed by `uv run playwright install firefox` (Phase 3) | None — runtime unchanged |

**Nothing in DB schema/migration category** — verified: STATE.md «Phase 7 — нет новых `runs.stats.*` namespace» (CONTEXT.md Claude's Discretion line 154) + «pyproject.toml: NO changes» (Action Items line 308).

## Common Pitfalls

### Pitfall #1: `/etc/cron.d/` файл с точкой в имени тихо игнорируется

**Symptom:** Cron entry deployed, `cat /etc/cron.d/ga_crawler.conf` shows correct content, но job никогда не запускается. `journalctl -u cron` пусто. Healthchecks.io alert «missed run» через grace period — но непонятно почему.

**Root cause:** Vixie cron на Ubuntu 24.04 принимает в `/etc/cron.d/` ТОЛЬКО файлы с именами из `[A-Za-z0-9_-]+` (letters, digits, underscore, hyphen — **NO dots**) [VERIFIED: manpages.ubuntu.com/jammy/man8/cron.8 — "must consist solely of upper- and lower-case letters, digits, underscores, and hyphens"]. Файлы с точкой ИЛИ другим punctuation silently skipped — no log, no warning.

**Fix/guard:** Имя файла = `ga_crawler` (no extension). Planner verifier: Plan 07-XX Wave 0 task — `test -f /etc/cron.d/ga_crawler` AND `! ls /etc/cron.d/*.conf 2>/dev/null | grep ga_crawler` (negative-assert). README §2 setup row uses exact filename. **Test:** `sudo run-parts --test /etc/cron.d/` lists ga_crawler (run-parts uses same naming rules — proves cron will pick it up).

### Pitfall #2: `MAILTO` unset vs `MAILTO=""` — silent root@localhost mailbox bloat

**Symptom:** After first cron run, `/var/mail/root` grows; if mail subsystem disabled (default Ubuntu 24.04 server), `journalctl` shows `cron: postfix not running, message dropped` errors filling system journal.

**Root cause:** Если `MAILTO` НЕ задан, cron шлёт any stdout/stderr from cron'd command на email root@localhost. Wrapper редиректит stdout+stderr в LOG_FILE — но любой `set -x` debug **before** redirect line ИЛИ early-failure (e.g., `cd /opt/ga_crawler` fails because directory moved) → cron captures that output and emails. `MAILTO=""` (empty string) explicitly disables cron email [VERIFIED: crontab(5) "If MAILTO is defined but empty (MAILTO=""), no mail will be sent"].

**Fix/guard:** D-708 cron entry has `MAILTO=""` verbatim. Planner Plan 07-XX Wave 0: `grep '^MAILTO=""' deploy/etc-cron-d-ga_crawler` returns 1 line; canary in test_cron_template_shape.

### Pitfall #3: flock `-n` exit code 1 collides with generic "error" exit code; CONTEXT.md uses exit 5

**Symptom:** Operator runs `bin/weekly-run.sh` manually while cron'd one is still running → exit code 1; HC.io /fail ping with `exit=1` — looks like a generic Python error, ops investigates wrong layer.

**Root cause:** flock(1) `-n` default behavior: «if `-n` is set and the lock fails due to EWOULDBLOCK, the command exits with the conflict exit code [default 1]» [VERIFIED: man7.org/linux/man-pages/man1/flock.1 + util-linux flock.c source]. Conflated with Python exit-1 (generic error).

**Fix/guard:** D-709 wrapper uses **shell-level explicit exit code** `flock -n 9 || { echo "..." >&2; exit 5; }` — exit 5 reserved for «double-run refused». README §3 ENV table documents reserved exit codes (3=skipped_no_credentials, 4=missing HC_PING_URL, 5=flock-double-run-refused). Planner canary in `bin/weekly-run.sh`: source-grep `exit 5` substring present + comment cites D-709.

### Pitfall #4: `set -a; source .env` vs python-dotenv parser drift on values containing `#` or multiline content

**Symptom:** `TG_BOT_TOKEN=12345:abc#xyz` in `.env` → bash sees full string; python-dotenv (used by `cli.py::_cmd_deliver` for local-dev) sees `12345:abc` (treats `#` as inline comment even within unquoted value). Manual `deliver-run` works (bash didn't apply), but production cron'd weekly-run sees full token via bash — both PASS in current path. **But** if operator quotes: `TG_BOT_TOKEN="12345:abc#xyz"` → bash strips quotes and keeps `#xyz`; python-dotenv ALSO strips quotes but parses comment differently depending on dotenv version. Drift between Phase 6 local-dev path (Python-dotenv) and Phase 7 production path (bash) for non-trivial values.

**Root cause:** python-dotenv treats `#` as comment start inside quoted strings [CITED: dev.to/proteusiq] — bash does not when `#` is within `"..."` or `'...'`. Multiline values (`KEY="line1\nline2"`) also parse differently.

**Fix/guard:** Current production secrets do NOT contain `#` (TG_BOT_TOKEN = `<bot_id>:<35-char-alphanum-token>` — Telegram BotFather format excludes `#`; HC_PING_URL = `https://hc-ping.com/<uuid>` — no `#`; chat_ids = numeric). Planner Plan 07-XX adds explicit canary `test_env_example_simple_values_only`: parses `.env.example`, asserts no value contains `#`, `\n`, or unbalanced quotes. README §3 ENV table notes «values MUST be single-line, no `#` or backticks; if you need them, escape via bash quoting `'...'` AND keep python-dotenv version pinned to ≥1.0.»

### Pitfall #5: logrotate runs BEFORE `ga_crawler` user exists → silent fail; logrotate runs ON empty 0-byte log → `notifempty` skips

**Symptom (sub-case A):** Operator follows README §2 in wrong order: installs logrotate config, runs `logrotate -f` BEFORE `useradd ga_crawler` → logrotate fails silently (no user → can't chown → drops to fallback or errors invisibly). First weekly run later writes new log as wrong owner.

**Symptom (sub-case B):** First Sunday's run fails immediately (Camoufox bootstrap crash) before writing any structlog event → log file is 0 bytes → logrotate next Sunday skips it via `notifempty` → no rotation cycle established → 13-rotate retention window never starts. Subtle: not a bug, but ops needs to know «empty logs intentionally not rotated» before they expect to see `.log.gz` archives.

**Root cause:** `create 0644 ga_crawler ga_crawler` requires user `ga_crawler` to exist when `logrotate` is invoked; `notifempty` skips 0-byte files per definition [VERIFIED: linux.die.net/man/8/logrotate].

**Fix/guard:** README §2 setup order: `useradd -r -m -d /opt/ga_crawler ga_crawler` (line 1) **BEFORE** `sudo cp deploy/etc-logrotate-d-ga_crawler /etc/logrotate.d/ga_crawler` (line N). Planner README §2 ordering checklist enforces. Smoke gate after setup: `sudo logrotate -d /etc/logrotate.d/ga_crawler` (debug, no-act) prints `Acquired lock` + parse summary без errors → operator sees «config valid». For sub-case B: README §9 notes «.log.gz archives appear week 2 onwards (week 1's log rotates first Sunday after creation); 0-byte logs are intentionally not rotated per `notifempty`».

### Pitfall #6: Camoufox Firefox needs $HOME to exist OR `XDG_CACHE_HOME` set; cron env is minimal

**Symptom:** Cron'd weekly-run reaches `uv run python -m ga_crawler weekly-run` → Camoufox bootstrap attempts to create profile cache → `mkdir: cannot create directory '/.cache/mozilla'` — Camoufox subprocess crashes → exit ≠ 0 → /fail ping fires → operator sees «Camoufox exit 1» in HC dashboard with no further diagnostic.

**Root cause:** Cron's exec environment is minimal: `HOME=/home/$USER` IF user has home dir; `PATH=/usr/bin:/bin` (no `/usr/local/bin`, no uv-installed binaries); no `XDG_*` vars. Firefox storage default: `$XDG_CACHE_HOME` → fallback `$HOME/.cache/mozilla` [VERIFIED: bugzilla.mozilla.org/259356]. If `HOME` is empty string (system user without `-m` flag in `useradd`), Firefox tries `/.cache/mozilla` (root) → permission denied → crash.

**Fix/guard:** `useradd -r -m -d /opt/ga_crawler -s /bin/bash ga_crawler` (D-708) — `-m` creates home dir `/opt/ga_crawler`; `-d /opt/ga_crawler` sets HOME for the user. Cron entry runs as `ga_crawler` per user column — cron picks up `HOME` from `/etc/passwd` entry. Wrapper's `cd /opt/ga_crawler` ensures cwd matches. `uv run` itself sets up venv-aware PATH inside subprocess. Planner README §2 verbatim cites `useradd -r -m -d /opt/ga_crawler` and adds smoke gate `sudo -u ga_crawler bash -c 'env | grep -E "^(HOME|PATH)="'` shows non-empty HOME. Plan 07-XX Wave 0: in `bin/weekly-run.sh`, **after** `set -a; source .env; set +a`, optionally add defensive `export HOME="${HOME:-/opt/ga_crawler}"` (belt-and-suspenders; remove if redundant after testing). Test: `bin/test-failure-alert.sh` first invocation in smoke runs end-to-end against viled only — exercises Camoufox? **No, `--viled-only` skips goldapple/Camoufox**. Real Camoufox smoke happens at first goldapple weekly run. README §2 closing step: «After first full weekly cron run, verify `/opt/ga_crawler/.cache/mozilla/firefox/` exists and is owned by `ga_crawler`.»

### Pitfall #7: HC.io `--data-raw "exit=$N"` POST body shown in dashboard but NOT in Telegram alert by default

**Symptom:** Operator pings `/fail` with `--data-raw "exit=5"` (flock collision); HC dashboard shows the body as "Last Failure" event detail. Operator expects Telegram alert to include `exit=5` text → opens Telegram and sees only «ga_crawler weekly is DOWN» — no exit code.

**Root cause:** HC.io stores POST body (up to 100 kB UTF-8) and surfaces it in web UI "Pings" page [VERIFIED: healthchecks.io/docs/http_api/]. Telegram integration template by default shows check name + status + ping URL — does NOT inline the body. To include body, operator must customize the Telegram alert template (HC supports per-integration templating in paid tiers; free tier uses default).

**Fix/guard:** README §5 Healthchecks.io setup step «Telegram integration» includes operator note: «Telegram alert shows status + check name; click the HC dashboard link in the alert to see exit code from the POST body. For self-contained alerts, free-tier default template is what you get — exit code is one click away.» Plan 07-XX Wave 0: README §5 final paragraph documents this. **Alternative:** Operator может upgrade HC.io free→paid for custom templates ($5-10/month) — out of scope v1 per CONTEXT.md «20 checks free is enough».

### Pitfall #8: `curl --retry 3` обходит `-m 10` timeout per-attempt — total wait can reach 30s+ exposed to cron-budget

**Symptom:** HC.io has brief outage; wrapper's `curl -fsS -m 10 --retry 3` on `/start` ping waits up to 10s × 3 attempts = 30s+ before falling through `|| true`. Cron job nominally Sunday 23:00; if HC outage at that moment → production exec starts at 23:00:30 instead of 23:00:00. Cumulative across `/start`+`/success`-or-`/fail` pings = up to 60s budget burn.

**Root cause:** `curl -m N` is per-attempt max time, not total; `--retry 3` adds 3 retries with exponential backoff. Plus DNS resolution `hc-ping.com` adds latency.

**Fix/guard:** 30-60s budget burn is acceptable for weekly batch job (production exec is 2-4h; 60s ≪ 1%). Wrapper's `|| true` ensures HC outage never blocks production exec. **However:** ops should know via README §5 «HC outage adds up to ~60s to run start/end; no operator action needed». Planner can keep `--retry 3` for resilience (transient TLS handshake failures) OR replace with `--retry 1` if budget-tightness desired — Claude's Discretion in CONTEXT.md does not constrain. **Recommendation:** Keep D-709 verbatim (`--retry 3`); add README §9 note.

## Code Examples

### Example 1: `/etc/cron.d/ga_crawler` (D-708 verbatim)

```
# Source: CONTEXT.md D-708; crontab(5); Pitfall #1 (no dots in filename)
CRON_TZ=Asia/Almaty
MAILTO=""
0 23 * * 0 ga_crawler /opt/ga_crawler/bin/weekly-run.sh
0 1  * * * ga_crawler /opt/ga_crawler/bin/backup.sh
```

### Example 2: `/etc/logrotate.d/ga_crawler` (D-705 verbatim)

```
# Source: CONTEXT.md D-705; logrotate(8)
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

### Example 3: Test logrotate config without waiting for Sunday

```bash
# Dry-run (no actual rotation; print what would happen)
sudo logrotate -d /etc/logrotate.d/ga_crawler

# Force rotation immediately (use carefully — bypasses state-file timing)
sudo logrotate -f /etc/logrotate.d/ga_crawler

# Inspect state file (when was each rotated last?)
sudo cat /var/lib/logrotate/status | grep ga_crawler
```

[VERIFIED: man7.org/linux/man-pages/man8/logrotate.8 via mirror — `-d` debug, `-f` force, `/var/lib/logrotate/status` default state file]

### Example 4: Deliberate-failure orchestrator shape (D-706)

```bash
#!/bin/bash
# Source: CONTEXT.md D-706; reuses --sanity-gate-n 999999 (Plan 04-05) + deliver-run (Phase 6 D-608)
set -euo pipefail
cd /opt/ga_crawler

echo "==> Step 1: Forced sanity-N gate fail (viled-only crawl, ~2 min)"
bin/weekly-run.sh --viled-only --sanity-gate-n 999999 || true
# Wrapper exits 2 (undelivered) or 5 (flock); we don't care here — log captures it

echo "==> Step 2: Extract last run_id from log"
LOG_FILE="/var/log/ga_crawler/weekly-run-$(date +%F).log"
RID=$(tail -200 "$LOG_FILE" | grep -o '"run_id":[0-9]*' | tail -1 | grep -o '[0-9]*')
echo "    run_id=$RID"

echo "==> Step 3: Invoke deliver-run for ops alert (no HC ping — separate invocation)"
sudo -u ga_crawler /opt/ga_crawler/.venv/bin/python -m ga_crawler deliver-run --run-id "$RID"

echo "==> Step 4: Verification checklist (operator runs visually)"
cat <<EOF
  [ ] Telegram ops chat: alert message visible with reason='upstream pipeline failed' for run #$RID
  [ ] Telegram business chat: NO new message
  [ ] Healthchecks.io dashboard: /start + /fail pings logged
  [ ] DB: sqlite3 /opt/ga_crawler/prices.db 'SELECT run_id, status, reason FROM runs WHERE run_id=$RID'
        Expected: failed | sanity_gate_n_failed:120<999999
  [ ] DB stats: sqlite3 ... "SELECT json_extract(stats,'\$.deliver.delivery_status') FROM runs WHERE run_id=$RID"
        Expected: delivered_ops_only
EOF
```

### Example 5: HC.io ping flow (curl wrapper idiom)

```bash
# /start (job initiated)
curl -fsS -m 10 --retry 3 "${HC_PING_URL}/start" > /dev/null || true

# /success (bare UUID; job ended OK)
curl -fsS -m 10 --retry 3 "${HC_PING_URL}" > /dev/null || true

# /fail with diagnostic body (job ended non-zero; body shown in HC dashboard)
curl -fsS -m 10 --retry 3 --data-raw "exit=$EXIT" "${HC_PING_URL}/fail" > /dev/null || true
```

[VERIFIED: healthchecks.io/docs/http_api/ — `HEAD|GET|POST https://hc-ping.com/<uuid>{/,/start,/fail}`; POST body stored up to 100 kB]

## State of the Art

| Old Approach | Current Approach (2026) | When Changed | Impact |
|--------------|------------------------|--------------|--------|
| Per-user crontab (`crontab -u ga_crawler -e`) | `/etc/cron.d/<app>` with user column | Vixie cron `/etc/cron.d/*` format mid-2010s | ops visibility (`cat /etc/cron.d/*` shows all), git-trackable, `CRON_TZ` supported |
| `MAILTO=ops@example.com` for cron failure alerts | `MAILTO=""` + external monitoring (HC.io / Sentry / Datadog) | ~2018+ as SaaS observability matured | Dead-man's-switch + Telegram routing without local MTA setup |
| `/var/run/<app>.pid` lockfile + signal trap | flock(1) `-n` advisory lock on `/var/lock/<app>.lock` | flock(1) shipped in util-linux 2.6+ (2007+) | Kernel-level mutex; auto-released at process exit; tmpfs auto-cleanup at reboot |
| `nohup foo &; tail -f log` adhoc Python rotation | logrotate(8) + structlog JSONRenderer to stdout + wrapper redirect | logrotate stable since 2000s; structlog ≥25 standard | Standard Linux pattern; multi-process (Camoufox subprocess) captured uniformly |

**Deprecated/outdated:**
- `MAILTO=root@localhost` (or missing `MAILTO`): silent mail-spool growth on hosts without MTA — replaced by `MAILTO=""` + external monitoring.
- `/var/run/<app>.pid` lock files: replaced by flock(1) `/var/lock/*.lock` (FHS-blessed location).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `set -a; source .env` parses Phase 6 + Phase 7 `.env` values identically to `python-dotenv 1.0+` for current set of 4 vars (no `#`, no multiline, no escaped quotes) | Pitfall #4 | LOW — current vars are simple K=V strings; if future operator adds `#` to a token, planner canary catches it |
| A2 | Camoufox 0.4.11 (Firefox 135.0.1-beta.24) launches successfully under cron context when `HOME` is set by `useradd -m -d /opt/ga_crawler` | Pitfall #6 | MEDIUM — Camoufox spike (Phase 1) ran on KZ-laptop, NOT under cron on Hetzner CX22 EU. STATE.md line 157 + line 207 «[Phase 7 backlog] Camoufox+EU smoke fetch» — verification deferred to operator first-run smoke. If Camoufox fails under cron+EU, fallback paths: (a) IPRoyal KZ residential proxy (Phase 1 D-08 reactivation), (b) move from cron → systemd-user-service with explicit env setup. CONTEXT.md acknowledges this risk («mini-smoke `--viled-only --sanity-gate-n 1` purpose-covers setup-green check; full Camoufox+goldapple+EU smoke — отдельная operator task»). |
| A3 | Healthchecks.io free tier (≤20 checks, 2 team members) remains free and includes Telegram integration through v1's operational lifetime | Standard Stack | LOW — HC.io has had free tier since 2015; Telegram integration since 2017; no announced changes. If pricing changes, fallback: (a) self-hosted HC on second VPS, (b) GitHub Actions cron as monitor-of-monitor. |
| A4 | Hetzner CX22 EU has reliable 1-Gbps outbound to `hc-ping.com` (Healthchecks.io) — no firewall/DDoS-protection chokepoints | Standard Stack | LOW — Hetzner is established provider; outbound HTTPS to public SaaS is default-allowed |
| A5 | Vixie cron on Ubuntu 24.04 LTS supports `CRON_TZ` variable scoped to single `/etc/cron.d/*` file | Pattern 2 + Pitfall #1 | LOW — `CRON_TZ` shipped in Vixie cron since ~2010; Ubuntu inherits via `cron` package. [VERIFIED: crontab(5) on manpages.ubuntu.com — references `CRON_TZ`] |

**If user wants to reduce Risk A2:** operator runs a single Camoufox smoke fetch on Hetzner CX22 EU **before** locking Phase 7 deploy — `sudo -u ga_crawler /opt/ga_crawler/.venv/bin/python -m ga_crawler goldapple-smoke`. If gate-shell-rate > 5% or pass < 95/100 → reactivate IPRoyal trial (Phase 1 D-08).

## Open Questions

1. **Does the operator team have an existing Telegram ops chat ID for HC integration, or does Phase 7 deploy require creating a new ops chat?**
   - What we know: Phase 6 ENV setup defines `TG_OPS_CHAT_ID` for `delivery/` ops alerts (separate from HC integration); HC.io Telegram integration goes through `@my_hc_bot` (HC.io's own bot, NOT our `TG_BOT_TOKEN`'s bot).
   - What's unclear: HC.io's `@my_hc_bot` and our `delivery/`'s bot post to the **same** ops chat (correct setup) or to two **different** chats (alert sprawl).
   - Recommendation: README §5 explicitly states «add `@my_hc_bot` to the SAME chat that `TG_OPS_CHAT_ID` resolves to; consolidate ops signals into one chat for simpler triage».

2. **Should the deliberate-failure test (`bin/test-failure-alert.sh`) ping HC.io?**
   - What we know: D-706 step 1 invokes `bin/weekly-run.sh --viled-only --sanity-gate-n 999999`, which DOES fire HC pings (full wrapper path). D-706 step 3 invokes `python -m ga_crawler deliver-run --run-id $RID` directly (NOT via wrapper) — no HC ping there.
   - What's unclear: First half of test fires HC `/fail` ping (with `exit=2` body) → operator sees test runs in HC dashboard alongside real cron runs. Acceptable noise? Or should test script use a separate HC URL (`HC_PING_URL_TEST`)?
   - Recommendation: Acceptable noise per CONTEXT.md "NO cleanup — failed run остаётся в БД как evidence"; deliberate-failure runs are infrequent (post-deploy + after major code changes); operator can manually mark HC failures as expected. Add README §7 note «deliberate-failure test fires a real HC /fail ping; this is expected — mark the alert as `expected` in HC UI».

3. **Logrotate fires from `/etc/cron.daily/logrotate`, which runs at random time within daily window — what if it runs DURING a weekly-run mid-execution?**
   - What we know: `/etc/cron.daily/logrotate` typically runs ~6:25 AM (anacron schedule). Weekly-run starts Sunday 23:00 Almaty (Sunday 18:00 UTC) and lasts 2-4h → ends ~Monday 03:00 Almaty (Sunday 22:00 UTC). Hetzner EU host's logrotate cron runs in UTC → likely Monday 06:25 UTC = Monday 11:25 Almaty. **No overlap** in typical case.
   - What's unclear: Edge case — long-running weekly-run extends past Monday 06:00 UTC → logrotate rotates the `weekly-run-YYYY-MM-DD.log` file while wrapper still has `>>` append redirect open. Standard `create 0644` behavior: logrotate creates new empty file with same name; wrapper's already-open file descriptor (`>>` opens at start) keeps writing to the *rotated* inode — bytes lost from operator's "current log" view.
   - Recommendation: Acceptable risk for weekly batch (small typical-run window; edge case = extended run). Mitigation: README §9 documents «if you see a `.log.1` after current Sunday's run, check `.log.1` for tail bytes — they may belong to current run». Bigger-hammer fix (overkill): use `copytruncate` directive instead of `create` — but `copytruncate` has its own race (zero-byte window) and is anti-pattern when wrapper restart between rotations is feasible (it isn't here — wrapper exits at end of weekly run). **Leave as-is per D-705**; document in §9.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| cron (Vixie) | SCHED-01 / SCHED-02 | ✓ | Ubuntu 24.04 base `cron` package | systemd timer (rejected per STATE.md line 138) |
| logrotate | SCHED-04 / D-705 | ✓ | Ubuntu 24.04 base | structlog `RotatingFileHandler` (rejected per D-704 — Camoufox subprocess stdout invisible) |
| flock(1) | D-709 | ✓ | util-linux base | pidfile + `kill -0 $PID` (rejected — stale-pid races) |
| curl | D-709 HC pings | ✓ | base | `wget` (works; curl more flexible with `--data-raw`) |
| bash | wrapper runtime | ✓ | `/bin/bash` base | none (project standard per `bin/backup.sh`) |
| sqlite3 (CLI) | README §8 runbook + `bin/test-failure-alert.sh` | ✓ | base | Python `sqlite3` module (works but more verbose) |
| Healthchecks.io account | SCHED-03 | external | SaaS free tier | self-hosted HC on second VPS (SPOF avoidance rejects local install) |
| Telegram bot `@my_hc_bot` | HC.io → Telegram alerts | external | SaaS (operated by HC.io) | HC.io email integration (also available free tier) |
| Hetzner CX22 EU VPS | All | external | provisioned by operator | DigitalOcean Droplet (~2× cost; CLAUDE.md §Deployment alternative) |
| Telegram bot (project's own — Phase 6) | DELIVER-* | external (already provisioned Phase 6) | aiogram 3.27+ client | — |
| Camoufox Firefox runtime | Cron'd weekly-run (Phase 3 inheritance) | runtime — install via `uv run playwright install firefox` | Firefox 135.0.1-beta.24 (Plan 03-01 D-313 pin) | IPRoyal KZ residential proxy (Phase 1 D-08 reactivation) if EU+Camoufox fails |

**Missing dependencies with no fallback:** none — all required tools present in Ubuntu 24.04 base, two SaaS accounts (HC.io + Telegram) are operator-provisioned per README §2/§5/§6 setup.

**Missing dependencies with fallback:** Hetzner CX22 EU + Camoufox combination unverified (Assumption A2); fallback paths documented.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (inherited Phase 2..6) for `bin/*.sh` script smoke + ops-config-shape canaries |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_phase07_*.py -x` |
| Full suite command | `uv run pytest -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCHED-01 | Cron entry deploys to `/etc/cron.d/ga_crawler` and matches template verbatim | unit (shape-canary on template file) | `uv run pytest tests/test_phase07_cron_template_shape.py -x` | ❌ Wave 0 |
| SCHED-02 | Cron template contains `CRON_TZ=Asia/Almaty` line and Sunday-23:00 row | unit (string-grep canary on `deploy/etc-cron-d-ga_crawler`) | same as SCHED-01 | ❌ Wave 0 |
| SCHED-03 | `bin/weekly-run.sh` source contains `${HC_PING_URL}/start` + `${HC_PING_URL}` + `${HC_PING_URL}/fail` + `${HC_PING_URL:?...}` substrings | unit (source-lock canary) | `uv run pytest tests/test_phase07_wrapper_contract.py -x` | ❌ Wave 0 |
| SCHED-03 | `bin/weekly-run.sh` source contains `flock -n 9` + `|| true` for HC pings + `exit 5` reserved exit code | unit (source-lock canary on D-709 invariants) | same as above | ❌ Wave 0 |
| SCHED-04 | `deploy/etc-logrotate-d-ga_crawler` contains weekly + rotate 13 + compress + delaycompress + missingok + notifempty + create directives | unit (shape-canary) | `uv run pytest tests/test_phase07_logrotate_template_shape.py -x` | ❌ Wave 0 |
| SCHED-04 | `bin/weekly-run.sh` redirects stdout+stderr to `/var/log/ga_crawler/weekly-run-$(date +%F).log` | unit (source-lock canary) | same as wrapper_contract | ❌ Wave 0 |
| SCHED-05 | `README.md` contains 10 required sections (in order) per D-707 | unit (markdown-heading-shape canary) | `uv run pytest tests/test_phase07_readme_structure.py -x` | ❌ Wave 0 |
| SCHED-05 | `bin/test-failure-alert.sh` source contains `--sanity-gate-n 999999` + `deliver-run --run-id` + verification checklist | unit (source-lock canary) | `uv run pytest tests/test_phase07_test_failure_alert_shape.py -x` | ❌ Wave 0 |
| SCHED-05 | `.env.example` contains `HC_PING_URL=` placeholder line | unit (line-presence canary) | same as wrapper_contract | ❌ Wave 0 |
| SC#1 (cron lands at Almaty time) | manual operator smoke after deploy: monitor first Sunday 23:00 Almaty | manual-only — runtime evidence cannot be automated in CI | `sudo -u ga_crawler /opt/ga_crawler/bin/weekly-run.sh --viled-only --sanity-gate-n 1` (mini-run) | manual-only |
| SC#5 (deliberate-failure end-to-end) | `bin/test-failure-alert.sh` end-to-end on VPS | manual-only — requires real Telegram + HC.io accounts | `sudo -u ga_crawler /opt/ga_crawler/bin/test-failure-alert.sh` | ❌ Wave 0 |

**Manual-only justification:** SC#1 requires runtime observation of a real cron tick; SC#5 requires real Telegram + HC.io network round-trips. Both are operator runbook items, not CI-suitable. Their automated proxies (source-locked shapes of the artifacts that produce these runtime behaviors) cover the «did we ship the right config?» question; the runtime question is owned by the operator's first-deploy smoke per README §2 closing step + README §7 deliberate-failure procedure.

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_phase07_*.py -x` (≤ 5 sec; pure shape canaries on template files; no network, no subprocess)
- **Per wave merge:** `uv run pytest -x` (full suite; ~30 sec; ensures Phase 2..6 frozen modules stay green per `src/ga_crawler/` canary list — `git diff src/ga_crawler/cli.py` empty between Phase 6 head and Phase 7 close-out commits)
- **Phase gate:** Full suite green + manual operator runbook checklist (SC#1 + SC#5 from README §2 + §7) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_phase07_cron_template_shape.py` — covers SCHED-01 + SCHED-02
- [ ] `tests/test_phase07_logrotate_template_shape.py` — covers SCHED-04 directive grep
- [ ] `tests/test_phase07_wrapper_contract.py` — covers SCHED-03 + SCHED-04 source-locks on `bin/weekly-run.sh`
- [ ] `tests/test_phase07_test_failure_alert_shape.py` — covers SCHED-05 source-lock on `bin/test-failure-alert.sh`
- [ ] `tests/test_phase07_readme_structure.py` — covers SCHED-05 README 10-section shape
- [ ] `tests/test_phase07_env_example_shape.py` — covers `.env.example` adding `HC_PING_URL=` line; also Pitfall #4 «no `#` in values» canary
- [ ] `tests/test_phase07_structural_canaries.py` — `git diff` proxies (file-content hash invariants on `src/ga_crawler/cli.py`, `src/ga_crawler/runners/main_run.py`, `src/ga_crawler/_configure_logging` snapshot, no new keys in `runs.stats.*`)
- [ ] Framework install: none — Phase 7 adds zero deps; reuses pytest 8.x + uv from Phase 2..6

*(No `pyproject.toml` changes per D-710 + CONTEXT.md Action Items line 308.)*

## Security Domain

### Applicable ASVS Categories

> `security_enforcement: true` + `security_asvs_level: 1` per `.planning/config.json` line 40-41.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `TG_BOT_TOKEN` (Phase 6) + `HC_PING_URL` UUID — both treated as bearer-token-equivalent secrets; stored in `.env` on VPS, never in git (Phase 6 `.gitignore` already excludes `.env`); README §3 documents secret-handling |
| V3 Session Management | n/a | No sessions in batch job |
| V4 Access Control | yes | `/etc/cron.d/ga_crawler` root-owned 0644; `/var/log/ga_crawler/` owned by `ga_crawler` user 0755; `bin/weekly-run.sh` runs as `ga_crawler` non-root via cron user-column; principle of least privilege |
| V5 Input Validation | n/a | Phase 7 wrapper does not parse untrusted input — `"$@"` pass-through is operator-controlled CLI args |
| V6 Cryptography | yes | HTTPS to `hc-ping.com` + `api.telegram.org` (curl defaults — TLS 1.2+ negotiated automatically); UUID for HC.io is 122-bit entropy [VERIFIED: healthchecks.io/docs/http_api/ "Check's UUID is automatically assigned"] — sufficient for secrecy; treat as bearer token |
| V7 Error Handling | yes | Wrapper exits with explicit codes (3/4/5 reserved per CONTEXT.md); structlog JSON to disk includes `run_id` for forensics; HC alert routes to ops chat |
| V8 Data Protection | yes | `.env` on VPS readable only by `ga_crawler` (set via `chmod 0600 .env`); README §2 includes this step |
| V9 Communications | yes | All outbound HC.io + Telegram + Camoufox traffic is TLS; Hetzner egress firewall default permits |
| V10 Malicious Code | n/a | No exec of untrusted code |
| V11 Business Logic | yes | Single-writer flock guard (D-709) prevents concurrent runs from corrupting `runs` table |
| V12 Files & Resources | yes | logrotate `create 0644 ga_crawler ga_crawler` — no world-writable logs; `/var/lock/*.lock` tmpfs-isolated |
| V13 API & Web Services | n/a | No API exposed by ga_crawler — outbound only |
| V14 Configuration | yes | Cron + logrotate + wrapper are config-as-code (`deploy/*` in repo, deployed via `sudo cp ... && chmod ...`); `.env.example` template + `.env` in `.gitignore` |

### Known Threat Patterns for Phase 7 stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret leak via cron MAILTO | Information Disclosure | `MAILTO=""` disables cron-email; wrapper redirects stdout/stderr to logfile (not stdout to cron) |
| Lock-file race causing double-run + DB corruption | Tampering | flock(1) `-n` advisory lock (D-709); SQLite WAL also offers write-serialization defense in depth |
| Cron command injection via crafted ENV value | Tampering | ENV loaded from operator-controlled `.env` (no untrusted source); cron file root-owned (no unprivileged write) |
| HC.io UUID leak in source / logs | Information Disclosure | UUID lives in `.env` (gitignored) and is referenced as `${HC_PING_URL}` in wrapper (never logged); README §5 warns operator |
| logrotate runs while wrapper writes → bytes lost to rotated inode | DoS (data) | Acceptable per Open Question #3; README §9 documents edge case |
| Camoufox subprocess fingerprint leak to anti-bot vendor | Information Disclosure | Pinned Firefox 135.0.1-beta.24 + Camoufox geoip spoof (Phase 3 D-313); Phase 7 inherits, does not change |
| flock lock-file world-writable allows DoS by unprivileged user | DoS | `/var/lock/` is root-writable; `exec 9>` creates file as `ga_crawler` user with umask-default 0644 — acceptable (lock is advisory, not auth) |
| `set -a; source .env` evaluates malicious shell content | Code injection | `.env` operator-controlled (file ownership `ga_crawler:ga_crawler` 0600); README §2 instructs `chmod 0600 .env`; threat model assumes operator+VPS-root not compromised |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: healthchecks.io/docs/http_api/] — UUID-based ping URL `https://hc-ping.com/<uuid>{/,/start,/fail}`; POST body stored up to 100 kB; rate-limit 5/min/check
- [VERIFIED: healthchecks.io/integrations/telegram/] — `@my_hc_bot` integration steps (invite-to-group + `/start@my_hc_bot` activation + confirmation link)
- [VERIFIED: manpages.ubuntu.com/jammy/man8/cron.8 + crontab(5)] — `/etc/cron.d/*` user-column format; `MAILTO=""` disables email; filename restrictions (no dots, only `[A-Za-z0-9_-]`); `CRON_TZ` variable scope
- [VERIFIED: man7.org/linux/man-pages/man1/flock.1 + util-linux flock.c source] — `-n` exit code default 1 on EWOULDBLOCK; `-E` override; `9>file` redirect creates file if missing
- [VERIFIED: wiki.debian.org/ReleaseGoals/RunDirectory + lwn.net/Articles/436012] — `/var/lock` → `/run/lock` symlink (tmpfs) on modern Linux including Ubuntu 24.04; reboot clears
- [VERIFIED: bugzilla.mozilla.org/259356] — Firefox uses `$XDG_CACHE_HOME` then falls back to `$HOME/.cache/mozilla`
- [VERIFIED: CONTEXT.md D-701..D-710 + REQUIREMENTS.md SCHED-01..05] — locked decisions for Phase 7 deliverable shape
- [VERIFIED: STATE.md lines 138, 157, 184, 195, 196, 207-208] — cascaded invariants for Phase 7 (system cron locked; Hetzner CX22 EU; backup cron row; HC probe `deliver.delivery_status` not `runs.status`; D-606 enum mapping; Phase 7 backlog items)
- [VERIFIED: ROADMAP.md Phase 7 lines 152-164] — phase goal + SC#1..5
- [VERIFIED: CLAUDE.md §Scheduling + §Deployment/Hosting + §Docker?] — cron over APScheduler; Hetzner CX22 EU + Ubuntu 24.04; Docker «optional, recommended» but Phase 7 D-710 defers
- [VERIFIED: bin/backup.sh] — established bash convention pattern Phase 7 mirrors (`#!/usr/bin/env bash`, `set -euo pipefail`, Windows xargs quirk noted)
- [VERIFIED: pyproject.toml] — current deps list; Phase 7 ADDS NOTHING (verified by reading `[project]` block)
- [VERIFIED: src/ga_crawler/cli.py] — current 5 subcommands; exit codes 0/2/3 already returned per phase; Phase 7 wrapper inherits exit-code semantics
- [VERIFIED: .env.example + .gitignore] — Phase 6 setup: 3 TG_* vars in template; `.env` excluded

### Secondary (MEDIUM confidence)
- [CITED: dohost.us logrotate guide 2025-11; betterstack.com logrotate guide] — `weekly` + `rotate N` + `compress` + `delaycompress` + `missingok` + `notifempty` + `create` directive semantics
- [CITED: manpages.ubuntu.com xenial flock(1)] — `flock -n 9` shell-script idiom; `9>/var/lock/...` pattern verified across multiple Ubuntu manpage versions
- [CITED: dev.to/proteusiq «load_dotenv anti-pattern»] — python-dotenv treats `#` as comment inside quoted strings; bash does not — drift risk on values containing `#`
- [CITED: lwn.net/Articles/436012 «Introducing /run»] — `/run` tmpfs purpose: ephemeral system state; `/var/lock` → `/run/lock` migration rationale

### Tertiary (LOW confidence)
- [WebSearch results for «healthchecks Telegram alert template customization» — free tier behavior] — Telegram alert default template inferred from HC.io community discussion; not directly verified against HC.io paid-tier docs. Mitigation: README §5 + Open Question #2 note operator must «click HC dashboard link to see exit code».

## Metadata

**Confidence breakdown:**
- Standard stack (cron + logrotate + flock + bash + HC.io + Hetzner): HIGH — All locked in CONTEXT.md D-701..D-710 and verified against upstream specs (HC.io docs, manpages, Ubuntu wiki)
- Architecture (bash wrapper owns pings + flock guard + log redirect + cron in `/etc/cron.d/`): HIGH — Standard Linux ops patterns confirmed via multiple authoritative sources
- Pitfalls (8 identified): HIGH for #1-#5 + #7-#8 (all VERIFIED upstream); MEDIUM for #6 Camoufox+cron context (untested on Hetzner EU; Assumption A2)
- HC.io specifics (ping semantics + Telegram integration): HIGH (verified against official docs)
- Runtime State Inventory (5 categories): HIGH — exhaustively enumerated; greenfield only (no existing state to migrate)
- Validation Architecture (10 test types mapped to 5 SCs): HIGH — pure shape-canary tests; deterministic; deferrals to manual-only are operator runbook items

**Research date:** 2026-05-12
**Valid until:** 2026-06-12 (30 days for stable; HC.io API + cron + logrotate are decades-stable; Healthchecks.io free-tier policy is the only meaningful risk and changes would be announced)

---

*Generated by gsd-researcher for Phase 7 — Scheduler + Observability Hardening.*
*Phase: 7-scheduler-observability-hardening; 10 decisions locked (D-701..D-710); zero production Python; ships 6 ops artifacts.*
