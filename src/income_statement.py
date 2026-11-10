"""Extract the consolidated statement of income from an insurer filing.

File naming: insurer_PERIOD.pdf, PERIOD = 2024Q3 (interim, quarter) or 2024FY (annual).

Column layout (read from the header row of years):
  4 cols  -> [quarter cur, quarter prior, YTD cur, YTD prior]   (Q2/Q3 files)
  2 cols  -> [cur, prior]                                       (Q1 and FY files)
Output rows: one per (line item, column) for the quarter/annual columns, flagged
basis='current' or 'comparative' (prior-year column of the same filing; may be
restated, so prefer 'current' where both exist). YTD columns are kept as
scope='ytd' for later Q4 = FY - 9M checks.

Usage:
    python -m src.income_statement data/raw/bupa_2024Q3.pdf data/raw/tawuniya_2024Q3.pdf --out data/clean/statements_long.csv
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import pdfplumber

NUM = re.compile(r"^\(?-?\d[\d,]*(\.\d+)?\)?$|^[-–—]$")
YEAR = re.compile(r"^20\d\d$")


def to_float(tok: str) -> float:
    if tok in {"-", "–", "—"}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    v = float(tok.strip("()").replace(",", ""))
    return -v if neg else v


OCR_CACHE = Path("data/interim/ocr")
REV_KEYS = ("insurancerevenue", "insuranceservicerevenue")


def _squash(t: str) -> str:
    return re.sub(r"\s+", "", t.lower())


def _looks_like_income(text: str) -> bool:
    sq = _squash(text)
    head = sq[:500]
    return (any(k in sq for k in REV_KEYS) and "zakat" in sq and
            ("statementofincome" in head or "statementofprofit" in head or
             "pershare" in sq or "statementofcomprehensiveincome" in head))


def _ocr_text(pdf_path: Path, pno: int) -> str:
    OCR_CACHE.mkdir(parents=True, exist_ok=True)
    f = OCR_CACHE / f"{pdf_path.stem}_p{pno}.txt"
    if f.exists():
        return f.read_text(encoding="utf-8")
    from .ocr import page_text  # heavy import, only when needed
    t = page_text(pdf_path, pno)
    f.write_text(t, encoding="utf-8")
    return t


GLITCH = re.compile(r"\d\s,\d|\(\s+\d|\d\s+\)|\d,\d{3}\s\d{3}(?![\d,])")


def _glitchy(t: str) -> bool:
    """Text layer with split numbers ('1 ,445,363', '3,551 790'): not safe to parse.
    Splitting is ambiguous (note column vs digit), so such pages go to OCR instead."""
    return bool(GLITCH.search(t))


def _score(text: str) -> int:
    """How many full-width statement rows this page yields (0 if unparseable)."""
    try:
        ncols = infer_ncols(text)
        return sum(1 for _, v in parse_lines(text, ncols) if len(v) == ncols)
    except Exception:
        return 0


def find_income_page(pdf_path: Path, pdf, max_page: int = 20, min_rows: int = 8):
    """Return (page_no, text, method) for the primary statement of income.

    Candidates are pages in the front section of the filing that look like an
    income statement; the page yielding the most rows wins (note pages that merely
    mention revenue/zakat yield few). Image-only or garbled pages are OCR'd (cached)
    only if no text page reaches min_rows.
    """
    last = min(len(pdf.pages), max_page)
    cands, weak = [], []
    for i in range(1, last + 1):
        t = pdf.pages[i - 1].extract_text() or ""
        if len(t) < 400 or _garbled(t) or (_looks_like_income(t) and _glitchy(t)):
            weak.append(i)
        elif _looks_like_income(t):
            cands.append((_score(t), i, t, "pdfplumber"))
    best = max(cands, default=(0, 0, "", ""))
    if best[0] >= min_rows:
        return best[1], best[2], best[3]
    for i in weak:
        if i < 3:
            continue
        t = _ocr_text(pdf_path, i)
        if _looks_like_income(t):
            cands.append((_score(t), i, t, "ocr"))
    best = max(cands, default=(0, 0, "", ""))
    if best[0] == 0:
        raise ValueError("income statement page not found")
    return best[1], best[2], best[3]


def _garbled(t: str) -> bool:
    """Heuristic: a bad text layer has many tokens with no vowels / odd symbols."""
    toks = t.split()
    bad = sum(1 for w in toks if len(w) > 3 and not re.search(r"[aeiouAEIOU\d]", w))
    return bool(toks) and bad / len(toks) > 0.08


def detect_unit(text: str) -> str:
    low = text.lower()
    header = low[:1200]  # unit marker sits in the column header (OCR may drop the quote)
    if ("thousand" in low or any(q + "000" in low for q in "’‘'`\"")
            or re.search(r"(?<![\d,.])000(?![\d,])", header)):
        return "SAR_thousands"
    if "million" in low:
        return "SAR_millions"
    return "UNKNOWN"


def n_columns(lines: list[str]) -> int:
    """Count period columns from the header: a row of bare years, or the 'Notes'
    row where dates are spelled out ('March 31, 2025 March 31, 2024')."""
    for ln in lines[:25]:
        toks = [t for t in ln.split() if t.lower() != "notes"]
        if toks and all(YEAR.match(t) for t in toks):
            return len(toks)
    for ln in lines[:25]:
        if ln.lower().startswith("notes"):
            n = sum(bool(YEAR.match(t)) for t in ln.split())
            if n:
                return n
    raise ValueError("year header row not found")


def infer_ncols(text: str) -> int:
    """Columns from the revenue row (robust to OCR); fall back to the year header."""
    for ln in text.splitlines():
        toks = ln.split()
        if _squash(ln).startswith(REV_KEYS):
            k = 0
            while k < len(toks) and NUM.match(toks[-1 - k]):
                k += 1
            if k >= 2:
                return k if k % 2 == 0 else k - 1
    return n_columns(text.splitlines())


NOTE_TOKEN = re.compile(r"^[\d٠-٩]{1,3}(\.\d)?$")


def _clean(label: str) -> str:
    toks = label.split()
    while toks and NOTE_TOKEN.match(toks[-1]):  # stray note-number column
        toks.pop()
    return " ".join(toks)


def parse_lines(text: str, ncols: int):
    """Yield (label, values). Handles labels wrapped before and/or after the numbers."""
    buf: list[str] = []
    pending = None  # (label_so_far, vals) waiting for a trailing label fragment
    lines = text.splitlines()
    has_header = any(l.lower().startswith("notes") or
                     (l.split() and all(YEAR.match(t) for t in l.split())) for l in lines)
    started = not has_header
    for ln in lines:
        toks = ln.split()
        low = ln.lower()
        if not toks:
            continue
        if not started:  # skip title/header block up to the column-header row
            started = (low.startswith("notes") or
                       (bool(toks) and all(YEAR.match(t) for t in toks)))
            continue
        if "accompanyingnotes" in _squash(ln) or low.startswith(("chairman", "board director")):
            break  # signature block
        if any(w in low for w in ("unaudited", "000", "all amounts", "audited")) and not NUM.match(toks[-1]):
            continue  # unit / review-status lines
        k = 0
        while k < len(toks) and NUM.match(toks[-1 - k]):
            k += 1
        nums = toks[len(toks) - k:] if k else []
        label_part = toks[: len(toks) - k]
        if k == 0:
            if pending:
                yield _clean(pending[0] + " " + ln.strip()), pending[1]
                pending = None
            else:
                buf = (buf + [ln.strip()])[-2:]  # labels wrap over at most 2 lines
            continue
        if pending:
            yield _clean(pending[0]), pending[1]
            pending = None
        if k < ncols:
            buf = []
            continue
        vals = [to_float(t) for t in nums]
        if len(vals) == ncols + 1:  # leading note-number column
            vals = vals[1:]
        elif len(vals) > ncols + 1:
            buf = []
            continue
        if label_part:
            yield _clean(" ".join(buf + label_part)), vals
            buf = []
        elif buf:  # numbers on their own line; label continues on the next line
            pending = (" ".join(buf), vals)
            buf = []
    if pending:
        yield _clean(pending[0]), pending[1]


def extract_statement(pdf_path: Path) -> pd.DataFrame:
    insurer, period = pdf_path.stem.rsplit("_", 1)
    with pdfplumber.open(pdf_path) as pdf:
        pno, text, method = find_income_page(pdf_path, pdf)
        unit = detect_unit(text)
        if unit == "UNKNOWN":  # OCR can drop the unit marker; the text layer may still have it
            unit = detect_unit(pdf.pages[pno - 1].extract_text() or "")
    if unit == "UNKNOWN":
        raise ValueError(f"unit not detected on page {pno}; set it by hand")
    ncols = infer_ncols(text)
    year = int(period[:4])
    tag = period[4:]  # 'Q3' / 'FY'
    cols = [(period, "current", "period"), (f"{year-1}{tag}", "comparative", "period")]
    if ncols == 4:
        cols += [(period, "current", "ytd"), (f"{year-1}{tag}", "comparative", "ytd")]
    rows = []
    for label, vals in parse_lines(text, ncols):
        if len(vals) != ncols or "per share" in label.lower() or "weighted" in label.lower():
            continue
        for (per, basis, scope), v in zip(cols, vals):
            rows.append(dict(insurer=insurer, period=per, basis=basis, scope=scope,
                             raw_label=label, value=v, unit=unit,
                             source_file=pdf_path.name, source_page=pno, method=method))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", type=Path, nargs="+")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    frames, failed = [], []
    for p in a.pdfs:
        try:
            frames.append(extract_statement(p))
            print("ok  ", p.name, flush=True)
        except Exception as e:  # keep going; report at the end
            failed.append((p.name, str(e)))
            print("FAIL", p.name, e, flush=True)
    df = pd.concat(frames, ignore_index=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print(df.groupby(["source_file", "method", "source_page"]).size())
    print("failed:", failed)
