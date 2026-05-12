---
phase: 07-scheduler-observability-hardening
reviewed: 2026-05-12T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - bin/weekly-run.sh
  - bin/test-failure-alert.sh
  - deploy/etc-cron-d-ga_crawler
  - deploy/etc-logrotate-d-ga_crawler
  - .env.example
  - README.md
  - tests/test_phase07_cron_template_shape.py
  - tests/test_phase07_env_example_shape.py
  - tests/test_phase07_logrotate_template_shape.py
  - tests/test_phase07_readme_structure.py
  - tests/test_phase07_structural_canaries.py
  - tests/test_phase07_test_failure_alert_shape.py
  - tests/test_phase07_wrapper_contract.py
findings:
  critical: 4
  warning: 9
  info: 4
  total: 17
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-05-12
**Depth:** standard
**Files Reviewed:** 13 (2 bash wrappers, 2 deploy templates, .env.example, README.md, 7 canary test files)
**Status:** issues_found

## Summary

Phase 7 ships operational artefacts (cron wrapper, deliberate-failure orchestrator, cron/logrotate configs, RU operator runbook) plus seven shape-canary test files. The structural canaries are well-scoped and tight against D-7xx decisions — they will catch most accidental drift in future phases.

However, a focused source review surfaced four **BLOCKER**-class defects in the deployment path that the canaries cannot see (they only source-grep substrings; they do not execute the scripts or simulate a fresh VPS):

1. The "fail-loud HC_PING_URL missing" exit code is wrong: actual exit is **1**, documented as **4** (D-703 contract violation).
2. `README §2` step ordering creates `/opt/ga_crawler` via `useradd -m`, then tries to `git clone` into it — fails because directory is non-empty.
3. `uv` is installed under the unprivileged user's `~/.local/bin` but is invoked via `sudo -u ga_crawler uv ...` and via cron, neither of which inherits that PATH — every `uv run` invocation in README and `weekly-run.sh` will hit "command not found" in a fresh deploy.
4. `bin/test-failure-alert.sh` does `sudo -u ga_crawler` from inside a script already running as `ga_crawler` (a system user with no sudoers entry) — SC#5 deliberate-failure verification will fail at step 3.

These combine to mean the documented from-scratch deploy will not work end-to-end on a clean Hetzner VPS. SCHED-03 fail-loud contract is also broken (HC alert payload will show exit=1, not exit=4). The Wave 0 canaries do not catch any of these because they are pure substring source-greps, not runtime/semantic assertions.

Several **WARNING**-class issues: README ENV table conflates wrapper vs. Python-child exit codes (claims wrapper exits 3 for missing TG_BOT_TOKEN — false), `zgrep | jq` example will produce malformed JSON on multi-file matches, README's stated reserved exit codes are inconsistent with the actual `_cmd_weekly` mapping (only 0/2 reachable from the wrapper path), `test-failure-alert.sh` step 2 crashes opaquely under `pipefail` when no run_id is in log.

The bash wrappers themselves are otherwise idiomatic: `set -euo pipefail`, exit-code preservation via `set +e/EXIT=$?/set -e`, fail-soft HC pings via `|| true`, no hardcoded UUIDs, correct flock usage, correct redirect ordering. Deploy templates (cron + logrotate) match D-705/D-708 verbatim and end with newlines.

---

## Critical Issues

### CR-01: `${HC_PING_URL:?}` exits 1, not 4 — D-703 contract broken

**File:** `bin/weekly-run.sh:50`
**Category:** Bug / Contract violation
**Issue:**

The wrapper documents (line 11) "Fail-loud if HC_PING_URL missing (exit 4 per D-703)", and the README §3 reserved-exit-codes table (lines 60, 73) advertises exit 4 as the fail-loud sentinel for missing `HC_PING_URL`. The actual code at line 50 uses bash parameter expansion `: "${HC_PING_URL:?HC_PING_URL missing — refusing to run per D-703}"`.

