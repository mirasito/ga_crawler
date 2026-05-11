---
phase: 03-goldapple-crawl
reviewed: 2026-05-11T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - src/ga_crawler/fetchers/goldapple.py
  - src/ga_crawler/runner/gates.py
  - tests/integration/test_goldapple_fetch_loop_mocked.py
  - tests/unit/test_smoke_probe.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 3 Plan 03-09: Code Review Report

**Reviewed:** 2026-05-11
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found
**Scope:** Cold-start `Loading`-race gap-closure (plan 03-09, commits 9e4f3b4..bc76fed)

## Summary

The retry-once gap-closure is **structurally sound** — Pitfall 7 cleanup invariant is preserved, the retry decision shape (`status==200` AND `block==False` AND `'loading '` AND NOT `'checking device'`) correctly excludes both gate-shell and non-200 failure modes, and the test matrix exercises each rejection branch.

However, there is **one Critical defect** that breaks the very invariant plan 03-09 was supposed to enforce: the gate-shell rejection in `_is_loading_race` uses the substring `"checking device"`, but the fetcher's gate-poll loop (`fetch_one` line 297) strips the gate title much earlier by polling for the marker `"checking"` (declared in `goldapple_microdata.GATE_TITLE_MARKER`). The two-word check in `gates.py` will silently accept any gate-shell whose page-title says only `Gold Apple — checking` (no `" device"` suffix) — turning a real fingerprint failure into a retry-and-mask. The tests do not catch this because every gate-shell fixture happens to use the longer "checking device" string.

The remaining findings are smaller robustness issues (`asyncio.sleep` not injectable in `smoke_probe`; `_compute_price_extracted` calls `parse_pdp` on every record even when not needed; `phase3_smoke_probe_retry` does not log the retry *outcome*; `WARMUP_SETTLE_SECONDS` runs even when warm-up succeeded fast). All are fixable; none should block the next operator run on their own, but the Critical must be addressed before plan 03-09 is considered closed.

---

## Critical Issues

### CR-01: `_is_loading_race` gate-shell rejection drifts from the project-wide gate marker

**File:** `src/ga_crawler/runner/gates.py:129`
**Issue:**
The function rejects gate-shells with:

```python
if "checking device" in title_l:
    return False
```

But the canonical gate marker for the project is `GATE_TITLE_MARKER = "checking"` (parsers/goldapple_microdata.py:39), and `fetch_one` polls for `GATE_TITLE_MARKER not in last_title.lower()` (fetchers/goldapple.py:297). The 7-character substring `"checking"` is what `detect_state` and the fetcher's gate-poll loop consider "gate-shell".

Consequence: a real fingerprint failure that emits a title like `"Gold Apple — checking"` (no `" device"` suffix) will:
1. Satisfy `"loading "` lookup? No — but consider a title `"checking… Loading https://..."` or any GroupIB variant whose Russian/localised text omits `device`. The retry-once layer will treat it as a Loading-race, sleep 1 s, and re-probe — exactly the behaviour Operational Finding #2 was explicitly written to forbid.
2. Even if such a title never appears in production, the test `test_smoke_probe_no_retry_on_gate_shell` only asserts the *current* operator-observed string. The invariant the docstring claims to enforce — "gate-shell is a real fingerprint failure, must fail-fast per D-312" — is one Cloudflare/GroupIB challenge-page revision away from being violated silently.

This is the same coupling defect (two independent string constants for "gate-shell title") that the project already paid for once when `GATE_TITLE_MARKER` was hoisted out of the spike notebook.

**Fix:** Reuse the canonical constant, and key the rejection off `block`/`block_reason` too (defence-in-depth):

```python
from ga_crawler.parsers.goldapple_microdata import GATE_TITLE_MARKER
# ...
def _is_loading_race(rec: Any, price_extracted: bool) -> bool:
    if not isinstance(rec, dict):
        return False
    if rec.get("status") != 200:
        return False
    if price_extracted:
        return False
    if rec.get("block", True):
        return False
    if rec.get("block_reason") == "gate_shell_not_cleared":
        return False  # defence-in-depth; should already be excluded by block check
    title = rec.get("title") or ""
    title_l = title.lower()
    if "loading " not in title_l:
        return False
    if GATE_TITLE_MARKER in title_l:   # matches `checking`, `checking device`, etc.
        return False
    return True
```

Add a regression test that supplies title `"Gold Apple — checking"` (no `device`) and asserts no retry fires.

---

## Warnings

### WR-01: `asyncio.sleep(1.0)` in `smoke_probe` is not injectable — slows the whole pytest matrix by 1 s per retry test

**File:** `src/ga_crawler/runner/gates.py:178`
**Issue:**
`smoke_probe` hard-codes `await asyncio.sleep(1.0)` for the inter-attempt back-off. Tests cannot inject a no-op sleep, so `test_smoke_probe_retries_once_on_loading_race` (and any future retry-positive test) pays the full second of real wall-clock time. The fetcher's `run_loop` already learned this lesson and takes a `sleep_fn` parameter (fetchers/goldapple.py:335) — `smoke_probe` should follow the same pattern.

