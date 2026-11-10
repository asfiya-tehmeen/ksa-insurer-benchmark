"""OCR for statement pages that are scanned images (no text layer).

Renders a PDF page with pypdfium2, runs RapidOCR, and rebuilds text lines by
grouping boxes on the y-axis, so the output looks like pdfplumber text and can
go through src.income_statement.parse_lines. OCR output MUST be spot-checked
against the PDF image (README: 10% re-check); rows from here carry method='ocr'.
"""
from __future__ import annotations

import numpy as np
import pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR

_engine = None


def page_text(pdf_path, page_no: int, scale: float = 3.0) -> str:
    global _engine
    _engine = _engine or RapidOCR()
    pdf = pdfium.PdfDocument(str(pdf_path))
    img = np.array(pdf[page_no - 1].render(scale=scale).to_pil().convert("RGB"))
    result, _ = _engine(img)
    if not result:
        return ""
    boxes = []  # (y_center, x_left, h, text)
    for pts, text, _conf in result:
        ys = [p[1] for p in pts]; xs = [p[0] for p in pts]
        boxes.append(((min(ys) + max(ys)) / 2, min(xs), max(ys) - min(ys), text))
    boxes.sort()
    lines, cur = [], [boxes[0]]
    for b in boxes[1:]:
        if abs(b[0] - cur[-1][0]) <= 0.6 * max(b[2], cur[-1][2]):
            cur.append(b)
        else:
            lines.append(cur); cur = [b]
    lines.append(cur)
    return "\n".join(" ".join(t for _, _, _, t in sorted(l, key=lambda b: b[1])) for l in lines)