Under `set -euo pipefail`, the `${VAR:?word}` expansion form prints `word` to stderr and exits the non-interactive shell with status **1**, not 4. There is no explicit `exit 4` anywhere in the wrapper (verified — only one `exit 4` reference, and it lives in a comment). This conflates a documented config-error (HC_PING_URL missing) with generic bash error exit, defeating the entire purpose of reserving exit 4.

Downstream impact:
- HC.io `/fail` is **not** pinged (we exit before reaching the ping logic) — acceptable, dead-man's-switch grace period covers it.
- But operators reading cron logs / sudo invocation output will see exit 1 and reach for the generic-error troubleshooting paths instead of "missing `HC_PING_URL` in `.env`".
- Plan 07-03 SUMMARY.md and 07-05 SUMMARY.md both claim D-703 is "closed at source" — this assertion is incorrect.

The canary `test_wrapper_fails_loud_when_hc_ping_url_missing` only greps for substring `${HC_PING_URL:?`, not for exit-4 semantics, so it stays green despite the defect.

**Fix:**
```bash
# Replace line 50 with explicit guard.
if [[ -z "${HC_PING_URL:-}" ]]; then
  echo "HC_PING_URL missing — refusing to run per D-703" >&2
  exit 4
fi
```

Also add a canary that verifies `exit 4` literal appears in the wrapper, paralleling `test_wrapper_reserves_exit_5_for_flock`:
```python
def test_wrapper_reserves_exit_4_for_missing_hc_ping_url(wrapper_text):
    assert "exit 4" in wrapper_text, (
        "wrapper missing 'exit 4' on HC_PING_URL fail-loud — violates D-703 (Pitfall similar to #3)"
    )
```

---

### CR-02: README §2 setup is unrunnable — `useradd -m` populates `/opt/ga_crawler`, then `git clone` fails

**File:** `README.md:19,25`
**Category:** Bug / Deployment-breaking
**Issue:**

The README §2 from-scratch deploy block runs:

```bash
# step 2
sudo useradd -r -m -d /opt/ga_crawler -s /bin/bash ga_crawler
...
# step 4
sudo -u ga_crawler git clone <repo-url> /opt/ga_crawler
```

`useradd -m -d /opt/ga_crawler` creates `/opt/ga_crawler` if missing AND populates it with `/etc/skel` contents (`.bashrc`, `.profile`, `.bash_logout`). The subsequent `git clone <repo-url> /opt/ga_crawler` then fails with `fatal: destination path '/opt/ga_crawler' already exists and is not an empty directory.`

On a clean Hetzner CX22 VPS following the README verbatim, deploy is blocked at step 4. SC#1 (smoke test on step 8) never runs.

**Fix:** several acceptable options:

1. Drop `-m` from `useradd` (no shell skeleton needed for a cron-only system user), and create the directory inline before clone:
```bash
sudo useradd -r -d /opt/ga_crawler -s /usr/sbin/nologin ga_crawler
sudo install -d -o ga_crawler -g ga_crawler -m 0755 /opt/ga_crawler
sudo -u ga_crawler git clone <repo-url> /opt/ga_crawler
```

2. Or keep `-m` and clone elsewhere, then move; but #1 is cleaner.

3. Or clone into a tmpdir and `rsync -a` the contents in.

Pitfall #6 referenced in README line 12 ("`useradd -m` для $HOME") is the root cause of this confusion — Camoufox cache only needs `$HOME` to exist and be owned by `ga_crawler`, which option (1) satisfies without skeleton-file collision.

---

### CR-03: `uv` is unreachable from `sudo -u ga_crawler ...` and from cron — every `uv run` invocation fails

**File:** `README.md:22,27,28,46,151,157,165,184`; `bin/weekly-run.sh:65`
**Category:** Bug / Deployment-breaking
**Issue:**

`README §2` step 3 installs `uv` as the unprivileged `ga_crawler` user via the Astral installer:

```bash
sudo -u ga_crawler bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
```

The installer places the `uv` binary at `~/.local/bin/uv` (i.e. `/opt/ga_crawler/.local/bin/uv`) and patches the user's shell init files (`~/.bashrc`, `~/.zshenv`) to prepend `~/.local/bin` to `PATH`. **Non-interactive, non-login shells do not source those init files.**

