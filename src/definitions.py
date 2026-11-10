"""Write reports/RATIO_DEFINITIONS.md: the exact printed line behind each ratio component, per insurer."""
from __future__ import annotations

import pandas as pd

from .clean import map_label

BUPA_FY24_NOTE = dict(page=66, revenue=18_101_517, incurred_claims_and_attrib=16_674_245,
                      past_service_adj=-552_239, acquisition_cf_amortisation=911_454, ise_total=17_033_460)
ITEMS = [("revenue", "Insurance revenue"), ("claims_incurred", "Numerator of loss ratio"),
         ("reinsurance_net", "Net reinsurance result"), ("other_expenses", "Numerator of expense ratio")]
NAMES = {"alrajhitakaful": "Al Rajhi Takaful", "bupa": "Bupa Arabia", "gig": "GIG (Saudi)", "malath": "Malath",
         "medgulf": "Medgulf", "tawuniya": "Tawuniya", "walaa": "Walaa"}


def table() -> pd.DataFrame:
    d = pd.read_csv("data/clean/statements_long.csv")
    d = d[(d.basis == "current") & (d.scope == "period")].copy()
    d["item"] = d.raw_label.map(map_label)
    rows = []
    for ins, g in d.groupby("insurer"):
        r = {"insurer": NAMES[ins]}
        for item, _ in ITEMS:
            x = g[g.item == item].sort_values("source_file")
            r[item] = f"{x.raw_label.iloc[0]} (p.{int(x.source_page.iloc[0])}, {x.source_file.iloc[0]})" if len(x) else "NOT PRINTED"
        rows.append(r)
    return pd.DataFrame(rows)


def main():
    t = table()
    b = BUPA_FY24_NOTE
    pct = {k: v / b["revenue"] for k, v in b.items() if k not in ("page", "revenue")}
    pan = pd.read_csv("data/clean/panel.csv")
    bup = pan[(pan.insurer == "bupa") & (pan.period == "2024FY")].iloc[0]
    md = ["# Ratio definitions (identical for every insurer)", "",
          "| Ratio | Definition |", "|---|---|",
          "| Loss ratio | insurance service expenses / insurance revenue (gross of reinsurance) |",
          "| Net service ratio | (insurance service expenses - net reinsurance result - pool surplus) / insurance revenue |",
          "| Service margin | insurance service result / insurance revenue (= 1 - net service ratio) |",
          "| Expense ratio (whole company only) | other operating expenses / insurance revenue |",
          "| Combined ratio (whole company only) | loss ratio + expense ratio |", "",
          "**'Loss ratio' is an insurance-service-expense ratio, not a pure claims ratio.** Under IFRS 17 the line",
          "*insurance service expenses* contains incurred claims **and** other directly attributable expenses",
          "(including amortised acquisition cash flows, onerous-contract losses and changes to past-service LIC).",
          "The split is not comparable across insurers' notes, so it is not separated here.", "",
          "**Why the expense ratio is whole-company only:** every insurer reports *other operating expenses* as an",
          "unallocated item outside the segment note. A medical expense or combined ratio would need an allocation",
          "key, i.e. an estimate. The medical view therefore stops at the net service ratio / service margin.", "",
          "## What Bupa's ~2% expense ratio measures",
          f"Bupa FY2024 expense ratio = other operating expenses / revenue = {bup.expense_ratio:.2%} (statement of income, p.9).",
          "It excludes everything inside insurance service expenses. From Bupa's FY2024 note (p.66), as % of insurance revenue:", "",
          "| Component of insurance service expenses | % of revenue |", "|---|---|",
          f"| Incurred claims and other directly attributable expenses | {pct['incurred_claims_and_attrib']:.2%} |",
          f"| Changes relating to past service (favourable LIC adjustment) | {pct['past_service_adj']:.2%} |",
          f"| Insurance acquisition cash flows amortisation | {pct['acquisition_cf_amortisation']:.2%} |",
          f"| **Insurance service expenses (= numerator of loss ratio)** | **{pct['ise_total']:.2%}** |", "",
          "So Bupa's acquisition-cost load (about 5% of revenue) sits in the loss-ratio numerator, and the ~2% 'expense ratio'",
          "is only the residual non-attributable overhead. Ratios built this way are **not comparable to pre-IFRS 17 loss ratios**",
          "(net claims incurred / net premiums earned) and should not be read as a claims-only or underwriting-expense-only measure.", "",
          "## Printed line behind each component (first current-period filing, page = PDF page index)", ""]
    md.append("| Insurer | Revenue | Loss-ratio numerator | Net reinsurance | Expense-ratio numerator |")
    md.append("|---|---|---|---|---|")
    for _, r in t.iterrows():
        md.append(f"| {r.insurer} | {r.revenue} | {r.claims_incurred} | {r.reinsurance_net} | {r.other_expenses} |")
    open("reports/RATIO_DEFINITIONS.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md[-12:]))
    print({k: round(v, 4) for k, v in pct.items()}, "check ISE:", round(pct['incurred_claims_and_attrib'] + pct['past_service_adj'] + pct['acquisition_cf_amortisation'] - pct['ise_total'], 6))


if __name__ == "__main__":
    main()
