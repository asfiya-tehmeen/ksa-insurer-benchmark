"""Phase 3: standardise labels/units, resolve overlaps, build the panel.

Ratio definitions (GROSS of reinsurance, so they are comparable across insurers
and match how both Tawuniya and Bupa present the statement):
    loss_ratio      = insurance service expenses / insurance revenue
    expense_ratio   = other operating expenses   / insurance revenue
    combined_ratio  = loss_ratio + expense_ratio
    service_margin  = insurance service result (net of reinsurance) / insurance revenue
These differ from Milliman's NET combined ratio; reconcile in notebooks/03.
"""
from __future__ import annotations

import re

import pandas as pd

from .ratios import is_post_ifrs17

# Matched on SQUASHED text (lower-case, no spaces, 'results'->'result') so OCR output
# like 'Insuranceservicerevenue' maps the same as clean text. First match wins.
LABEL_MAP = [
    ("beforezakat", "pretax_income"),
    ("afterzakat", "net_income"),
    ("netincomeattributabletoshareholdersbefore", "pretax_income"),   # Malath, OCR cut 'zakat'
    ("netincomeattributabletoshareholders", "net_income"),            # Malath
    ("totalincomefortheperiodattributabletotheshareholders", "net_income"),  # GIG
    ("netincomefortheyearattributabletoshareholders", "net_income"),
    ("directlywrittenbusiness", "direct_service_result"),             # GIG subtotal before pools
    ("shareofsurplusfrominsurancepools", "pool_surplus"),             # GIG, Medgulf
    ("insuranceserviceresultbefore", "gross_service_result"),         # any 'before ...reinsurance/retakaful'
    ("netincome(expenses)fromreinsurance", "reinsurance_net"),         # GIG FY
    ("totalincomefortheyearattributabletotheshareholders", "net_income"),  # GIG FY
    ("netexpensesfromreinsurance", "reinsurance_net"),
    ("netexpensefromreinsurance", "reinsurance_net"),                  # singular (Medgulf, GIG)
    ("net(expense)fromretakaful", "reinsurance_net"),                  # Al Rajhi
    ("netexpensefromretakaful", "reinsurance_net"),
    ("netrevenues/(expenses)fromreinsurance", "reinsurance_net"),      # Malath
    ("net(expenses)/incomefromreinsurance", "reinsurance_net"),
    ("netincomefromreinsurance", "reinsurance_net"),
    ("insuranceserviceresult", "service_result"),      # also 'Net/Total insurance service result'
    ("insuranceservicerevenue", "revenue"),
    ("insurancerevenue", "revenue"),
    ("netpremiumsearned", "revenue"),
    ("insuranceserviceexpense", "claims_incurred"),    # singular matches plural
    ("netclaimsincurred", "claims_incurred"),
    ("otheroperatingexpense", "other_expenses"),
    ("netinvestmentincome", "investment_income"),
    ("netinvestmentreturn", "investment_income"),
    ("investmentreturn", "investment_income"),
    ("netinvestmentresult", "investment_income"),
]
# expenses are printed negative in the statements; store them as positive costs
COST_ITEMS = {"claims_incurred", "other_expenses"}

UNIT_TO_THOUSANDS = {"SAR_thousands": 1.0, "SAR_millions": 1000.0, "SAR": 0.001}


def _squash(raw: str) -> str:
    return "".join(raw.lower().split()).replace("results", "result")


def map_label(raw: str):
    r = _squash(raw)
    for key, std in LABEL_MAP:
        if key in r:
            return std
    # wording variants: 'Net (expense) / income from retakaful / reinsurance contracts held',
    # 'Net expenses / (income) from reinsurance ...' (never the finance-income lines)
    if r.startswith("net") and "finance" not in r and re.search(r"from(retakaful/)?reinsurancecontract", r):
        return "reinsurance_net"
    return None


def standardise(long_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (mapped rows, unmapped labels for review)."""
    df = long_df.copy()
    df["item"] = df["raw_label"].map(map_label)
    unmapped = df[df["item"].isna()][["insurer", "raw_label"]].drop_duplicates()
    bad_units = set(df["unit"]) - set(UNIT_TO_THOUSANDS)
    if bad_units:
        raise ValueError(f"Unknown units (fix by hand): {bad_units}")
    df["value_sar_k"] = df["value"] * df["unit"].map(UNIT_TO_THOUSANDS)
    df.loc[df["item"].isin(COST_ITEMS), "value_sar_k"] = df["value_sar_k"].abs()
    return df.dropna(subset=["item"]), unmapped


def resolve_overlaps(std_df: pd.DataFrame) -> pd.DataFrame:
    """One value per (insurer, period, item): prefer the filing for that period
    ('current') over a later filing's prior-year column ('comparative')."""
    d = std_df[std_df["scope"] == "period"].copy()
    d["_rank"] = d["basis"].map({"current": 0, "comparative": 1})
    d = d.sort_values(["insurer", "period", "item", "_rank"], kind="stable")
    return d.drop_duplicates(["insurer", "period", "item"], keep="first").drop(columns="_rank")


WATERFALL_TOL = 2  # SAR thousands (rounding in the filings)


def _waterfall_diff(w: pd.DataFrame) -> pd.Series:
    """|revenue - service expenses + net reinsurance - reported subtotal|.
    Subtotal = GIG's 'directly written business' result if present, else the
    insurance service result less any insurance-pool surplus. NaN = not testable.
    """
    for c in ("reinsurance_net", "pool_surplus", "direct_service_result"):
        if c not in w:
            w[c] = float("nan")
    calc = w["revenue"] - w["claims_incurred"] + w["reinsurance_net"]
    target = w["direct_service_result"].where(
        w["direct_service_result"].notna(),
        w["service_result"] - w["pool_surplus"].fillna(0))
    return (calc - target).abs()


def build_panel(std_df: pd.DataFrame) -> pd.DataFrame:
    d = resolve_overlaps(std_df)
    src = (d.groupby(["insurer", "period"])
             .agg(source_files=("source_file", lambda s: "; ".join(sorted(set(s)))),
                  basis=("basis", lambda s: "current" if (s == "current").all() else "mixed/comparative"))
             .reset_index())
    wide = d.pivot_table(index=["insurer", "period"], columns="item",
                         values="value_sar_k", aggfunc="first").reset_index()
    wide = wide.merge(src, on=["insurer", "period"])
    wide["freq"] = wide["period"].str[4:].map(lambda x: "annual" if x == "FY" else "quarter")
    wide["post_ifrs17"] = wide["period"].map(is_post_ifrs17)
    rev = wide["revenue"].where(wide["revenue"] != 0)
    wide["loss_ratio"] = wide["claims_incurred"] / rev
    wide["expense_ratio"] = wide["other_expenses"] / rev
    wide["combined_ratio"] = wide["loss_ratio"] + wide["expense_ratio"]
    wide["service_margin"] = wide["service_result"] / rev
    wide["waterfall_diff"] = _waterfall_diff(wide)
    wide["waterfall_ok"] = wide["waterfall_diff"].map(lambda x: None if pd.isna(x) else bool(x <= WATERFALL_TOL))
    return wide.sort_values(["insurer", "period"]).reset_index(drop=True)


if __name__ == "__main__":
    long_df = pd.read_csv("data/clean/statements_long.csv")
    std, unmapped = standardise(long_df)
    panel = build_panel(std)
    panel.to_csv("data/clean/panel.csv", index=False)
    print(panel[["insurer", "period", "revenue", "loss_ratio", "expense_ratio",
                 "combined_ratio", "service_margin", "basis"]].round(3).to_string(index=False))
