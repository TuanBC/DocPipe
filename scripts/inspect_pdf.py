"""Inspect a PDF: page count, text-layer coverage, and pages matching statement keywords.

Run: uv run python scripts/inspect_pdf.py data/raw/<file>.pdf
"""
import sys

import pymupdf

KEYS = {
    "balance_sheet": ["BẢNG CÂN ĐỐI KẾ TOÁN", "CÂN ĐỐI KẾ TOÁN"],
    "income_stmt": ["BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH"],
    "cash_flow": ["BÁO CÁO LƯU CHUYỂN TIỀN TỆ"],
    "auditor": ["BÁO CÁO CỦA KIỂM TOÁN", "Ý KIẾN CỦA KIỂM TOÁN"],
}

doc = pymupdf.open(sys.argv[1])
print(f"{sys.argv[1]}: {len(doc)} pages")
with_text, hits = 0, {k: [] for k in KEYS}
for i, page in enumerate(doc, 1):
    t = page.get_text()
    if len(t.strip()) > 50:
        with_text += 1
    up = t.upper()
    for k, words in KEYS.items():
        if any(w.upper() in up for w in words):
            hits[k].append(i)
print(f"pages with text layer: {with_text}/{len(doc)}")
for k, v in hits.items():
    print(f"{k}: {v[:20]}{' ...' if len(v) > 20 else ''}")
