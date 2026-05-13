---
tags: [decision, deploy, vps, yandex-cloud, hetzner, anti-bot, v1-1]
date: 2026-05-13
phase: v1.1-planning
status: locked
impacts: [DEPLOY-01, DEPLOY-05, DEPLOY-06]
---

# Yandex Cloud kz1 over Hetzner EU для KZ-IP anti-bot

## Утверждение

v1.1 deploy target = **Yandex Cloud kz1** (Karaganda zone), не Hetzner CX22 EU.

Несмотря на v1.0 RECON-01 verdict "Hetzner EU работает 99/100 с Camoufox-direct без proxy", пользователь выбрал KZ-region IP как дополнительную защиту против goldapple anti-bot.

## Trade-offs

| | Hetzner CX22 EU | Yandex Cloud kz1 |
|---|---|---|
| **Стоимость** | €4.50/мес (~₸2500) | ~₸6800/мес (~$14) |
| **IP region** | Германия/Финляндия | Казахстан (Karaganda) |
| **Anti-bot risk** | Medium (99/100 verified) | Low (предполагаемый — KZ-IP родной для goldapple.kz) |
| **Camoufox compat** | HIGH (Phase 1 spike verified) | MEDIUM (не верифицирован — Yandex Cloud kz1 запущен 2024) |
| **Stack** | vanilla Ubuntu | vanilla Ubuntu — same setup script работает |
| **Billing** | EU карта | KZ карта / KZ юр.лицо |

## Decision

**Yandex Cloud kz1**, потому что:

1. Пользователь хочет KZ-IP как страховку. Anti-bot vendor GroupIB/F.A.C.C.T. (identified в Phase 1 RECON-01) может усилить geo-discrimination со временем; KZ-IP остаётся внутренним customer-IP для goldapple.kz
2. Stack один в один — `bin/setup-vps.sh` (DEPLOY-02) provider-agnostic, работает на обоих
3. v1.0 deferred backlog уже содержит "Camoufox+EU smoke from Hetzner — если goldapple-smoke regresses from EU IP → revive D-08 IPRoyal trial" — KZ-deploy preempt'ит этот риск

## Wired mitigations в Phase 11

- **DEPLOY-05**: Pre-deploy Camoufox×Yandex compat smoke — verify Camoufox 0.4.11 запускается на Yandex Cloud Ubuntu 24.04 ДО cron handoff (Yandex region 2024 launch, limited Camoufox corpus — risk MEDIUM)
- **DEPLOY-06**: Egress connectivity smoke — `curl -I` к api.telegram.org, hc-ping.com, goldapple.kz, viled.kz from KZ instance. KZ-region может иметь нестандартные filtering rules
- **DEPLOY-04**: `sudo timedatectl set-timezone Asia/Almaty` ОБЯЗАТЕЛЬНО (Pitfall #7 — Yandex Cloud KZ defaults to Moscow TZ; system cron без `CRON_TZ` work в Moscow, Sunday 23:00 Almaty = 21:00 Moscow → 21:00 UTC → 2h раньше)

## Fallback

Если **DEPLOY-05 или DEPLOY-06 fail** на Yandex Cloud kz1:
1. Pivot на Hetzner CX22 EU (v1.0 default) — README §2 stays valid
2. Document failure в `.planning/spikes/v1.1-yandex-cloud-fail/MEMO.md`
3. Revive D-08 IPRoyal trial (v2-backlog) если EU тоже regress

## Alternative considered

- **Hetzner CX22 EU** (v1.0 default) — REJECTED по choice пользователя; держим как fallback
- **Defer to deploy-time** (3rd option в AskUserQuestion) — REJECTED пользователем (явно выбрал Yandex)
- **Self-hosted на existing infra** — нет available infra
- **AWS Lambda / GCP Functions** — already rejected в v1.0 CLAUDE.md (15-min execution limit + headless-browser pain)

## Sources

- AskUserQuestion 2026-05-13 — пользователь выбрал "Yandex Cloud kz1"
- `.planning/research/STACK.md` — Yandex Cloud kz1 = vanilla Ubuntu + SSH confirmed (no proprietary SDK)
- `.planning/research/PITFALLS.md` #8 — Yandex Cloud × Camoufox compat MEDIUM-risk
- CLAUDE.md § Anti-Bot Strategy Tier 1 — "Local KZ-region IP from VPS would be ideal but Hetzner is EU; expect this to fail eventually"
- v1.0 RECON-01 MEMO `milestones/01-MEMO-MULTI-GEO-DECISION.md` — Hetzner EU 99/100 verified
