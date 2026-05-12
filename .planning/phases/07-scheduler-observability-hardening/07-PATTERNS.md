# Phase 7: Scheduler + Observability Hardening — Pattern Map

**Mapped:** 2026-05-12
**Files analyzed:** 13 (6 production artifacts + 7 Wave 0 test stubs)
**Analogs found:** 13 / 13 (5 strong in-repo matches; 4 verbatim-from-CONTEXT no-analog; 4 partial / first-of-kind)

> Phase 7 ships **zero lines of production Python**. All new artifacts are shell scripts, config-as-code templates (cron + logrotate), a top-level Markdown runbook, an `.env.example` edit, and pytest shape-canary stubs that hash/grep the above. The dominant pattern: **CONTEXT.md decisions D-701..D-710 are themselves the source-of-truth** — many artifacts are reproduced **verbatim** from CONTEXT.md code blocks; the in-repo analog supplies only conventions (shebang, `set -euo pipefail`, comment header style, structural-canary skeleton).

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `bin/weekly-run.sh` | wrapper / orchestrator script | event-driven (cron-invoked → exec child → ping monitor) | `bin/backup.sh` | role + conventions match; **content verbatim from CONTEXT.md D-709** |
| `bin/test-failure-alert.sh` | operator harness script | event-driven (operator-invoked → orchestrates wrapper + CLI subcommand → emits checklist) | `bin/backup.sh` | role + conventions match; **content from RESEARCH.md Example 4 + CONTEXT.md D-706** |
| `deploy/etc-cron-d-ga_crawler` | config template (cron) | static (deployed via `cp` to `/etc/cron.d/`) | none in repo (first `deploy/*` file) | no in-repo analog; **content verbatim from CONTEXT.md D-708 / RESEARCH.md Example 1** |
| `deploy/etc-logrotate-d-ga_crawler` | config template (logrotate) | static (deployed via `cp` to `/etc/logrotate.d/`) | none in repo (first `deploy/*` file) | no in-repo analog; **content verbatim from CONTEXT.md D-705 / RESEARCH.md Example 2** |
| `README.md` (NEW repo root) | operator + developer runbook | static documentation | none in repo (first repo-root README); `CLAUDE.md` as tone-reference only | first repo-root README; **10-section structure verbatim from CONTEXT.md D-707** |
| `.env.example` (MODIFY) | config template (ENV) | static (operator `cp .env.example .env`) | `.env.example` (current Phase 6 version) | exact (same file; append one line) |
| `tests/test_phase07_cron_template_shape.py` | test (shape canary) | request-response (read file → grep substrings → assert) | `tests/unit/test_phase06_wave0_pyproject_envexample.py` | strong — same line-presence canary idiom |
| `tests/test_phase07_logrotate_template_shape.py` | test (shape canary) | same | same | strong |
| `tests/test_phase07_wrapper_contract.py` | test (source-lock canary) | same | `tests/test_delivery_source_lock.py` | strong — same source-grep-on-file idiom |
| `tests/test_phase07_test_failure_alert_shape.py` | test (source-lock canary) | same | `tests/test_delivery_source_lock.py` | strong |
| `tests/test_phase07_readme_structure.py` | test (markdown heading-shape canary) | same | `tests/test_delivery_source_lock.py` (idiom: read file → assert structure) | partial — heading-order check is new domain, but read-file-then-assert pattern reused |
| `tests/test_phase07_env_example_shape.py` | test (line-presence canary) | same | `tests/unit/test_phase06_wave0_pyproject_envexample.py::test_env_example_committed_with_three_placeholders` | exact — extends the existing test pattern by one line |
| `tests/test_phase07_structural_canaries.py` | test (file-hash + grep canary) | same | `tests/test_delivery_source_lock.py` + `tests/unit/test_stats_namespace_five_way.py` | strong — combines source-grep and namespace-disjoint canary idioms |

---

## Pattern Assignments

### `bin/weekly-run.sh` (wrapper script, event-driven)

**Analog:** `bin/backup.sh` (Plan 02-06; the ONLY existing bash script in the project; Windows-quirk-handled)
**Content source:** CONTEXT.md D-709 (verbatim code block, lines 92–131) — RESEARCH.md confirms the same idiom at lines 176–214.

**Convention header to copy from `bin/backup.sh`** (lines 1–20):

