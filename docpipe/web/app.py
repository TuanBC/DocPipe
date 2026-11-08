"""Web UI + JSON API over the docpipe pipeline.

Run: uv run --group gateway python -m docpipe serve   (http://127.0.0.1:8800)

Long work (pipeline runs, OCR, corrections, KB syncs) goes through a single background worker, so the file-based store
is never written by two pipeline runs at once; reads (library, KB search, Q&A) are served directly.
"""
import json
import queue
import re
import threading
import time
import traceback
import uuid
from pathlib import Path

import httpx
import pymupdf
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response

from .. import filing, kb, llm, monitor, ocr, pipeline, qa
from ..ov_adapter import OpenViking, OVError

STATIC = Path(__file__).parent / "static"


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _safe_name(name: str) -> str:
    name = Path(name or "upload").name
    return re.sub(r"[^\w.\-]+", "_", name)[:120] or "upload"


class Jobs:
    """In-process job queue with one worker thread."""

    def __init__(self):
        self.jobs: dict = {}
        self.q: queue.Queue = queue.Queue()
        self.lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True, name="docpipe-jobs").start()

    def submit(self, kind: str, label: str, fn, doc_id: str | None = None) -> dict:
        job = {"id": uuid.uuid4().hex[:10], "kind": kind, "label": label, "doc_id": doc_id, "status": "queued",
               "created": _now(), "started": None, "finished": None, "result": None, "error": None}
        with self.lock:
            self.jobs[job["id"]] = job
        self.q.put((job["id"], fn))
        return job

    def _worker(self):
        while True:
            jid, fn = self.q.get()
            job = self.jobs[jid]
            job["status"], job["started"] = "running", _now()
            try:
                job["result"] = fn()
                job["status"] = "done"
            except Exception as e:  # noqa: BLE001 - surfaced to the UI
                job["status"], job["error"] = "error", f"{type(e).__name__}: {e}"
                traceback.print_exc()
            job["finished"] = _now()

    def list(self):
        with self.lock:
            return sorted(self.jobs.values(), key=lambda j: j["created"], reverse=True)


