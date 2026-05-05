# Stack Research

**Project:** GA Crawler — Competitive Pricing Intelligence (viled.kz vs goldapple.kz)
**Domain:** Weekly competitor price-monitoring scraper (Python, greenfield)
**Researched:** 2026-05-05
**Overall confidence:** HIGH (core stack), MEDIUM (anti-bot specifics for goldapple.kz — needs spike validation)

## TL;DR

> Python 3.12 + uv + Playwright 1.57 (for goldapple) + curl_cffi 0.15 (for viled) + selectolax (HTML parsing) + SQLite/SQLModel (storage) + pandas 2.x + xlsxwriter (Excel) + aiogram 3.27 (Telegram) + system cron on Hetzner CX22 (deployment). Wrap goldapple crawl in **Patchright** if Playwright vanilla fails. Add **Decodo** or **IPRoyal** residential proxies on a metered budget only if the IP is blocked.

The stack is intentionally boring everywhere except anti-bot, where `goldapple.kz` may force a tooling escalation (vanilla Playwright -> Patchright -> Camoufox/Scrapling). Single-process, single-VPS, no Celery, no Docker Swarm, no orchestrators.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python** | 3.12.x | Runtime | Stable, broadly supported by every library below. 3.13 still has a few rough edges with C-ext libs (lxml, curl_cffi); 3.11 is fine but missing perf wins. Avoid 3.13 as default. |
| **uv** | 0.10.x+ | Project + dependency manager | 2026 default for new Python projects. Replaces pip/poetry/pyenv. 10–100x faster, lockfile native, ships Python toolchains. Drastically cleaner than `requirements.txt`. |
| **Playwright (Python)** | 1.57.0 | Headless browser orchestration | Industry-standard headless automation in 2026. Better than Selenium (faster, cleaner API, native async, auto-wait), better than puppeteer-py (unmaintained). Required for goldapple.kz (JS-rendered + anti-bot). |
| **curl_cffi** | 0.15.x | HTTP client with browser TLS fingerprinting | The killer library for scraping in 2026. Drop-in replacement for `requests`, but impersonates Chrome/Safari TLS+JA3+HTTP/2 fingerprints. 10–100x faster than launching a browser. Use for viled.kz and any goldapple endpoints that don't strictly need JS. |
| **selectolax** | 0.3.x | HTML parsing (CSS selectors) | Up to 30x faster than BeautifulSoup, simpler than raw lxml. Enough for product-card extraction. BS4 only if you need exotic malformed-HTML tolerance. |
| **SQLModel** | 0.0.24+ | ORM (SQLAlchemy + Pydantic) | Best DX for small Python projects in 2026. Same models work for DB schema and validation. SQLAlchemy 2.x under the hood — no rewrite if we outgrow it. |
| **SQLite** | 3.45+ (bundled) | Storage (v1) | Right tool for "weekly snapshot, single-writer, single-reader, archival." Zero ops. Migrate to Postgres only when concurrency or remote access demands it (see "Stack Patterns by Variant"). |
| **pandas** | 2.2.x | Data wrangling + Excel export | For our scale (~tens of thousands of rows weekly), pandas is the right call. Polars wins at >1GB; we have <100MB. `df.to_excel()` ecosystem is unmatched. |
| **xlsxwriter** | 3.2.x | Excel writer (formatted) | Pandas' default Excel engine in 2026. Supports conditional formatting, freeze panes, autofilter, column widths — all things commercial users expect. openpyxl can read+write but is slower and less polished for write-only workflows. |
| **aiogram** | 3.27.x | Telegram Bot SDK | Modern async-native Python Telegram framework. Cleanest API for `send_document` with files. Active maintenance, rich type hints, FSM if we ever add chat commands. |
| **APScheduler** | 4.0.x (or system cron) | Scheduling | For v1: just use **system cron** on the VPS. APScheduler 4 is excellent if we want in-process Python scheduling with persistence, but cron is simpler for one weekly job. Pick cron unless a reason emerges. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Patchright** | 1.55+ | Drop-in patched Playwright with stealth | Use only if vanilla Playwright is detected by goldapple. Drop-in API replacement; passes Cloudflare Turnstile, DataDome, Akamai. Switch with one import line. |
| **playwright-stealth (v2.x)** | 2.0.2 | Lightweight stealth patches for Playwright | Lighter alternative to Patchright. Try first if goldapple uses only basic detection. Actively maintained again in 2026 (v2 fork). |
| **Camoufox** | latest fork (`coryking/camoufox` Firefox 142) | Anti-detect Firefox-based browser | Escalation path beyond Patchright. C++-level fingerprint spoofing. Used only if Patchright fails. Note: original `daijro/camoufox` is unmaintained as of 2025; use the maintained fork. |
| **Scrapling** | 0.2.x | Adaptive scraping with built-in StealthyFetcher | Alternative escalation path: handles selector drift + Cloudflare Turnstile bypass in one library. Worth a spike if Patchright + curl_cffi both fail. |
| **tenacity** | 9.x | Retry decorator with backoff | Wrap every network call. Exponential backoff + jitter, declarative, battle-tested. |
| **pydantic** | 2.10+ | Data validation | Validate scraped product records before DB insert. Catches schema drift early (renamed fields = exception, not silent corruption). |
| **structlog** | 25.x | Structured logging | Better than `logging` for scrapers: JSON output, contextual binding (URL, page, attempt). Easy to grep run logs and ship to a file. |
| **alembic** | 1.14+ | DB migrations | Add when schema changes after first deploy. SQLModel ships SQLAlchemy 2.x, alembic integrates cleanly. Skip on day 1, add at first migration. |
| **python-dotenv** | 1.0.x | Load `.env` for tokens/proxies | Trivial, ubiquitous; keeps Telegram bot token & proxy creds out of git. |
| **httpx** | 0.28.x | Plain async HTTP (alternative to curl_cffi) | Use if site has no anti-bot at all (likely viled). curl_cffi handles both, so httpx is optional. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **uv** | Project + dep manager | `uv init`, `uv add`, `uv run` — replaces pip, virtualenv, poetry. |
| **ruff** | Linter + formatter | Replaces flake8 + black + isort. Ships with uv toolchain. Configure `line-length=100`, target `py312`. |
| **pytest** | Test runner | For unit tests on parsers and matchers. Mock HTTP with `respx` (curl_cffi) or fixtures. |
| **mypy** or **pyright** | Static type-checking | Optional but recommended given Pydantic + SQLModel are typed end-to-end. Pyright is faster. |

