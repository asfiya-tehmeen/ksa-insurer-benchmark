# Power BI: model, DAX measures and one-page layout

Data are SAR thousands. Build the `.pbix` from the three CSVs in this folder (Get Data > Text/CSV, UTF-8).

## 1. Model

| Table | Grain | Key |
|---|---|---|
| `fact_insurer_period` | insurer x period x segment (`medical` / `total`) | `insurer_key`, `period_key`, `segment` |
| `dim_insurer` | one row per insurer (7) | `insurer_key` |
| `dim_period` | one row per period (15: FY and quarters 2023-2025) | `period_key` (integer, e.g. `20253` = 2025 Q3, `20250` = FY2025) |

Relationships (both many-to-one, single direction, dim -> fact):
`dim_insurer[insurer_key]` -> `fact_insurer_period[insurer_key]`, `dim_period[period_key]` -> `fact_insurer_period[period_key]`.

Set column types: `period_key`, `prior_year_key`, `prior_period_key` = Whole number. Sort `dim_period[period_label]` by `dim_period[period_key]`.
Hide `fact_insurer_period` columns after creating the base measures.

**Do not add ratio columns to the fact table or average them.** Every ratio below is a ratio of sums, so it stays correct
when you slice by several insurers or periods. Fact rows with `is_derived = TRUE` are Q4 = FY minus 9M (not printed in a filing).

## 2. Base measures

```dax
Revenue = SUM ( fact_insurer_period[revenue] )
Service Expenses = SUM ( fact_insurer_period[service_expenses] )
Net Reinsurance = SUM ( fact_insurer_period[reinsurance_net] )
Pool Surplus = SUM ( fact_insurer_period[pool_surplus] )
Service Result = SUM ( fact_insurer_period[service_result] )
Other Operating Expenses = SUM ( fact_insurer_period[other_operating_expenses] )
```

## 3. Ratio measures (medical segment is the primary view)

```dax
Medical Revenue =
CALCULATE ( [Revenue], fact_insurer_period[segment] = "medical" )

Medical Loss Ratio =
DIVIDE (
    CALCULATE ( [Service Expenses], fact_insurer_period[segment] = "medical" ),
    [Medical Revenue]
)

Medical Net Service Ratio =
DIVIDE (
    CALCULATE ( [Service Expenses] - [Net Reinsurance] - [Pool Surplus], fact_insurer_period[segment] = "medical" ),
    [Medical Revenue]
)

Medical Service Margin =
DIVIDE (
    CALCULATE ( [Service Result], fact_insurer_period[segment] = "medical" ),
    [Medical Revenue]
)

-- Whole company only: other operating expenses are not allocated to segments by any insurer.
-- Blank for Medgulf (no such line printed).
Total Combined Ratio =
VAR rev = CALCULATE ( [Revenue], fact_insurer_period[segment] = "total" )
VAR opex = CALCULATE ( [Other Operating Expenses], fact_insurer_period[segment] = "total" )
RETURN
    IF (
        ISBLANK ( opex ),
        BLANK (),
        DIVIDE ( CALCULATE ( [Service Expenses], fact_insurer_period[segment] = "total" ) + opex, rev )
    )

Total Loss Ratio =
DIVIDE (
    CALCULATE ( [Service Expenses], fact_insurer_period[segment] = "total" ),
    CALCULATE ( [Revenue], fact_insurer_period[segment] = "total" )
)

Medical Share of Revenue =
DIVIDE ( [Medical Revenue], CALCULATE ( [Revenue], fact_insurer_period[segment] = "total" ) )
```

`Medical Loss Ratio` = insurance service expenses / insurance revenue. That line contains claims *and* directly attributable
expenses (see `RATIO_DEFINITIONS.md`); label the visuals "Medical insurance service expense ratio (loss ratio)".

## 4. Change vs prior period and rank

