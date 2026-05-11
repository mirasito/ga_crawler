---
status: partial
phase: 05-reporter-excel-summary
source: [05-VERIFICATION.md]
started: 2026-05-12T20:30:00Z
updated: 2026-05-12T20:30:00Z
---

## Current Test

[awaiting human testing — open generated xlsx in MS Excel or LibreOffice Calc and validate visual rendering]

## Tests

### 1. 3-color conditional formatting renders correctly on Per-SKU deltas + Goldapple promos sheets

expected: `Дельта, %` column on "Per-SKU deltas" sheet shows a 3-color gradient (red → white → green) anchored at mid_value=0; same gradient on `Скидка, %` column on "Goldapple promos" sheet. Summary and Assortment gaps sheets have NO conditional formatting (D-508).
how_to_verify: run `uv run python -m ga_crawler report-run --run-id <existing-success-run-id>`, open `reports/YYYY-WNN.xlsx`, visually inspect both sheets' CF gradient direction (negative deltas should be red/cooler, positive deltas warmer/green).
result: [pending]

### 2. Russian Cyrillic + emoji glyphs render correctly in Summary sheet cell A1

expected: Cell A1 of the "Summary" sheet shows the D-504 caption with all Cyrillic glyphs ("📊 Неделя", "📦 viled:", "🎯 Совпало:", "🆕 Гэпы:", "💸 Промо у goldapple:", "🔝 Топ-3 дельты") and all emojis visible — no tofu boxes, no question marks, no mojibake. Russian column headers across all 4 sheets (`Бренд`, `Название`, `Объём`, `Цена viled, ₸`, etc.) render verbatim per D-503.
how_to_verify: open the xlsx in Excel/LibreOffice, scroll Summary sheet, then header row of each remaining sheet.
result: [pending]

### 3. freeze_panes + autofilter UX behaves as designed

expected: All 4 sheets have row 1 frozen (header stays visible when scrolling); autofilter dropdown arrows appear on every column header in row 1 (per D-508). Column widths are readable (no clipped Russian text).
how_to_verify: scroll each sheet vertically — header row stays pinned; click any column-1 header dropdown — filter UI opens.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

(none yet — pending visual inspection)

## Notes

Programmatic verification PASSED (6/6 must-haves, 610 tests green, 0 regressions). The 3 items above require human eyeballs because spreadsheet applications render CF gradients, Unicode glyphs, and freeze/filter UX outside the scope of automated openpyxl XML inspection (which only confirms the rules/attributes are written, not how Excel actually displays them).

Recommended trigger: run after the first live `weekly-run` produces a real-data xlsx (synthetic fixture xlsx is technically equivalent but operator confidence is higher with real prices). Resolve via `/gsd-verify-work 5`.
