---
tags: [decision, planning, p2-bundle, time-budget, mid-phase-checkpoint, v1-1, phase-9]
date: 2026-05-14
phase: 9-contexted
status: locked
---

# P2 bundle gate — time-budget 8h elapsed W0+W1 для GO/NO-GO checkpoint

## Утверждение

Phase 9 W2 (Plan 09-03) выполняет mid-phase budget-driven branch decision:

- **Измерение**: `elapsed = git commit timestamp(last GREEN commit in 09-02) - git commit timestamp(first RED commit in 09-01)`
- **Gate**: `elapsed < 8h` → **GO** = 09-03 ship'ит TEST-HARNESS-04 (brand-coverage quota canary) + TEST-HARNESS-05 (`python -m ga_crawler capture-fixtures` CLI subcommand)
- **Fallback**: `elapsed ≥ 8h` → **NO-GO** = 09-03 пишет defer-to-v1.2 doc cascade (REQUIREMENTS.md / STATE.md / ROADMAP.md обновляются с `TEST-HARNESS-04/05 → Deferred to v1.2`)
- **Override**: User может ручным аргументом переопределить решение в любую сторону (через CONTEXT-PATCH или explicit invocation flag)

## Reasoning

### 1. STATE.md locked decision требует "bundle if quick, else defer"

`.planning/STATE.md` locked decisions block: *"B4/B5 (TEST-HARNESS-04/05) = P2 cheap-bundle inside Phase 9 (try same milestone, else defer to v1.2)"*. REQUIREMENTS.md аналогично: *"P2 cheap-bundle — bundle if quick, else defer to v1.2"*. Это уже decided на milestone level. Phase 9 ОБЯЗАН реализовать GO/NO-GO checkpoint.

Открытый вопрос — **что значит "quick"**. Time-budget — most defensible operationalization.

### 2. 8h corresponds to "one day of work" mental anchor

Phase 8 (5-plan phase, similar scope shape) занял ~10 hours wall-clock (W0 spike 2h + W1 3 parallel plans ~3h + W2 doc cascade + verification ~5h). Phase 9 имеет 4 must-have reqs + 2 P2 reqs vs Phase 8's 5 reqs — comparable phase volume.

8h = «1 working day» — операторский mental anchor «если за день дошли до конца W1 — есть смысл попробовать P2 same-day; если нет — defer'им чтобы не растягивать phase до недели».

Это не precise estimate, но **objective criterion** который не зависит от subjective «implementation feels straightforward» — последнее склонно к рост scope creep'а.

### 3. Test-count delta — отвергнут как слабый proxy

Альтернатива была: `if W0+W1 added ≤ 12 tests → GO`. Это **слабый proxy** для сложности:

- TEST-HARNESS-06 (Pydantic boundary) может быть +3 tests но забрать 4 часа на storage module inspection + integration refactor
- TEST-HARNESS-03 (live drift test) может быть +8 tests за 1 час (просто wrappers вокруг существующих fixtures)
- Test count ≠ implementation complexity

Time-budget directly measures «have we used up daily focus budget» — что и есть intent.

### 4. Always GO / Always DEFER отвергнуты как inconsistent с STATE.md

