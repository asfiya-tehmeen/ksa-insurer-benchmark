# Data dictionary

All files are in `data/clean/`. Every number traces to a source PDF page (`source_file`, `source_page`); the PDFs are in `data/raw/` and are not redistributed, so `reports/sources.csv` lists where each came from.

## Conventions (apply to every table)

| Topic | Rule |
|---|---|
| Currency and unit | Saudi riyal, **thousands** (`unit = SAR_thousands`). Milliman sector table in `src/crosscheck.py` is in millions and says so. |
| Insurer keys | `alrajhitakaful` (Al Rajhi Takaful), `bupa` (Bupa Arabia), `gig` (Gulf Insurance Group, the Saudi company), `malath`, `medgulf`, `tawuniya`, `walaa`. |
| Period labels | Quarter `YYYYQn` (the **three-month** period, e.g. `2025Q3` = Jul to Sep 2025), full year `YYYYFY`. `ytd` rows carry the year-to-date figure (6 or 9 months) under the label of the filing quarter. |
| Signs | `statements_long` and `segments_raw` keep the **printed** sign (costs negative). `segment_long`, `panel` and `panel_segment` store **claims positive** and keep `reinsurance_net` and `pool_surplus` signed (negative = net cost / negative contribution). |
| IFRS 17 | Every row is 2023 or later, so `post_ifrs17` is always true. No pre-2023 (IFRS 4) data were extracted. |
| `basis` | `current` = value comes from the filing for that period. `comparative` = taken from the prior-year column of a later filing. `derived` = computed (Q4 = FY minus 9M). Where both `current` and `comparative` exist the panels use `current`. Overlapping values were checked and never conflict. |
| `scope` | `period` = the quarter (Q1 to Q3) or the full year. `ytd` = 6 or 9 month cumulative column. Panels use `period` only. |
| `method` | `pdfplumber` = read from the PDF text layer. `ocr` = the page is scanned or its text layer is unreliable, so it was read by OCR (`src/ocr.py`) and verified by reconciliation checks. `derived_q4` = FY minus 9M. |

## statements_long.csv (1,780 rows)

Consolidated statement of income, one row per printed line and column. Grain: insurer x period x basis x scope x line.

| Column | Meaning |
|---|---|
| insurer, period | See conventions. |
| basis, scope | `current` / `comparative`; `period` / `ytd`. |
| raw_label | The line label exactly as extracted. OCR text may have missing spaces ("Insurancerevenue"); mapping ignores spaces. |
| value | Printed value, printed sign. |
| unit | `SAR_thousands`. |
| source_file, source_page | PDF file name in `data/raw/` and **PDF page index** (1-based; not the printed page number). |
| method | `pdfplumber` or `ocr`. |

## milliman_long.csv (480 rows)

Milliman KSA Industry Update 2025, Exhibits 1 to 4, whole company, 24 insurers x 2022 to 2025. Used only to cross-check.

| Column | Meaning |
|---|---|
| insurer | Milliman's name (for example `AlRajhi Takaful`, `MALATH`). |
| period | `YYYYFY`. |
| item | `insurance_revenue` (Ex.1), `gwp` (Ex.2), `net_income` (Ex.3), `total_assets`, `equity` (Ex.4). |
| value, unit | SAR thousands. |
| source_file, source_page, source_exhibit | PDF page index and exhibit. Printed page number = PDF index minus 2. |

## segments_raw.csv (588 rows)

Operating-segment note extraction, **non-Bupa insurers only** (Bupa is mono-line; see `segment_long`). Grain: insurer x period x basis x scope x segment x item.

| Column | Meaning |
|---|---|
| segment | `medical` (the insurer's medical / health column) or `total` (the note's total column). Each insurer defines its own medical segment (Tawuniya includes compulsory medical business; Al Rajhi labels it "Medical / Health"; GIG "Health"). |
| item | `revenue` (insurance revenue), `claims_incurred` (**insurance service expenses**, printed sign), `reinsurance_net` (net result from reinsurance contracts held), `service_result` (insurance service result; not printed by GIG), `pool_surplus` (share of surplus from insurance pools; Medgulf only in the segment note). |
| other columns | As in `statements_long`. `source_page` is the segment-note page. |

Integrity: each row's segment columns sum to the printed total column (within 3 thousand), otherwise the row is rejected.

## segment_long.csv (788 rows)

Resolved version of `segments_raw` plus Bupa plus derived Q4. One value per insurer x period x scope x segment x item.

| Column | Meaning |
|---|---|
| item | `revenue`, `claims` (**insurance service expenses, stored positive**), `reinsurance_net`, `pool_surplus`, `service_result`. |
| basis | `current`, `comparative` or `derived`. |
| method | `pdfplumber`, `ocr` or `derived_q4`. Segment-note pages were all read from the text layer; Bupa rows inherit the method of the statement page. |
| mono_line | True for Bupa. Its `medical` and `total` rows are identical (it only writes medical insurance). |
| segment_note_page | Bupa only: PDF page where the filing states it is a mono-line medical insurer. |
| source_file, source_page | For `derived_q4` rows these are text: `"FYfile minus 9Mfile"` and `"FYpage/9Mpage"`. |

## panel.csv (57 rows)

