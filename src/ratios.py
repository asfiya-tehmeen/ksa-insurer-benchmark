"""Insurance ratio definitions. All inputs in the same unit (e.g. SAR thousands).

Definitions (state these in the report):
- loss_ratio     = insurance service expense (claims incurred) / insurance revenue
- expense_ratio  = other operating / acquisition expenses / insurance revenue
- combined_ratio = loss_ratio + expense_ratio
- service_margin = insurance service result / insurance revenue

Pre-IFRS 17 filings use "net premiums earned" and "net claims incurred";
post-IFRS 17 use "insurance revenue" and "insurance service expenses".
The standard names below cover both; clean.py maps raw labels onto them.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

IFRS17_START = pd.Period("2023Q1")


def _safe_div(num, den):
    num = pd.Series(num, dtype="float64")
    den = pd.Series(den, dtype="float64").replace(0, np.nan)
    return num / den


def loss_ratio(claims_incurred, revenue):
    return _safe_div(claims_incurred, revenue)


def expense_ratio(other_expenses, revenue):
    return _safe_div(other_expenses, revenue)


def combined_ratio(claims_incurred, other_expenses, revenue):
    return loss_ratio(claims_incurred, revenue) + expense_ratio(other_expenses, revenue)


def service_margin(service_result, revenue):
    return _safe_div(service_result, revenue)


def is_post_ifrs17(period) -> bool:
    """Accepts quarterly ('2023Q1') or annual ('2023FY') labels."""
    p = str(period)
    if p.upper().endswith("FY"):
        return int(p[:4]) >= IFRS17_START.year
    return pd.Period(p, freq="Q") >= IFRS17_START
