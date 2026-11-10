"""Seeded random 10% audit of extracted values against the source PDFs.

Population = every value that feeds the panels:
  (a) consolidated statement items (revenue, claims, reinsurance, service result, net income), current period/ytd columns;
  (b) segment-note items (medical + total columns).
Text-layer pages are checked automatically: the printed number must appear on the page text (whitespace removed,
so digit-split layers still match; whole-number boundaries enforced). OCR pages have no text layer; their sampled
values are written to reports/audit_ocr_sample.csv for visual checking against the rendered page.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

from .clean import map_label

RAW = Path("data/raw")
SEED = 42
KEEP = {"revenue", "claims_incurred", "reinsurance_net", "service_result", "net_income"}


def population() -> pd.DataFrame:
    s = pd.read_csv("data/clean/statements_long.csv")
    s["item"] = s.raw_label.map(map_label)
    s = s[s["item"].isin(KEEP) & (s.basis == "current")].drop_duplicates(["source_file", "period", "scope", "item"])
    s = s.assign(origin="statement", segment="total")[["origin", "source_file", "source_page", "method", "period", "scope", "segment", "item", "value"]]
    g = pd.read_csv("data/clean/segments_raw.csv")
    g = g[g.basis == "current"].drop_duplicates(["source_file", "period", "scope", "segment", "item", "source_page"])
    g = g.assign(origin="segment")[["origin", "source_file", "source_page", "method", "period", "scope", "segment", "item", "value"]]
    return pd.concat([s, g], ignore_index=True)


def printed_forms(v: float) -> list[str]:
    n = f"{abs(round(v)):,}"
    return [f"({n})", n] if v < 0 else [n]


def on_page(raw_text: str, v: float) -> str:
    """'strict'  : printed form found as a whole number in the normally spaced page text;
    'loose'   : found only after removing all spaces (digit-split text layer: needs a human look);
    'missing' : not found."""
    if v == 0:
        return "strict"
    squeezed = re.sub(r"\s+", "", raw_text)
    for f in printed_forms(v):
        if re.search(r"(?<![\d,.])" + re.escape(f) + r"(?![\d,])", raw_text):
            return "strict"
    for f in printed_forms(v):
        if f in squeezed:
            return "loose"
    return "missing"


def run(frac: float = 0.10) -> tuple[pd.DataFrame, dict]:
    pop = population()
    sample = pop.sample(frac=frac, random_state=SEED).reset_index(drop=True)
    sample["check"] = None
    cache: dict[tuple[str, int], str] = {}
    for i, r in sample.iterrows():
        if r.method == "ocr":
            continue  # visual check
        key = (r.source_file, int(r.source_page))
        if key not in cache:
            with pdfplumber.open(RAW / r.source_file) as pdf:
                cache[key] = pdf.pages[key[1] - 1].extract_text() or ""
        sample.at[i, "check"] = on_page(cache[key], r.value)
    sample.loc[sample.method == "ocr"].to_csv("reports/audit_ocr_sample.csv", index=False)
    sample.to_csv("reports/audit_sample.csv", index=False)
    c = sample.check.value_counts()
    return sample, {"population": len(pop), "sample": len(sample),
                    "text_strict_pass": int(c.get("strict", 0)), "text_loose_needs_look": int(c.get("loose", 0)),
                    "text_missing": int(c.get("missing", 0)), "ocr_to_check": int((sample.method == "ocr").sum())}


if __name__ == "__main__":
    s, info = run()
    print(info)
    print(s[s.check.isin(["loose", "missing"])][["source_file", "source_page", "period", "segment", "item", "value", "check"]].to_string())
    print(s[s.method == "ocr"].groupby(["source_file", "source_page"]).size())