Three downstream invocations therefore fail with `uv: command not found`:

1. `README §2` steps 4 and 8 — `sudo -u ga_crawler uv sync`, `sudo -u ga_crawler uv run playwright install firefox`, `sudo -u ga_crawler /opt/ga_crawler/bin/weekly-run.sh ...`. `sudo` defaults to `secure_path` from `/etc/sudoers` which does not include `/opt/ga_crawler/.local/bin`.

2. `README §8` Operations runbook uses absolute `.venv/bin/python` (line 151 etc.) which sidesteps `uv`, but only after the venv exists — and the venv won't exist if step 4 failed.

3. **Cron context (most severe)**: `bin/weekly-run.sh:65` runs `uv run python -m ga_crawler weekly-run "$@"`. Cron's PATH is even more restricted than sudo (typically `/usr/bin:/bin`). `uv` is not on it. The wrapper will exit non-zero (uv missing) with `set +e` active → HC `/fail` pinged with `exit=127`, log file shows `bash: uv: command not found`. SCHED-01 (cron schedule) is broken end-to-end.

**Fix:** several options, pick one and apply everywhere:

1. Have the wrapper explicitly add `uv` to PATH (canonical):
   ```bash
   # bin/weekly-run.sh, after `cd /opt/ga_crawler`:
   export PATH="/opt/ga_crawler/.local/bin:$PATH"
   ```

2. Or set `PATH=` in `/etc/cron.d/ga_crawler`:
   ```
   PATH=/opt/ga_crawler/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
   ```
   (Cron honors PATH directive in `/etc/cron.d/*` files.)

3. Or use absolute path everywhere:
   ```bash
   /opt/ga_crawler/.local/bin/uv run python -m ga_crawler weekly-run "$@"
   ```

4. Or install `uv` system-wide (`/usr/local/bin/uv`) instead of per-user — README §2 step 3 would change to root-context install.

For `sudo -u ga_crawler uv ...` invocations in README, the simplest fix is to use the wrapper or the absolute-path form:
```bash
sudo -u ga_crawler /opt/ga_crawler/.local/bin/uv sync
```

This is a **deployment-blocking** defect for the cron path — SCHED-01 cannot succeed on the documented setup. Plan 07-05 SUMMARY claims SCHED-01 closed; that closure is contingent on a setup that does not yet work.

---

### CR-04: `bin/test-failure-alert.sh` does `sudo -u ga_crawler` from within an already-`ga_crawler` shell — SC#5 breaks at step 3

**File:** `bin/test-failure-alert.sh:46`
**Category:** Bug / Privilege-escalation impossible
**Issue:**

README §7 line 123 documents the invocation as:
```bash
sudo -u ga_crawler /opt/ga_crawler/bin/test-failure-alert.sh
```

i.e. the operator launches the script as the `ga_crawler` system user. Inside the script, line 46 does:
```bash
sudo -u ga_crawler /opt/ga_crawler/.venv/bin/python -m ga_crawler deliver-run --run-id "$RID"
```

Re-invoking `sudo` from inside an `unprivileged` user shell requires that user to be in `/etc/sudoers`. `useradd -r` (README §2 step 2) creates a system user with no sudo permissions — by design. The script will either:

- **Most likely:** Hit `sudo: a password is required` and abort (no TTY available, no NOPASSWD entry).
- Or: `sudo: ga_crawler is not in the sudoers file. This incident will be reported.` if not allowed at all.

Either way, step 3 (`deliver-run` → ops alert) of the SC#5 procedure never runs. The verification checklist in step 4 then describes outcomes that never materialised. SC#5 cannot be verified using the documented procedure.

Also, the inner `sudo -u ga_crawler` is **semantically redundant** even if it worked — we're already that user.

**Fix:** drop the inner `sudo -u ga_crawler`:
```bash
/opt/ga_crawler/.venv/bin/python -m ga_crawler deliver-run --run-id "$RID"
```

