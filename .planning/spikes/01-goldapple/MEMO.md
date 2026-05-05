# Spike 01: Goldapple Anti-Bot Decision Memo

**Sign-off:** _PENDING — заполнить дату + подпись после plan 01-11_
**Spike start:** _TBD_
**Spike end:** _TBD_

> Заполняется в plan 01-11 на основе всех findings 01-04..01-10.
> На завершении спайка копия дублируется в Obsidian `knowledge/decisions/` через `/gsd-spike --wrap-up`.

## TL;DR

> Однострочное summary: tier, engine, proxy, prod-IP recommendation.

- **Chosen tier:** _TBD (0 / 2 / 3 / 4)_
- **Browser engine:** _TBD (curl_cffi only / vanilla Playwright / Patchright / Camoufox)_
- **Proxy provider:** _TBD (none / IPRoyal residential / Decodo / managed unblocker)_
- **Production IP recommendation (Phase 7):** _TBD_

## Problem

Goldapple.kz anti-bot tier — defining unknown проекта (см. research/SUMMARY.md, research/PITFALLS.md). Phase 3 stack гейтится этим решением.

## Options tested

| Tier | Engine | Proxy | Result | Notes |
|------|--------|-------|--------|-------|
| _TBD_ | _TBD_ | _TBD_ | _TBD/100 fetches, X challenges_ | _TBD_ |

## Chosen

**Tier:** _TBD_
**Rationale:** _TBD_
**Exact 100-fetch results:**
- KZ-laptop (D-06): _N/100, X challenges_
- EU/RU residential (D-05): _N/100, X challenges_

## JSON-endpoint hunt verdict (D-09, D-10)

_TBD — found / not found. Если found: какие эндпоинты, как используются, влияет на сценарий Tier 0._

## Page-volume estimate (RECON-03)

_TBD — products per typical brand, source: sitemap.xml / pagination meta._

## viled.kz feasibility (RECON-02)

_TBD — N/10 successful curl_cffi fetches, JSON-LD presence, timing._

## robots/ToS audit summary (RECON-04)

_См. tos-audit.md. Committed rate-limits:_
- viled.kz: _TBD_
- goldapple.kz: _TBD_

## Next-step impact

- **Phase 3 stack:** _TBD_
- **Phase 7 hosting / prod-IP:** _TBD_

## Open risks

- _TBD_

## Appendix: Challenge-rate (D-15)

_TBD — если challenge-rate >20%, tier помечается "fragile" даже на технически-passing._
