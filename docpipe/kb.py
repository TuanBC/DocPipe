"""Knowledge-base adapter and a local backend (BM25 keyword retrieval, optional dense, with an access filter).

The pipeline talks to the KB only through `KBBackend`; `LocalKB` is the backend that runs without containers.
`OpenVikingKB` sits behind the same interface: OpenViking ranks documents semantically (docpipe/ov_adapter.py), and
the local index picks the cited pages inside those documents, so answers keep page-level citations.

Chunks are built from the filed sidecars (extraction JSON), not from the masked Markdown export, so every chunk
keeps its document id and page for citations, and carries the document's sensitivity label for the access filter.
"""
import json
import math
import os
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

LEVELS = {"public": 0, "internal": 1, "restricted": 2}
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LINES_PER_CHUNK = 30


@dataclass
class Chunk:
    id: str
    doc_id: str
    page: int
    company: str
    year: int | None
    sensitivity: str
    text: str


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def tokens(s: str) -> list:
    return re.findall(r"[a-z0-9]+", fold(s))


def fmt(v):
    if v is None:
        return "-"
    return f"{int(v):,}".replace(",", ".") if float(v).is_integer() else str(v)


# Canonical names for headline rows, keyed by the validators' label patterns. Issuers print "TỔNG CỘNG TÀI SẢN",
# "Tổng lợi nhuận kế toán trước thuế", ...; tagging the recognised row with the plain name analysts ask for keeps
# the headline figure retrievable when a long balance sheet is split across chunks.
CANONICAL = {"total_assets": "Tổng tài sản (total assets)", "total_le": "Tổng nguồn vốn (total liabilities and equity)",
             "liabilities": "Nợ phải trả (total liabilities)", "equity": "Vốn chủ sở hữu (equity)",
             "revenue": "Doanh thu thuần (net revenue)", "pbt": "Lợi nhuận trước thuế (profit before tax)",
             "net_profit": "Lợi nhuận sau thuế (net profit)", "bs_cash": "Tiền và tương đương tiền (cash)"}


def _canonical(label: str) -> str:
    from .validators import PATTERNS, norm
    n = norm(label)
    return next((name for key, name in CANONICAL.items() if PATTERNS[key].match(n)), "")


def chunks_from_result(result: dict) -> list:
    m = result["meta"]
    out = []
    for page, ex in result["extraction"].items():
        head = (f"Công ty: {m['company']} | Năm: {m.get('fiscal_year')} | Kỳ: {m.get('period')} | Phạm vi: {m.get('scope')} | "
                f"Loại: {m['doc_type']} | Trang {page} ({ex['page_type']}), đơn vị {ex['unit']}; cột {ex['period_current']} / {ex['period_prior']}")
        items = ex["items"]
        for i in range(0, len(items), LINES_PER_CHUNK):
            lines = []
            for it in items[i:i + LINES_PER_CHUNK]:
                tag = _canonical(it["label"])
                lines.append(f"- {it['label']}{' [' + tag + ']' if tag else ''}: {ex['period_current']} = {fmt(it['current'])}; "
                             f"{ex['period_prior']} = {fmt(it['prior'])}")
            out.append(Chunk(id=f"{result['doc_id']}:p{page}:{i // LINES_PER_CHUNK}", doc_id=result["doc_id"], page=int(page),
                             company=m["company"], year=m.get("fiscal_year"), sensitivity=result.get("sensitivity", "internal"),
                             text=head + "\n" + "\n".join(lines)))
    return out


_LEGAL_WORDS = {"cong", "ty", "co", "phan", "tnhh", "trach", "nhiem", "huu", "han", "ctcp", "tap", "doan", "ngan", "hang",
                "thuong", "mai", "tmcp", "jsc", "mtv", "thanh", "vien"}
_company_cache: dict = {}


def _company_named(company: str, qset: set) -> bool:
    core = _company_cache.get(company)
    if core is None:
        core = _company_cache[company] = frozenset(t for t in tokens(company) if t not in _LEGAL_WORDS and len(t) > 1)
    return bool(core) and core <= qset


FULLTEXT_CHARS = 1500
_PAGE_HEAD = re.compile(r"^## Page (\d+)[^\n]*$", re.M)


