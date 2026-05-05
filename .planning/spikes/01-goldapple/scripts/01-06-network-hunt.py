"""
Spike 01-06: Goldapple JSON-endpoint hunt via Patchright network capture.

REPLACES manual DevTools session (plan 01-06 Task 1) with programmatic equivalent.
Per-user authorisation: 01-04 found goldapple globally JS-gated, so DevTools requires
loading the site in a real browser anyway; programmatic capture via page.on('request')
exposes the SAME endpoints DevTools would show, in machine-readable form.

This is a THROWAWAY recon script (kept for re-run / drift check), NOT production code.

Configuration:
- Patchright (NOT vanilla playwright) per CONTEXT.md D-01 (Tier 2 default).
- Persistent context per CONTEXT.md D-04 (cookies live across page-loads).
- headless=False so the operator can spot-watch the JS-challenge auto-resolve on
  first run; flip to True for batch/Wave 2 once verified.
- 3-5s random sleep between page-loads per 01-04 committed rate-limit.
- NO proxy (D-06 baseline = KZ-laptop direct).
- viewport 1366x900 — common laptop res, looks natural.

Outputs:
- .planning/spikes/01-goldapple/sample-payloads/goldapple-network-trace.json
  Machine-readable trace: all request/response events + render markers per page.
- .planning/spikes/01-goldapple/sample-payloads/goldapple-product-html-{1,2}.html
  Two product-page HTML samples (different brands) for post-hoc __NEXT_DATA__/JSON-LD analysis.

Operator decision points captured in trace via 'render-marker' phase entries:
- has_next_data: True/False (Tier 0 viability if True)
- has_jsonld:    True/False (D-14 success-criterion realism)
- still_challenge: True/False (Patchright pass/fail signal — warm-up for 01-08)
- title:         page <title> after render
- html_size:     proxy for "real content vs challenge shell" (challenge ≈ 18 912 B per 01-04)
"""
import asyncio
import json
import random
import time
from pathlib import Path

from patchright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]  # .planning/spikes/01-goldapple/
USER_DATA_DIR = ROOT / "browser-state"  # gitignored (see .gitignore)
SAMPLES_DIR = ROOT / "sample-payloads"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# 7 URLs covering: home, brands index, 2 brand listings, 3 product pages from
# different brands. Product URLs picked from goldapple-all-urls.txt
# (numeric-id /<id>-<slug> pattern == real Magento product entity_id).
# Diversity across brands per CONTEXT.md D-12 (5 brands selected for Phase 1).
URLS = [
    ("home",           "https://goldapple.kz/"),
    ("brands-index",   "https://goldapple.kz/brands/"),
    ("brand-tom-ford", "https://goldapple.kz/brands/tom-ford"),
    ("brand-givenchy", "https://goldapple.kz/brands/givenchy"),
    # Three product pages from selected brands (distinct brands for cross-validation):
    ("product-givenchy",     "https://goldapple.kz/19000032744-givenchy-gentleman-reserve-privee-eau-de-parfum"),
    ("product-tom-ford",     "https://goldapple.kz/f/tom-ford-tualetnaja-voda"),  # facet not product but tom-ford slug-products are sparse — facet still tests JSON-LD/__NEXT_DATA__
    ("product-creed",        "https://goldapple.kz/26543200002-creed-royal-water"),
]

# Map URL identifier to which sample slot saves HTML (only 2 product HTMLs needed).
HTML_SAVE_SLOTS = {
    "product-givenchy": SAMPLES_DIR / "goldapple-product-html-1.html",
    "product-creed":    SAMPLES_DIR / "goldapple-product-html-2.html",
}


