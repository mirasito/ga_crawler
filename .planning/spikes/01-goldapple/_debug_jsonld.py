"""Quick debug — fetch one goldapple product URL and dump HTML + extracted JSON-LD."""
import asyncio
import json
from pathlib import Path

from camoufox.async_api import AsyncCamoufox
from selectolax.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[3]
URL = "https://goldapple.kz/7681000002-givenchy-pour-homme-blue-label"
OUT_HTML = ROOT / ".planning" / "spikes" / "01-goldapple" / "sample-payloads" / "_debug-product-page.html"
OUT_JSONLD = ROOT / ".planning" / "spikes" / "01-goldapple" / "sample-payloads" / "_debug-jsonld-blocks.json"
USER_DATA_DIR = ROOT / ".planning" / "spikes" / "01-goldapple" / ".camoufox-state"


async def main() -> None:
    async with AsyncCamoufox(
        headless=True,
        geoip=True,
        locale=["ru-RU", "kk-KZ", "en-US"],
        humanize=True,
        persistent_context=True,
        user_data_dir=str(USER_DATA_DIR),
    ) as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()
        print(f"goto: {URL}")
        await page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        # Wait for title clearance
        for _ in range(50):
            t = await page.title()
            if "checking" not in t.lower():
                break
            await page.wait_for_timeout(500)
        html = await page.content()
        OUT_HTML.write_text(html, encoding="utf-8")
        print(f"  title: {await page.title()!r}")
        print(f"  size:  {len(html)}")

        tree = HTMLParser(html)
        blocks = []
        for s in tree.css('script[type="application/ld+json"]'):
            txt = s.text() or ""
            try:
                obj = json.loads(txt)
            except json.JSONDecodeError as e:
                blocks.append({"raw": txt[:500], "error": str(e)})
                continue
            blocks.append(obj)
        OUT_JSONLD.write_text(json.dumps(blocks, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  jsonld_blocks: {len(blocks)}")
        for i, b in enumerate(blocks):
            top = b.get("@type") if isinstance(b, dict) else "list-or-other"
            print(f"    [{i}] @type={top!r}")


if __name__ == "__main__":
    asyncio.run(main())
