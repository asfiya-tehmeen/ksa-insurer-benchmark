import pandas as pd
import pytest

from src.clean import map_label, standardise
from src.extract import parse_number
from src.ratios import combined_ratio, is_post_ifrs17, loss_ratio


def test_loss_ratio_basic():
    assert loss_ratio([80], [100]).iloc[0] == pytest.approx(0.8)


def test_zero_revenue_gives_nan_not_error():
    assert pd.isna(loss_ratio([5], [0]).iloc[0])


def test_combined_is_sum():
    assert combined_ratio([80], [15], [100]).iloc[0] == pytest.approx(0.95)


def test_ifrs17_flag_boundary():
    assert not is_post_ifrs17("2022Q4")
    assert is_post_ifrs17("2023Q1")


def test_parse_number():
    assert parse_number("(1,234)") == -1234.0
    assert parse_number("1,234.5") == 1234.5
    assert parse_number("-") is None


def test_label_map_pre_and_post_ifrs17():
    assert map_label("Net premiums earned") == "revenue"
    assert map_label("Insurance revenue") == "revenue"
    assert map_label("Something odd") is None


def test_unit_reconciliation():
    df = pd.DataFrame(dict(insurer=["a"], period=["2024Q1"], raw_label=["Insurance revenue"],
                           value=[2.0], unit=["SAR_millions"]))
    std, _ = standardise(df)
    assert std["value_sar_k"].iloc[0] == 2000.0
