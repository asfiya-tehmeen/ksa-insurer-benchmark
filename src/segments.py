"""Extract MEDICAL-segment (and total) insurance figures from the operating-segment note.

Why: only Bupa is mono-line medical. Tawuniya, Al Rajhi Takaful, GIG, Malath, Medgulf
and Walaa also write motor / property / etc., so whole-company ratios are not a
health-insurance benchmark.

Method (no estimation):
* find pages whose text has 'segment' + 'insurance revenue' (+ medical/health);
* per table row, read the numbers with a per-insurer column layout (LAYOUTS);
* digit-split text layers ('8 4,537') are resolved by enumerating the ways to join
  tokens into the expected number of columns and keeping the one whose segment columns
  SUM TO THE PRINTED TOTAL column. No solution / several solutions -> row is rejected.
* the period block comes from the caption ('three-month ... September 30, 2025');
  captions whose month does not match the filing's quarter are ignored.

Output rows: insurer, period, basis, scope, segment ('medical'|'total'), item, value,
unit, source_file, source_page, method ('pdfplumber' | 'derived' | 'mono_line').
Signs are as printed (costs negative).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pdfplumber

from .clean import map_label

NUMRE = re.compile(r"^\(?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?$|^-$")
WANTED = {"revenue", "claims_incurred", "reinsurance_net", "service_result", "pool_surplus"}
MONTH_OF = {"Q1": "march", "Q2": "june", "Q3": "september", "FY": "december"}
TOL = 3  # SAR thousands; segment columns vs printed total (rounding)


@dataclass(frozen=True)
class Layout:
    ncols: int       # numbers per row on the page (all blocks side by side)
    block: int       # numbers per block (== ncols unless blocks sit side by side)
    medical: int     # index of the medical/health column inside a block
    total: int       # index of the total column inside a block
    n_sum: int       # first n_sum columns must sum to the total column


# candidate layouts per insurer; the one whose sum check passes is used
LAYOUTS: dict[str, list[Layout]] = {
    "tawuniya":       [Layout(8, 8, 0, 7, 7)],
    "alrajhitakaful": [Layout(6, 6, 1, 5, 5)],
    "gig":            [Layout(10, 5, 2, 4, 4), Layout(5, 5, 2, 4, 4)],
    "medgulf":        [Layout(6, 6, 0, 3, 3)],          # Medical, Motor, P&C | ins. total | shareholders | total
    "malath":         [Layout(9, 9, 0, 6, 6), Layout(7, 7, 0, 6, 6)],
    "walaa":          [Layout(10, 10, 0, 9, 9)],
}


# ---------------------------------------------------------------- number parsing
def _val(tok: str) -> float:
    if tok == "-":
        return 0.0
    neg = tok.startswith("(")
    v = float(tok.strip("()").replace(",", ""))
    return -v if neg else v


def _solutions(tokens: list[str], ncols: int):
    """All ways to join up to 3 adjacent tokens into exactly ncols valid numbers."""
    def rec(i, k):
        if k == 0:
            if i == len(tokens):
                yield []
            return
        for g in (1, 2, 3):
            if i + g > len(tokens):
                break
            cand = "".join(tokens[i:i + g])
            if NUMRE.match(cand):
                for rest in rec(i + g, k - 1):
                    yield [cand] + rest
    return rec(0, ncols)


def solve_row(tokens: list[str], layout: Layout):
    """Return list of floats or None. Needs sum(segments)==total in every block."""
    good = []
    for sol in _solutions(tokens, layout.ncols):
        vals = [_val(t) for t in sol]
        ok = True
        for b in range(layout.ncols // layout.block):
            blk = vals[b * layout.block:(b + 1) * layout.block]
            if abs(sum(blk[:layout.n_sum]) - blk[layout.total]) > TOL:
                ok = False
                break
        if ok:
            good.append(vals)
    uniq = {tuple(g) for g in good}
    return list(next(iter(uniq))) if len(uniq) == 1 else None


# ---------------------------------------------------------------- line parsing
def _split_label(line: str):
    """(label, numeric tokens). Numeric region starts at the first digit-like token."""
    line = re.sub(r"\(\s+", "(", line)
    line = re.sub(r"\s+\)", ")", line)
    toks = line.split()
    for i, t in enumerate(toks):
        if re.match(r"^\(?-?\d", t) or t == "-" or re.match(r"^,\d{3}", t):
            return " ".join(toks[:i]), toks[i:]
    return " ".join(toks), []


CAP_RE = re.compile(r"(three|six|nine|twelve)[\s-]*months?|year\s+ended", re.I)


def _captions(text: str):
    """[(scope_word, year, month_name)] found in a caption line (+ context)."""
    out = []
    for m in CAP_RE.finditer(text):
        tail = text[m.end(): m.end() + 120]
        # stop at the next caption so a second block in the same line gets its own year
        nxt = CAP_RE.search(tail)
        tail = tail[: nxt.start()] if nxt else tail
        y = re.search(r"(20\d\d)", tail)
        mo = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)", tail, re.I)
        word = m.group(1).lower() if m.group(1) else "year"
        out.append((word, int(y.group(1)) if y else None, mo.group(1).lower() if mo else None))
    return out


def extract_segments(pdf_path: Path) -> pd.DataFrame:
    insurer, period = pdf_path.stem.rsplit("_", 1)
    fyear, ftag = int(period[:4]), period[4:]
    layouts = LAYOUTS[insurer]
    rows: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        pages = []
        for i, p in enumerate(pdf.pages, 1):
            t = p.extract_text() or ""
            sq = re.sub(r"\s+", "", t.lower())
            if "segment" in t.lower() and ("insurancerevenue" in sq or "insuranceservicerevenue" in sq):
                pages.append((i, t))
        ctx = None  # list of (scope, year) per block, or None
        for pno, text in pages:
            ctx = None  # every table must carry its own caption on the same page
            lines = text.splitlines()
            buf: list[str] = []
            pending = None
            for li, ln in enumerate(lines):
                if CAP_RE.search(ln):
                    window = " ".join(lines[li: li + 3])
                    caps = _captions(window if len(_captions(ln)) < 2 else ln)
                    if caps and all(c[1] for c in caps):
                        if all(c[2] is None or c[2] == MONTH_OF[ftag] for c in caps):
                            ctx = [("period" if c[0] in ("three", "year", "twelve") else "ytd", c[1]) for c in caps]
                        else:
                            ctx = None
                m_p = re.match(r"^for the (?:period|year) ended\s+(?:(\d{1,2})\s+)?([A-Za-z]+)\s+(?:\d{1,2},?\s+)?(20\d\d)", ln, re.I)
                m_d = re.match(r"^(\d{1,2})\s+(December)\s+(20\d\d)", ln) if ftag == "FY" else None
                if m_p or m_d:
                    mon = (m_p.group(2) if m_p else m_d.group(2)).lower()
                    yr = int((m_p.group(3)) if m_p else m_d.group(3))
                    ctx = [("period", yr)] if mon == MONTH_OF[ftag] else None
                label, toks = _split_label(ln)
                if not toks:
                    if pending is not None:
                        _emit(rows, insurer, period, fyear, pending[0] + " " + label, pending[1], pending[2], pno, pdf_path.name)
                        pending = None
                    else:
                        buf = (buf + [label])[-2:]
                    continue
                if pending is not None:
                    _emit(rows, insurer, period, fyear, pending[0], pending[1], pending[2], pno, pdf_path.name)
                    pending = None
                if ctx is None:
                    buf = []
                    continue
                if not label:
                    pending = (" ".join(buf), toks, ctx)  # numbers alone; label continues on next line
                    buf = []
                    continue
                _emit(rows, insurer, period, fyear, " ".join(buf + [label]), toks, ctx, pno, pdf_path.name)
                buf = []
            if pending is not None:
                _emit(rows, insurer, period, fyear, pending[0], pending[1], pending[2], pno, pdf_path.name)
    return pd.DataFrame(rows)


def _emit(rows, insurer, period, fyear, label, toks, ctx, pno, fname):
    item = map_label(label)
    if item not in WANTED:
        return
    for lay in LAYOUTS[insurer]:
        if len(ctx) * lay.block != lay.ncols and not (len(ctx) == 1 and lay.ncols == lay.block):
            continue
        vals = solve_row(toks, lay)
        if vals is None:
            continue
        tag = period[4:]
        for b, (scope, year) in enumerate(ctx):
            blk = vals[b * lay.block:(b + 1) * lay.block]
            per = f"{year}{tag}"
            basis = "current" if year == fyear else "comparative"
            for seg, idx in (("medical", lay.medical), ("total", lay.total)):
                rows.append(dict(insurer=insurer, period=per, basis=basis, scope=scope, segment=seg,
                                 item=item, value=blk[idx], unit="SAR_thousands",
                                 source_file=fname, source_page=pno, method="pdfplumber"))
        return


if __name__ == "__main__":
    import glob

    frames = [extract_segments(Path(f)) for f in sorted(glob.glob("data/raw/*_20[0-9][0-9][QF]*.pdf"))
              if not Path(f).name.startswith("bupa")]          # Bupa is mono-line: no segment split to extract
    seg = pd.concat(frames, ignore_index=True)
    seg.to_csv("data/clean/segments_raw.csv", index=False)
    print(len(seg), "segment rows from", len(frames), "filings")