---

## Installation

```bash
# Install uv (one-time, on dev machine and on VPS)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize project
uv init ga_crawler --python 3.12
cd ga_crawler

# Core scraping
uv add playwright curl_cffi selectolax pydantic tenacity structlog python-dotenv

# Storage
uv add sqlmodel alembic

# Data + Excel
uv add pandas xlsxwriter openpyxl   # openpyxl as fallback reader

# Telegram delivery
uv add aiogram

# Anti-bot escalation (install only if needed; pin lazily)
uv add patchright             # tier 1 escalation
# uv add scrapling            # tier 2 escalation (only if Patchright fails)
# uv add camoufox             # tier 3 escalation

# Dev
uv add --dev ruff pytest pyright

# Install browser binary (after `uv add playwright`)
uv run playwright install chromium

# (If using Patchright instead)
uv run patchright install chromium
```

---

## Anti-Bot Strategy (concrete, tiered)

We do not know yet which tier goldapple.kz needs. Architect for escalation.

### Tier 0 — viled.kz
- **Tool:** `curl_cffi` with `impersonate="chrome"`.
- **Proxy:** None (likely not needed; site is small, not under Cloudflare).
- **Fallback:** Plain Playwright if HTML is JS-rendered.
- **Confidence:** HIGH.

### Tier 1 — goldapple.kz, optimistic case
- **Tool:** Vanilla Playwright Chromium (headless), realistic viewport, real `User-Agent`, slow throttled crawl (2–5 req/min), respect `robots.txt` semantics in spirit.
- **Cookies:** Reuse session cookies across runs.
- **Proxy:** None initially. Local KZ-region IP from VPS would be ideal but Hetzner is EU; **expect this to fail eventually**.
- **Confidence:** MEDIUM — goldapple.kz is operated by a major retailer, almost certainly behind Cloudflare or DataDome.