```dax
Medical LR Prior Year =
VAR py = MAX ( dim_period[prior_year_key] )
RETURN
    CALCULATE ( [Medical Loss Ratio], REMOVEFILTERS ( dim_period ), dim_period[period_key] = py )

Medical LR YoY (pp) =
VAR cur = [Medical Loss Ratio]
VAR py = [Medical LR Prior Year]
RETURN IF ( ISBLANK ( cur ) || ISBLANK ( py ), BLANK (), ( cur - py ) * 100 )

Medical LR Prior Quarter =
VAR pq = MAX ( dim_period[prior_period_key] )
RETURN
    IF ( ISBLANK ( pq ), BLANK (),
        CALCULATE ( [Medical Loss Ratio], REMOVEFILTERS ( dim_period ), dim_period[period_key] = pq ) )

Medical LR QoQ (pp) =
VAR cur = [Medical Loss Ratio]
VAR pq = [Medical LR Prior Quarter]
RETURN IF ( ISBLANK ( cur ) || ISBLANK ( pq ), BLANK (), ( cur - pq ) * 100 )

Medical LR Rank =   -- 1 = lowest loss ratio among the insurers on the visual
IF (
    ISBLANK ( [Medical Loss Ratio] ),
    BLANK (),
    RANKX ( ALLSELECTED ( dim_insurer[insurer_name] ), [Medical Loss Ratio], , ASC, DENSE )
)

Peers In Period =
COUNTROWS ( FILTER ( ALLSELECTED ( dim_insurer[insurer_name] ), NOT ISBLANK ( [Medical Loss Ratio] ) ) )

-- For the TABLE only: ranks the insurers shown (slicer-aware).
Rank Label = IF ( ISBLANK ( [Medical LR Rank] ), BLANK (), [Medical LR Rank] & " of " & [Peers In Period] )

-- For the KPI CARD. Do not put Rank Label on a card: with several insurers in view the card holds the
-- POOLED ratio, which is not an insurer, so ranking it gives a meaningless "3 of 7".
-- This measure shows a rank only when exactly one insurer is selected, ranked among ALL insurers that
-- have a value in the selected period (ignores the insurer slicer, keeps the period filters).
Rank Label (card) =
VAR one = HASONEVALUE ( dim_insurer[insurer_name] )
VAR rk = RANKX ( ALL ( dim_insurer[insurer_name] ), [Medical Loss Ratio], , ASC, DENSE )
VAR n = COUNTROWS ( FILTER ( ALL ( dim_insurer[insurer_name] ), NOT ISBLANK ( [Medical Loss Ratio] ) ) )
RETURN IF ( one && NOT ISBLANK ( [Medical Loss Ratio] ), rk & " of " & n, "Select one insurer" )
-- Test in Desktop: period 2025 Q2, insurer = Bupa Arabia -> "3 of 7"; all insurers -> "Select one insurer".

Medical Revenue Share of Peers =
DIVIDE ( [Medical Revenue], CALCULATE ( [Medical Revenue], ALLSELECTED ( dim_insurer ) ) )

Derived Note =
IF (
    CALCULATE ( COUNTROWS ( fact_insurer_period ), fact_insurer_period[is_derived] = TRUE () ) > 0,
    "Q4 derived as FY minus 9M",
    BLANK ()
)
```

Prior-year and prior-quarter lookups return BLANK when the earlier period is absent (for example Tawuniya has no Q4).
That is intended: never fill gaps.

## 5. Layout: one page "Medical insurer benchmark" (16:9)

| Zone | Content |
|---|---|
| Title bar | "Saudi health insurers: medical-segment benchmark". Subtitle: "Source: company filings and Milliman KSA Industry Update 2025. SAR, gross of reinsurance unless stated." |
| Slicers (left rail) | `dim_period[freq]` (default `quarter`); `dim_period[period_label]` (single select, default `2025 Q3`); `dim_insurer[insurer_name]` (multi-select, all). |
| KPI cards (top row, 4 cards) | `Medical Loss Ratio`, `Medical Service Margin`, `Medical LR YoY (pp)`, `Rank Label (card)` for the current selection (it reads "Select one insurer" until one insurer is chosen). |
| Left, large | Clustered bar: `insurer_name` x `Medical Loss Ratio`, sorted ascending, data labels on, constant line at 100%. Tooltip: `Medical Revenue`, `Medical Net Service Ratio`, `Medical Share of Revenue`. |
| Right, large | Line chart: x = `period_label` (sorted by `period_key`, freq = quarter, ignore the period slicer with *Edit interactions*), y = `Medical Loss Ratio`, legend = `insurer_name`. Add the 100% line. |
| Bottom left | Table: `insurer_name`, `Medical Revenue`, `Medical Revenue Share of Peers`, `Medical Loss Ratio`, `Medical Service Margin`, `Medical LR YoY (pp)`, `Medical LR QoQ (pp)`, `Rank Label`. Conditional format loss ratio (diverging around 100%). |
| Bottom right | Column chart: `insurer_name` x `Medical Share of Revenue` with title "Medical share of each insurer's revenue". It shows why whole-company ratios are not a health benchmark: only Bupa is 100%. |
| Footer text box | "Small sample: 7 insurers, 8 quarterly points at most. Q4 values are FY minus 9M. Gross of reinsurance: heavy reinsurers look better on net measures. Associated-with language only; no causal claims; filings contain no claim-denial data." |

Colour: one neutral for peers, one accent for the selected insurer; do not use red/green alone (colour-blind safe), use the 100% line for meaning.