def chunks_from_fulltext(result: dict, md: str) -> list:
    """Chunks from the masked OCR/full text (used for documents without extracted statement tables)."""
    m = result["meta"]
    head = (f"Công ty: {m['company']} | Năm: {m.get('fiscal_year')} | Loại: {m['doc_type']} | "
            f"Tệp: {result.get('source_file', '')}")
    parts = _PAGE_HEAD.split(md)
    out = []
    for j in range(1, len(parts) - 1, 2):
        page, text = int(parts[j]), parts[j + 1].strip()
        for k in range(0, len(text), FULLTEXT_CHARS):
            if text[k:k + FULLTEXT_CHARS].strip():
                out.append(Chunk(id=f"{result['doc_id']}:p{page}:t{k // FULLTEXT_CHARS}", doc_id=result["doc_id"], page=page,
                                 company=m["company"], year=m.get("fiscal_year"), sensitivity=result.get("sensitivity", "internal"),
                                 text=f"{head} | Trang {page}\n{text[k:k + FULLTEXT_CHARS]}"))
    return out


class KBBackend:
    def add(self, chunks: list):  # pragma: no cover - interface
        raise NotImplementedError

    def search(self, query: str, k: int = 6, clearance: str = "internal") -> list:
        raise NotImplementedError


class LocalKB(KBBackend):
    """BM25 over accent-folded tokens, plus optional dense embeddings (DOCPIPE_DENSE=1).

    Dense retrieval is off by default: the multilingual ONNX embedding model failed to load on the dev machine
    (commit limit, 'bad allocation'), so every measured result in docs/eval-results.md is BM25-only unless stated.
    """

    K1, B = 1.5, 0.75
    COMPANY_BOOST = 1.0

    def __init__(self, dense=None):
        self.dense = (os.environ.get("DOCPIPE_DENSE") == "1") if dense is None else dense
        self.chunks: list = []
        self._vecs = None
        self._model = None
        self._toks: list = []

    # --- build ---
    def _embed(self, texts):
        """Dense vectors. DOCPIPE_EMBED_MODEL (a LiteLLM model id such as github_copilot/text-embedding-3-small)
        uses a hosted/gateway endpoint; otherwise the local fastembed ONNX model."""
        import numpy as np
        remote = os.environ.get("DOCPIPE_EMBED_MODEL")
        if remote:
            import litellm
            kw = {"api_base": os.environ["DOCPIPE_EMBED_API_BASE"], "api_key": os.environ.get("DOCPIPE_API_KEY")} \
                if os.environ.get("DOCPIPE_EMBED_API_BASE") else {}
            rows = []
            for i in range(0, len(texts), 64):
                rows += [d["embedding"] for d in litellm.embedding(model=remote, input=texts[i:i + 64], **kw).data]
            v = np.array(rows, dtype="float32")
        else:
            from fastembed import TextEmbedding
            if self._model is None:
                self._model = TextEmbedding(model_name=EMBED_MODEL)
            v = np.array(list(self._model.embed(texts)), dtype="float32")
        return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)

    def add(self, chunks: list):
        self.chunks += chunks
        self._toks += [tokens(c.text) for c in chunks]
        if self.dense:
            import numpy as np
            new = self._embed([c.text for c in chunks])
            self._vecs = new if self._vecs is None else np.vstack([self._vecs, new])

    def load_filed(self, out: Path):
        for f in sorted((out / "filed").rglob("*.json")):
            result = json.loads(f.read_text(encoding="utf-8"))
            chunks = chunks_from_result(result)
            ft = out / "fulltext" / f"{result['doc_id']}.md"
            if not chunks and ft.exists():
                chunks = chunks_from_fulltext(result, ft.read_text(encoding="utf-8"))
            if chunks:
                self.add(chunks)
        return self

    # --- query ---
    def _bm25(self, q_tokens, idxs):
        n = len(self._toks)
        avgdl = sum(len(t) for t in self._toks) / max(n, 1)
        df = Counter(tok for t in self._toks for tok in set(t))
        scores = []
        for i in idxs:
            tf, dl, s = Counter(self._toks[i]), len(self._toks[i]), 0.0
            for tok in set(q_tokens):
                if tok in tf:
                    idf = math.log(1 + (n - df[tok] + 0.5) / (df[tok] + 0.5))
                    s += idf * tf[tok] * (self.K1 + 1) / (tf[tok] + self.K1 * (1 - self.B + self.B * dl / avgdl))
            scores.append(s)
        # Phrase bonus: word pairs from the question that occur adjacently in the chunk ("tổng tài sản" is
        # informative; "tổng", "tài", "sản" alone occur in every statement). One IDF-weighted term per matching pair.
        q_bi = set(zip(q_tokens, q_tokens[1:]))
        if q_bi:
            bis = [set(zip(t, t[1:])) for t in self._toks]
            bdf = Counter(b for s in bis for b in s if b in q_bi)
            for j, i in enumerate(idxs):
                scores[j] += sum(math.log(1 + (n - bdf[b] + 0.5) / (bdf[b] + 0.5)) for b in q_bi & bis[i])
        return scores

    def search(self, query: str, k: int = 6, clearance: str = "internal") -> list:
        allowed = [i for i, c in enumerate(self.chunks) if LEVELS[c.sensitivity] <= LEVELS[clearance]]
        if not allowed:
            return []
        q_toks = tokens(query)
        bm = self._bm25(q_toks, allowed)
        # Company-aware ranking: BM25 alone lets short prose chunks of another company (a contract page sharing
        # "công ty cổ phần ... tài sản ... năm 2025") outrank the asked company's balance sheet. A chunk whose company
        # name (legal-form words removed) is fully named in the question is boosted; nothing is penalised, so
        # questions using an alias (Vinamilk, HPG) rank exactly as before.
        qset = set(q_toks)
        bm = [b * (1 + self.COMPANY_BOOST) if b and _company_named(self.chunks[i].company, qset) else b
              for b, i in zip(bm, allowed)]
        top = max(bm) or 1.0
        score = [b / top for b in bm]
        if self.dense and self._vecs is not None:
            dense = self._vecs[allowed] @ self._embed([query])[0]
            score = [0.5 * s + 0.5 * float(d) for s, d in zip(score, dense)]
        order = sorted(range(len(allowed)), key=lambda j: -score[j])[:k]
        return [(float(score[j]), self.chunks[allowed[j]]) for j in order if score[j] > 0]

    # --- persistence ---
    def save(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        (path / "chunks.json").write_text(json.dumps([asdict(c) for c in self.chunks], ensure_ascii=False), encoding="utf-8")
        if self._vecs is not None:
            import numpy as np
            np.save(path / "vectors.npy", self._vecs)

    @classmethod
    def load(cls, path: Path):
        kb = cls(dense=(path / "vectors.npy").exists())
        kb.chunks = [Chunk(**c) for c in json.loads((path / "chunks.json").read_text(encoding="utf-8"))]
        kb._toks = [tokens(c.text) for c in kb.chunks]
        if kb.dense:
            import numpy as np
            kb._vecs = np.load(path / "vectors.npy")
        return kb


class OpenVikingKB(KBBackend):
    """OpenViking picks the documents (semantic, over the masked exports); the local index picks pages inside them.

    The access filter stays local: chunks above the caller's clearance are never returned, whatever OpenViking ranks.
    If OpenViking is unreachable or returns no known document, it falls back to the local ranking (and says so).
    """

    def __init__(self, local: LocalKB, ov, docs_k: int = 3):
        self.local, self.ov, self.docs_k = local, ov, docs_k
        self.last_info: dict = {}

    def search(self, query: str, k: int = 6, clearance: str = "internal") -> list:
        try:
            docs = self.ov.find_docs(query, limit=self.docs_k)
        except Exception as e:  # noqa: BLE001 - degrade to local retrieval, report why
            self.last_info = {"backend": "local (openviking failed)", "error": str(e)[:200]}
            return self.local.search(query, k=k, clearance=clearance)
        known = {c.doc_id for c in self.local.chunks}
        docs = [d for d in docs if d in known]
        if not docs:
            self.last_info = {"backend": "local (openviking returned no filed document)", "ov_docs": []}
            return self.local.search(query, k=k, clearance=clearance)
        self.last_info = {"backend": "openviking", "ov_docs": docs}
        hits = self.local.search(query, k=len(self.local.chunks) or 1, clearance=clearance)
        rank = {d: i for i, d in enumerate(docs)}
        inside = [h for h in hits if h[1].doc_id in rank]
        # keep OpenViking's document order as the primary key, local page score inside each document
        inside.sort(key=lambda h: (rank[h[1].doc_id], -h[0]))
        per_doc, out = {}, []
        for s, c in inside:
            if per_doc.get(c.doc_id, 0) < max(2, k // len(docs)):
                per_doc[c.doc_id] = per_doc.get(c.doc_id, 0) + 1
                out.append((s, c))
        return out[:k]


def build(cfg, out: Path, backend: str | None = None):
    """KB for Q&A according to cfg.kb.backend (or an explicit override): 'local' or 'openviking'."""
    local = LocalKB().load_filed(out)
    if (backend or cfg.kb.backend) == "openviking":
        from .ov_adapter import OpenViking
        return OpenVikingKB(local, OpenViking.from_cfg(cfg))
    return local