### Tier 2 — vanilla Playwright detected
- **Tool:** Swap to **Patchright** (`from patchright.async_api import async_playwright`). One-line code change.
- **Why:** Patchright passes Cloudflare, DataDome, Akamai, Kasada, Bet365, Sannysoft, CreepJS as of 2026 with default settings. Drop-in for Playwright.
- **Confidence:** HIGH that this is the right next step.

### Tier 3 — Patchright detected or rate-limited by IP
- **Add residential proxies.** Recommendation in priority order:
  1. **Decodo** (formerly Smartproxy) — best quality/price in 2026. ~$3.50/GB pay-as-you-go. KZ/RU geos available.
  2. **IPRoyal** — pay-as-you-go, traffic never expires; smallest minimum spend. Good for low-volume weekly use (~$1–5/run).
  3. **SOAX** — strong KZ/RU coverage, higher price.
  4. **Bright Data / Oxylabs** — overkill at our scale; enterprise pricing. Skip.
- **Budget guideline:** weekly run with subset of goldapple ≈ 100–500 MB → ~$0.50–$2/week with IPRoyal/Decodo.
- **Confidence:** MEDIUM — provider quality changes, validate at spike time.

### Tier 4 — still failing
- **Tool:** **Camoufox** (maintained fork) for Firefox-based fingerprint spoofing, OR **Scrapling.StealthyFetcher** for one-shot Cloudflare Turnstile bypass.
- **Last resort:** managed scraping API (ZenRows, ScrapingBee, Bright Data Web Unlocker) — pay-per-page. Reframes the project: "we no longer scrape, we proxy through a paid bypass service." Acceptable but defer until justified by failure data.
- **Confidence:** LOW — only if goldapple has aggressive bot mitigation. Worth measuring before paying.

### What does NOT work in 2026 (do not waste time here)
- **cloudscraper** / **cfscrape** — defeated by current Cloudflare. Abandoned approach.
- **selenium-stealth** / vanilla Selenium — also detected.
- **Original `playwright-stealth` (v1.x)** — unmaintained since 2023; only v2.x (April 2026 release) is viable.
- Pure `requests` + custom headers — Cloudflare reads TLS, not headers. Useless.

---

## Storage: SQLite vs Postgres

### v1: SQLite (recommended)

**Schema (rough):**
```
products(id, retailer, brand, name, volume, normalized_key, url, first_seen)
price_snapshots(id, product_id, run_id, price, sale_price, in_stock, captured_at)
runs(id, started_at, finished_at, status, viled_count, goldapple_count)
```

**Why SQLite:**
- Single writer, weekly batch — perfect concurrency profile.
- Whole DB is one file; backups = `cp prices.db prices.db.bak`.
- Zero ops on VPS (no Postgres install/config/upgrade).
- For 5 years × 52 weeks × 50k SKUs = ~13M rows. SQLite handles this easily with proper indexes.
- DuckDB is tempting for analytics but introduces a second engine. Skip for v1.

**Enable from day 1:**
- `PRAGMA journal_mode=WAL` — concurrent reads, faster writes.
- `PRAGMA synchronous=NORMAL` — fast and safe enough for batch jobs.
- Index `(product_id, captured_at)` and `(retailer, normalized_key)`.

### Migrate to Postgres when:
- Need real-time read access from a dashboard or other process.
- Multi-writer (multiple parallel scraper processes).
- Want time-series extensions (TimescaleDB) for trend queries.
- Outgrow ~10M rows with complex joins (still survivable in SQLite, but Postgres feels better).

SQLModel makes the migration trivial: change connection string, run `alembic upgrade head` against new DB, copy data with `pgloader`.

---

## Scheduling: cron vs APScheduler vs Celery vs Prefect

| Option | Verdict | Reason |
|--------|---------|--------|
| **System cron** | RECOMMENDED for v1 | One job, weekly. cron works, has worked for 50 years, requires zero Python. `0 2 * * 0 cd /opt/ga_crawler && uv run python -m ga_crawler.run` |
| **APScheduler 4** | Use if running as long-lived daemon | Reasonable if we add other periodic tasks (health checks, retries). Persistent SQLAlchemy data store works with our SQLite. |
| **Celery + Redis** | NO | Overkill. Adds a broker, a worker, a result backend. Designed for distributed task queues, not weekly cron. |
| **Prefect / Dagster** | NO | Pipeline orchestrators. Useful at 10+ pipelines or with a team. We have one weekly job. |
| **systemd timer** | Reasonable alternative to cron | Slightly nicer logging/dependency management; identical conceptually. Pick cron OR systemd timer based on team preference. |