Or, if you want to be defensive against being launched as root:
```bash
if [[ "$(id -un)" != "ga_crawler" ]]; then
  echo "This script must run as ga_crawler (got $(id -un))" >&2
  exit 1
fi
/opt/ga_crawler/.venv/bin/python -m ga_crawler deliver-run --run-id "$RID"
```

Also adjust the inline canary in `tests/test_phase07_test_failure_alert_shape.py` — it currently checks for `deliver-run --run-id`, which is fine, but a regression canary for the privilege-redundancy would be useful:
```python
def test_script_does_not_self_sudo(script_text):
    """README §7 invokes script as ga_crawler; inner `sudo -u ga_crawler` is impossible
    (system user has no sudoers entry) and semantically redundant."""
    assert "sudo -u ga_crawler" not in script_text, (
        "script must not re-invoke sudo from within ga_crawler context"
    )
```

---

## Warnings

### WR-01: README §3 ENV table claims wrapper exits 3 on missing TG_BOT_TOKEN — false

**File:** `README.md:57,59,72`
**Category:** Documentation accuracy
**Issue:**

The ENV table (lines 56–60) and reserved-exit-codes table (lines 68–74) assert:

- `TG_BOT_TOKEN` — "Wrapper exits **3** если отсутствует"
- `TG_OPS_CHAT_ID` — "Отсутствие на ops route → exit **3**"
- Exit code `3` — "Missing `TG_BOT_TOKEN` / `TG_OPS_CHAT_ID` (config error)"

Looking at `src/ga_crawler/cli.py`:
- `_cmd_weekly` (the **subcommand the cron wrapper invokes**) returns only `0` (status==success) or `2` (anything else) — see `cli.py:118`.
- `_cmd_deliver` (the **standalone recovery subcommand** invoked manually for `deliver-run --run-id`) returns `3` only when `result.delivery_status == "skipped_no_credentials"` — see `cli.py:319-321`.

Therefore exit code `3` is **unreachable via `bin/weekly-run.sh`** in normal cron operation. It is reachable only via the standalone `deliver-run` path, which is not wrapped by `weekly-run.sh`. The wrapper does not validate TG_BOT_TOKEN itself.

Concretely: a fresh VPS with `.env` missing `TG_BOT_TOKEN` will run the cron job, hit `weekly-run`, complete the crawl, attempt delivery, log `skipped_no_credentials`, then return exit 0 (because `delivered_ops_only` and `skipped_no_credentials` both fall outside `success`, and `_cmd_weekly` returns 2 only when MainRunResult.status != "success"). Actually, status depends on D-605 — needs verification — but in any case it is not exit 3 from the wrapper.

**Fix:** rewrite §3 ENV table to disambiguate "wrapper passes through Python child exit code" from "wrapper's own validation":

| ENV | Wrapper validates? | Python `weekly-run` exit | Python `deliver-run` exit |
|-----|---|---|---|
| `TG_BOT_TOKEN` | No | 0 or 2 (delivery degrades to ops_only or pending) | 3 if missing |
| `TG_BUSINESS_CHAT_ID` | No | 0 (degrades to ops_only per D-611) | 0 (degrades to ops_only) |
| `TG_OPS_CHAT_ID` | No | 0 or 2 | 3 if missing AND ops-only routed |
| `HC_PING_URL` | **Yes — wrapper exits 4** (BUT see CR-01: actual exit is 1) | n/a | n/a |

Operationally this matters because operators reading "Wrapper exits 3 if TG_BOT_TOKEN missing" will look in the wrong place for the failure (wrapper logs, not Python child JSON).

---

### WR-02: README §9 `zgrep` example breaks `jq` parsing

**File:** `README.md:211`
**Category:** Documentation accuracy / Usability
**Issue:**

```bash
zgrep '"run_id":42' /var/log/ga_crawler/*.log.gz | jq .
```

