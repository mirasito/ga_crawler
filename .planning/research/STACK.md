# Stack Research — v1.1 (Parser bug fixes + live HTML harness + operator deploy)

**Domain:** Python web-scraper, ecommerce competitive-pricing intelligence (KZ market)
**Researched:** 2026-05-13
**Confidence:** HIGH (selectolax + syrupy validated against Context7; Yandex Cloud answer validated against vendor docs; viled volume path verified against in-repo fixture)

> v1.0 stack (Python 3.12 + uv + Camoufox 0.4.11 + curl_cffi 0.15 + SQLModel 0.0.24 + pandas 2.2 + xlsxwriter 3.2 + aiogram 3.27 + structlog 25 + tenacity 9 + pytest 8 + respx 0.21) is LOCKED. This document only covers v1.1 ADDITIONS / UPGRADES. Inherited rationale lives in `CLAUDE.md § Technology Stack`.

## TL;DR

v1.1 needs **two small library changes** (selectolax upgrade 0.3 → 0.4 for the Lexbor backend, syrupy as a dev dep for HTML fixture snapshot replay) and **zero infrastructure changes**. No new SDKs for either Hetzner CX22 or Yandex Cloud kz1.

- **Bug #1 (goldapple volume):** Solvable inside selectolax 0.4 via `:lexbor-contains("ОБЪЁМ" i)` pseudo-class. No library swap.
- **Bug #2 (goldapple brand/name):** Solvable using microdata already emitted by goldapple (`<span itemprop="brand"><meta itemprop="name" content="Givenchy ">` + product-level `<meta itemprop="name">`). Pure code fix; no library change. **Fixture-verified.**
- **Bug #3 (viled volume_raw):** Solvable from `__NEXT_DATA__.props.pageProps.attributes[].name == "Размер"`. No library change. **Fixture-verified.**
- **Live HTML harness:** syrupy + `SingleFileSnapshotExtension` (subclassed with `file_extension = "html"`, `WriteMode.TEXT`).
- **Operator deploy:** Hetzner CX22 (default) OR Yandex Cloud kz1 — both are vanilla Ubuntu over SSH. Same `uv` + Camoufox + cron procedure. Choice is legal/network, not technical.

## Recommended Additions / Changes to LOCKED v1.0 Stack

### Core (additions or upgrades)

| Technology | Version | Purpose | Why Recommended | Integration with v1.0 |
|------------|---------|---------|-----------------|------------------------|
| **selectolax** | upgrade `>=0.3,<0.4` → `>=0.4.7,<0.5` | HTML5 parser; unlocks the **Lexbor backend** with `:lexbor-contains()` pseudo-class and `LexborSelector.text_contains()` | The 0.4 line ships `LexborHTMLParser` with `:lexbor-contains("text" i)` pseudo-selector and `text_contains(..., deep=True, strip=False)` Selector filter. These are exactly the primitives missing in 0.3.x for **finding a label node by visible Russian text and walking to its sibling/parent** — the shape of the goldapple PDP volume block (`<div>78</div><div>ОБЪЁМ / МЛ</div>`). Latest 0.4.8 = May 4 2026; actively maintained. | Drop-in. `from selectolax.parser import HTMLParser` (Modest backend) still works unchanged. New code adds `from selectolax.lexbor import LexborHTMLParser` only in `goldapple_microdata.py`. viled parser unchanged. |
| **syrupy** | new dev-only dep, `>=4.7,<5.0` | pytest snapshot plugin; provides `SingleFileSnapshotExtension` → one HTML fixture file per test | Right primitive for "captured live PDP HTML → frozen test fixture, with `--snapshot-update` re-record." Subclass `SingleFileSnapshotExtension` with `file_extension = "html"`, `_write_mode = WriteMode.TEXT` to store each captured PDP as readable `.html` next to the test. **Soundness rule:** Syrupy fails the test if a snapshot is MISSING, not just on diff — directly addresses live-run #13 root cause (parsers tested only against frozen fixtures that didn't cover Armani / Contre-Jour shapes). Idiomatic pytest syntax (`assert html == snapshot`). | Dev-only. Lives in `[dependency-groups] dev`. Snapshot files in `tests/fixtures/<retailer>/snapshots/`. Existing 803 unit tests untouched — new live-capture tests are ADDITIVE (marked `@pytest.mark.live`, deselected by default). |

