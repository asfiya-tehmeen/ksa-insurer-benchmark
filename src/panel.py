"""Build the insurer x period x segment panel (segment = 'medical' | 'total').

Inputs
  data/clean/segments_raw.csv      segment-note extraction (all multi-line insurers)
  data/clean/statements_long.csv   consolidated income statements (used for Bupa and for
                                   whole-company 'other operating expenses')
Outputs
  data/clean/segment_long.csv      one resolved value per insurer/period/segment/item with source page
  data/clean/panel_segment.csv     wide panel with ratios

DEFINITIONS (identical for every insurer; see README 'Ratio definitions')
  revenue         insurance revenue
  claims          insurance service expenses (IFRS 17). Includes incurred claims AND other directly
                  attributable expenses (e.g. acquisition-cash-flow amortisation, onerous-contract
                  losses). It is NOT a pure claims number.
  reinsurance     net result from reinsurance contracts held (negative = net cost)
  pool_surplus    share of surplus from insurance pools (only GIG/Medgulf; 0 elsewhere)
  service_result  revenue - claims + reinsurance + pool_surplus   (= printed 'insurance service result')
  loss_ratio      claims / revenue                                  (gross of reinsurance)
  net_service_ratio (claims - reinsurance - pool_surplus) / revenue = 1 - service_margin
  service_margin  service_result / revenue
  expense_ratio, combined_ratio   WHOLE-COMPANY ONLY: 'other operating expenses' are not allocated to
                  segments by any insurer, so a medical expense/combined ratio would be an estimate.

Mono-line: Bupa states it only writes medical insurance, so medical == total.
Derived: Q4 = FY - 9M (flagged is_derived) when both are printed for the same insurer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .clean import map_label, resolve_overlaps, standardise
from .ratios import is_post_ifrs17

BUPA_NOTE_PAGES = {  # page of the 'mono-line medical insurer' statement in each Bupa filing
    "bupa_2024Q1.pdf": 25, "bupa_2024Q2.pdf": 26, "bupa_2024Q3.pdf": 26,
    "bupa_2024FY.pdf": 52, "bupa_2025Q1.pdf": 22, "bupa_2025Q2.pdf": 23,
}
ITEMS = ["revenue", "claims", "reinsurance_net", "pool_surplus"]


def _segment_long() -> pd.DataFrame:
    seg = pd.read_csv("data/clean/segments_raw.csv")
    seg["item"] = seg["item"].replace({"claims_incurred": "claims"})
    seg.loc[seg["item"] == "claims", "value"] = seg["value"].abs()
    seg["mono_line"] = False
    return seg


def _bupa_long() -> pd.DataFrame:
    """Bupa: segments = whole company (mono-line). Values from the consolidated statement."""
    d = pd.read_csv("data/clean/statements_long.csv")
    d = d[d.insurer == "bupa"].copy()
    d["item"] = d["raw_label"].map(map_label)
    d = d[d["item"].isin(["revenue", "claims_incurred", "reinsurance_net", "service_result"])]
    d["item"] = d["item"].replace({"claims_incurred": "claims"})
    d.loc[d["item"] == "claims", "value"] = d["value"].abs()
    d = d.drop_duplicates(["source_file", "period", "basis", "scope", "item"])
    out = []
    for segname in ("medical", "total"):
        x = d.copy()
        x["segment"] = segname
        out.append(x)
    x = pd.concat(out, ignore_index=True)
    x["mono_line"] = True
    x["segment_note_page"] = x["source_file"].map(BUPA_NOTE_PAGES)
    return x[["insurer", "period", "basis", "scope", "segment", "item", "value", "unit",
              "source_file", "source_page", "method", "mono_line", "segment_note_page"]]


def build_long() -> pd.DataFrame:
    long = pd.concat([_segment_long(), _bupa_long()], ignore_index=True)
    long["unit"] = "SAR_thousands"
    return long


def resolve(long: pd.DataFrame) -> pd.DataFrame:
    """One value per insurer/period/scope/segment/item. Prefer 'current' over 'comparative';
    refuse silently-conflicting duplicates of the same basis."""
    long = long.copy()
    long["_r"] = long["basis"].map({"current": 0, "comparative": 1})
    k = ["insurer", "period", "scope", "segment", "item"]
    conflicts = long.groupby(k + ["basis"]).value.nunique()
    if (conflicts > 1).any():
        raise ValueError(f"conflicting duplicate values:\n{conflicts[conflicts > 1]}")
    return long.sort_values(k + ["_r"], kind="stable").drop_duplicates(k, keep="first").drop(columns="_r")


def add_derived_q4(res: pd.DataFrame) -> pd.DataFrame:
    """Q4 = FY - 9M year-to-date, where both come from filings (flagged derived)."""
    rows = []
    fy = res[(res.scope == "period") & res.period.str.endswith("FY")]
    ytd = res[(res.scope == "ytd") & res.period.str.endswith("Q3")]
    for (ins, seg_, item), g in fy.groupby(["insurer", "segment", "item"]):
        for _, r in g.iterrows():
            year = r.period[:4]
            y = ytd[(ytd.insurer == ins) & (ytd.segment == seg_) & (ytd.item == item) & (ytd.period == f"{year}Q3")]
            if y.empty:
                continue
            rows.append(dict(insurer=ins, period=f"{year}Q4", basis="derived", scope="period", segment=seg_,
                             item=item, value=r.value - y.iloc[0].value, unit="SAR_thousands",
                             source_file=f"{r.source_file} minus {y.iloc[0].source_file}",
                             source_page=f"{r.source_page}/{y.iloc[0].source_page}", method="derived_q4",
                             mono_line=r.mono_line))
    return pd.concat([res, pd.DataFrame(rows)], ignore_index=True)


def build_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    res = resolve(build_long())
    res = add_derived_q4(res)
    res.to_csv("data/clean/segment_long.csv", index=False)
    p = res[res.scope == "period"]
    wide = p.pivot_table(index=["insurer", "period", "segment"], columns="item", values="value", aggfunc="first").reset_index()
    for c in ITEMS + ["service_result"]:
        if c not in wide:
            wide[c] = np.nan
    wide["pool_surplus"] = wide["pool_surplus"].fillna(0.0)
    wide["service_result_printed"] = wide["service_result"]
    wide["service_result"] = wide["revenue"] - wide["claims"] + wide["reinsurance_net"] + wide["pool_surplus"]
    wide["printed_vs_calc_diff"] = (wide["service_result_printed"] - wide["service_result"]).abs()
    wide["freq"] = np.where(wide.period.str.endswith("FY"), "annual", "quarter")
    wide["post_ifrs17"] = wide["period"].map(lambda x: is_post_ifrs17(x))
    wide["loss_ratio"] = wide["claims"] / wide["revenue"]
    wide["net_service_ratio"] = (wide["claims"] - wide["reinsurance_net"] - wide["pool_surplus"]) / wide["revenue"]
    wide["service_margin"] = wide["service_result"] / wide["revenue"]
    mono = res.groupby("insurer").mono_line.first()
    wide["mono_line"] = wide["insurer"].map(mono)
    meta = (p.groupby(["insurer", "period", "segment"])
              .agg(is_derived=("method", lambda s: bool((s == "derived_q4").any())),
                   source_files=("source_file", lambda s: "; ".join(sorted(set(s)))),
                   source_pages=("source_page", lambda s: "; ".join(sorted({str(x) for x in s}))))
              .reset_index())
    wide = wide.merge(meta, on=["insurer", "period", "segment"])
    # medical share of the insurer's total revenue
    tot = wide[wide.segment == "total"].set_index(["insurer", "period"]).revenue
    wide["medical_share_of_revenue"] = np.where(
        wide.segment == "medical",
        wide.apply(lambda r: r.revenue / tot.get((r.insurer, r.period), np.nan), axis=1), np.nan)
    # whole-company expense / combined ratio (other operating expenses from consolidated statement)
    d = pd.read_csv("data/clean/statements_long.csv")
    std, _ = standardise(d)
    cons = resolve_overlaps(std)
    oe = cons[cons.item == "other_expenses"].set_index(["insurer", "period"]).value_sar_k
    wide["other_operating_expenses"] = np.where(
        wide.segment == "total", wide.apply(lambda r: oe.get((r.insurer, r.period), np.nan), axis=1), np.nan)
    wide["expense_ratio_total"] = wide["other_operating_expenses"] / wide["revenue"]
    wide["combined_ratio_total"] = wide["loss_ratio"] + wide["expense_ratio_total"]
    wide = wide.sort_values(["insurer", "segment", "period"]).reset_index(drop=True)
    wide.to_csv("data/clean/panel_segment.csv", index=False)
    return res, wide


if __name__ == "__main__":
    res, wide = build_panel()
    m = wide[wide.segment == "medical"]
    print(len(res), "long rows;", len(wide), "panel rows;", m.insurer.nunique(), "insurers")
    print(m.pivot_table(index="period", columns="insurer", values="loss_ratio").round(3).to_string())
