"""OpenAI-compatible /v1/embeddings that needs no model: feature-hashed lexical vectors.

Why this exists: the dev machine runs close to its memory commit limit and could not load the multilingual ONNX
embedding model, and the subscription route has no embeddings endpoint. OpenViking needs *an* embedding endpoint.
This one hashes accent-folded word unigrams, bigrams and character trigrams into a fixed-size vector (sublinear
term frequency, L2-normalised). Quality is lexical, not semantic: it finds shared words, not paraphrases.
Use a real multilingual embedding model (see services/embed_server.py or TEI in deploy/compose.yaml) for production.

Run: uv run --group gateway uvicorn services.hash_embed_server:app --host 127.0.0.1 --port 8081
"""
import math
import re
import unicodedata
import zlib
from typing import List, Union

from fastapi import FastAPI
from pydantic import BaseModel

DIM = 512
MODEL = "hash-embed-512"
app = FastAPI(title="hash-embed-server")


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def features(text: str):
    words = re.findall(r"[a-z0-9]+", fold(text))
    for w in words:
        yield "w:" + w
        padded = f"^{w}$"
        for i in range(len(padded) - 2):
            yield "c:" + padded[i:i + 3]
    for a, b in zip(words, words[1:]):
        yield f"b:{a}_{b}"


def embed(text: str) -> List[float]:
    v = [0.0] * DIM
    counts = {}
    for f in features(text):
        counts[f] = counts.get(f, 0) + 1
    for f, c in counts.items():
        h = zlib.crc32(f.encode())
        sign = 1.0 if (h >> 16) & 1 else -1.0
        v[h % DIM] += sign * (1.0 + math.log(c))
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


class Req(BaseModel):
    input: Union[str, List[str]]
    model: str = MODEL


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL, "dimension": DIM}


@app.post("/v1/embeddings")
def embeddings(req: Req):
    texts = [req.input] if isinstance(req.input, str) else req.input
    n = sum(len(t.split()) for t in texts)
    return {"object": "list", "model": req.model,
            "data": [{"object": "embedding", "index": i, "embedding": embed(t)} for i, t in enumerate(texts)],
            "usage": {"prompt_tokens": n, "total_tokens": n}}
