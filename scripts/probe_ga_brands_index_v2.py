"""Probe v2 — goldapple.kz/brands authoritative brand→slug map.

v1 (probe_ga_brands_index.py) regex-scraped href links from rendered HTML
and only captured 8 Cyrillic-named brands. The /brands page actually
holds the full list in memory (the search input filters client-side per
the operator-confirmed screenshot 2026-05-16), so v1 was looking in the
wrong place.

Strategy
--------
1. Navigate to /brands; install a `page.on("response", ...)` listener
   BEFORE goto so we capture every XHR fired during initial render.
2. Wait + scroll aggressively to flush any lazy-loaded sections.
3. After settle, dump:
   - all captured XHR URLs with body sizes (to identify the brands JSON)
   - any JSON body whose URL looks brand-related
   - the page's window state for ``__NEXT_DATA__`` / `__INITIAL_STATE__`
     equivalents
   - rendered HTML (so a follow-up parse can iterate per brand)
4. Try search-input interaction: focus, type "tom", capture resulting
   XHR if filtering hits the network rather than running client-side.

Outputs:
  inbox/ga_brands_index/v2_xhr_log.json     — list of {url, status, size_bytes}
  inbox/ga_brands_index/v2_xhr_bodies/      — dir of <i>__<basename>.json files
  inbox/ga_brands_index/v2_window_state.json — extracted Next/Nuxt data blobs
  inbox/ga_brands_index/v2_rendered.html    — final HTML after settle+scroll

Usage:
    uv run python scripts/probe_ga_brands_index_v2.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ga_crawler.fetchers.goldapple import GoldappleFetcher

OUT_DIR = Path("inbox/ga_brands_index")
BODIES_DIR = OUT_DIR / "v2_xhr_bodies"


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BODIES_DIR.mkdir(parents=True, exist_ok=True)

    xhr_log: list[dict] = []
    captured_bodies: list[tuple[int, str, bytes]] = []
    counter = {"i": 0}

    async with GoldappleFetcher(run_id=9994, headless=True) as fetcher:
        page = fetcher._page

        def _on_response(resp):
            try:
                url = resp.url
                if not url.startswith("https://goldapple.kz"):
                    return
                # Skip obvious media/CSS/JS
                if any(seg in url for seg in (".png", ".jpg", ".webp", ".svg", ".css", ".woff", ".ico")):
                    return
                xhr_log.append({"url": url, "status": resp.status})
                # Schedule body capture for likely-API responses
                if "/api/" in url or url.endswith("/brands"):
                    asyncio.create_task(_capture_body(resp))
            except Exception as e:
                xhr_log.append({"error": str(e)})

        async def _capture_body(resp):
            try:
                body = await resp.body()
            except Exception:
                return
            counter["i"] += 1
            i = counter["i"]
            captured_bodies.append((i, resp.url, body))

        page.on("response", _on_response)

        url = "https://goldapple.kz/brands"
        print(f"=== GET {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(6_000)  # let initial XHRs land

        # Scroll the page hard — if the brand list is virtualized
        # (windowed), only visible cards exist in DOM at any moment.
        await page.evaluate(
            """() => new Promise(r => {
                let y = 0;
                const id = setInterval(() => {
                    window.scrollBy(0, 2000);
                    y += 2000;
                    if (y > 80000) { clearInterval(id); r(); }
                }, 200);
            })"""
        )
        await page.wait_for_timeout(4_000)

        # Try the search input: focus it (if present), type "tom",
        # observe whether new XHR fires (i.e. server-side filter) or
        # nothing happens (i.e. fully client-side).
        try:
            search_xhr_before = len(xhr_log)
            await page.evaluate(
                """() => {
                    const inputs = document.querySelectorAll('input');
                    for (const i of inputs) {
                        i.focus();
                        i.value = 'tom';
                        i.dispatchEvent(new Event('input', {bubbles: true}));
                        i.dispatchEvent(new Event('change', {bubbles: true}));
                        return i.outerHTML;
                    }
                    return null;
                }"""
            )
            await page.wait_for_timeout(3_000)
            search_xhr_after = len(xhr_log)
            print(f"  search-typing: XHR delta = {search_xhr_after - search_xhr_before}")
        except Exception as e:
            print(f"  search-typing failed: {e}")

        # Pull window state blobs
        window_state = await page.evaluate(
            """() => {
                const out = {};
                try {
                    const ns = document.getElementById('__NEXT_DATA__');
                    if (ns) out.__NEXT_DATA__ = JSON.parse(ns.textContent);
                } catch (e) { out.__NEXT_DATA___error = String(e); }
                try {
                    // Nuxt 3 hydration payload
                    const nx = document.getElementById('__NUXT_DATA__');
                    if (nx) out.__NUXT_DATA__ = nx.textContent.slice(0, 5_000_000);
                } catch (e) { out.__NUXT_DATA___error = String(e); }
                try {
                    if (window.__NUXT__) {
                        out.window___NUXT__ = JSON.parse(JSON.stringify(window.__NUXT__));
                    }
                } catch (e) { out.window___NUXT___error = String(e); }
                return out;
            }"""
        )

        html = await page.content()

    # ---- Persist captures ----
    (OUT_DIR / "v2_xhr_log.json").write_text(
        json.dumps(xhr_log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  XHR responses logged: {len(xhr_log)}")
    print(f"  bodies captured: {len(captured_bodies)}")

    for i, url, body in captured_bodies:
        slug = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1] or "root"
        slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug)[:60]
        out_path = BODIES_DIR / f"{i:03d}__{slug}.bin"
        out_path.write_bytes(body)
        # Try also json-pretty
        try:
            decoded = json.loads(body.decode("utf-8"))
            (BODIES_DIR / f"{i:03d}__{slug}.json").write_text(
                json.dumps(decoded, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    (OUT_DIR / "v2_window_state.json").write_text(
        json.dumps(window_state, ensure_ascii=False, indent=2)[:5_000_000],
        encoding="utf-8",
    )
    (OUT_DIR / "v2_rendered.html").write_text(html, encoding="utf-8")
    print(f"  HTML size: {len(html)}")
    print(f"  Done. See inbox/ga_brands_index/v2_*")


if __name__ == "__main__":
    asyncio.run(main())
