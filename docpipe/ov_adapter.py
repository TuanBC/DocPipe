"""OpenViking adapter: push filed documents into the OpenViking knowledge base, mirroring the folder layout, and query it.

Layout in OpenViking (same keys as the filing tree on disk):
    {root}/{company}/{year}/{period}/{doc_type}__{scope}__{doc_id}/...

Only the PII-masked KB export (`kb_export/{doc_id}.md`) is sent; the restricted mapping never leaves the machine.
OpenViking parses the Markdown by headings, builds semantic summaries with the gateway model and embeds every node.

HTTP API used (OpenViking 0.5.x): POST /api/v1/resources/temp_upload, POST /api/v1/resources, POST /api/v1/search/find,
GET /api/v1/fs/ls, GET /api/v1/content/read, DELETE /api/v1/fs. A target name ending in '.md' is treated as hidden by
the server, so document folders carry no extension.
"""
import re
import time
from pathlib import Path

import httpx

from .filing import folder_parts

DOC_ID = re.compile(r"(?<![0-9a-f])([0-9a-f]{16})(?![0-9a-f])")


class OVError(Exception):
    pass


class OpenViking:
    def __init__(self, url: str, api_key: str | None = None, root: str = "viking://resources/docpipe", timeout: float = 600):
        self.url = url.rstrip("/")
        self.root = root.rstrip("/")
        self.timeout = timeout
        self.headers = {"X-API-Key": api_key} if api_key else {}

    @classmethod
    def from_cfg(cls, cfg):
        o = cfg.kb.openviking
        return cls(o.url, o.api_key, o.root, o.timeout)

    # --- low level ---
    def _req(self, method, path, timeout=None, **kw):
        try:
            r = httpx.request(method, self.url + path, headers=self.headers, timeout=timeout or self.timeout, **kw)
        except httpx.HTTPError as e:
            raise OVError(f"OpenViking unreachable at {self.url}: {e}") from e
        try:
            body = r.json()
        except ValueError:
            raise OVError(f"{method} {path}: HTTP {r.status_code} {r.text[:200]}")
        if r.status_code >= 400 or body.get("status") not in (None, "ok"):
            err = body.get("error") or body.get("detail") or body
            raise OVError(f"{method} {path}: HTTP {r.status_code} {str(err)[:300]}")
        return body

    def health(self) -> dict:
        try:
            r = httpx.get(self.url + "/health", headers=self.headers, timeout=5)
            return {"ok": r.status_code == 200 and r.json().get("healthy", False), **r.json()}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    # --- layout ---
    def target_uri(self, result: dict) -> str:
        m = result["meta"]
        name = f"{m['doc_type']}__{m.get('scope') or 'unknown'}__{result['doc_id']}"
        return "/".join([self.root, *folder_parts(m), name])

    # --- write ---
    def remove(self, uri: str):
        try:
            return self._req("DELETE", "/api/v1/fs", params={"uri": uri, "recursive": "true"}, timeout=120)["result"]
        except OVError as e:
            if "404" in str(e) or "not found" in str(e).lower():
                return None
            raise

    def _prune_parents(self, uri: str):
        """Remove folders left empty (only hidden .abstract/.overview files) after a document moved."""
        parent = uri.rsplit("/", 1)[0]
        while parent.startswith(self.root + "/"):
            if any(not e.get("name", ".").startswith(".") for e in self.ls(parent)):
                break
            self.remove(parent)
            parent = parent.rsplit("/", 1)[0]

    def ingest(self, md_path: Path, result: dict, previous_uri: str | None = None, wait: bool = True) -> dict:
        """Upload one masked KB export to its folder. Replaces an earlier copy (previous location or legacy flat file)."""
        t0 = time.time()
        uri = self.target_uri(result)
        for old in {previous_uri, f"{self.root}/{result['doc_id']}.md", uri} - {None}:
            if self.remove(old) is not None and old != uri:
                self._prune_parents(old)
        with open(md_path, "rb") as f:
            up = self._req("POST", "/api/v1/resources/temp_upload", timeout=120,
                           files={"file": (f"{result['doc_id']}.md", f, "text/markdown")})
        tid = up["result"]["temp_file_id"]
        m = result["meta"]
        res = self._req("POST", "/api/v1/resources", json={
            "temp_file_id": tid, "to": uri, "create_parent": True, "wait": wait,
            "reason": f"docpipe filed document: {m['company']} {m.get('fiscal_year')} {m['doc_type']}",
        })["result"]
        errors = list(res.get("errors") or [])
        for q in (res.get("queue_status") or {}).values():
            errors += q.get("errors") or []
        # OpenViking reports success even when its semantic summaries failed (model errors are only logged server-side);
        # without summaries, search matches folder names only. Check the document's overview explicitly.
        status = "error" if errors else "ingested"
        if not errors and wait:
            try:
                if "[Directory overview is not generated]" in self.read(res.get("root_uri", uri) + "/.overview.md"):
                    status = "ingested_no_summary"
                    errors.append("semantic summary not generated (check the OpenViking VLM/gateway model; see server log)")
            except OVError:
                pass
        return {"ov_uri": res.get("root_uri", uri), "ov_status": status,
                "ov_errors": [str(e)[:200] for e in errors], "ov_seconds": round(time.time() - t0, 1),
                "ov_ts": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # --- read ---
    def find(self, query: str, limit: int = 8, target: str | None = None) -> list:
        res = self._req("POST", "/api/v1/search/find", timeout=120,
                        json={"query": query, "target_uri": target or self.root, "limit": limit})["result"]
        out = []
        for r in res.get("resources", []):
            m = DOC_ID.search(r["uri"])
            out.append({"uri": r["uri"], "doc_id": m.group(1) if m else None, "score": round(r.get("score") or 0, 4),
                        "level": r.get("level"), "abstract": (r.get("abstract") or "")[:400]})
        return out

    def find_docs(self, query: str, limit: int = 4) -> list:
        """Distinct document ids in rank order. Over-fetches because several nodes of one document can match."""
        docs = []
        for r in self.find(query, limit=limit * 4):
            if r["doc_id"] and r["doc_id"] not in docs:
                docs.append(r["doc_id"])
        return docs[:limit]

    def ls(self, uri: str | None = None, recursive: bool = False, levels: int = 6) -> list:
        """Directory listing. recursive uses /fs/tree, because /fs/ls?recursive stops at 3 levels and document folders
        sit at level 4 (company/year/period/document)."""
        try:
            if recursive:
                return self._req("GET", "/api/v1/fs/tree", timeout=60, params={
                    "uri": uri or self.root, "output": "original", "node_limit": 5000, "level_limit": levels})["result"]
            return self._req("GET", "/api/v1/fs/ls", timeout=60, params={
                "uri": uri or self.root, "output": "original", "show_all_hidden": "true", "node_limit": 5000})["result"]
        except OVError as e:
            if "404" in str(e) or "not found" in str(e).lower():
                return []
            raise

    def read(self, uri: str) -> str:
        return self._req("GET", "/api/v1/content/read", timeout=60, params={"uri": uri})["result"]

    def document_folders(self) -> dict:
        """{doc_id: uri} for every document folder under root (new layout and legacy flat files)."""
        out = {}
        for e in self.ls(recursive=True):
            name = e.get("name", "")
            if e.get("isDir") and not name.startswith(".") and (m := DOC_ID.search(name)):
                out.setdefault(m.group(1), e["uri"])
        return out
