I'm a Dubai-based data analyst job seeker targeting medical insurance, payer analytics and healthcare finance roles in the UAE and KSA (employers like Dubai Insurance, Daman, Bupa Arabia, Tawuniya, GIG, NAS, Nextcare). This project benchmarks health insurers from public financial filings. It's partway done: PDFs for 8 insurers are in `data/raw/`, extraction code is in `src/`, and `data/clean/panel.csv` currently has only Bupa and Tawuniya (15 rows).

Read `README.md`, `reports/sources.csv`, everything in `src/` and `tests/`, and the clean CSVs before changing anything.

## The problem to fix first
The panel uses **whole-company** figures. Bupa Arabia sells only health insurance, but most of the others (Tawuniya, Al Rajhi Takaful, GIG, Malath, MedGulf, Walaa) are multi-line: they also sell motor, property and other cover. So comparing their total loss ratios against Bupa's is not a health-insurance comparison. **Verify this for each insurer from its own filing; don't assume it.**

## Task
1. **Extract medical-segment figures.** In each filing, find the operating segment note and pull the **medical / health segment** insurance revenue, insurance service expense (claims incurred), reinsurance result and insurance service result. Record the source page per value in `reports/sources.csv`. Where a filing has no usable segment split, mark the insurer as whole-company only and say so. Don't estimate.
2. **Redefine the panel** as insurer x period x segment (`medical` and `total`). Compute the ratios on the medical segment as the primary view. Keep the totals for reference.
3. **Check ratio definitions under IFRS 17.** "Insurance service expenses" can include attributable expenses as well as claims. Document exactly which line goes into the numerator of the loss ratio and the expense ratio for each insurer, and make the definition consistent across insurers. Bupa's expense ratio is about 2%, which looks low, so check what it is really measuring.
4. **Add every insurer already downloaded**, not just two. Use OCR (`src/ocr.py`) only where there is no text layer. Double-check a random 10% of extracted values against the PDF and record the error rate in the README.
5. **Cross-check** the medical-segment ratios against the Milliman figures in `data/clean/milliman_long.csv` where they overlap, and log the differences with an explanation.
6. **Add SQL.** Load the long tables and panel into DuckDB (`data/clean/insurers.duckdb`) and write `sql/` views: medical loss ratio, combined ratio and service margin per insurer and period; market share of medical revenue; quarter-on-quarter and year-on-year change; peer rank per period.
7. **Prepare a Power BI page** (I'll build the .pbix myself). Export a small star schema to `reports/powerbi/`: `fact_insurer_period.csv`, `dim_insurer.csv`, `dim_period.csv`. Add `reports/powerbi/MEASURES.md` with the DAX measures (loss ratio, combined ratio, YoY change, rank) and a short layout spec for one benchmark page.
8. **Cut the scope.** With fewer than 10 insurers and a few years of data, drop the panel regression with fixed effects, the Chow / structural-break test and the hierarchical clustering. Keep: peer comparison, trends, rolling volatility, and a simple next-period loss-ratio forecast (last value vs seasonal naive vs ETS, rolling-origin backtest, MAE) **only if** there are at least 8 quarterly points per insurer. Otherwise say so and skip it.
9. **Write `reports/REPORT.md`** (1 to 2 pages, findings first): the sector medical loss ratio trend, 3 insurer comparisons, what the segment split changed compared with whole-company figures, and limitations. Use "associated with", not causal language, and make no claims about claim denials.
10. Update the README status, results table and resume line template with real numbers only.

## Stretch (only after the above is done)
Add UAE-listed insurers that publish segment data, starting with **Dubai Insurance**, so the benchmark covers the UAE as well as KSA. Check that their filings are publicly downloadable first.

## Rules
- Every number must trace to a source page. Never report a number you haven't run.
- Target about 3 days of work. Stop and ask me before adding anything that isn't listed.
- At the end, run `pytest`, show the results, and list anything you couldn't extract.
