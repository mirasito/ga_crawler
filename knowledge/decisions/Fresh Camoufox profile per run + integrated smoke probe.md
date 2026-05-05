---
tags: [decision, phase-3, camoufox, anti-bot, lifecycle, smoke-test]
date: 2026-05-06
phase: 3
decisions: [D-311, D-312, D-313]
---

# Fresh Camoufox profile per run + integrated smoke probe

Phase 3 запускает Camoufox на **fresh profile dir** каждую неделю (tmp dir, сносится после run), с **integrated smoke probe ПЕРЕД** crawl-фазой, и **pin exact version** `camoufox==135.0.1.beta24` в uv.lock.

## Почему fresh, не persistent

Спайк 01-08 валидировал **99/100 на ХОЛОДНОМ старте** — warm cookies между weekly runs не нужны для gate-pass. Persistent profile несёт три риска:

1. **Cookie expiry** — GroupIB / F.A.C.C.T. может ротировать gib-token-сессии на fraud-prevention частоте (часы/дни, не недели)
2. **Fingerprint drift** — после Camoufox/Firefox upgrade fingerprint hash меняется, кэшированный профиль перестаёт совпадать
3. **Profile bloat** — кэш, history, cookies растут unbounded

Fresh profile = +30с boot warmup на каждый run (приемлемо в ~4.4ч общем wall-clock).

## Smoke probe ПЕРЕД crawl

После Camoufox-boot на fresh profile, **до full crawl**:
1. Phase 3 пробует 1-3 known-good URLs из config (`smoke_urls`).
2. Pass-критерий: все probe-URLs возвращают 200 + microdata-price extracted.
3. Fail → `runs.status='failed'`, ops-Telegram с диагностикой (Camoufox version, response-bytes, gate-shell title).

**Зачем:** ловит fingerprint-regression (Camoufox upgrade сломал spoof) ДО того как 4ч беспоsлезных fetches уйдут в shell-responses. Spike-skill recommendation «weekly Camoufox-vs-goldapple smoke» удовлетворяется этим integrated-механизмом — отдельный midweek cron не нужен.

## Pin exact version

`camoufox==135.0.1.beta24` (или эквивалентная PyPI-версия). Manual upgrade workflow:
1. Operator в dev запускает goldapple-smoke на новой версии.
2. Pass → PR в `uv.lock`.
3. coryking/camoufox fork как drop-in backup если daijro upstream stalls.

**Защищает:** spike-validation остаётся правдивой. Fingerprint hash меняется на каждом patch (Camoufox = C++-level spoof) — auto-patch updates могут свалить gate без предупреждения.

## Что отвергнуто

- **Persistent profile dir между runs** — недоказанная польза, доказанные риски
- **Adaptive lifecycle** (persist + wipe on smoke-fail) — переосложнение для v1, никто не валидировал warm-savings
- **Latest stable Camoufox без pin** — фейл случится в воскресенье ночью

## Связанные

- [[Camoufox а не Patchright — engine для goldapple]] — engine choice
- [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]] — spike sign-off
- [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]] — vendor контекст
- [[Тиры anti-bot эскалации]] — pattern parent
- [[Sitemap-only URL pool для goldapple, без brand-facet rendering]] — что smoke probe защищает
- `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` §Camoufox profile lifecycle — D-311, D-312, D-313
- `.claude/skills/spike-01-goldapple/SKILL.md` §Production monitoring — weekly smoke playbook