---

## Deployment / Hosting

### Recommended: Hetzner CX22 (or CPX22)

| Spec | Value |
|------|-------|
| Cost | ~€4.50–€8/month |
| Specs | 2 vCPU, 4 GB RAM, 40 GB SSD |
| OS | Ubuntu 24.04 LTS |
| Region | Falkenstein/Helsinki (EU); use Hetzner Cloud KZ if available, otherwise EU is fine |
| Why | Cheapest reliable VPS with enough RAM for headless Chromium. ~5x cheaper than DO equivalent. |

**Setup:**
- Install `uv` and Python 3.12.
- Install `playwright` system deps: `uv run playwright install-deps chromium`.
- Clone repo to `/opt/ga_crawler`, run via `uv run`.
- Cron entry runs the scraper, captures stderr to a file `structlog` writes JSON to `/var/log/ga_crawler/`.
- Healthcheck: cron mailbox + Telegram bot self-message on failure.

### Alternatives considered:

| Option | Verdict | Why |
|--------|---------|-----|
| **DigitalOcean Droplet** | Acceptable, more expensive | $12+/month for 2GB. Better docs/community than Hetzner; pay 2x for that. |
| **Fly.io** | NO | Edge-deployed containers, scale-to-zero, billed per-second. ~$40+/month for headless-Chromium-capable size. Wrong abstraction for weekly batch. |
| **Render / Railway** | NO | PaaS pricing model designed for web apps; cron jobs are an afterthought and expensive. |
| **AWS Lambda / GCP Cloud Functions** | NO | 15-min execution limit (Lambda) and headless-browser pain. Crawl will exceed time budget. |
| **GitHub Actions** | Tempting but NO | 6-hour limit; cron schedules drift; sharing state across runs requires external storage. Acceptable as backup runner only. |
| **Local machine + cron** | NO for production | Box must be on Sunday night; networking flakiness; no separation from dev work. |

### Docker?
- **Optional, recommended**. One Dockerfile based on `mcr.microsoft.com/playwright/python:v1.57.0-noble` (ships browsers + system deps preinstalled). Saves the `playwright install-deps` step.
- Keeps the host clean and makes redeploys reproducible.
- Compose unnecessary; one container, restart policy = `no` (cron starts it).
- Skip Docker if team is unfamiliar — cron + uv on the VPS is fine.

---

## Telegram Delivery

**Library:** `aiogram` 3.27.x.

**Why aiogram over python-telegram-bot:**
- Pure async, idiomatic for the rest of the async stack (Playwright, httpx, curl_cffi async).
- Cleaner API for our use case (send file + caption, not interactive bot).
- Both are fine; this is preference. Pick aiogram for consistency with async scraper.

**Why not raw HTTP:**
- `requests.post('https://api.telegram.org/bot.../sendDocument', files=...)` works, but file upload form-data + retries + error parsing are tedious.
- 30 LOC saved, real type hints, free retry & rate-limit handling.

**Telegram limits to know:**
- **Standard Bot API: 50 MB max file upload.** Our Excel will be ~1–10 MB. Fine.
- If we ever exceed 50 MB, run a self-hosted Telegram Bot API server (raises to 2 GB).
- Message rate limit: 30 messages/sec to different chats, 1 msg/sec to same chat. Trivially within limit.

