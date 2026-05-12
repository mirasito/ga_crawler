---
tags: [decision, phase-7, documentation, readme]
date: 2026-05-12
decision-id: D-707
status: active
---

# README 10 sections RU primary EN code — single file для operator-is-developer team

`README.md` at repo root — primary deliverable Phase 7 SCHED-05. **Single file, не split** в OPERATOR.md + DEVELOPER.md: команда — пара человек (PROJECT.md «внутренний инструмент»), operator IS developer initially; split добавляет «куда смотреть?» friction.

## Structure (10 H2 sections в exact order, canary-enforced)

1. **Что это** — 5-line summary из PROJECT.md
2. **VPS setup from-scratch** — Hetzner CX22 Ubuntu 24.04 + `useradd -r -m -d /opt/ga_crawler` + uv + Playwright Firefox + `/var/log/ga_crawler/` + cron file + logrotate file + smoke test
3. **ENV vars** — `TG_BOT_TOKEN` / `TG_BUSINESS_CHAT_ID` / `TG_OPS_CHAT_ID` / `HC_PING_URL` table + ссылка на `.env.example`
4. **Cron entry** — `/etc/cron.d/ga_crawler` content verbatim + SCHED-02 invariant пояснён
5. **Healthchecks.io setup** — пошаговое (account → check → cron schedule + grace 2h → Telegram integration → UUID в `.env`)
6. **Telegram bot setup** — `/newbot` + admin в чатах + chat_id через `@userinfobot`
7. **Deliberate-failure test** — `bin/test-failure-alert.sh` + verification checklist
8. **Operations runbook** — recipes для `undelivered_telegram_unreachable`, reporter bug, matcher bug, backups recovery, run status query
9. **Логи** — location + rotation policy + `tail`/`grep`/`zgrep`+`jq` examples
10. **Dev setup** — короткий блок (5 строк) + ссылка на `CLAUDE.md`

## Language

**RU primary prose, EN code blocks.** Operators читают prose, копипастят code. Команды/flag-имена/ENV-имена не локализуются (потеряется grep-ability в bug reports). PROJECT.md «команда полностью русскоязычная».

## Canary

`tests/test_phase07_readme_structure.py` — markdown-heading-shape canary с ordered H2 list. Нарушение порядка или Cyrillic'а заголовка → RED.

## Connected

- [[Phase 7 ships zero production Python — ops layer over frozen pipeline]] *(README — primary user-facing deliverable)*
- [[bin weekly-run.sh — rigid contract with flock and fail-loud HC_PING_URL]] *(D-709 — README §4 cron + §3 ENV reference wrapper invariants)*
- [[Bash wrapper владеет Healthchecks pings, не Python — hard-crash coverage critical]] *(D-701 — README §5 HC.io setup + §7 deliberate-failure verify rationale)*
