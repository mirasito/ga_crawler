"""
Spike 01: Goldapple Camoufox Tier 2 fetch experiment.

Запуск из repo root:
  uv run python .planning/spikes/01-goldapple/notebook.py
  uv run python .planning/spikes/01-goldapple/notebook.py --limit 10           # smoke test
  uv run python .planning/spikes/01-goldapple/notebook.py --headless false     # observe browser

Per CONTEXT.md decisions (post-2026-05-06 re-route):
  D-01 (revised): Tier 2 = Camoufox (Firefox + C++ fingerprint spoof).
                  Patchright superseded по 01-06.
  D-03: Stop-rule = 5 consecutive blocks OR first gate-shell без auto-clear через 25s poll.
  D-04: persistent context (warm), random 3-5s pause, cookies live across fetches.
  D-13: Threshold >=95/100 successful fetches (timeout/exception retries allowed).
  D-14: Successful fetch = HTTP 200 + JSON-LD product schema present.
  D-15: gate-shell auto-cleared = pass; gate-shell rate logged separately. >20% = "fragile".
  D-08 (cancelled): IPRoyal не нужен — Camoufox + KZ-laptop direct passes per 01-06b spike.

Output:
  sample-payloads/tier2-camoufox-kz-results.json
  sample-payloads/tier2-camoufox-kz-log.txt
"""

import argparse
import asyncio
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog
from camoufox.async_api import AsyncCamoufox
from selectolax.parser import HTMLParser

REPO_ROOT = Path(__file__).resolve().parents[3]
SPIKE_DIR = REPO_ROOT / ".planning" / "spikes" / "01-goldapple"
URLS_FILE = SPIKE_DIR / "sample-payloads" / "goldapple-product-urls.txt"
OUTPUT_DIR = SPIKE_DIR / "sample-payloads"
USER_DATA_DIR = SPIKE_DIR / ".camoufox-state"   # gitignored

PAUSE_RANGE = (3.0, 5.0)            # D-04 random uniform
PAGE_TIMEOUT_MS = 60_000
GATE_POLL_DEADLINE_MS = 25_000      # 01-06b proven enough; 0/3 needed it but margin OK
GATE_POLL_STEP_MS = 500
CONSECUTIVE_BLOCK_LIMIT = 5         # D-03 stop-rule
RETRY_PER_URL = 1                   # D-13: timeout/exception retry разрешён
GATE_TITLE_MARKER = "checking"      # appears in "Gold Apple — checking device"
CHALLENGE_HTML_MAX_SIZE = 30_000    # GUN gate shell ~18KB; real app 200KB+

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()


def has_jsonld_product(html: str) -> tuple[bool, bool]:
    """JSON-LD path. Returns (has_product, has_price). Standard schema.org."""
    tree = HTMLParser(html)
    for s in tree.css('script[type="application/ld+json"]'):
        try:
            obj = json.loads(s.text() or "")
        except (json.JSONDecodeError, AttributeError):
            continue
        items = obj if isinstance(obj, list) else [obj]
        flat: list = []
        for it in items:
            if isinstance(it, dict) and "@graph" in it:
                flat.extend(it["@graph"])
            else:
                flat.append(it)
        for it in flat:
            if not isinstance(it, dict):
                continue
            t = it.get("@type")
            is_product = t == "Product" or (isinstance(t, list) and "Product" in t)
            if not is_product:
                continue
            offers = it.get("offers", {})
            price_present = (
                isinstance(offers, dict) and offers.get("price")
            ) or (
                isinstance(offers, list)
                and any(isinstance(o, dict) and o.get("price") for o in offers)
            )
            return True, bool(price_present)
    return False, False


