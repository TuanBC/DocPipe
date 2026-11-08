"""End-to-end flow for one document (PDF or image):
route -> full-text OCR -> classify -> extract -> validate -> PII guard -> file or review -> KB sync (OpenViking)."""
import json
import time
from pathlib import Path

import pymupdf

from . import extract, filing, llm, ocr, pii, router, validators


def _transcript(pages: dict) -> str:
    lines = []
    for i, ex in pages.items():
        lines.append(f"[p{i}] {ex.page_type} ({ex.unit}; {ex.period_current} vs {ex.period_prior})")
        lines += [f"[p{i}] {it.quote}" for it in ex.items]
    return "\n".join(lines)


def _kb_markdown(result, pages: dict, masked_transcript: str, masked_fulltext: str = "", max_chars: int = 60000) -> str:
    m = result["meta"]
    head = (f"---\ndoc_id: {result['doc_id']}\ncompany: {m['company']}\nfiscal_year: {m.get('fiscal_year')}\n"
            f"period: {m.get('period')}\nscope: {m.get('scope')}\naudited: {m.get('audited')}\n"
            f"doc_type: {m['doc_type']}\nsensitivity: {result['sensitivity']}\n---\n\n")
    body = [f"# {m['company']} {m.get('fiscal_year')} {m.get('period')} ({m.get('scope')})\n"]
    for i, ex in pages.items():
        body.append(f"## Page {i}: {ex.page_type} (unit {ex.unit}; {ex.period_current} vs {ex.period_prior})\n")
        body.append("| line item | current | prior |\n|---|---|---|")
        body += [f"| {it.label} | {it.current} | {it.prior} |" for it in ex.items]
        body.append("")
    md = head + "\n".join(body)
    if pages:
        md += "\n\n## Transcript (masked)\n\n" + masked_transcript + "\n"
    elif masked_fulltext:
        # documents without statement tables (contracts, registrations, scans): the OCR text is the knowledge.
        # Page headings are demoted one level so OpenViking keeps them under the document heading.
        text = masked_fulltext.replace("\n## Page ", "\n### Page ")
        if text.startswith("## Page "):
            text = "#" + text
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[truncated at {max_chars} characters; full text in fulltext/{result['doc_id']}.md]"
        md += "\n## Full text (OCR, masked)\n\n" + text + "\n"
    return md


