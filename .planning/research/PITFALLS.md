# Pitfalls Research — v1.1 Parser Fixes + Live-HTML Harness + KZ Operator Deploy

**Domain:** Parser fixes against drifting live websites; live-HTML test harness construction; operator deploy of an existing scraper to KZ-region VPS (Yandex Cloud) vs EU (Hetzner CX22)
**Researched:** 2026-05-13
**Confidence:** HIGH on harness/cassette antipatterns + parser-fix overfitting (multi-source 2024-2026 retrospectives). HIGH on .env loading + cron TZ specifics (already burned by D-705 / SCHED-02 in v1.0). MEDIUM on Yandex Cloud KZ + Camoufox interaction (region launched 2024, limited corpus). MEDIUM on Healthchecks.io accessibility from KZ (no documented blockers, but no positive verification either).

> Scope note: pitfalls are ordered by how likely they are to either (a) recur in v1.1 or (b) hide silently and waste a Sunday. Each pitfall is wired to a concrete v1.1 phase candidate in the final mapping. v1.0's PITFALLS.md covered the *building* phase — this document covers the *fixing + deploying* phase, which has a different failure surface.

---

## Critical Pitfalls

### Pitfall 1: Fixing the parser against one PDP screenshot — works for `STEREOTYPE sago`, breaks for 50 other brand shapes

**What goes wrong:**
Developer reads `v1.1-PARSER-BUG-FINDINGS.md`, sees the `STEREOTYPE sago` evidence, writes a regex `^([A-ZА-Я]+)\s+(.+)$` that splits uppercase-brand from lowercase-name. Ships. Run #14 fails on:
- **Multi-word brands**: `TOM FORD private blend` → captures `TOM` as brand, drops `FORD`.
- **Mixed-case brand designation**: `Diptyque tam dao` (cap-then-lower) → regex doesn't match at all → empty brand again.
- **Brand with ampersand or apostrophe**: `Dolce & Gabbana light blue`, `L'Occitane shea butter` → splits at the wrong token.
- **Numeric brand names**: `19-69 capri`, `27 87 oneness` → digit-prefix breaks character-class assumption.
- **Russian brand collisions with Russian product name**: `НАТУРА СИБИРИКА крем для рук` — both brand and name in caps Cyrillic if the title is fully shouted.
- **Brand that contains the product name verbatim** (already in DB sample): `Armaniarmani code` — the duplication is the *symptom*, not a fluke; the goldapple SSR-template emits brand twice and the heuristic must dedupe rather than split.

Net effect: parser-fix appears to work in dev review (the one fixture passes), regresses 30-60% of the goldapple catalog in run #14, match-rate stays at 0%, and the operator is back to staring at an empty xlsx Monday morning. The 803-test suite still passes because no test covers the new shapes.