**Pattern:**
```python
from aiogram import Bot
from aiogram.types import FSInputFile

bot = Bot(token=os.environ["TG_BOT_TOKEN"])
await bot.send_document(
    chat_id=CHAT_ID,
    document=FSInputFile("report_2026-W18.xlsx"),
    caption=summary_text_markdown,
    parse_mode="MarkdownV2",
)
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Playwright | **Scrapy + scrapy-playwright** | If we expand to 5+ retailers and need pipeline architecture, request scheduling, deduplication, retries built-in. Currently overkill for 2 sites. |
| Playwright (vanilla) | **SeleniumBase UC Mode** | Strong undetected-chromedriver successor with active maintenance. Pick if we already use Selenium. We do not. |
| curl_cffi | **httpx** | If both sites have zero anti-bot — but goldapple definitely has some. curl_cffi is a strict superset (impersonate flag is opt-in). |
| selectolax | **parsel** (Scrapy's parser) | If we adopt Scrapy. Otherwise selectolax is faster for raw HTML. |
| selectolax | **BeautifulSoup4** | If site HTML is severely malformed and tolerant parsing is required. Add `+ lxml` parser. |
| SQLite | **DuckDB** | If we want analytical queries (window functions, percentiles) against snapshot history. Can run alongside SQLite (`ATTACH`). Add only when reporting demands it. |
| SQLite | **Postgres** | Multi-writer, remote access, dashboard. See "Migrate when" above. |
| pandas | **polars** | Datasets >1 GB. We are at ~10–50 MB. Polars overkill. |
| xlsxwriter | **openpyxl** | If we need to *read* and modify existing Excel files. xlsxwriter is write-only. Pandas uses openpyxl by default for `read_excel`. |
| aiogram | **python-telegram-bot 22** | If team is more familiar with PTB. Equivalent capability. |
| aiogram | **raw `httpx.post(...)` to Bot API** | If we want zero dependencies for delivery. Saves ~5 MB but loses ergonomics. Not worth it. |
| system cron | **APScheduler 4** | If scraper runs as a long-lived daemon (not the case here). |
| Hetzner | **DigitalOcean** | Better docs, established managed Postgres, $12+/month vs Hetzner's $5. Pay 2x for ergonomics. |
| Hetzner | **Self-hosted on existing infra** | If team has spare server already. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Selenium** | Slower, dated API, harder anti-bot story, no async. Selenium 4 is decent but Playwright wins on every axis for new projects. | Playwright (or Patchright) |
| **requests** library | Cannot impersonate TLS/JA3. Cloudflare and DataDome detect the urllib3 fingerprint instantly. | curl_cffi (drop-in replacement with `impersonate=`) |
| **cloudscraper / cfscrape** | Defeated by current Cloudflare. Will fail on goldapple. | Patchright + residential proxy |
| **playwright-stealth v1.x** | Unmaintained since 2023. Patches written for Chrome 109 era; useless against modern fingerprinting. | Patchright OR playwright-stealth v2.x (April 2026 fork) |
| **undetected-chromedriver** (Selenium) | Bound to Selenium ecosystem. Successor (`nodriver`) is newer but less mature than Patchright for our use case. | Patchright |
| **BeautifulSoup4** as default parser | 10–30x slower than alternatives, fine for malformed HTML but our targets aren't broken. | selectolax (or lxml for XPath) |
| **Polars for our scale** | Adds API to learn, brings tiny perf win on <100 MB data, slightly weaker Excel interop. | pandas 2.x |
| **openpyxl** for write-heavy reports | Slower, less polished formatting API than xlsxwriter. | xlsxwriter (pandas default) |
| **Celery / Prefect / Dagster** | Designed for distributed pipelines or 10+ DAGs. Single weekly job. | system cron |
| **requirements.txt + pip + virtualenv** | Slow, no lockfile by default, manual venv management. | uv (project + deps + Python) |
| **Heroku / Render / Railway / Fly.io** for batch cron | Pricing model wrong; $30+/month for what Hetzner does at $5. | Hetzner CX22 |
| **Kubernetes** | One weekly cron job. | systemd unit / cron / Docker `restart: no` |

---

## Stack Patterns by Variant

### If goldapple.kz uses Cloudflare basic + JS challenge:
- Vanilla Playwright works. Add realistic UA, viewport, slow rate.
- Skip proxies (use VPS IP).

### If goldapple.kz uses Cloudflare Bot Management / Turnstile:
- Patchright as drop-in for Playwright.
- Add Decodo or IPRoyal residential proxy (KZ if available, else RU).
- Cookie persistence between requests. Slow rate (1 req every 3–5 seconds).

### If goldapple.kz uses DataDome:
- Patchright is documented to pass DataDome.
- Almost certainly need residential proxy.
- Monitor closely; DataDome rotates challenges.

### If goldapple.kz aggressively blocks even Patchright:
- Camoufox (maintained fork) or Scrapling StealthyFetcher.
- If still failing, switch to a managed unblocker API (Bright Data Web Unlocker / ZenRows / ScrapingBee). Pay-per-page, ~$1–3/1000 pages. Reframes the project but unblocks delivery.

### If we eventually need a dashboard (out of scope for v1):
- Migrate SQLite -> Postgres.
- FastAPI + HTMX or a Streamlit/Dash app pointed at the same DB.
- Keep scraper unchanged.

### If we expand to 5+ retailers:
- Adopt Scrapy (with scrapy-playwright + scrapy-impersonate for curl_cffi integration).
- Move scheduling into Scrapy CLI invocations.
- Storage stays the same.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `playwright==1.57.x` | Python 3.10–3.13 | Bundled Chromium auto-managed. Run `playwright install chromium` after upgrade. |
| `patchright==1.55+` | Drop-in for Playwright same major | Pin together. After `pip install`, run `patchright install chromium` (separate browser install). |
| `curl_cffi==0.15.x` | Python 3.10+ | v0.14 dropped Python 3.9. Wheels for Linux/macOS/Windows. Latest `impersonate="chrome"` tracks Chrome 136+. |
| `aiogram==3.27.x` | Python 3.10+ | v3.x is async-native. Avoid v2.x docs (pre-2024 API). v4.x exists but not yet recommended for production. |
| `sqlmodel==0.0.24+` | SQLAlchemy 2.x, Pydantic 2.x | Both must be v2. Upgrade SQLAlchemy/Pydantic together. |
| `pandas==2.2.x` + `xlsxwriter==3.2.x` | Auto-detected by `df.to_excel(..., engine="xlsxwriter")` | Default engine in pandas 2.x. |
| `apscheduler==4.0.x` | Python 3.9+ | v4 is async-first; v3.x API differs significantly. Read v4 docs only. |
| `uv` | Manages own Python | `uv python install 3.12` + `uv sync` is reproducible across machines. |

**Single binary trap:** Playwright/Patchright bundles its own Chromium. Don't rely on system Chrome. After every Playwright/Patchright upgrade, re-run `<tool> install chromium`.

---

## Confidence Summary

| Decision | Confidence | Reason |
|----------|------------|--------|
| Python 3.12 + uv | HIGH | Industry default in 2026; verified via PyPI / Astral docs. |
| Playwright 1.57 for headless | HIGH | Verified via Context7 + recent uv setup tutorials (Jan 2026). |
| curl_cffi for HTTP | HIGH | Verified via Context7 + curl_cffi docs (v0.11+ supports chrome136, safari184). |
| selectolax for HTML | HIGH | Multiple 2026 benchmarks confirm 10–30x perf advantage. |
| pandas (not Polars) at our scale | HIGH | Multiple 2026 sources agree polars below 1GB is no win. |
| xlsxwriter for Excel write | HIGH | Pandas default engine, mature, conditional formatting verified via Context7. |
| SQLite v1 + SQLModel | HIGH | Time-series price snapshots fit SQLite envelope; SQLModel gives painless Postgres migration. |
| aiogram 3.27 for Telegram | HIGH | Verified via Context7 + PyPI release notes; matches async stack. |
| system cron over APScheduler/Celery | HIGH | Single weekly job, no parallelism — cron is the right tool. |
| Hetzner CX22 hosting | HIGH | Well-documented price/perf advantage in 2026. |
| Patchright as Tier-2 anti-bot | MEDIUM-HIGH | Strong 2026 benchmark coverage; works for Cloudflare/DataDome per multiple sources. Validate at spike time. |
| Decodo / IPRoyal proxies | MEDIUM | 2026 reviews positive but provider quality shifts; revisit at spike time. |
| Camoufox / Scrapling as Tier-3/4 | MEDIUM | Original Camoufox unmaintained as of mid-2025; recommended fork (`coryking/camoufox`) tracks Firefox 142. Scrapling StealthyFetcher actively developed. Use only if needed. |
| goldapple.kz needs Tier 2 specifically | LOW | Unverified empirically. Validate with spike in Phase 1. May need only Tier 1 or as much as Tier 3. |

---

## Open Questions for Phase 1 Spike

1. **Does vanilla Playwright pass goldapple.kz?** (binary: yes -> Tier 1, no -> Tier 2)
2. **If Patchright is needed, is the Hetzner EU IP sufficient or do we need a KZ/RU residential IP?**
3. **What is the actual product page volume for the cross-section of brands?** (informs proxy budget)
4. **Does goldapple.kz expose a JSON catalog endpoint that bypasses the need for browser?** (would let us drop Playwright for goldapple entirely and use curl_cffi only)
5. **Is `goldapple.kz` Cloudflare or DataDome or something else?** (changes Tier 3 tooling)

These are scoped for the first phase, not blocking for project initialization.

---

## Sources

**Authoritative (Context7):**
- `/microsoft/playwright-python` — browser launch, async API, headless options.
- `/lexiforest/curl_cffi` — `impersonate="chrome"` syntax, latest browser targets (chrome136, safari184).
- `/aiogram/aiogram` — `send_document` API, `FSInputFile`, current version v3.27.0.
- `/python-telegram-bot/python-telegram-bot` — `send_document` semantics, file size limits.
- `/agronholm/apscheduler` — CronTrigger, SQLAlchemyDataStore for persistence.
- `/jmcnamara/xlsxwriter` — conditional formatting, data bars, color scales.
- `/scrapy/scrapy`, `/scrapy-plugins/scrapy-playwright`, `/jxlil/scrapy-impersonate` — confirmed for "if we scale" path.

**Official docs / PyPI (verified):**
- [curl-cffi PyPI](https://pypi.org/project/curl-cffi/) — current version, Python 3.10+ requirement.
- [curl_cffi Read the Docs (v0.11.4)](https://curl-cffi.readthedocs.io/en/v0.11.4/impersonate.html) — supported targets.
- [python-telegram-bot 22.7](https://pypi.org/project/python-telegram-bot/) — March 2026 release.
- [aiogram PyPI](https://pypi.org/project/aiogram/) — v3.27 current, v4.x preview.
- [Patchright GitHub](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) — drop-in Playwright with Cloudflare/DataDome bypass.
- [Patchright Python](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python) — Python distribution.
- [Camoufox](https://github.com/daijro/camoufox) and [maintained fork](https://github.com/coryking/camoufox) — anti-detect Firefox.
- [Scrapling StealthyFetcher docs](https://scrapling.readthedocs.io/en/latest/fetching/stealthy/) — Cloudflare Turnstile bypass.
- [uv docs](https://docs.astral.sh/uv/guides/projects/) — project management.

**Web (MEDIUM confidence; verified across multiple sources):**
- [Web Scraping With curl_cffi (Bright Data, 2026)](https://brightdata.com/blog/web-data/web-scraping-with-curl-cffi)
- [Playwright Stealth 2026 (scrapewise)](https://scrapewise.ai/blogs/playwright-stealth-2026)
- [Patchright alternatives (Round Proxies, 2026)](https://roundproxies.com/blog/best-patchright-alternatives/)
- [Anti-detect browser comparison (pim97 GitHub)](https://github.com/pim97/anti-detect-browser-tools-tech-comparison)
- [Best residential proxies 2026 (aimultiple, Round Proxies, Proxyway)](https://roundproxies.com/blog/best-residential-proxies/)
- [Hetzner vs DigitalOcean vs Fly.io 2026](https://1vps.com/hetzner-vs-digitalocean)
- [Polars vs pandas 2026 benchmarks (TildAlice)](https://tildalice.io/polars-vs-pandas-2026-benchmarks/)
- [SQLite for time-series (sqliteforum, MoldStud)](https://www.sqliteforum.com/p/sqlite-and-temporal-tables)
- [Scrapling: Adaptive Web Scraping (ScrapingBee)](https://www.scrapingbee.com/blog/scrapling-adaptive-python-web-scraping/)
- [Bypass Cloudflare 2026 (Scrapfly, ZenRows, AlterLab)](https://scrapfly.io/blog/posts/how-to-bypass-cloudflare-anti-scraping)
- [selectolax vs lxml vs BeautifulSoup benchmarks](https://medium.com/@yahyamrafe202/in-depth-comparison-of-web-scraping-parsers-lxml-beautifulsoup-and-selectolax-4f268ddea8df)

---
*Stack research for: Weekly competitor pricing scraper (viled.kz vs goldapple.kz)*
*Researched: 2026-05-05*