Reading the current test: `test_smoke_probe_retries_once_on_loading_race` does not use `freezegun`, does not monkeypatch `gates.asyncio.sleep`, and does not assert that the back-off elapsed — so a future "speed up the suite" change could accidentally remove the sleep and the test would not notice.

**Fix:** Add an optional `sleep_fn: Optional[Callable[[float], Awaitable[None]]] = None` parameter to `smoke_probe`, default to `asyncio.sleep`, and call `await sleep_fn(1.0)` in the retry branch. Update the two retry tests to pass a recording fake and assert it was awaited exactly once with `1.0`.

---

### WR-02: `_compute_price_extracted` re-invokes `parse_pdp` on already-blocked records — wastes work and re-runs the heavy selectolax parse on every smoke URL

**File:** `src/ga_crawler/runner/gates.py:84-97`
**Issue:**
The helper unconditionally calls `parse_pdp(html, url)` whenever `rec["html"]` is truthy. But in `smoke_probe`, the retry branch and the diagnostics packaging both invoke this helper *once per attempt*, even for records where `block is True` (gate-shell — no `html` attached) or for records where the retry already established `price_extracted=True`. On the happy path (3 URLs) this is 3 × `parse_pdp(~200KB HTML)` calls; with `selectolax` that is fine, but it is also unnecessary and slightly muddies the cost model.

More importantly: `parse_pdp` can raise — there is no try/except wrapper here. A schema-drift exception (renamed `itemprop`) inside `parse_pdp` will propagate out of `_compute_price_extracted` and abort the entire smoke probe with an uncaught exception, defeating the "smoke probe reports diagnostics, never crashes the run" contract that D-312 implies.

**Fix:**
1. Short-circuit when `rec.get("block")` is truthy or `html` is falsy (return `(False, None)` immediately).
2. Wrap `parse_pdp` in `try / except Exception as e: log.warning("smoke_probe_parse_error", url=url, error=str(e))` and return `(False, html)`.

---

### WR-03: `phase3_smoke_probe_retry` logs first-attempt diagnostics but never logs the retry *outcome* — operator cannot tell from logs whether the retry helped

**File:** `src/ga_crawler/runner/gates.py:171-180`
**Issue:**
The structlog event records first-attempt `title/size/status`, but after `await asyncio.sleep(1.0)` and the second `fetch_one`, there is no `phase3_smoke_probe_retry_complete` (or equivalent) event capturing `second_attempt_status / title / price_extracted / recovered`. The only signal the operator has post-hoc is the aggregate `smoke_probe_complete` boolean. For a feature whose stated purpose is empirical observability of a transient race (UAT Test 6), this is a regression in introspection vs the original spike.

Without the post-retry event, a future increase in "retry fires but does not help" rate is invisible until the smoke probe outright fails — exactly the slow-creep regression mode D-310 warns against.

**Fix:** Emit a second event after the retry returns:

```python
await asyncio.sleep(1.0)
rec = await fetcher.fetch_one(fetcher._page, url)
price_extracted, _ = _compute_price_extracted(rec, url)
log.info(
    "phase3_smoke_probe_retry_complete",
    url=url,
    second_attempt_status=rec.get("status") if isinstance(rec, dict) else None,
    second_attempt_title=rec.get("title") if isinstance(rec, dict) else None,
    recovered=price_extracted,
)
```

Add a test asserting the event fires with `recovered=True` on the happy-recovery path.

---

### WR-04: `WARMUP_SETTLE_SECONDS` sleep runs even after warm-up succeeded quickly — pure overhead on every boot

**File:** `src/ga_crawler/fetchers/goldapple.py:222-235`
**Issue:**
The comment says "Settle ALWAYS runs — race is bounded to first nav, even if networkidle stalled." That is correct in the failure case (networkidle raised, total elapsed ≈ 15 s, the +2 s tail is fine). But on a healthy boot, the `goto(WARMUP_URL, wait_until="networkidle")` returns in ~1-3 s, and then a fixed 2 s `asyncio.sleep` is added on top — a 70-200 % overhead on the warm-up step relative to what's needed.

This is not a correctness bug, but: (a) every cron run now pays at least 2 s of dead time; (b) the magic number `2.0` is not justified anywhere in the gap-closure plan against any timing measurement. UAT Test 6 evidence (run-3 + run-4) shows the race resolves within ~1 s of `networkidle` settling, so 2 s is precautionary, not measured.

**Fix:** Either:
- Make the settle time conditional: only sleep `max(0, WARMUP_SETTLE_SECONDS - warmup_goto_elapsed)` when goto succeeded, full `WARMUP_SETTLE_SECONDS` only when goto raised; OR
- Add a comment citing the measurement that produced `2.0`, OR a STATE.md entry justifying it as a budget.

Note: the existing test `test_warmup_goto_failure_does_not_abort_boot` only asserts the sleep ran *at all*, not its duration — it would still pass under either fix.

---

### WR-05: `_make_retry_decorator` swallows ImportError-after-import — defensive code masks the wrong failure mode