**Why it happens:**
- The PDP screenshot is **N=1 evidence**, but the developer treats it as the schema definition. Goldapple's SSR template emits the brand as a structured field elsewhere on the page (per the live PDP `STEREOTYPE` brand badge); regexing the title is solving the wrong problem.
- "Fix what's in front of you" is the cheapest dopamine loop; sampling 20 brands and listing variants first feels like wasted time.
- The bug report shows the ONE shape that broke; the developer doesn't ask "what other shapes exist?"
- E-commerce data is wildly heterogeneous: industry retrospectives report scrapers need weekly fixes on 10-15% of selectors, and the dominant cause is single-page-redesign-extrapolation. See [BinaryBits: Why Your Web Scraper Keeps Breaking](https://binarybits.co/blog/why-web-scraper-keeps-breaking).

**How to avoid:**
- **Sample-first protocol**: Before writing parser code, fetch 30+ live PDPs across stratified brand categories (lux/mass-market/niche/Russian/Western), dump to `.planning/spikes/v1.1-brand-name-shapes/`, eyeball the title field as a list. Categorise into shape buckets. THEN design the parser.
- **Prefer structured fields over title heuristics**. The PDP renders a brand badge `<a class="brand-link">STEREOTYPE</a>` (or whatever the actual structure) — use *that* selector, not a regex on `<h1>`. The volume bug is the same pattern: there's a structured `[78] ОБЪЁМ / МЛ` block — target it directly, don't regex the name.
- **Property-based tests with hypothesis or a hand-built brand-shape table**: parameterize the parser test over 30+ live brand titles capturing every shape variant. The new test file becomes the spec.
- **Equivalence-class assertion**: After parsing, `assert brand.lower() not in name.lower()` — catches the Armani-in-name regression class as a universal invariant.
- **Goldapple's own product schema, if any**: re-check 2026-05-13 PDP HTML for OpenGraph `og:title` / `og:brand` meta tags; SPA microdata can drift but OG tags rarely do (used by social previews → stable).

**Warning signs:**
- Test suite is green but match_rate < 30% on goldapple ⇄ viled overlap (D-405 KPI canary).
- DB sample of last run shows brand-column populated for <80% of goldapple SKUs (the 88/88 NULL is the loud version; the silent version is 70/88 NULL).
- `len(brand) <= 2` for any SKU (single letter or empty — likely the heuristic captured the wrong token).
- Same SKU appears with different parsed brands across runs (heuristic is unstable, not deterministic).

**Phase to address:**
**Phase 1 (Parser-fix research + sampling)** — must include 30-PDP eyeball survey + shape-table BEFORE Phase 2 ships code.
**Phase 2 (Parser-fix code)** — implement structured-selector approach + parameterized tests on shape-table.

---

### Pitfall 2: Live-HTML cassettes captured once and never refreshed → harness goes stale and tests pass on dead fixtures

**What goes wrong:**
v1.1 adds a `pytest-recording` (or vcrpy) harness that records goldapple/viled HTML responses into `tests/cassettes/`. First-run cassettes capture 2026-05-15 HTML. Tests pass. CI gets green. Sunday rolls around in 2026-08-20 — goldapple has redesigned the PDP template twice in between — and `pytest` is still cheerfully replaying the May fixture. Run #28 hits the new template, parser fails, match-rate drops to 0%. The harness gave **false confidence** instead of catching the drift it was added to catch.

This is the meta-pitfall: the cure for "tests pass on frozen fixtures while live HTML drifts" can itself become "tests pass on slightly-less-frozen fixtures while live HTML drifts."

**Why it happens:**
- pytest-recording defaults to `record-mode=none` (replay-only) to prevent accidental network calls. Devs don't reset it without a flag/cron job. See [pytest-recording docs](https://github.com/kiwicom/pytest-recording).
- Refreshing cassettes is a manual `pytest --record-mode=rewrite` step that nobody puts on their calendar.
- Cassettes get committed to git; once committed they look "official" and authoritative.
- The harness purpose (catch drift) gets lost; cassettes get treated as test inputs, not drift detectors.
- Industry retrospectives: silent failures via stale fixtures account for ~40% of production scraper outages in 2025 ([Grepsr: Testing vs Production](https://www.grepsr.com/blog/web-scraping-testing-vs-production/)).

**How to avoid:**
- **Cassette-age canary**: a unit test asserts `max(cassette.mtime for cassette in tests/cassettes/) > now - 14 days` (or whatever cadence). Test fails CI when cassettes are stale → forces refresh before merge.
- **Weekly automated cassette refresh job**: a separate cron entry (or GitHub Action with VPS secret) runs `pytest --record-mode=rewrite tests/live_html/` weekly. Diffs the cassette dir and posts to ops chat. PR-bot opens a review if diffs are non-trivial.
- **Two-tier test classification**:
  - **Tier A — unit tests** against frozen synthetic HTML in `tests/fixtures/` (fast, deterministic, run on every commit). These verify *parser logic*.
  - **Tier B — live-HTML cassette tests** in `tests/live_html/` with cassettes refreshed weekly. These verify *parser-vs-current-site*. Mark with `@pytest.mark.live` and only run in a nightly/weekly job, not on every commit.
  - **Tier C — true live tests** that hit the real site (no cassette). Run weekly pre-deploy or after suspicious diff. Marked `@pytest.mark.live_no_cassette`.
- **Cassette-diff is the signal**: weekly refresh produces a diff PR. If `tests/cassettes/*.yaml` diff is non-empty, the site changed. Reviewer either updates parser, updates expectations, or notes "irrelevant CSS change."
- **Document the refresh ritual** in README + CLAUDE.md as an explicit invariant: "cassettes refreshed weekly via `make refresh-cassettes` or via the Sunday post-run job."

**Warning signs:**
- `git log tests/cassettes/` shows no commits in >30 days while live runs still execute weekly.
- Tests pass green but live run #N parses 0% of expected volumes (cassettes don't reflect the structural change).
- New developer joins, runs `pytest` locally → passes; runs `weekly-run.sh --viled-only --sanity-gate-n 1` → reports empty.
- `--record-mode=rewrite` produces large unexpected diffs that nobody triages.

**Phase to address:**
**Phase 3 (Live-HTML harness)** — must implement the three-tier classification AND the cassette-age canary AND the refresh job (or document the weekly manual ritual). Skipping the refresh side ships a Pitfall #2 generator.

---

### Pitfall 3: Cassettes capture sensitive data — auth tokens, session cookies, anti-bot challenge cookies — get committed to git

**What goes wrong:**
Developer captures a goldapple PDP cassette during a session that also did a Healthchecks.io ping and a Telegram-send-test. The recorded yaml file contains:
- `cf_clearance` cookie value (Cloudflare anti-bot session) — leakage might let an attacker piggyback on the bypass.
- `X-Hc-Ping-Key` query string in URL → committed to public repo → free wrapper for DDoS.
- Bot token in an Authorization header from a debugging Telegram call.
- Camoufox/Patchright user-agent + fingerprint — less catastrophic but still telegraphs setup.

The cassette is committed by a developer who skimmed the file ("looks like HTML, fine"), the PR merges, the secret is now in git history forever. By the time it's noticed, the secret has been rotated → but the cassette commit still triggers GitGuardian alerts.

Per CLAUDE.md, repo is private *now* — but the cost-of-leak is asymmetric and the repo may go public in the future.

**Why it happens:**
- vcrpy/pytest-recording record **everything** by default — request headers, cookies, response Set-Cookie, query strings. See [Redacting secrets and PII from VCR.py cassettes](https://imoskvin.com/blog/redacting-vcrpy-cassettes/).
- Developers don't review yaml cassettes line-by-line; they trust the recording.
- `git add tests/cassettes/` is bulk-add by convention.
- `.gitignore` patterns for `.env` / `secrets/` don't cover cassette content (it's serialized inside a yaml).
- Cassettes for "anti-bot tests" inherently capture anti-bot artifacts → the exact thing you don't want public.

**How to avoid:**
- **Configure `before_record_request` / `before_record_response` filters in conftest.py from day-1**:
  ```python
  @pytest.fixture(scope="module")
  def vcr_config():
      return {
          "filter_headers": [
              ("authorization", "REDACTED"),
              ("cookie", "REDACTED"),
              ("set-cookie", "REDACTED"),
              ("x-bot-token", "REDACTED"),
          ],
          "filter_query_parameters": ["api_key", "ping", "uuid"],
          "filter_post_data_parameters": ["password", "token"],
          "before_record_response": redact_response_body,  # strip cf_clearance from body too
      }
  ```
- **Pre-commit hook with `detect-secrets` or `gitleaks`** scanning `tests/cassettes/`. CI gate that fails the PR if a candidate secret is detected.
- **Cassette PII scan canary**: a unit test loads every `*.yaml` in `tests/cassettes/` and asserts known-bad regex patterns (UUID-like ping tokens, `cf_clearance=`, `Authorization: Bearer`, Telegram bot-token format `\d{9,10}:[A-Za-z0-9_-]{35}`) are absent.
- **Smaller default capture surface**: cassettes for *parser* tests don't need anti-bot challenge headers — only the final HTML body. Configure vcrpy to drop request/response headers entirely for parser-focused cassettes (`record_mode="new_episodes"` plus a request/response transformer that strips everything except body).
- **Manual review checklist on PR**: every cassette-touching PR asks "have you skimmed for secrets?" — codify in `.github/PULL_REQUEST_TEMPLATE.md`.

**Warning signs:**
- Cassette yaml contains `cf_clearance=` literal, `Authorization: Bearer` literal, `bot\d+:` token shape, or `hc-ping.com/` UUID in a query string.
- `git diff` on a cassette commit shows >50% of changed lines are headers/metadata (vs body content).
- `detect-secrets scan` flags `tests/cassettes/`.
- GitHub Secret Scanning sends an automated alert.

**Phase to address:**
**Phase 3 (Live-HTML harness)** — redaction config + canary must ship in the same plan that introduces the harness. Adding redaction *after* cassettes are committed is rotate-everything cleanup.

---

### Pitfall 4: Live HTML loads via JS race conditions → harness flaky → "flaky tests" gets normalized → real drift hides

**What goes wrong:**
Goldapple PDP renders title in SSR (in initial HTML) but renders the volume block via client-side JS hydration. Camoufox captures the page on `domcontentloaded` event ~600ms — sometimes the volume `<div>` is hydrated, sometimes not. Cassette test passes 7/10 runs and fails 3/10 with `volume_norm=None`. Devs add `@pytest.mark.flaky(reruns=3)` and move on.

Six weeks later: the goldapple template change that *did* break volume extraction looks identical to the existing flake — same `volume_norm=None` symptom — and gets silenced by the flake-retry. The harness has trained itself to mask the very class of bug it was added to detect.

Same risk for viled.kz: `__NEXT_DATA__` is in the HTML but the rendered DOM also has volume in a hydrated panel; if the parser walks both paths and one is conditional on JS, captures will diverge.

**Why it happens:**
- Camoufox/Patchright wait strategies are imperfect: `wait_until="domcontentloaded"` returns before lazy-loaded sections render; `networkidle` is unreliable on sites with long-poll connections; explicit `wait_for_selector` only works if you know the selector.
- Phase 1 v1.0 spike found cold-start "Loading…" race already — same family of bug.
- Flake-retry decorators (`pytest-rerunfailures`, `pytest-flaky`) are designed to hide intermittent failures from CI noise → they will hide *real* intermittent failures too.
- Developers normalize "retry 3 times" as a virtue ("CI is more stable now") rather than a debt.

**How to avoid:**
- **Capture cassettes with deterministic wait conditions**: explicit `await page.wait_for_selector("[data-testid='volume-block']", timeout=15s)` or whatever the real anchor is. If selector doesn't exist on this page-type (e.g. hair brush has no volume), branch explicitly, don't fall through.
- **Cassettes are deterministic by construction**: once recorded, the cassette IS the request/response pair. Flakiness from cassette playback indicates a *parser non-determinism* (e.g. parser uses `dict` iteration order, or asserts position-of-element on a multi-block page) — fix the parser, not the test.
- **Ban `@pytest.mark.flaky` in `tests/live_html/`** via grep canary in CI. Force the cause to be diagnosed.
- **Two-capture verification**: when refreshing a cassette, capture twice 30 seconds apart. Diff. If diff is non-trivial (more than timestamp / nonce), the page is non-deterministic in a way that breaks parser assumptions → either the parser walks the page wrong or the wait strategy is wrong. Don't ship until diff stabilizes.
- **Save the screenshot alongside the cassette**: `tests/cassettes/goldapple-stereotype-sago/page.html` + `page.png` + `page.har`. Visual diff for the developer; HAR for network-level inspection.

**Warning signs:**
- Any test in `tests/live_html/` decorated with `flaky`/`rerun` markers.
- `pytest --record-mode=rewrite` produces volatile diffs (different content each run).
- Cassette playback failure rate >5% in nightly job.
- Tests that "sometimes pass, sometimes fail" are accepted as normal.

**Phase to address:**
**Phase 3 (Live-HTML harness)** — wait-strategy + flake-ban canary belong in the harness scaffold. **Phase 2 (Parser fix)** also needs to verify parsers don't depend on JS-only DOM that may not be in the cassette.

---

### Pitfall 5: Drift detection only watches the SKUs that worked yesterday — site adds a new category that bypasses the brand-intersect filter, silently shrinking the dataset

**What goes wrong:**
v1.0 goldapple crawl uses `intersect_brand_pool` to limit goldapple URLs to brands present on viled. Site introduces a new category "Корейская косметика" with brand `MIXSOON` not on viled yet. Goldapple slug pattern changes from `/<brand>/<sku>` to `/korean/<brand>/<sku>` for items in this new top-level path. The `intersect_brand_pool` bucket index (Path A from Wave-7 gap-closure plan 03-08) was tuned to longest-prefix-in-whitelist on the old slug pattern — new pattern falls through, those URLs never enter the crawl frontier. We never notice because *the brands we already had still work*.

Six months later commercial team asks "почему у нас нет матча на Korean skincare? У goldapple их полно" — discovery via user complaint, not via alerting.

**Why it happens:**
- Drift detection is usually shaped like "compare today's parse vs yesterday's parse on the same URLs." It cannot detect URLs that *never enter* the frontier.
- The brand-intersect filter is a v1 cost-control mechanism (don't crawl irrelevant brands); the assumption that "irrelevant today = irrelevant tomorrow" is unstated and unverified.
- Sitemap drift is a separate failure mode from PDP drift — different parser, often missed.
- Industry retrospective: "field-level completeness failures, when not actively monitored, are discovered on average 3-5 days later through downstream reporting discrepancies" ([extralt: Ecommerce scraping in 2026](https://extralt.com/blog/ecommerce-web-scraping)). For unknown-categories it's months, not days.

**How to avoid:**
- **Sitemap delta canary**: weekly job re-downloads `goldapple.kz/sitemap.xml` (or whatever the master URL index is), compares against last-week's sitemap, logs:
  - new top-level path segments (e.g. `/korean/` is new)
  - new slug-pattern shapes (regex-equivalence-class of slugs)
  - SKU count delta per top-level category
- **Brand-discovery widening**: alongside `intersect_brand_pool`, run a tiny **"reconnaissance" crawl** that samples 10 random URLs per top-level category every week and dumps brand names found. If a brand appears >3 weeks in a row that's NOT on viled, flag for review — could be a category viled should expand into.
- **Don't conflate "no match" with "no SKU"**: matcher already separates `goldapple_total_count` from `match_count`. Add a third metric `goldapple_categories_seen` (count distinct top-level path segments). If this drops to a number lower than last week, alert.
- **Anti-bot-on-subset**: goldapple may eventually challenge *only the new category* (different WAF rule). Smoke-probe must rotate across categories, not just hit the same warm URL.

**Warning signs:**
- `goldapple_total_count` from sitemap parse drops or holds flat while site is observably adding products (manual spot-check).
- New goldapple URLs appearing in browser autocomplete that the crawler never visits.
- Sitemap diff job (if implemented) flags new path segments.
- Reports go from "X% match-rate" to "X% match-rate" week after week but commercial team complains coverage feels narrow.

**Phase to address:**
**Phase 4 (Drift detection extensions)** — sitemap-delta canary + brand-discovery widening. Cannot be addressed only in parser-fix phase because parsers see only the URLs they're given.

---

### Pitfall 6: D-705 .env loading pitfall recurs — Python child sees stale env when invoked directly (root cause of run #13 `delivery_status=skipped_no_credentials`)

**What goes wrong:**
Already burned us in run #13. Operator runs `python -m ga_crawler deliver-run --run-id 13` directly from a fresh shell that doesn't have `TG_BOT_TOKEN` exported. Bash wrapper `bin/weekly-run.sh` does `set -a; source .env; set +a` correctly — but the direct CLI invocation bypasses the wrapper. Python's `os.environ` doesn't auto-load `.env`; `python-dotenv` only loads if the code explicitly calls `load_dotenv()`. Result: `delivery_status=skipped_no_credentials`, ops alert fires, operator scratches head ("I have a .env right there...").

In v1.1 this recurs if:
- The new live-HTML harness shells out to a Python helper that needs `TG_BOT_TOKEN` for a smoke message → child doesn't see it.
- Phase audit paperwork generation runs a one-off `python -m ga_crawler audit-foo` → no .env load.
- Operator deploys to new VPS, tests `deliver-run` manually before cron handoff → silent skip.

**Why it happens:**
- Python `subprocess.run([...])` inherits parent `os.environ` by default, but if parent shell never sourced `.env`, child sees nothing. Bash `source` is *not* automatic.
- `python-dotenv` is library-level — only loads when imported and called. CLI entrypoints sometimes import it and sometimes don't; inconsistency across subcommands.
- Wrapper-only contract is invisible: nothing in the Python code says "this requires bash wrapper context" → operator who reads `python -m ga_crawler deliver-run --help` gets no warning.
- See [Python subprocess env pitfall](https://github.com/python/cpython/issues/120836) — Windows-specific but the inheritance model bites cross-platform when parent env is partial.

**How to avoid:**
- **`load_dotenv(verbose=True)` at CLI entrypoint** — `src/ga_crawler/__main__.py` or `cli.py` calls `python-dotenv` unconditionally for every subcommand, idempotent (no-op if vars already set). This makes the CLI work standalone without the bash wrapper.
- **Fail-loud preflight**: each subcommand that needs Telegram credentials calls `assert_env(["TG_BOT_TOKEN", "TG_BUSINESS_CHAT_ID"])` early; on miss, log `"missing TG_BOT_TOKEN; if running standalone, did you `source .env` or have you populated .env at $CWD?"` and exit with a documented code (3 for deliver-run per README §3).
- **Single canonical source-of-truth for env contract**: a `.env.example` with comment headers grouping vars by subcommand. Test (canary) that asserts every var referenced by `os.environ[...]` in source code is documented in `.env.example`.
- **Operator runbook update**: README §7 "Operations runbook" recovery recipes already shell out to `python -m ga_crawler ...`. Each one must either (a) document `export $(grep -v '^#' .env | xargs)` as prerequisite OR (b) rely on the in-Python `load_dotenv()` fix above. Pick (b) — less for the operator to remember.
- **Canary test**: assert that `python -m ga_crawler deliver-run --help` in a clean shell with `.env` present in CWD produces the same env-contract output as via wrapper — proves the CLI loads `.env` on its own.

**Warning signs:**
- `delivery_status=skipped_no_credentials` in a run that completed everything else.
- Operator manually runs a recovery subcommand and the run silently degrades.
- New subcommand added by a phase reads env-vars but doesn't call `load_dotenv()`.

**Phase to address:**
**Phase 5 (Operator deploy)** — `load_dotenv()` at CLI entrypoint must be added BEFORE first VPS deploy, otherwise the first manual recovery on the VPS hits this. Co-locate with operator runbook update.

---

### Pitfall 7: Cron timezone gotcha — Yandex Cloud KZ default TZ might be Moscow (UTC+3) not Almaty (UTC+5), `CRON_TZ` invariant becomes critical

**What goes wrong:**
Operator deploys to Yandex Cloud Almaty zone. Yandex Cloud Ubuntu images historically default to `Europe/Moscow` (Russian-headquartered company, Russian default). Cron file from `deploy/etc-cron-d-ga_crawler` has `CRON_TZ=Asia/Almaty`, which Vixie cron respects file-scoped — good. BUT bash scripts inside the run might call `date +%F` to construct log filenames, and `date` uses the system `/etc/timezone`. Result:
- Cron fires at Almaty Sunday 23:00 (correct).
- Log filename becomes `weekly-run-2026-05-18.log` because system TZ says Moscow, where it's still 21:00 Sunday — fine.
- BUT: logrotate runs at `06:25 system-TZ`, which is `08:25 Almaty` — different from documented "Monday 06:25 UTC" assumption in README §7 logrotate edge cases.
- Healthchecks.io schedule was set to `cron 0 23 * * 0 Asia/Almaty` — pings arrive as expected.
- BUT: HC.io dashboard timestamps might display in operator's browser TZ, which the team in Almaty reads as their local time → consistent.
- AND: `bin/backup.sh` rotation logic uses `date +%F` for filenames — if system TZ is Moscow, two consecutive Almaty days could share a backup filename (rare edge but possible).

The pitfall is **mixed TZ layers** — cron is file-scoped, but bash `date` is system-scoped, and Python `datetime.now()` is system-scoped. They diverge under stress.

**Why it happens:**
- `CRON_TZ` only scopes the cron daemon's schedule interpretation; it does NOT export `TZ=` to the spawned child process.
- Yandex Cloud images often default to `Europe/Moscow`, sometimes `UTC`. Hetzner CX22 defaults to UTC. Different starting point → different cron drift class.
- Camoufox/Firefox uses its own TZ-spoof for fingerprint (Camoufox can be configured with a target locale that doesn't match the system) — yet another layer.
- Operator deploys to Yandex Cloud, sees first cron tick fire at the expected wall-clock time, assumes correct, doesn't check that downstream timestamps agree.

**How to avoid:**
- **Standardize system TZ at deploy**: README §2 step 1.5 add `sudo timedatectl set-timezone Asia/Almaty` between OS deps install and ga_crawler user create. Idempotent + visible. **Adds belt-and-braces over the `CRON_TZ` invariant.**
- **Canary test**: assert that the cron template line `CRON_TZ=Asia/Almaty` AND a README line documenting `timedatectl set-timezone Asia/Almaty` both exist. Source-lock both shapes.
- **TZ-aware log filename test**: assert `bin/weekly-run.sh` uses `date +%F` AND that the operator setup ensures system TZ matches `CRON_TZ`. Or migrate to `TZ=Asia/Almaty date +%F` inside the wrapper to make it explicit (preferred — survives wrong system default).
- **Python datetime audit**: any `datetime.now()` (naive) call in v1.1 new code → reject in code review. Use `datetime.now(tz=ZoneInfo("Asia/Almaty"))` or `datetime.now(tz=timezone.utc)` explicitly.
- **Healthchecks.io schedule verify**: README §5 step 4 already says timezone `Asia/Almaty` — keep, AND add post-deploy verification: trigger one manual run, check HC dashboard shows "last run was N minutes ago" matching wall-clock-Almaty (catches a mis-configured timezone in HC settings).

**Warning signs:**
- Log filename day-of-week disagrees with the actual day the run fired (`weekly-run-2026-05-18.log` containing a Sunday run that fired Sunday 23:00 Almaty would still look like Monday in Moscow TZ — confusing).
- Backups rotate at unexpected wall-clock times.
- HC.io alerts arrive "off-schedule" relative to user expectation.
- Two backup files share a date suffix.

**Phase to address:**
**Phase 5 (Operator deploy)** — TZ-normalization step added to README + canary on cron-template invariant.

---

### Pitfall 8: Yandex Cloud Kazakhstan vs Hetzner EU — IP geography helps goldapple anti-bot but introduces new compatibility unknowns for Camoufox/Firefox stack

**What goes wrong:**
Operator picks Yandex Cloud KZ (Karaganda DC, launched April 2024) because "KZ IP will help goldapple anti-bot." After deploy:
- **Outbound bandwidth pricing surprise**: Yandex Cloud charges per-GB egress; goldapple crawl ~500 MB/week — manageable but operator didn't budget.
- **Camoufox/Firefox binary** built for a slightly different libc / glibc / Mesa stack than the Yandex Cloud base image (often a slightly older Ubuntu variant or custom kernel). Firefox 142 fork might fail to launch with cryptic `libxslt` / `libstdc++` errors. Worked on Hetzner Ubuntu 24.04, breaks on Yandex Cloud.
- **DC IP block flagged anyway**: Yandex Cloud Karaganda IPs are *datacenter* ASN, not residential. Cloudflare/DataDome bot-detection databases catalog ASN, not country. Result: same 403 challenge from goldapple as Hetzner Falkenstein — KZ geography didn't help because the IP is still a known DC.
- **Healthchecks.io reachability**: HC.io runs on Hetzner bare-metal in EU. Outbound HTTPS from Yandex Cloud KZ → HC.io EU should work but routes through Russia first; if any geopolitical filtering hiccups happen (rare but documented for Russia↔EU routes 2022-2025), HC pings could drop intermittently. Dead-man's-switch then fires false alarms.
- **Egress to api.telegram.org**: Telegram is unblocked in KZ as of 2026 (last block was Russia 2018-2020, not KZ), but Yandex Cloud network policies might have implicit filtering for `t.me` / `api.telegram.org` since Yandex is Russian-corporate; unverified.
- **Egress to PyPI** (for `uv sync`): goes through European mirrors via Russia; intermittent slowness.

**Why it happens:**
- "KZ IP solves goldapple" is an assumption, not a verified fact. v1.0 spike showed `Camoufox-direct, 99/100, no proxy needed` from Hetzner — there was NEVER a proven need for KZ IP.
- Yandex Cloud KZ is new (2024 launch), small corpus of community deployments, edge cases not well documented.
- Camoufox is a fork-of-fork-of-Firefox; its binary linkage assumptions track its build host, not yours.
- Different cloud providers have different egress quirks; Russian-headquartered ones have different geopolitical exposure than EU/US providers.

**How to avoid:**
- **Re-read v1.0 RECON-01 spike memo** (2026-05-06) before picking provider. Camoufox-direct from Hetzner already works — there is **no evidence** that KZ IP is required. Default = Hetzner CX22 EU per README §2 unless v1.1 surfaces concrete anti-bot regression.
- **If Yandex Cloud is chosen**: smoke-test Camoufox binary launch BEFORE wiring cron. Concrete steps:
  ```bash
  sudo -u ga_crawler /opt/ga_crawler/.local/bin/uv run python -c \
    "from camoufox.async_api import AsyncCamoufox; import asyncio; \
     asyncio.run(AsyncCamoufox().__aenter__())"
  ```
  Capture exit code, dynamic-library errors, missing-deps. If failure, escalate via `apt install <missing-libs>` BEFORE proceeding past README §2 step 4.
- **Verify outbound paths**: from VPS run `curl -I https://hc-ping.com/test`, `curl -I https://api.telegram.org/bot111:test/getMe`, `curl -I https://goldapple.kz/`. All three must return non-zero meaningful response. Latency >2s to HC.io → consider alternate monitor (Better Uptime, etc).
- **Recovery path documented**: README adds an explicit "if KZ IP fails too" runbook entry — residential proxy (Decodo / IPRoyal, ~$8-15/GB) configured via env-var, single config switch, no code change.
- **Pre-commit to Hetzner**: stretch v1.1 ships Hetzner. v2 (only if needed) revisits KZ-region after evidence accumulates.

**Warning signs:**
- Camoufox launch fails on first VPS smoke-test with library error.
- HC.io pings successful from local dev box but intermittent from VPS.
- Goldapple smoke-probe returns Cloudflare interstitial despite KZ IP (proves the geography hypothesis wrong).
- Telegram `getMe` returns 403 or hangs (cloud-network filtering).
- Outbound bandwidth charges show up in Yandex Cloud billing > $10/month for our 500MB/week footprint.

**Phase to address:**
**Phase 5 (Operator deploy)** — provider-choice decision + smoke-test gate BEFORE moving past README §2 step 4. If `--provider=yandex` is chosen, ADD a compatibility-smoke phase plan.

---

### Pitfall 9: Cassettes grow unbounded → repository bloat → CI slows → developers stop running tests locally

**What goes wrong:**
Each goldapple PDP cassette is ~30-50 KB of HTML; if Phase 3 captures 30 brand-shape variants × 2 retailers × multiple page-types (PDP / catalog / sitemap) → 200+ cassettes × 50 KB = ~10 MB. Then refresh-weekly job appends new cassettes (different file names for different SKUs sampled this week) → 50 MB by month 3. Then someone records full catalog pages (5 MB each) → 500 MB. Repo balloons.
- `git clone` takes minutes (was seconds).
- `pytest tests/live_html/` reads gigabytes of yaml → slow startup → devs skip running it locally → drift hides.
- Git history bloats with binary-ish yaml diffs → `git log -p` unusable.
- CI cache invalidates on every cassette refresh.

**Why it happens:**
- vcrpy serializes the entire HTTP exchange; HTML bodies are the bulk and they don't compress in yaml.
- Cassettes captured for "let me verify this one thing" tend to accumulate; nobody deletes.
- The shape-table from Pitfall #1 wants 30+ samples per retailer — that's the *minimum* corpus, not the maximum.
- No `tests/cassettes/.gitattributes` filter → text-diff treats yaml as text → noisy diffs.

**How to avoid:**
- **Cassette size budget canary**: assert `sum(size for f in tests/cassettes/*) < 50 MB`. Fail CI if exceeded. Forces curation.
- **Per-shape-class cassette**: keep ONE cassette per *shape* (e.g. `goldapple-volume-structured-block.yaml`), not one per SKU. Add SKU-specific cassettes only when documenting a specific bug. Drop the cassette once the fix ships unless it's representative of a permanent shape class.
- **Strip response bodies of irrelevant noise pre-record**: HTML can be downsampled to "just the part the parser touches" — extract `<div data-component="pdp-main">` subtree, drop CSS, drop scripts. Cassette becomes 2-5 KB instead of 50 KB. Doable via vcrpy `before_record_response` hook.
- **Compress with git LFS** if cassettes must be full HTML — moves bulk out of main git history. Adds a deploy step (`git lfs install`) but keeps the repo lean.
- **Quarterly cassette purge**: scheduled to delete cassettes >6 months old that aren't referenced by any test. Force re-record on next refresh.

**Warning signs:**
- `du -sh tests/cassettes/` > 20 MB.
- `git clone` time visible to user as a wait.
- CI `pytest tests/live_html/` runtime > 60 seconds.
- Developer says "I'll skip the live tests, takes too long."
- `git log --stat` shows cassette files in nearly every commit.

**Phase to address:**
**Phase 3 (Live-HTML harness)** — size canary + per-shape-class discipline in the initial design. Adding curation after bloat is much costlier.

---

### Pitfall 10: Audit paperwork done after-the-fact loses fidelity (v1.0 retrospective lesson — and v1.1 ships SECURITY/VALIDATION for phases 2/4/6 retroactively)

**What goes wrong:**
v1.0 retrospective explicitly flags: "SECURITY.md was only generated for phases 3, 5, 7. VALIDATION.md only for 2, 3, 5, 6, 7." Now v1.1 has to generate **SECURITY.md for phases 2/4/6 + VALIDATION.md for phase 4** as carryover.

The pitfall: writing security threat models for code that already shipped is essentially **code-review-flavored-as-paperwork** — the threats already either materialized or didn't. Without the prospective discipline ("what if X attacker tries Y?"), the doc becomes a defensive justification of what was built rather than a critique of what could be attacked.

Worse: v1.1 might apply the same "do it later" pattern to its own new artifacts (parser-fix SECURITY, harness SECURITY, deploy VALIDATION) → repeats the trap.

**Why it happens:**
- "Code first, paper later" is the universal default; paperwork has lower dopamine and feels like overhead.
- `/gsd-complete-milestone` discovers the gap at milestone close — too late to influence design.
- Retrospective SECURITY analyses often pass the verdict gate because the worst-case threats didn't materialize *yet*, not because they were designed out.
- v1.0 retrospective specifically calls this out as the dominant reason v1.0 closed `tech_debt` not `passed`.

**How to avoid:**
- **`/gsd-secure-phase` and `/gsd-validate-phase` as phase-close prerequisites**, not milestone-close. v1.1's `/gsd-execute-phase` or `/gsd-transition` workflow should refuse to proceed past phase N until phase N's SECURITY.md + VALIDATION.md are present.
- **Threat model written BEFORE code in each phase**: the threat list informs test design, not the other way around.
- **Retroactive phases use a different verdict bar**: SECURITY/VALIDATION written for already-shipped code should explicitly note "retroactive — threats inferred not designed-against, recommend pen-testing or chaos exercises to compensate."
- **Pair carryover with new work**: v1.1 SECURITY for phase-2 viled parser is a 2-page doc; pairing it with phase-2-parser-fix-of-v1.1 forces the author to think about new code AND retrospective code in the same session.

**Warning signs:**
- Phase N+1 starts before phase N's audit paperwork exists.
- Milestone audit verdict comes back `tech_debt` with paperwork items.
- SECURITY.md for a shipped phase contains zero "this threat is currently exploitable" findings (probably means rubber-stamp).
- VALIDATION.md doesn't link to specific test files / canaries.

**Phase to address:**
**All phases of v1.1** — workflow-level enforcement. Specifically: **Phase 6 (Audit carryover)** to ship the v1.0 retroactive docs as a *distinct phase* rather than as background work.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Fix parser against single PDP screenshot ("ship it, see if it works Sunday") | 1-day turnaround | Pitfall #1 regression: works for 1 brand shape, breaks 50 others; back-and-forth across 3+ weekly runs | Never for goldapple/viled in v1.1. Acceptable for one-off ops scripts that crawl ≤10 URLs. |
| Capture cassettes once, never refresh | Tests stay green | Pitfall #2: harness becomes lie | Only for parser-internal-logic tests that don't depend on live HTML structure. Synthetic-fixture tests are fine forever. |
| `@pytest.mark.flaky(reruns=3)` on live-HTML tests | Green CI badge | Pitfall #4: real drift hides behind retry-noise | Never on `tests/live_html/`. Acceptable on Telegram-send tests that hit real API (rate limits cause real flakiness). |
| Commit cassettes without redaction config | Saves 30min of config | Pitfall #3: rotate-everything-and-cleanup-git-history if secrets leak | Never. Add redaction config in same PR that introduces cassettes. |
| Run parser-fix without sampling 30+ shapes first | Skip "wasted" survey day | Pitfall #1 | Never for the goldapple bugs explicitly cited in v1.1-PARSER-BUG-FINDINGS.md (Armani-prefix, volume-block, viled volume_raw). |
| Deploy to Yandex Cloud KZ without Camoufox launch-smoke | Saves 1h of pre-deploy testing | Pitfall #8: first cron tick fails Sunday night, debugged Monday morning at 2am | Never. Always smoke-test browser binary on a new image. |
| Defer .env `load_dotenv()` to "real CLI rework later" | Saves 1h, "wrapper already handles it" | Pitfall #6: silent skipped_no_credentials on every manual recovery | Never if the CLI is operator-facing. Acceptable for internal dev-only entrypoints. |
| Audit paperwork after milestone close | Phase work feels faster | Pitfall #10: `tech_debt` verdict + retroactive docs of weaker quality | Never per v1.0 retrospective lesson. Always run `/gsd-secure-phase` and `/gsd-validate-phase` at phase close. |
| Skip sitemap-delta canary "because we have brand-intersect filter" | Less monitoring surface | Pitfall #5: new categories invisible for months | Acceptable in v1 (already shipped); must close in v1.1 or v1.2. |
| Hardcode `mtime`-based cassette age expectation as literal date string in test | Quickest implementation | Test will start failing 14 days after commit, blocking unrelated PRs | Never. Use relative window (`now - 14 days`). |

---

## Integration Gotchas

Common mistakes when connecting v1.1 new code to v1.0 surfaces.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| New parser code ↔ existing `ParseDispatcher` (D-14 routing) | Adding a third parser strategy (JSON-LD fallback?) without updating dispatcher → silent unrouted SKUs | Extend dispatcher first, add unit test for new route, then add parser. Dispatcher test should fail loud on unrouted shapes. |
| Live-HTML harness ↔ existing 803 unit tests | Harness imports same fixtures dir → cassette pollution into synthetic-fixture tests | Strict directory separation: `tests/fixtures/` (synthetic, frozen) vs `tests/cassettes/` (live, refreshed). Different conftest fixtures, different marker namespace. |
| Cassette tests ↔ Camoufox fetcher | Tests directly invoke real Camoufox to record → CI requires browser binary, slow | Cassettes recorded against any HTTP backend that hits the live site; replay path uses a thin mock client that responds from cassette. Decouple recording-time backend from replay-time backend. |
| Parser-fix matcher integration ↔ v1.0 `denormalized matches` schema (D-401) | Parser now emits a structured `brand` field; matcher still uses old key composition that strips brand from a concatenated string | After parser-fix, re-derive matcher's `make_key()` from the new `brand`/`name`/`volume` fields explicitly. Add canary that asserts `make_key(brand="Armani", name="armani code", volume="...")` doesn't accidentally re-concatenate. |
| New volume extractor ↔ v1.0 `NORM-03` normalizer | Volume now comes from a structured block as `"75"` (just digits, no unit) → existing regex `(\d+)\s*(?:мл|ml|г|g)` returns None because no unit | Normalizer accepts `(volume_raw: str, unit_hint: Literal["ML","G","..."] = None)` — caller passes hint when known. Existing regex-on-name path still works for viled-style data; structured-block path passes hint. |
| Live-HTML harness CI ↔ existing GitHub Actions / CI config | Harness needs Playwright/Camoufox binaries on CI runner → CI fails or skips silently | Either: split CI into "unit" (no browser) and "live" (browser) workflows OR run harness only on a self-hosted runner (VPS, post-deploy). Skip-with-warning is acceptable; skip-silent is not. |
| Telegram delivery from VPS ↔ Yandex Cloud KZ egress | `aiogram` async client hangs on `api.telegram.org` if Yandex Cloud has implicit egress filter | Smoke-test `getMe` from VPS BEFORE wiring cron. Document fallback: route Telegram through HTTP proxy if direct egress is filtered. |
| HC.io pings from VPS ↔ wrapper exit codes | Wrapper exits before HC.io ping fires on hard-crash (already mitigated D-701 by pinging from bash, not Python) | Verify v1.1 doesn't add a Python-only ping path; HC pings stay in bash per D-701. New code uses bash to ping if needed. |
| Backup cron ↔ live-HTML cassette refresh cron | Both write to `/opt/ga_crawler` concurrently → SQLite WAL contention or git race | Run cassette refresh from a separate working tree (`/opt/ga_crawler-test/`) or as a non-cron operator-initiated task. Don't co-schedule with backup or weekly-run. |

---

## Performance Traps

Patterns that work at small scale but fail as cassette-volume and run-frequency grow.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading every cassette in conftest.py session-scope fixture | Pytest startup 30s+; devs skip local runs | Module-scope fixture per cassette file; lazy yaml deserialize | ~50 cassettes (~5 MB), Pitfall #9 |
| Recording cassettes against real Camoufox each run | CI run > 10 min; bandwidth cost to goldapple; Sunday ops drift | Record once locally, replay in CI. Refresh job is separate. | First merge that adds >5 live tests |
| Storing full PDP HTML in cassettes (with images base64'd, scripts, CSS) | Cassettes 200 KB+ each; repo bloat | `before_record_response` strips `<script>`, `<style>`, images. Body becomes ~5 KB. | First 20 cassettes |
| Diff-based drift detection re-parses every snapshot in DB on every run | Run wall-time grows O(history); week 50 takes 30+ minutes | Compare only against `v_current_snapshots` view (last run per SKU) — already exists in v1 schema. | Run #50 or so |
| Sitemap-delta canary loads full sitemap into memory | OOM on Hetzner CX22 4GB if sitemap >100k URLs | Stream-parse with lxml `iterparse` or splitting strategy. | If goldapple sitemap >200K URLs (currently 45K per v1.0 Wave-7) |
| Cassette refresh job in same git working tree as production | Mid-refresh race between cron weekly-run and cassette-refresh causes file lock errors | Refresh in `/opt/ga_crawler-test/` (separate clone). Push cassette updates via PR. | First Sunday where refresh and run overlap |
| Property-test brand-shape table loaded as Python list at module import | Test collection time > 5s, IDE intellisense lags | Use `pytest.mark.parametrize` with `indirect=True` and a fixture that yields per-row. | 100+ shape rows |
| Camoufox launched per-test in pytest | Each test 5-10s startup; full suite 30+ min | Session-scope Camoufox fixture; reset cookies between tests | First 10 live-no-cassette tests |

---

## Security Mistakes

Domain-specific security issues for parser-fix + harness + KZ deploy work.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Commit cassette containing `cf_clearance` cookie | Attacker piggybacks on anti-bot bypass; in extreme case rate-limit shared with abuser | Pitfall #3 redaction config; pre-commit `detect-secrets` |
| Commit cassette containing `hc-ping.com/<uuid>` URL | Anyone with repo access can spoof success/failure pings → mask real outages | Filter `hc-ping.com` from query params; redact path segments matching UUID regex |
| Commit cassette containing `https://api.telegram.org/bot\d+:...` | Bot token leak → attacker sends messages to business chat as our bot | Filter `bot\d+:` in URL path; pre-commit gitleaks scan |
| Yandex Cloud VPS without firewall → SSH open to world | Compromised, scraper hijacked for botnet | `ufw allow 22/tcp; ufw enable` BEFORE first `weekly-run.sh`; preferably restrict SSH to known IPs |
| `.env` committed accidentally (history retention) | Long-lived bot token leak | `.gitignore .env`; pre-commit `gitleaks`; verify `git ls-files | grep -E "^\.env$"` is empty in canary |
| Cassette refresh job runs as root | Single bug → full system compromise | Refresh runs as `ga_crawler` user; sudo limited to single deploy commands |
| Storing residential proxy credentials in cassettes (if Tier-3 escalation is added) | Proxy credential leak ≈ paying for someone else's traffic | Strip `Proxy-Authorization` headers; never log full proxy URLs |
| Live-HTML cassettes log scraping evidence (e.g. timestamps, user-agent rotation patterns) that goldapple's legal team could subpoena if scraping dispute arises | Legal exposure if KZ-legal review (deferred to v2 per PROJECT.md) goes wrong | Keep cassette commit messages neutral ("update goldapple fixture"); keep `.planning/` private; don't tag cassettes with anti-detection-specific labels in public files |
| Parser-fix code reads/writes outside `/opt/ga_crawler/` (e.g. `os.path.expanduser("~")` leaks home dir) | Privilege escalation on shared infra; cron-user confusion | Path-canary: assert all file I/O is within `/opt/ga_crawler/` or `/var/log/ga_crawler/` |

---

## UX Pitfalls

Common operator/team UX mistakes specific to v1.1 scope.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Empty xlsx delivered to business chat (Sunday morning sees empty file) | Lost trust; pricing team assumes scraper broken; manual fallback | Hard-gate at delivery: if `match_count == 0` OR `goldapple_total_count == 0`, route to ops-only with explicit failure reason; never deliver empty xlsx to business chat. (Already partially in v1.0 D-611; v1.1 should harden the threshold.) |
| Cassette refresh job posts noisy diffs to ops chat every week | Ops chat fatigue; alerts ignored | Filter diff noise: only post if cassette content (not just timestamp/order) differs; weekly digest, not per-cassette message |
| Parser-fix verification asks operator "did Sunday's run look right?" — operator can't tell from xlsx alone | Discovery delay; another bad week | Auto-compute parse-quality KPIs in weekly summary: `% volumes parsed`, `% brands non-empty`, `% match-rate`. Display in Telegram summary, not just xlsx. |
| Failure-test (SC#5 per README §6) shows up as real alert in HC dashboard, ops marks each "expected" manually | Alert fatigue; one Sunday a real failure gets marked "expected" by reflex | Test-failure script auto-tags HC.io alert as `test` via UI label OR uses a separate HC check `ga_crawler test-failure` per [HC docs configuring_checks] |
| New cassette-refresh PR opens automatically every week → reviewer fatigue | PR-approval rubber-stamping risks merging real-drift cassette changes without parser update | Bot opens PR only if diff is non-trivial AND parser tests still pass against new cassettes (auto-validation). If parser breaks against new cassette, PR labeled `drift-detected` and assigned to maintainer. |
| Yandex Cloud KZ deploy README assumes Russian-language Yandex docs are accessible — operator clicks through to broken/Russian-only pages | Setup friction; doc abandonment | README links only to English-language Yandex Cloud docs OR pre-screenshot critical steps |

---

## "Looks Done But Isn't" Checklist

Things that appear complete in v1.1 but may be missing critical pieces. Use during phase verification.

- [ ] **Parser fix shipped for `STEREOTYPE sago` shape:** Often missing 30-shape regression coverage — verify `tests/unit/test_goldapple_brand_extraction.py` has parametrized cases for `multi-word brand`, `ampersand brand`, `numeric brand`, `Cyrillic-caps brand`, `brand contains name verbatim`, `samples-size/multipack`, `gift-set`, `out-of-stock-SKU`.
- [ ] **Live-HTML harness installed:** Often missing the **refresh job** — verify `bin/refresh-cassettes.sh` exists AND a cron/CI schedule fires it weekly AND cassette-age canary test exists.
- [ ] **Cassettes committed:** Often missing **redaction config** — verify conftest.py has `filter_headers`, `filter_query_parameters`, and a canary test scans cassettes for known-bad regex.
- [ ] **Volume extraction fixed:** Often missing **categorization for volumeless SKUs** (hair tools, brushes, gift cards) — verify parser exposes `is_volumeless=True` for these and matcher honors it; verify volume-null-rate KPI is computed and gated.
- [ ] **Brand extraction fixed:** Often missing **invariant assertion** `brand.lower() not in name.lower()` post-parse — verify canary.
- [ ] **Sitemap-delta drift detection:** Often missing **alert path** — verify diff is posted somewhere (ops chat, dashboard, log-grep canary), not just computed silently.
- [ ] **Operator deploy doc updated:** Often missing **provider-fork** (Hetzner vs Yandex Cloud) explicit decision recorded — verify README §2 has a "If you chose Yandex Cloud KZ instead" sub-section OR a doc-only spike memo locks the choice.
- [ ] **`load_dotenv()` at CLI entrypoint:** Often missing **canary test** — verify `python -m ga_crawler deliver-run --help` with `.env` in CWD and `TG_BOT_TOKEN` only in `.env` actually loads (test via subprocess in fresh shell context).
- [ ] **First Sunday production cron tick verified:** Often missing **verifier resume of phase-7 UAT** — verify `/gsd-verify-work 7` was rerun post-tick and converted blocked items to pass.
- [ ] **SECURITY/VALIDATION carryover docs for phases 2/4/6:** Often missing **threat-link-to-test mapping** — verify each documented threat has a test or canary that exercises it (not just prose).
- [ ] **Cassette canary catches `cf_clearance` / `bot\d+:` / `hc-ping.com/UUID`:** Often missing — explicit regex set in `tests/test_cassette_redaction.py`.
- [ ] **Camoufox launch-smoke on target VPS:** Often missing — verify operator runbook lists `uv run python -c "from camoufox..."` smoke step BEFORE first `weekly-run.sh`.
- [ ] **CRON_TZ + system TZ both Asia/Almaty:** Often missing **system-TZ check** — verify README §2 step 1.5 adds `timedatectl set-timezone Asia/Almaty` AND that a canary asserts both invariants.
- [ ] **Match-rate KPI gates v1.0 D-405 still active:** Often broken by v1.1 if matcher formula changes — verify D-405 source-lock canary still green AND parser-fix didn't inadvertently boost match-rate via false positives (e.g. fuzzy fallback sneaking in).
- [ ] **Three-tier test classification (unit / cassette / live):** Often missing **CI awareness** — verify `pyproject.toml` `[tool.pytest.ini_options]` markers documented AND default `pytest` invocation runs only unit (fast), with explicit opt-in for cassette/live tiers.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **#1 Parser-fix overfits, regresses week N+1** | MEDIUM (1-2 day rework + re-run) | (a) `/opt/ga_crawler/.venv/bin/python -m ga_crawler matcher-run --run-id N` after parser hotfix (D-412 idempotent); (b) hotfix is itself a Phase-2 follow-up plan, not a milestone; (c) post-mortem captures the missed shape class → add to parametrized test corpus. |
| **#2 Stale cassettes** | LOW (1 hour) | `pytest --record-mode=rewrite tests/live_html/`; commit diff; if diff is enormous, file a "parser-fix-needed" ticket; meanwhile cassette-age canary keeps red until resolved. |
| **#3 Secret committed to cassette** | HIGH (rotate + git-history-rewrite) | (a) Rotate the leaked secret IMMEDIATELY (`@BotFather /revoke` for Telegram, regen HC.io ping URL, etc); (b) `git filter-repo --path tests/cassettes/X.yaml --invert-paths` to scrub history; (c) force-push (only if you own the only remote); (d) add the redaction config in same PR; (e) GitGuardian/secret-scan re-audit. |
| **#4 Flake-decorator hiding drift** | MEDIUM (find the masked failures) | (a) Remove all `@pytest.mark.flaky` from `tests/live_html/`; (b) run suite; (c) any test that fails has a real issue — bisect parser vs cassette vs wait-strategy. |
| **#5 Sitemap drift unnoticed for months** | MEDIUM (1 week to add canary, 1 month for parsers to widen) | (a) Snapshot today's sitemap as baseline; (b) implement diff canary; (c) when canary fires, prioritize parser/matcher widening as a milestone-scoped plan. |
| **#6 `skipped_no_credentials` on manual recovery** | LOW (1 hour) | (a) Hotfix `load_dotenv()` in CLI entrypoint; (b) re-run `python -m ga_crawler deliver-run --run-id N`; (c) canary test added in same PR. |
| **#7 TZ mismatch caused wrong-day filenames** | LOW (1 hour for fix, log filenames stay confusing for current week) | (a) `timedatectl set-timezone Asia/Almaty`; (b) verify next run's filename + `date +%F` agree; (c) accept that historical `weekly-run-2026-MM-DD.log` filenames for the affected window are off-by-day. |
| **#8 Yandex Cloud Camoufox launch fails** | MEDIUM (1-3 days; might require provider switch) | (a) Capture exact lib error; (b) `apt install` missing deps; (c) if still failing, try Patchright as fallback; (d) if still failing, revert to Hetzner EU and accept the IP-geography unknown. |
| **#9 Repo bloat from cassettes** | MEDIUM (1 day for migration to LFS or curation) | (a) Inventory cassette sizes; (b) downsample bodies via the `before_record_response` hook; (c) re-record everything; (d) consider `git lfs migrate` for historical bloat. |
| **#10 Audit paperwork tech-debt at milestone close** | LOW per phase, HIGH cumulative | (a) Stop new phase work; (b) run `/gsd-secure-phase` and `/gsd-validate-phase` for the carryover phases; (c) only after all phases have audit docs, resume new work. |

---

## Pitfall-to-Phase Mapping

How v1.1 roadmap phases should address these pitfalls. Phase numbering is suggested ordering — roadmapper may re-order based on dependencies.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| #1 Parser-fix overfits to one PDP shape | **Phase 1 (Parser-fix research / sampling)** | 30-shape table exists in `.planning/spikes/v1.1-brand-name-shapes/`; canary parametrizes against it; match-rate KPI improves >0% post-fix on live run |
| #1 (code side) | **Phase 2 (Parser-fix implementation)** | Parametrized tests pass for all 30 shapes; `brand.lower() not in name.lower()` canary passes; goldapple `volume_norm` non-null rate >90% |
| #2 Stale cassettes | **Phase 3 (Live-HTML harness)** | Cassette-age canary present; refresh job documented or scheduled; 3-tier test classification ships |
| #3 Cassette secrets leak | **Phase 3 (Live-HTML harness)** | Redaction config in conftest.py; PII-scan canary; gitleaks/detect-secrets pre-commit |
| #4 Flake hides drift | **Phase 3 (Live-HTML harness)** | `pytest.mark.flaky` grep-banned in `tests/live_html/`; deterministic wait strategy documented; cassette-determinism test (record twice 30s apart, diff) |
| #5 Sitemap/category drift bypasses brand-intersect filter | **Phase 4 (Drift detection extensions)** | Sitemap-delta canary computes weekly; ops alert on new top-level path segments; `goldapple_categories_seen` KPI in summary |
| #6 `.env` not loaded in CLI standalone path | **Phase 5 (Operator deploy + CLI hardening)** | `load_dotenv()` at CLI entrypoint; canary test in clean-shell context; README recovery recipes don't require `source .env` |
| #7 TZ mismatch between cron and system | **Phase 5 (Operator deploy + CLI hardening)** | `timedatectl set-timezone Asia/Almaty` in README §2; canary on `CRON_TZ` invariant; explicit log filename TZ verification |
| #8 Yandex Cloud / Camoufox compatibility unknown | **Phase 5 (Operator deploy + CLI hardening)** | Provider-choice decision recorded as D-NNN; if Yandex Cloud, Camoufox launch-smoke in operator runbook BEFORE cron handoff |
| #9 Cassette repo bloat | **Phase 3 (Live-HTML harness)** | Cassette size budget canary <50MB; body-downsampling hook configured; per-shape-class curation discipline documented |
| #10 Audit paperwork done after-the-fact | **Phase 6 (Audit carryover)** + workflow enforcement across all phases | SECURITY.md for phases 2/4/6 + VALIDATION.md for phase 4 exist with verdict; each new v1.1 phase ships SECURITY+VALIDATION at phase close, not milestone close |

### Phase ordering implications for roadmapper

- **Phase 1 (research/sampling) must precede Phase 2 (parser code)** — Pitfall #1 demands shape-table BEFORE code.
- **Phase 3 (harness) can run in parallel with Phase 2 (parser code)** — they share cassettes but build independently. The first parser-fix PR uses ad-hoc fixtures; once harness ships, regression tests move into cassettes.
- **Phase 4 (drift extensions) is independent** of Phases 1-3 in code dependency, but should NOT ship before parser-fix lands — adding new drift detectors while parsers are broken creates noise.
- **Phase 5 (operator deploy) blocks on Phase 2 minimum** — cannot deploy a still-broken parser. Phase 3 is nice-to-have for deploy but not blocking.
- **Phase 6 (audit carryover) is an independent track** — can run parallel to everything; should close BEFORE milestone audit.

### Phases that need deeper research flags

- **Phase 5 (Operator deploy)**: provider choice (Hetzner EU vs Yandex Cloud KZ) needs a fresh research/spike — v1.0 RECON-01 didn't compare providers, just locked Camoufox-direct. Flag for roadmapper as "spike candidate" before full phase plan.
- **Phase 4 (Drift detection)**: sitemap-delta canary design needs research on goldapple's sitemap structure (incremental? per-category?) and viled's catalog-shape stability. Flag as MEDIUM-research.
- **Phase 3 (Live-HTML harness)**: choice of vcrpy vs pytest-recording vs hand-rolled is a small spike — both work, but pytest-recording has stronger ergonomics for our case ([pytest-recording](https://github.com/kiwicom/pytest-recording)). Flag as LOW-research, decide in phase plan.

---

## Sources

### Live-HTML harness / cassette tooling
- [pytest-recording (kiwicom) — VCR.py-powered pytest plugin](https://github.com/kiwicom/pytest-recording) — record modes, `--record-mode` flag, env-var `VCR_RECORD_MODE`
- [VCR.py 8.0 documentation](https://vcrpy.readthedocs.io/) — record modes (none/once/new_episodes/all/rewrite), filter_headers, before_record_response hooks
- [Redacting secrets and PII from VCR.py cassettes (Illya Moskvin)](https://imoskvin.com/blog/redacting-vcrpy-cassettes/) — concrete filter patterns
- [VCR & .gitignore (Ashley Lewis)](https://ashleymichal.github.io/VCR-and-gitignore/) — when to gitignore vs commit cassettes
- [Test a Playwright Web Scraper (datawookie, 2025-04)](https://datawookie.dev/blog/2025-04-02-test-a-playwright-scraper/) — Playwright-specific cassette patterns
- [Test a Web Scraper using VCR (datawookie, 2025-01)](https://datawookie.dev/blog/2025-01-28-test-a-web-scraper-using-vcr/) — pytest-vcr config examples

### Silent failure / drift retrospectives
- [Why Most Web Scraping Systems Fail Silently (DEV Community, 2025)](https://dev.to/anna_6c67c00f5c3f53660978/why-most-web-scraping-systems-fail-silently-and-how-to-design-around-it-40o6) — "40% of production scraper outages 2025 caused by silent failures"
- [Why Scraping Fails Silently — And Why That's Worse Than Crashing (Medium, Jan 2026)](https://medium.com/@patryk_b/the-silent-data-crisis-is-your-web-scraping-working-b87f2c7ad1b5) — silent failure design patterns
- [Why Web Scrapers Fail in Production (Promptcloud)](https://www.promptcloud.com/why-web-scrapers-fail-in-production/) — 11 production failure modes
- [Why Web Scraping Works in Testing but Fails in Production (Grepsr)](https://www.grepsr.com/blog/web-scraping-testing-vs-production/) — direct mapping of test/prod drift
- [Ecommerce Web Scraping in 2026 (extralt)](https://extralt.com/blog/ecommerce-web-scraping) — 3-5 day average detection delay for completeness failures
- [Why Your Web Scraper Keeps Breaking (BinaryBits)](https://binarybits.co/blog/why-web-scraper-keeps-breaking) — 10-15% weekly fix rate; selector-extrapolation antipattern

### Parser overfitting / multi-shape edge cases
- [Scraping E-commerce through Brands (Web Scraper)](https://webscraper.io/blog/scraping-brands) — brand-prefix shape variants
- [Multiple variations Web Scraper How-To](https://webscraper.io/tutorials/product-with-multiple-variations) — multipack/variant N×M matrix
- [Cyrillic regex patterns reference](https://regexpattern.com/russian-cyrillic-characters/) — `\p{Cyrillic}` and pitfalls
- [SPA Structured Data Implementation (Stackmatix)](https://www.stackmatix.com/blog/spa-structured-data-implementation) — microdata breaks on React re-render; JSON-LD preferred

### Python env / subprocess
- [Python subprocess env Windows pitfall (cpython#120836)](https://github.com/python/cpython/issues/120836) — env inheritance edge cases
- [subprocess docs (Python 3.12)](https://docs.python.org/3/library/subprocess.html) — env parameter semantics

### Yandex Cloud / KZ region
- [Yandex launches new cloud region in Kazakhstan (DCD, April 2024)](https://www.datacenterdynamics.com/en/news/yandex-launches-new-cloud-region-in-kazakhstan/) — Karaganda DC launch
- [Yandex Cloud begins providing services from KZ DC (TAdviser)](https://tadviser.com/index.php/Product:Yandex_Cloud_Virtual_Computing_Infrastructure_Services) — `kz1` region
- [Yandex Cloud (Wikipedia)](https://en.wikipedia.org/wiki/Yandex_Cloud) — corporate context

### Anti-bot / Camoufox
- [camofox-browser (jo-inc) — Camoufox/Camofox stealth browser](https://github.com/jo-inc/camofox-browser) — drop-in Playwright replacement
- v1.0 internal spike memo `.planning/spikes/01-goldapple/` (2026-05-06) — Camoufox-direct 99/100 from Hetzner EU, no proxy needed

### Healthchecks.io
- [Healthchecks.io documentation](https://healthchecks.io/docs/) — cron mode, dead-man's switch, schedule semantics
- [Configuring Checks (HC.io)](https://healthchecks.io/docs/configuring_checks/) — labels, timezone, grace period

### v1.0 internal references (project-specific)
- `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` — the 3 bugs to fix
- `.planning/RETROSPECTIVE.md` § v1.0 — "What Was Inefficient" #5 (audit-framework lag); #4 (cold-start race); patterns established
- `README.md` § 1 + § 7 — current operator runbook, `.env` loading pattern, TZ invariants
- v1.0 `PITFALLS.md` (sibling research file) — building-phase pitfalls; not directly recurring but provides volume/multipack/anti-bot context

---
*Pitfalls research for: v1.1 parser fixes + live-HTML harness + KZ operator deploy*
*Researched: 2026-05-13*
*Downstream consumer: gsd-roadmapper for v1.1 milestone phase plan*
