"""Phase 2: pull candidate income-statement rows out of filing PDFs.

Output is a LONG table: insurer, period, raw_label, value, unit, source_page, method.
method = 'pdfplumber' or 'manual' (hand-transcribed cells must be marked).

Usage:
    python -m src.extract data/raw/tawuniya_2024Q4.pdf --pages 12 13 --out data/clean/raw_long.csv
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import pdfplumber

NUM = re.compile(r"^\(?-?[\d,]+(\.\d+)?\)?$")


def parse_number(text: str):
    """'(1,234)' -> -1234.0 ; '-' or '' -> None."""
    t = text.strip().replace(" ", "")
    if not t or t in {"-", "—", "–"} or not NUM.match(t):
        return None
    neg = t.startswith("(") and t.endswith(")")
    val = float(t.strip("()").replace(",", ""))
    return -val if neg else val


def parse_filename(path: Path):
    """insurer_period.pdf, e.g. tawuniya_2024Q4.pdf -> ('tawuniya', '2024Q4')."""
    insurer, period = path.stem.rsplit("_", 1)
    return insurer, period


def extract_pages(pdf_path: Path, pages: list[int]) -> pd.DataFrame:
    insurer, period = parse_filename(pdf_path)
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pages:  # 1-indexed page numbers, as printed in the PDF viewer
            page = pdf.pages[p - 1]
            for table in page.extract_tables():
                for row in table:
                    cells = [c for c in row if c is not None]
                    if not cells:
                        continue
                    label = cells[0].strip().replace("\n", " ")
                    values = [parse_number(c) for c in cells[1:]]
                    values = [v for v in values if v is not None]
                    if label and values:
                        # first numeric column = current period by convention; verify!
                        rows.append(
                            dict(insurer=insurer, period=period, raw_label=label,
                                 value=values[0], unit="UNKNOWN",
                                 source_page=p, method="pdfplumber")
                        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--pages", type=int, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    df = extract_pages(a.pdf, a.pages)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, mode="a", header=not a.out.exists(), index=False)
    print(f"{len(df)} rows from {a.pdf.name}; set the 'unit' column by hand after checking the header.")
