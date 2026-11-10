"""Peer comparison, trends, rolling volatility and forecast eligibility (scope cut per README).

Run:  python -m src.analysis        -> reports/tables/*.csv  (+ prints the numbers used in REPORT.md)

Choices (small sample, so deliberately simple):
* Peer comparison uses PRINTED quarters only (derived Q4 = FY - 9M excluded) in a window common to all 7 insurers:
  2024Q1, 2024Q2, 2024Q3, 2025Q1, 2025Q2  (n = 5 quarters). CI = t-interval on the mean of quarterly ratios;
  it ignores autocorrelation, so treat it as indicative.
* 'pooled' = ratio of sums over the window (weights quarters by revenue).
* Rolling volatility = std of the medical loss ratio over 4 consecutive quarters (needs 4 contiguous quarters).
* A forecast is attempted only if EVERY insurer has >= 8 contiguous quarterly points (README rule).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

OUT = Path("reports/tables")
WINDOW = ["2024Q1", "2024Q2", "2024Q3", "2025Q1", "2025Q2"]
NAME = {"alrajhitakaful": "Al Rajhi Takaful", "bupa": "Bupa Arabia", "gig": "GIG (Saudi)", "malath": "Malath",
        "medgulf": "Medgulf", "tawuniya": "Tawuniya", "walaa": "Walaa"}


def qidx(p: str) -> int:
    return int(p[:4]) * 4 + int(p[5]) - 1


def load() -> pd.DataFrame:
    w = pd.read_csv("data/clean/panel_segment.csv")
    return w[w.freq == "quarter"].copy()


def coverage(q: pd.DataFrame) -> pd.DataFrame:
    m = q[q.segment == "medical"].copy()
    rows = []
    for ins, g in m.groupby("insurer"):
        idx = sorted(qidx(p) for p in g.period)
        runs, cur = [], 1
        for a, b in zip(idx, idx[1:]):
            cur = cur + 1 if b == a + 1 else (runs.append(cur) or 1)
        runs.append(cur)
        rows.append(dict(insurer=NAME[ins], quarters=len(idx), derived_q4=int(g.is_derived.sum()),
                         first=g.period.min(), last=g.period.max(), longest_contiguous_run=max(runs),
                         meets_8_contiguous=max(runs) >= 8))
    return pd.DataFrame(rows).sort_values("insurer")


def peer_table(q: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ins in NAME:
        seg = {}
        for s in ("medical", "total"):
            g = q[(q.insurer == ins) & (q.segment == s) & (q.period.isin(WINDOW)) & (~q.is_derived)]
            assert len(g) == len(WINDOW), (ins, s, len(g))
            seg[s] = g
        m = seg["medical"]
        x = m.loss_ratio.values
        ci = stats.t.interval(0.95, len(x) - 1, loc=x.mean(), scale=stats.sem(x))
        t = seg["total"]
        rows.append(dict(
            insurer=NAME[ins], key=ins,
            medical_share_of_revenue=m.revenue.sum() / t.revenue.sum(),
            medical_loss_ratio_pooled=m.claims.sum() / m.revenue.sum(),
            medical_lr_mean=x.mean(), medical_lr_ci_low=ci[0], medical_lr_ci_high=ci[1],
            medical_lr_min=x.min(), medical_lr_max=x.max(),
            medical_net_service_ratio_pooled=(m.claims.sum() - m.reinsurance_net.sum() - m.pool_surplus.sum()) / m.revenue.sum(),
            medical_service_margin_pooled=m.service_result.sum() / m.revenue.sum(),
            total_loss_ratio_pooled=t.claims.sum() / t.revenue.sum(),
            total_service_margin_pooled=t.service_result.sum() / t.revenue.sum(),
        ))
    d = pd.DataFrame(rows)
    d["medical_minus_total_loss_ratio_pp"] = 100 * (d.medical_loss_ratio_pooled - d.total_loss_ratio_pooled)
    d["rank_medical_lr"] = d.medical_loss_ratio_pooled.rank(method="min").astype(int)
    d["rank_total_lr"] = d.total_loss_ratio_pooled.rank(method="min").astype(int)
    d["ci_overlaps_100pct"] = (d.medical_lr_ci_low <= 1) & (d.medical_lr_ci_high >= 1)
    return d.sort_values("medical_loss_ratio_pooled")


def rolling_vol(q: pd.DataFrame) -> pd.DataFrame:
    m = q[q.segment == "medical"].copy()
    m["i"] = m.period.map(qidx)
    rows = []
    for ins, g in m.groupby("insurer"):
        s = g.set_index("i").loss_ratio.sort_index()
        full = s.reindex(range(s.index.min(), s.index.max() + 1))
        vol = full.rolling(4).std()          # NaN across gaps
        vol = vol.dropna()
        rows.append(dict(insurer=NAME[ins], windows=len(vol), latest_4q_std_pp=100 * vol.iloc[-1] if len(vol) else np.nan,
                         mean_4q_std_pp=100 * vol.mean() if len(vol) else np.nan,
                         max_4q_std_pp=100 * vol.max() if len(vol) else np.nan))
    return pd.DataFrame(rows).sort_values("insurer")


def fixed_group_trend(q: pd.DataFrame) -> pd.DataFrame:
    """Ratio-of-sums medical loss ratio for the 5 insurers that have all 8 quarters 2024Q1-2025Q4 (constant composition)."""
    grp = ["alrajhitakaful", "gig", "malath", "medgulf", "walaa"]
    per = [f"{y}Q{k}" for y in (2024, 2025) for k in (1, 2, 3, 4)]
    m = q[(q.segment == "medical") & q.insurer.isin(grp) & q.period.isin(per)]
    assert m.groupby("insurer").period.nunique().eq(8).all()
    g = m.groupby("period").agg(revenue=("revenue", "sum"), claims=("claims", "sum"),
                                reins=("reinsurance_net", "sum"), pool=("pool_surplus", "sum"),
                                svc=("service_result", "sum"), has_derived=("is_derived", "any")).reset_index()
    g["loss_ratio"] = g.claims / g.revenue
    g["service_margin"] = g.svc / g.revenue
    return g


def yoy_same_quarter(q: pd.DataFrame) -> pd.DataFrame:
    m = q[(q.segment == "medical") & (~q.is_derived)].pivot_table(index="insurer", columns="period", values="loss_ratio")
    rows = []
    for ins in m.index:
        d = {}
        for qn in ("Q1", "Q2", "Q3"):
            a, b = m.loc[ins].get(f"2025{qn}"), m.loc[ins].get(f"2024{qn}")
            d[f"{qn}_yoy_pp"] = None if pd.isna(a) or pd.isna(b) else 100 * (a - b)
        rows.append(dict(insurer=NAME[ins], **d))
    return pd.DataFrame(rows).sort_values("insurer")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    q = load()
    cov, peer, vol, trend, yoy = coverage(q), peer_table(q), rolling_vol(q), fixed_group_trend(q), yoy_same_quarter(q)
    for n, d in [("coverage", cov), ("peer_comparison", peer), ("rolling_volatility", vol),
                 ("fixed_group_trend", trend), ("yoy_same_quarter", yoy)]:
        d.to_csv(OUT / f"{n}.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print("== coverage\n", cov.to_string(index=False))
    forecast_ok = bool(cov.meets_8_contiguous.all())
    print("\nforecast allowed (every insurer >= 8 contiguous quarters):", forecast_ok)
    print("\n== peer comparison (window", WINDOW, ")\n", peer.round(4).T.to_string())
    print("\n== rolling 4q volatility (pp)\n", vol.round(2).to_string(index=False))
    print("\n== fixed 5-insurer group, medical\n", trend.round(4).to_string(index=False))
    print("\n== yoy same quarter (pp)\n", yoy.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
