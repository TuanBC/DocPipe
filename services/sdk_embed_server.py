"""OpenAI-compatible /v1/embeddings that forwards to any LiteLLM SDK embedding model.

Why: the LiteLLM *proxy* cannot use the SDK's GitHub Copilot sign-in (its Copilot provider needs per-user OAuth stored
in the proxy database), but the SDK can. This shim runs in the SDK process and exposes the result as a plain OpenAI-style
endpoint, which the proxy and OpenViking can call.

Env: EMBED_BACKEND_MODEL (default github_copilot/text-embedding-3-small)
Run: uv run --group gateway uvicorn services.sdk_embed_server:app --host 127.0.0.1 --port 8081
"""
import os
from typing import List, Union

import litellm
from fastapi import FastAPI
from pydantic import BaseModel

BACKEND = os.environ.get("EMBED_BACKEND_MODEL", "github_copilot/text-embedding-3-small")
app = FastAPI(title="sdk-embed-server")


class Req(BaseModel):
    input: Union[str, List[str]]
    model: str = BACKEND


@app.get("/health")
def health():
    return {"status": "ok", "backend": BACKEND}


@app.post("/v1/embeddings")
def embeddings(req: Req):
    texts = [req.input] if isinstance(req.input, str) else req.input
    r = litellm.embedding(model=BACKEND, input=texts)
    return {"object": "list", "model": req.model,
            "data": [{"object": "embedding", "index": i, "embedding": d["embedding"]} for i, d in enumerate(r.data)],
            "usage": {"prompt_tokens": r.usage.prompt_tokens, "total_tokens": r.usage.total_tokens}}
