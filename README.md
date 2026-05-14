## Что это

Еженедельный краулер ассортимента и цен goldapple.kz vs viled.kz для коммерческой команды viled.kz.

- **Что делает:** парсит каталоги обоих ритейлеров, сопоставляет товары по нормализованному ключу `brand + название + объём`, считает дельты цен и собирает Excel-отчёт.
- **Что доставляет:** раз в неделю Telegram-бот шлёт текстовую сводку + Excel-вложение в business chat команды viled.kz.
- **Когда:** ночь воскресенья (Sunday 23:00 Asia/Almaty) → отчёт утром понедельника.
- **Кому:** pricing-менеджерам viled.kz — для корректировки цен, поиска ассортиментных разрывов и мониторинга промо-акций конкурента.

## VPS setup from-scratch

Целевая платформа: **Ubuntu 24.04 LTS** на Hetzner CX22 (Falkenstein/Helsinki, EU; 2 vCPU / 4 GB / 40 GB SSD). Шаги выполняются **строго в указанном порядке** — пользователь `ga_crawler` обязан существовать до первого запуска logrotate (Pitfall #5) и до Camoufox cache (Pitfall #6, `$HOME` создаётся через `install -d`, см. шаг 2).

```bash
# 1. OS deps (cron + logrotate входят в base, но фиксируем явно).
sudo apt update && sudo apt install -y curl sqlite3 logrotate cron git

# 2. System user (Pitfall #5 — ОБЯЗАТЕЛЬНО до logrotate cp ниже).
#    БЕЗ -m: иначе useradd создаёт /opt/ga_crawler и копирует туда /etc/skel
#    (.bashrc/.profile/.bash_logout), после чего git clone падает с
#    "destination path already exists and is not an empty directory".
#    $HOME создаём отдельно через install -d с правильным owner/mode (Pitfall #6 —
#    Camoufox cache требует $HOME существующим и принадлежащим ga_crawler).
sudo useradd -r -d /opt/ga_crawler -s /bin/bash ga_crawler
sudo install -d -o ga_crawler -g ga_crawler -m 0755 /opt/ga_crawler

# 3. uv (Astral) под пользователем ga_crawler.
sudo -u ga_crawler bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'

# 4. Клонирование репо + sync deps + Playwright/Firefox binary.
#    /opt/ga_crawler уже создан (шаг 2) и пуст — git clone в пустой существующий dir
#    разрешён. uv вызываем по абсолютному пути: sudo НЕ наследует ~/.local/bin
#    через secure_path в /etc/sudoers, а ~/.bashrc не читается non-login shell'ом.
sudo -u ga_crawler git clone <repo-url> /opt/ga_crawler
cd /opt/ga_crawler
sudo -u ga_crawler /opt/ga_crawler/.local/bin/uv sync
sudo -u ga_crawler /opt/ga_crawler/.local/bin/uv run playwright install firefox

# 5. Лог-директория (owned by ga_crawler — logrotate `create 0644 ga_crawler ga_crawler`).
sudo install -d -o ga_crawler -g ga_crawler -m 0755 /var/log/ga_crawler

# 6. Deploy cron + logrotate (Pitfall #1 — имена БЕЗ точек, иначе Vixie cron игнорирует).
sudo cp deploy/etc-cron-d-ga_crawler /etc/cron.d/ga_crawler
sudo chown root:root /etc/cron.d/ga_crawler && sudo chmod 0644 /etc/cron.d/ga_crawler
sudo cp deploy/etc-logrotate-d-ga_crawler /etc/logrotate.d/ga_crawler
sudo chown root:root /etc/logrotate.d/ga_crawler && sudo chmod 0644 /etc/logrotate.d/ga_crawler
sudo systemctl reload cron

# 7. Секреты в .env (см. §3 — заполнить значениями из §5 и §6).
sudo -u ga_crawler cp .env.example .env
sudo -u ga_crawler chmod 0600 .env   # T-07-08 mitigation — read+write только владельцу
sudo -u ga_crawler nano .env         # заполнить TG_BOT_TOKEN / TG_BUSINESS_CHAT_ID / TG_OPS_CHAT_ID / HC_PING_URL

# 8. Smoke test (SC#1) — viled-only mini run; ожидается exit 0 + HC /start + /success.
sudo -u ga_crawler /opt/ga_crawler/bin/weekly-run.sh --viled-only --sanity-gate-n 1
```

После шага 8 проверь, что в Telegram business chat пришёл mini-отчёт, а в HC dashboard зафиксированы `/start` и `/success` пинги.

## ENV vars

Четыре обязательных ENV. Все попадают через `.env` (см. `.env.example`); bash wrapper `bin/weekly-run.sh` загружает их через `set -a; source .env; set +a` и **отказывается стартовать** при отсутствии критичных.

| ENV | Required | Источник | Notes |
|-----|----------|----------|-------|
| `TG_BOT_TOKEN` | YES | `@BotFather` → `/newbot` | Отсутствие при `deliver-run --run-id N` (standalone) → exit **3**. В weekly-run пути НЕ валидируется wrapper'ом — Python child degrade'ит delivery (exit 0 или 2). |
| `TG_BUSINESS_CHAT_ID` | YES | `@userinfobot` в business chat | Отсутствие → degrade в ops-only с reason `missing_env_TG_BUSINESS_CHAT_ID` (D-611) |
| `TG_OPS_CHAT_ID` | YES | `@userinfobot` в ops chat | Отсутствие при ops-only route в `deliver-run` → exit **3**. В weekly-run пути не валидируется wrapper'ом. |
| `HC_PING_URL` | YES | https://healthchecks.io (см. §5) | Wrapper exits **4** если отсутствует (D-703 fail-loud) |

Опциональные CLI-флаги (override sanity gates per run): `--sanity-gate-n N`, `--sanity-gate-m M`, `--sanity-gate-p P`.

Указатель: `cp .env.example .env && chmod 0600 .env`.

### Reserved exit codes

Wrapper `bin/weekly-run.sh` сам валидирует только `HC_PING_URL` (exit 4) и flock (exit 5); все остальные коды — passthrough от Python child'a (`weekly-run` ИЛИ standalone `deliver-run`).

| Exit | Источник | Значение |
|------|----------|----------|
| `0` | weekly-run / deliver-run | Production success — delivered ИЛИ skipped-idempotent |
| `2` | weekly-run | Run не достиг success — sanity-N/M/P gate trip, reporter failure, ИЛИ undelivered Telegram. Disambiguate через `sqlite3 prices.db 'SELECT reason FROM runs WHERE run_id=N'`. |
| `3` | **only** deliver-run (standalone) | Missing `TG_BOT_TOKEN` / `TG_OPS_CHAT_ID` на ops-only route (`skipped_no_credentials`). НЕ возникает в weekly-run cron-пути. |
| `4` | wrapper | Missing `HC_PING_URL` (Phase 7 D-703 fail-loud — «без мониторинга мы не запускаемся») |
| `5` | wrapper | Другой инстанс `weekly-run.sh` держит flock на `/var/lock/ga_crawler-weekly.lock` (Phase 7 D-709 / Pitfall #3) |

Pitfall #4: значения ENV должны быть **single-line, без `#` в значении, без quotes** — bash `source` и `python-dotenv` парсят чуть по-разному; формат `KEY=value` без украшений безопасен для обоих.

## Cron entry

Содержимое `/etc/cron.d/ga_crawler` (verbatim-копия `deploy/etc-cron-d-ga_crawler`):

```
CRON_TZ=Asia/Almaty
MAILTO=""
0 23 * * 0 ga_crawler /opt/ga_crawler/bin/weekly-run.sh
0 1  * * * ga_crawler /opt/ga_crawler/bin/backup.sh
```

**SCHED-02 invariant:** `CRON_TZ=Asia/Almaty` обязателен. Без него system cron работает в UTC → Sunday 23:00 Almaty = Sunday 18:00 UTC → отчёт уйдёт **за 5 часов до желаемого окна**. С `CRON_TZ` область действия scope-limited к этому файлу [VERIFIED: `crontab(5)`].

**MAILTO=""** — пустая строка отключает cron email leak (T-07-01 Information Disclosure mitigation; см. Pitfall #2 в комментах `deploy/etc-cron-d-ga_crawler`).

Daily 01:00 backup row активирует `bin/backup.sh` (Plan 02-06; 4-rotate retention, `/opt/ga_crawler/backups/*.db`).

## Healthchecks.io setup

Healthchecks.io используется как **dead-man's switch** для еженедельного run (Phase 7 SCHED-03 / D-703). Бесплатный tier ≤ 20 checks покрывает наш кейс.

1. Регистрация на https://healthchecks.io.
2. **My Checks → Add Check** → name `ga_crawler weekly`.
3. **Pings → Show URL** — скопировать ping URL формата `https://hc-ping.com/<uuid>`.
4. **Settings → Schedule** → Type `Cron` → expression `0 23 * * 0` → timezone `Asia/Almaty` → grace period `2h` (верхняя граница 4h run + buffer — см. D-703).
5. **Integrations → Telegram** → invite `@my_hc_bot` в тот же чат, что и `TG_OPS_CHAT_ID` (консолидация ops signals в один канал — CONTEXT.md Open Q #1) → `/start@my_hc_bot` для активации → confirm link.
6. Записать URL в `.env` как `HC_PING_URL=https://hc-ping.com/<uuid>`.

**Pitfall #7:** Telegram alert от HC.io по умолчанию показывает только `status + check name`. Чтобы увидеть `exit code` из POST body (wrapper пингует `/fail` с `--data-raw "exit=$EXIT"`) — кликни ссылку HC dashboard прямо из alert. На free tier custom alert templates недоступны.

## Telegram bot setup

Бот для **delivery** (отдельный от `@my_hc_bot`):

1. `@BotFather` → `/newbot` → name → username → получить token. Записать в `.env` как `TG_BOT_TOKEN`.
2. Добавить бота в **business chat** (куда летит еженедельный отчёт) как admin. Опционально: `/setprivacy Disable` через BotFather, если бот должен видеть все сообщения чата.
3. Добавить того же бота в **ops chat** (отдельный — алерты, не отчёты) как admin.
4. Получить `chat_id` обоих чатов: добавь `@userinfobot` в чат → он напечатает `Chat ID`. Записать как `TG_BUSINESS_CHAT_ID` и `TG_OPS_CHAT_ID`.
5. (Опционально, рекомендовано) инвайтнуть `@my_hc_bot` в тот же ops chat → один канал для всех ops signals (HC alerts + bot ops alerts).

## Deliberate-failure test

Тест **SC#5 end-to-end** — запускается **ВРУЧНУЮ** после deploy и после major code changes (НЕ в cron):

```bash
sudo -u ga_crawler /opt/ga_crawler/bin/test-failure-alert.sh
```

Скрипт (`bin/test-failure-alert.sh`, Plan 07-03; реализация D-706):

1. Запускает `bin/weekly-run.sh --viled-only --sanity-gate-n 999999` → viled crawl собирает ~120 SKUs → sanity-N gate trips на `120 < 999999` → `runs.status='failed'` с reason `sanity_gate_n_failed:120<999999`. Wrapper пингует HC `/fail` с body `exit=2`.
2. Извлекает `run_id` из последнего `/var/log/ga_crawler/weekly-run-$(date +%F).log`.
3. Вызывает `deliver-run --run-id $RID` напрямую → gate trips на `read_run_status='failed'` → `route=ops_only` → ops chat получает alert.
4. Печатает operator verification checklist:
   - [ ] Telegram **ops chat**: alert message с reason `upstream pipeline failed` для run #N
   - [ ] Telegram **business chat**: ни одного нового message
   - [ ] **Healthchecks.io dashboard**: `/start` + `/fail` pings залогированы
   - [ ] **DB `runs`**: `failed | sanity_gate_n_failed:120<999999`
   - [ ] **DB `stats.deliver`**: `delivered_ops_only`

Runtime ~2–3 минуты. Если какой-либо пункт checklist'а fails — см. §8 Operations runbook.

**Note:** Тест пингует **реальный** HC.io endpoint (`/start` + `/fail`) — это expected behaviour. Помечай соответствующий alert в HC UI как `expected` чтобы не путать с production incident.

## Operations runbook

Recovery-рецепты для типичных incident'ов (CLI subcommands — Phase 4..6 standalone surface):

### `undelivered_telegram_unreachable` после weekly run

Telegram API был временно недоступен; xlsx остался на диске (`reports/YYYY-WNN.xlsx`; Phase 6 D-605 invariant — НИКОГДА не удаляем pending xlsx). Повторная доставка:

```bash
sudo -u ga_crawler /opt/ga_crawler/.venv/bin/python -m ga_crawler deliver-run --run-id N
```

### Reporter bug — нужно перегенерировать xlsx

```bash
sudo -u ga_crawler /opt/ga_crawler/.venv/bin/python -m ga_crawler report-run --run-id N
```

Plan 05-05 D-509 standalone recovery — НЕ делает re-crawl, читает из БД и пересобирает xlsx.

### Matcher bug — нужно re-match

```bash
sudo -u ga_crawler /opt/ga_crawler/.venv/bin/python -m ga_crawler matcher-run --run-id N --sanity-gate-p P
```

Plan 04-05 D-412 standalone recovery; idempotent `DELETE + INSERT` per `run_id` — безопасно гонять повторно.

### Recovery БД из бэкапа

```bash
sudo systemctl disable cron --now   # остановить scheduler
sudo -u ga_crawler cp /opt/ga_crawler/backups/YYYY-MM-DD.db /opt/ga_crawler/prices.db.restored
# verify content (sqlite3 ... '.tables', '.schema'), затем swap файлов и re-enable cron
sudo systemctl enable cron --now
```

Backups: `/opt/ga_crawler/backups/*.db` — 4-rotate retention (Plan 02-06).

### Проверить статус последних 5 runs

```bash
sudo -u ga_crawler sqlite3 /opt/ga_crawler/prices.db \
  'SELECT run_id, status, reason, started_at FROM runs ORDER BY run_id DESC LIMIT 5'
```

## Логи

**Location:** `/var/log/ga_crawler/weekly-run-YYYY-MM-DD.log[.gz]` (datestamped per run; `bin/weekly-run.sh` шаг 5 редиректит stdout+stderr).

**Rotation:** `/etc/logrotate.d/ga_crawler` (источник — `deploy/etc-logrotate-d-ga_crawler`):

- `weekly` + `rotate 13` → история **13 недель (~3 месяца)**.
- `compress` + `delaycompress` → `.gz` появляется только со 2-й ротации.
- `missingok` + `notifempty` → 0-byte logs НЕ ротируются.
- `create 0644 ga_crawler ga_crawler` → новые файлы owned by системным пользователем (Pitfall #5 — пользователь обязан существовать ДО первой ротации).

Дисковый бюджет: Hetzner CX22 40GB → ~5MB/run gzipped × 13 = ~65MB total (negligible).

### Grep / jq примеры

```bash
# Tail последнего run, все events:
# grep '^{' отфильтровывает non-JSON строки (uv install msgs, Camoufox/Firefox stderr,
# Python tracebacks) — jq strict-mode упал бы на первой такой строке и закрыл stream.
tail -f /var/log/ga_crawler/weekly-run-$(date +%F).log | grep --line-buffered -E '^\{' | jq .

# Все errors последнего run:
grep '"level":"error"' /var/log/ga_crawler/weekly-run-$(date +%F).log | jq .

# История по run_id (включая gzipped archives):
# -h обязателен: при multi-file match zgrep по умолчанию префиксит каждую строку
# "filename:" → jq падает на parse error и теряет весь stream.
zgrep -h '"run_id":42' /var/log/ga_crawler/*.log.gz | jq .

# Phase-level inspection (например только goldapple):
grep '"phase":"goldapple"' /var/log/ga_crawler/weekly-run-$(date +%F).log | jq .
```

### Edge cases

- `.log.gz` archives появятся со 2-й недели (notifempty + delaycompress) — week 1's log ротируется первым Sunday после создания.
- 0-byte logs не ротируются (`notifempty`) — намеренно (нечего архивировать).
- Если weekly run extends past Monday 06:25 UTC (когда `/etc/cron.daily/logrotate` запускается на Hetzner EU) → wrapper может писать в rotated inode → bytes окажутся в `.log.1` (RESEARCH §Open Q #3 — acceptable edge для weekly batch; T-07-05 `accept`).

## Live HTML harness

Phase 9 harness фиксирует Phase 8 parser-fix ретроактивно: ловит fixture-vs-live drift в parser shape (тип run #13 — Givenchy frozen fixture green, но STEREOTYPE/Armani/Contre-Jour shapes выдали null volume в проде). **D-905: operator-only opt-in, НЕ в cron.**

### Когда запускать

- **Pre-deploy** (после parser changes / SDK bump): убедиться что текущие Phase 8 fixtures parse без regression.
- **Post-suspected-drift**: если weekly run #N показал низкий match-rate / NULL-rate spike — refresh live cassettes и сравнить с frozen.
- **По запросу operator**: при routine quarterly check goldapple/viled HTML shape.

### Cassette-replay (быстро, no network)

```bash
uv run pytest -m live -x
```

Парсит 3 frozen `_live-2026-05-13-*.html` fixtures, assert'ит brand / name / volume_raw invariants. ~10s wallclock. Не обращается ни к Camoufox, ни к curl_cffi.

### Refresh (operator-only, hits Camoufox + curl_cffi)

```bash
uv run pytest -m live --refresh-live -x
```

Re-fetches SMOKE_URLs через Camoufox 0.4.11 (goldapple) и curl_cffi (viled). HTML нормализуется (strip cf_clearance / csrf-token / CSS build-hash / `__NEXT_DATA__.buildId`) перед syrupy diff vs frozen fixture. ~30+ s wallclock.

Если drift detected → syrupy fails + пишет `.planning/research/parser-drift-YYYY-MM-DD.md` с per-fixture per-assertion verdict.

### Принять drift (overwrite fixture)

```bash
uv run pytest -m live --refresh-live --snapshot-update -x
```

Перезаписывает `tests/fixtures/<retailer>/_live-YYYY-MM-DD-<slug>.html` + регенерирует sidecar JSON `{date, url, status, html_size, title, camoufox_version}`.

### Capture новой fixture (для нового brand-shape)

```bash
uv run python -m ga_crawler capture-fixtures \
  --retailer goldapple \
  --url https://goldapple.kz/<sku-id>-<slug> \
  --slug short-slug-here
```

Записывает `tests/fixtures/goldapple/_live-YYYY-MM-DD-<slug>.html` + сидекар JSON. **Auto-scrubs** cf_clearance / bot tokens / hc-ping paths перед записью (D-907 belt-and-suspenders). PII canary в `tests/test_live_fixtures_pii_canary.py` остаётся как safety net.

Для viled:

```bash
uv run python -m ga_crawler capture-fixtures \
  --retailer viled \
  --url https://viled.kz/<sku-id>-<slug> \
  --slug short-slug-here
```

### Stale-fixture warning (30 days)

Если sidecar `date` > 30 дней, pytest emits `UserWarning` (не fail). Считается напоминанием — operator решает refresh или нет.

### Что НЕ делает harness

- **Не запускается из cron** — D-905 explicit operator-only opt-in (избегаем blast radius на production stability).
- **Не пишет в business Telegram** — drift output только в `.planning/research/parser-drift-YYYY-MM-DD.md`.
- **Не правит parsers** — Phase 8 уже закрыт; harness только тестирует.

## Dev setup

```bash
git clone <repo> ga_crawler
cd ga_crawler
uv sync
uv run pytest -x
```

Архитектурные детали, декомпозиция по фазам и tech stack — см. `CLAUDE.md` в корне репо.