def has_microdata_price(html: str) -> tuple[bool, bool]:
    """Goldapple uses inline microdata (`<meta itemprop="price" content="...">`)
    instead of JSON-LD Product schema. Returns (has_offer_marker, has_price_value).
    The price itemprop appears on offer/option lines; presence of any non-zero value
    counts as has_price. Discovered during 01-08 smoke-test 2026-05-06.
    """
    tree = HTMLParser(html)
    nodes = tree.css('meta[itemprop="price"]')
    if not nodes:
        return False, False
    has_value = False
    for n in nodes:
        v = (n.attributes.get("content") or "").strip()
        if v and v != "0":
            has_value = True
            break
    return True, has_value


def evaluate_product_data(html: str) -> dict:
    """D-14 (revised): success = JSON-LD Product schema OR microdata itemprop=price.
    Returns dict with both signals so MEMO can record per-strategy hit-rate."""
    jl_p, jl_pr = has_jsonld_product(html)
    md_p, md_pr = has_microdata_price(html)
    return {
        "jsonld_has_product": jl_p,
        "jsonld_has_price": jl_pr,
        "microdata_has_offer": md_p,
        "microdata_has_price": md_pr,
        "has_product_data": jl_p or md_p,
        "has_price_data": jl_pr or md_pr,
    }


async def fetch_one(page, url: str) -> dict:
    started = time.perf_counter()
    rec = {
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "status": None,
        "timing_ms": None,
        "html_size": None,
        "title": None,
        "gate_cleared": False,
        "gate_cleared_after_ms": None,
        "jsonld_has_product": False,
        "jsonld_has_price": False,
        "microdata_has_offer": False,
        "microdata_has_price": False,
        "has_product_data": False,
        "has_price_data": False,
        "block": False,
        "block_reason": None,
        "error": None,
    }
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        rec["status"] = response.status if response else None

        # Best-effort networkidle, then poll title for gate clearance (D-15)
        try:
            await page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass

        elapsed = 0
        last_title = ""
        while elapsed < GATE_POLL_DEADLINE_MS:
            last_title = await page.title()
            if GATE_TITLE_MARKER not in last_title.lower():
                rec["gate_cleared"] = True
                rec["gate_cleared_after_ms"] = elapsed
                break
            await page.wait_for_timeout(GATE_POLL_STEP_MS)
            elapsed += GATE_POLL_STEP_MS
        rec["title"] = last_title

        html = await page.content()
        rec["html_size"] = len(html)

        if not rec["gate_cleared"] and rec["html_size"] < CHALLENGE_HTML_MAX_SIZE:
            rec["block"] = True
            rec["block_reason"] = "gate_shell_not_cleared"
        elif rec["status"] not in (200, 304):
            rec["block"] = True
            rec["block_reason"] = f"http_{rec['status']}"
        else:
            data = evaluate_product_data(html)
            rec.update(data)
            if not rec["has_product_data"]:
                rec["block"] = True
                rec["block_reason"] = "no_product_data"
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {repr(e)[:200]}"
        rec["block"] = True
        rec["block_reason"] = "exception"
    rec["timing_ms"] = int((time.perf_counter() - started) * 1000)
    return rec


