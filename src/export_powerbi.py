"""Export a small star schema for Power BI to reports/powerbi/.

    python -m src.export_powerbi

fact_insurer_period.csv  grain: insurer x period x segment ('medical' | 'total'); additive SAR-thousand values only.
dim_insurer.csv          one row per insurer.
dim_period.csv           one row per period; integer keys so DAX MAX()/lookups work.
Ratios are deliberately NOT in the fact table: they must be computed as ratio-of-sums by the DAX measures
(averaging row-level ratios is wrong). See MEASURES.md.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

OUT = Path("reports/powerbi")
NAMES = {"alrajhitakaful": "Al Rajhi Takaful", "bupa": "Bupa Arabia", "gig": "GIG (Saudi)", "malath": "Malath",
         "medgulf": "Medgulf", "tawuniya": "Tawuniya", "walaa": "Walaa"}
# lines of business as printed in each insurer's segment-note column headers
LINES = {
    "alrajhitakaful": "Motor; Medical/Health; Property & casualty; Protection & savings",
    "bupa": "Medical only (mono-line, stated in segment note)",
    "gig": "Motor; Property & casualty; Health; Protection",
    "malath": "Medical; Motor; Property; Engineering; Marine; Others",
    "medgulf": "Medical; Motor; Property & casualty",
    "tawuniya": "Medical; Motor; Property & casualty; General accident; Travel/Hajj/Umrah; COVID-19; Protection & savings",
    "walaa": "Medical; Motor; Property; Energy; Engineering; Protection & savings (linked / non-linked); Others",
}


def period_key(p: str) -> int:
    return int(p[:4]) * 10 + (0 if p.endswith("FY") else int(p[5]))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    w = pd.read_csv("data/clean/panel_segment.csv")

    fact = w.assign(
        insurer_key=w.insurer, period_key=w.period.map(period_key),
    )[["insurer_key", "period_key", "segment", "revenue", "claims", "reinsurance_net", "pool_surplus",
       "service_result", "other_operating_expenses", "is_derived", "source_files", "source_pages"]]
    fact = fact.rename(columns={"claims": "service_expenses"})
    fact.to_csv(OUT / "fact_insurer_period.csv", index=False)

    med = w[w.segment == "medical"]
    di = pd.DataFrame({"insurer_key": list(NAMES), "insurer_name": list(NAMES.values())})
    di["mono_line_medical"] = di.insurer_key.eq("bupa")
    di["lines_of_business"] = di.insurer_key.map(LINES)
    share = med.groupby("insurer").medical_share_of_revenue.agg(["min", "max"])
    di["medical_share_min"] = di.insurer_key.map(share["min"]).round(3)
    di["medical_share_max"] = di.insurer_key.map(share["max"]).round(3)
    di["first_period"] = di.insurer_key.map(med.groupby("insurer").period.min())
    di["last_period"] = di.insurer_key.map(med.groupby("insurer").period.max())
    di.to_csv(OUT / "dim_insurer.csv", index=False)

    per = sorted(set(w.period), key=period_key)
    rows = []
    for p in per:
        y, fy = int(p[:4]), p.endswith("FY")
        q = None if fy else int(p[5])
        end = pd.Timestamp(year=y, month=12 if fy else q * 3, day=31 if (fy or q in (1, 4)) else 30)
        rows.append(dict(
            period_key=period_key(p), period_label=f"FY{y}" if fy else f"{y} Q{q}", period_code=p, year=y, quarter=q,
            freq="annual" if fy else "quarter", period_end_date=end.date().isoformat(),
            post_ifrs17=y >= 2023,
            prior_year_key=(y - 1) * 10 + (0 if fy else q),
            prior_period_key=None if fy else (y * 10 + q - 1 if q > 1 else (y - 1) * 10 + 4),
        ))
    pd.DataFrame(rows).to_csv(OUT / "dim_period.csv", index=False)
    print(fact.shape, di.shape, len(rows), "->", OUT)


if __name__ == "__main__":
    main()
