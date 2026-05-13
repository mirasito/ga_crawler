---
tags: [session, milestone-open, v1-1-opened, live-run-discovery, parser-bugs, github-push, yandex-cloud, gsd-new-milestone]
date: 2026-05-13
phase: v1.1-planning
milestone: v1.1
session_type: milestone-open
commits: 5
---

# 2026-05-13 — live-run #13 vskrыl 3 парсер-бага, v1.1 milestone открыт через /gsd-new-milestone

Огромная сессия. Полная цепочка: GitHub push → Yandex Cloud KZ инструкция → локальный полный crawl на Windows → обнаружили 3 prod-бага парсеров → диагностический xlsx в Telegram → открыли v1.1 milestone через полный `/gsd-new-milestone` workflow (4 research-агента parallel + synthesizer + requirements + roadmapper) → запланировали 4 фазы (8-11) с 24 reqs.

## Что было сделано

### 1. GitHub repo + push

Пользователь создал https://github.com/mirasito/ga_crawler. Я добавил remote, запушил `master` ветку и тег `v1.0`. Готово для clone на VPS.

### 2. Yandex Cloud KZ инструкция

Пользователь спросил про VPS в Яндекс.Облако вместо Hetzner. Дал альтернативную пошаговую инструкцию (yandex.cloud/kz, kz1-a zone, Ubuntu 24.04). Шаги 4.1-4.7 настройки идентичны Hetzner после SSH-входа. Cost: ~₸6800/мес vs Hetzner €4.50.

### 3. Telegram bot setup (live, в чате с пользователем)

Пользователь прислал `TG_BOT_TOKEN` для `@gacrawler_bot`. Через `getMe` API подтвердил живость. `getUpdates` сначала был пустой (бот не получал сообщений), пользователь нажал `/start`. Получил `chat_id=986299192` (private). Создал `.env` с токеном + chat_id (тот же для business и ops). Тестовое сообщение msg_id=10 доставлено.

### 4. Полный crawl run #11 → #12 → #13

Запустил `weekly-run` через `uv run python -m ga_crawler weekly-run` (минуя bash wrapper — Windows):

- **#11 (sanity-gate-n=100 default)**: упал на viled 82 < 100. Known v1 limitation (SSR pagination).
- **#12 (--sanity-gate-n 1)**: упал на goldapple 89 < M=1000. Camoufox прошёл antibot **успешно** на Windows.
- **#13 (--sanity-gate-n 1 --sanity-gate-m 1 --sanity-gate-p 0)**: дошёл до конца, `status=success`. ~18 мин total. xlsx сгенерирован. **НО** delivery = `skipped_no_credentials, last_error=missing_env_TG_BOT_TOKEN` — Python не подцепил `.env`.

Manual `deliver-run --run-id 13` с явным `export TG_BOT_TOKEN=...` → доставка успешная, msg_id=11.

### 5. Пустой xlsx — обнаружили 3 prod-бага парсеров

Пользователь открыл xlsx и сказал "пустой, нет товаров". Проверил БД: 82 viled + 88 goldapple persisted нормально, но `match.goldapple_comparable_count=0`. Reporter показывает только matched pairs → empty xlsx.

Diagnostics:

| Bug | Что |
|---|---|
| **#1 goldapple volume** | 0/88 SKU имеют `volume_norm` — парсер не находит volume tag. Live PDP screenshot пользователя (`STEREOTYPE sago`) показал `78 ОБЪЁМ / МЛ` в **structured flexbox-блоке**, не в title и не в microdata `itemprop="size"`. |
| **#2 goldapple brand/name** | brand+name склеены в title: `Armaniarmani code`, `STEREOTYPE sago`. Парсер читает `<h1>` вербатим. Решение: читать sibling `<meta itemprop="name">` микроразметку. |
| **#3 viled volume** | `volume_raw = name целиком`, regex по name только если "100 мл" есть явно. Решение: читать `props.pageProps.attributes[].name == "Размер"` из `__NEXT_DATA__`. |

Создал `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` с evidence (DB samples + screenshot цитата). Собрал diagnostic xlsx с raw данными через `scripts/diagnostic_xlsx.py` (новый артефакт) и доставил пользователю как msg_id=12.

### 6. `/gsd-new-milestone` полный workflow

Полная цепочка по `workflows/new-milestone.md`:

1. **Verify milestone understanding** (AskUserQuestion) → "Looks good"
2. **PROJECT.md update** — Current Milestone v1.1 секция + 6 active reqs
3. **STATE.md** через `gsd-tools state milestone-switch --milestone v1.1` → status: planning, total_phases reset
4. **phases.clear --confirm** → 7 v1.0 фаз удалены (архивированы в milestones/v1.0-*)
5. **Commit `393be5c`**: milestone start
6. **Research decision** (AskUserQuestion) → "Research first" (несмотря на bug-fix nature)
7. **4 параллельных gsd-project-researcher агента** (sonnet model): STACK, FEATURES, ARCHITECTURE, PITFALLS
8. **gsd-research-synthesizer** → SUMMARY.md (синтезатор контент вернул в чат, я сохранил руками)
9. **Commit `7aaa972`**: 4 research files + SUMMARY + archive v1.0 versions
10. **AskUserQuestion gates** для open decisions:
    - **Yandex Cloud kz1** (NOT Hetzner) — пользователь выбрал KZ-IP
    - **B4/B5 → P2 cheap-bundle** в Phase 9
