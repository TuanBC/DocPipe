"""Offline unit tests for the deterministic parts added for OCR, filing layout and the KB (no model or server calls).

Run: uv run --group gateway --with pytest pytest -q tests
"""
import pymupdf
import pytest

from docpipe import config, filing, kb, ocr, pipeline, validators
from docpipe.models import DocMeta, Item, PageExtraction
from docpipe.ov_adapter import DOC_ID, OpenViking


def meta(**kw):
    base = dict(company="CÔNG TY CỔ PHẦN THƯƠNG MẠI AN PHÁT", fiscal_year=2025, doc_type="contract", confidence=0.99,
                evidence="HỢP ĐỒNG TÍN DỤNG HẠN MỨC; BÊN VAY: CÔNG TY CỔ PHẦN THƯƠNG MẠI AN PHÁT")
    base.update(kw)
    return DocMeta(**base)


TEXT = "CỘNG HÒA XÃ HỘI\nHỢP ĐỒNG TÍN DỤNG HẠN MỨC\nBÊN VAY: CÔNG TY CỔ PHẦN THƯƠNG MẠI AN PHÁT\nLãi suất 7,5%/năm"


# --- governance for documents without statement tables ---
def test_evidence_and_company_found():
    checks = validators.classification_evidence(meta(), TEXT)
    assert [c.status for c in checks] == ["pass", "pass"]


def test_hallucinated_company_fails():
    checks = validators.classification_evidence(meta(company="Công ty TNHH Minh Long"), TEXT)
    assert {c.name: c.status for c in checks}["company_in_text"] == "fail"
    assert validators.confidence(checks, 0.99) < 0.9  # cannot auto-file


def test_hallucinated_evidence_fails():
    checks = validators.classification_evidence(meta(evidence="GIẤY CHỨNG NHẬN QUYỀN SỬ DỤNG ĐẤT số AB 123"), TEXT)
    assert {c.name: c.status for c in checks}["classification_evidence"] == "fail"


# --- bank income statement: current + deferred + total tax lines ---
def _inc(items):
    return {8: PageExtraction(page_type="income_statement", unit="triệu đồng", period_current="2025", period_prior="2024",
                              items=[Item(label=l, current=c, prior=None, quote=l) for l, c in items])}


def _net_profit(pages):
    doc = pymupdf.open()
    for _ in range(8):
        doc.new_page()
    return [c for c in validators.run(pages, doc, config.load().validators) if c.name == "net_profit[current]"][0]


def test_net_profit_uses_total_tax_when_components_also_printed():
    c = _net_profit(_inc([("Tổng lợi nhuận trước thuế", 32538066), ("Chi phí thuế thu nhập doanh nghiệp hiện hành", -6544225),
                          ("Chi phí thuế thu nhập doanh nghiệp hoãn lại", -39369), ("Chi phí thuế thu nhập doanh nghiệp", -6583594),
                          ("Lợi nhuận sau thuế", 25954472)]))
    assert c.status == "pass", c.detail


def test_net_profit_sums_components_without_total():
    c = _net_profit(_inc([("Lợi nhuận kế toán trước thuế", 1000), ("Chi phí thuế TNDN hiện hành", -200),
                          ("Chi phí thuế TNDN hoãn lại", -50), ("Lợi nhuận sau thuế", 750)]))
    assert c.status == "pass", c.detail


# --- folder layout shared by disk and OpenViking ---
def test_folder_parts_period_or_doc_type():
    assert filing.folder_parts({"company": "Công ty Cổ phần Sữa Việt Nam", "fiscal_year": 2025, "period": "FY",
                                "doc_type": "annual_report"}) == ["sua-viet-nam", "2025", "FY"]
    assert filing.folder_parts({"company": "CÔNG TY CỔ PHẦN THƯƠNG MẠI AN PHÁT", "fiscal_year": None, "period": "unknown",
                                "doc_type": "invoice"}) == ["thuong-mai-an-phat", "unknown-year", "invoice"]