`zgrep` over multiple files (`*.log.gz`) prepends each matched line with `filename:` (default behaviour, identical to `grep`). Output looks like:
```
/var/log/ga_crawler/weekly-run-2026-04-26.log.gz:{"event":"...","run_id":42,...}
```
which is not valid JSON, so `jq .` exits with `parse error: Invalid numeric literal at line 1, column XX` on the first line and aborts. Operator loses the entire history.

**Fix:** add `-h` (no-filename) to `zgrep`:
```bash
zgrep -h '"run_id":42' /var/log/ga_crawler/*.log.gz | jq .
```

Or use a per-file loop if filenames matter:
```bash
for f in /var/log/ga_crawler/*.log.gz; do
  echo "== $f =="
  zgrep -h '"run_id":42' "$f" | jq .
done
```

The other `grep '"level":"error"' ... | jq .` examples on a single file (lines 205, 208, 214) do not prepend filenames so they are correct.

---

### WR-03: README §9 `tail -f | jq .` example crashes on first non-JSON line

**File:** `README.md:205`
**Category:** Documentation accuracy / Usability
**Issue:**

```bash
tail -f /var/log/ga_crawler/weekly-run-$(date +%F).log | jq .
```

`bin/weekly-run.sh:65` redirects both `stdout` AND `stderr` to `$LOG_FILE`. structlog JSONRenderer writes valid JSON to stdout, but:
- `uv run` itself can emit `Installed N packages in Xms` to stderr.
- Camoufox / Playwright subprocesses can emit non-JSON stderr (browser console warnings, `[Firefox] ...` lines).
- Python tracebacks (rare but possible) are multi-line non-JSON.

`jq .` is strict — first non-JSON line aborts the stream. Operator's tail-watch session dies silently on the first interleaved non-JSON line.

**Fix:** wrap jq with input pre-filter to drop non-JSON lines, e.g.
```bash
tail -f /var/log/ga_crawler/weekly-run-$(date +%F).log \
  | grep --line-buffered '^{' \
  | jq .
```

or use jq's `--unbuffered` + `-R` (raw input) `try fromjson catch empty`:
```bash
tail -f /var/log/ga_crawler/weekly-run-$(date +%F).log \
  | jq -R --unbuffered 'try fromjson catch empty'
```

---

### WR-04: README §3 exit-code table description for code 2 is misleadingly narrow

**File:** `README.md:71`
**Category:** Documentation accuracy
**Issue:**

The table row reads:
```
| `2` | Undelivered (Telegram unreachable; retryable; xlsx остаётся на диске для повторной доставки через §8) |
```

But `_cmd_weekly` (`cli.py:118`) returns `2` for any non-success status, which includes:
- `sanity_gate_n_failed` (viled snapshot too small)
- `sanity_gate_m_failed` (goldapple snapshot too small)
- `sanity_gate_p_failed` (match rate too low)
- reporter `skipped`/`failed`
- delivery `undelivered_telegram_unreachable`
- delivery `delivered_ops_only` (success status from delivery POV but main_run may map differently)

An operator following the recovery recipe "re-run `deliver-run --run-id N`" for an exit-2 that was actually a sanity-gate trip will waste time (delivery is not the failure point; the snapshot is).

**Fix:** broaden the description and direct operator to `runs.reason` for disambiguation:
```
| `2` | Run did not reach success — any of: sanity-N/M/P gate trip, reporter failure, undelivered Telegram. Run `sqlite3 prices.db 'SELECT reason FROM runs WHERE run_id=N'` to disambiguate. |
```

---

### WR-05: `test-failure-alert.sh:42` run_id extraction silently crashes on empty/missing log

**File:** `bin/test-failure-alert.sh:42`
**Category:** Error-handling / Usability
**Issue:**

```bash
RID=$(tail -200 "$LOG_FILE" | grep -o '"run_id":[0-9]*' | tail -1 | grep -o '[0-9]*')
```

