"""OpenAI-compatible /v1/embeddings served on CPU with fastembed (ONNX, no torch).

Why: the subscription (chatgpt/) route has no embeddings endpoint, and OpenViking needs one.
The model is multilingual (Vietnamese included), 384 dimensions, small enough for a laptop.

Run: uv run --group kb uvicorn services.embed_server:app --host 127.0.0.1 --port 8081
"""
import os
import time
from typing import List, Union

from fastapi import FastAPI
from fastembed import TextEmbedding
from pydantic import BaseModel

MODEL = os.environ.get("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
app = FastAPI(title="embed-server")
_model = TextEmbedding(model_name=MODEL)


class Req(BaseModel):
    input: Union[str, List[str]]
    model: str = MODEL


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post("/v1/embeddings")
def embeddings(req: Req):
    texts = [req.input] if isinstance(req.input, str) else req.input
    t0 = time.time()
    vecs = [v.tolist() for v in _model.embed(texts)]
    n_tokens = sum(len(t.split()) for t in texts)  # rough; this server is not a billing source
    return {
        "object": "list", "model": req.model,
        "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vecs)],
        "usage": {"prompt_tokens": n_tokens, "total_tokens": n_tokens, "seconds": round(time.time() - t0, 3)},
    }