def process(pdf: Path, cfg, force=False) -> dict:
    t0 = time.time()
    out = Path(cfg.paths.out)
    store = filing.Store(out)
    audit = llm.AuditLog(out / "audit.jsonl")
    sha = filing.sha256_file(pdf)  # hash of the original upload (image or PDF), so re-uploads are idempotent
    doc_id = sha[:16]

    prev = store.state(doc_id)
    if prev and prev.get("pipeline_version") == filing.PIPELINE_VERSION and not force:
        audit.write(event="skipped_idempotent", doc_id=doc_id, status=prev["status"])
        return {"doc_id": doc_id, "status": prev["status"], "skipped": True}

    original = pdf
    pdf = ocr.to_pdf(pdf, out / "_inbox" / doc_id)  # images become a PDF; PDFs pass through
    usage = llm.Usage()
    doc = pymupdf.open(pdf)
    audit.write(event="start", doc_id=doc_id, file=original.name, pages=len(doc), model=cfg.model.name)

    reasons = []
    pages2 = {}
    ocr_pages = {}
    try:
        pages_map = router.route(doc, cfg, usage, audit, doc_id, cache=store.cache_dir(doc_id) / "route.json")
        # Full text for every page: text layer for free, the vision model for image pages (cached, capped).
        ocr_pages = ocr.ocr_pages(doc, cfg, usage, audit, doc_id, store.cache_dir(doc_id), llm_ok=ocr.needs_llm(doc, cfg))
        page_text = {i: p["text"] for i, p in ocr_pages.items() if p["text"]}
        meta = extract.classify_document(doc, cfg, usage, audit, doc_id, extra_pages=list(pages_map),
                                         page_text=page_text or None)
        pages = extract.extract_pages(doc, pages_map, cfg, usage, audit, doc_id, store.cache_dir(doc_id)) if pages_map else {}
        # The router is keyword-based and can pick summary or notes pages; when the extractor reads the page as
        # something else, it is dropped from validation (and logged) instead of polluting unit and support checks.
        for i in [i for i, ex in pages.items() if ex.page_type not in router.STATEMENT_TYPES]:
            audit.write(event="page_demoted", doc_id=doc_id, page=i, routed_type=pages_map[i], extracted_type=pages[i].page_type)
            del pages[i], pages_map[i]
        mode = cfg.validators.second_pass
        if pages and mode != "never":
            corrected = {c["page"] for c in store.corrections(doc_id)}
            todo = {i: t for i, t in pages_map.items()
                    if i not in corrected and (mode == "always" or not router.has_text_layer(doc[i - 1]))}
            if todo:
                pages2 = extract.extract_pages(doc, todo, cfg, usage, audit, doc_id, store.cache_dir(doc_id),
                                               tag="p2_", dpi_boost=50, prompt=extract.PAGE_PROMPT_B)
    except llm.LLMError as e:
        reasons.append(f"model_error: {e}")
        pages_map, pages = {}, {}
        meta = None

    checks = validators.run(pages, doc, cfg.validators) if pages else []
    if pages2:
        checks.append(validators.agreement(pages, pages2))
    if meta is None:
        from .models import DocMeta
        meta = DocMeta(company="unknown", doc_type="other", confidence=0.0, evidence="")
    if not pages and meta.doc_type in cfg.taxonomy.statement_doc_types:
        reasons.append("no statement pages found or extracted")
    all_text = "\n".join(p["text"] for p in ocr_pages.values())
    if not pages and not all_text.strip():
        reasons.append("no text could be read from the document")
    elif not pages and meta.doc_type != "other":
        checks += validators.classification_evidence(meta, all_text)
    conf = validators.confidence(checks, meta.confidence)
    reasons += [f"validator_failed: {c.name} ({c.detail})" for c in checks if c.status == "fail"]
    if meta.doc_type == "other":
        reasons.append("doc_type not in taxonomy")
    if conf < cfg.governance.auto_file_threshold:
        reasons.append(f"confidence {conf} below threshold {cfg.governance.auto_file_threshold}")
    if store.killed(cfg):
        reasons.append("kill switch active")

    transcript = _transcript(pages)
    fulltext = ocr.to_markdown(ocr_pages)
    # The configured detector (regex / luna / both) reads the statement transcript, or the OCR text when there is no
    # transcript; the local regex detector always also scans the full text, which is what the KB export carries.
    # Sensitivity follows what is published to the KB: the statement transcript, or the full text when there are no
    # statement tables. The local full-text file is always masked, but contact lines elsewhere in a 200-page annual
    # report (company hotlines, IR e-mails) must not flip a statements document to 'restricted'.
    entities = pii.detect(transcript or fulltext[:20000], cfg, usage, audit, doc_id) if (transcript or fulltext) else []
    ft_entities = set(entities) | set(pii.detect_regex(fulltext, cfg.pii.entities)) if fulltext else set()
    if not pages:
        entities = sorted(ft_entities, key=lambda e: (e.type, e.text))
    masked, mapping = pii.mask(transcript, entities)
    masked_fulltext, mapping_ft = pii.mask(fulltext, sorted(ft_entities, key=lambda e: (e.type, e.text)))
    mapping.update(mapping_ft)
    sensitivity = "restricted" if entities else "internal"
    if fulltext:
        (out / "fulltext").mkdir(exist_ok=True)
        (out / "fulltext" / f"{doc_id}.md").write_text(masked_fulltext, encoding="utf-8")

    corrections = store.corrections(doc_id)
    result = {
        "doc_id": doc_id, "sha256": sha, "source_file": original.name, "pipeline_version": filing.PIPELINE_VERSION,
        "model": cfg.model.name, "total_pages": len(doc), "statement_pages": pages_map,
        "meta": json.loads(meta.model_dump_json()), "checks": [json.loads(c.model_dump_json()) for c in checks],
        "confidence": conf, "sensitivity": sensitivity,
        "pii": {"detector": cfg.pii.detector, "types": sorted({e.type for e in entities}), "count": len(entities)},
        "ocr": ocr.summary(ocr_pages),
        "extraction": {str(i): json.loads(ex.model_dump_json()) for i, ex in pages.items()},
        "usage": usage.as_dict(cfg.model), "seconds": round(time.time() - t0, 1), "corrections": corrections,
    }
    kb_md = _kb_markdown(result, pages, masked, masked_fulltext, cfg.ocr.kb_fulltext_max_chars)
    # carried across re-runs: the original upload (images are re-processed from it) and the KB location to replace
    keep = {"source": str(original.resolve()), **({"ov_uri": prev["ov_uri"]} if prev and prev.get("ov_uri") else {})}
    restricted = {"doc_id": doc_id, "pii_mapping": mapping}

    if reasons:
        result["decision"], result["reasons"] = "review", reasons
        store.queue_review(result, original, kb_md, restricted, pdf=pdf)
        store.set_state(doc_id, status="review", pipeline_version=filing.PIPELINE_VERSION, **keep)
    else:
        result["decision"], result["reasons"] = ("human_corrected" if corrections else "auto_filed"), []
        (out / "_review" / f"{doc_id}.json").unlink(missing_ok=True)
        path = store.file_document(result, pdf, kb_md, restricted)
        result["filed_path"] = str(path)
        store.set_state(doc_id, status="filed", pipeline_version=filing.PIPELINE_VERSION, path=str(path), **keep)
    audit.write(event="decision", doc_id=doc_id, decision=result["decision"], confidence=conf, reasons=reasons,
                usage=result["usage"], sensitivity=sensitivity)
    if result["decision"] != "review" and _publishes(cfg):
        result["kb"] = kb_sync(doc_id, cfg)
    return result