async def main() -> None:
    captured: list[dict] = []
    timings: dict[str, dict] = {}
    challenge_pass_count = 0
    challenge_fail_count = 0

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=False,  # operator watch first run; flip True for 01-08 batch
            viewport={"width": 1366, "height": 900},
            # No proxy: D-06 baseline = KZ-laptop direct.
            # No UA override: Patchright defaults already include realistic UA.
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Capture every request/response on every page-load. Lambdas append to
        # the shared `captured` list; we tag with current page_url externally.
        current_label = {"v": ""}

        def on_request(req):
            captured.append({
                "label": current_label["v"],
                "phase": "request",
                "url": req.url,
                "method": req.method,
                "resource_type": req.resource_type,
            })

        def on_response(resp):
            try:
                ct = resp.headers.get("content-type", "")
            except Exception:
                ct = ""
            captured.append({
                "label": current_label["v"],
                "phase": "response",
                "url": resp.url,
                "status": resp.status,
                "content_type": ct,
            })

        page.on("request", on_request)
        page.on("response", on_response)

        for label, url in URLS:
            current_label["v"] = label
            t0 = time.monotonic()
            print(f"[fetch] {label:22s} {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                # Wait for JS-challenge auto-resolve + dynamic content render.
                # First run with 5s showed 7/7 still on challenge shell -> need longer.
                # Strategy: wait up to 20s for challenge to clear (poll page title).
                challenge_clear_deadline = time.monotonic() + 20.0
                while time.monotonic() < challenge_clear_deadline:
                    await page.wait_for_timeout(1500)
                    try:
                        cur_title = await page.title()
                        if 'checking device' not in cur_title.lower():
                            break
                    except Exception:
                        pass
                # Try networkidle as additional settle signal (5s budget).
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                html = await page.content()
                title = await page.title()
                t1 = time.monotonic()

                has_next_data = ('__NEXT_DATA__' in html) or ('/_next/data/' in html)
                has_jsonld = '<script type="application/ld+json"' in html
                # Challenge-shell heuristic: from 01-04 we know the challenge HTML
                # is ~18 912 B and contains the title "Gold Apple - checking device".
                still_challenge = (
                    'checking device' in html.lower()
                    or (len(html) < 30_000 and 'goldapple' in html.lower() and not has_next_data)
                )

                if still_challenge:
                    challenge_fail_count += 1
                else:
                    challenge_pass_count += 1

                marker = {
                    "label": label,
                    "phase": "render-marker",
                    "url": url,
                    "title": title,
                    "html_size": len(html),
                    "has_next_data": has_next_data,
                    "has_jsonld": has_jsonld,
                    "still_challenge": still_challenge,
                    "render_seconds": round(t1 - t0, 2),
                }
                captured.append(marker)
                timings[label] = marker
                print(f"  -> {title!r:40s} | size={len(html):7d} | next_data={has_next_data} | "
                      f"jsonld={has_jsonld} | challenge={still_challenge} | {round(t1 - t0, 2)}s")

                # Save HTML for two product pages (post-hoc analysis in Task 2).
                if label in HTML_SAVE_SLOTS:
                    HTML_SAVE_SLOTS[label].write_text(html, encoding="utf-8")
                    print(f"  -> saved HTML to {HTML_SAVE_SLOTS[label].name}")

                # Honor 3-5s random rate-limit per 01-04 committed value.
                pause = random.uniform(3.0, 5.0)
                await page.wait_for_timeout(int(pause * 1000))
            except Exception as e:
                err = {"label": label, "phase": "error", "url": url, "error": repr(e)[:300]}
                captured.append(err)
                print(f"  -> ERROR: {err['error']}")

        await ctx.close()

    # Persist trace.
    trace_path = SAMPLES_DIR / "goldapple-network-trace.json"
    trace_path.write_text(json.dumps(captured, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[done] saved {len(captured)} events -> {trace_path.name}")
    print(f"[challenge] pass={challenge_pass_count} / fail={challenge_fail_count}")

    # Summary stdout for operator (also persisted in trace for re-analysis).
    print("\n=== Per-page summary ===")
    print(f"{'label':22s} {'size':>7s} {'next':>5s} {'jsonld':>6s} {'chal':>5s} {'sec':>5s}  title")
    for label, m in timings.items():
        print(f"{label:22s} {m['html_size']:7d} {str(m['has_next_data']):>5s} "
              f"{str(m['has_jsonld']):>6s} {str(m['still_challenge']):>5s} "
              f"{m['render_seconds']:>5.2f}  {m['title'][:60]!r}")


if __name__ == "__main__":
    asyncio.run(main())