With `set -euo pipefail` active:
- If `$LOG_FILE` doesn't exist (e.g. step 1's wrapper hit flock-refused at exit 5 before any log was written, then step 1's `|| true` swallowed it), `tail` fails → pipefail → command substitution non-zero → `set -e` exits the script with a `tail: cannot open` error to stderr.
- If `$LOG_FILE` exists but contains no `"run_id":N` JSON event (e.g. wrapper exited at HC_PING_URL check before invoking Python), first `grep -o` exits 1 (no match) → pipefail → same result.

Either way, the operator sees an opaque exit, not a clear diagnostic. The script's own header (line 30) says "≠0 — script setup failed (e.g. log file missing, run_id unparseable)" — so this is **documented** but still a UX defect for an operator-runnable tool.

**Fix:** explicit guard with diagnostic:
```bash
echo "==> Step 2: Extract last run_id from log"
LOG_FILE="/var/log/ga_crawler/weekly-run-$(date +%F).log"
if [[ ! -f "$LOG_FILE" ]]; then
  echo "ERROR: log file $LOG_FILE not found — step 1 may have exited before writing." >&2
  echo "       Check for flock contention (exit 5) or missing HC_PING_URL (exit 4)." >&2
  exit 1
fi
RID=$(tail -200 "$LOG_FILE" | grep -o '"run_id":[0-9]*' | tail -1 | grep -o '[0-9]*' || true)
if [[ -z "$RID" ]]; then
  echo "ERROR: no run_id found in last 200 lines of $LOG_FILE" >&2
  echo "       Inspect manually: tail -200 $LOG_FILE | jq ." >&2
  exit 1
fi
echo "    run_id=$RID"
```

---

### WR-06: `weekly-run.sh:65` redirect fails opaquely if `/var/log/ga_crawler/` missing

**File:** `bin/weekly-run.sh:57,65`
**Category:** Error-handling / Operational robustness
**Issue:**

```bash
LOG_FILE="/var/log/ga_crawler/weekly-run-$(date +%F).log"
...
set +e
uv run python -m ga_crawler weekly-run "$@" >> "$LOG_FILE" 2>&1
EXIT=$?
set -e
```

If `/var/log/ga_crawler/` doesn't exist (operator skipped README §2 step 5), the `>>` open fails. Bash prints `bin/weekly-run.sh: line 65: /var/log/ga_crawler/weekly-run-2026-XX-XX.log: No such file or directory` to its **original** stderr — which under cron with `MAILTO=""` is discarded. With `set +e` active, the redirect failure becomes `EXIT=1`, and HC `/fail` is pinged with `exit=1` — conflating "log dir missing" with "wrapper missing" with "Python crashed early" with HC_PING_URL missing (CR-01).

**Fix:** ensure the log dir exists before redirect:
```bash
LOG_FILE="/var/log/ga_crawler/weekly-run-$(date +%F).log"
mkdir -p "$(dirname "$LOG_FILE")" || {
  echo "ERROR: cannot create log dir $(dirname "$LOG_FILE")" >&2
  exit 1
}
```

The README documents creating this dir manually (§2 step 5), but defense-in-depth: a single `mkdir -p` costs nothing and turns a silent failure into a louder one.

---

### WR-07: README §8 backup recovery procedure uses non-existent rotated filename pattern

**File:** `README.md:174`
**Category:** Documentation accuracy
**Issue:**

```bash
sudo -u ga_crawler cp /opt/ga_crawler/backups/YYYY-MM-DD.db /opt/ga_crawler/prices.db.restored
```

Per `bin/backup.sh:31-32`:
```bash
TIMESTAMP=$(date +%Y-%m-%d)
TARGET="$BACKUP_DIR/$TIMESTAMP.db"
```

The backup file's basename is `YYYY-MM-DD.db` (matches). But the wrapper README says (line 179) "Backups: `/opt/ga_crawler/backups/*.db` — 4-rotate retention". So the path is correct.

However, the procedure does not actually swap files — it copies to `prices.db.restored` but does not `mv prices.db prices.db.broken && mv prices.db.restored prices.db`. The operator is left holding a `.restored` file and the cron is re-enabled with the original broken DB. The recipe is incomplete.

