# Acceptance results

Verified on 10 November 2026 with Power BI Desktop and the Power BI Modeling MCP. Source CSVs were read without modification. Live DAX results are in `dax-results.json`; independent CSV calculations are in `csv-checks.json`.

| Check | Result | Actual values |
|---|---|---|
| Rows and relationships | PASS | 138 fact rows, 7 insurers, 15 periods; 0 orphan keys, 0 blank source keys, no generated blank dimension members. Two active many-to-one, single-direction relationships. |
| 2025 Q2 medical loss ratio | PASS | Tawuniya 88.5543%; Bupa 95.0990%; Malath 84.8106%; Medgulf 96.0900%; GIG 107.6945%; Al Rajhi 100.9557%; Walaa 138.5219%. |
| FY2024 medical loss ratio | PASS | Bupa 94.0996%; Medgulf 99.5623%; Malath 100.1432%; Walaa 110.8854%; GIG 109.1104%; Al Rajhi 117.7902%; Tawuniya BLANK. |
| Combined ratio and missing expenses | PASS | Bupa FY2024 96.0257%; Medgulf combined ratio BLANK in every period. |
| Peer revenue shares | PASS | 100% for all 15 individual periods, subject only to floating-point precision. |
| Medical share of revenue | PASS at stated rounding | Bupa 100%; other insurers span 9.6702%–83.0256% across available periods (upper bound rounds to 83%; it is slightly above a literal 83.0000%). Q2 shares: Al Rajhi 28.9816%, GIG 24.8426%, Malath 39.1468%, Medgulf 78.1085%, Tawuniya 73.3323%, Walaa 13.9579%. |
| Tawuniya 2025 Q1 QoQ | PASS | BLANK; no 2024 Q4 row. |
| Pooled KPI calculation | PASS | All seven insurers in 2025 Q2: 93.29995%, versus arithmetic mean 101.67516%. Bupa + Tawuniya pooled: 92.16486%. |
| Page dimensions and layout | PASS | Native 1280 × 720 page rendered and inspected in Desktop; clipped title and table columns corrected. All seven insurer names appear in the slicer and vertical trend legend. |

## Implementation notes

- All 22 requested measures preserve the supplied DAX meaning. Measures live in `dim_insurer`, because Power BI prohibits a `Revenue` measure in the same table as a `revenue` column (case-insensitive collision). Display folders match sections 2–4.
- Three CSV import queries use UTF-8, a required text `DataFolder` parameter, explicit types, and null preservation. All fact columns except `is_derived` are hidden. `period_label` sorts by `period_key`.
- Default slicer state is quarter / 2025 Q2 / all insurers / derived=False. The period and frequency slicers do not filter the quarterly trend; its own filter restricts it to quarters. The derived slicer still controls the trend.
- Tooltip page is hidden in reading mode. Tooltip configuration exists, but hover behavior was not separately exercised. Prior-period values, ranking, and pooled values were tested through DAX.
- The trend legend is on the right to show all seven full names. Table columns use short captions to fit the one-page layout.
- Power BI Desktop normalized the report to PBIR version 2.0.0 and its native schema versions when saving.

## Open or save

1. Open `ksa_insurer_benchmark.pbip` from this folder in Power BI Desktop.
2. If moving the project, choose Transform data > Edit parameters, set `DataFolder` to the folder containing the three original CSVs, then Apply changes and Refresh.
3. To create another PBIX copy, use File > Save as > Browse this device, select **Power BI file (*.pbix)**, and save to `reports\powerbi\ksa_insurer_benchmark.pbix`.
4. When inspecting FY2024, switch Frequency to annual before selecting FY2024. The trend intentionally remains quarterly.

The report preserves the project limitations in its footer: small sample, derived Q4, IFRS 17 expense definition, gross reinsurance basis, and no causal or claim-denial claims.

PBIX copy successfully saved by Desktop as reports\powerbi\ksa_insurer_benchmark.pbix. See FILES.txt for the created-file inventory. desktop-verification.jpg records the inspected Desktop view.

## Review rerun
All numerical checks above were rerun against the live Desktop model after the review fixes, with identical values. See REVIEW_FIXES.md for the new card tests, visual changes, tooltip limitation and native reference-line thickness limitation; review-dax-results.json contains the new raw query results. There are now 23 measures (the original 22 plus Rank Label (card)).
