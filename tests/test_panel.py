from pathlib import Path

import pandas as pd
import pytest

from src.clean import build_panel, map_label, standardise

LONG, MILL = Path("data/clean/statements_long.csv"), Path("data/clean/milliman_long.csv")
pytestmark = pytest.mark.skipif(not LONG.exists(), reason="run src.income_statement first")


@pytest.fixture(scope="module")
def long_df():
    return pd.read_csv(LONG)


def _val(df, insurer, period, item, scope="period", basis="current"):
    d = df[(df.insurer == insurer) & (df.period == period) & (df.scope == scope) & (df.basis == basis)]
    d = d[d.raw_label.map(map_label) == item]
    assert len(d) == 1, (insurer, period, item, len(d))
    return d.value.iloc[0]


def test_service_result_waterfall_every_filing(long_df):
    """revenue + service expenses + net reinsurance = reported subtotal, per filing column.
    Subtotal = 'directly written business' result (GIG) if printed, else service result
    less insurance-pool surplus (GIG, Medgulf)."""
    bad = []
    for (ins, per, src, basis, scope), g in long_df.groupby(
            ["insurer", "period", "source_file", "basis", "scope"]):
        items = {}
        for l, v in zip(g.raw_label, g.value):
            k = map_label(l)
            if k and k not in items:
                items[k] = v
        if {"revenue", "claims_incurred", "reinsurance_net"} <= items.keys() and (
                "direct_service_result" in items or "service_result" in items):
            calc = items["revenue"] + items["claims_incurred"] + items["reinsurance_net"]
            target = items.get("direct_service_result",
                               items.get("service_result", 0) - items.get("pool_surplus", 0))
            if abs(calc - target) > 2:  # rounding, SAR thousands
                bad.append((ins, per, src, scope, calc, target))
    assert not bad, bad


@pytest.mark.parametrize("insurer,q", [("tawuniya", ["2024Q1", "2024Q2", "2024Q3"]),
                                       ("bupa", ["2024Q1", "2024Q2", "2024Q3"])])
def test_quarters_sum_to_nine_months(long_df, insurer, q):
    nine_month = _val(long_df, insurer, "2024Q3", "revenue", scope="ytd")
    total = 0
    for p in q:
        d = long_df[(long_df.insurer == insurer) & (long_df.period == p) & (long_df.scope == "period")]
        d = d[d.raw_label.map(map_label) == "revenue"].sort_values("basis")  # 'comparative' < 'current'
        total += d.value.iloc[-1]
    assert total == pytest.approx(nine_month, abs=2)


@pytest.mark.skipif(not MILL.exists(), reason="run src.milliman first")
def test_bupa_fy2024_matches_milliman(long_df):
    m = pd.read_csv(MILL)
    mv = lambda item: m[(m.insurer == "Bupa") & (m.period == "2024FY") & (m.item == item)].value.iloc[0]
    assert _val(long_df, "bupa", "2024FY", "revenue") == mv("insurance_revenue")
    assert _val(long_df, "bupa", "2024FY", "net_income") == mv("net_income")


def test_panel_ratios_are_sane(long_df):
    std, _ = standardise(long_df)
    p = build_panel(std)
    assert p[["loss_ratio", "service_margin"]].notna().all().all()
    assert p.loss_ratio.between(0.5, 1.2).all()
    assert not p.duplicated(["insurer", "period"]).any()


# ---- multi-insurer checks (added after OCR extraction of scanned statements) ----
MILLIMAN_NAME = {"alrajhitakaful": "AlRajhi Takaful", "bupa": "Bupa", "gig": "GIG",
                 "malath": "MALATH", "medgulf": "Medgulf", "walaa": "Walaa", "tawuniya": "Tawuniya"}


@pytest.fixture(scope="module")
def panel(long_df):
    std, _ = standardise(long_df)
    return build_panel(std)


def test_every_panel_row_passes_waterfall(panel):
    """revenue - service expenses + net reinsurance (+ pool surplus) = reported subtotal.
    Guards against OCR misreads in revenue / claims / reinsurance cells."""
    assert panel.waterfall_ok.notna().all(), panel[panel.waterfall_ok.isna()][["insurer", "period"]]
    assert panel.waterfall_ok.all(), panel[~panel.waterfall_ok.astype(bool)][["insurer", "period", "waterfall_diff"]]


@pytest.mark.skipif(not MILL.exists(), reason="run src.milliman first")
def test_full_year_revenue_and_net_income_match_milliman(panel):
    m = pd.read_csv(MILL)
    checked = 0
    for _, r in panel[panel.freq == "annual"].iterrows():
        for item, col in (("insurance_revenue", "revenue"), ("net_income", "net_income")):
            mv = m[(m.insurer == MILLIMAN_NAME[r.insurer]) & (m.period == r.period) & (m.item == item)].value
            if len(mv) and pd.notna(r[col]):
                assert r[col] == mv.iloc[0], (r.insurer, r.period, col, r[col], mv.iloc[0])
                checked += 1
    assert checked >= 20


def test_panel_covers_seven_insurers(panel):
    assert set(panel.insurer) == set(MILLIMAN_NAME)


def test_quarters_sum_to_nine_months_all_insurers(long_df):
    """Q1+Q2+Q3 (3-month columns) must equal the reported 9M column.
    Revenue: exact for every insurer. Claims: exact except Tawuniya, whose 3-month
    columns sum 0.5-1% BELOW its 9M column in both 2024 and 2025 (verified against the
    text layer: the filings themselves are inconsistent, i.e. YTD true-ups). Do not
    derive Tawuniya quarterly claims from YTD differences without flagging this."""
    from src.clean import resolve_overlaps
    std, _ = standardise(long_df)
    q = resolve_overlaps(std)
    ytd = std[(std.scope == "ytd") & (std.basis == "current") & std.period.str.endswith("Q3")]
    ytd = ytd.drop_duplicates(["insurer", "period", "item"])
    checked = 0
    for yr in ("2024", "2025"):
        for ins in sorted(long_df.insurer.unique()):
            for item in ("revenue", "claims_incurred"):
                y = ytd[(ytd.insurer == ins) & (ytd.period == f"{yr}Q3") & (ytd.item == item)].value_sar_k
                qs = [q[(q.insurer == ins) & (q.period == f"{yr}Q{k}") & (q.item == item)].value_sar_k
                      for k in (1, 2, 3)]
                if not len(y) or not all(len(x) for x in qs):
                    continue
                diff = sum(x.iloc[0] for x in qs) - y.iloc[0]
                if ins == "tawuniya" and item == "claims_incurred":
                    assert -0.015 * y.iloc[0] < diff < 0, (yr, diff)   # known, documented gap
                else:
                    assert abs(diff) <= 2, (ins, yr, item, diff)
                checked += 1
    assert checked >= 14