**Fix:**
```bash
sudo systemctl disable cron --now
sudo -u ga_crawler mv /opt/ga_crawler/prices.db /opt/ga_crawler/prices.db.broken
sudo -u ga_crawler cp /opt/ga_crawler/backups/YYYY-MM-DD.db /opt/ga_crawler/prices.db
# Verify:
sudo -u ga_crawler sqlite3 /opt/ga_crawler/prices.db 'SELECT count(*) FROM runs;'
sudo systemctl enable cron --now
```

Also note: the README example uses `cp` rather than `sqlite3 ... .restore` (the WAL-safe online restore form). For an offline DB (cron disabled), `cp` is fine. For a live DB it would be wrong — but cron is disabled here.

---

### WR-08: README §2 step 7 `chmod 0600 .env` happens after the file was created — narrow but real race

**File:** `README.md:41-42`
**Category:** Security / Race condition
**Issue:**

```bash
sudo -u ga_crawler cp .env.example .env
sudo -u ga_crawler chmod 0600 .env
```

For the brief window between `cp` and `chmod`, `.env` exists with the **inherited umask permissions** (typically `0644`) — readable by all users on the box. The file at this point is identical to `.env.example` (no secrets yet), so the practical exposure is zero in this exact sequence. But if an operator follows this pattern for a non-trivial `.env` rotation later (`cp /tmp/new-env .env && chmod 0600 .env`), the secrets would briefly be 0644.

**Fix:** swap order or use `install`:
```bash
sudo -u ga_crawler install -m 0600 .env.example .env
```

`install -m` sets the mode atomically with file creation. This is also the form already used elsewhere in the README (§2 step 5 uses `install -d -m 0755 ...`), so the inconsistency is small.

---

### WR-09: Wrapper line 55 flock-refused path is silent in cron context (no HC ping)

**File:** `bin/weekly-run.sh:54-55`
**Category:** Observability gap
**Issue:**

```bash
exec 9>/var/lock/ga_crawler-weekly.lock
flock -n 9 || { echo "Another weekly-run holds the lock — refusing" >&2; exit 5; }
```

