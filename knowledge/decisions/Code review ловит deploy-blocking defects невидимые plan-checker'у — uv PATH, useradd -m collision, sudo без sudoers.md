---
tags: [code-review, plan-checker-blind-spots, cross-environment, deploy-time-bugs, source-lock-canary-limitation, phase-7]
date: 2026-05-13
phase: 7
severity: critical
---

# Code review ловит deploy-blocking defects невидимые plan-checker'у — uv PATH, useradd -m collision, sudo без sudoers

## Утверждение

`gsd-code-reviewer` ловит **cross-environment interaction bugs**, которые `gsd-plan-checker` и source-lock канарейки структурно не могут заметить, потому что они касаются взаимодействия артефактов друг с другом и с реальной средой исполнения, а не shape/structure отдельных файлов.

## Конкретика Phase 7 (4 Critical / 8 found)

| ID | Defect | Почему canary не словил |
|---|---|---|
| CR-01 | `${HC_PING_URL:?msg}` exits 1, contract обещает 4 | Канарейка `test_wrapper_fails_loud_when_hc_ping_url_missing` грепала текстовый substring `HC_PING_URL`, не проверяла фактический exit code subprocess'а |
| CR-02 | `useradd -m` создаёт `/opt/ga_crawler/{.bashrc,...}`, потом `git clone <repo> /opt/ga_crawler` fails | Канарейки проверяли README отдельно от bash-команд порядка execution; cross-command state не моделировалось |
| CR-03 | `uv` в `/opt/ga_crawler/.local/bin/uv` невидим из cron (минимальный PATH) и `sudo -u ga_crawler` (`secure_path`) | Wrapper и cron-файл проверялись каждый отдельно; runtime PATH context не часть source-lock |
| CR-04 | Inner `sudo -u ga_crawler` падает потому что `useradd -r` не создаёт sudoers entry | Shell script читался изолированно от того, как его вызовут (`sudo -u ga_crawler script.sh`) |

## Почему

Source-lock канарейки — это структурная защита: «текст файла X содержит substring Y». Они отлично ловят drift внутри одного артефакта. Но они **не моделируют** runtime composition: какой PATH у subprocess, что произойдёт когда команда A создаст состояние которое команде B мешает, кто фактически вызывающий subject у вложенного sudo.

`plan-checker` тоже работает на уровне *intent* (план логически непротиворечив, success criteria измеримы), а не на уровне *real-world execution semantics* (что делает `bash` с `${VAR:?}`, чем `useradd -m` отличается от `-r`, как Astral installer прописывает PATH).

`gsd-code-reviewer` читает файлы и **симулирует выполнение** — what happens when this runs on Ubuntu 24.04, what's the actual exit code of this construct, does this path exist after step N. Это другой режим verification.

## Как применять

1. **Source-lock канарейки нужны, но недостаточны.** Они ловят drift, не correctness. Использовать как фундамент, но не как exhaustive coverage.
2. **`gsd-code-review` обязателен для phases с deploy artifacts** (bash, cron, deploy templates, README с copy-paste commands). Не пропускать его как «non-blocking advisory» когда фаза ship'ит ops layer.
3. **При нахождении такого defect — обновить канарейку** так, чтобы она ловила именно symptom, не только substring. Phase 7 fix CR-01 добавил `test_wrapper_reserves_exit_4_for_missing_hc_ping_url` который греппит литерал `exit 4` в правильном code path.
4. **Чем чувствительнее runtime context (cron, sudo, system user, fresh VM)** — тем критичнее cross-environment review pass до того, как README попадёт оператору.

## Антипример процесса

В Phase 7 я (executor) и canary collectively decided что `${HC_PING_URL:?msg}` достаточно: канарейка грепала `HC_PING_URL` substring и стояла GREEN, plan говорил «fail loud», я писал «exit 4» в комментариях. Никто не проверил **что bash действительно делает** при `${VAR:?}`. Spec и implementation расходились silently 4 коммита подряд. Code reviewer это поймал за один проход.

## Связи

[[bin weekly-run.sh — rigid contract with flock and fail-loud HC_PING_URL]] — артефакт где defects жили
[[Phase 7 ships zero production Python — ops layer over frozen pipeline]] — почему именно эта фаза была exposed
[[Bash wrapper владеет Healthchecks pings, не Python — hard-crash coverage critical]] — design decision который повысил criticality правильных exit codes
[[2026-05-13 — Phase 7 executed end-to-end + code review fixes, v1 milestone code-ship complete]] — session где это материализовалось
