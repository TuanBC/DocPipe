"""Concurrency / rate-limit probe for the subscription route.

Sends N small requests at several concurrency levels and records errors and latency.
Run: uv run --group gateway python -m evals.rate_probe
"""
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import litellm

from docpipe import config

N = 24


def one(model):
    t = time.time()
    try:
        r = litellm.completion(model=model, messages=[{"role": "user", "content": "Reply with the word ok."}])
        return ("ok", time.time() - t, r.usage.prompt_tokens)
    except Exception as e:  # noqa: BLE001
        return (type(e).__name__ + ": " + str(e)[:120], time.time() - t, 0)


def main():
    cfg = config.load()
    rows = []
    for workers in (1, 4, 8, 16):
        t0 = time.time()
        with ThreadPoolExecutor(workers) as ex:
            res = list(ex.map(lambda _: one(cfg.model.name), range(N)))
        wall = time.time() - t0
        errs = [r[0] for r in res if r[0] != "ok"]
        lat = [r[1] for r in res if r[0] == "ok"]
        row = {"workers": workers, "requests": N, "errors": len(errs), "error_sample": sorted(set(errs))[:3],
               "wall_s": round(wall, 1), "req_per_s": round(N / wall, 2),
               "p50_s": round(statistics.median(lat), 2) if lat else None,
               "max_s": round(max(lat), 2) if lat else None}
        rows.append(row)
        print(row)
        if len(errs) > N // 2:
            break
    Path("data/eval").mkdir(parents=True, exist_ok=True)
    Path("data/eval/rate_probe.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