11. **REQUIREMENTS.md** — 24 reqs в 4 buckets (PARSE-FIX × 5, TEST-HARNESS × 6, AUDIT-DEBT × 5, DEPLOY × 8)
12. **Commit `6235cad`**: REQUIREMENTS.md
13. **gsd-roadmapper** → ROADMAP.md (Phases 8-11) + traceability filled + STATE updated
14. **Approval gate** → "Approve"
15. **Commit `0477cda`**: ROADMAP + STATE + REQUIREMENTS traceability

## Решения (lock'нутые в roadmap)

- **Deploy target: Yandex Cloud kz1** — пользователь выбрал KZ-IP над Hetzner EU. Cost ~₸6800/мес vs €4.50, но goldapple anti-bot чище от KZ. Phase 11 включает DEPLOY-05 Camoufox×Yandex compat smoke + DEPLOY-06 egress smoke перед cron handoff.
- **selectolax 0.3 → 0.4** upgrade — Lexbor backend с `:lexbor-contains("ОБЪЁМ" i)` решает Bug #1 (drop-in, Modest backend остаётся)
- **syrupy 4.7** dev-only — HTML snapshot harness (rejected pytest-recording/VCR.py — оба hook'ают urllib3 которое curl_cffi и Camoufox bypass'ят)
- **Camoufox 0.4.11 LOCKED** (Phase 3 D-313)
- **Forward-only** — не backfill runs 1-13 (HTML gone, matcher idempotent выдаст те же 0 matches, auto-suggest 4-week median roll-off naturally)
- **B4/B5 = P2 cheap-bundle** — bundle в Phase 9 если быстро лендит, иначе defer to v1.2

## Critical learnings

### `.env` не подхватывается Python автоматически (D-705 recurrence)

`bin/weekly-run.sh` использует `set -a; source .env; set +a` — но прямой запуск Python через `uv run python -m ga_crawler weekly-run` пропускает этот шаг. Run #13 `delivery_status=skipped_no_credentials` хотя `.env` существует и заполнен. **Fix wired в Phase 11 DEPLOY-03**: `load_dotenv(verbose=True)` at `src/ga_crawler/__main__.py` entrypoint.

### Frozen fixtures маскируют live drift

v1.0 audit verdict был `tech_debt` (paperwork only) — 803 unit-теста all green на fixtures captured 5-11 мая. Live runs 13 мая показали HTML drift: brand `STEREOTYPE` (CAPS), unbeaten brand+name pattern Armani, новая структура volume block. **Critical methodology gap**: unit tests на frozen fixtures не достаточны. Phase 9 ставит syrupy harness + Pydantic write-boundary validation как защиту.

### Synthesizer/Researcher subagents с sandbox блокировкой

`gsd-project-researcher` для ARCHITECTURE и `gsd-research-synthesizer` оба отказались писать `.md` файлы из-за внутренних system reminders ("Do NOT Write report/summary/findings/analysis .md files"). Вернули контент в текст. Я сохранил руками. **Pattern**: ожидать что subagents возвращают контент в response, не на диск; orchestrator должен персистить.

### Camoufox работает на Windows

Не очевидно было до live-run #12 что Camoufox 0.4.11 запустится на Windows 11 без проблем. **Verified empirically**: Camoufox прошёл goldapple antibot, 89 SKU спарсилось, 0 блокировок. Снимает риск что local dev на Windows невозможен.

## Commits

1. **`393be5c`** docs: start milestone v1.1
2. **`7aaa972`** docs(research): v1.1 4-dimension research + SUMMARY
3. **`6235cad`** docs: define milestone v1.1 requirements (24/24)
4. **`0477cda`** docs: create milestone v1.1 roadmap (4 phases)
5. **PRIOR (this session)**: github push (master + tag v1.0)

## Status post-session

- v1.1 milestone **OPEN** — phases 8-11 planned, не started
- Phase 8 next via `/gsd-discuss-phase 8` (рекомендуется) или `/gsd-plan-phase 8`
- v1.0 архивированный, всё ещё на `tech_debt` verdict — Phase 10 закроет это
- Operator deploy на Yandex Cloud kz1 заплпнирован Phase 11 (last)

## Related

- [[Текущие приоритеты — v1.1 milestone открыт, Phase 8 parser fix next]] (new)
- [[Goldapple PDP renders volume в structured flexbox blok, не в microdata]] (new decision)
- [[viled volume — в attributes Размер JSON-поле, не в name]] (new decision)
- [[Yandex Cloud kz1 over Hetzner EU для KZ-IP anti-bot]] (new decision)
- [[Forward-only no backfill runs 1-13]] (new decision)
- [[`.env` не подхватывается Python при прямом uv run — D-705 recurrence]] (new debugging)
- [[2026-05-13 — operator boundaries re-confirmed, deploy остаётся за человеком]] (предыдущая)
- `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` — full evidence
- `.planning/research/SUMMARY.md` — convergent synthesis
- `.planning/ROADMAP.md` § v1.1 Active — 4 phases expanded