**File:** `src/ga_crawler/fetchers/goldapple.py:83-89`
**Issue:** (Outside the explicit plan 03-09 scope but the warm-up code lives in the same `__aenter__` and depends on `playwright.async_api.TimeoutError`'s behaviour.)
The fallback `class PWTimeout(Exception): pass` is defined only when `playwright.async_api` is missing. But in production, Camoufox brings playwright; the only realistic place the fallback fires is in a misconfigured dev env. In that case, retries silently no-op on timeouts (the fallback class will never be raised by anyone). Test coverage for this branch is zero.

Strictly speaking this code is **outside the plan-03-09 scope marker** — flagging informationally because the warm-up `goto` failure mode in `__aenter__` (line 222) catches *any* `Exception` and so is not affected. Out of scope for this review's "fix list" — log for plan-03-10 hardening.

**Fix:** Defer; tag `WR-05` and revisit when retry hardening returns.

---

## Info

### IN-01: `_compute_price_extracted`'s `url` parameter is unused for the success path but used by `parse_pdp`

**File:** `src/ga_crawler/runner/gates.py:84`
**Issue:** Reads cleanly, but the `(price_extracted, html)` tuple's second element is never used by `smoke_probe`. The function is over-built for its one caller. Consider returning just `price_extracted: bool` and inlining the `html` extraction at the call site, or document the intended second-caller.

**Fix:** Optional — drop unused return or document why the tuple shape exists (defensive: future debug log).

---

### IN-02: `_compute_price_extracted` does `product.current_price > 0` but `current_price` is typed `int` and `parse_pdp` validates `100..1_000_000` range

**File:** `src/ga_crawler/runner/gates.py:96`
**Issue:** `GoldappleRawProduct.current_price` is `int` and `parse_pdp` already enforces `100..1_000_000` sanity range (PARSE-04). The `> 0` check is therefore dead-code-equivalent — it cannot fire in any successful parse. Not wrong, just redundant.

**Fix:** Replace `product is not None and product.current_price > 0` with simply `product is not None`. (Or, if you want to keep the belt-and-braces, add a comment citing PARSE-04 so the next reader understands the redundancy is intentional.)

---

### IN-03: Russian-prose-style docstring "Operational Finding #1" labels are inconsistent across files

**File:** `src/ga_crawler/runner/gates.py:101, 155, 159` and `src/ga_crawler/fetchers/goldapple.py:48`
**Issue:** The same fix is variously cited as "Operational Finding #1", "D-314", "cold-start `Loading` race", "Cold-start Loading race", and "UAT Phase 3 Test 6". Future grep-archaeology will be harder than it needs to be.

**Fix:** Pick one canonical label (suggest: `D-314 (Operational Finding #1)`) and use it everywhere. Optional — chase down at next docs sweep.

---

### IN-04: Test `test_smoke_probe_retries_once_on_loading_race` does not assert the back-off elapsed

**File:** `tests/unit/test_smoke_probe.py:141-205`
**Issue:** The test verifies `len(call_log) == 4` and that URL[0] was called twice, but it does not assert that an `asyncio.sleep(1.0)` actually fired between the two attempts. A future refactor that removes the back-off entirely would not be caught.

**Fix:** Once WR-01 is implemented (inject `sleep_fn`), assert the fake recorded exactly one call with `1.0`.

---

## Verification of in-scope invariants

These were checked and **hold** (no findings):

- **Pitfall 7 (Camoufox-boot failure cleans profile dir):** confirmed — `__aenter__` wraps page-capture + warm-up in `try/except` that runs `shutil.rmtree(self.profile_dir, ignore_errors=True)` before re-raising. `test_camoufox_boot_failure_cleans_profile_dir` exercises this explicitly.
- **Warm-up `goto` failure is best-effort:** confirmed — exception is caught at line 228, logged, and the settle sleep + boot continue. `test_warmup_goto_failure_does_not_abort_boot` exercises this and additionally asserts the profile_dir survives warm-up failure but is cleaned on normal `__aexit__`.
- **D-312 strict-gate invariant preserved:** `passed = all(price_extracted) and all(status in (200, 304) and not block)` (gates.py:197-200) is unchanged in spirit. Retry-once narrows only the *Loading-race shape*, not the pass criteria.
- **Retry does not fire on gate-shell / non-200 / pre-blocked:** confirmed via `test_smoke_probe_no_retry_on_gate_shell` + `test_smoke_probe_no_retry_on_non_200` + the `rec.get("block", True)` guard in `_is_loading_race` (gates.py:123). Subject to CR-01.
- **No leaked tasks / `_page` races between probe attempts:** sequential `await` chain — no concurrency. Safe.
- **`camoufox_booted` event payload extended:** `warmup_url` + `warmup_elapsed_ms` present (fetchers/goldapple.py:247-248). `camoufox_warmup_networkidle_timeout` emitted on warm-up failure with bounded `repr(...)[:200]`. Good.
- **Test isolation:** smoke_probe tests construct a fresh `MagicMock` fetcher per test; fetcher tests construct fresh `GoldappleFetcher(run_id=...)` per test with separate tmp dirs. No shared state.

---

_Reviewed: 2026-05-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Scope: plan 03-09 only (cold-start Loading-race gap-closure)_