def create_app(cfg) -> FastAPI:
    out = Path(cfg.paths.out)
    store = filing.Store(out)
    uploads = out / "_uploads"
    ocr_only = out / "_ocr_only"
    uploads.mkdir(parents=True, exist_ok=True)
    ocr_only.mkdir(parents=True, exist_ok=True)
    jobs = Jobs()
    app = FastAPI(title="docpipe", version=filing.PIPELINE_VERSION)
    # alerts: re-check on the configured interval for as long as the server runs (no external scheduler needed)
    stop_monitor = threading.Event()
    threading.Thread(target=monitor.watch, args=(cfg, stop_monitor), daemon=True, name="docpipe-monitor").start()
    app.state.stop_monitor = stop_monitor

    def ov():
        return OpenViking.from_cfg(cfg)

    # ---------- helpers ----------
    def doc_record(doc_id: str) -> dict | None:
        """Everything the UI needs about one document, from its state file and sidecar / review item."""
        st = store.state(doc_id)
        if not st:
            return None
        rec = {"doc_id": doc_id, "status": st.get("status"), "state": st}
        if st.get("status") == "filed" and st.get("path") and Path(st["path"]).exists():
            res = json.loads(Path(st["path"]).read_text(encoding="utf-8"))
            rec["pdf"] = str(Path(st["path"]).with_suffix(".pdf"))
            rec["folder"] = str(Path(st["path"]).parent.relative_to(out / "filed")).replace("\\", "/")
        elif (out / "_review" / f"{doc_id}.json").exists():
            item = json.loads((out / "_review" / f"{doc_id}.json").read_text(encoding="utf-8"))
            res = item["result"]
            rec["pdf"] = item.get("pdf") or item["source"]
            rec["folder"] = "_review"
        else:
            return None
        rec["result"] = res
        return rec

    def summary(rec: dict) -> dict:
        r, m, st = rec["result"], rec["result"]["meta"], rec["state"]
        return {"doc_id": rec["doc_id"], "status": rec["status"], "folder": rec.get("folder"),
                "source_file": r.get("source_file"), "company": m.get("company"), "fiscal_year": m.get("fiscal_year"),
                "period": m.get("period"), "scope": m.get("scope"), "doc_type": m.get("doc_type"),
                "decision": r.get("decision"), "confidence": r.get("confidence"), "sensitivity": r.get("sensitivity"),
                "pages": r.get("total_pages"), "statement_pages": len(r.get("statement_pages") or {}),
                "ocr": r.get("ocr"), "reasons": r.get("reasons", []),
                "kb": {k: st.get(k) for k in ("ov_status", "ov_uri", "ov_ts", "ov_errors") if st.get(k) is not None}}

    def all_records():
        recs = []
        for f in sorted((out / "_state").glob("*.json")):
            rec = doc_record(f.stem)
            if rec:
                recs.append(rec)
        return recs

    def need(doc_id: str) -> dict:
        if not re.fullmatch(r"[0-9a-f]{16}", doc_id):
            raise HTTPException(400, "bad doc_id")
        rec = doc_record(doc_id)
        if not rec:
            raise HTTPException(404, "document not found")
        return rec

    # ---------- UI ----------
    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC / "index.html").read_text(encoding="utf-8")

    # ---------- system ----------
    @app.get("/api/status")
    def status():
        def probe(url):
            try:
                return httpx.get(url, timeout=3).status_code < 500
            except Exception:  # noqa: BLE001
                return False
        recs = all_records()
        o = ov().health()
        return {
            "model": cfg.model.name, "api_base": cfg.model.api_base, "kb_backend": cfg.kb.backend,
            "ov_url": cfg.kb.openviking.url, "ov_root": cfg.kb.openviking.root, "auto_ingest": cfg.kb.openviking.auto_ingest,
            "auto_file_threshold": cfg.governance.auto_file_threshold, "pii_detector": cfg.pii.detector,
            "taxonomy": cfg.taxonomy.doc_types, "ocr": vars(cfg.ocr),
            "kill_switch": store.killed(cfg),
            "alerts": monitor.active(cfg),
            "services": {
                "openviking": {"ok": o.get("ok", False), "detail": o.get("version") or o.get("error")},
                "litellm_gateway": {"ok": probe("http://127.0.0.1:4010/health/liveliness"),
                                    "detail": "127.0.0.1:4010 (used by OpenViking summaries)"},
                "embeddings": {"ok": probe("http://127.0.0.1:8081/health"), "detail": "127.0.0.1:8081 (used by OpenViking)"},
            },
            "counts": {"filed": sum(r["status"] == "filed" for r in recs), "review": sum(r["status"] == "review" for r in recs),
                       "in_kb": sum(r["state"].get("ov_status", "").startswith("ingested") for r in recs),
                       "jobs_active": sum(j["status"] in ("queued", "running") for j in jobs.list())},
        }

    @app.post("/api/kill")
    def kill(on: bool = Body(..., embed=True)):
        flag = out / cfg.governance.kill_switch_file
        if on:
            flag.write_text("kill switch on\n")
        else:
            flag.unlink(missing_ok=True)
        llm.AuditLog(out / "audit.jsonl").write(event="kill_switch", on=on, actor="web")
        return {"kill_switch": on}

    # ---------- jobs / upload ----------
    @app.get("/api/jobs")
    def list_jobs():
        return jobs.list()[:100]

    @app.get("/api/jobs/{jid}/events")
    def job_events(jid: str):
        job = jobs.jobs.get(jid)
        if not job:
            raise HTTPException(404)
        if not job["doc_id"] or not (out / "audit.jsonl").exists():
            return []
        evs = []
        with open(out / "audit.jsonl", encoding="utf-8") as f:
            for line in f:
                if job["doc_id"] in line:
                    e = json.loads(line)
                    if e.get("doc_id") == job["doc_id"] and e.get("ts", "") >= job["created"]:
                        e.pop("raw", None)
                        evs.append(e)
        return evs[-200:]

    @app.post("/api/upload")
    async def upload(files: list[UploadFile] = File(...), mode: str = Form("pipeline"), force: bool = Form(False)):
        if mode not in ("pipeline", "ocr"):
            raise HTTPException(400, "mode must be pipeline or ocr")
        created = []
        for uf in files:
            name = _safe_name(uf.filename)
            if Path(name).suffix.lower() not in ocr.SUPPORTED_SUFFIXES:
                raise HTTPException(400, f"{name}: unsupported type; use PDF or an image ({', '.join(sorted(ocr.SUPPORTED_SUFFIXES))})")
            tmp = uploads / f"tmp_{uuid.uuid4().hex}_{name}"
            tmp.write_bytes(await uf.read())
            doc_id = filing.sha256_file(tmp)[:16]
            dest = uploads / doc_id / name  # per-document folder keeps the original file name for the sidecar
            dest.parent.mkdir(exist_ok=True)
            tmp.replace(dest)
            if mode == "pipeline":
                created.append(jobs.submit("pipeline", f"Process {name}",
                                           lambda d=dest: _slim(pipeline.process(d, cfg, force=force)), doc_id))
            else:
                created.append(jobs.submit("ocr", f"OCR {name}", lambda d=dest, i=doc_id: run_ocr_only(d, i), doc_id))
        return created

    def run_ocr_only(src: Path, doc_id: str) -> dict:
        pdf = ocr.to_pdf(src, out / "_inbox" / doc_id)
        usage = llm.Usage()
        pages = ocr.ocr_pages(pymupdf.open(pdf), cfg, usage, llm.AuditLog(out / "audit.jsonl"), doc_id,
                              store.cache_dir(doc_id))
        md = ocr.to_markdown(pages, title=src.name)
        (ocr_only / f"{doc_id}.md").write_text(md, encoding="utf-8")
        return {"doc_id": doc_id, "summary": ocr.summary(pages), "usage": usage.as_dict(cfg.model)}

    @app.get("/api/ocr/{doc_id}", response_class=PlainTextResponse)
    def ocr_result(doc_id: str):
        f = ocr_only / f"{doc_id}.md"
        if not re.fullmatch(r"[0-9a-f]{16}", doc_id) or not f.exists():
            raise HTTPException(404)
        return f.read_text(encoding="utf-8")

    def _slim(res: dict) -> dict:
        if res.get("skipped"):
            return res
        return {k: res.get(k) for k in ("doc_id", "decision", "confidence", "reasons", "filed_path", "usage", "seconds", "kb")} | \
            {"meta": res.get("meta")}

    # ---------- library ----------
    @app.get("/api/documents")
    def documents():
        return [summary(r) for r in all_records()]

    @app.get("/api/documents/{doc_id}")
    def document(doc_id: str):
        rec = need(doc_id)
        return {**summary(rec), "result": rec["result"],
                "has_fulltext": (out / "fulltext" / f"{doc_id}.md").exists()}

    @app.get("/api/documents/{doc_id}/file")
    def document_file(doc_id: str):
        rec = need(doc_id)
        return FileResponse(rec["pdf"], media_type="application/pdf")

    @app.get("/api/documents/{doc_id}/page/{n}.png")
    def page_png(doc_id: str, n: int, dpi: int = 110):
        rec = need(doc_id)
        doc = pymupdf.open(rec["pdf"])
        if not 1 <= n <= len(doc):
            raise HTTPException(404, "page out of range")
        z = min(max(dpi, 30), 200) / 72
        pix = doc[n - 1].get_pixmap(matrix=pymupdf.Matrix(z, z))
        return Response(pix.tobytes("png"), media_type="image/png", headers={"Cache-Control": "max-age=300"})

    @app.get("/api/documents/{doc_id}/fulltext", response_class=PlainTextResponse)
    def fulltext(doc_id: str):
        need(doc_id)
        f = out / "fulltext" / f"{doc_id}.md"
        if not f.exists():
            raise HTTPException(404, "no full text yet (re-run the document)")
        return f.read_text(encoding="utf-8")

    @app.post("/api/documents/{doc_id}/reocr")
    def reocr(doc_id: str, page: int = Body(..., embed=True)):
        """Re-transcribe one page with the vision model (e.g. garbled text layer), then re-run the document."""
        rec = need(doc_id)
        src = Path(rec["state"].get("source") or rec["pdf"])

        def run():
            doc = pymupdf.open(rec["pdf"])
            ocr.ocr_pages(doc, cfg, llm.Usage(), llm.AuditLog(out / "audit.jsonl"), doc_id, store.cache_dir(doc_id),
                          pages=[page], force_llm=True)
            return _slim(pipeline.process(src, cfg, force=True))
        return jobs.submit("reocr", f"Re-OCR page {page} of {rec['result'].get('source_file')}", run, doc_id)

    @app.post("/api/documents/{doc_id}/rerun")
    def rerun(doc_id: str):
        rec = need(doc_id)
        src = Path(rec["state"].get("source") or rec["pdf"])
        return jobs.submit("pipeline", f"Re-run {rec['result'].get('source_file')}",
                           lambda: _slim(pipeline.process(src, cfg, force=True)), doc_id)

    @app.get("/api/documents/{doc_id}/history")
    def doc_history(doc_id: str):
        need(doc_id)
        return store.history(doc_id)

    @app.post("/api/documents/{doc_id}/rollback")
    def doc_rollback(doc_id: str, payload: dict = Body(...)):
        need(doc_id)
        actor, reason = str(payload.get("actor", "")).strip(), str(payload.get("reason", "")).strip()
        version = payload.get("version")
        if not actor:
            raise HTTPException(400, "actor (your name) is required: it goes into the audit log")
        try:
            version = int(version) if version is not None else None
        except (TypeError, ValueError):
            raise HTTPException(400, "version must be an integer")
        return jobs.submit("rollback", f"Roll back {doc_id} to v{version or 'latest'}",
                           lambda: pipeline.rollback(doc_id, cfg, version, actor=actor, reason=reason), doc_id)

    # ---------- monitoring ----------
    @app.get("/api/monitor")
    def monitor_now():
        r = monitor.check(cfg)
        return {**r, "history": monitor.history(cfg, 30), "thresholds": monitor._cfg(cfg)}

    @app.get("/api/tree")
    def tree():
        root: dict = {"name": "filed", "children": {}, "docs": []}
        review = []
        for rec in all_records():
            s = summary(rec)
            if rec["status"] != "filed":
                review.append(s)
                continue
            node = root
            for part in (rec.get("folder") or "").split("/"):
                node = node["children"].setdefault(part, {"name": part, "children": {}, "docs": []})
            node["docs"].append(s)

        def norm(n):
            return {"name": n["name"], "docs": n["docs"], "children": [norm(c) for _, c in sorted(n["children"].items())]}
        return {"tree": norm(root), "review": review}

    # ---------- review ----------
    @app.post("/api/review/{doc_id}/approve")
    def approve(doc_id: str, reviewer: str = Body(..., embed=True)):
        need(doc_id)
        if not reviewer.strip():
            raise HTTPException(400, "reviewer name required")
        return jobs.submit("approve", f"Approve {doc_id}", lambda: _slim(pipeline.approve(doc_id, reviewer.strip(), cfg)), doc_id)

    @app.post("/api/review/{doc_id}/correct")
    def correct(doc_id: str, payload: dict = Body(...)):
        need(doc_id)
        try:
            page, label, field = int(payload["page"]), str(payload["label"]), payload["field"]
            value, reviewer = float(payload["value"]), str(payload["reviewer"]).strip()
        except (KeyError, ValueError, TypeError) as e:
            raise HTTPException(400, f"bad correction: {e}")
        if field not in ("current", "prior") or not reviewer:
            raise HTTPException(400, "field must be current|prior and reviewer is required")
        return jobs.submit("correct", f"Correct {label!r} p{page}",
                           lambda: _slim(pipeline.correct(doc_id, page, label, field, value, reviewer, cfg)), doc_id)

    # ---------- knowledge base ----------
    @app.post("/api/kb/sync/{doc_id}")
    def kb_sync(doc_id: str):
        need(doc_id)
        return jobs.submit("kb_sync", f"KB sync {doc_id}", lambda: pipeline.kb_sync(doc_id, cfg), doc_id)

    @app.post("/api/kb/sync_all")
    def kb_sync_all():
        ids = [r["doc_id"] for r in all_records() if r["status"] == "filed"]
        return jobs.submit("kb_sync", f"KB sync all ({len(ids)} documents)",
                           lambda: {d: pipeline.kb_sync(d, cfg).get("ov_status") for d in ids})

    @app.get("/api/kb/tree")
    def kb_tree():
        try:
            entries = ov().ls(recursive=True, levels=6)
        except OVError as e:
            raise HTTPException(502, str(e))
        return [{"rel_path": e.get("rel_path", e["name"]), "name": e["name"], "isDir": e["isDir"], "uri": e["uri"]}
                for e in entries if not e["name"].startswith(".")]

    @app.get("/api/kb/read", response_class=PlainTextResponse)
    def kb_read(uri: str):
        if not uri.startswith(cfg.kb.openviking.root + "/") or ".." in uri:
            raise HTTPException(400, "uri outside the docpipe root")
        try:
            target = uri if uri.endswith(".md") else uri.rstrip("/") + "/.overview.md"
            return ov().read(target)
        except OVError as e:
            raise HTTPException(502, str(e))

    @app.post("/api/kb/find")
    def kb_find(query: str = Body(..., embed=True), limit: int = Body(10, embed=True)):
        try:
            return ov().find(query, limit=min(max(limit, 1), 50))
        except OVError as e:
            raise HTTPException(502, str(e))

    @app.post("/api/ask")
    def ask(question: str = Body(..., embed=True), clearance: str = Body("internal", embed=True),
            backend: str = Body("openviking", embed=True)):
        if clearance not in kb.LEVELS or backend not in ("local", "openviking"):
            raise HTTPException(400, "bad clearance or backend")
        store_kb = kb.build(cfg, out, backend)
        usage = llm.Usage()
        res = qa.ask(question, store_kb, cfg, usage, audit=llm.AuditLog(out / "audit.jsonl"), clearance=clearance)
        res["retrieval"] = getattr(store_kb, "last_info", {"backend": "local"})
        res["usage"] = usage.as_dict(cfg.model)
        names = {r["doc_id"]: summary(r) for r in all_records()}
        ids = {c["doc_id"] for c in res["citations"]} | {x[1] for x in res["retrieved"]}
        res["docs"] = {d: {k: names[d][k] for k in ("company", "doc_type", "fiscal_year", "source_file")}
                       for d in ids if d in names}
        return res

    return app
