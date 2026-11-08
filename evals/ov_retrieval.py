"""Document-level retrieval: OpenViking semantic find vs the local BM25 backend, on the kb_qa questions.

Needs the OpenViking server on :1933 with the kb_export files ingested under viking://resources/docpipe/
(see docs/eval-results.md section 7d). No model calls. Questions whose answer lives in a known document are scored by
whether that document id appears in the top-k results.
Run: uv run python -m evals.ov_retrieval
"""
import json
import re
import urllib.request
from pathlib import Path

from docpipe import kb
from evals.kb_qa import OUT, build_questions

URL = "http://127.0.0.1:1933/api/v1/search/find"


def ov_docs(query: str, limit: int = 4) -> list:
    req = urllib.request.Request(URL, data=json.dumps({"query": query, "target_uri": "viking://resources/docpipe", "limit": limit}).encode(),
                                 headers={"Content-Type": "application/json"})
    res = json.loads(urllib.request.urlopen(req, timeout=60).read())["result"]["resources"]
    out = []
    for r in res:
        m = re.search(r"docpipe/([0-9a-f]{16})\.md", r["uri"])
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def main():
    qs = [q for q in build_questions(None) if q["kind"] in ("answerable", "answerable_prior", "alias")]
    store = kb.LocalKB().load_filed(OUT)
    rows = {"ov": {1: 0, 2: 0, 4: 0}, "bm25": {1: 0, 2: 0, 4: 0}}
    for q in qs:
        o = ov_docs(q["q"])
        b = []
        for _, c in store.search(q["q"], k=12):
            if c.doc_id not in b:
                b.append(c.doc_id)
        for name, docs in (("ov", o), ("bm25", b)):
            for k in (1, 2, 4):
                rows[name][k] += q["doc_id"] in docs[:k]
    n = len(qs)
    print(f"questions: {n}")
    for name in rows:
        print(name, {f"hit@{k}": f"{v}/{n}" for k, v in rows[name].items()})
    Path("data/eval").mkdir(parents=True, exist_ok=True)
    Path("data/eval/ov_retrieval.json").write_text(json.dumps({"n": n, **rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
