"""HTML normalization for syrupy snapshot diff (T-09-DRIFT mitigation).

Camoufox HTML capture is non-deterministic on goldapple PDP:
  - <meta name="csrf-token" content="..."> rotates per request
  - cf_clearance cookie echoes in inline <script> JSON payloads
  - CSS-class build-hash suffix (_ga-pdp-title__heading_<HASH>) rotates on deploys
  - __NEXT_DATA__ buildId field

Without normalization, every --refresh-live run produces false-positive
drift. RESEARCH §7.1 + SKILL.md L45 (CSS-class build-hash evidence).
"""

from __future__ import annotations

import re

_CSRF_TOKEN_RE = re.compile(r'(<meta name="csrf-token" content=")[^"]*(")')
_CF_CLEARANCE_RE = re.compile(r'cf_clearance=[^;"\s]*')
_BUILD_HASH_RE = re.compile(
    r'(_ga-pdp-(?:title__heading|title__brand|title__name|brand|name)_)[a-zA-Z0-9_]+'
)
_BUILD_ID_RE = re.compile(r'("buildId":")[^"]*(")')


def normalize_for_snapshot(html: str) -> str:
    """Strip rotating tokens. Idempotent: normalize(normalize(x)) == normalize(x)."""
    html = _CSRF_TOKEN_RE.sub(r'\1NORM\2', html)
    html = _CF_CLEARANCE_RE.sub('cf_clearance=NORM', html)
    html = _BUILD_HASH_RE.sub(r'\1NORM', html)
    html = _BUILD_ID_RE.sub(r'\1NORM\2', html)
    return html
