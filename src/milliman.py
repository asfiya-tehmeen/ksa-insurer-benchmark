"""Parse the Milliman 'KSA Industry Update' exhibit tables into a long table.

Milliman is the CROSS-CHECK source (README), but its exhibits are clean annual
tables for all listed insurers, so they also seed the panel. Annual periods are
labelled '2024FY'. Unit: SAR thousands (as printed in the exhibit titles).

Usage:
    python -m src.milliman data/raw/6_4_26_KSA-Industry-update-2025.pdf --out data/clean/milliman_long.csv
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import pdfplumber

YEARS = [2025, 2024, 2023, 2022]  # column order used in every exhibit
NUM = re.compile(r"^\(?\d[\d,]*\)?$")

# exhibit title -> list of (item, columns) ; columns are consecutive blocks of 4 years
EXHIBITS = {
    "Exhibit 1": [("insurance_revenue", 0)],
    "Exhibit 2": [("gwp", 0)],
    "Exhibit 3": [("net_income", 0)],
    "Exhibit 4": [("total_assets", 0), ("equity", 4)],
}
SKIP = ("total", "insurance company", "market", "exhibit", "ksa industry")


def _num(tok: str) -> float:
    neg = tok.startswith("(")
    v = float(tok.strip("()").replace(",", ""))
    return -v if neg else v


def parse_rows(text: str):
    """Yield (company, [numbers]) for each table row on a page."""
    for line in text.splitlines():
        toks = line.split()
        idx = next((i for i, t in enumerate(toks) if NUM.match(t) and ("," in t or len(t) > 3)), None)
        if not idx:
            continue
        name = " ".join(toks[:idx])
        if name.lower().startswith(SKIP) or not re.search(r"[A-Za-z]", name):
            continue
        nums = [_num(t) for t in toks[idx:] if NUM.match(t)]
        yield name, nums


def extract(pdf_path: Path) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            head = text.strip().splitlines()[0] if text.strip() else ""
            if head not in EXHIBITS:
                continue
            for company, nums in parse_rows(text):
                for item, offset in EXHIBITS[head]:
                    for k, year in enumerate(YEARS):
                        j = offset + k
                        if j < len(nums):
                            rows.append(dict(
                                insurer=company, period=f"{year}FY", item=item,
                                value=nums[j], unit="SAR_thousands",
                                source_file=pdf_path.name, source_page=pno,
                                source_exhibit=head, method="pdfplumber"))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    df = extract(a.pdf)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print(df.groupby(["source_exhibit", "item"]).agg(insurers=("insurer", "nunique"), rows=("value", "size")))
