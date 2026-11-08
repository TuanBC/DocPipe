"""Page router: pick the statement pages so only they go to the expensive extraction call.

Text-layer pages are routed for free by title keywords plus numeric density.
Pages with no text layer (scans) are classified by a cheap low-resolution model call.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor

import pymupdf

from . import llm
from .models import PageKind

NUM = re.compile(r"\d{1,3}(?:\.\d{3})+")
STATEMENT_TYPES = ("balance_sheet", "income_statement", "cash_flow")


def has_text_layer(page) -> bool:
    return len(page.get_text().strip()) > 50


MAX_PX = 2400  # longest rendered side; oversize pages (some annual-report spreads) exhausted memory at 150 dpi


def render(page, dpi, gray=True) -> bytes:
    """PNG of the page. Grayscale by default: statements are black text and it cuts memory 3x (the dev
    machine runs close to its commit limit). The longest side is capped at MAX_PX."""
    cs = pymupdf.csGRAY if gray else pymupdf.csRGB
    zoom = dpi / 72
    longest = max(page.rect.width, page.rect.height) * zoom
    if longest > MAX_PX:
        zoom *= MAX_PX / longest
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=cs).tobytes("png")


def _by_keywords(text: str, rcfg):
    """Statement type from the title keywords.

    Text-layer order is not reading order, so titles can sit anywhere in `text`; but notes and management
    discussion repeat the same words near the END of a page (footers, cross-references). A match counts only
    in the first `title_max_rel_pos` of the page, and the earliest match decides the type (HPG 2024 page 103
    carries both 'income statement' at 2% and a balance-sheet cross-reference at 93%).
    """
    if len(NUM.findall(text)) < rcfg.min_numeric_tokens:
        return None
    up, n = text.upper(), max(len(text), 1)
    best = None
    for ptype, words in vars(rcfg.statement_keywords).items():
        for w in words:
            pos = up.find(w.upper())
            if pos >= 0 and pos / n <= rcfg.title_max_rel_pos and (best is None or pos < best[0]):
                best = (pos, ptype)
    return best[1] if best else None


def route(doc: pymupdf.Document, cfg, usage, audit=None, doc_id="", cache=None) -> dict:
    """Return {page_number(1-based): page_type} for statement pages.

    `cache` (a json path) stores the model's verdict per scanned page so a re-run does not pay for it again.
    """
    rcfg = cfg.router
    out, scans = {}, []
    for i, page in enumerate(doc, 1):
        if has_text_layer(page):
            ptype = _by_keywords(page.get_text(), rcfg)
            if ptype:
                out[i] = ptype
        else:
            scans.append(i)

    cached = json.loads(cache.read_text(encoding="utf-8")) if cache is not None and cache.exists() else {}

    def classify(i):
        if str(i) in cached:
            return i, cached[str(i)]
        png = render(doc[i - 1], rcfg.vlm_dpi)
        r = llm.call(cfg.model, "Classify this page of a Vietnamese company report. page_type is balance_sheet, "
                     "income_statement or cash_flow only if the page is that primary financial statement "
                     "(a table of line items with numbers); otherwise notes or other.",
                     PageKind, images=[png], usage=usage, audit=audit, doc_id=doc_id, step=f"route_p{i}")
        return i, r.page_type

    if scans:
        with ThreadPoolExecutor(cfg.model.workers) as ex:
            for i, ptype in ex.map(classify, scans):
                cached[str(i)] = ptype
                if ptype in STATEMENT_TYPES:
                    out[i] = ptype
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(cached), encoding="utf-8")
    return dict(sorted(out.items()))