def _publishes(cfg) -> bool:
    """Auto-publish to OpenViking only from the configured output directory: evaluation harnesses redirect
    cfg.paths.out to scratch folders and must never write their seeded/degraded copies into the real KB."""
    o = cfg.kb.openviking
    home = getattr(o, "home_out", cfg.paths.out)
    return bool(o.auto_ingest) and cfg.kb.backend == "openviking" and Path(cfg.paths.out).resolve() == Path(home).resolve()


def kb_sync(doc_id: str, cfg) -> dict:
    """Push one filed document's masked KB export into OpenViking under its folder. Never raises: a KB outage must
    not undo filing; the outcome is recorded in the state file, the sidecar and the audit log."""
    from .ov_adapter import OpenViking
    out = Path(cfg.paths.out)
    store = filing.Store(out)
    audit = llm.AuditLog(out / "audit.jsonl")
    st = store.state(doc_id) or {}
    if st.get("status") != "filed":
        return {"ov_status": "skipped", "ov_errors": ["document is not filed (review queue items are not published)"]}
    sidecar = Path(st["path"])
    result = json.loads(sidecar.read_text(encoding="utf-8"))
    md = out / "kb_export" / f"{doc_id}.md"
    try:
        kb = OpenViking.from_cfg(cfg).ingest(md, result, previous_uri=st.get("ov_uri"))
    except Exception as e:  # noqa: BLE001
        kb = {"ov_status": "error", "ov_errors": [str(e)[:300]], "ov_ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    store.set_state(doc_id, **{**st, **kb})
    result["kb"] = kb
    sidecar.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    audit.write(event="kb_sync", doc_id=doc_id, **kb)
    return kb


def approve(doc_id: str, reviewer: str, cfg) -> dict:
    out = Path(cfg.paths.out)
    store = filing.Store(out)
    audit = llm.AuditLog(out / "audit.jsonl")
    f, item = store.pop_review(doc_id)
    result = item["result"]
    result["decision"], result["reviewer"] = "human_approved", reviewer
    path = store.file_document(result, Path(item.get("pdf") or item["source"]), item["kb_markdown"], item["restricted"])
    result["filed_path"] = str(path)
    f.unlink()
    prev = store.state(doc_id) or {}
    store.set_state(doc_id, status="filed", pipeline_version=filing.PIPELINE_VERSION, path=str(path), reviewer=reviewer,
                    source=item["source"], **({"ov_uri": prev["ov_uri"]} if prev.get("ov_uri") else {}))
    audit.write(event="human_approved", doc_id=doc_id, reviewer=reviewer, reasons=result.get("reasons"))
    if _publishes(cfg):
        result["kb"] = kb_sync(doc_id, cfg)
    return result


def correct(doc_id: str, page: int, label_contains: str, field: str, value: float, reviewer: str, cfg) -> dict:
    """Reviewer fixes one extracted value; the correction is logged and the document is re-validated and re-filed."""
    out = Path(cfg.paths.out)
    store = filing.Store(out)
    audit = llm.AuditLog(out / "audit.jsonl")
    f, item = store.pop_review(doc_id)
    cache = store.cache_dir(doc_id) / f"page_{page:04d}.json"
    data = json.loads(cache.read_text(encoding="utf-8"))
    hits = [it for it in data["items"] if label_contains.lower() in it["label"].lower()]
    if len(hits) != 1:
        raise ValueError(f"label filter matched {len(hits)} items on page {page}; need exactly 1")
    old = hits[0][field]
    hits[0][field] = value
    cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    entry = {"page": page, "label": hits[0]["label"], "field": field, "old": old, "new": value, "reviewer": reviewer,
             "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    store.add_correction(doc_id, entry)
    audit.write(event="human_correction", doc_id=doc_id, **entry)
    return process(Path(item["source"]), cfg, force=True)


def rollback(doc_id: str, cfg, version: int | None = None, actor: str = "", reason: str = "") -> dict:
    """Restore an earlier filed version of a document (default: the latest snapshot), re-publish it to the KB and log
    who did it. The version being replaced is snapshotted first, so the rollback is itself reversible."""
    out = Path(cfg.paths.out)
    store = filing.Store(out)
    hist = store.history(doc_id)
    if not hist:
        raise ValueError(f"no earlier version of {doc_id} to roll back to")
    version = version or hist[-1]["version"]
    if version not in {h["version"] for h in hist}:
        raise ValueError(f"version {version} not in history {[h['version'] for h in hist]}")
    path = store.restore(doc_id, version)
    restored = json.loads(path.read_text(encoding="utf-8"))
    st = store.state(doc_id) or {}
    (out / "_review" / f"{doc_id}.json").unlink(missing_ok=True)
    store.set_state(doc_id, **{**st, "status": "filed", "path": str(path),
                               "pipeline_version": restored.get("pipeline_version"), "rolled_back_to": version})
    llm.AuditLog(out / "audit.jsonl").write(event="rollback", doc_id=doc_id, to_version=version, actor=actor,
                                            reason=reason, restored_pipeline_version=restored.get("pipeline_version"))
    res = {"doc_id": doc_id, "restored_version": version, "path": str(path),
           "pipeline_version": restored.get("pipeline_version"), "decision": restored.get("decision")}
    if _publishes(cfg):
        res["kb"] = kb_sync(doc_id, cfg)
    return res


def rollback_release(bad_version: str, cfg, actor: str = "", reason: str = "") -> list:
    """Bulk rollback after a bad release: every document currently filed by pipeline `bad_version` goes back to its
    newest snapshot produced by a different pipeline version. Documents with no such snapshot are listed, not touched."""
    out = Path(cfg.paths.out)
    store = filing.Store(out)
    report = []
    for f in sorted((out / "_state").glob("*.json")):
        st = json.loads(f.read_text(encoding="utf-8"))
        if st.get("status") != "filed" or st.get("pipeline_version") != bad_version:
            continue
        good = [h for h in store.history(f.stem) if h.get("pipeline_version") != bad_version]
        if not good:
            report.append({"doc_id": f.stem, "status": "no_earlier_version"})
            continue
        r = rollback(f.stem, cfg, good[-1]["version"], actor=actor, reason=reason or f"release {bad_version} rolled back")
        report.append({"doc_id": f.stem, "status": "rolled_back", **r})
    return report
