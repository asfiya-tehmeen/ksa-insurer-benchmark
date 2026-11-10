"""Cross-check medical-segment figures against Milliman's KSA Industry Update 2025.

Milliman prints a SECTOR medical table (p.15 of the PDF; SAR millions, ~21 companies) and
company-level medical figures only as charts (no table). So we can compare
  (1) our insurers' medical subtotal to the sector table, with coverage shown;
  (2) the ranking by 2025 medical revenue to the order of the company labels in the chart.
Milliman values below are transcribed from that table (page 15) and re-checked by the test.
"""
from __future__ import annotations

import pandas as pd

# Milliman p.15 (SAR millions). service result = revenue + ISE + net reinsurance (their line 4).
MILLIMAN_MEDICAL = pd.DataFrame({
    "period":  ["2025FY", "2024FY", "2023FY", "2022FY"],
    "revenue": [44648, 40357, 35620, 28328],
    "claims":  [42662, 38808, 33904, 27359],
    "reinsurance_net": [-204, -176, -78, -196],
    "service_result":  [1782, 1374, 1637, 774],
}).assign(source_page=15)
# order of company labels in Milliman's 'Top 10 by Medical Insurance Revenue' chart (2025), p.15
MILLIMAN_RANK_2025 = ["Bupa", "Tawuniya", "Medgulf", "AlRajhi Takaful", "Arabian Shield", "MALATH",
                      "Gulf Union", "Walaa", "AICC", "GIG"]
NAME = {"bupa": "Bupa", "tawuniya": "Tawuniya", "medgulf": "Medgulf", "alrajhitakaful": "AlRajhi Takaful",
        "malath": "MALATH", "walaa": "Walaa", "gig": "GIG"}


def sector_comparison(panel: pd.DataFrame) -> pd.DataFrame:
    m = panel[(panel.segment == "medical") & (panel.freq == "annual")]
    rows = []
    for _, mil in MILLIMAN_MEDICAL.iterrows():
        g = m[m.period == mil.period]
        if g.empty:
            continue
        ours = g[["revenue", "claims", "reinsurance_net", "service_result"]].sum() / 1000  # SAR m
        rows.append(dict(
            period=mil.period, our_insurers=", ".join(NAME[i] for i in sorted(g.insurer)),
            n_insurers=len(g), our_revenue=round(ours.revenue), milliman_revenue=mil.revenue,
            coverage_of_sector_revenue=round(ours.revenue / mil.revenue, 3),
            our_loss_ratio=round(ours.claims / ours.revenue, 4),
            milliman_loss_ratio=round(mil.claims / mil.revenue, 4),
            our_service_margin=round(ours.service_result / ours.revenue, 4),
            milliman_service_margin=round(mil.service_result / mil.revenue, 4),
            implied_rest_of_sector_loss_ratio=round((mil.claims - ours.claims) / (mil.revenue - ours.revenue), 4),
        ))
    return pd.DataFrame(rows)


def rank_check(panel: pd.DataFrame) -> pd.DataFrame:
    """Rank our insurers by 2025 medical revenue (FY where available, else 9M YTD) and compare to Milliman order."""
    res = pd.read_csv("data/clean/segment_long.csv")
    fy = res[(res.segment == "medical") & (res.item == "revenue") & (res.scope == "period") & (res.period == "2025FY")]
    ytd = res[(res.segment == "medical") & (res.item == "revenue") & (res.scope == "ytd") & res.period.str.startswith("2025")]
    v = {r.insurer: r.value for _, r in fy.iterrows()}
    # no FY2025 filing (Tawuniya, Bupa): annualise latest 2025 YTD (3 quarters -> x12/9, 2 -> x12/6); ranking only
    for ins, g in ytd.groupby("insurer"):
        if ins not in v:
            last = g.sort_values("period").iloc[-1]
            v[ins] = last.value * 12 / (3 * int(last.period[-1]))
    ours = sorted(v, key=v.get, reverse=True)
    mil = [n for n in MILLIMAN_RANK_2025 if n in {NAME[i] for i in v}]
    return pd.DataFrame({"our_rank": range(1, len(ours) + 1), "insurer": [NAME[i] for i in ours],
                         "milliman_chart_rank_among_these": [mil.index(NAME[i]) + 1 if NAME[i] in mil else None for i in ours]})


if __name__ == "__main__":
    panel = pd.read_csv("data/clean/panel_segment.csv")
    sc = sector_comparison(panel)
    sc.to_csv("reports/milliman_crosscheck.csv", index=False)
    print(sc.T.to_string())
    print(rank_check(panel).to_string(index=False))