### Supporting (no new library — uses what's already locked)

| Capability | Existing library | Use |
|------------|------------------|-----|
| Live PDP capture via Camoufox `page.content()` | `camoufox==0.4.11` (LOCKED) | Captures HTML into syrupy snapshot via `assert html == html_snapshot` inside a `@pytest.mark.live` async test |
| New parser observability events (`parser.field_missing`, `parser.volume_label_match`) | `structlog>=25` (LOCKED) | Pure code change in parser files |
| Async test runtime | `pytest-asyncio>=0.24` (LOCKED) | Hosts the live-capture tests |

## Installation

```bash
# Bump selectolax in pyproject.toml [project].dependencies:
#   "selectolax>=0.4.7,<0.5"      (was "selectolax>=0.3,<0.4")
uv lock --upgrade-package selectolax
uv sync

# Add syrupy to [dependency-groups].dev
uv add --dev "syrupy>=4.7,<5.0"

# Confirm Camoufox stays locked at exactly 0.4.11 (Phase 3 D-313)
# No action needed; pyproject.toml already pins this.
```

## Library-Specific Answers to the Four Open Questions

### A) Better HTML parsing options than selectolax + microdata for goldapple's flexbox PDP?

**Recommendation: Stay on selectolax. Upgrade to 0.4.x and use the Lexbor backend.**

