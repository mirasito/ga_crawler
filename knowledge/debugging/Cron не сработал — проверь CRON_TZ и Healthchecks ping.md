---
tags: [debugging, ops, cron, schedule]
date: 2026-05-05
---

# Cron не сработал — проверь CRON_TZ и Healthchecks ping

## Симптом

- Понедельник, отчёта в business-чат нет
- Алертов в ops-чат тоже нет (или они были, но прошли мимо)

## Чек-лист

1. **Healthchecks alert пришёл?**
   - Если да — cron запустился, но фаза упала. Смотри `runs.failure_reason`
   - Если нет — cron вообще не сработал

2. **TZ корректен?**
   ```bash
   crontab -l   # должно быть CRON_TZ=Asia/Almaty в начале
   ```
   Без `CRON_TZ` server дефолтит в UTC → запуск 00:00 UTC = 05:00 Almaty (не "ночь воскресенья")

3. **Cron daemon запущен?**
   ```bash
   systemctl status cron
   journalctl -u cron --since "1 day ago"
   ```

4. **VPS живой?**
   - Hetzner console / ping / SSH

5. **Permissions / venv путь корректен?**
   ```bash
   sudo -u <user> /opt/ga_crawler/.venv/bin/python -m ga_crawler --dry-run
   ```

## Глубже

Логи cron на Ubuntu: `/var/log/syslog` — `grep CRON`.

## Превентивно

[[Healthchecks.io — dead-mans-switch для weekly cron]] **обязан** быть настроен **до** scheduling. Без него — пропуск запуска заметишь только когда кто-то спросит "где отчёт".

## Связанные

- [[Деплой — Hetzner CX22 + system cron в Asia Almaty]]
- [[Healthchecks.io — dead-mans-switch для weekly cron]]
