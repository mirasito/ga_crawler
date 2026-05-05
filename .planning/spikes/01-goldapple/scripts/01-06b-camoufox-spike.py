"""
Camoufox spike — sibling of 01-06-network-hunt.py, but with Camoufox (Firefox-based,
C++-level fingerprint spoofing) instead of Patchright (Chromium).

Hypothesis under test (per 01-06 finding):
  goldapple.kz uses GroupIB/F.A.C.C.T. anti-bot. Patchright + KZ-laptop = 0/7
  gate-pass. The 403 is fingerprint-based, not rate-based. → A different fingerprint
  surface (Firefox via Camoufox) may pass the gate even from the same KZ-laptop IP.

Outcome we look for:
  - real Next.js app loads (HTML > 30 KB, NOT the 18 KB challenge shell)
  - gate API `/web/api/v1/settings` returns 200 (not 403)
  - `__NEXT_DATA__` or JSON-LD appears in HTML

If TRUE → IPRoyal can stay deferred; 01-08 should rebase on Camoufox.
If FALSE → both fingerprint AND IP-rep matter; revive 01-03 IPRoyal + plan combo test.

Throwaway spike script. NOT production code. Lives under .planning/spikes/.
"""
import asyncio
import json
import random
from pathlib import Path

from camoufox.async_api import AsyncCamoufox

REPO_ROOT = Path(__file__).resolve().parents[4]
SPIKE_DIR = REPO_ROOT / ".planning" / "spikes" / "01-goldapple"
USER_DATA_DIR = SPIKE_DIR / ".camoufox-state"  # gitignored (added below)
TRACE_JSON = SPIKE_DIR / "sample-payloads" / "camoufox-spike-trace.json"

URLS = [
    "https://goldapple.kz/",
    "https://goldapple.kz/brands/tom-ford",
    "https://goldapple.kz/19000032744-givenchy-gentleman-reserve-privee-eau-de-parfum",
]

CHALLENGE_SIGNATURE = "checking device"  # GroupIB GUN gate body marker (per 01-06)


async def main() -> None:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_JSON.parent.mkdir(parents=True, exist_ok=True)

    captured: list[dict] = []

    # geoip=True → spoof timezone/locale to match the OUTBOUND IP's geo (here = KZ).
    # locale=['ru-RU', 'kk-KZ'] → realistic Accept-Language for a KZ user.
    # humanize=True → small human-like cursor/keypress jitter (helps with behavioral fingerprinting).
    async with AsyncCamoufox(
        headless=False,
        geoip=True,
        locale=['ru-RU', 'kk-KZ', 'en-US'],
        humanize=True,
        persistent_context=True,
        user_data_dir=str(USER_DATA_DIR),
    ) as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        page.on("request", lambda req: captured.append({
            "page": page.url,
            "phase": "request",
            "url": req.url,
            "method": req.method,
            "resource_type": req.resource_type,
        }))
        page.on("response", lambda resp: captured.append({
            "page": page.url,
            "phase": "response",
            "url": resp.url,
            "status": resp.status,
            "content_type": resp.headers.get("content-type", "")[:120],
        }))

        for url in URLS:
            try:
                print(f"\n--- visiting: {url}", flush=True)
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)

                # Same wait pattern as Patchright run (01-06): 5s networkidle + 20s gate poll
                try:
                    await page.wait_for_load_state("networkidle", timeout=10_000)
                except Exception:
                    pass

                # Poll for gate-clearance: title changes away from "Gold Apple — checking device"
                deadline_ms = 25_000
                step_ms = 500
                elapsed = 0
                last_title = ""
                while elapsed < deadline_ms:
                    last_title = await page.title()
                    if "checking" not in last_title.lower():
                        break
                    await page.wait_for_timeout(step_ms)
                    elapsed += step_ms

                html = await page.content()
                size = len(html)
                still_challenge = (
                    CHALLENGE_SIGNATURE in html.lower()
                    and size < 30_000
                )
                has_next_data = "__NEXT_DATA__" in html
                has_jsonld = '<script type="application/ld+json"' in html

                marker = {
                    "page": url,
                    "phase": "render-marker",
                    "title": last_title,
                    "html_size": size,
                    "still_challenge": still_challenge,
                    "has_next_data": has_next_data,
                    "has_jsonld": has_jsonld,
                    "wait_ms_for_clearance": elapsed,
                }
                captured.append(marker)
                print(
                    f"  title={last_title!r}  size={size}  challenge={still_challenge}  "
                    f"__NEXT_DATA__={has_next_data}  jsonld={has_jsonld}  wait_ms={elapsed}",
                    flush=True,
                )

                # honor goldapple committed rate-limit (3-5s random per 01-04)
                pause = random.uniform(3.0, 5.0)
                await page.wait_for_timeout(int(pause * 1000))

            except Exception as e:
                err = repr(e)[:300]
                captured.append({"page": url, "phase": "error", "error": err})
                print(f"  ERROR: {err}", flush=True)

    TRACE_JSON.write_text(
        json.dumps(captured, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Quick verdict at the end
    markers = [c for c in captured if c.get("phase") == "render-marker"]
    if markers:
        gate_passes = sum(1 for m in markers if not m["still_challenge"])
        print(f"\n=== VERDICT: {gate_passes}/{len(markers)} pages passed the gate ===", flush=True)
        for m in markers:
            print(f"  {m['page']}: pass={not m['still_challenge']} size={m['html_size']}", flush=True)
    else:
        print("\n=== VERDICT: no render markers captured (likely error in script) ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