- **Always GO** (P2 всегда bundle'ится): отменяет «P2 cheap-bundle» опцию из STATE.md locked decision — противоречие; пришлось бы перерисовывать REQUIREMENTS.md
- **Always DEFER** (P2 upfront в v1.2): сокращает Phase 9 до 4 reqs но теряет brand-coverage quota canary критичный для STEREOTYPE/Armani brand-drift detection; capture-fixtures CLI потребуется в Phase 11 operator workflow

Time-budget gate — preserves option value на mid-phase point.

### 5. User override allowed — explicit escape hatch

Не любая automation perfect. Может быть случай когда:
- 09-02 закончилось в 7h59min но имеет unfinished TODOs → user override на DEFER чтобы W2 stabilize а не bundle
- 09-02 закончилось в 8h05min но TH-04 это 30 min minor brand-coverage canary → user override на GO

CONTEXT-PATCH workflow (если будет needed) или explicit `/gsd-execute-phase 9 --plan 09-03 --p2-override go` flag — позволяют human-in-the-loop solve edge cases. Default automation — explicit time gate.

## Implication

- Plan 09-03 (W2 conditional) PLAN.md имеет **2 alternative task lists**:
  - **GO path** (default if `elapsed < 8h`): Wave 2 tasks ship TH-04 + TH-05 implementation + tests
  - **NO-GO path** (default if `elapsed ≥ 8h`): Wave 2 tasks edit REQUIREMENTS.md / STATE.md / ROADMAP.md to mark TH-04/05 as `Deferred to v1.2`, update PROJECT.md milestone status accordingly, commit doc cascade
- gsd-planner должен generate PLAN.md с conditional sections clearly demarcated (e.g., `## Tasks (GO path)` + `## Tasks (NO-GO path)`)
- gsd-executor читает git timestamp arithmetic перед picking section
- Override mechanism — minimal: user пишет в CONTEXT.md `<decisions>` блок overriding D-902 ИЛИ передаёт flag в execute invocation

## Measurement protocol

```bash
# At W1→W2 checkpoint (executed by 09-03 executor):
RED_COMMIT=$(git log --reverse --format="%H %ct" -- .planning/phases/09-live-html-harness/09-01-PLAN.md | head -1 | awk '{print $1}')
LAST_W1=$(git log --format="%H %ct" -- .planning/phases/09-live-html-harness/09-02-SUMMARY.md | head -1 | awk '{print $1}')

START_TS=$(git show -s --format=%ct "$RED_COMMIT")
END_TS=$(git show -s --format=%ct "$LAST_W1")
ELAPSED_SEC=$((END_TS - START_TS))
ELAPSED_HRS=$(echo "scale=2; $ELAPSED_SEC / 3600" | bc)

if (( $(echo "$ELAPSED_HRS < 8.0" | bc -l) )); then
  echo "P2 GATE: GO ($ELAPSED_HRS h < 8h)"
else
  echo "P2 GATE: NO-GO ($ELAPSED_HRS h ≥ 8h) — writing defer-to-v1.2 doc cascade"
fi
```

Edge cases:
- W0 + W1 spanned multiple sessions (commits separated by overnight idle): time math captures wall-clock not work-time → may overcount. Mitigation: in CONTEXT-PATCH, user может subtract idle hours explicitly
- Если 09-02 имел deviation requiring re-plan: take last GREEN commit, not deviation commit

## Test artefact (NO-GO path must ship)

Если NO-GO path triggered, doc cascade obligated:

```
REQUIREMENTS.md:
  TEST-HARNESS-04 | Phase 9 | Deferred to v1.2 (P2 NO-GO via time-budget gate)
  TEST-HARNESS-05 | Phase 9 | Deferred to v1.2 (P2 NO-GO via time-budget gate)

STATE.md locked decisions: B4/B5 → Deferred to v1.2

ROADMAP.md Phase 9 Success Criteria #5: TEST-HARNESS-04/05 status update

MILESTONES.md v1.1 (or PROJECT.md v1.2 section): add TH-04/05 to v1.2 backlog с rationale
```

## Alternative considered

- **Test-count delta < 12 tests → GO** — REJECTED. Weak proxy для complexity (см. reasoning §3)
- **Always GO** — REJECTED. Contradicts STATE.md locked B4/B5 P2 status
- **Always DEFER (upfront в v1.2)** — REJECTED. Phase 11 operator workflow needs capture-fixtures CLI; brand-coverage canary critical для STEREOTYPE/Armani brand drift detection
- **Manual decision at checkpoint (no automation)** — REJECTED. Inconsistent execution; subjective; не выгодно для autonomous run sessions (user prefers YOLO mode per memory `feedback_yolo_autonomous_runs.md`)

## Related

- [[Текущие приоритеты — Phase 9 contexted, plan next]] — текущий priority с D-902 inline
- `.planning/phases/09-live-html-harness/09-CONTEXT.md` — D-902 verbatim
- `.planning/REQUIREMENTS.md` lines 94-95 — `TEST-HARNESS-04/05 | Pending (P2 cheap-bundle — bundle if quick, else defer to v1.2)`
- `.planning/STATE.md` locked decisions block — B4/B5 P2 cheap-bundle inside Phase 9
- Phase 8 wave shape precedent — W0 sequential / W1 parallel / W2 sequential (Phase 9 mirrors)