def test_ov_target_uri_mirrors_disk_and_parses_doc_id():
    res = {"doc_id": "0123456789abcdef", "meta": {"company": "Tập đoàn Hòa Phát", "fiscal_year": 2024, "period": "FY",
                                                 "doc_type": "annual_report", "scope": "consolidated"}}
    uri = OpenViking("http://x", root="viking://resources/docpipe").target_uri(res)
    assert uri == "viking://resources/docpipe/hoa-phat/2024/FY/annual_report__consolidated__0123456789abcdef"
    assert DOC_ID.search(uri + "/node/.overview.md").group(1) == "0123456789abcdef"
    assert DOC_ID.search("viking://resources/docpipe/0123456789abcdef.md").group(1) == "0123456789abcdef"


def test_refiling_moves_and_prunes_empty_folders(tmp_path):
    store = filing.Store(tmp_path)
    src = tmp_path / "x.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    res = {"doc_id": "0123456789abcdef", "meta": {"company": "A Co", "fiscal_year": 2025, "period": "unknown",
                                                 "doc_type": "contract", "scope": "unknown", "audited": None}}
    p1 = store.file_document(res, src, "md", {})
    res["meta"]["doc_type"] = "invoice"
    p2 = store.file_document(res, src, "md", {})
    assert p2.exists() and not p1.exists()
    assert not (tmp_path / "filed" / "a-co" / "2025" / "contract").exists()
    p3 = store.file_document(res, src, "md", {})  # same folder again: must not delete its own target
    assert p3.exists()


# --- KB chunks from OCR text ---
def test_fulltext_chunks_keep_page_numbers_and_access_filter():
    res = {"doc_id": "0123456789abcdef", "source_file": "a.png", "sensitivity": "restricted",
           "meta": {"company": "A", "fiscal_year": 2025, "doc_type": "contract"}}
    md = ocr.to_markdown({1: {"text": "Điều 1. Hạn mức", "source": "llm"}, 2: {"text": "Điều 3. Tài sản bảo đảm", "source": "llm"}})
    chunks = kb.chunks_from_fulltext(res, md)
    assert [c.page for c in chunks] == [1, 2] and chunks[1].sensitivity == "restricted"
    local = kb.LocalKB(dense=False)
    local.add(chunks)
    assert local.search("tài sản bảo đảm", clearance="internal") == []
    assert local.search("tài sản bảo đảm", clearance="restricted")[0][1].page == 2


def test_openviking_kb_keeps_access_filter_and_falls_back():
    local = kb.LocalKB(dense=False)
    local.add([kb.Chunk("a:p1:0", "a" * 16, 1, "A", 2025, "restricted", "vốn điều lệ 45 tỷ"),
               kb.Chunk("b:p1:0", "b" * 16, 1, "B", 2025, "internal", "vốn điều lệ 10 tỷ")])

    class FakeOV:
        def find_docs(self, q, limit):
            return ["a" * 16, "b" * 16]
    hits = kb.OpenVikingKB(local, FakeOV()).search("vốn điều lệ", clearance="internal")
    assert [c.doc_id for _, c in hits] == ["b" * 16]

    class DownOV:
        def find_docs(self, q, limit):
            raise RuntimeError("down")
    k = kb.OpenVikingKB(local, DownOV())
    assert k.search("vốn điều lệ", clearance="restricted") and "failed" in k.last_info["backend"]


# --- input normalisation and OCR policy ---
def test_image_to_pdf_and_text_layer_ocr_is_free(tmp_path):
    from PIL import Image
    img = tmp_path / "scan.png"
    Image.new("L", (200, 100), 255).save(img)
    pdf = ocr.to_pdf(img, tmp_path / "inbox")
    assert pdf.suffix == ".pdf" and len(pymupdf.open(pdf)) == 1
    with pytest.raises(ValueError):
        ocr.to_pdf(tmp_path / "a.docx", tmp_path)

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Bang can doi ke toan " * 5)
    doc.new_page()  # image-like page without text, model OCR disabled -> skipped, no call made
    pages = ocr.ocr_pages(doc, config.load(), None, None, "t", tmp_path / "cache", llm_ok=False)
    assert pages[1]["source"] == "text_layer" and pages[2]["source"] == "skipped"


def test_publish_guard_blocks_redirected_output():
    cfg = config.load()
    assert pipeline._publishes(cfg) == (cfg.kb.backend == "openviking" and bool(cfg.kb.openviking.auto_ingest))
    cfg.paths.out = "data/eval/some_harness"
    assert pipeline._publishes(cfg) is False
