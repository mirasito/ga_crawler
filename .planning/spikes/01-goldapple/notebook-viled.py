"""
Spike 01: viled.kz curl_cffi feasibility check (RECON-02).

Reproducible: запускается из repo root через
    uv run python .planning/spikes/01-goldapple/notebook-viled.py

Per RECON-02: >=10 product fetches via curl_cffi impersonate="chrome".
Per CONTEXT.md "Не обсуждали явно":
  - timing per fetch (ms)
  - JSON-LD presence per fetch
  - pagination shape (manual observation in Task 1 + this script's per-URL data)
  - robots/UA strictness (do we get blocked? do we need realistic UA?)

Output: sample-payloads/viled-fetch-results.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 stdout on Windows (per 01-05 deviation 2 lesson).
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

from curl_cffi import requests
from selectolax.parser import HTMLParser

# Config
URLS_FILE = Path(".planning/spikes/01-goldapple/sample-payloads/viled-product-urls.txt")
RESULTS_FILE = Path(".planning/spikes/01-goldapple/sample-payloads/viled-fetch-results.json")
PAUSE_S = 2.0  # per tos-audit.md committed rate-limit для viled (2s sequential)
TIMEOUT_S = 30
MAX_URLS = 15
IMPERSONATE = "chrome"


def fetch_one(url: str) -> dict:
    """Fetch one URL, return per-URL metrics (status, timing, JSON-LD presence)."""
    started = time.perf_counter()
    record: dict = {
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "status": None,
        "timing_ms": None,
        "content_length": None,
        "content_type": None,
        "jsonld_present": False,
        "jsonld_has_product": False,
        "jsonld_has_price": False,
        "jsonld_currency": None,
        "next_data_present": False,
        "error": None,
    }
    try:
        r = requests.get(url, impersonate=IMPERSONATE, timeout=TIMEOUT_S)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        record["status"] = r.status_code
        record["timing_ms"] = elapsed_ms
        record["content_length"] = len(r.content)
        record["content_type"] = r.headers.get("content-type", "")

        if r.status_code == 200 and "html" in record["content_type"].lower():
            tree = HTMLParser(r.text)
            jsonld_nodes = tree.css('script[type="application/ld+json"]')
            record["jsonld_present"] = len(jsonld_nodes) > 0
            for n in jsonld_nodes:
                try:
                    raw = n.text() or ""
                    obj = json.loads(raw)
                except (json.JSONDecodeError, AttributeError):
                    continue
                items = obj if isinstance(obj, list) else [obj]
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    typ = it.get("@type", "")
                    typ_list = typ if isinstance(typ, list) else [typ]
                    if "Product" in typ_list:
                        record["jsonld_has_product"] = True
                        offers = it.get("offers", {})
                        offer_list = offers if isinstance(offers, list) else [offers]
                        for o in offer_list:
                            if isinstance(o, dict) and o.get("price"):
                                record["jsonld_has_price"] = True
                                if o.get("priceCurrency"):
                                    record["jsonld_currency"] = o["priceCurrency"]
            # Also note __NEXT_DATA__ presence (viled is Next.js per 01-04/01-05)
            if 'id="__NEXT_DATA__"' in r.text:
                record["next_data_present"] = True
    except Exception as e:
        record["error"] = f"{type(e).__name__}: {e}"
    return record


def main() -> int:
    if not URLS_FILE.exists():
        print(f"ERROR: URLs file not found: {URLS_FILE}")
        print("Run _fetch_viled_urls.py first (Task 1 of plan 01-07).")
        return 1

    urls = [u.strip() for u in URLS_FILE.read_text(encoding="utf-8").splitlines() if u.strip()]
    urls = urls[:MAX_URLS]
    print(f"Fetching {len(urls)} viled.kz URLs via curl_cffi impersonate={IMPERSONATE!r} "
          f"with pause={PAUSE_S}s between fetches ...\n")

    results: list[dict] = []
    run_started = time.perf_counter()
    for i, url in enumerate(urls, 1):
        print(f"  [{i:>2}/{len(urls)}] {url}")
        rec = fetch_one(url)
        if rec["error"]:
            print(f"        ERR: {rec['error']}")
        else:
            print(f"        status={rec['status']} timing={rec['timing_ms']}ms "
                  f"jsonld_product={rec['jsonld_has_product']} "
                  f"jsonld_price={rec['jsonld_has_price']} "
                  f"next_data={rec['next_data_present']} "
                  f"size={rec['content_length']}b")
        results.append(rec)
        if i < len(urls):
            time.sleep(PAUSE_S)

    run_elapsed_s = round(time.perf_counter() - run_started, 1)

    # Aggregates
    successful = [r for r in results if r["status"] == 200]
    with_product_jsonld = [r for r in successful if r["jsonld_has_product"]]
    with_price_jsonld = [r for r in successful if r["jsonld_has_price"]]
    with_next_data = [r for r in successful if r["next_data_present"]]
    timings = [r["timing_ms"] for r in successful if r["timing_ms"]]
    errors = [r for r in results if r["error"]]
    non_200 = [r for r in results if r["status"] is not None and r["status"] != 200]

    summary: dict = {
        "config": {
            "impersonate": IMPERSONATE,
            "pause_s": PAUSE_S,
            "timeout_s": TIMEOUT_S,
            "rate_limit_source": "tos-audit.md viled.kz committed (2s sequential)",
        },
        "total": len(results),
        "successful_200": len(successful),
        "with_product_jsonld": len(with_product_jsonld),
        "with_price_jsonld": len(with_price_jsonld),
        "with_next_data": len(with_next_data),
        "non_200_status_codes": [r["status"] for r in non_200],
        "errors": [{"url": r["url"], "error": r["error"]} for r in errors],
        "timing_ms": {
            "min": min(timings) if timings else None,
            "max": max(timings) if timings else None,
            "avg": int(sum(timings) / len(timings)) if timings else None,
        },
        "wall_clock_s": run_elapsed_s,
        "currency_observed": next(
            (r["jsonld_currency"] for r in successful if r["jsonld_currency"]), None
        ),
    }
    out = {"summary": summary, "results": results}
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n[OK] Saved to {RESULTS_FILE}")
    print(f"\nSummary:")
    print(f"  HTTP 200: {summary['successful_200']}/{summary['total']}")
    print(f"  JSON-LD Product: {summary['with_product_jsonld']}/{summary['successful_200']}")
    print(f"  JSON-LD price (D-14 satisfaction proxy): "
          f"{summary['with_price_jsonld']}/{summary['successful_200']}")
    print(f"  __NEXT_DATA__ present: {summary['with_next_data']}/{summary['successful_200']}")
    print(f"  Currency: {summary['currency_observed']}")
    print(f"  Timing min/avg/max: {summary['timing_ms']['min']}/"
          f"{summary['timing_ms']['avg']}/{summary['timing_ms']['max']}ms")
    print(f"  Wall-clock: {summary['wall_clock_s']}s")
    if non_200:
        print(f"  Non-200 statuses: {summary['non_200_status_codes']}")
    if errors:
        print(f"  Errors: {len(errors)}")

    return 0 if summary["successful_200"] >= 1 else 2


if __name__ == "__main__":
    sys.exit(main())