async def run(args) -> None:
    urls = [u.strip() for u in URLS_FILE.read_text(encoding="utf-8").splitlines() if u.strip()][: args.limit]
    print(f"URLs: {len(urls)}, headless: {args.headless}, pause range: {PAUSE_RANGE}s")

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_file = OUTPUT_DIR / "tier2-camoufox-kz-log.txt"
    log_handle = log_file.open("w", encoding="utf-8")

    results: list[dict] = []
    consecutive_blocks = 0
    stopped_early = False
    stop_reason = None

    async with AsyncCamoufox(
        headless=args.headless,
        geoip=True,
        locale=["ru-RU", "kk-KZ", "en-US"],
        humanize=True,
        persistent_context=True,
        user_data_dir=str(USER_DATA_DIR),
    ) as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] {url}")
            attempts = 0
            rec: dict = {}
            while attempts <= RETRY_PER_URL:
                attempts += 1
                rec = await fetch_one(page, url)
                if rec["block"] and rec["block_reason"] == "exception" and attempts <= RETRY_PER_URL:
                    print(f"  retry {attempts} after error: {rec['error']}")
                    await asyncio.sleep(random.uniform(*PAUSE_RANGE))
                    continue
                break
            results.append(rec)
            log_handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log_handle.flush()
            print(
                f"  -> status={rec['status']} timing={rec['timing_ms']}ms "
                f"size={rec['html_size']} gate_cleared={rec['gate_cleared']} "
                f"({rec.get('gate_cleared_after_ms')}ms) "
                f"jsonld={rec['jsonld_has_product']} microdata={rec['microdata_has_price']} "
                f"block={rec['block']} ({rec['block_reason'] or 'OK'})"
            )

            # D-03 stop-rule
            if rec["block"]:
                consecutive_blocks += 1
                if consecutive_blocks >= CONSECUTIVE_BLOCK_LIMIT:
                    stopped_early = True
                    stop_reason = f"{consecutive_blocks} consecutive blocks"
                    print(f"\n!!! STOP-RULE TRIGGERED: {stop_reason}")
                    break
                if rec["block_reason"] == "gate_shell_not_cleared":
                    stopped_early = True
                    stop_reason = f"gate-shell did not auto-clear after {GATE_POLL_DEADLINE_MS}ms at fetch {i}"
                    print(f"\n!!! STOP-RULE TRIGGERED: {stop_reason}")
                    break
            else:
                consecutive_blocks = 0

            if i < len(urls):
                await asyncio.sleep(random.uniform(*PAUSE_RANGE))

    log_handle.close()

    success = sum(1 for r in results if not r["block"] and r["has_product_data"])
    success_jsonld = sum(1 for r in results if not r["block"] and r["jsonld_has_product"])
    success_microdata = sum(1 for r in results if not r["block"] and r["microdata_has_offer"])
    success_with_price = sum(1 for r in results if not r["block"] and r["has_price_data"])
    gate_cleared = sum(1 for r in results if r["gate_cleared"])
    gate_required_wait = sum(
        1 for r in results
        if r["gate_cleared"] and (r["gate_cleared_after_ms"] or 0) > 0
    )
    blocks = sum(1 for r in results if r["block"])
    gate_shell_rate_pct = (
        sum(1 for r in results if not r["gate_cleared"]) / len(results) * 100
        if results else 0.0
    )

    summary = {
        "mode": "camoufox-kz",
        "engine": "camoufox",
        "proxy_used": False,
        "total_attempted": len(results),
        "total_planned": len(urls),
        "success_count": success,
        "success_jsonld_count": success_jsonld,
        "success_microdata_count": success_microdata,
        "success_with_price_count": success_with_price,
        "gate_cleared_count": gate_cleared,
        "gate_required_wait_count": gate_required_wait,
        "block_count": blocks,
        "gate_shell_rate_pct": round(gate_shell_rate_pct, 1),
        "stopped_early": stopped_early,
        "stop_reason": stop_reason,
        "passes_d13_threshold": success >= 95,           # D-13
        "fragile_per_d15": gate_shell_rate_pct > 20,     # D-15 adapted to Camoufox
    }
    out = {"summary": summary, "results": results}
    out_path = OUTPUT_DIR / "tier2-camoufox-kz-results.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(
        f"SUMMARY: success={success}/{len(results)} "
        f"(jsonld={success_jsonld}, microdata={success_microdata}, with_price={success_with_price}), "
        f"gate_cleared={gate_cleared}, required_wait={gate_required_wait}, blocks={blocks}, "
        f"gate_shell_rate={gate_shell_rate_pct:.1f}%, stopped_early={stopped_early}"
    )
    print(f"D-13 (>=95/100): {'PASS' if summary['passes_d13_threshold'] else 'FAIL'}")
    print(f"D-15 (fragile if >20% gate-shell): {'YES' if summary['fragile_per_d15'] else 'NO'}")
    print(f"\nSaved: {out_path}")
    print(f"Log:   {log_file}")


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--headless", default="true", choices=["true", "false"])
    args = ap.parse_args()
    args.headless = args.headless == "true"
    return args


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
