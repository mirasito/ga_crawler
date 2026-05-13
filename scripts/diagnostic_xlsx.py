"""Ad-hoc diagnostic xlsx: показать пользователю что спарсилось из run #13.

Pipeline reporter не показывает raw snapshots (он показывает только matched
pairs / gaps), поэтому при `goldapple_comparable=0` итоговый xlsx выглядит
пустым. Этот скрипт обходит reporter и собирает 4 листа напрямую из БД:

1. Summary — KPI + найденные баги парсеров
2. Viled raw — все 82 SKU run #13
3. Goldapple raw — все 88 SKU run #13
4. Brand overlap — какие бренды есть у обоих

Не идемпотентен, не часть pipeline. Только для пользовательского sanity-check.
"""

import sqlite3
import pandas as pd
from pathlib import Path
import sys

DB = Path("prices.db")
RUN_ID = 13
OUT = Path(f"reports/run-{RUN_ID}-diagnostic.xlsx")

conn = sqlite3.connect(DB)

viled = pd.read_sql_query(
    """SELECT sku_id, brand, name, volume_raw, volume_norm,
       current_price, was_price, stock_state, url
       FROM snapshots WHERE run_id=? AND retailer='viled'
       ORDER BY brand, name""",
    conn, params=(RUN_ID,),
)
goldapple = pd.read_sql_query(
    """SELECT sku_id, brand, name, volume_raw, volume_norm,
       current_price, was_price, stock_state, url
       FROM snapshots WHERE run_id=? AND retailer='goldapple'
       ORDER BY brand, name""",
    conn, params=(RUN_ID,),
)

brand_overlap = pd.read_sql_query(
    """SELECT v.brand_norm AS brand,
              COUNT(DISTINCT v.sku_id) AS viled_skus,
              COUNT(DISTINCT g.sku_id) AS goldapple_skus
       FROM snapshots v
       JOIN snapshots g ON v.brand_norm = g.brand_norm
       WHERE v.run_id=? AND g.run_id=?
         AND v.retailer='viled' AND g.retailer='goldapple'
       GROUP BY v.brand_norm
       ORDER BY viled_skus DESC""",
    conn, params=(RUN_ID, RUN_ID),
)

summary_rows = [
    ("Run ID", RUN_ID),
    ("Дата", "2026-05-13 (тестовый локальный запуск)"),
    ("", ""),
    ("=== Сырые счётчики ===", ""),
    ("Viled SKU (всего)", len(viled)),
    ("Goldapple SKU (всего)", len(goldapple)),
    ("Общих брендов", len(brand_overlap)),
    ("", ""),
    ("=== Качество данных ===", ""),
    ("Viled с волюмом извлечённым", int(viled["volume_norm"].notna().sum() - (viled["volume_norm"] == "").sum())),
    ("Viled с ценой", int(viled["current_price"].notna().sum())),
    ("Goldapple с волюмом извлечённым", int(goldapple["volume_norm"].notna().sum() - (goldapple["volume_norm"] == "").sum())),
    ("Goldapple с ценой", int(goldapple["current_price"].notna().sum())),
    ("", ""),
    ("=== Найденные баги парсеров ===", ""),
    ("BUG #1 Goldapple", "volume_norm пуст у 88/88 SKU — парсер не находит volume tag"),
    ("BUG #2 Goldapple", "brand+name склеены (видно как 'Armaniarmani code')"),
    ("BUG #3 Viled", "volume_raw содержит весь name, не отдельное поле — regex срабатывает только если '100 мл' в названии"),
    ("Последствие", "match-rate = 0 потому что ключ (brand+name+volume) не строится у goldapple"),
    ("Это prod-баг", "Да — на VPS будет идентично. Документируем как v1.1 backlog."),
    ("", ""),
    ("=== Ограничения v1 (известные) ===", ""),
    ("Viled пагинация", "SSR ignores ?page=N → парсим только page-1, ~82 SKU вместо 1956+5692"),
    ("Goldapple scope", "только brand-intersect (бренды которые есть у viled)"),
]
summary = pd.DataFrame(summary_rows, columns=["Параметр", "Значение"])

OUT.parent.mkdir(exist_ok=True)
with pd.ExcelWriter(OUT, engine="xlsxwriter") as w:
    summary.to_excel(w, sheet_name="Summary", index=False)
    viled.to_excel(w, sheet_name=f"Viled ({len(viled)} SKU)", index=False)
    goldapple.to_excel(w, sheet_name=f"Goldapple ({len(goldapple)} SKU)", index=False)
    brand_overlap.to_excel(w, sheet_name="Brand overlap", index=False)

    for sheet_name in w.sheets:
        ws = w.sheets[sheet_name]
        ws.set_column(0, 10, 20)
        ws.freeze_panes(1, 0)

print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
print(f"viled={len(viled)} goldapple={len(goldapple)} overlap_brands={len(brand_overlap)}")
