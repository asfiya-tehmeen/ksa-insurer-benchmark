"""Segment (medical vs total) extraction and panel checks."""
from pathlib import Path

import pandas as pd
import pytest

from src.segments import Layout, solve_row

SEG, PANEL, LONG = (Path("data/clean/segments_raw.csv"), Path("data/clean/panel_segment.csv"),
                    Path("data/clean/segment_long.csv"))
needs_panel = pytest.mark.skipif(not PANEL.exists(), reason="run src.segments / src.panel first")


# ---- parser: digit-split text layers are resolved only when the columns add up -------------
def test_split_digits_resolved_by_sum_check():
    lay = Layout(ncols=4, block=4, medical=0, total=3, n_sum=3)
    # '8 4,537' is 84,537 (not 8 and 4,537) because 84,537 + 10 + 5 = 84,552
    assert solve_row(["8", "4,537", "10", "5", "84,552"], lay) == [84537, 10, 5, 84552]


def test_row_that_does_not_add_up_is_rejected():
    lay = Layout(ncols=3, block=3, medical=0, total=2, n_sum=2)
    assert solve_row(["100", "50", "999"], lay) is None


def test_parentheses_and_dash():
    lay = Layout(ncols=3, block=3, medical=0, total=2, n_sum=2)
    assert solve_row(["(30)", "-", "(30)"], lay) == [-30, 0, -30]


# ---- extracted data ---------------------------------------------------------------------
@needs_panel
def test_no_conflicting_duplicate_segment_values():
    s = pd.read_csv(SEG)
    k = ["insurer", "period", "scope", "segment", "item"]
    assert (s.groupby(k).value.nunique() <= 1).all()


@needs_panel
def test_printed_service_result_equals_revenue_less_expenses_plus_reinsurance():
    w = pd.read_csv(PANEL)
    x = w[w.printed_vs_calc_diff.notna()]
    assert len(x) >= 100
    assert (x.printed_vs_calc_diff <= 3).all(), x[x.printed_vs_calc_diff > 3][["insurer", "period", "segment"]]


@needs_panel
def test_segment_totals_equal_consolidated_statements():
    w = pd.read_csv(PANEL)
    c = pd.read_csv("data/clean/panel.csv")[["insurer", "period", "revenue", "claims_incurred"]]
    t = w[(w.segment == "total") & (~w.is_derived)].merge(c, on=["insurer", "period"], suffixes=("", "_c"))
    assert len(t) >= 50
    assert ((t.revenue - t.revenue_c).abs() <= 3).all()
    assert ((t.claims - t.claims_incurred).abs() <= 3).all()


@needs_panel
def test_bupa_is_mono_line_medical_equals_total():
    w = pd.read_csv(PANEL)
    b = w[w.insurer == "bupa"].pivot_table(index="period", columns="segment", values=["revenue", "claims"])
    assert (b["revenue"]["medical"] == b["revenue"]["total"]).all()
    assert (b["claims"]["medical"] == b["claims"]["total"]).all()


@needs_panel
def test_multi_line_insurers_medical_is_a_strict_part_of_total():
    w = pd.read_csv(PANEL)
    m = w[(w.segment == "medical") & (~w.mono_line)]
    assert (m.medical_share_of_revenue < 1).all() and (m.medical_share_of_revenue > 0.05).all()


@needs_panel
def test_derived_q4_is_fy_minus_nine_months():
    res = pd.read_csv(LONG)
    d = res[(res.method == "derived_q4") & (res.segment == "medical") & (res.item == "revenue")]
    assert len(d) >= 8
    for _, r in d.iterrows():
        year = r.period[:4]
        fy = res[(res.insurer == r.insurer) & (res.segment == "medical") & (res.item == "revenue")
                 & (res.scope == "period") & (res.period == f"{year}FY")].value.iloc[0]
        ytd = res[(res.insurer == r.insurer) & (res.segment == "medical") & (res.item == "revenue")
                  & (res.scope == "ytd") & (res.period == f"{year}Q3")].value.iloc[0]
        assert r.value == pytest.approx(fy - ytd, abs=0.5)


@needs_panel
def test_ratio_definitions():
    w = pd.read_csv(PANEL)
    assert ((w.claims / w.revenue) - w.loss_ratio).abs().max() < 1e-12
    assert (w.net_service_ratio + w.service_margin - 1).abs().max() < 1e-9
    # expense / combined ratios exist ONLY for the whole-company rows
    assert w[w.segment == "medical"].combined_ratio_total.isna().all()
