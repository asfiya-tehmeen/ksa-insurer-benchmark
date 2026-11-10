# Review fixes and verification

Verified using the live model in Power BI Desktop on 10 November 2026. Raw results: `review-dax-results.json`. The existing 22 measures and source CSVs were not changed.

## Changes

- Added `Rank Label (card)` in `04 Change and rank`; changed the card binding and title to `Rank among peers`. The table continues to use `Rank Label`.
- Corrected the supplied new-measure fallback: multiple insurers return `Select one insurer`; exactly one insurer with no data returns BLANK. Ranking excludes blank peers and ranks across all insurer names while preserving period and derived filters.
- Bar labels: Outside end, 10 pt, #0b0b0b, 0–160% axis, opaque surface background to separate labels from the reference. The 100% reference is dashed #52514e behind the marks with its label disabled. Desktop uses its native reference-line thickness; unsupported explicit width overrides were discarded on saving.
- Trend: seven series retained; Bupa #2a78d6, Tawuniya #eb6834, Medgulf #1baf7a; Al Rajhi #30302e, GIG #50504c, Malath #6d6c66, Walaa #8a8983, with different dash-style settings for the four neutral series. Lines 2 px; markers 8 px. The 100% reference and legend remain.
- Replaced `desktop-verification.jpg` with a crop containing only the report canvas, excluding all app chrome and user details.

## New card tests — all PASS

| Selection | Actual |
|---|---|
| 2025 Q2, all insurers | Select one insurer |
| 2025 Q2, Bupa Arabia | 3 of 7 |
| 2025 Q2, Malath | 1 of 7 |
| 2025 Q2, Walaa | 7 of 7 |
| FY2024, Tawuniya | BLANK |
| 2025 Q2, Bupa, derived excluded | 3 of 7 |
| 2025 Q2, Bupa, derived included | 3 of 7 |

These cases were queried through MCP against the live Desktop model; the all-insurer card was also inspected on the report canvas.

## Existing acceptance checks rerun

| Check | Result and actual |
|---|---|
| Integrity | PASS: 138 facts, 7 insurers, 15 periods; 0 orphan insurer keys, 0 orphan period keys, 0 blank dimension members. |
| Q2 2025 medical LR | PASS: Tawuniya 88.5543%, Bupa 95.0990%, Malath 84.8106%, Medgulf 96.0900%, GIG 107.6945%, Al Rajhi 100.9557%, Walaa 138.5219%. |
| FY2024 medical LR | PASS: Bupa 94.0996%, Medgulf 99.5623%, Malath 100.1432%, Walaa 110.8854%, GIG 109.1104%, Al Rajhi 117.7902%; Tawuniya BLANK. |
| Combined ratios | PASS: Bupa FY2024 96.0257%; Medgulf nonblank combined-ratio periods = 0. |
| Peer shares | PASS: 100% in all 15 periods within floating-point precision. |
| Medical share | PASS at original rounding: Bupa 100%; non-Bupa 9.6702%–83.0256%. The maximum is slightly above a strict 83.0000%, as already disclosed. |
| Tawuniya Q1 2025 QoQ | PASS: BLANK. |
| Pooled KPI | PASS: Q2 93.2999501%, versus unweighted average 101.6751601%; Bupa + Tawuniya pooled 92.1648630%. |
| Layout | PASS: 1280×720 page inspected in Desktop; rank text, bar labels, chart legend and table fit. |

## Verification limit

Tooltip hover is NOT VERIFIED. The available Desktop API has no hover/move action. The existing report-page tooltip binding and its three cards remain; no hover verification is claimed.

The settings for dashDot and longDash were retained by Desktop; exact rendering of those two patterns was not independently measured. Explicit 1 px reference-line thickness is not supported by the native saved object; the native dashed reference line is retained.

## Save and cleanup
PBIP saved in Desktop. Canonical PBIX re-saved successfully (82,641 bytes, 10 November 2026 23:30 Asia/Dubai). Only after that successful save, reports\powerbi\dashboard.pbix (81,007 bytes) was deleted. No other file was deleted. Final inventory: FILES.txt.
