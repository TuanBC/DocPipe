"""Build a read-only static snapshot of the DocPipe web UI for public hosting (e.g. Vercel).

The real UI needs the local stack (LiteLLM, OpenViking, Hermes, the job worker, data/out). This script reads every GET
endpoint of a running UI (default http://127.0.0.1:8800), records saved answers for a few Q&A and Agent questions,
renders page images, and writes a static site whose fetch() shim (scripts/demo_shim.js) serves those files. Writes
are refused in the snapshot with a message pointing to the local setup.

    uv run python scripts/build_demo_site.py            # -> dist/docpipe-demo/
    vercel deploy dist/docpipe-demo --prod

Privacy: documents listed in EXCLUDE (personal or internal files uploaded during testing) are dropped everywhere.
_restricted/ (the PII mapping) is never read. Full text and KB content are the PII-masked versions.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "docpipe" / "web" / "static" / "index.html"
REPO = "https://github.com/TuanBC/DocPipe"

# Uploaded during testing; personal or internal, not for a public site.
EXCLUDE = {"2da23cb2c51720b3", "ef614605626cb253", "f5b6629f7c7ca4b9"}

ASK_QUESTIONS = [
    "Tổng tài sản của Vinamilk năm 2025?",
    "Vốn điều lệ của An Phát?",
    "Hợp đồng vay của Hưng Thịnh: số tiền, thời hạn, lãi suất?",
]
AGENT_QUESTIONS = [  # same as AG_EXAMPLES in index.html
    "Hợp đồng cho vay của Công ty Cổ phần Xây dựng Hưng Thịnh: số tiền vay, thời hạn và lãi suất là bao nhiêu?",
    "Vốn điều lệ của Công ty Thương mại An Phát là bao nhiêu?",
    "Tổng tài sản của Vinamilk tại 31/12/2025?",
    "Lãi suất hợp đồng vay của Vietcombank với An Phát là bao nhiêu?",
]
PDF_MAX_BYTES = 4_000_000
SHORT_DOC_PAGES = 20            # documents up to this length keep every page image
LONG_DOC_FIRST = 8              # longer ones keep their first pages, statement pages and cited pages
PAGE_DPI, PAGE_QUALITY = 100, 60
LONG_DPI, LONG_QUALITY = 80, 50
NOPAGE_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="620" height="200" viewBox="0 0 620 200">'
              '<rect width="620" height="200" fill="#f4f4f2" stroke="#ccc"/><text x="310" y="92" font-family="sans-serif" '
              'font-size="16" text-anchor="middle" fill="#555">This page image is not in the demo snapshot.</text>'
              '<text x="310" y="120" font-family="sans-serif" font-size="14" text-anchor="middle" fill="#777">'
              'Large public reports keep their first pages, statement pages and cited pages.</text></svg>')


def key(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def norm(q: str) -> str:
    return " ".join(q.lower().split()).rstrip("?").strip()


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def raw(self, path: str, body: dict | None = None, timeout: int = 300) -> bytes:
        req = urllib.request.Request(self.base + path, method="POST" if body is not None else "GET",
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"} if body is not None else {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()

    def get(self, path: str):
        return json.loads(self.raw(path))

    def text(self, path: str) -> str:
        return self.raw(path).decode("utf-8")


def drop_excluded(node):
    """Remove excluded documents from any nested structure (tree, job results)."""
    if isinstance(node, dict):
        return {k: drop_excluded(v) for k, v in node.items() if k not in EXCLUDE}
    if isinstance(node, list):
        return [drop_excluded(v) for v in node
                if not (isinstance(v, dict) and v.get("doc_id") in EXCLUDE)]
    return node


def mentions_excluded(obj) -> bool:
    s = json.dumps(obj, ensure_ascii=False)
    return any(x in s for x in EXCLUDE)


def write(path: Path, data, text: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    elif text:
        path.write_text(data, encoding="utf-8", newline="")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def record_agent(api: Api, question: str) -> list:
    """Run one Hermes question through the live UI and keep the NDJSON events with their arrival times."""
    req = urllib.request.Request(api.base + "/api/agent/ask", method="POST",
                                 data=json.dumps({"question": question}).encode(),
                                 headers={"Content-Type": "application/json"})
    events, t0 = [], time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        for line in r:
            line = line.strip()
            if line:
                events.append({"t": round(time.time() - t0, 2), "ev": json.loads(line)})
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8800")
    ap.add_argument("--out", default=str(ROOT / "dist" / "docpipe-demo"))
    ap.add_argument("--reuse-answers", action="store_true",
                    help="keep saved Q&A and agent answers from a previous build instead of asking again")
    a = ap.parse_args()
    api, out = Api(a.base), Path(a.out)
    snap = out / "snap"
    old = {}
    for name in ("ask.json", "agent.json"):
        if a.reuse_answers and (snap / name).exists():
            old[name] = json.loads((snap / name).read_text(encoding="utf-8"))
    if out.exists():
        shutil.rmtree(out)
    taken = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ---- system ----
    status = api.get("/api/status")
    docs = [d for d in api.get("/api/documents") if d["doc_id"] not in EXCLUDE]
    status["counts"]["filed"] = sum(d["status"] == "filed" for d in docs)
    status["counts"]["review"] = sum(d["status"] == "review" for d in docs)
    status["counts"]["jobs_active"] = 0
    status["demo"] = {"taken": taken, "repo": REPO}
    for s in status.get("services", {}).values():
        s["detail"] = f"{s.get('detail', '')} · at snapshot time"
    write(snap / "status.json", status)
    mon = api.get("/api/monitor")
    mon["metrics"]["review_queue_size"] = status["counts"]["review"]
    write(snap / "monitor.json", mon)
    jobs = [j for j in api.get("/api/jobs") if not mentions_excluded({k: v for k, v in j.items() if k != "result"})]
    jobs = drop_excluded(jobs)
    for j in jobs:
        write(snap / "jobs" / f"{j['id']}.json", drop_excluded(api.get(f"/api/jobs/{j['id']}/events")))
    write(snap / "jobs.json", jobs)
    write(snap / "tree.json", drop_excluded(api.get("/api/tree")))
    write(snap / "documents.json", docs)

    # ---- saved answers ----
    asks = old.get("ask.json")
    if asks is None:
        asks = {}
        for q in ASK_QUESTIONS:
            r = json.loads(api.raw("/api/ask", {"question": q, "backend": "openviking", "clearance": "internal"}))
            asks[norm(q)] = {"question": q, "answer": r}
            print("ask:", q, "->", r.get("answer", "")[:80], flush=True)
    write(snap / "ask.json", asks)
    agent = old.get("agent.json")
    if agent is None:
        agent = {}
        for q in AGENT_QUESTIONS:
            t0 = time.time()
            agent[norm(q)] = {"question": q, "events": record_agent(api, q)}
            print(f"agent: {q[:50]}… {time.time() - t0:.0f}s", flush=True)
    write(snap / "agent.json", agent)

    cited: dict[str, set[int]] = {}
    for s in asks.values():
        for c in s["answer"].get("citations") or []:
            cited.setdefault(c["doc_id"], set()).add(int(c["page"]))

    # ---- documents ----
    pdfs = {}
    for d in docs:
        i = d["doc_id"]
        full = api.get(f"/api/documents/{i}")
        write(snap / "doc" / f"{i}.json", full)
        try:
            write(snap / "doc" / f"{i}.history.json", api.get(f"/api/documents/{i}/history"))
        except Exception:  # noqa: BLE001 - no history is a normal state
            write(snap / "doc" / f"{i}.history.json", [])
        if full.get("has_fulltext"):
            write(snap / "doc" / f"{i}.fulltext.txt", api.text(f"/api/documents/{i}/fulltext"), text=True)
        pdf = api.raw(f"/api/documents/{i}/file")
        if len(pdf) <= PDF_MAX_BYTES:
            write(snap / "pdf" / f"{i}.pdf", pdf)
            pdfs[i] = True
        doc = pymupdf.open(stream=pdf, filetype="pdf")
        keep = set(range(1, len(doc) + 1))
        if len(doc) > SHORT_DOC_PAGES:  # long public reports: cover pages, statement pages, cited pages
            keep = set(range(1, LONG_DOC_FIRST + 1)) | {int(p) for p in full["result"].get("statement_pages") or {}}
            keep |= cited.get(i, set())
        dpi, q = (PAGE_DPI, PAGE_QUALITY) if len(doc) <= SHORT_DOC_PAGES else (LONG_DPI, LONG_QUALITY)
        for n in sorted(k for k in keep if 1 <= k <= len(doc)):
            pix = doc[n - 1].get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72))
            buf = io.BytesIO()
            Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(buf, "WEBP", quality=q, method=4)
            write(snap / "page" / i / f"{n}.webp", buf.getvalue())
        print(f"doc {i} · {len(keep)}/{len(doc)} pages · pdf {'included' if i in pdfs else 'too large, left out'}",
              flush=True)
    write(snap / "pdfs.json", pdfs)
    write(snap / "nopage.svg", NOPAGE_SVG, text=True)

    # ---- knowledge base ----
    kb_tree = api.get("/api/kb/tree")
    write(snap / "kb" / "tree.json", kb_tree)
    index = {}
    for u in sorted({e["uri"] for e in kb_tree}):
        try:
            t = api.text("/api/kb/read?uri=" + urllib.parse.quote(u, safe=""))
        except Exception as e:  # noqa: BLE001 - a node without an overview is shown as unavailable
            t = f"(not available in the snapshot: {e})"
        write(snap / "kb" / "read" / f"{key(u)}.txt", t, text=True)
        index[u] = t[:4000]
    write(snap / "kb" / "index.json", index)
    print(f"kb: {len(index)} nodes", flush=True)

    # ---- page ----
    html = STATIC.read_text(encoding="utf-8")
    for old_s, new_s in [("/api/documents/${id}/page/${p}.png?dpi=110", "snap/page/${id}/${p}.webp"),
                         ('href="/api/documents/${id}/file"', 'href="${pdfHref(id)}"')]:
        assert old_s in html, f"index.html changed; update the build script ({old_s})"
        html = html.replace(old_s, new_s)
    shim = (ROOT / "scripts" / "demo_shim.js").read_text(encoding="utf-8")
    banner = (f'<div id="demo-banner">Read-only demo snapshot, taken {taken}. Uploads, approvals and new questions '
              f'need the local stack; the suggested questions replay recorded answers. '
              f'<a href="{REPO}" target="_blank" rel="noopener">Source and setup on GitHub</a></div>')
    style = ("<style>#demo-banner{background:#fff4d6;color:#5a4300;border-bottom:1px solid #e8d49a;padding:8px 16px;"
             "font-size:13px;line-height:1.4}#demo-banner a{color:inherit;text-decoration:underline}"
             "@media (prefers-color-scheme: dark){#demo-banner{background:#3a2f12;color:#f3e2b3;border-color:#5a4a1e}}"
             "</style>")
    html = html.replace("</head>", style + "\n</head>", 1)
    html = html.replace("<body>", "<body>\n" + banner, 1)
    html = html.replace("<script>", "<script>\n" + shim + "\n</script>\n<script>", 1)
    html = html.replace("<title>", '<meta name="robots" content="noindex">\n<title>', 1)
    write(out / "index.html", html, text=True)
    write(snap / "nopdf.html", '<!doctype html><meta charset="utf-8"><meta name="viewport" '
          'content="width=device-width,initial-scale=1"><title>PDF not included</title><body style="font:15px '
          'system-ui;max-width:560px;margin:40px auto;padding:0 16px">This PDF is too large for the demo snapshot. '
          'Every page is in the viewer (Pages tab).</body>', text=True)
    write(out / "vercel.json", {"headers": [{"source": "/snap/(.*)", "headers": [
        {"key": "Cache-Control", "value": "public, max-age=3600"}]}]})
    files = [f for f in out.rglob("*") if f.is_file()]
    print(f"wrote {out} · {len(files)} files · {sum(f.stat().st_size for f in files) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