Whole-company panel from the consolidated statements. Grain: insurer x period (quarters and full years, 2023 to 2025). Superseded as the primary view by `panel_segment.csv`, kept for reference and for the segment-total reconciliation.

| Column | Meaning |
|---|---|
| revenue | Insurance revenue. |
| claims_incurred | Insurance service expenses (positive). |
| reinsurance_net | Net result from reinsurance contracts held (signed). |
| gross_service_result | Insurance service result before reinsurance (where printed). |
| service_result | Insurance service result after reinsurance. |
| direct_service_result, pool_surplus | GIG's "directly written business" subtotal and pool surplus (GIG, Medgulf). |
| investment_income, other_expenses, pretax_income, net_income | As printed (net income is after zakat and tax). `other_expenses` = other operating expenses; Medgulf prints none. |
| loss_ratio | claims_incurred / revenue. |
| expense_ratio, combined_ratio | other_expenses / revenue; loss ratio + expense ratio. Empty for Medgulf. |
| service_margin | service_result / revenue. |
| waterfall_diff, waterfall_ok | Absolute gap between revenue - claims + reinsurance (+ pool) and the printed subtotal (SAR thousands); `waterfall_ok` is true when within 2. |
| basis | `current` or `mixed/comparative` (at least one value came from a later filing's prior-year column). |
| freq, post_ifrs17, source_files | `annual` / `quarter`; always true; `;`-separated files. |

## panel_segment.csv (138 rows): the main analysis table

Grain: insurer x period x segment (`medical`, `total`). 69 insurer-periods x 2 segments.

| Column | Meaning |
|---|---|
| segment | `medical` or `total` (whole company). |
| revenue, claims, reinsurance_net, pool_surplus, service_result | As in `segment_long` (claims positive). `service_result` is **calculated**: revenue - claims + reinsurance_net + pool_surplus. `pool_surplus` is 0 where none is printed. |
| service_result_printed | The insurance service result as printed in the segment note or statement, where the filing prints one (GIG's segment note prints none, so it is empty for GIG). |
| printed_vs_calc_diff | Absolute difference between printed and calculated service result. All 118 comparable rows are within 3. |
| loss_ratio | claims / revenue (gross of reinsurance). **This is an insurance-service-expense ratio**: IFRS 17 service expenses include incurred claims and other directly attributable expenses (for example acquisition-cost amortisation), so it is not a pure claims ratio. |
| net_service_ratio | (claims - reinsurance_net - pool_surplus) / revenue. Equals 1 - service_margin. |
| service_margin | service_result / revenue. |
| medical_share_of_revenue | Medical revenue / total revenue of the same insurer and period (medical rows only). |
| other_operating_expenses, expense_ratio_total, combined_ratio_total | **Total rows only.** No insurer allocates other operating expenses to segments, so there is no medical expense or combined ratio. Empty for Medgulf. |
| mono_line | True for Bupa. |
| is_derived | True where the row is Q4 = FY minus 9M (not a filed quarter). 2023Q4 (Bupa only), 2024Q4 and 2025Q4 where both FY and 9M exist. |
| freq, post_ifrs17 | `annual` / `quarter`; always true. |
| source_files, source_pages | `;`-separated files and PDF pages the row was built from. |

Coverage: Bupa 2023Q1 to 2025Q2 (+FY2023, FY2024); Tawuniya 2023Q3 to 2025Q3 (no FY, no Q4); the other five 2024Q1 to 2025Q4 plus FY2024 and FY2025.

## DuckDB: `insurers.duckdb`

Tables `statements_long`, `milliman_long`, `segment_long`, `panel_consolidated`, `panel_segment`, `milliman_medical_sector` (Milliman p.15, SAR **millions**). Views from `sql/`:

| View | Contents |
|---|---|
| `v_medical_ratios` | Medical ratios per insurer and period with whole-company expense and combined ratio beside them. |
| `v_medical_market_share` | Medical revenue share within the benchmark set (`n_insurers_in_period` says how many) and, for full years, share of Milliman's sector. |
| `v_medical_changes` | Quarter-on-quarter and year-on-year change in percentage points. A missing prior period gives NULL, never a skipped gap. |
| `v_medical_peer_rank` | Rank per period (1 = lowest loss ratio / highest margin) among the insurers present. |

## Power BI star schema: `reports/powerbi/`

`fact_insurer_period.csv` (insurer x period x segment; additive SAR thousands only, no ratios), `dim_insurer.csv`, `dim_period.csv` (integer `period_key`, for example `20253` = 2025 Q3, `20250` = FY2025). Column meanings and DAX: `reports/powerbi/MEASURES.md`.

## Known data limitations

* Bupa has no 2025Q3/Q4 or FY2025; Tawuniya has no full-year filings (so no Q4) and nothing before 2023Q3.
* Tawuniya's three-month claims columns sum 0.5% to 1% below its own reported nine-month figure in 2024 and 2025 (an inconsistency in the filings).
* Medgulf prints no "other operating expenses" line.
* GIG does not print a per-segment service result; it is calculated from the printed lines.
* A random 10% audit (seed 42) of 52 of 523 values found 0 errors (95% upper bound 6.9%); see `reports/audit_results.csv`.
