# KSA Health Insurer Benchmark

A medical-segment benchmark of seven Saudi health insurers built from their published financial statements: PDF extraction (including OCR for scanned pages), reconciliation, SQL views and a Power BI dashboard.

![Power BI dashboard](reports/powerbi/dashboard/desktop-verification.jpg)

## Question

How do Saudi health insurers differ in **medical-segment** loss ratio and service margin, what is associated with the differences, and is the sector trend changing?

Only Bupa Arabia is a medical-only insurer. The other six (Tawuniya, Al Rajhi Takaful, GIG, Malath, Medgulf, Walaa) also write motor, property and other cover, so their whole-company ratios are not a health benchmark. The panel is therefore built at **insurer x period x segment** (`medical`, `total`) from each filing's operating-segment note.

## Approach

1. **Extract.** `src/income_statement.py` and `src/segments.py` read the statement of income and the operating-segment note from 30 interim and annual filings (2024 to 2025, with comparatives back to 2023). Scanned pages are read with OCR (`src/ocr.py`, RapidOCR, cached).
2. **Build the panel.** `src/panel.py` produces the medical and total panel. Q4 is derived as FY minus nine months and flagged `is_derived`.
3. **Define ratios consistently under IFRS 17.** Loss ratio = insurance service expenses / insurance revenue. This includes directly attributable expenses, so it is not a pure claims ratio. Definitions per insurer are in [`reports/RATIO_DEFINITIONS.md`](reports/RATIO_DEFINITIONS.md).
4. **Reconcile and audit.** Segment columns sum to the printed totals, segment totals equal the consolidated statements, and full-year figures are cross-checked against Milliman's KSA industry data. A random 10% of extracted values was checked against the PDFs.
5. **SQL layer.** `src/build_db.py` loads everything into DuckDB, and `sql/` defines views for medical ratios, market share, period-on-period change and peer rank.
6. **Analysis.** Peer comparison with confidence intervals, trends and rolling volatility (`src/analysis.py`).
7. **Power BI.** `src/export_powerbi.py` writes a star schema. The one-page dashboard's DAX results match the SQL views for all seven insurers.

## Results

Pooled 2024Q1 to 2025Q2, printed quarters only, gross of reinsurance:

| Insurer | Medical share of revenue | Medical loss ratio | 95% CI of quarterly mean (n=5) | Medical service margin | Whole-company loss ratio |
|---|---|---|---|---|---|
| Tawuniya | 72% | 91.5% | 86.4 to 96.7 | +7.7% | 83.5% |
| Bupa Arabia | 100% | 92.4% | 90.5 to 94.4 | +7.2% | 92.4% |
| Malath | 49% | 97.0% | 85.7 to 109.3 | +2.7% | 98.4% |
| Medgulf | 80% | 98.5% | 94.3 to 102.9 | +0.6% | 90.0% |
| GIG (Saudi) | 28% | 108.0% | 98.4 to 117.6 | -7.4% | 80.9% |
| Al Rajhi Takaful | 27% | 112.8% | 100.6 to 125.1 | -12.8% | 84.0% |
| Walaa | 18% | 119.4% | 104.7 to 135.6 | -19.3% | 58.4% |

Sector medical loss ratio (Milliman, about 21 companies): 96.6% (2022), 95.2% (2023), 96.2% (2024), 95.6% (2025).

**Medical-segment ratios re-rank the insurers.** Walaa's whole-company loss ratio (58%) looks like the best in the group, but its medical book runs at 119%. The multi-line insurers with a small medical share have the weakest medical results.

The full write-up is in [`reports/REPORT.md`](reports/REPORT.md).

## Data quality

