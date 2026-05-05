---
tags: [priorities, current-focus, phase-1, closed]
date: 2026-05-06
---

# Текущие приоритеты — Phase 1 спайк CLOSED ✓

**Phase 1 закрыта 2026-05-06**, sign-off MEMO + Obsidian decision-нота + project skill + STATE update — всё на месте. Spike прошёл за 2 дня из 1-недельного timebox (D-02). Tier-вердикт получен decisively.

→ Дальше: см. [[Текущие приоритеты — Phase 2 viled]] (создаётся по `/gsd-discuss-phase 2`) или [[Текущие приоритеты — Phase 3 goldapple]] (по `/gsd-discuss-phase 3`).

## Финальный вердикт Phase 1

| Поле | Значение |
|---|---|
| **Chosen tier** | 2 |
| **Browser engine** | Camoufox v135.0.1-beta.24 (Firefox + C++ fingerprint spoof) |
| **Proxy** | none (KZ-laptop direct) |
| **Production IP (Phase 7)** | Hetzner CX22 EU + smoke gate; IPRoyal KZ как fallback |
| **100-fetch верификация** | 99/100 success, 0% gate-shell, NOT FRAGILE per D-15 |
| **goldapple parser** | `selectolax` + microdata `<meta itemprop="price">` (НЕ JSON-LD!) |
| **viled parser** | `curl_cffi` + `__NEXT_DATA__` JSON blob |
| **Phase 3 budget** | $0/week proxy baseline, ~5.5h/week sequential |
| **Sign-off** | mirdbek@gmail.com 2026-05-06 APPROVED |

## Что выполнено в этой сессии

| Plan | Что дало |
|---|---|
| 01-08 ✓ | Camoufox 100-fetch run: 99/100, 0% gate-shell. D-14 revised mid-spike (microdata not JSON-LD). |
| 01-11 ✓ | MEMO.md финализирован: TL;DR + Chosen + 12 секций, sign-off date. |
| 01-12 ✓ | Obsidian decision-note + project skill + STATE.md update |

## Что осталось из исходного плана и было SKIPPED (с явным rationale в MEMO)

- ❌ **01-03 IPRoyal trial** — D-08 cancelled, proxy не нужен (Camoufox без него работает 99/100)
- ❌ **01-09 EU-proxy multi-geo** — value-of-info ≈ 0 когда фингерпринт сам решает gate
- ❌ **01-10 Tier 3 escalation** — триггер не сработал (Tier 2 Camoufox PASS)

## Все Phase 1 plans (closed status)

| Plan | Status | Что дало |
|---|---|---|
| 01-01 ✓ | done | spike skeleton |
| 01-02 ✓ | done | uv project + curl_cffi + patchright + selectolax + chromium + camoufox |
| 01-03 ⏭ | SKIPPED | D-08 cancelled — see [[Camoufox а не Patchright — engine для goldapple]] |
| 01-04 ✓ | done | RECON-04: rate-limits committed (viled 2s, goldapple 3-5s random) |
| 01-05 ✓ | done | RECON-03 part 1: sitemap.xml plain-deliverable, 112k URLs, ~600 MB/week budget |
| 01-06 ✓ | done | JSON-endpoint hunt: Tier 0 dead for product data; vendor ID = GroupIB |
| 01-06b spike ✓ | side-spike | Camoufox 3/3 instantly — the big finding |
| 01-07 ✓ | done | RECON-02: viled 15/15 HTTP 200, `__NEXT_DATA__` extraction frozen |
| 01-08 ✓ | done | Camoufox 100-fetch 99/100, microdata extraction confirmed |
| 01-09 ⏭ | SKIPPED | multi-geo VOI ≈ 0 |
| 01-10 ⏭ | SKIPPED | Tier 3 trigger never fired |
| 01-11 ✓ | done | MEMO finalized + signed off |
| 01-12 ✓ | done | Obsidian + project skill + STATE close |

## Ключевые решения (Phase 1 sign-off)

- [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]] — финальный sign-off
- [[Camoufox а не Patchright — engine для goldapple]] — engine выбор
- [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]] — vendor ID
- [[Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом]] — но sitemap живой

## Superseded решения (audit trail)

- ~~[[Tier 2 Patchright — стартовый tier для goldapple]]~~ — superseded
- ~~[[Спайковый fetch-OK = HTML 200 плюс product JSON-LD]]~~ — D-14 revised: goldapple uses microdata, не JSON-LD

## Команда для следующего шага

```
/gsd-discuss-phase 2
```

(или `/gsd-discuss-phase 3` — Phase 2 и 3 независимы по data dependencies)

## Phase 7 backlog (не теряем)

- Camoufox+EU smoke fetch перед locking Hetzner — если регрессия → revive D-08 (IPRoyal KZ)
- KZ-legal review (30 min с юристом) с bundle = `tos-audit.md` + `viled-privacy.txt` + robots snapshots + GroupIB vendor flag
- Weekly Camoufox-vs-goldapple smoke (gate-shell rate >5% → alert)
- Camoufox upstream maintenance check (daijro vs coryking fork)
