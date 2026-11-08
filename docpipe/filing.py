"""Filing: folder layout, sidecar JSON, masked KB export, review queue, idempotent state."""
import hashlib
import json
import re
import shutil
import unicodedata
from pathlib import Path

PIPELINE_VERSION = "0.3"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "unknown"


_LEGAL = re.compile(r"^(cong-ty-co-phan|cong-ty-tnhh|cong-ty-trach-nhiem-huu-han|ctcp|tap-doan)-")


def slug_company(name: str) -> str:
    """Folder key for a company: drop parentheticals and legal-form prefixes so name variants share a folder."""
    s = re.sub(r"\([^)]*\)", " ", name)
    s = slug(s)
    prev = None
    while prev != s:
        prev, s = s, _LEGAL.sub("", s)
    return s or "unknown"


def folder_parts(meta: dict) -> list:
    """Folder keys shared by the disk tree and the OpenViking tree: company / year / period.
    Documents without a reporting period (contracts, registrations, invoices) use their doc type instead of 'unknown'."""
    period = meta.get("period") or "unknown"
    return [slug_company(meta["company"]), str(meta.get("fiscal_year") or "unknown-year"),
            period if period != "unknown" else meta.get("doc_type") or "unknown"]


class Store:
    def __init__(self, out: Path):
        self.out = out
        for d in ("filed", "_review", "_state", "_restricted", "_cache", "_corrections", "kb_export", "fulltext", "_inbox"):
            (out / d).mkdir(parents=True, exist_ok=True)

    # --- state (idempotency) ---
    def state(self, doc_id):
        f = self.out / "_state" / f"{doc_id}.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

    def set_state(self, doc_id, **kw):
        (self.out / "_state" / f"{doc_id}.json").write_text(json.dumps(kw, ensure_ascii=False, indent=1), encoding="utf-8")

    def cache_dir(self, doc_id):
        return self.out / "_cache" / doc_id

    # --- kill switch ---
    def killed(self, cfg) -> bool:
        return (self.out / cfg.governance.kill_switch_file).exists()

    # --- filing ---
    def target_dir(self, meta) -> Path:
        return self.out / "filed" / Path(*folder_parts(meta))

    def file_document(self, result: dict, source: Path, kb_markdown: str, restricted: dict) -> Path:
        meta = result["meta"]
        audited = {True: "audited", False: "unaudited", None: "audit-unknown"}[meta.get("audited")]
        base = f"{meta['doc_type']}__{meta.get('scope', 'unknown')}__{audited}__{result['doc_id']}"
        d = self.target_dir(meta)
        for old in list((self.out / "filed").rglob(f"*__{result['doc_id']}.*")):
            old.unlink()  # re-filing replaces earlier copies (e.g. a corrected scope)
            parent = old.parent
            while parent != self.out / "filed" and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()  # drop folders the move left empty
                parent = parent.parent
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, d / f"{base}.pdf")
        (d / f"{base}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        (self.out / "kb_export" / f"{result['doc_id']}.md").write_text(kb_markdown, encoding="utf-8")
        (self.out / "_restricted" / f"{result['doc_id']}.json").write_text(
            json.dumps(restricted, ensure_ascii=False, indent=1), encoding="utf-8")
        return d / f"{base}.json"

    # --- review queue ---
    def queue_review(self, result: dict, source: Path, kb_markdown: str, restricted: dict, pdf: Path | None = None):
        """source = the original upload (re-runs hash it, so the doc_id stays stable); pdf = the file to file on
        approval (differs from source when an image was converted)."""
        item = {"result": result, "source": str(source.resolve()), "kb_markdown": kb_markdown, "restricted": restricted,
                "pdf": str((pdf or source).resolve())}
        (self.out / "_review" / f"{result['doc_id']}.json").write_text(json.dumps(item, ensure_ascii=False, indent=1), encoding="utf-8")

    def review_items(self):
        return sorted((self.out / "_review").glob("*.json"))

    def pop_review(self, doc_id):
        f = self.out / "_review" / f"{doc_id}.json"
        item = json.loads(f.read_text(encoding="utf-8"))
        return f, item

    # --- human corrections ---
    def corrections(self, doc_id) -> list:
        f = self.out / "_corrections" / f"{doc_id}.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

    def add_correction(self, doc_id, entry):
        f = self.out / "_corrections" / f"{doc_id}.json"
        f.write_text(json.dumps(self.corrections(doc_id) + [entry], ensure_ascii=False, indent=1), encoding="utf-8")