- **Random audit** (seed 42): 52 of 523 extracted values checked against the PDFs, **0 errors** (95% upper bound on the error rate 6.9%). Detail in `reports/audit_results.csv`.
- **Reconciliations** (in `tests/`): revenue minus service expenses plus net reinsurance equals the printed subtotal on every filing; segments sum to totals; segment totals equal the consolidated statements (57 periods); all 24 full-year revenue and net-income values equal Milliman's.
- **Milliman cross-check** (`reports/milliman_crosscheck.csv`): in FY2024 the six insurers with full-year filings covered 59.5% of sector medical revenue; their combined medical loss ratio of 97.0% compares with 96.2% for the sector.

## Limitations

- Few insurers and periods, so statistical power is low. Intervals use n = 5 quarters and ignore autocorrelation.
- All periods are under IFRS 17 (2023 onward), so the IFRS 4 to IFRS 17 transition is not observed.
- Ratios are gross of reinsurance. Medical expense and combined ratios cannot be built, because no insurer allocates other operating expenses to segments.
- Gaps: no Bupa 2025Q3 to FY2025; no Tawuniya full-year filings (so no Tawuniya Q4); Medgulf prints no other operating expenses line. Tawuniya's three-month claims columns sum 0.5% to 1% below its nine-month figure.
- No loss-ratio forecast was run. The rule required at least 8 quarterly points per insurer, and Tawuniya has 7.
- Financial statements do not show claim denials or provider-level data. Differences are described as "associated with", not caused by.
- **UAE insurers were screened but not added.** Dubai Insurance reports "Life and Medical" as one segment, Sukoon reports "general insurance including medical", and AMAN reports investments vs underwriting. None publishes a medical-only segment (evidence in `reports/uae_screen.csv`).

## Power BI dashboard

Open `reports/powerbi/ksa_insurer_benchmark.pbix`, or the Power BI Project `reports/powerbi/dashboard/ksa_insurer_benchmark.pbip`. If the CSVs move, change the `DataFolder` parameter (Transform data > Edit parameters) and refresh.

- Model and DAX: [`reports/powerbi/MEASURES.md`](reports/powerbi/MEASURES.md)
- Verification against SQL: [`reports/powerbi/dashboard/ACCEPTANCE.md`](reports/powerbi/dashboard/ACCEPTANCE.md) and [`REVIEW_FIXES.md`](reports/powerbi/dashboard/REVIEW_FIXES.md)

## Project structure

```
data/raw/        filings as PDFs (not in the repository; see Data)
data/interim/    cached OCR text
data/clean/      statements_long, segment_long, panel_segment, milliman_long, DATA_DICTIONARY.md
notebooks/       01_walkthrough.ipynb (reads the clean data; needs no PDFs)
src/             income_statement, segments, panel, clean, ratios, ocr, milliman, crosscheck,
                 analysis, audit, build_db, export_powerbi, figures, definitions
sql/             01_medical_ratios, 02_market_share, 03_changes, 04_peer_rank (DuckDB views)
tests/           parsing, reconciliations, panel definitions, SQL vs pandas
reports/         REPORT.md, RATIO_DEFINITIONS.md, sources.csv, cross-checks, audit, tables/, figures/, powerbi/
run_all.ps1      one-command rebuild and tests
```

## Run it

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\run_all.ps1          # rebuilds every output from data\raw and runs the tests
```

On macOS or Linux, run the modules listed in `run_all.ps1` in order with `python -m`, then `pytest`. The first run reads scanned pages with OCR (about a minute per page); later runs use the cache. To explore the results without the PDFs, open `notebooks/01_walkthrough.ipynb`.

## Data

The filings are public but are not redistributed here. Download them from the Saudi Exchange (Tadawul) and the insurers' investor-relations pages, and save them in `data/raw/` as `insurer_PERIOD.pdf` (for example `malath_2025Q2.pdf`, `walaa_2025FY.pdf`). [`reports/sources.csv`](reports/sources.csv) lists every file, its URL where available, and the pages used. Every value in the clean data traces back to a file and page. The Milliman KSA Industry Update 2025 is used only as a cross-check.

## Tech

Python, pandas, pdfplumber, RapidOCR, DuckDB (SQL), SciPy, matplotlib, pytest, Power BI (DAX).
