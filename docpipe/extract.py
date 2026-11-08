"""Page extraction and document classification. Page results are cached so re-runs resume."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

from . import llm
from .models import DocMeta, PageExtraction
from .router import has_text_layer, render

PAGE_PROMPT = (
    "You read one page of a Vietnamese financial statement. Extract every line item that has numbers. "
    "Numbers are printed with '.' as thousands separator and parentheses mean negative; return plain "
    "numbers without separators, negative as '-'. A dash or blank cell is null. Copy the row text into "
    "'quote' exactly as printed. Never compute or guess a value that is not printed on the page."
)
PAGE_PROMPT_B = (
    "Independent re-read of one page of a Vietnamese financial statement. Go row by row and copy every printed "
    "number digit by digit; the thousands separator is '.', parentheses mean negative, a dash or blank is null. "
    "Return plain numbers without separators, negative as '-', and copy each row into 'quote' exactly as printed. "
    "Do not compute, round or infer any value."
)


def extract_pages(doc: pymupdf.Document, pages: dict, cfg, usage, audit, doc_id, cache_dir: Path,
                  tag: str = "", dpi_boost: int = 0, prompt: str = PAGE_PROMPT) -> dict:
    """Return {page: PageExtraction}. Uses cached results when present.

    tag/dpi_boost/prompt allow an independent second pass (different prompt and resolution).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    def one(i):
        f = cache_dir / f"{tag}page_{i:04d}.json"
        if f.exists():
            return i, PageExtraction.model_validate_json(f.read_text(encoding="utf-8")), True
        png = render(doc[i - 1], cfg.model.render_dpi + dpi_boost)
        r = llm.call(cfg.model, prompt, PageExtraction, images=[png], usage=usage, audit=audit,
                     doc_id=doc_id, step=f"extract{'_' + tag.strip('_') if tag else ''}_p{i}")
        f.write_text(r.model_dump_json(indent=1), encoding="utf-8")
        return i, r, False

    out = {}
    with ThreadPoolExecutor(cfg.model.workers) as ex:
        for i, r, cached in ex.map(one, list(pages)):
            out[i] = r
            if audit:
                audit.write(event="page_extracted", doc_id=doc_id, page=i, cached=cached, pass_tag=tag or "a",
                            page_type=r.page_type, items=len(r.items))
    return out


def classify_document(doc: pymupdf.Document, cfg, usage, audit, doc_id, extra_pages=(), page_text=None) -> DocMeta:
    """Cheap document-level classification from the first pages plus the first statement page.

    The statement page title carries scope (hợp nhất / riêng lẻ), which cover pages usually lack.
    page_text ({page: text}, e.g. from full-text OCR) replaces the text layer so scanned documents are classified
    from their transcription instead of low-resolution images.
    """
    nums = list(range(1, min(3, len(doc)) + 1)) + list(extra_pages)[:1]
    if page_text:
        text = "\n".join((page_text.get(i) or "")[:2500] for i in nums)[:7000].strip()
    else:
        text = "\n".join(doc[i - 1].get_text()[:2500] for i in nums if has_text_layer(doc[i - 1]))[:7000]
    first = [doc[i - 1] for i in nums]
    images = None if text else [render(p, 80) for p in first]
    types = ", ".join(cfg.taxonomy.doc_types)
    instr = (f"Classify this Vietnamese company document. doc_type must be one of: {types}. "
             "Hints: financial_statements = báo cáo tài chính; annual_report = báo cáo thường niên; "
             "auditor_report = báo cáo kiểm toán độc lập; business_registration = giấy chứng nhận đăng ký doanh nghiệp; "
             "board_resolution = nghị quyết / biên bản họp HĐQT hoặc ĐHĐCĐ; contract = hợp đồng; invoice = hóa đơn; "
             "tax_document = tờ khai / quyết toán thuế; bank_statement = sao kê tài khoản; "
             "collateral_document = giấy tờ tài sản bảo đảm (GCN quyền sử dụng đất, đăng ký xe, chứng thư thẩm định giá). "
             "company is the bank's corporate customer the document is about: the issuer of a report, the registrant, "
             "the borrower in a contract, the BUYER on an invoice (not the seller), the account holder on a statement; "
             "never the bank, the auditor or a government office. Copy its full legal name as printed. "
             "fiscal_year is the year the document refers to (report year, or issue/signing year for other documents). "
             "scope is consolidated (hợp nhất) or separate (riêng lẻ), unknown when it does not apply. period FY = full year. "
             "Use 'other' with low confidence if unsure.")
    meta = llm.call(cfg.model, instr, DocMeta, text=text, images=images, usage=usage, audit=audit,
                    doc_id=doc_id, step="classify_doc")
    if meta.doc_type not in cfg.taxonomy.doc_types:
        meta.doc_type, meta.confidence = "other", min(meta.confidence, 0.3)
    return meta


def dump(obj) -> dict:
    return json.loads(obj.model_dump_json())