1. **The flexbox PDP is solvable with selectolax 0.4 — no library swap.** The Lexbor backend supports `:lexbor-contains("текст" i)` (case-insensitive substring) and `LexborSelector.text_contains(...)` filtering, which lets us find the cell whose text contains "ОБЪЁМ" and walk to its sibling holding the numeric value. ([Context7: selectolax LexborSelector.text_contains](https://selectolax.readthedocs.io/en/latest/lexbor.html))

   ```python
   from selectolax.lexbor import LexborHTMLParser
   tree = LexborHTMLParser(html)
   # Find the label cell whose text contains "ОБЪЁМ"
   label_nodes = tree.css('div:lexbor-contains("ОБЪЁМ" i)')
   # Walk to adjacent sibling holding the numeric value (e.g. "78")
   ```

2. **XPath / parsel NOT recommended.** Would add lxml + parsel (~5 MB native dep), give us tree-traversal we don't need (the volume block is shallow), and force a partial rewrite. selectolax+Lexbor has all the bidirectional traversal we need (`Node.parent`, `Node.iter()` already shipped in 0.3 and continue in 0.4).

3. **JSON-LD probing NOT viable.** Confirmed in v1.0 D-14 revision (2026-05-06): "goldapple.kz PDP emits ONLY OfferShippingDetails JSON-LD (shipping policy); there is NO Product schema JSON-LD." Re-verified during this research against the in-repo fixture `_debug-product-page.html` — exactly one `application/ld+json` block, shipping-only data.

4. **`window.__NUXT__` SSR state — POSSIBLE but inferior.** Goldapple emits `window.__NUXT__ = {...}` inline JS. Requires regex extraction and brittle JSON-parse (JS object syntax is a superset of JSON — trailing commas, undefined). NOT primary path. **Acceptable as Tier-2 fallback** if Lexbor-contains fails on a future PDP shape variant. Do not implement on day 1 of v1.1.

5. **Bug #2 (brand/name separation): NO library change at all.** The in-repo fixture `_debug-product-page.html` already shows clean structured separation:
   ```html
   <span itemprop="brand" itemtype="https://schema.org/Brand" itemscope>
     <meta itemprop="name" content="Givenchy ">
   </span>
   ...
   <meta itemprop="name" content="Pour Homme">  <!-- product-level name -->
   ```
   The current parser at `goldapple_microdata.py:328` reads `<h1>` text verbatim. **Fix: read the product-level `<meta itemprop="name">` (sibling of `[itemprop="brand"]` inside the product `itemscope`).** Pure code fix.

   **Confidence: HIGH** — fixture-verified.

### B) Best-in-class library for "live HTML fixture capture + replay + drift detection" in Python (2026)?

**Recommendation: syrupy with custom `SingleFileSnapshotExtension`. Avoid VCR.py / pytest-recording.**

Three candidates considered:

1. **syrupy ✅ RECOMMENDED.** Latest 4.x. Per-test single-file snapshots with custom file extensions. `--snapshot-update` flow well-documented. **Soundness:** "missing snapshot = test failure, not just diff" — the exact discipline we need to force every new SKU/parser branch to be backed by a captured fixture. Zero runtime deps. ([Context7: /syrupy-project/syrupy](https://github.com/syrupy-project/syrupy))

2. **pytest-recording / VCR.py ❌ NOT VIABLE.** VCR.py hooks at the urllib3 client layer. **curl_cffi bypasses urllib3** (uses libcurl through CFFI) and **Camoufox bypasses Python HTTP entirely** (the browser process makes the requests, not Python). vcrpy has no hook for either of our two scrapers. curl_cffi GH issues confirm only `requests_mock` (a different library) was made to interop. pytest-recording last release 0.13.4 = May 2025; no curl_cffi support on roadmap. ([pytest-recording PyPI](https://pypi.org/project/pytest-recording/))

3. **snapshottest ❌ DEPRECATED.** Predecessor of syrupy. Migration path from syrupy docs: "delete snapshots, install syrupy, regenerate." Do not adopt.

**Pattern:**
```python
# tests/parsers/test_goldapple_live.py
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

class HTMLSnapshotExtension(SingleFileSnapshotExtension):
    file_extension = "html"
    _write_mode = WriteMode.TEXT

@pytest.fixture
def html_snapshot(snapshot):
    return snapshot.with_defaults(extension_class=HTMLSnapshotExtension)

@pytest.mark.live
async def test_goldapple_armani_pdp_shape(html_snapshot):
    # First run with --snapshot-update: captures live HTML
    # Subsequent runs: compares live HTML to snapshot, fails on drift
    html = await fetch_via_camoufox("https://goldapple.kz/.../armani")
    assert html == html_snapshot
    # Same snapshot then feeds parse_pdp(html) and its expected dict
```

The `live` pytest marker is **already declared** in `pyproject.toml [tool.pytest.ini_options].markers`. CI runs `-m "not live"` by default; operator runs the live capture monthly or on PDP-shape suspicion.

### C) Viled volume extraction — dedicated JSON field vs. regex on `name`?

**Verified against repo fixtures: YES — use `props.pageProps.attributes[].name == "Размер"`, not regex on `name`.**

Evidence from `tests/fixtures/viled/viled-pdp-multipack.html` (in-repo, captured Phase 2):
```json
"attributes":[
  {"name":"Размер","value":"200мл + 200мл + 250мл","id":231977,"sort":0},
  {"name":"пол","value":"унисекс","id":193008,"sort":0},
  {"name":"Область применения","value":"Волосы","id":200503,"sort":0},
  ...
]
```

⚠️ **viled `__NEXT_DATA__` has TWO `attributes` arrays at different paths** — be careful not to confuse them:

| JSON path | Role | What we already use |
|-----------|------|--------------------|
| `props.pageProps.attributes[0]` (or `[N]`) | **Price variant** — has `price`, `realPrice`, `currency`, `itemImages` | YES — `viled_nextdata.py:155` reads `a0.get("price")` |
| `props.pageProps.item.attributes[]` (likely path; spike-confirm) OR a sibling under `props.pageProps` | **Descriptive attributes** — `[{name, value, id, sort}, ...]` including `Размер` (size/volume) | NO — this is the new path for v1.1 |

Code shape (after v1.1 Phase 1 spike confirms exact path):
```python
# Inside viled_nextdata.parse_pdp, after existing price extraction:
descriptive = item.get("attributes") or []  # confirm path via syrupy live capture
raw_volume_text = next(
    (a["value"] for a in descriptive
     if a.get("name", "").strip().lower() in ("размер", "объем", "объём")),
    None,
)
# Pass raw_volume_text into existing NORM-03 regex normalizer
```

**Confidence:**
- Field EXISTS as `{name: "Размер", value: ...}`: HIGH (fixture-verified)
- Exact JSON path on beauty PDPs (vs. clothing): MEDIUM — confirm with one syrupy live capture in v1.1 Phase 1 (≤15 min spike)

### D) Yandex Cloud KZ vs Hetzner — does kz1 require a vendor SDK / agent?

**Answer: NO. Yandex Cloud kz1 is vanilla Ubuntu over SSH. Same `uv` + Camoufox + cron deploy as Hetzner CX22. The choice is legal/network, not technical.**

| Question | Hetzner CX22 (EU) | Yandex Cloud kz1 |
|----------|-------------------|------------------|
| Region | Falkenstein DE / Helsinki FI | Karaganda KZ (launched April 2024, region name `kz1`) |
| IP geolocation | EU IP | KZ IP — material if goldapple geo-blocks or serves region-variant content |
| OS images | Ubuntu 24.04 LTS official | Ubuntu 22.04 LTS confirmed on marketplace; 24.04 not confirmed in search results — verify in Yandex Cloud console at deploy time |
| Access pattern | SSH + `apt install` | SSH + `apt install` — explicit in [Yandex Cloud compute docs](https://yandex.cloud/en/docs/compute/operations/vm-create/create-linux-vm): "Connect to VMs using SSH keys… Public images have SSH access enabled by default" |
| Vendor SDK required for our app | No | **No** — verified per vendor docs |
| Vendor agent required for our app | No | No (Cloud Backup agent exists but is optional, not required) |
| Billing | EUR, EU credit card | **Requires Russian or Kazakhstan resident business** for billing account |
| Pricing | ~€4.50–€8/month | Not retrieved in this research; expected same order of magnitude for comparable VPS class |

Sources:
- [Yandex Cloud Compute VM create-linux-vm](https://yandex.cloud/en/docs/compute/operations/vm-create/create-linux-vm) — vanilla SSH + apt is the explicit standard
- [DCD: Yandex launches kz1 in Karaganda](https://www.datacenterdynamics.com/en/news/yandex-launches-new-cloud-region-in-kazakhstan/) — April 2024 launch confirmed
- [Yandex Cloud KZ data-center access](https://yandex.cloud/en/docs/troubleshooting/business/how-to/accessing-data-centers-in-kazakhstan) — KZ-region procedures

**Decision criterion for v1.1 deploy:**
- **Default → Hetzner CX22.** Cheaper, faster signup (EU card, no KZ legal entity), zero KZ billing complications. Camoufox `geoip=true` + `locales=["ru-RU","kk-KZ","en-US"]` already lies about geo at the browser fingerprint level (already in `pyproject.toml [tool.ga_crawler.crawl.goldapple]`).
- **Escalate → Yandex Cloud kz1** only if a v1.1 spike empirically shows goldapple serves materially-different HTML or rate-limits harder from EU IPs. Cost: ~1 week extra for KZ-resident business registration + Yandex billing setup.
- **NOT for v1.1: managed unblocker API** (ZenRows / Bright Data Web Unlocker). Reframes the project; defer until empirical failure data justifies.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| selectolax 0.4 + Lexbor backend | `parsel` (Scrapy parser, XPath) | If we adopt Scrapy at 5+ retailers (v3 territory). selectolax+Lexbor covers all v1.1 needs without lxml. |
| selectolax 0.4 + Lexbor backend | Regex on raw HTML | For single-shot edge extractions (we already do this for `sku_id` from URL). Not for structured blocks. |
| selectolax 0.4 + Lexbor backend | `window.__NUXT__` JS-state regex parse | Only as Tier-2 fallback if a future PDP shape variant defeats Lexbor-contains. |
| syrupy `SingleFileSnapshotExtension` | Hand-rolled golden-master (write `tests/fixtures/*.html` manually) | If team strongly prefers zero new deps. Loses `--snapshot-update` ergonomics and missing-snapshot enforcement. Acceptable backstop. |
| syrupy `SingleFileSnapshotExtension` | pytest-recording / vcrpy | Never — doesn't intercept curl_cffi or Camoufox. |
| Hetzner CX22 | Yandex Cloud kz1 | Only when EU IP causes empirical goldapple failures. KZ-resident business required. |
| Hetzner CX22 | PS Cloud (ps.kz), DaintyCloud KZ, Serverspace KZ | If we need KZ IP but want to avoid Yandex's legal-entity friction. Smaller providers; less documented. Spike at deploy time only if needed. |
| Camoufox 0.4.11 (LOCKED) | Patchright | LOCKED per Phase 3 D-313 spike sign-off; do not re-evaluate in v1.1. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **pytest-recording / VCR.py for HTML capture** | Hooks at urllib3 layer; curl_cffi bypasses urllib3 (libcurl through CFFI), Camoufox bypasses Python HTTP entirely (browser process owns the requests). Will silently record nothing. | syrupy `SingleFileSnapshotExtension`; existing respx for any future httpx-shaped client |
| **snapshottest** | Deprecated predecessor of syrupy; open bugs unresolved | syrupy |
| **lxml + parsel (just for XPath)** | 5+ MB native dep, Windows wheel + glibc compat surface, no incremental capability over selectolax 0.4 Lexbor backend | selectolax 0.4 Lexbor backend |
| **Bumping Camoufox above 0.4.11** | Phase 3 D-313 lock — smoke probe asserts `camoufox_version_expected == "135.0.1.beta24"`. Upgrade flow requires fresh goldapple spike (per CLAUDE.md L9-14). v1.1 is NOT the time to re-spike anti-bot. | Keep `camoufox[geoip]==0.4.11` |
| **Yandex Cloud `yc` CLI / SDK for runtime** | Not needed. Only the operator's local machine needs `yc` (to create the VM); the VM runs vanilla Ubuntu. | Standard `ssh`, `uv`, `cron` on the VM |
| **Cloud-init / Terraform / Ansible for v1.1** | One VM, one weekly cron — operator-grade IaC is over-engineering for current scale. Existing README §2 manual procedure already works. | README §2 + bin/weekly-run.sh |
| **Postgres migration in v1.1** | Out of scope. SQLite continues to fit single-writer weekly batch shape. | Keep SQLite; revisit per v1.0 STACK.md "Migrate when" trigger list |

## Stack Patterns by v1.1 Variant

**If Bug #1 needs a fallback when Lexbor-contains misses:**
- Add a Tier-2 extractor against `window.__NUXT__` JS-object state.
- Pattern: `re.search(r'window\.__NUXT__\s*=\s*Object\.assign\(.+?,\s*({.+?})\);', html, re.DOTALL)` (Nuxt 3 inlines state via `Object.assign`).
- Best-effort `json.loads`; on JS-only syntax failure (trailing commas) → return `None` + log `parser.nuxt_state_unparseable`.

**If viled `props.pageProps.item.attributes` isn't where descriptive attrs live on beauty PDPs:**
- v1.1 Phase 1 spike captures one beauty PDP via syrupy.
- Walk captured JSON for any key matching `(?i)размер|объ[её]м|capacity|volume`.
- Path discovery is mechanical (≤30 min).

**If we need cross-IP-region empirical testing (Hetzner EU vs KZ-IP):**
- Same code, same Docker image, different VPS.
- Add `RETAILER_PROXY_URL` env var (already structured for it via `python-dotenv`); Camoufox `launch(proxy={"server": ...})` accepts it.

**If we expand to a 3rd retailer in v2:**
- Migrate to Scrapy + scrapy-playwright + parsel.
- Until then, the parser-per-retailer module pattern in `src/ga_crawler/parsers/` scales fine to 3–4 retailers.

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `selectolax>=0.4.7,<0.5` | Python 3.10–3.13 | Drop-in for 0.3 (Modest backend still available). New imports: `selectolax.lexbor.LexborHTMLParser`. Wheels for Linux/macOS/Windows confirmed on PyPI. |
| `syrupy>=4.7,<5.0` | pytest ≥7, Python 3.8–3.13 | Zero runtime deps. Snapshot files default to `tests/__snapshots__/`; we override to colocate next to fixtures. |
| `syrupy` + `pytest-asyncio>=0.24` | Compatible | `assert == snapshot` works inside `async def test_*` when pytest-asyncio collects it. |
| `selectolax 0.4` + `pydantic 2.10` + `sqlmodel 0.0.24` | No interaction | Parsers don't touch these libs at the boundary. |
| `Camoufox==0.4.11` (LOCKED) | Firefox 135.0.1.beta24 | Pin intentional (D-313). Smoke probe must continue to pass `camoufox_version_expected`. No 0.4.12+ released as of May 2026. |
| `curl_cffi>=0.15,<0.16` (LOCKED) | Python 3.10+ | No change in v1.1. Chrome impersonation continues to handle viled. |
| Yandex Cloud kz1 + Ubuntu 24.04 | Verify at deploy time | Search did not find explicit kz1 + Ubuntu 24.04 marketplace listing. Ubuntu 22.04 is fine — uv installs Python 3.12 independent of system Python. |

## Sources

### Authoritative (HIGH confidence)
- **Context7 `/syrupy-project/syrupy`** — `SingleFileSnapshotExtension` API, custom `file_extension`, `WriteMode.BINARY/TEXT`, missing-snapshot soundness rule
- **Context7 `/websites/selectolax_readthedocs_io_en`** — `LexborSelector.text_contains`, `:lexbor-contains("text" i)` pseudo-class, `any_text_contains`
- **PyPI release history** — selectolax 0.4.8 (May 4 2026), pytest-recording 0.13.4 (May 2025 — no 2026 release), syrupy 4.x current, camoufox 0.4.11 (Jan 2025, unchanged through May 2026)
- **Yandex Cloud official docs** — [compute/vm-create/create-linux-vm](https://yandex.cloud/en/docs/compute/operations/vm-create/create-linux-vm) — confirms SSH + apt is standard, no proprietary agent
- **In-repo fixture verification** — `tests/fixtures/goldapple/_debug-product-page.html` (microdata `<meta itemprop="name">` separation for Bug #2 fix); `tests/fixtures/viled/viled-pdp-multipack.html` (`{name: "Размер", value: "200мл + 200мл + 250мл"}` for Bug #3)

### Web research (MEDIUM confidence — corroborated by authoritative source)
- [DCD: Yandex launches kz1 in Karaganda](https://www.datacenterdynamics.com/en/news/yandex-launches-new-cloud-region-in-kazakhstan/) — April 2024 region launch
- [Telecompaper: Yandex Cloud starts services in Kazakhstan](https://www.telecompaper.com/news/yandex-cloud-starts-services-in-kazakhstan--1497253) — corroborates launch
- [Bright Data: Web Scraping with curl_cffi (2026)](https://brightdata.com/blog/web-data/web-scraping-with-curl-cffi) — confirms curl_cffi bypasses urllib3 mocking layer
- [pytest-recording GH](https://github.com/kiwicom/pytest-recording) — no curl_cffi support
- [Simon Willison: Snapshot testing with Syrupy](https://til.simonwillison.net/pytest/syrupy) — idiomatic patterns
- [Hetzner Cloud locations](https://docs.hetzner.com/cloud/general/locations/) — CX22 / CPX22 specs unchanged in 2026

### Inherited from v1.0 (LOCKED — not re-debated)
- Python 3.12, uv 0.11.x, Camoufox 0.4.11, curl_cffi 0.15, SQLModel 0.0.24, pandas 2.2, xlsxwriter 3.2, aiogram 3.27, structlog 25, tenacity 9, pydantic 2.10, pytest 8, respx 0.21 — see `CLAUDE.md § Technology Stack` and `pyproject.toml`

## Open Questions Carried into v1.1 Phase Planning

1. **viled descriptive-attributes JSON path** — `{name: "Размер", value: ...}` is fixture-confirmed for clothing PDPs (Размер = S/L). Beauty PDPs almost certainly follow the same shape (multipack fixture shows `"200мл + 200мл + 250мл"` value). Spike requires one live capture (15 minutes).
2. **goldapple volume label exact string** — Bug #1 evidence shows `78 ОБЪЁМ / МЛ`. Exact whitespace and case in the live PDP need confirmation before pinning the `:lexbor-contains()` literal. Resolve by capturing one live PDP via syrupy.
3. **Yandex Cloud kz1 Ubuntu 24.04 availability** — confirm in console at deploy time. Fallback is Ubuntu 22.04 (uv installs Python 3.12 either way; no functional impact).
4. **goldapple geo-sensitivity** — empirical question: does goldapple.kz from a Hetzner EU IP serve the same HTML as from a KZ IP? Resolve with one Camoufox smoke probe from each before committing to deploy target. If identical → Hetzner wins on price + signup speed.

---
*Stack research for: GA Crawler v1.1 (parser-fix milestone)*
*Researched: 2026-05-13*
