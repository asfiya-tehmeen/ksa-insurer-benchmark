from pathlib import Path

import pandas as pd
import pytest

CSV = Path("data/clean/milliman_long.csv")
pytestmark = pytest.mark.skipif(not CSV.exists(), reason="run src.milliman first")

# 'Totals' row printed under Exhibit 1 (PDF page 23)
PRINTED_REVENUE_TOTALS = {"2025FY": 71_234_546, "2024FY": 64_668_226,
                          "2023FY": 55_974_699, "2022FY": 44_506_282}


def test_complete_grid():
    d = pd.read_csv(CSV)
    assert d.insurer.nunique() == 24
    assert d.groupby("item").size().eq(96).all()


@pytest.mark.parametrize("period,total", PRINTED_REVENUE_TOTALS.items())
def test_revenue_sums_to_printed_total(period, total):
    d = pd.read_csv(CSV)
    got = d[(d.item == "insurance_revenue") & (d.period == period)].value.sum()
    # 2022/23/25 match exactly; 2024 components sum 2 (SAR k) below the printed total
    # (all 24 rows parsed) -> treated as source rounding. Tolerance: 5 SAR thousand.
    assert got == pytest.approx(total, abs=5)


def test_tawuniya_net_income_matches_annual_report():
    d = pd.read_csv(CSV)
    v = d[(d.insurer == "Tawuniya") & (d.item == "net_income") & (d.period == "2024FY")].value.iloc[0]
    assert v == 1_022_025  # annual report p.41: ~SAR 1,022m
