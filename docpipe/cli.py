"""CLI: uv run --group gateway python -m docpipe <command>

  run <pdf...> [--force]      process documents (idempotent; --force re-runs)
  review list                 show the review queue
  review approve <id> --reviewer NAME
  kill on|off                 kill switch: everything goes to review while on
  ask "<question>" [--clearance ..] [--backend local|openviking]
  ocr <pdf|image> [--force-llm] [--out file.md]   full-text OCR via the vision model
  kb sync [doc_id|all] | kb status | kb tree | kb search "<q>"   OpenViking knowledge base
  serve [--port 8800]         web UI
  monitor [--watch]           metrics + alerts (thresholds: monitoring in config)
  rollback <doc_id> [--version N] --actor NAME     restore an earlier filed version
  rollback --release 0.3 --actor NAME              bulk: undo everything filed by a bad pipeline version
  history <doc_id>            list filed versions of a document
"""
import argparse
import json
import sys
from pathlib import Path

from . import config, filing


def main(argv=None):
    ap = argparse.ArgumentParser(prog="docpipe")
    ap.add_argument("--config", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("pdf", nargs="+")
    r.add_argument("--force", action="store_true")
    rv = sub.add_parser("review")
    rv.add_argument("action", choices=["list", "approve", "correct"])
    rv.add_argument("doc_id", nargs="?")
    rv.add_argument("--reviewer", default="")
    rv.add_argument("--page", type=int)
    rv.add_argument("--label", help="substring identifying exactly one line item on --page")
    rv.add_argument("--field", choices=["current", "prior"])
    rv.add_argument("--value", type=float)
    k = sub.add_parser("kill")
    k.add_argument("state", choices=["on", "off"])
    q = sub.add_parser("ask")
    q.add_argument("question")
    q.add_argument("--clearance", choices=["public", "internal", "restricted"], default="internal")
    q.add_argument("--backend", choices=["local", "openviking"], default=None, help="default: kb.backend in config")
    o = sub.add_parser("ocr", help="full-text OCR of a PDF or image (text layer for free, vision model for image pages)")
    o.add_argument("file")
    o.add_argument("--force-llm", action="store_true", help="transcribe text-layer pages with the model too")
    o.add_argument("--out", help="write the Markdown here instead of stdout")
    kbp = sub.add_parser("kb", help="OpenViking knowledge base")
    kbp.add_argument("action", choices=["sync", "status", "search", "tree"])
    kbp.add_argument("arg", nargs="?", help="sync: doc_id or 'all'; search: query")
    sv = sub.add_parser("serve", help="web UI + API")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8800)
    mo = sub.add_parser("monitor", help="compute metrics, fire/resolve alerts")
    mo.add_argument("--watch", action="store_true", help="keep checking every monitoring.check_interval_minutes")
    rb = sub.add_parser("rollback", help="restore an earlier filed version (per document or per release)")
    rb.add_argument("doc_id", nargs="?")
    rb.add_argument("--version", type=int)
    rb.add_argument("--release", help="pipeline version to undo across all documents")
    rb.add_argument("--actor", default="")
    rb.add_argument("--reason", default="")
    hi = sub.add_parser("history", help="filed versions of a document")
    hi.add_argument("doc_id")
    a = ap.parse_args(argv)
    cfg = config.load(a.config)
    out = Path(cfg.paths.out)

    if a.cmd == "serve":
        import uvicorn
        from .web.app import create_app
        uvicorn.run(create_app(cfg), host=a.host, port=a.port)
        return
    if a.cmd == "monitor":
        from . import monitor
        sys.stdout.reconfigure(encoding="utf-8")
        if a.watch:
            monitor.watch(cfg)
            return
        r = monitor.check(cfg)
        print(json.dumps(r["metrics"], indent=1))
        for al in r["active"]:
            print(f"ALERT [{al['severity']}] {al['rule']}: {al['message']} (value {al['value']}, threshold {al['threshold']}, since {al['since']})")
        for t in r["transitions"]:
            print(f"-> {t['state']}: {t['rule']}")
        if not r["active"]:
            print("no active alerts")
        return
    if a.cmd == "history":
        sys.stdout.reconfigure(encoding="utf-8")
        for h in filing.Store(out).history(a.doc_id):
            print(f"v{h['version']}  {h['snapshot_ts']}  pipeline {h['pipeline_version']}  {h['decision']}  {h['folder']}  ({h['reason']})")
        return
    if a.cmd == "rollback":
        from . import pipeline
        if not a.actor:
            sys.exit("rollback needs --actor (it is written to the audit log)")
        try:
            if a.release:
                for r in pipeline.rollback_release(a.release, cfg, actor=a.actor, reason=a.reason):
                    print(r["doc_id"], r["status"], r.get("restored_version", ""), r.get("pipeline_version", ""))
            elif a.doc_id:
                r = pipeline.rollback(a.doc_id, cfg, a.version, actor=a.actor, reason=a.reason)
                print(f"restored {a.doc_id} v{r['restored_version']} (pipeline {r['pipeline_version']}) -> {r['path']}")
                if r.get("kb"):
                    print("kb:", r["kb"].get("ov_status"), r["kb"].get("ov_uri", ""))
            else:
                sys.exit("rollback needs <doc_id> or --release VERSION")
        except ValueError as e:
            sys.exit(str(e))
        return
    if a.cmd == "ocr":
        import pymupdf
        from . import llm, ocr
        src = Path(a.file)
        doc_id = filing.sha256_file(src)[:16]
        pdf = ocr.to_pdf(src, out / "_inbox" / doc_id)
        usage = llm.Usage()
        pages = ocr.ocr_pages(pymupdf.open(pdf), cfg, usage, llm.AuditLog(out / "audit.jsonl"), doc_id,
                              out / "_cache" / doc_id, force_llm=a.force_llm)
        md = ocr.to_markdown(pages, title=src.name)
        if a.out:
            Path(a.out).write_text(md, encoding="utf-8")
            print(f"wrote {a.out}: {ocr.summary(pages)} usage={usage.as_dict(cfg.model)}")
        else:
            sys.stdout.reconfigure(encoding="utf-8")
            print(md)
        return
    if a.cmd == "kb":
        from . import pipeline
        from .ov_adapter import OpenViking
        ov = OpenViking.from_cfg(cfg)
        sys.stdout.reconfigure(encoding="utf-8")
        if a.action == "status":
            print(json.dumps(ov.health(), indent=1))
            print("documents in OpenViking:", json.dumps(ov.document_folders(), indent=1, ensure_ascii=False))
        elif a.action == "tree":
            for e in ov.ls(recursive=True):
                if not e["name"].startswith("."):
                    print(("  " * e.get("rel_path", "").count("/")) + e["name"] + ("/" if e["isDir"] else ""))
        elif a.action == "search":
            for r in ov.find(a.arg or ""):
                print(r["score"], r["doc_id"], r["uri"])
        else:
            store = filing.Store(out)
            ids = [f.stem for f in (out / "_state").glob("*.json")] if a.arg in (None, "all") else [a.arg]
            for d in ids:
                if (store.state(d) or {}).get("status") == "filed":
                    r = pipeline.kb_sync(d, cfg)
                    print(d, r.get("ov_status"), r.get("ov_uri", ""), r.get("ov_errors") or "")
        return

    if a.cmd == "run":
        from . import pipeline
        for p in a.pdf:
            res = pipeline.process(Path(p), cfg, force=a.force)
            if res.get("skipped"):
                print(f"{p}: skipped (already {res['status']}) doc_id={res['doc_id']}")
                continue
            m = res["meta"]
            print(f"{p}: {res['decision']} doc_id={res['doc_id']} conf={res['confidence']} "
                  f"{m['company']} {m.get('fiscal_year')} {m.get('period')} {m.get('scope')} {m['doc_type']}")
            for c in res["checks"]:
                print(f"   [{c['status']}] {c['name']} {c['detail']}")
            for why in res["reasons"]:
                print(f"   reason: {why}")
            print(f"   usage: {res['usage']} in {res['seconds']}s")
    elif a.cmd == "review":
        store = filing.Store(out)
        if a.action == "list":
            for f in store.review_items():
                it = json.loads(f.read_text(encoding="utf-8"))["result"]
                print(f"{it['doc_id']}  {it['source_file']}  conf={it['confidence']}  reasons={it['reasons']}")
        elif a.action == "approve":
            if not (a.doc_id and a.reviewer):
                sys.exit("approve needs <doc_id> and --reviewer")
            from . import pipeline
            res = pipeline.approve(a.doc_id, a.reviewer, cfg)
            print(f"approved {a.doc_id} by {a.reviewer} -> {res['filed_path']}")
        else:
            if None in (a.doc_id, a.page, a.label, a.field, a.value) or not a.reviewer:
                sys.exit("correct needs <doc_id> --page --label --field --value --reviewer")
            from . import pipeline
            try:
                res = pipeline.correct(a.doc_id, a.page, a.label, a.field, a.value, a.reviewer, cfg)
            except ValueError as e:
                sys.exit(str(e))
            print(f"corrected -> {res['decision']} conf={res['confidence']} {res.get('filed_path', '')}")
            for why in res["reasons"]:
                print(f"   reason: {why}")
    elif a.cmd == "ask":
        from . import kb, llm, qa
        store = kb.build(cfg, out, a.backend)
        usage = llm.Usage()
        res = qa.ask(a.question, store, cfg, usage, audit=llm.AuditLog(out / "audit.jsonl"), clearance=a.clearance)
        print(res["answer"])
        print("not_found:" if res["not_found"] else "cited:", res["citations"])
        if res["invalid_citations"] or res["ungrounded_numbers"]:
            print("WARNING invalid citations:", res["invalid_citations"], "ungrounded numbers:", res["ungrounded_numbers"])
        print("retrieval:", getattr(store, "last_info", {"backend": "local"}))
        print("usage:", usage.as_dict(cfg.model))
    elif a.cmd == "kill":
        flag = out / cfg.governance.kill_switch_file
        flag.parent.mkdir(parents=True, exist_ok=True)
        if a.state == "on":
            flag.write_text("kill switch on\n")
        elif flag.exists():
            flag.unlink()
        print(f"kill switch {a.state}")


if __name__ == "__main__":
    main()
