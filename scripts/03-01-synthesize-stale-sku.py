"""Synthesize tests/fixtures/goldapple/stale-sku-9.5kb.html.

Mimics spike result row 0 (status=200 + ~9500 bytes + no microdata + title='Loading <url>').
Per 03-PATTERNS.md §"Test fixtures" line 440: "no spike file — must be re-fetched
or synthesized". Wave 0 chooses synthesize (re-fetch needs Camoufox boot).

Critical properties (validate Pitfall 4: stale-SKU vs gate-shell distinction):
  - 5000 < size < 13000 bytes  (well below CHALLENGE_HTML_MAX_SIZE = 30000)
  - title contains 'Loading' (NOT 'checking' — that's the gate-shell marker)
  - NO <meta itemprop="price"> (microdata-absent — primary stale-SKU signal)
"""

import os
from pathlib import Path

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "goldapple" / "stale-sku-9.5kb.html"

filler = "<!-- " + ("x" * 9000) + " -->"
html = (
    '<!DOCTYPE html>\n'
    '<html lang="ru">\n'
    '<head><title>Loading https://goldapple.kz/7681000002-givenchy-pour-homme-blue-label</title></head>\n'
    f'<body><div id="root"></div>{filler}</body>\n'
    '</html>\n'
)

FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
FIXTURE_PATH.write_text(html, encoding="utf-8")
size = os.path.getsize(FIXTURE_PATH)
print(f"wrote {FIXTURE_PATH.name}, size={size} bytes")
assert 5000 < size < 13000, f"size out of range: {size}"
print("OK")
