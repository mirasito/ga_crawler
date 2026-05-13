"""Ad-hoc 30-PDP capture for Phase 8 W0 shape-sampling spike (D-801..D-804).

NOT a long-term committed CLI surface — Phase 9 (TEST-HARNESS-05) formalizes this
as `python -m ga_crawler capture-fixtures`. For Phase 8, this script is a
one-shot helper used to populate .planning/spikes/v1.1-brand-name-shapes/.

OPERATOR TASK (Plan 08-01 Task 1):
    Fill the 30 placeholder URL tuples below with real goldapple.kz PDP URLs
    matching the stratification buckets defined in CONTEXT.md D-801. Each URL
    MUST match PRODUCT_URL_RE from src/ga_crawler/enumeration/goldapple_sitemap.py
    (i.e. https://goldapple.kz/<digits>-<a-z0-9а-я-+>).

Run with:
    uv run python .planning/spikes/v1.1-brand-name-shapes/capture.py

Output: 30 files pdp-NN-<slug>.html in this directory (NN zero-padded 01..30).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow `from ga_crawler...` imports when run directly via `uv run python`.
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ga_crawler.fetchers.goldapple import GoldappleFetcher  # noqa: E402

# Stratified 5 × 6 = 30 URLs per CONTEXT.md D-801.
# Sourced from goldapple.kz/sitemap.xml via curate_urls.py (52,051 unique slugs).
# Buckets adapted to real KZ inventory: Tom Ford / Jo Malone / Atelier Cologne /
# Diptyque / Chanel / YSL / Versace / Hugo-Boss-compound / Профумум Рома /
# Натура Сибирика-Cyrillic NOT available in goldapple.kz/KZ sitemap;
# substitutes selected from same shape category.
URLS: list[tuple[str, str]] = [
    # ---- Bucket 1: Lux (Creed × 6 / Dior / Frederic Malle as fillers)
    ("lux-creed-royal-water", "https://goldapple.kz/26543200002-creed-royal-water"),
    ("lux-creed-carmina", "https://goldapple.kz/19000491423-creed-carmina"),
    ("lux-creed-queen-of-silk", "https://goldapple.kz/19000491455-creed-queen-of-silk"),
    ("lux-creed-aventus-for-her", "https://goldapple.kz/19000491450-creed-aventus-for-her"),
    ("lux-creed-aventus", "https://goldapple.kz/19000491449-creed-aventus"),
    ("lux-creed-millesime-imperial", "https://goldapple.kz/19000491426-creed-millesime-imperial"),

    # ---- Bucket 2: Mass-market (Armani [armani-code FORCED — Bug #2 evidence] + Givenchy ×4 + Armani-prive)
    ("mass-armani-code", "https://goldapple.kz/19000195723-armani-code"),
    ("mass-armani-prive-orangerie-venise", "https://goldapple.kz/26600200023-armani-prive-orangerie-venise"),
    ("mass-givenchy-pour-homme-blue-label", "https://goldapple.kz/7681000002-givenchy-pour-homme-blue-label"),
    ("mass-givenchy-gentleman-reserve-privee-eau-de-parfum", "https://goldapple.kz/19000032744-givenchy-gentleman-reserve-privee-eau-de-parfum"),
    ("mass-givenchy-pour-homme", "https://goldapple.kz/7680200024-givenchy-pour-homme"),
    ("mass-givenchy-irresistible-nectar", "https://goldapple.kz/19000488687-givenchy-irresistible-nectar"),

    # ---- Bucket 3: Niche (STEREOTYPE ×4 [Bug #1+#2 FORCED — niche-stereotype-sago is canonical bug source] + sago + Byredo)
    ("niche-stereotype-flow", "https://goldapple.kz/19000440471-stereotype-flow"),
    ("niche-stereotype-brace", "https://goldapple.kz/19000440472-stereotype-brace"),
    ("niche-stereotype-unframe", "https://goldapple.kz/19000440473-stereotype-unframe"),
    ("niche-stereotype-sago", "https://goldapple.kz/19000440474-stereotype-sago"),
    ("niche-sago", "https://goldapple.kz/19000331477-sago"),
    ("niche-byredo-alto-astral", "https://goldapple.kz/19000495948-byredo-alto-astral"),

    # ---- Bucket 4: RU-brands (Black Pearl ×3 + Natura Siberica ×2 + Sibirskie Travy)
    ("ru-black-pearl", "https://goldapple.kz/19000026808-black-pearl"),
    ("ru-black-pearl-eye-cream", "https://goldapple.kz/41160100001-black-pearl-eye-cream"),
    ("ru-black-pearl-gold-hydrogel-eye-patch", "https://goldapple.kz/99690100008-black-pearl-gold-hydrogel-eye-patch"),
    ("ru-natura-siberica-total-renewal", "https://goldapple.kz/19000491752-natura-siberica-total-renewal"),
    ("ru-natura-siberica-refresh-scalp", "https://goldapple.kz/19000491787-natura-siberica-refresh-scalp"),
    ("ru-sibirskie-travy", "https://goldapple.kz/30013000004-sibirskie-travy"),

    # ---- Bucket 5: Multi-word brands (Maison Margiela ×2 + Calvin Klein ×4 — tests 2-word brand prefix-strip)
    ("multi-maison-margiela-set-replica-jazz-club", "https://goldapple.kz/19000223943-maison-margiela-set-replica-jazz-club"),
    ("multi-maison-margiela-replica-ideal-one", "https://goldapple.kz/19000479467-maison-margiela-replica-ideal-one"),
    ("multi-calvin-klein-silky-coconut", "https://goldapple.kz/19000507676-calvin-klein-silky-coconut"),
    ("multi-calvin-klein-nude-vanilla", "https://goldapple.kz/19000507674-calvin-klein-nude-vanilla"),
    ("multi-calvin-klein-sheer-peach", "https://goldapple.kz/19000507675-calvin-klein-sheer-peach"),
    ("multi-calvin-klein-cotton-musk", "https://goldapple.kz/19000507673-calvin-klein-cotton-musk"),
]
assert len(URLS) == 30, f"D-801 requires exactly 30 URLs (5 buckets × 6); got {len(URLS)}"

OUTPUT_DIR = Path(__file__).resolve().parent


async def main() -> None:
    """Sequential capture loop. fetch_one enforces 3-5s rate-limit per D-307."""
    fetcher = GoldappleFetcher(run_id=0)
    async with fetcher:
        for i, (slug, url) in enumerate(URLS, start=1):
            try:
                rec = await fetcher.fetch_one(fetcher._page, url)
            except Exception as exc:  # noqa: BLE001 — diagnostic capture, log & continue
                print(f"[{i:02d}/{len(URLS)}] FAIL {slug}: {type(exc).__name__}: {exc}")
                continue
            html = rec.get("html") or ""
            status = rec.get("status")
            print(f"[{i:02d}/{len(URLS)}] {status} len={len(html):>7} {slug}")
            if html:
                out = OUTPUT_DIR / f"pdp-{i:02d}-{slug}.html"
                out.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