The `flock` failure path emits to stderr and exits 5 — but this happens **before** any HC ping is sent (HC `/start` is at line 60). Under cron with `MAILTO=""` (correct per Pitfall #2), stderr is discarded. HC.io sees nothing for that scheduled window. The dead-man's-switch grace period (2h per README §5) eventually fires — but operator has lost 2h of observability and has no signal that the failure was lock-contention vs. cron-not-running vs. host-down.

Concrete scenario: operator runs `bin/test-failure-alert.sh` Sunday afternoon (intentional contention test); cron fires Sunday 23:00; cron's invocation hits flock-refused → exit 5 → silent → HC dead-man's-switch fires Monday 01:00. Operator pages on "weekly cron never ran" when actually it was self-induced contention.

**Fix:** ping HC `/fail` with `exit=5` body before exiting on lock contention:
```bash
exec 9>/var/lock/ga_crawler-weekly.lock
if ! flock -n 9; then
  echo "Another weekly-run holds the lock — refusing" >&2
  curl -fsS -m 10 --retry 3 --data-raw "exit=5" "${HC_PING_URL}/fail" > /dev/null || true
  exit 5
fi
```

This requires HC_PING_URL to be validated first (line 50) — which the current code already does (the `:?` check runs before flock), so the ordering is correct. After the fix, lock-contention surfaces as a "fail" ping with body `exit=5` in HC dashboard instantly, not as a 2h dead-man's-switch.

---

## Info

### IN-01: `bin/weekly-run.sh:55` uses inconsistent error message format vs. project convention

**File:** `bin/weekly-run.sh:55`
**Category:** Style / Convention
**Issue:**

Error message uses an em-dash (U+2014) in source:
```bash
echo "Another weekly-run holds the lock — refusing" >&2
```

`bin/backup.sh` uses plain ASCII for error messages (`echo "ERROR: source DB not found: $DB_PATH" >&2`). Em-dash will render fine on UTF-8 terminals (Ubuntu default) but could be mangled in cron mail or in older terminal emulators. Project has not pinned a convention but the precedent (backup.sh) is ASCII-only.

**Fix:** prefer ASCII for log/error strings:
```bash
echo "ERROR: another weekly-run holds the lock — refusing" >&2
```

Or accept em-dash project-wide (UTF-8 is universal in 2026).

---

### IN-02: README §2 `useradd ... -s /bin/bash` — login shell is wrong for a system service user

**File:** `README.md:19`
**Category:** Style / Security hardening
**Issue:**

```bash
sudo useradd -r -m -d /opt/ga_crawler -s /bin/bash ga_crawler
```

`-s /bin/bash` gives `ga_crawler` an interactive shell. This is unnecessary (cron does not need a login shell; manual invocations via `sudo -u ga_crawler bash` still work because `sudo` forces the requested shell), and arguably weakens hardening (if SSH password auth ever gets misconfigured, this user is a viable target).

`/usr/sbin/nologin` is the conventional choice for system service users.

**Fix:**
```bash
sudo useradd -r -d /opt/ga_crawler -s /usr/sbin/nologin ga_crawler
# install dir + permissions explicitly (since we dropped -m, see CR-02):
sudo install -d -o ga_crawler -g ga_crawler -m 0755 /opt/ga_crawler
```

Note: `sudo -u ga_crawler bash -c '...'` still works because `bash -c` overrides the user's login shell. The README's existing usage patterns (line 22, 25, 27, 28) all use `sudo -u ga_crawler bash -c` or `sudo -u ga_crawler <command>` form — both compatible with `nologin` shell.

---

### IN-03: `test_phase07_env_example_shape.py:80` overly permissive `key.replace("_", "").isalnum()` filter

**File:** `tests/test_phase07_env_example_shape.py:80`
**Category:** Test robustness
**Issue:**

```python
key, _, value = stripped.partition("=")
if not key.replace("_", "").isalnum():
    continue
```

This skips lines whose `key` portion (before `=`) contains non-alphanumeric, non-underscore characters. Intent appears to be "skip lines that aren't real KEY=VALUE assignments". But the check is loose:
- Empty `key` (line starting with `=`) → `key.replace("_", "")` is `""`, `"".isalnum()` is `False`, so `not False` is `True` → skipped. OK.
- Leading whitespace on key was stripped via `stripped`, so OK.
- But `KEY-WITH-DASH=val` (uncommon) → `isalnum() == False` → skipped, even though it's a real assignment.

For Phase 7's known KEY set this is moot, but the filter is fragile. A simpler regex match would be cleaner:
```python
import re
if not re.match(r"^[A-Z_][A-Z0-9_]*$", key):
    continue
```

This documents the assumed ENV-name convention (uppercase + underscore + digits) explicitly.

---

### IN-04: `bin/test-failure-alert.sh` shebang convention conflict between project and CONTEXT.md verbatim

**File:** `bin/test-failure-alert.sh:1`, `bin/weekly-run.sh:1`
**Category:** Convention drift / documentation
**Issue:**

Both bash scripts use `#!/usr/bin/env bash` per project convention (matches `bin/backup.sh:1`). However:
- `07-CONTEXT.md` D-709 verbatim (line 94) shows `#!/bin/bash`.
- `07-03-SUMMARY.md` documents the divergence as a deliberate planner reconciliation ("Plan 03 D-1: Shebang divergence").
- The canary `test_wrapper_shebang_is_env_bash` enforces `#!/usr/bin/env bash`.

So the divergence is **documented and intentional**. No code defect — but the CONTEXT.md "Required shape" wording is now out-of-sync with the implementation and the canary. Future readers comparing CONTEXT.md to wrapper source will be briefly confused.

**Fix:** either (a) annotate `07-CONTEXT.md` D-709 with a note "shebang reconciled to project convention per 07-03 SUMMARY D-1" so the verbatim block is no longer authoritative, or (b) just leave it — the SUMMARY is the source of truth and a careful reader will follow the trail. Low priority.

---

_Reviewed: 2026-05-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
