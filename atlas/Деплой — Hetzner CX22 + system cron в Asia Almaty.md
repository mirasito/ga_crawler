---
tags: [atlas, deployment, ops, cron]
date: 2026-05-05
---

# Деплой — Hetzner CX22 + system cron в Asia Almaty

Маленькая VPS, один процесс, один cron-entry. Нет Docker, нет Kubernetes, нет orchestrator-а.

## VPS

- **Hetzner CX22** (~€4.50–€8/месяц): 2 vCPU, 4 GB RAM, 40 GB SSD, Ubuntu 24.04 LTS
- Hetzner > DigitalOcean / Fly.io по price/perf для batch cron
- EU IP — для goldapple может потребоваться [[Residential proxies — нужны только для goldapple]]

## Cron

```
CRON_TZ=Asia/Almaty
0 2 * * 0 cd /opt/ga_crawler && /opt/ga_crawler/.venv/bin/python -m ga_crawler
```

`CRON_TZ` обязателен — server дефолтит в UTC и сместит запуск на 5 часов. См. [[Cron не сработал — проверь CRON_TZ и Healthchecks ping]].

## Observability

- [[Healthchecks.io — dead-mans-switch для weekly cron]] — внешний сторож
- structlog → JSON в `logs/run-YYYY-WNN.log` с ротацией
- `runs` таблица — internal status; healthchecks pings `/start` `/success` `/fail`
- Алерты в [[Два Telegram чата — ops и business]] (ops-чат)

## Setup на чистом VPS

1. `apt install python3.12 git`
2. `curl -LsSf https://astral.sh/uv/install.sh | sh`
3. `git clone … && cd ga_crawler && uv sync`
4. `playwright install chromium` (если выбран Tier 1+)
5. `cp .env.example .env` → заполнить токены
6. Crontab + Healthchecks URL
7. Запустить deliberate-failure тест

См. также: `.planning/research/STACK.md` (раздел Hosting)