```bash
#!/usr/bin/env bash
# Online SQLite backup + 4-rotate retention. D-219.
#
# Source: 02-RESEARCH.md §"Don't Hand-Roll Backup" + §Pitfall 3 (WAL-safe atomic backup);
#         02-CONTEXT.md D-219 (online .backup chosen over VACUUM INTO for atomicity + WAL).
#
# Phase 7 ops-playbook adds cron entry: `0 1 * * * /opt/ga_crawler/bin/backup.sh`
# (daily 01:00 KZ — runs AFTER weekly Sunday-night batch completes; DB checkpointed).
#
# Usage:
#   bin/backup.sh                          # uses defaults: prices.db -> backups/
#   ...
#
# Exit codes:
#   0 — backup written successfully
#   1 — source DB not found
#   2 — backup file empty or missing after sqlite3 .backup

set -euo pipefail
```

**Mirror exactly:**
- Shebang `#!/usr/bin/env bash` (NOT `#!/bin/bash` — D-709 CONTEXT.md uses the latter, but `bin/backup.sh` convention is `/usr/bin/env bash` which is more portable; **planner reconciles — recommendation: use `#!/usr/bin/env bash` per existing project convention**).
- Top-of-file `#` comment block with: title, source citation (`CONTEXT.md D-709`, `RESEARCH.md Example` references), usage examples, **exit code table** (Phase 7 has codes 0/2/3/4/5 reserved per CONTEXT.md Claude's Discretion line 156).
- `set -euo pipefail` immediately after the comment block.
- Error messages to stderr via `>&2` (see `bin/backup.sh:26,41`).
- `exit N` with explicit numeric codes; no implicit fall-through.

**Core pattern (verbatim from CONTEXT.md D-709 lines 93–131):**

```bash
#!/bin/bash
set -euo pipefail
cd /opt/ga_crawler

set -a
source .env
set +a

: "${HC_PING_URL:?HC_PING_URL missing — refusing to run per D-703}"

exec 9>/var/lock/ga_crawler-weekly.lock
flock -n 9 || { echo "Another weekly-run holds the lock — refusing" >&2; exit 5; }

LOG_DIR=/var/log/ga_crawler
LOG_FILE="$LOG_DIR/weekly-run-$(date +%F).log"

curl -fsS -m 10 --retry 3 "${HC_PING_URL}/start" > /dev/null || true

set +e
uv run python -m ga_crawler weekly-run "$@" >> "$LOG_FILE" 2>&1
EXIT=$?
set -e

if [[ $EXIT -eq 0 ]]; then
  curl -fsS -m 10 --retry 3 "${HC_PING_URL}" > /dev/null || true
else
  curl -fsS -m 10 --retry 3 --data-raw "exit=$EXIT" "${HC_PING_URL}/fail" > /dev/null || true
fi

exit $EXIT
```

**Error-redirect convention pattern from `bin/backup.sh` (line 26):**

```bash
if [ ! -f "$DB_PATH" ]; then
  echo "ERROR: source DB not found: $DB_PATH" >&2
  exit 1
fi
```

**Apply to wrapper:** the `flock -n 9 || { echo "..." >&2; exit 5; }` line already follows this convention; comment block exit-code table mirrors `bin/backup.sh:15-19`.

---

### `bin/test-failure-alert.sh` (operator orchestrator script, event-driven)

**Analog:** `bin/backup.sh` (conventions); `bin/weekly-run.sh` (siblling script, same wrapper conventions).
**Content source:** CONTEXT.md D-706 (5-step recipe lines 48–55) + RESEARCH.md Example 4 (verbatim code block lines 415–444).

**Header (mirror `bin/backup.sh` style):**

```bash
#!/usr/bin/env bash
# Deliberate-failure orchestrator — verifies SC#5 end-to-end. D-706.
#
# Source: 07-CONTEXT.md D-706 (5-step recipe); 07-RESEARCH.md Example 4.
#
# Sequence:
#   1) Force sanity-N gate fail via --sanity-gate-n 999999 (viled-only crawl ~2 min)
#   2) Extract run_id from the latest weekly-run log
#   3) Invoke deliver-run for the failed run → expects ops chat alert + business silent
#   4) Emit verification checklist for operator (ops chat / business chat / HC / DB)
#   5) NO cleanup — failed run remains in DB as evidence (script is idempotent)
#
# Usage:
#   sudo -u ga_crawler /opt/ga_crawler/bin/test-failure-alert.sh
#
# Exit codes:
#   0 — checklist emitted (operator validates visually)
#   any non-zero — script setup failed (script-level), NOT pipeline failure

set -euo pipefail
cd /opt/ga_crawler
```

**Core pattern (verbatim from RESEARCH.md Example 4):**

```bash
echo "==> Step 1: Forced sanity-N gate fail (viled-only crawl, ~2 min)"
bin/weekly-run.sh --viled-only --sanity-gate-n 999999 || true

echo "==> Step 2: Extract last run_id from log"
LOG_FILE="/var/log/ga_crawler/weekly-run-$(date +%F).log"
RID=$(tail -200 "$LOG_FILE" | grep -o '"run_id":[0-9]*' | tail -1 | grep -o '[0-9]*')
echo "    run_id=$RID"

echo "==> Step 3: Invoke deliver-run for ops alert (no HC ping — separate invocation)"
sudo -u ga_crawler /opt/ga_crawler/.venv/bin/python -m ga_crawler deliver-run --run-id "$RID"

echo "==> Step 4: Verification checklist (operator runs visually)"
cat <<EOF
  [ ] Telegram ops chat: alert message visible with reason='upstream pipeline failed' for run #$RID
  [ ] Telegram business chat: NO new message
  [ ] Healthchecks.io dashboard: /start + /fail pings logged
  [ ] DB: sqlite3 /opt/ga_crawler/prices.db 'SELECT run_id, status, reason FROM runs WHERE run_id=$RID'
        Expected: failed | sanity_gate_n_failed:120<999999
  [ ] DB stats: sqlite3 ... "SELECT json_extract(stats,'\$.deliver.delivery_status') FROM runs WHERE run_id=$RID"
        Expected: delivered_ops_only
EOF
```

**Reuses existing CLI surface (no new Python LOC):** `--viled-only` (Plan 02-05 D-212), `--sanity-gate-n` (Plan 04-05), `deliver-run --run-id N` (Phase 6 D-608). Pattern shows orchestrator wraps existing CLI subcommands; **DO NOT add new flags or production-code paths.**

---

### `deploy/etc-cron-d-ga_crawler` (cron config template, static)

**In-repo analog:** NONE — `deploy/` directory does not yet exist. This is the first `deploy/*` artifact.
**Content source:** **VERBATIM** from CONTEXT.md D-708 (lines 84–89) and RESEARCH.md Example 1 (lines 374–382).

**Verbatim content:**

```
# Source: CONTEXT.md D-708; crontab(5); Pitfall #1 (no dots in filename)
CRON_TZ=Asia/Almaty
MAILTO=""
0 23 * * 0 ga_crawler /opt/ga_crawler/bin/weekly-run.sh
0 1  * * * ga_crawler /opt/ga_crawler/bin/backup.sh
```

**Pattern notes for planner:**
- **Filename has NO dots and NO extension** — Vixie cron silently ignores files with dots (Pitfall #1; RESEARCH.md line 306). Repo path `deploy/etc-cron-d-ga_crawler` and target path `/etc/cron.d/ga_crawler` are both Vixie-safe.
- `CRON_TZ=Asia/Almaty` MUST be the first non-comment line (scope-limited to this file).
- `MAILTO=""` (empty string, NOT unset) explicitly disables cron-email — required guard for Pitfall #2.
- User column `ga_crawler` between schedule and command (Vixie `/etc/cron.d/*` format; differs from per-user crontab).
- Two rows: weekly-run Sunday 23:00 + backup daily 01:00 (both required by SCHED-02; backup row activates the Plan 02-06 `bin/backup.sh` script that is currently un-scheduled).

---

### `deploy/etc-logrotate-d-ga_crawler` (logrotate config template, static)

**In-repo analog:** NONE — first logrotate config in the repo.
**Content source:** **VERBATIM** from CONTEXT.md D-705 (lines 33–43) and RESEARCH.md Example 2 (lines 385–397).

**Verbatim content:**

```
# Source: CONTEXT.md D-705; logrotate(8); RESEARCH.md Pitfall #5 (user must exist first)
/var/log/ga_crawler/*.log {
    weekly
    rotate 13
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ga_crawler ga_crawler
}
```

**Pattern notes for planner:**
- 7 directives, all required (each individually grepped by the shape-canary in `tests/test_phase07_logrotate_template_shape.py`):
  - `weekly` — rotation cadence
  - `rotate 13` — keep 13 archives (3 months)
  - `compress` — gzip rotated files
  - `delaycompress` — keep last rotation uncompressed (diagnosis-friendly)
  - `missingok` — first-run safety (no error if glob matches zero files)
  - `notifempty` — skip 0-byte logs (avoid rotating empty placeholder)
  - `create 0644 ga_crawler ga_crawler` — post-rotation file owner + mode
- **`ga_crawler` system user MUST exist BEFORE first logrotate run** (Pitfall #5; README §2 setup order enforces).

---

### `README.md` (NEW at repo root; operator + developer runbook)

**In-repo analog:** NONE — no top-level README exists yet (the existing `inbox/README.md` and `.planning/spikes/01-goldapple/README.md` are not analogs — different audiences and scope).
**Tone analog:** `CLAUDE.md` (project root, RU/EN mixed prose style; technical terms in EN, prose in RU) — use as reference for RU/EN code-fence convention.
**Content source:** CONTEXT.md D-707 (lines 59–79, 10-section structure verbatim).

**Mandatory 10-section structure (order MUST be exact; canary `tests/test_phase07_readme_structure.py` asserts heading order):**

1. `## Что это` — 5-line summary (core value + delivery contract from PROJECT.md)
2. `## VPS setup from-scratch` — Ubuntu 24.04 LTS commands (apt install, useradd, uv install, git clone, uv sync, playwright install firefox, install -d /var/log/ga_crawler, cp deploy/etc-cron-d-ga_crawler /etc/cron.d/ga_crawler, cp deploy/etc-logrotate-d-ga_crawler /etc/logrotate.d/ga_crawler, smoke test `bin/weekly-run.sh --viled-only --sanity-gate-n 1`)
3. `## ENV vars` — table of TG_BOT_TOKEN / TG_BUSINESS_CHAT_ID / TG_OPS_CHAT_ID / HC_PING_URL + override flags + ref to `.env.example`; document **reserved exit codes 3/4/5**
4. `## Cron entry` — `/etc/cron.d/ga_crawler` content verbatim + SCHED-02 CRON_TZ invariant explanation
5. `## Healthchecks.io setup` — step-by-step (create account, create check, copy ping URL, schedule, grace period 2h, Telegram integration `@my_hc_bot`)
6. `## Telegram bot setup` — step-by-step (BotFather, chat_id discovery, .env wiring)
7. `## Deliberate-failure test` — `bin/test-failure-alert.sh` invocation + checklist + troubleshooting pointer
8. `## Operations runbook` — recovery recipes (deliver-run / report-run / matcher-run / backup restore / `sqlite3` status query)
9. `## Логи` — location, rotation policy, grep examples (`tail -f`, `grep '"level":"error"'`, `zgrep '"run_id":"42"' *.log.gz`)
10. `## Dev setup` — short block (5 lines): clone + `uv sync` + `uv run pytest` + ref to `CLAUDE.md`

**Language convention (from D-707):** **RU primary for prose; EN for code blocks, commands, ENV names, flags, exit codes.** Operator reads RU, copies EN commands verbatim. Mirror `CLAUDE.md` tone (Russian explanatory prose; English technical artifacts).

---

### `.env.example` (MODIFY — existing file, append one line)

**Analog:** itself — current Phase 6 version at `C:\Users\gstorepc\projects\ga_crawler\.env.example`.

**Current content (lines 1–8):**

```
# Telegram delivery (Phase 6 — DELIVER-05)
# Create bot: @BotFather → /newbot
# Get chat_id: add @userinfobot to chat → it prints the chat_id

TG_BOT_TOKEN=
TG_BUSINESS_CHAT_ID=
TG_OPS_CHAT_ID=
```

**Pattern to mirror (insertion point: AFTER current line 7 `TG_OPS_CHAT_ID=`; append new comment block + new placeholder):**

```
# Telegram delivery (Phase 6 — DELIVER-05)
# Create bot: @BotFather → /newbot
# Get chat_id: add @userinfobot to chat → it prints the chat_id

TG_BOT_TOKEN=
TG_BUSINESS_CHAT_ID=
TG_OPS_CHAT_ID=

# Healthchecks.io dead-man's-switch (Phase 7 — SCHED-03)
# Create check at healthchecks.io → copy ping URL (full URL incl. scheme)
# Required: bash wrapper refuses to run if missing (exit 4 per D-703).

HC_PING_URL=
```

**Conventions to preserve (from existing Phase 6 file):**
- Comment block per logical group of vars (Phase 6 grouped 3 TG_* vars under one comment block; Phase 7 adds a second block for HC_PING_URL).
- Empty value after `=` (no placeholder string, no quotes) — enforced by `test_env_example_has_no_real_secret_values` canary already in `tests/unit/test_phase06_wave0_pyproject_envexample.py`.
- **No `#` inside values, no quotes around values** (Pitfall #4 — bash `source .env` vs python-dotenv parser drift on `#` inside quoted strings); the Phase 7 canary `test_phase07_env_example_shape.py` extends this assertion.
- Plain `K=V` form with K matching `[A-Z_]+`.

---

### `tests/test_phase07_cron_template_shape.py` (shape canary)

**Analog:** `tests/unit/test_phase06_wave0_pyproject_envexample.py` (file lines 1–85; **line-presence canary** idiom).

**Excerpt to mirror (lines 12–31, 54–79):**

```python
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_env_example_committed_with_three_placeholders():
    env_example = REPO_ROOT / ".env.example"
    assert env_example.exists(), ".env.example must exist at repo root (D-612)"
    txt = env_example.read_text(encoding="utf-8")
    assert "TG_BOT_TOKEN=" in txt
    assert "TG_BUSINESS_CHAT_ID=" in txt
    assert "TG_OPS_CHAT_ID=" in txt
```

**Pattern to apply (cron template canary):**
- `REPO_ROOT = Path(__file__).resolve().parents[1]` (Phase 7 tests live at `tests/` root, not `tests/unit/`; per VALIDATION.md table all `tests/test_phase07_*.py` are top-level → use `parents[1]` NOT `parents[2]`).
- Read `deploy/etc-cron-d-ga_crawler` via `Path.read_text(encoding="utf-8")`.
- Assert presence of substrings: `"CRON_TZ=Asia/Almaty"`, `'MAILTO=""'`, `"0 23 * * 0 ga_crawler /opt/ga_crawler/bin/weekly-run.sh"`, `"0 1  * * * ga_crawler /opt/ga_crawler/bin/backup.sh"` (note 2 spaces — match D-708 verbatim).
- Negative-assert filename has no dot: split filename, assert `"." not in Path(...).name` (Pitfall #1 guard).

---

### `tests/test_phase07_logrotate_template_shape.py` (shape canary)

**Analog:** same as above (`test_phase06_wave0_pyproject_envexample.py` line-presence idiom).

**Pattern to apply:**
- Read `deploy/etc-logrotate-d-ga_crawler`.
- Assert presence of each of 7 directives as substring: `"weekly"`, `"rotate 13"`, `"compress"`, `"delaycompress"`, `"missingok"`, `"notifempty"`, `"create 0644 ga_crawler ga_crawler"`.
- One assert per directive (separate test functions per VALIDATION.md sampling-rate target: 5-second feedback loop on commit).

---

### `tests/test_phase07_wrapper_contract.py` (source-lock canary on `bin/weekly-run.sh`)

**Analog:** `tests/test_delivery_source_lock.py` (lines 1–110; **source-grep on file-set** idiom).

**Excerpt to mirror (lines 11–50):**

```python
from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_DIR = REPO_ROOT / "src" / "ga_crawler" / "delivery"
FORBIDDEN_IMPORTS = (
    "summary_builder",
    "excel_builder",
    "reporter.queries",
    "reporter.archive",
)


@pytest.fixture
def delivery_source_text() -> str:
    """Combined text of every ``src/ga_crawler/delivery/*.py`` module."""
    files = list(DELIVERY_DIR.glob("*.py"))
    assert len(files) >= 4, ...
    return "\n".join(f.read_text(encoding="utf-8") for f in files)


def test_no_summary_builder_import_in_delivery(delivery_source_text):
    for forbidden in FORBIDDEN_IMPORTS:
        assert forbidden not in delivery_source_text, ...
```

**Pattern to apply (wrapper contract canary, D-709 invariants):**
- `REPO_ROOT = Path(__file__).resolve().parents[1]`.
- `WRAPPER = REPO_ROOT / "bin" / "weekly-run.sh"`.
- `text = WRAPPER.read_text(encoding="utf-8")`.
- **Positive-asserts (substring present)** per VALIDATION.md table:
  - `"set -euo pipefail"` (line 95 of D-709 verbatim)
  - `"${HC_PING_URL}/start"` and `"${HC_PING_URL}"` (bare) and `"${HC_PING_URL}/fail"` (D-701)
  - `'"${HC_PING_URL:?'` (fail-loud sentinel substring; D-703)
  - `"flock -n 9"` (D-709)
  - `"exit 5"` (Pitfall #3 reserved exit code for flock-double-run-refused)
  - `"|| true"` (HC pings fail-soft; appears ≥ 3 times — one per /start, /success, /fail)
  - `">> \"$LOG_FILE\" 2>&1"` (SCHED-04 stdout+stderr redirect)
  - `"/var/log/ga_crawler/weekly-run-$(date +%F).log"` (log path)
  - `"--data-raw \"exit=$EXIT\""` (D-701 diagnostic body)
- **Negative-assert:** no `simulate-failure` / `fail.mode` substring (Phase 7 specifics line 259).

---

### `tests/test_phase07_test_failure_alert_shape.py` (source-lock canary on `bin/test-failure-alert.sh`)

**Analog:** `tests/test_delivery_source_lock.py` (same source-grep idiom).

**Pattern to apply (D-706 step invariants):**
- `SCRIPT = REPO_ROOT / "bin" / "test-failure-alert.sh"`.
- Positive-asserts:
  - `"--viled-only"` (D-706 step 1)
  - `"--sanity-gate-n 999999"` (D-706 step 1)
  - `"deliver-run --run-id"` (D-706 step 3)
  - `"Telegram ops chat"` (checklist line — D-706 step 4)
  - `"Telegram business chat"` (checklist line)
  - `"Healthchecks.io dashboard"` (checklist line)
  - `"delivered_ops_only"` (expected delivery_status — D-706 step 4)
  - `"sanity_gate_n_failed:120<999999"` (expected reason — D-706 step 4)

---

### `tests/test_phase07_readme_structure.py` (markdown-heading-shape canary)

**Analog (idiom):** `tests/test_delivery_source_lock.py` (read-file-then-assert-structure pattern); no exact precedent for markdown heading-order assertion — **partial match, first of its kind in this project**.

**Pattern to apply (D-707 10-section structure):**
- `README = REPO_ROOT / "README.md"`.
- Parse top-level `##` headings via line-prefix grep:
  ```python
  headings = [
      line.strip()
      for line in README.read_text(encoding="utf-8").splitlines()
      if line.startswith("## ")
  ]
  ```
- Assert `len(headings) == 10`.
- Assert **exact order**: `["## Что это", "## VPS setup from-scratch", "## ENV vars", "## Cron entry", "## Healthchecks.io setup", "## Telegram bot setup", "## Deliberate-failure test", "## Operations runbook", "## Логи", "## Dev setup"]` (verbatim from D-707).
- Optional: assert RU-primary by checking presence of Cyrillic in headings ≥1 (`"Что это"`, `"Логи"`).

---

### `tests/test_phase07_env_example_shape.py` (line-presence + value-format canary)

**Analog:** `tests/unit/test_phase06_wave0_pyproject_envexample.py::test_env_example_committed_with_three_placeholders` (lines 54–79) + `::test_env_example_has_no_real_secret_values` (lines 63–79).

**Excerpt to extend (verbatim from analog lines 63–79):**

```python
def test_env_example_has_no_real_secret_values():
    env_example = REPO_ROOT / ".env.example"
    txt = env_example.read_text(encoding="utf-8")
    for line in txt.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.startswith("TG_"):
            assert value == "", ...
```

**Pattern to apply (Phase 7 extension):**
- Inherit `test_env_example_committed_with_three_placeholders` shape, ADD assertion:
  ```python
  assert "HC_PING_URL=" in txt, ".env.example must contain HC_PING_URL= placeholder (D-703)"
  ```
- Extend `test_env_example_has_no_real_secret_values` to cover HC_PING_URL too (loop condition `key.startswith("TG_") or key == "HC_PING_URL"`).
- **Pitfall #4 canary** (RESEARCH.md line 330): for each non-comment line with `=`, assert `"#" not in value` AND `'"' not in value` AND `"'" not in value` AND `"\n" not in value` (single-line, unquoted, no inline-comment — bash/python-dotenv parser parity).

---

### `tests/test_phase07_structural_canaries.py` (cross-phase invariant canary)

**Analog:** `tests/test_delivery_source_lock.py` (source-grep idiom) + `tests/unit/test_stats_namespace_five_way.py` (namespace-disjoint canary).

**Stats namespace excerpt (verbatim from `test_stats_namespace_five_way.py` lines 17–30):**

```python
def test_five_way_namespaces_disjoint():
    sets = {
        "viled":     set(VILED_STATS_KEYS),
        "goldapple": set(GOLDAPPLE_STATS_KEYS),
        "match":     set(MATCH_STATS_KEYS),
        "report":    set(REPORT_STATS_KEYS),
        "deliver":   set(DELIVER_STATS_KEYS),
    }
    names = list(sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert sets[a].isdisjoint(sets[b]), ...
```

**Pattern to apply (Phase 7 "zero production Python" + namespace-preserved invariant):**

1. **File-hash canary on frozen modules** (Phase 7 ships zero production Python):
   - Hash `src/ga_crawler/cli.py` content (SHA-256 of `read_text("utf-8")`).
   - Hash `src/ga_crawler/runners/main_run.py` content.
   - Compare against a **pinned hash** captured at Phase 6 close-out commit `8c03acb` / `13e1325` (planner snapshots; Wave 0 RED until Phase 7 close-out commit re-pins).
   - Alternative simpler form: assert specific anchor substrings present (the existing `_configure_logging` signature, `def _cmd_weekly`, `run_weekly` import in CLI handler). Per VALIDATION.md row 54 — file-hash IS the strategy.

2. **No new production-source `simulate` / `fail.mode` substrings:**
   ```python
   SRC_ROOT = REPO_ROOT / "src" / "ga_crawler"
   FORBIDDEN_SUBSTRINGS = ("simulate-failure", "simulate_failure", "fail.mode", "fail_mode")
   for py in SRC_ROOT.rglob("*.py"):
       text = py.read_text(encoding="utf-8")
       for forbidden in FORBIDDEN_SUBSTRINGS:
           assert forbidden not in text, f"{py.name} contains {forbidden!r} ..."
   ```

3. **Reuse 5-way namespace-disjoint canary verbatim** (no Phase 7 6th namespace per CONTEXT.md Claude's Discretion line 154):
   - Import `test_five_way_namespaces_disjoint` indirectly, or duplicate the body to keep the canary co-located with Phase 7 tests. (Recommendation: **re-export-and-call** — import `DELIVER_STATS_KEYS` etc. and assert disjoint; do NOT re-add a 6th namespace key set.)

4. **`load_dotenv` only in `cli.py` invariant** (Phase 6 RESEARCH caveat #4 — Phase 7 inherits):
   - Mirror the `test_load_dotenv_not_in_delivery_module` body but expand scope to **all `src/ga_crawler/**/*.py` except `cli.py`**.

5. **`pyproject.toml` no new `[tool.ga_crawler.*]` namespace** (CONTEXT.md line 153):
   ```python
   import tomllib
   data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
   tool_ns = set(data.get("tool", {}).get("ga_crawler", {}).keys())
   # Phase 6 added exactly: deliver, report, match, viled, goldapple
   EXPECTED = {"deliver", "report", "match", "viled", "goldapple"}
   assert tool_ns == EXPECTED, f"Phase 7 must not add new namespaces; got {tool_ns - EXPECTED}"
   ```
   (Planner verifies `EXPECTED` matches current Phase 6 reality; adjust if drift discovered.)

---

## Shared Patterns

### bash wrapper convention (`set -euo pipefail` + stderr error + numeric exit)

**Source:** `bin/backup.sh` (entire file; only existing bash script in the project).
**Apply to:** Both new `bin/*.sh` files (`weekly-run.sh`, `test-failure-alert.sh`).

```bash
#!/usr/bin/env bash
# <Title>. <Decision-ID>.
#
# Source: <CONTEXT.md decision> + <RESEARCH.md section>.
#
# Usage:
#   <invocation example>
#
# Exit codes:
#   0 — <success>
#   N — <documented condition>

set -euo pipefail

# ... body ...

# Error path:
if [ <bad condition> ]; then
  echo "ERROR: <human-readable>" >&2
  exit <N>
fi
```

**Mirror exactly:**
- `#!/usr/bin/env bash` shebang (project convention; **CONTEXT.md D-709 uses `#!/bin/bash` but planner SHOULD reconcile to `/usr/bin/env bash` for consistency with `bin/backup.sh`** — or document the divergence).
- Top-of-file comment block with title + source + usage + exit-code table.
- `set -euo pipefail` directly after the comment block.
- All errors → stderr via `>&2`, exit with explicit numeric code.

### Source-grep canary pattern (read file → assert substring presence)

**Source:** `tests/test_delivery_source_lock.py` (lines 11–110).
**Apply to:** All 7 Phase 7 test files.

```python
from __future__ import annotations
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]   # tests/ at repo root


@pytest.fixture
def <artifact>_text() -> str:
    path = REPO_ROOT / "<rel path>"
    assert path.exists(), f"{path} must exist"
    return path.read_text(encoding="utf-8")


def test_<artifact>_contains_<invariant>(<artifact>_text):
    assert "<substring>" in <artifact>_text, (
        "<artifact> missing <substring> — violates <D-NNN> invariant"
    )
```

**Mirror exactly:**
- `from __future__ import annotations` at top.
- `REPO_ROOT` via `Path(__file__).resolve().parents[N]` (N=1 for `tests/`-rooted, N=2 for `tests/unit/`-rooted).
- pytest fixture for the file content (re-used across multiple asserts in same file).
- One assertion per logical invariant; descriptive failure message citing the D-NNN decision.

### Line-presence canary pattern (extends source-grep with structured parsing)

**Source:** `tests/unit/test_phase06_wave0_pyproject_envexample.py` (lines 54–79).
**Apply to:** `test_phase07_env_example_shape.py`, `test_phase07_cron_template_shape.py`, `test_phase07_logrotate_template_shape.py`.

```python
def test_<file>_contains_<expected>():
    txt = (REPO_ROOT / "<file>").read_text(encoding="utf-8")
    assert "<expected>" in txt, "<file> missing <expected> (<D-NNN>)"


def test_<file>_values_are_blank():
    txt = (REPO_ROOT / "<file>").read_text(encoding="utf-8")
    for line in txt.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if <predicate on key>:
            assert value == "", f"{key} must be blank (got {value!r})"
```

### Test file location convention

**Source:** existing test layout — `tests/test_*.py` for Phase-6-package-level canaries; `tests/unit/test_*.py` for module unit tests; `tests/integration/test_*.py` for integration.
**Apply to:** All Phase 7 test files go at **`tests/test_phase07_*.py`** (top-level, NOT under `unit/`) per VALIDATION.md table — matches Phase 6 source-lock convention (`tests/test_delivery_source_lock.py` is also top-level). `REPO_ROOT = Path(__file__).resolve().parents[1]` accordingly.

### Comment header source-of-truth citation

**Source:** `bin/backup.sh` lines 2–10 (citation block: `Source: 02-RESEARCH.md §..., 02-CONTEXT.md D-219`).
**Apply to:** Every new artifact (bash, cron, logrotate) — first comment block cites the originating CONTEXT.md decision ID (D-701..D-710) and RESEARCH.md section/Pitfall, so reverse lookup from production artifact to design rationale is single-grep.

---

## No Analog Found

Files with no in-repo analog (planner uses CONTEXT.md / RESEARCH.md verbatim blocks as the source):

| File | Role | Data Flow | Reason / Source-of-Truth |
|------|------|-----------|--------------------------|
| `deploy/etc-cron-d-ga_crawler` | config template | static | First `deploy/*` artifact; **content verbatim from CONTEXT.md D-708 / RESEARCH.md Example 1**. No bash, no Python — just cron directives. |
| `deploy/etc-logrotate-d-ga_crawler` | config template | static | Same — first logrotate config in repo; **content verbatim from CONTEXT.md D-705 / RESEARCH.md Example 2**. |
| `README.md` at repo root | runbook docs | static | First repo-root README; **10-section structure verbatim from CONTEXT.md D-707**. Tone-ref only: `CLAUDE.md` RU/EN mix. |
| `tests/test_phase07_readme_structure.py` | markdown heading-order canary | request-response | No precedent for markdown structure assertion; planner extends the read-file-then-assert pattern from `tests/test_delivery_source_lock.py`. Heading-list parsing is new but trivial (`startswith("## ")`). |

---

## Metadata

**Analog search scope:**
- `bin/` (1 file: `backup.sh`)
- `tests/` (top-level + `unit/` + `integration/`)
- `.env.example` (root)
- `src/ga_crawler/` (READ-ONLY for Phase 7 structural-canary anchor)

**Key analogs read (5 in-repo files):**
- `bin/backup.sh` — bash conventions (1 file, 56 lines, full read)
- `.env.example` — current Phase 6 state for the modify-target (1 file, 8 lines, full read)
- `tests/test_delivery_source_lock.py` — source-lock canary idiom (1 file, 110 lines, full read)
- `tests/unit/test_phase06_wave0_pyproject_envexample.py` — line-presence + value-format canary idiom (1 file, 85 lines, full read)
- `tests/unit/test_stats_namespace_five_way.py` — namespace-disjoint canary idiom (1 file, 36 lines, full read)

**Supporting files inspected (4 partial reads):**
- `src/ga_crawler/cli.py` lines 1–119 — frozen surface; exit-code conventions (`return 0 if … else 2` lines 80, 118)
- `tests/unit/test_phase06_wave0_stub_inventory.py` lines 1–60 — stub-inventory pattern (not a Phase 7 fit; documents wave-closure cadence)
- `tests/test_delivery_stats.py` lines 1–60 — stats-key shape canary (not a Phase 7 fit; Phase 7 adds no stats namespace)
- `07-CONTEXT.md` full read + `07-RESEARCH.md` lines 1–600 + `07-VALIDATION.md` full read — design-source-of-truth for verbatim blocks

**Pattern extraction date:** 2026-05-12
**Files scanned:** ~16 test files + 1 bash script + 1 env template + 3 design docs
**Planner cue:** Phase 7 plans should reference this PATTERNS.md per-file under "Reuse" subsections; verbatim blocks from CONTEXT.md D-705 / D-708 / D-709 + RESEARCH.md Examples 1–4 are the **primary source** for the four no-analog artifacts.
